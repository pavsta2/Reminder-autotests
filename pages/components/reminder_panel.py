"""
ReminderPanel — контекстная секция плагина "Reminder for Jira Cloud"
на странице задачи (issue glance / web panel в сайдбаре "Details").
Кнопка Create в этой секции открывает модалку "New reminder" — это
ОТДЕЛЬНЫЙ компонент, см. pages/components/reminder_modal.py. Используйте
open_create_modal() ниже, чтобы получить Page Object модалки.

============================================================================
НАХОДКИ ПО ВЁРСТКЕ (сохранять при рефакторинге — на них опираются локаторы)
============================================================================

1. Нет role="region" у САМОЙ app-секции. Секция — это <section> БЕЗ
   aria-label/aria-labelledby, поэтому implicit role="region" у неё не
   появляется (ARIA spec) — page.get_by_role("region") её не найдёт.
   Контейнер ищется как ближайший <section>-предок заголовка:
   heading.locator("xpath=ancestor::section[1]").
   (Не путать с ОБЁРТКОЙ Apps — у неё role="region" aria-label="Apps section"
   ЕСТЬ, см. п.8.)

2. Заголовок — обычный <h2 data-testid="issue-view-layout-group.common.ui.
   collapsible-group-factory.title">. Подтверждено повторно 2026-11-25.

3. У секции стабильный data-testid с зашитым ARI инсталляции:
   "...collapsible-group-factory.context-group-ari:cloud:ecosystem::extension/
   <extension_id>/<env_id>/static/issue-context".

4. Содержимое секции (Create / Tomorrow / In a week / Child Rems / No reminders)
   рендерится Forge в <iframe>, который НЕ является потомком <section>: он
   лежит в СОСЕДНЕМ div[data-testid="issue-view-layout-group.animated-body"].
   Поэтому section.frame_locator("iframe") ничего не находит. iframe ищется
   по title="Embedded app content for <extension_id>" + подстроке env_id в src.
   Подтверждено повторно 2026-11-25 (в разметке iframe также имеет
   data-testid="hosted-resources-iframe" и data-forge-iframe="true", но они
   НЕ различают окружения — для этого нужны именно title+src).

5. Содержимое cross-origin iframe недоступно инструменту живой разведки —
   точные role/name кнопок внутри подтверждены только скриншотом/реальным
   прогоном Playwright.

6. МНОЖЕСТВЕННЫЕ ОКРУЖЕНИЯ (2026-11-15, PKP-5; повторно 2026-11-25,
   starshinov-dev): на одном инстансе может быть несколько deployment-
   окружений аппа. STG/DEV помечены lozenge-бейджем
   <span data-testid="forge-ui-extension-title.ui.environment-lozenge.lozenge">
   внутри того же <h2> (не aria-hidden) → входит в accessible name.
   extension_id у окружений может СОВПАДАТЬ, различается только env_id —
   поэтому заголовок матчится ТОЧНО по окружению, а iframe фильтруется
   И по title, И по env_id в src. Атрибут id iframe (iFrameResizer0/1/...) —
   порядковый номер монтирования, НЕ идентификатор окружения.
   На starshinov-dev (2026-11-25) наблюдалось ровно два окружения:
   env 63da55c4-... → "Reminder DEV" (раскрыта),
   env d58d1f3d-... → "Reminder" (PROD, свёрнута, подзаголовок
   "Follow Up Work Items").

7. has_reminder_with_text() (2026-11-16, REMCL-1038) — подтверждает создание
   ремайндера прямо в этой секции, без My reminders/Queue. Разметка строки
   созданного ремайндера вживую не снята — ищем по вхождению текста.

8. ДОБАВЛЕНО (2026-11-25, по обеим присланным разметкам правого сайдбара):
   ОБЁРТКА "Apps". В части проектов app-секции лежат не прямо в сайдбаре, а
   внутри дополнительной сворачиваемой обёртки Apps:
     wrapper: data-testid="work-item-layout.layout-sidebar.ecosystem-apps-wrapper"
     тоггл:   data-testid="issue.views.common.collapsible-section.
              ECOSYSTEM_CONTEXT_PANELS.toggle"  (aria-expanded / aria-label
              "Expand Apps" ↔ "Collapse Apps")
     тело:    при свёрнутой обёртке — <div inert=""> ПУСТОЙ, секций аппов
              в DOM вообще нет; при раскрытой — появляется
              <div role="region" aria-label="Apps section"> с секциями.
   ВАЖНО (отдельно подчёркнуто пользователем): обёртка Apps есть НЕ ВО ВСЕХ
   проектах. Поэтому expand_apps_wrapper_if_present() — условный и
   идемпотентный: нет обёртки → это норма, возвращаем False и ищем секцию
   напрямую; обёртка уже раскрыта → не кликаем (повторный клик свернёт).
   Вызывается из is_present() и expand(), поэтому существующие фикстуры и
   тесты менять не нужно.

9. НАХОДКА 1 (2026-11-25, КРИТИЧНО, исправлено в pages/base_page.py): наш
   же BasePage.dismiss_onboarding_overlays() содержал угаданный кандидат
   role_button с regex "collapse|minimize|свернуть". В актуальной разметке
   тогглы секций имеют aria-label "Collapse Details" / "Collapse Apps" /
   "Collapse ", поэтому этот кандидат матчил их и КЛИКАЛ — то есть
   IssuePage.open() сам сворачивал Details и Apps, а затем тест не находил
   секцию Reminder. Кандидат удалён. Это была вторая, более коварная
   причина поломки помимо изначально свёрнутой обёртки Apps.

10. ИСПРАВЛЕНО (2026-11-25): внутри <section> теперь ДВА элемента с ролью
    button, а не один:
      a) div[role="button"][tabindex="0"][aria-expanded] — обёртка заголовка
         (кликабельная область, видна всегда);
      b) button[data-testid="issue-view-layout-group.context-panel-chevron"]
         с data-chevron-state="expanded|collapsed" и
         data-chevron-visible="true|false".
    Поэтому прежний _section.get_by_role("button").first больше не годится
    как явный локатор (он формально всё ещё берёт (a), но опирается на
    порядок DOM). Теперь локаторы скоуплены явно, а состояние читается
    ПРЕИМУЩЕСТВЕННО из data-chevron-state (более надёжный признак), с
    фоллбеком на aria-expanded.
    Кликаем при этом по (a), а не по шеврону: у раскрытой секции шеврон
    имеет data-chevron-visible="false" (показывается только по hover),
    клик по нему нестабилен.

11. Подзаголовок секции (напр. "Follow Up Work Items", "Linked Objects")
    обёрнут в aria-hidden="true" → в accessible name заголовка НЕ входит,
    точные regex заголовков им не ломаются. Подтверждено 2026-11-25.
"""
from __future__ import annotations

