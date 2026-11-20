"""
ReminderPanel — контекстная секция плагина "Reminder for Jira Cloud"
на странице задачи (issue glance / web panel в сайдбаре "Details").

Кнопка Create в этой секции открывает модалку "New reminder" — это
ОТДЕЛЬНЫЙ компонент, см. pages/components/reminder_modal.py (там же —
подробный разбор поля Recipients). Используйте open_create_modal() ниже,
чтобы получить Page Object модалки.

ПЕРЕСМОТРЕНО по итогам живого прогона через built-in browser (2026-11-11,
десктопная раскладка, ширина вьюпорта >= 1024px — на узких вьюпортах Jira
схлопывает сайдбар в общий поток страницы, см. ниже):

1. Заголовок секции — это обычный `<h2>` с текстом "Reminder", БЕЗ обёртки
   в элемент с `role="region"`. У нативного `<section>` implicit role="region"
   появляется только когда у него есть aria-label/aria-labelledby (ARIA spec);
   у секции Reminder (как и у остальных app-секций в сайдбаре: Automation,
   CRM for Jira Test, Calendar) этих атрибутов НЕТ. Поэтому прежний локатор
   `page.get_by_role("region").filter(has=heading)` НИКОГДА ничего не находил —
   это и было причиной `AssertionError: Секция Reminder не найдена`, а не
   проблема со скроллом/ленивой подгрузкой.
2. Контейнер секции — ближайший `<section>`-предок заголовка, у него стабильный
   `data-testid`, где зашит ARI extension id инсталляции аппа Reminder, напр.:
   "...collapsible-group-factory.context-group-ari:cloud:ecosystem::extension/
   6f251f9a-5e31-4cbb-8c17-361129d5aa59/<env-id>/static/issue-context".
3. Тоггл сворачивания/разворота — единственный `div[role="button"]` внутри
   этого `<section>`, с атрибутом `aria-expanded`. ВАЖНО: на тестовом инстансе
   секция по умолчанию УЖЕ развёрнута (`aria-expanded="true"`) сразу после
   рендера страницы, без клика — клик по тогглу в этом состоянии её свернёт.
   Поэтому expand() сначала проверяет текущее состояние и кликает только если
   оно `!= "true"`.
4. Содержимое секции (кнопка "Create", пресеты "Tomorrow"/"In a week", кнопка
   "Child Rems", текст "No reminders", время часового пояса) рендерится
   Atlassian Forge НЕ внутри `<section>` секции, а отдельным `<iframe>`,
   вынесенным в другое место DOM и визуально спозиционированным поверх
   секции через getBoundingClientRect() (стандартная техника Forge UI Kit,
   чтобы iframe не клипился overflow родителя). Поэтому
   `section.frame_locator("iframe")` ничего не находит — ⁣iframe нужно искать
   по атрибуту `title="Embedded app content for <extension_id>"`, где
   `extension_id` — тот же ID, что зашит в data-testid секции (подтверждено
   живым прогоном: `document.querySelectorAll('iframe[title="Embedded app
   content for <id>"]')` возвращает ровно 1 элемент).
5. Содержимое iframe — кросс-доменное (cdn.prod.atlassian-dev.net), live-
   рекон-инструмент (built-in browser) не читает accessibility-дерево внутри
   кросс-доменных iframe, поэтому точные role/name кнопок Create/Tomorrow/
   In a week/Child Rems/No reminders ПОДТВЕРЖДЕНЫ ТОЛЬКО ПО СКРИНШОТУ, не по
   accessibility tree — это остаётся техническим риском (см. README), и их
   стоит проверить/поправить по факту первого реального прогона теста,
   который реально взаимодействует с этим содержимым (Playwright, в отличие
   от инструмента разведки, умеет работать с cross-origin iframe через
   frame_locator на уровне браузерного движка).

6. МНОЖЕСТВЕННЫЕ ОКРУЖЕНИЯ ОДНОГО АППА (2026-11-15, подтверждено живым прогоном
   на PKP-5 / starshinov-pr.atlassian.net): на одном Jira-инстансе одновременно
   может быть установлено НЕСКОЛЬКО deployment-окружений аппа Reminder —
   PROD/STG/DEV, каждое со своей секцией в сайдбаре. Окружение STG/DEV помечено
   "lozenge"-бейджем Atlassian — `<span data-testid="forge-ui-extension-title.
   ui.environment-lozenge.lozenge">STG</span>` (или "DEV"), вложенным в <h2>
   сразу после текста "Reminder ". У PROD такого бейджа нет — заголовок просто
   "Reminder". Поэтому прежний префиксный `_HEADING_RE = re.compile("^Reminder",
   re.IGNORECASE)` при нескольких одновременно установленных окружениях
   находил ВСЕ секции разом (строгий locator падал бы с "strict mode
   violation") — заголовок нужно матчить ТОЧНО, по конкретному окружению.

   Хуже того: STG и PROD-инсталляции МОГУТ иметь ОДИН И ТОТ ЖЕ extension_id в
   ARI (подтверждено: оба — "6f251f9a-5e31-4cbb-8c17-361129d5aa59" на PKP-5),
   различаясь только вторым UUID в ARI — env_id (у каждой секции он зашит в её
   собственный data-testid, см. _SECTION_TESTID_IDS_RE ниже). Из-за этого
   прежняя стратегия поиска iframe только по
   `title="Embedded app content for {extension_id}"` стала НЕОДНОЗНАЧНОЙ: у
   STG- и PROD-иframe этот title ОДИНАКОВЫЙ. Подтверждено живым дампом атрибутов
   обоих iframe через javascript_tool. Решение: тот же env_id, что в data-testid
   секции, зашит и во ВТОРОЙ путь-сегмент атрибута `src` самого iframe
   (вида ".../cdn.../{extension_id}/{env_id}/{random}/main/..."), поэтому
   фильтруем iframe ОДНОВРЕМЕННО по title (extension_id) И по подстроке в src
   (env_id) — см. ReminderPanel.frame.

   Атрибут `id` у iframe (iFrameResizer0/1/2...) — НЕ стабильный идентификатор
   окружения, это просто порядковый номер монтирования (зависит от порядка/
   таймингов разворота секций) — использовать его для различения окружений
   НЕЛЬЗЯ.

   Также подтверждено: содержимое секции (а значит и её iframe) монтируется в
   DOM только ПОСЛЕ разворота секции (см. expand()) — у свёрнутой секции
   querySelectorAll по iframe её title/src вообще не найдёт.

7. ДОБАВЛЕНО (2026-11-16, REMCL-1038, по указанию пользователя):
   has_reminder_with_text() — проверяет, что созданный ремайндер реально
   появился в этой секции, без необходимости открывать My reminders/Queue.
   ТЕХНИЧЕСКИЙ РИСК: точная разметка строки созданного ремайндера здесь НЕ
   подтверждена вживую — секция до сих пор наблюдалась только в пустом
   состоянии "No reminders" (см. has_no_reminders_message). Метод ищет
   просто вхождение текста в содержимом iframe.

   ПРОВЕРЕНО на синтетическом моке (mock_site_v4_create, см. п.12
   докстринга reminder_modal.py): сквозной прогон open_create_modal() ->
   modal.fill_message() -> modal.submit() -> has_reminder_with_text()
   пройден 5 раз без флейков, включая негативный контроль (заведомо
   отсутствующий текст корректно даёт False, а не ложный True) и
   искусственную задержку в 400мс между сабмитом и обновлением списка в
   панели — увеличенный таймаут (15с) её покрывает с большим запасом.
   Мок не заменяет первый реальный прогон: сама разметка строки
   ремайндера в нём задана по предположению (см. риск выше).
"""

