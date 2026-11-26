"""
Notification — всплывающие уведомления плагина Reminder (об ошибках и об
успешных операциях): заголовок + текст + кнопка закрытия.

Отдельный сквозной компонент (решение пользователя 2026-11-25): сущность не
принадлежит ни странице, ни форме. До этого логика была размазана по
IssuePage.has_recipients_visibility_warning_flag() и
ReminderModal.invalid_url_error_text() — с одинаковым угадыванием контекста.

============================================================================
НАХОДКИ ПО РАЗМЕТКЕ (2026-11-25, по HTML success- и error-флагов)
============================================================================

1. Это AtlasKit Flag ХОСТА Jira в TOP-документе, ВНЕ iframe приложения.
   Признак: скомпилированные Atlaskit-классы (_30huDKYbGa, _24h04i2Njc, ...),
   а не MUI-классы аппа (MuiBox-root, css-xxx). Приложение вызывает API хоста
   (@forge/bridge, view.createFlag), рендерит флаг сам Jira через FlagGroup.
   Поэтому здесь везде self.page, без frame_locator.

2. data-testid НЕТ ни у одного элемента флага, классы хешированные —
   использовать их нельзя. Единственный стабильный семантический якорь —
   ИКОНКА: <span role="img" aria-label="Success"> / aria-label="Error".
   Это одновременно и локатор, и определитель типа. Контейнер достаётся от
   иконки через ancestor:: (разрешённое проектом исключение — структурная
   навигация от найденного по роли элемента, не позиционный индекс).

3. ЛОВУШКА: заголовок и тело помечены aria-hidden="true":
       <h2 ...><span aria-hidden="true">Error</span></h2>
       <div aria-hidden="true" ...>Invalid URL. Enter the full...</div>
   get_by_role("heading", name="Error") НЕ найдёт заголовок — aria-hidden
   исключается из вычисления accessible name. Читать через text_content().

4. ЛОВУШКА: строка "Error Invalid URL..." из кейса — СКЛЕЕННЫЕ заголовок и
   тело. В DOM они раздельные; слитно встречаются только в screen-reader-only
   span (>ErrorInvalid URL...</span>). Проверять раздельно.

5. Кнопка закрытия — accessible name "Dismiss" (из видимого span; svg внутри
   aria-hidden). Имя ОБЩЕЕ, поэтому клик скоупится внутри контейнера флага.

6. ВРЕМЯ ЖИЗНИ ~5 СЕКУНД (подтверждено пользователем). Следствия:
     a) проверять флаг НЕМЕДЛЕННО после действия, ДО долгих проверок
        контента (has_reminder_with_text() с таймаутом 15с съест окно);
     b) ReminderModal.submit() ждёт закрытия модалки до 20с; при ОШИБКЕ
        модалка не закрывается — вызывать submit(settle_timeout_ms=500);
     c) дефолтный таймаут здесь 3с (< времени жизни) — быстрое падение.

ТЕХНИЧЕСКИЙ РИСК: разметкой подтверждены Success и Error. Warning опирается
на более ранний скриншот REMCL-2734/2735 (жёлтый треугольник + заголовок
"Warning"); точный aria-label его иконки не снят. Другие типы не поддержаны —
список _KNOWN_KINDS расширяется по факту подтверждения.

ТЕХНИЧЕСКИЙ РИСК: одновременный стек из нескольких флагов вживую не
наблюдался. count()/dismiss_all() перебирают известные типы; чтение
заголовка/тела берёт .first — для конкретного флага ищите по тексту тела.
"""
from __future__ import annotations

import re

from playwright.sync_api import Locator, Page

FLAG_KIND_SUCCESS = "Success"
FLAG_KIND_ERROR = "Error"
FLAG_KIND_WARNING = "Warning"

_KNOWN_KINDS: tuple[str, ...] = (
    FLAG_KIND_SUCCESS,
    FLAG_KIND_ERROR,
    FLAG_KIND_WARNING,
)
_KNOWN_KINDS_RE = re.compile(
    r"^(?:" + "|".join(_KNOWN_KINDS) + r")$", re.IGNORECASE
)

_DISMISS_BUTTON_NAME = re.compile(r"^Dismiss$", re.IGNORECASE)

# Меньше времени жизни флага (~5с) — отсутствие флага должно падать быстро.
DEFAULT_TIMEOUT_MS = 3_000

# Наблюдаемое время жизни флага до автоисчезновения (сек).
FLAG_LIFETIME_S = 5

# Подтверждённый текст тела success-уведомления о создании ремайндера.
REMINDER_CREATED_SUCCESS_TEXT = "A new reminder was added"


