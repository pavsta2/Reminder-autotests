"""
Тест: авторизация под обычным пользователем, открытие задачи CPR1-10 и
проверка наличия контекстной секции плагина Reminder в сайдбаре задачи.

Логинится явно через LoginPage в НОВОМ контексте (fresh_page), а не через
переиспользуемый storage_state — т.к. тест фактически проверяет сам login
flow (см. Project Instructions: "Тесты на сам flow авторизации логинятся
явно через LoginPage").

Atlassian почти всегда присылает на новое устройство/сессию одноразовый код
подтверждения на почту пользователя — автоматически получить его без доступа
к почте нельзя (см. README -> "Email-код подтверждения"). Чтобы прогнать этот
тест, передайте код через переменную окружения EMAIL_OTP_CODE:

    EMAIL_OTP_CODE=ABC123 pytest tests/ui/test_login.py

Если код требуется, а переменная не задана — тест аккуратно скипается
(а не падает) с понятной причиной.
"""

from __future__ import annotations

import os

import allure
import pytest

from config.settings import Settings
from pages.issue_page import IssuePage
from pages.login_page import LoginPage

ISSUE_KEY = "CPR1-10"


@allure.severity(allure.severity_level.CRITICAL)
@allure.label("feature", "Issue panel")
@allure.label("story", "Reminder context section")
@pytest.mark.ui
@pytest.mark.auth
@pytest.mark.issue_panel
@pytest.mark.smoke
def test_login_and_reminder_section_present(settings: Settings, fresh_page) -> None:
    login_page = LoginPage(fresh_page)
    issue_page = IssuePage(fresh_page)

    with allure.step("Открыть страницу логина Jira Cloud"):
        login_page.open()

    with allure.step("Ввести email и пароль обычного тестового пользователя"):
        login_page.login_with_password(
            settings.jira_user_email,
            settings.jira_user_password.get_secret_value(),
        )

    if login_page.is_email_verification_required():
        code = os.environ.get("EMAIL_OTP_CODE")
        if not code:
            pytest.skip(
                "Atlassian запросил код подтверждения с почты, а переменная "
                "окружения EMAIL_OTP_CODE не задана. Либо передайте код "
                "(EMAIL_OTP_CODE=... pytest ...), либо один раз сгенерируйте "
                "storage_state через scripts/generate_storage_state.py и "
                "используйте обычные тесты с переиспользованием сессии."
            )
        with allure.step("Ввести код подтверждения, присланный на почту"):
            login_page.enter_email_verification_code(code)

    with allure.step("Отказаться от предложения включить 2FA, если оно появилось"):
        login_page.decline_two_factor_prompt_if_present()

    with allure.step("Дождаться перехода на инстанс Jira"):
        assert login_page.is_logged_in(), f"Логин не выполнен, текущий URL: {login_page.current_url}"

    with allure.step(f"Открыть задачу {ISSUE_KEY}"):
        issue_page.open(ISSUE_KEY)

    with allure.step("Проверить наличие контекстной секции Reminder в сайдбаре задачи"):
        assert issue_page.has_reminder_section(), "Секция Reminder не найдена на странице задачи"