from __future__ import annotations

import re
from typing import Literal

from playwright.sync_api import FrameLocator, Locator, Page

from pages.components.reminder_modal import ReminderModal

Environment = Literal["prod", "stg", "dev"]

# Точное совпадение заголовка секции по окружению (см. п.6 докстринга модуля).
# PROD: заголовок — просто "Reminder", без лейбла. STG/DEV — "Reminder" +
# текст lozenge-бейджа ("STG"/"DEV"), который рендерится ВНУТРИ того же <h2>
# (не aria-hidden), поэтому входит в accessible name заголовка.
_ENVIRONMENT_HEADING_RE: dict[Environment, re.Pattern[str]] = {
    "prod": re.compile(r"^Reminder$", re.IGNORECASE),
    "stg": re.compile(r"^Reminder\s+STG$", re.IGNORECASE),
    "dev": re.compile(r"^Reminder\s+DEV$", re.IGNORECASE),
}

# Извлекает И extension id, И env id из data-testid секции, например из
# "...collapsible-group-factory.context-group-ari:cloud:ecosystem::extension/
#  6f251f9a-5e31-4cbb-8c17-361129d5aa59/d58d1f3d-.../static/issue-context"
# достаёт ("6f251f9a-5e31-4cbb-8c17-361129d5aa59", "d58d1f3d-...").
# env_id нужен, чтобы отличить STG от PROD, когда у них совпадает extension_id
# (см. п.6 докстринга модуля).
_SECTION_TESTID_IDS_RE = re.compile(r"extension/([0-9a-fA-F-]+)/([0-9a-fA-F-]+)/")