class Notification:
    """
    Компонент: всплывающие уведомления (AtlasKit Flag) в TOP-документе.

    Принимает Page, а НЕ FrameLocator — флаги рендерит хост Jira вне iframe
    приложения (п.1 докстринга модуля). Ассертов здесь нет.
    """

    def __init__(self, page: Page) -> None:
        self.page = page

    # --- Локаторы ---

    def _icon(self, kind: str | None) -> Locator:
        """Иконка флага: role="img" + aria-label с типом. None → любой известный."""
        name = (
            re.compile(rf"^{re.escape(kind)}$", re.IGNORECASE)
            if kind
            else _KNOWN_KINDS_RE
        )
        return self.page.get_by_role("img", name=name)

    def locator(self, kind: str | None = None) -> Locator:
        """
        Контейнер флага (может матчить несколько).

        От иконки поднимаемся к ближайшему div-предку с кнопкой внутри — это
        ряд флага, содержащий иконку, заголовок, тело и Dismiss. Структурная
        навигация, не позиционный индекс.

        Публичный — чтобы тест сам делал expect(...).to_be_visible() с retry.
        """
        return self._icon(kind).locator("xpath=ancestor::div[.//button][1]")

    def title_locator(self, kind: str | None = None) -> Locator:
        """Заголовок — <h2>. По роли с именем НЕ матчится (aria-hidden, п.3)."""
        return self.locator(kind).first.locator("h2").first

    def body_locator(self, kind: str | None = None) -> Locator:
        """
        Тело флага. .last: во время анимации скрытия aria-hidden появляется
        ещё и у ОБЁРТКИ тела, матчей становится два; текст лежит во вложенном
        (последнем в DOM) узле.
        """
        return self.locator(kind).first.locator("div[aria-hidden]").last

    def _dismiss_button(self, kind: str | None = None) -> Locator:
        return self.locator(kind).first.get_by_role(
            "button", name=_DISMISS_BUTTON_NAME
        )

    # --- Состояние ---

    def is_visible(
        self, kind: str | None = None, timeout_ms: int = DEFAULT_TIMEOUT_MS
    ) -> bool:
        """Виден ли флаг указанного типа (или любой из известных)."""
        try:
            self.locator(kind).first.wait_for(
                state="visible", timeout=timeout_ms
            )
            return True
        except Exception:
            return False

    def wait_for(
        self, kind: str | None = None, timeout_ms: int = DEFAULT_TIMEOUT_MS
    ) -> bool:
        """Ждёт появления флага. Вызывать СРАЗУ после действия (п.6)."""
        return self.is_visible(kind=kind, timeout_ms=timeout_ms)

    def count(self) -> int:
        """
        Сколько флагов известных типов в DOM. Перебор типов, а не общий
        селектор: у флага нет ни testid, ни роли контейнера (п.2).
        """
        return sum(self.locator(kind).count() for kind in _KNOWN_KINDS)

    def kind(self, kind: str | None = None) -> str | None:
        """Тип первого флага — из aria-label его иконки; None если не найден."""
        try:
            root = self.locator(kind).first
            icon = root.get_by_role("img", name=_KNOWN_KINDS_RE).first
            return icon.get_attribute("aria-label")
        except Exception:
            return None

    def title(self, kind: str | None = None) -> str | None:
        """
        Текст заголовка. ОДНОКРАТНЫЙ снимок — для проверки после действия
        используйте expect(notification.title_locator(...)).to_have_text(...).
        """
        try:
            return (self.title_locator(kind).text_content() or "").strip()
        except Exception:
            return None

    def body(self, kind: str | None = None) -> str | None:
        """Текст тела уведомления; None если не найдено."""
        try:
            return (self.body_locator(kind).text_content() or "").strip()
        except Exception:
            return None

    def has_with_text(
        self,
        text: str | re.Pattern[str],
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> bool:
        """
        Есть ли флаг, чьё ТЕЛО содержит text (строка или regex). Поиск в
        TOP-документе. Нужно, когда тип не важен или флагов одного типа
        несколько.
        """
        locator = (
            self.page.get_by_text(text)
            if isinstance(text, re.Pattern)
            else self.page.get_by_text(text, exact=False)
        )
        try:
            locator.first.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    # --- Действия ---

    def dismiss(self, kind: str | None = None) -> bool:
        """
        Закрывает флаг кнопкой Dismiss внутри его контейнера (имя общее, п.5).
        True если кнопка найдена и клик прошёл. Пригодится в teardown.
        """
        try:
            button = self._dismiss_button(kind)
            button.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
            button.click(timeout=DEFAULT_TIMEOUT_MS)
            return True
        except Exception:
            return False

    def dismiss_all(self, max_rounds: int = 5) -> int:
        """Закрывает все флаги известных типов; возвращает число закрытий."""
        closed = 0
        for _ in range(max_rounds):
            if self.count() == 0:
                break
            if not self.dismiss():
                break
            closed += 1
        return closed