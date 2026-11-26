"""
IssuePage — страница задачи Jira Cloud: {jira_host}/browse/{issue_key}.

ИСПРАВЛЕНО (2026-11-25, по решению пользователя): работа с всплывающими
уведомлениями вынесена в отдельный сквозной компонент
pages/components/notification.py (Notification). Метод
has_recipients_visibility_warning_flag() сохранён с прежней сигнатурой и
теперь делегирует в него — уведомления не принадлежат ни странице, ни
форме, и держать их локаторы здесь означало дублировать их же в других
местах (ошибка URL и т.п.).
"""
from __future__ import annotations

from playwright.sync_api import Page

from config.settings import get_settings
from pages.base_page import BasePage
from pages.components.notification import Notification
from pages.components.reminder_panel import Environment, ReminderPanel

_settings = get_settings()

# REMCL-2734/2735: текст предупреждающего уведомления, которое Jira
# показывает ПОСЛЕ успешного создания ремайндера. ПОДТВЕРЖДЕНО (2026-11-16)
# живым скриншотом пользователя — точный текст взят оттуда напрямую.
# Заголовок при этом — "Warning", иконка — жёлтый треугольник.
# Константа оставлена здесь (на неё могут ссылаться существующие тесты);
# сам поиск теперь идёт через Notification.
RECIPIENTS_VISIBILITY_WARNING_TEXT = (
    "Only recipients who can view the work item when the reminder is sent "
    "will receive it."
)


class IssuePage(BasePage):
    def __init__(self, page: Page, environment: Environment = "prod") -> None:
        """
        environment: какую инсталляцию аппа Reminder искать в сайдбаре этой
        задачи — на инстансах с несколькими одновременно установленными
        окружениями (prod/stg/dev), см. docstring ReminderPanel. По
        умолчанию "prod" — на инстансах с единственной инсталляцией
        (CPR1/REMCL) поведение не меняется.
        """
        super().__init__(page)
        self.reminder_panel = ReminderPanel(page, environment=environment)
        # Всплывающие уведомления — сквозной компонент, рендерятся хостом
        # Jira в TOP-документе (см. докстринг notification.py).
        self.notification = Notification(page)

    def open(self, issue_key: str) -> None:
        self.goto(_settings.issue_url(issue_key))
        # На первом визите в инстанс с нового браузерного профиля Jira может
        # показать онбординг-оверлеи (Quickstart, Rovo-приглашение, coachmark-
        # тултипы) поверх сайдбара — закрываем их до любых проверок/кликов.
        self.dismiss_onboarding_overlays()

    def has_reminder_section(self, timeout_ms: int = 10_000) -> bool:
        """Проверяет наличие контекстной секции плагина Reminder в сайдбаре задачи."""
        return self.reminder_panel.is_present(timeout_ms=timeout_ms)

    def has_recipients_visibility_warning_flag(
        self, timeout_ms: int = 10_000
    ) -> bool:
        """
        REMCL-2734/2735: проверяет, что после создания ремайндера появился
        предупреждающий flag с текстом RECIPIENTS_VISIBILITY_WARNING_TEXT.

        ИСПРАВЛЕНО (2026-11-25): делегирует в Notification.has_with_text().
        Сигнатура и смысл сохранены. Поиск по-прежнему идёт в TOP-документе
        (флаг рендерит хост Jira через AtlasKit FlagGroup, вне iframe
        приложения) — это теперь зафиксировано разметкой, а не предположением.

        ВНИМАНИЕ (находка 2026-11-25): флаг живёт ~5 секунд и исчезает сам.
        Вызывать СРАЗУ после submit(), до долгих проверок контента страницы.
        Прежний таймаут 10с сохранён для совместимости, но он БОЛЬШЕ времени
        жизни флага: при отсутствии флага тест будет ждать лишние секунды.
        Для новых тестов используйте notification.wait_for(kind="Warning")
        с дефолтным коротким таймаутом.

        ТЕХНИЧЕСКИЙ РИСК (не снят): текст подтверждён скриншотом только для
        recipient'а-пользователя (REMCL-2734). Для группы (REMCL-2735) тот же
        текст предполагается по аналогии — отдельным скриншотом не подтверждён.
        """
        return self.notification.has_with_text(
            RECIPIENTS_VISIBILITY_WARNING_TEXT, timeout_ms=timeout_ms
        )