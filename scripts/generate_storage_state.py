"""
Разовый (или по мере протухания сессии) бутстрап: логинится под тестовым
пользователем и сохраняет Playwright storage_state, чтобы обычные автотесты
переиспользовали сессию и не проходили email-код подтверждения на каждом
прогоне (см. README -> "Авторизация и email-код подтверждения").

Запуск из корня проекта (обычный тестовый пользователь):
    python -m scripts.generate_storage_state

Запуск для ВТОРОГО тестового пользователя — БЕЗ права 'Ability to create
reminders for groups or roles' (см. REMCL-1076/1079/1065) — через флаг --as:
    python -m scripts.generate_storage_state --as=without_group_reminder_permission

Если Atlassian запросит код подтверждения с почты — скрипт возьмёт его из
переменной окружения EMAIL_OTP_CODE:
    EMAIL_OTP_CODE=ABC123 python -m scripts.generate_storage_state
либо, если переменная не задана и запуск интерактивный, запросит код через
input(). Это же работает и для второго пользователя (--as=...) — email-код
придёт на ЕГО почту, а EMAIL_OTP_CODE остаётся общей переменной для обоих
(запуски в любом случае разделены по времени, а не параллельны).

Логика логина вынесена в login_and_save_storage_state(), чтобы её же
переиспользовали фикстуры _ensured_storage_state /
_ensured_without_group_reminder_permission_storage_state в
fixtures/conftest.py (автоматическая регенерация протухшей сессии перед
прогоном тестов) — без копипасты флоу логина в нескольких местах (см.
правило DRY в Project Instructions). Функция изначально была жёстко привязана
к обычному пользователю; теперь принимает email/password/storage_state_path
как необязательные переопределения именно для того, чтобы её же можно было
переиспользовать для второго (и в будущем — третьего, см.
JIRA_USER_WITHOUT_ISSUE_ACCESS_* в .env.example) тестового аккаунта без
копипасты всего флоу логина.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from playwright.sync_api import Browser, sync_playwright  # noqa: E402

from config.settings import Settings, get_settings  # noqa: E402
from pages.login_page import LoginPage  # noqa: E402

# Известные "профили" аккаунтов для CLI-флага --as (см. main() ниже). Ключ —
# значение флага; значения берутся из соответствующих полей Settings.
_KNOWN_ACCOUNT_PROFILES = frozenset({"main", "without_group_reminder_permission"})


def login_and_save_storage_state(
    settings: Settings,
    browser: Browser | None = None,
    *,
    email: str | None = None,
    password: str | None = None,
    storage_state_path: Path | None = None,
    account_label: str = "обычного тестового пользователя",
) -> None:
    """
    Логинится и сохраняет storage_state.

    По умолчанию (без email/password/storage_state_path) логинится под
    ОБЫЧНЫМ тестовым пользователем и сохраняет сессию в
    settings.storage_state_path — ровно как раньше. Чтобы залогиниться под
    ДРУГИМ аккаунтом (например, пользователем без права на групповые
    ремайндеры, REMCL-1076/1079/1065), передайте его email/password и
    отдельный storage_state_path — ничего в логике логина при этом не
    меняется, меняются только креды и файл, в который сохраняется сессия.

    Если передан уже запущенный `browser` (например, из pytest-playwright
    фикстуры `browser` в fixtures/conftest.py) — логин выполняется в НОВОМ
    контексте этого же браузера, без запуска отдельного процесса браузера.
    Если `browser` не передан (обычный CLI-запуск этого файла) — поднимает
    свой Playwright + браузер и закрывает их по завершению, как и раньше.
    """
    login_email = email if email is not None else settings.jira_user_email
    login_password = (
        password
        if password is not None
        else settings.jira_user_password.get_secret_value()
    )
    target_storage_state_path = (
        storage_state_path
        if storage_state_path is not None
        else settings.storage_state_path
    )

    target_storage_state_path.parent.mkdir(parents=True, exist_ok=True)

    def _run(active_browser: Browser) -> None:
        context = active_browser.new_context(
            locale="ru-RU", timezone_id="Europe/Moscow"
        )
        page = context.new_page()

        login_page = LoginPage(page)
        login_page.open()
        login_page.login_with_password(login_email, login_password)

        if login_page.is_email_verification_required():
            code = os.environ.get("EMAIL_OTP_CODE")
            if not code:
                print(
                    f"Проверьте почту {login_email} — "
                    "Atlassian прислал код подтверждения."
                )
                code = input("Введите код подтверждения: ").strip()
            login_page.enter_email_verification_code(code)

        login_page.decline_two_factor_prompt_if_present()

        if not login_page.is_logged_in(timeout_ms=15_000):
            current_url = page.url
            context.close()
            raise RuntimeError(
                f"Не удалось залогиниться ({account_label}, {login_email!r}): "
                f"текущий URL {current_url!r}. Проверьте креды в .env и "
                "вывод выше."
            )

        context.storage_state(path=str(target_storage_state_path))
        print(
            f"storage_state ({account_label}) сохранён: " f"{target_storage_state_path}"
        )
        context.close()

    if browser is not None:
        _run(browser)
        return

    with sync_playwright() as p:
        browser_type = getattr(p, settings.browser)
        launch_kwargs: dict = {"headless": settings.headless}
        if settings.browser_channel:
            # Использовать уже установленный в системе браузер (chrome/msedge)
            # вместо бандлованного — нужно, когда playwright install не может
            # поставить свой Chromium/Firefox/WebKit под текущую ОС (см. .env).
            launch_kwargs["channel"] = settings.browser_channel
        own_browser = browser_type.launch(**launch_kwargs)
        try:
            _run(own_browser)
        finally:
            own_browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--as",
        dest="account",
        choices=sorted(_KNOWN_ACCOUNT_PROFILES),
        default="main",
        help=(
            "Под каким тестовым аккаунтом логиниться: 'main' (обычный "
            "тестовый пользователь, по умолчанию) или "
            "'without_group_reminder_permission' (пользователь без права "
            "'Ability to create reminders for groups or roles', см. "
            "REMCL-1076/1079/1065 — требует JIRA_USER_WITHOUT_GROUP_"
            "REMINDER_PERMISSION_EMAIL/_PASSWORD в .env)."
        ),
    )
    args = parser.parse_args()

    settings = get_settings()

    if args.account == "main":
        login_and_save_storage_state(settings)
        return

    # args.account == "without_group_reminder_permission"
    if not settings.has_user_without_group_reminder_permission_credentials():
        raise SystemExit(
            "JIRA_USER_WITHOUT_GROUP_REMINDER_PERMISSION_EMAIL/_PASSWORD не "
            "заданы в .env — без них нельзя залогиниться под этим "
            "пользователем (см. .env.example и REMCL-1076/1079/1065)."
        )
    login_and_save_storage_state(
        settings,
        email=settings.jira_user_without_group_reminder_permission_email,
        password=(
            settings.jira_user_without_group_reminder_permission_password.get_secret_value()
        ),
        storage_state_path=settings.without_group_reminder_permission_storage_state_path,
        account_label="пользователя без права на групповые ремайндеры",
    )


if __name__ == "__main__":
    main()