class ReminderPanel:
    """
    Компонент: контекстная секция Reminder в сайдбаре Details страницы задачи.

    environment: какую именно инсталляцию аппа искать на странице — "prod"
    (дефолт, заголовок секции — просто "Reminder", без лейбла),
    "stg" (заголовок "Reminder STG") или "dev" (заголовок "Reminder DEV").
    Нужно только на инстансах, где установлено больше одного окружения
    одновременно (см. п.6 докстринга модуля) — на инстансах с единственной
    инсталляцией (CPR1/REMCL) дефолтного "prod" достаточно.
    """

    def __init__(self, page: Page, environment: Environment = "prod") -> None:
        self.page = page
        self.environment = environment
        heading_re = _ENVIRONMENT_HEADING_RE[environment]
        # Заголовок секции — обычный <h2>, без role="region"-обёртки (см. docstring модуля).
        # Матчим ТОЧНО нужное окружение (не префиксом "^Reminder") — иначе при
        # нескольких одновременно установленных окружениях locator найдёт
        # больше одной секции и упадёт как strict-mode violation.
        self._heading: Locator = page.get_by_role("heading", name=heading_re)
        # Контейнер — ближайший <section>-предок заголовка (НЕ get_by_role("region") —
        # у этого <section> нет aria-label/aria-labelledby, implicit role="region" не применяется).
        self._section: Locator = self._heading.locator("xpath=ancestor::section[1]")
        # Единственный div[role="button"] внутри секции — тоггл сворачивания/разворота.
        self._toggle_button: Locator = self._section.get_by_role("button").first

    # --- Базовое наличие / разворот секции ---

    def is_present(self, timeout_ms: int = 10_000) -> bool:
        """Есть ли контекстная секция Reminder на странице задачи."""
        try:
            self._heading.first.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def expand(self, timeout_ms: int = 10_000) -> None:
        """
        Разворачивает секцию, если она ещё свёрнута.

        На практике секция часто УЖЕ развёрнута по умолчанию сразу после
        рендера (aria-expanded="true" без единого клика) — повторный клик по
        тому же тогглу в этом состоянии её свернёт, поэтому сначала проверяем
        текущее состояние и кликаем только если оно не "true".
        """
        self._toggle_button.wait_for(state="visible", timeout=timeout_ms)
        expanded = self._toggle_button.get_attribute("aria-expanded")
        if expanded != "true":
            self._toggle_button.click()

    # --- Содержимое внутри iframe ---

    def _extension_and_env_id(self) -> tuple[str, str] | None:
        test_id = self._section.get_attribute("data-testid") or ""
        match = _SECTION_TESTID_IDS_RE.search(test_id)
        return (match.group(1), match.group(2)) if match else None

    @property
    def frame(self) -> FrameLocator:
        """
        FrameLocator на встроенный Forge-iframe ИМЕННО этой секции (этого
        environment).

        iframe ищется по атрибуту title="Embedded app content for <extension_id>"
        (НЕ как потомок <section> — см. пункт 4 в docstring модуля), И
        ДОПОЛНИТЕЛЬНО по подстроке env_id в атрибуте src — иначе при
        нескольких одновременно установленных окружениях с ОДИНАКОВЫМ
        extension_id (STG и PROD могут совпадать, см. п.6 докстринга модуля)
        locator находил бы iframe ЛЮБОГО из них, а не именно нужного
        self.environment. extension_id и env_id достаются из ОДНОГО и того же
        data-testid секции, в котором закодирован ARI этой КОНКРЕТНОЙ
        инсталляции — значит пара однозначно идентифицирует нужный iframe,
        даже когда на странице несколько секций с совпадающим extension_id.

        Если по какой-то причине extension_id/env_id не удалось вынуть из
        data-testid секции — используется фоллбек через потомка <section>
        (не должен понадобиться, но на случай изменений в разметке Atlassian
        оставлен как резерв; на инстансе с несколькими окружениями этот
        фоллбек ненадёжен, см. п.6 докстринга модуля).
        """
        ids = self._extension_and_env_id()
        if ids:
            extension_id, env_id = ids
            return self.page.frame_locator(
                f'iframe[title="Embedded app content for {extension_id}"]'
                f'[src*="/{env_id}/"]'
            )
        return self._section.frame_locator("iframe")

    def has_no_reminders_message(self, timeout_ms: int = 10_000) -> bool:
        locator = self.frame.get_by_text("No reminders", exact=False)
        try:
            locator.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def has_reminder_with_text(self, text: str, timeout_ms: int = 15_000) -> bool:
        """
        True, если текст (например, уникальное сообщение только что
        созданного ремайндера) появился где-то в содержимом этой секции —
        REMCL-1038: по указанию пользователя, факт реального создания
        ремайндера подтверждается тем, что он отображается прямо здесь, в
        контекстной секции Reminder на странице задачи, БЕЗ необходимости
        открывать My reminders/Queue.

        ТЕХНИЧЕСКИЙ РИСК (2026-11-16, не подтверждено вживую): точная
        разметка строки созданного ремайндера в этой секции раньше не
        наблюдалась (секция до сих пор фигурировала в тестах только в
        пустом состоянии "No reminders", см. has_no_reminders_message
        выше) — поэтому ищем просто по вхождению текста (exact=False) в
        содержимом iframe, а не по конкретной роли/структуре строки.
        Таймаут увеличен относительно остальных проверок в этом файле:
        после submit() модалки секции, возможно, нужно время на то, чтобы
        забрать свежий список ремайндеров — тоже не подтверждено вживую.

        ИСПРАВЛЕНО (2026-11-16, по скриншоту живого прогона — клик Create
        запускает сетевой запрос, который идёт какое-то время, и проверка
        стартовала раньше, чем он завершился): ReminderModal.submit() сам
        теперь дополнительно ждёт закрытия модалки (до 20с) ПЕРЕД
        возвратом — у этого метода к моменту вызова уже есть неплохая
        фора, 15с таймаут здесь оставлен как есть (вторая, независимая
        линия защиты, а не единственная).
        """
        locator = self.frame.get_by_text(text, exact=False)
        try:
            locator.first.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def count_elements(self, css: str) -> int:
        """
        Сколько элементов по css-селектору сейчас в содержимом секции
        (iframe панели). ДОБАВЛЕНО (2026-11-20) для REMCL-1273: проверить,
        что сохранённый в Message HTML/JS НЕ превратился в реальные
        элементы (<img onerror>, <script>, <a href="javascript:">) при
        отображении ремайндера в секции.
        """
        return self.frame.locator(css).count()

    def click_create(self) -> None:
        self.frame.get_by_role(
            "button", name=re.compile("Create", re.IGNORECASE)
        ).click()

    def open_create_modal(self) -> ReminderModal:
        """
        Кликает Create и возвращает Page Object модалки "New reminder"
        (см. pages/components/reminder_modal.py). Модалка — ОТДЕЛЬНЫЙ
        компонент: она рендерится в собственном iframe, ОТДЕЛЬНОМ от iframe
        этой секции (хотя у обоих одинаковый title — тот же extension id
        аппа Reminder), обёрнутом в section[role="dialog"] в top-документе
        (см. докстринг ReminderModal, раунд 2, исправление от 2026-11-13).

        Явно дожидаемся wait_until_ready() ПЕРЕД тем, как отдать
        ReminderModal тесту — см. причину в докстринге этого метода у
        ReminderModal.wait_until_ready: форма рендерится не мгновенно по
        клику, и отдельные короткие (5с) проверки внутри конкретных тестов
        иногда проигрывали эту гонку.
        """
        self.click_create()
        modal = ReminderModal(self.page)
        modal.wait_until_ready()
        return modal

    def click_quick_preset(self, label: str) -> None:
        """label: например 'Tomorrow' / 'In a week'."""
        self.frame.get_by_role(
            "button", name=re.compile(re.escape(label), re.IGNORECASE)
        ).click()

    def click_child_reminders(self) -> None:
        self.frame.get_by_role(
            "button", name=re.compile("Child Rem", re.IGNORECASE)
        ).click()