import re
from typing import Literal

from playwright.sync_api import FrameLocator, Locator, Page

from pages.components.reminder_modal import ReminderModal

Environment = Literal["prod", "stg", "dev"]

# Точное совпадение заголовка секции по окружению (см. п.6 докстринга).
# PROD: заголовок — просто "Reminder", без бейджа. STG/DEV — "Reminder" +
# текст lozenge-бейджа, который рендерится ВНУТРИ того же <h2> (не
# aria-hidden), поэтому входит в accessible name заголовка.
_ENVIRONMENT_HEADING_RE: dict[Environment, re.Pattern[str]] = {
    "prod": re.compile(r"^Reminder$", re.IGNORECASE),
    "stg": re.compile(r"^Reminder\s+STG$", re.IGNORECASE),
    "dev": re.compile(r"^Reminder\s+DEV$", re.IGNORECASE),
}

# Извлекает И extension id, И env id из data-testid секции (см. п.3/п.6).
# Формат подтверждён повторно 2026-11-25 — не менялся.
_SECTION_TESTID_IDS_RE = re.compile(r"extension/([0-9a-fA-F-]+)/([0-9a-fA-F-]+)/")

# --- Обёртка Apps (см. п.8 докстринга; добавлено 2026-11-25) ---
# Тоггл обёртки — стабильный data-testid (приоритет №1 по правилам проекта).
_APPS_TOGGLE_TESTID = (
    "issue.views.common.collapsible-section.ECOSYSTEM_CONTEXT_PANELS.toggle"
)
# Признак того, что тело обёртки раскрылось и секции аппов смонтированы:
# у раскрытой обёртки появляется region с aria-label "Apps section"
# (подтверждено присланной разметкой 2026-11-25).
_APPS_REGION_NAME_RE = re.compile(r"^Apps section$", re.IGNORECASE)

