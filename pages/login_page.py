"""
LoginPage — страница авторизации Jira Cloud (id.atlassian.com).

Найдено при живом исследовании (сессия Claude in Chrome / built-in browser,
инстанс https://starshinov-release.atlassian.net, 2026-11-11):

1. Переход на {host}/browse/{issue_key} неавторизованным пользователем
   редиректит на https://id.atlassian.com (форма в два шага: email -> password).
2. После email+пароль Atlassian почти всегда присылает одноразовый код на
   почту пользователя («Вам отправлен код по электронной почте») — 6 отдельных
   однобуквенных/одноцифровых полей с accessible-name вида
   "Please enter OTP character N" (эти лейблы на английском независимо от
   локали интерфейса — удобно для устойчивого локатора).
3. Диалог предложения включить двухфакторную аутентификацию появляется для
   новых браузерных профилей/сессий (не появился в первой сессии разведки
   через browser-pane с уже знакомым Atlassian браузером, но появился при
   первом реальном прогоне через чистый Chrome-профиль). Текст кнопки
   отказа подтверждён реальным прогоном (headed, 2026-11-12):
   "Продолжить без двухфакторной аутентификации".

Дополнено по итогам первого реального прогона через Playwright (не через
browser-pane, настоящий Chrome): кнопка подтверждения OTP имеет стабильный
id `#otp-submit`. Важно: этот виджет в некоторых случаях САМ сабмитится,
как только заполнены все 6 полей (кнопка в этот момент может уже быть
disabled/удалена из DOM) — поэтому клик по ней не должен блокировать тест
надолго, если он не удался.
"""

from __future__ import annotations

import re
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from config.settings import get_settings
from pages.base_page import BasePage

_settings = get_settings()

_OTP_LABEL_RE = re.compile(r"OTP character", re.IGNORECASE)

# Точный текст подтверждён реальным прогоном (headed, 2026-11-12):
# "Продолжить без двухфакторной аутентификации". Остальные варианты оставлены
# как запасные на случай A/B-формулировок или смены локали интерфейса.
_DECLINE_2FA_TEXTS = [
    "Продолжить без двухфакторной аутентификации",
    "Not now",
    "Remind me later",
    "Skip for now",
    "Continue without two-factor authentication",
    "Не сейчас",
    "Напомнить позже",
    "Пропустить",
]


class LoginPage(BasePage):
    """Страница логина Atlassian ID (id.atlassian.com)."""

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        # type=email / type=password — локаль-независимые, стабильные CSS-атрибуты.
        self._email_input = page.locator('input[type="email"]')
        self._password_input = page.locator('input[type="password"]')
        # На обоих шагах (email -> Продолжить, password -> Войти) кнопка — submit.
        self._submit_button = page.locator('button[type="submit"]')
        self._otp_inputs = page.get_by_role("textbox", name=_OTP_LABEL_RE)

    # --- Основной флоу ---

    def open(self) -> None:
        self.goto(_settings.jira_host)

    def fill_email(self, email: str) -> None:
        self.fill(self._email_input, email)
        self.click(self._submit_button)

    def fill_password(self, password: str) -> None:
        self.fill(self._password_input, password)
        self.click(self._submit_button)

    def login_with_password(self, email: str, password: str) -> None:
        """Email + пароль. НЕ обрабатывает email-код подтверждения — это отдельный шаг,
        т.к. код живёт в почте и не может быть получен автоматически без доступа к ней
        (см. is_email_verification_required / enter_email_verification_code)."""
        self.fill_email(email)
        self.fill_password(password)

    # --- Email-код подтверждения (OTP) ---

    def is_email_verification_required(self, timeout_ms: int = 5_000) -> bool:
        """Проверяет, показан ли экран «Вам отправлен код по электронной почте»."""
        return self.is_visible(self._otp_inputs.first, timeout_ms=timeout_ms)

    def enter_email_verification_code(self, code: str) -> None:
        """
        Вводит код подтверждения, присланный на почту, в 6 отдельных полей
        и подтверждает форму.

        code: строка длиной 6 символов (цифры/буквы, как прислал Atlassian).
        """
        code = code.strip()
        boxes = self._otp_inputs
        count = boxes.count()
        if count == 0:
            raise AssertionError("Поля ввода email-кода не найдены на странице")
        if len(code) != count:
            raise ValueError(f"Код подтверждения должен содержать {count} символ(ов), получено: {len(code)!r}")

        for i in range(count):
            boxes.nth(i).fill(code[i])

        # Кнопка подтверждения OTP — стабильный id #otp-submit (подтверждено
        # реальным прогоном). Если он вдруг пропадёт у Atlassian — откатываемся
        # на общий button[type=submit].
        submit = self.page.locator("#otp-submit")
        if submit.count() == 0:
            submit = self._submit_button

        try:
            # Короткий таймаут, а не self.timeout/30с по умолчанию: виджет
            # иногда сабмитится сам сразу после заполнения последнего поля,
            # и кнопка к моменту клика уже disabled или удалена из DOM —
            # это не ошибка, а нормальный исход, дальше это проверят
            # decline_two_factor_prompt_if_present()/is_logged_in().
            submit.first.click(timeout=5_000)
        except PlaywrightTimeoutError:
            pass

    # --- Опциональный диалог включения 2FA ---

    def decline_two_factor_prompt_if_present(self, timeout_ms: int = 3_000) -> bool:
        """
        Если после логина/подтверждения кода показывается предложение включить
        двухфакторную аутентификацию — отказывается от него. Если диалог не
        появился за timeout_ms — тихо продолжает (диалог необязателен).

        ТЕХНИЧЕСКИЙ РИСК: точный локатор/текст кнопки не подтверждён вживую
        (см. docstring модуля). Перебираем несколько вероятных вариантов текста.
        """
        for text in _DECLINE_2FA_TEXTS:
            button = self.page.get_by_role("button", name=text, exact=False)
            if self.click_if_visible(button, timeout_ms=timeout_ms):
                return True
        return False

    def is_logged_in(self, timeout_ms: Optional[int] = None) -> bool:
        """Грубая проверка: ушли с id.atlassian.com на инстанс Jira."""
        try:
            self.page.wait_for_url(
                re.compile(re.escape(_settings.jira_host)),
                timeout=timeout_ms or self.timeout,
            )
            return True
        except Exception:
            return _settings.jira_host in self.current_url
