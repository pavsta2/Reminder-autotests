"""
IssuePage — страница задачи Jira Cloud: {jira_host}/browse/{issue_key}.
"""

from __future__ import annotations

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from config.settings import get_settings
from pages.base_page import BasePage
from pages.components.reminder_panel import Environment, ReminderPanel

_settings = get_settings()

# REMCL-2734/2735: предупреждающее информационное окно (AtlasKit Flag),
# которое Jira показывает ПОСЛЕ успешного создания ремайндера.
#
# ПОДТВЕРЖДЕНО (2026-11-16) живым скриншотом пользователя — точный текст
# взят оттуда напрямую, а не угадан. Внешний вид на скриншоте: иконка
# предупреждения (жёлтый треугольник с "!"), жирный заголовок "Warning",
# крестик закрытия справа от заголовка, под ним — этот текст. Соответствует
# стандартному AtlasKit Flag/FlagGroup.
RECIPIENTS_VISIBILITY_WARNING_TEXT = (
    "Only recipients who can view the work item when the reminder is sent "
    "will receive it."
)


class IssuePage(BasePage):
    def __init__(self, page: Page, environment: Environment = "prod") -> None:
        """
        environment: какую инсталляцию аппа Reminder искать в сайдбаре этой
        задачи — на инстансах с несколькими одновременно установленными
        окружениями (prod/stg/dev), см. docstring ReminderPanel. По умолчанию
        "prod" — на инстансах с единственной инсталляцией (CPR1/REMCL)
        поведение не меняется.
        """
        super().__init__(page)
        self.reminder_panel = ReminderPanel(page, environment=environment)

    def open(self, issue_key: str) -> None:
        self.goto(_settings.issue_url(issue_key))
        # На первом визите в инстанс с нового браузерного профиля Jira может
        # показать онбординг-оверлеи (Quickstart, Rovo-приглашение, coachmark-
        # тултипы) поверх сайдбара — закрываем их до любых проверок/кликов.
        self.dismiss_onboarding_overlays()

    def has_reminder_section(self, timeout_ms: int = 10_000) -> bool:
        """Проверяет наличие контекстной секции плагина Reminder в сайдбаре задачи."""
        return self.reminder_panel.is_present(timeout_ms=timeout_ms)

    def has_recipients_visibility_warning_flag(self, timeout_ms: int = 10_000) -> bool:
        """
        REMCL-2734/2735: проверяет, что после создания ремайндера появился
        предупреждающий flag с текстом RECIPIENTS_VISIBILITY_WARNING_TEXT
        (см. константу выше — подтверждена живым скриншотом).

        МЕТОД — НА IssuePage, А НЕ НА ReminderModal/ReminderPanel: flag
        рендерится ВЕРХНЕУРОВНЕВО, напрямую в TOP-документе страницы
        задачи (а не внутри iframe формы или панели) — это стандартный для
        Forge-приложений паттерн: само приложение вызывает API хоста
        (`@forge/bridge`, `view.createFlag(...)`), а РЕНДЕРИТ flag уже сам
        Jira-хост через свой собственный AtlasKit FlagGroup-портал, вне
        какого-либо iframe приложения. Тот же принцип, что и у модалки
        "New reminder" (см. докстринг ReminderModal, п.2: `section[role=
        "dialog"]` тоже в TOP-документе, а не внутри iframe секции/панели).
        Поэтому здесь используется self.page.get_by_text(...) напрямую,
        без какого-либо frame_locator.

        К моменту вызова ReminderModal.submit() уже дождался закрытия
        модалки (см. её докстринг) — flag появляется уже ПОСЛЕ этого,
        поэтому вызывать этот метод имеет смысл только после submit().

        ТЕХНИЧЕСКИЙ РИСК (не снят полностью): скриншотом подтверждён текст
        ТОЛЬКО для recipient'а-пользователя (Reporter/Assignee/Watchers —
        REMCL-2734). Для recipient'а-группы (REMCL-2735) тот же самый
        текст предполагается по аналогии (сам текст не содержит имени
        конкретного recipient'а и выглядит как общая оговорка про
        видимость задачи, а не специфичная для типа recipient'а формулировка),
        но ОТДЕЛЬНЫМ скриншотом для группы это не подтверждено. Также не
        подтверждено, через сколько секунд flag исчезает сам — таймаут
        подобран с запасом (10с), а не по факту замера.
        """
        try:
            self.page.get_by_text(
                RECIPIENTS_VISIBILITY_WARNING_TEXT, exact=True
            ).first.wait_for(state="visible", timeout=timeout_ms)
            return True
        except PlaywrightTimeoutError:
            return False