# Шеврон app-секции (см. п.10) — стабильный data-testid, но встречается у
# КАЖДОЙ app-секции, поэтому используется ТОЛЬКО скоупленно внутри self._section.
_SECTION_CHEVRON_TESTID = "issue-view-layout-group.context-panel-chevron"


class ReminderPanel:
    """
    Компонент: контекстная секция Reminder в сайдбаре Details страницы задачи.

    environment: какую именно инсталляцию аппа искать на странице — "prod"
        (дефолт, заголовок секции — просто "Reminder", без бейджа),
        "stg" (заголовок "Reminder STG") или "dev" (заголовок "Reminder DEV").
        Нужно только на инстансах, где установлено больше одного окружения
        одновременно (см. п.6 докстринга модуля).
    """

    def __init__(self, page: Page, environment: Environment = "prod") -> None:
        self.page = page
        self.environment = environment
        heading_re = _ENVIRONMENT_HEADING_RE[environment]

        # Заголовок секции — обычный <h2> (см. п.2). Матчим ТОЧНО нужное
        # окружение, иначе при нескольких установленных окружениях locator
        # найдёт больше одной секции (strict-mode violation).
        self._heading: Locator = page.get_by_role("heading", name=heading_re)

        # Контейнер — ближайший <section>-предок заголовка (НЕ get_by_role
        # ("region") — у app-секции нет aria-label, implicit region не
        # применяется, см. п.1).
        self._section: Locator = self._heading.locator("xpath=ancestor::section[1]")

        # ИСПРАВЛЕНО (2026-11-25, п.10): внутри секции теперь ДВА button--role
        # элемента, поэтому локаторы скоуплены явно, а не через .first по
        # всем кнопкам секции.
        # (a) Кликабельная обёртка заголовка — видна всегда, по ней и кликаем.
        self._header_toggle: Locator = self._section.locator(
            '[role="button"][aria-expanded]'
        ).first
        # (b) Шеврон — несёт data-chevron-state (надёжный признак состояния),
        # но при раскрытой секции виден только по hover, поэтому НЕ кликаем.
        self._chevron: Locator = self._section.locator(
            f'[data-testid="{_SECTION_CHEVRON_TESTID}"]'
        ).first

        # Тоггл обёртки Apps (может отсутствовать — это норма, см. п.8).
        self._apps_toggle: Locator = page.locator(
            f'[data-testid="{_APPS_TOGGLE_TESTID}"]'
        )

    # --- Обёртка Apps (условно, есть не во всех проектах) ---

    def expand_apps_wrapper_if_present(self, timeout_ms: int = 1_500) -> bool:
        """
        Раскрывает обёртку Apps, если она ЕСТЬ на странице и свёрнута.
        Возвращает True, если обёртка присутствует (независимо от того,
        кликали мы или она уже была раскрыта), False — если её нет.

        УСЛОВНОСТЬ (см. п.8 докстринга, отдельно подчёркнуто пользователем):
        обёртка Apps встречается НЕ ВО ВСЕХ проектах. Её отсутствие — не
        ошибка и не повод падать: возвращаем False, и поиск секции идёт
        напрямую по заголовку, как раньше.

        ИДЕМПОТЕНТНОСТЬ: если aria-expanded уже "true" — НЕ кликаем.
        Повторный клик по тому же тогглу свернёт обёртку и уберёт секции
        аппов из DOM (тело обёртки в свёрнутом состоянии — пустой
        <div inert="">), то есть сломает как раз то, что мы хотим получить.

        timeout_ms намеренно короткий (1.5с): это ПРОБА наличия обёртки, а
        не ожидание её появления. На проектах без Apps мы платим эту
        полторы секунды один раз за вызов — сознательный размен на
        простоту и предсказуемость вместо усложнения логики.
        """
        try:
            self._apps_toggle.wait_for(state="visible", timeout=timeout_ms)
        except Exception:
            return False

        try:
            expanded = self._apps_toggle.get_attribute("aria-expanded")
        except Exception:
            expanded = None

        if expanded == "true":
            return True

        try:
            self._apps_toggle.click(timeout=timeout_ms)
        except Exception:
            return True

        # Ждём именно МОНТИРОВАНИЯ содержимого, а не только смены атрибута:
        # секции аппов появляются в DOM не мгновенно после клика.
        try:
            self.page.get_by_role("region", name=_APPS_REGION_NAME_RE).wait_for(
                state="visible", timeout=5_000
            )
        except Exception:
            # Region мог не появиться (иная разметка/версия UI) — не считаем
            # это ошибкой: дальше is_present()/expand() сами подождут секцию.
            pass
        return True

    # --- Базовое наличие / разворот секции ---

    def is_present(self, timeout_ms: int = 10_000) -> bool:
        """
        Есть ли контекстная секция Reminder на странице задачи.

        ИСПРАВЛЕНО (2026-11-25): сначала раскрываем обёртку Apps, если она
        есть и свёрнута — иначе секции Reminder в DOM просто нет (см. п.8)
        и поиск заголовка всегда давал False. На проектах без обёртки Apps
        вызов — no-op, поведение прежнее.
        """
        self.expand_apps_wrapper_if_present()
        try:
            self._heading.first.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def _is_section_expanded(self) -> bool:
        """
        Раскрыта ли сама секция Reminder.

        Приоритет признака (см. п.10): data-chevron-state шеврона
        ("expanded"/"collapsed") → фоллбек на aria-expanded обёртки
        заголовка. Оба прочтения best-effort: если ни один признак не
        доступен, считаем секцию свёрнутой и пробуем клик (expand()
        идемпотентен по результату, а не по числу кликов).
        """
        try:
            state = self._chevron.get_attribute("data-chevron-state")
            if state in ("expanded", "collapsed"):
                return state == "expanded"
        except Exception:
            pass
        try:
            return self._header_toggle.get_attribute("aria-expanded") == "true"
        except Exception:
            return False

    def expand(self, timeout_ms: int = 10_000) -> None:
        """
        Разворачивает секцию Reminder, если она ещё свёрнута (и обёртку
        Apps, если она есть — см. п.8).

        Секция часто УЖЕ раскрыта по умолчанию сразу после рендера —
        повторный клик по тому же тогглу её свернёт, поэтому сначала
        читаем текущее состояние (см. _is_section_expanded) и кликаем
        только если оно не "expanded".

        Кликаем по кликабельной обёртке заголовка, а НЕ по шеврону: у
        раскрытой секции шеврон имеет data-chevron-visible="false"
        (виден только по hover) — клик по нему нестабилен (п.10).
        """
        self.expand_apps_wrapper_if_present()
        self._header_toggle.wait_for(state="visible", timeout=timeout_ms)
        if not self._is_section_expanded():
            self._header_toggle.click()

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

        iframe ищется по title="Embedded app content for <extension_id>"
        (НЕ как потомок <section> — см. п.4) И дополнительно по подстроке
        env_id в src — иначе при нескольких окружениях с ОДИНАКОВЫМ
        extension_id locator находил бы iframe любого из них.
        Оба id достаются из ОДНОГО data-testid секции → пара однозначно
        идентифицирует нужный iframe.

        Фоллбек через потомка <section> оставлен как резерв на случай
        изменений разметки, но на практике не работает (iframe не потомок
        section, п.4) и на инстансе с несколькими окружениями ненадёжен.
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
        созданного ремайндера) появился в содержимом этой секции —
        REMCL-1038: факт создания подтверждается прямо здесь, БЕЗ
        My reminders/Queue.

        ТЕХНИЧЕСКИЙ РИСК (не снят): точная разметка строки созданного
        ремайндера вживую не наблюдалась — ищем по вхождению текста
        (exact=False), а не по роли/структуре строки.

        Таймаут увеличен относительно остальных проверок: после submit()
        секции нужно время, чтобы забрать свежий список. ReminderModal.
        submit() сам ждёт закрытия модалки, так что у этого метода уже
        есть фора — 15с здесь вторая, независимая линия защиты.
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
        (iframe панели). Для REMCL-1273: проверить, что сохранённый в
        Message HTML/JS НЕ превратился в реальные элементы.
        """
        return self.frame.locator(css).count()

    def click_create(self) -> None:
        self.frame.get_by_role(
            "button", name=re.compile("Create", re.IGNORECASE)
        ).click()

    def open_create_modal(self) -> ReminderModal:
        """
        Кликает Create и возвращает Page Object модалки "New reminder".
        Модалка — ОТДЕЛЬный компонент в собственном iframe, обёрнутом в
        section[role="dialog"] в top-документе (см. докстринг ReminderModal).
        Явно дожидаемся wait_until_ready() перед выдачей модалки тесту.
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
