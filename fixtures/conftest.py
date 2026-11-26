"""
Общие фикстуры фреймворка: конфигурация, переиспользование сессии браузера
(storage_state) и вложения в Allure при падении теста.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import allure
import pytest
from playwright.sync_api import Browser, Page

from config.settings import Settings, get_settings
from pages.components.reminder_panel import Environment
from pages.issue_page import IssuePage
from pages.login_page import LoginPage
from scripts.generate_storage_state import login_and_save_storage_state
from utils.mail_client import MailClient
from pages.components.reminder_modal import ReminderModal


def pytest_addoption(parser: pytest.Parser) -> None:
    """
    Регистрирует CLI-флаг --app-env, чтобы выбирать, с какой инсталляцией
    аппа Reminder работает прогон — prod (по умолчанию) / stg / dev. Нужно
    на инстансах, где одновременно установлено несколько окружений (см.
    docstring ReminderPanel, п.6, и IssuePage) — например:
    `pytest --app-env=stg tests/ui/test_reminder_recipients.py`.

    На инстансах с единственной инсталляцией (CPR1/REMCL) флаг можно не
    указывать — дефолтный "prod" соответствует прежнему поведению.

    Эта функция определена здесь (fixtures/conftest.py), а не в корневом
    conftest.py, но исправно подхватывается pytest: корневой conftest.py
    подключает этот модуль как плагин через `pytest_plugins =
    ["fixtures.conftest"]` НА РАННЕЙ стадии (до финального разбора argv),
    поэтому pytest_addoption отсюда учитывается точно так же, как если бы
    был объявлен прямо в корневом conftest.py — проверено механически
    отдельным изолированным pytest-проектом, воспроизводящим эту же схему
    (root conftest.py -> pytest_plugins -> fixtures/conftest.py с
    pytest_addoption): `pytest --app-env=stg` и дефолт без флага оба
    отработали корректно, а `--app-env=bogus` корректно упал с ошибкой
    argparse "invalid choice".
    """
    parser.addoption(
        "--app-env",
        action="store",
        default="prod",
        choices=["prod", "stg", "dev"],
        help=(
            "Какую инсталляцию аппа Reminder использовать на инстансах с "
            "несколькими одновременно установленными окружениями "
            "(prod/stg/dev, см. ReminderPanel). По умолчанию: prod."
        ),
    )
    parser.addoption(
        "--issue-key",
        action="store",
        default="CPR1-10",
        help=(
            "Issue key задачи Jira, на странице которой тесты ищут секцию "
            "Reminder (используется, например, фикстурой recipients_modal в "
            "tests/ui/test_reminder_recipients.py). По умолчанию: CPR1-10 — "
            "задача с подтверждённым наличием секции Reminder и правом "
            "текущего пользователя на выбор групп/ролей (см. "
            "tests/ui/test_login.py). На другом инстансе (другой JIRA_HOST в "
            "`.env`, например starshinov-pr с несколькими окружениями — см. "
            "--app-env выше) нужно указать СВОЙ issue key, например: "
            "`pytest --issue-key=PKP-5 --app-env=stg ...`."
        ),
    )


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings()


@pytest.fixture(scope="session")
def app_env(request: pytest.FixtureRequest) -> Environment:
    """
    Окружение аппа Reminder (prod/stg/dev), выбранное через CLI-флаг
    --app-env (см. pytest_addoption выше). Используется фикстурой
    issue_page, чтобы ReminderPanel искал секцию именно нужной инсталляции.
    """
    return request.config.getoption("--app-env")


@pytest.fixture(scope="session")
def issue_key(request: pytest.FixtureRequest) -> str:
    """
    Issue key, выбранный через CLI-флаг --issue-key (см. pytest_addoption
    выше). По умолчанию CPR1-10 — дефолт самого флага. Используется
    фикстурами, которым нужна конкретная задача с секцией Reminder (см.
    recipients_modal в tests/ui/test_reminder_recipients.py).
    """
    return request.config.getoption("--issue-key")


@pytest.fixture(scope="session")
def browser_type_launch_args(
    browser_type_launch_args: dict, settings: Settings
) -> dict:
    """
    Если playwright install не может поставить бандлованный браузер под
    текущую ОС (например "Playwright does not support chromium on mac12" на
    старых macOS) — задайте BROWSER_CHANNEL=chrome в .env, и Playwright будет
    водить уже установленный в системе Google Chrome / Edge вместо скачивания
    своего Chromium. Не требует playwright install вообще для этого браузера.
    """
    args = dict(browser_type_launch_args)
    if settings.browser_channel:
        args["channel"] = settings.browser_channel
    return args


def _storage_state_is_valid(
    browser: Browser, storage_state_path: Path, *, target_url: str
) -> bool:
    """
    Открывает `target_url` в отдельном одноразовом контексте с указанным
    storage_state (если файл существует) и проверяет, что Jira не
    редиректнула на логин (id.atlassian.com). Используется только для
    sanity-проверки перед прогоном — поэтому навигация здесь намеренно
    упрощена, без retry из BasePage.goto на транзиентные сбои Atlassian CDN.

    Обобщённая версия (параметризована storage_state_path/target_url, а не
    жёстко привязана к settings.storage_state_path/settings.my_reminders_url
    обычного пользователя) — чтобы её же переиспользовать для ВТОРОГО
    тестового аккаунта (см. _ensured_without_group_reminder_permission_
    storage_state ниже), без копипасты (см. правило DRY в Project
    Instructions).
    """
    if not storage_state_path.exists():
        return False

    context = browser.new_context(storage_state=str(storage_state_path))
    try:
        page = context.new_page()
        page.goto(target_url, wait_until="domcontentloaded", timeout=20_000)
        return "id.atlassian.com" not in page.url
    finally:
        context.close()


def _session_is_valid(browser: Browser, settings: Settings) -> bool:
    """Sanity-проверка сессии ОБЫЧНОГО тестового пользователя (см. выше)."""
    return _storage_state_is_valid(
        browser, settings.storage_state_path, target_url=settings.my_reminders_url
    )


@pytest.fixture(scope="session")
def _ensured_storage_state(browser: Browser, settings: Settings) -> Path:
    """
    Гарантирует валидный storage_state ДО того, как browser_context_args
    соберёт итоговые аргументы контекста. Это важно: browser_context_args —
    session-scope фикстура, pytest вычисляет и кеширует её РОВНО ОДИН раз за
    весь прогон, поэтому регенерация файла на диске ПОСЛЕ того, как
    browser_context_args уже собрала словарь аргументов, никуда не попала бы —
    все созданные дальше контексты тестов продолжали бы использовать старый/
    отсутствующий storage_state. Поэтому проверка и, если нужно, логин должны
    случиться раньше, а не внутри отдельных фикстур страниц типа issue_page.

    Если storage_state отсутствует или протух — автоматически прогоняет тот
    же флоу логина, что и `python -m scripts.generate_storage_state`
    (включая обработку email-кода через EMAIL_OTP_CODE или интерактивный
    input(), и отказ от предложения 2FA — см. scripts/generate_storage_state.py
    и pages/login_page.py). Если и это не помогло (неверные креды, код не
    пришёл и т.п.) — падает с понятной ошибкой сразу в начале прогона, а не
    по отдельности в каждом тесте, которому нужна авторизация.

    ВАЖНО: при протухшей/отсутствующей сессии первый запуск pytest после
    этого добавит реальный живой логин (секунды — десятки секунд, а при
    запросе email-кода без EMAIL_OTP_CODE — паузу на интерактивный ввод кода
    с почты, совершенно так же, как при ручном запуске скрипта). Это
    осознанный компромисс: вместо отдельного ручного шага "сначала запустите
    scripts.generate_storage_state" прогон сам делает это по требованию.
    Если это нежелательно (например, не хочется, чтобы pytest незаметно
    открывал живой логин) — выставьте SKIP_AUTO_LOGIN=1, тогда при протухшей
    сессии будет фейл с инструкцией вместо автологина.
    """
    if _session_is_valid(browser, settings):
        return settings.storage_state_path

    if os.environ.get("SKIP_AUTO_LOGIN"):
        pytest.fail(
            "storage_state отсутствует или протух "
            f"({settings.storage_state_path}), а SKIP_AUTO_LOGIN=1 — "
            "автологин отключён. Сгенерируйте сессию вручную: "
            "python -m scripts.generate_storage_state (см. README)."
        )

    login_and_save_storage_state(settings, browser=browser)

    if not _session_is_valid(browser, settings):
        pytest.fail(
            "Не удалось автоматически получить валидную сессию "
            f"({settings.storage_state_path}) даже после попытки логина. "
            "Проверьте креды в .env и попробуйте запустить вручную: "
            "python -m scripts.generate_storage_state (см. README)."
        )

    return settings.storage_state_path


@pytest.fixture(scope="session")
def browser_context_args(
    browser_context_args: dict, settings: Settings, _ensured_storage_state: Path
) -> dict:
    """
    Расширяем стандартные аргументы контекста pytest-playwright:
    - переиспользуем (и при необходимости автоматически регенерируем —
      см. _ensured_storage_state выше) сохранённую сессию обычного
      пользователя (storage_state);
    - фиксируем локаль/часовой пояс, т.к. UI плагина завязан на часовой пояс
      пользователя (см. ReminderPanel: "Your time zone: ...").
    """
    return {
        **browser_context_args,
        "locale": "ru-RU",
        "timezone_id": "Europe/Moscow",
        "storage_state": str(_ensured_storage_state),
    }


@pytest.fixture
def issue_page(page: Page, app_env: Environment) -> IssuePage:
    return IssuePage(page, environment=app_env)


@pytest.fixture
def login_page(page: Page) -> LoginPage:
    return LoginPage(page)


@pytest.fixture
def fresh_page(browser: Browser, browser_context_args: dict) -> Iterator[Page]:
    """
    Страница в НОВОМ контексте без переиспользования storage_state —
    для тестов, которые явно проверяют сам процесс логина (см.
    tests/ui/test_login.py). Обычные тесты используют стандартную фикстуру
    `page` из pytest-playwright (с уже подмешанным storage_state, если он
    сгенерирован).
    """
    args = dict(browser_context_args)
    args.pop("storage_state", None)
    context = browser.new_context(**args)
    page = context.new_page()
    yield page
    context.close()


# --- Второй тестовый пользователь: БЕЗ права 'Ability to create reminders
# for groups or roles' (см. REMCL-1076/1079/1065) ---


@pytest.fixture(scope="session")
def _ensured_without_group_reminder_permission_storage_state(
    browser: Browser, settings: Settings
) -> Path | None:
    """
    Аналог _ensured_storage_state (см. выше), но для ВТОРОГО тестового
    аккаунта — пользователя без права на групповые ремайндеры.

    Если JIRA_USER_WITHOUT_GROUP_REMINDER_PERMISSION_EMAIL/_PASSWORD не
    заданы в .env — возвращает None (а не падает и не логинится под обычным
    пользователем по ошибке): единственное отображаемое имя, которое могло
    быть задано раньше (JIRA_USER_WITHOUT_GROUP_REMINDER_PERMISSION_
    DISPLAY_NAME), НЕДОСТАТОЧНО, чтобы реально залогиниться под этим
    аккаунтом. Тест/фикстура, которой нужна эта сессия (см.
    user_without_group_reminder_permission_page ниже), сами honestly
    skip'аются, увидев None — ровно тот же принцип, что уже применяется к
    multiple_groups в tests/ui/test_reminder_recipients.py при недостатке
    настроенных групп.

    Намеренно НЕ использует SKIP_AUTO_LOGIN обычного пользователя — если
    креды этого пользователя заданы, автологин под ним выполняется всегда
    (сам факт настройки этих переменных в .env — осознанное решение
    завести этот тест, а не случайность, в отличие от основной сессии,
    которая нужна почти всем тестам).
    """
    if not settings.has_user_without_group_reminder_permission_credentials():
        return None

    state_path = settings.without_group_reminder_permission_storage_state_path
    target_url = settings.my_reminders_url

    if _storage_state_is_valid(browser, state_path, target_url=target_url):
        return state_path

    login_and_save_storage_state(
        settings,
        browser=browser,
        email=settings.jira_user_without_group_reminder_permission_email,
        password=(
            settings.jira_user_without_group_reminder_permission_password.get_secret_value()
        ),
        storage_state_path=state_path,
        account_label="пользователя без права на групповые ремайндеры",
    )

    if not _storage_state_is_valid(browser, state_path, target_url=target_url):
        pytest.fail(
            "Не удалось автоматически получить валидную сессию пользователя "
            f"без права на групповые ремайндеры ({state_path}) даже после "
            "попытки логина. Проверьте JIRA_USER_WITHOUT_GROUP_REMINDER_"
            "PERMISSION_EMAIL/_PASSWORD в .env и попробуйте запустить вручную: "
            "python -m scripts.generate_storage_state "
            "--as=without_group_reminder_permission (см. README)."
        )

    return state_path


@pytest.fixture
def user_without_group_reminder_permission_page(
    browser: Browser,
    _ensured_without_group_reminder_permission_storage_state: Path | None,
) -> Iterator[Page]:
    """
    Страница в НОВОМ, НЕЗАВИСИМОМ от обычного пользователя контексте —
    авторизованная под тестовым аккаунтом без права 'Ability to create
    reminders for groups or roles' (см. REMCL-1076/1079/1065).

    Honestly skip'ает тест (а не падает/не подменяет обычным
    пользователем), если JIRA_USER_WITHOUT_GROUP_REMINDER_PERMISSION_EMAIL/
    _PASSWORD не заданы в .env — см. docstring _ensured_without_group_
    reminder_permission_storage_state выше и .env.example.

    НАМЕРЕННО НЕ берёт готовый словарь из фикстуры `browser_context_args`
    (как это делает, например, `fresh_page` выше) — `browser_context_args`
    session-scope и сама тянет `_ensured_storage_state` ОБЫЧНОГО
    пользователя, то есть при первом обращении попыталась бы
    залогинить/провалидировать ЕГО сессию, даже если тест этой фикстурой
    вообще не пользуется. Это сделало бы тесты на втором пользователе
    зависимыми от валидности credentials первого — прямо противоречит
    смыслу "независимая сессия". Поэтому локаль/часовой пояс здесь
    продублированы (те же значения, что и в browser_context_args) явно,
    а не унаследованы.
    """
    if _ensured_without_group_reminder_permission_storage_state is None:
        pytest.skip(
            "JIRA_USER_WITHOUT_GROUP_REMINDER_PERMISSION_EMAIL/_PASSWORD не "
            "заданы в .env — тест, которому нужна отдельная сессия "
            "пользователя без права на групповые ремайндеры, пропущен "
            "(см. REMCL-1076/1079/1065 и .env.example)."
        )

    context = browser.new_context(
        locale="ru-RU",
        timezone_id="Europe/Moscow",
        storage_state=str(_ensured_without_group_reminder_permission_storage_state),
    )
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture
def issue_page_as_user_without_group_reminder_permission(
    user_without_group_reminder_permission_page: Page, app_env: Environment
) -> IssuePage:
    """
    IssuePage, открываемый пользователем без права на групповые ремайндеры
    (см. user_without_group_reminder_permission_page выше) — для
    test_groups_and_roles_hidden_for_user_without_rights в
    tests/ui/test_reminder_recipients.py.
    """
    return IssuePage(user_without_group_reminder_permission_page, environment=app_env)


# --- Почта: проверка РЕАЛЬНОЙ доставки письма (REMCL-1114 и т.п.) ---


@pytest.fixture
def mail_client(settings: Settings) -> MailClient:
    """
    MailClient (см. utils/mail_client.py) для тестов с меткой
    @pytest.mark.email, которым нужно подтвердить, что плагин Reminder
    РЕАЛЬНО отправил письмо (а не только показал что-то в UI) — например,
    проверка дедупликации получателей, REMCL-1114.

    Honestly skip'ает тест (а не падает с неясной ошибкой IMAP-подключения
    или не притворяется обычным пользователем), если MAIL_IMAP_HOST/
    _LOGIN/_PASSWORD не заданы в .env — см. Settings.has_mail_imap_
    credentials и README.
    """
    if not settings.has_mail_imap_credentials():
        pytest.skip(
            "MAIL_IMAP_HOST/_LOGIN/_PASSWORD не заданы в .env — тест, "
            "которому нужна проверка реальной доставки письма по IMAP, "
            "пропущен (см. README)."
        )
    return MailClient(settings)


# --- Allure: скриншот и HTML-дамп страницы при падении теста ---


def _get_page_even_if_setup_failed(item) -> Page | None:
    """
    Достаёт текущую `page`, даже если тест упал ВНУТРИ фикстуры (setup),
    не дойдя до тела теста.

    `item.funcargs` заполняется ТОЛЬКО когда весь граф фикстур теста
    успешно разрешился — если упадёт фикстура в середине цепочки (например,
    recipients_modal после того, как issue_page/page уже отработали), то
    `item.funcargs.get("page")` вернёт None, даже если `page` была создана
    и уже успела что-то сделать (проверено механически: простой фикстуре,
    которая берёт `page`, что-то на ней делает и затем падает, — funcargs
    оказывается пуст). Поэтому при setup-падении лезем напрямую в кеш
    результата фикстуры `page` через `item._fixtureinfo.name2fixturedefs`
    (у каждого `FixtureDef` после успешного выполнения `cached_result`
    хранит `(result, cache_key, exc_info)`) — это уже сработавшая фикстура,
    просто ещё не попавшая в funcargs. Используется приватный API pytest,
    но именно так эту задачу решают сами авторы pytest-playwright/allure-
    pytest в похожих плагинах; альтернативы через публичный API нет.
    """
    page = item.funcargs.get("page")
    if page is not None:
        return page

    fixturedefs = item._fixtureinfo.name2fixturedefs.get("page")
    if not fixturedefs:
        return None
    for fixturedef in reversed(fixturedefs):
        cached = getattr(fixturedef, "cached_result", None)
        if cached is not None:
            return cached[0]
    return None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Сохраняет отчёт по каждой фазе прогона (setup/call/teardown) и, если
    тест упал на setup или call, сразу же прикладывает в Allure скриншот,
    HTML-дамп страницы и текущий URL — пока `page` ещё жива.

    РАНЬШЕ это делалось отдельной autouse-фикстурой
    `_attach_debug_info_on_failure` с `yield`, и её код после `yield`
    (teardown) ничего не прикладывал: pytest инстанцирует autouse-фикстуру
    БЕЗ зависимостей раньше, чем обычную `page` (которую тянет issue_page/
    recipients_modal), а финализация идёт в обратном порядке — значит
    `page`/`context` от pytest-playwright закрывались ПЕРВЫМИ, и только
    потом резюмировался `_attach_debug_info_on_failure`, пытаясь сделать
    screenshot/content() на уже закрытой странице. Исключение тихо
    проглатывалось в `try/except: pass`, поэтому вложений не было вообще
    ни у одного теста. Здесь же это выполняется прямо в фазе "call"/"setup"
    hook'а makereport — ДО того как teardown фикстур теста вообще начнётся,
    пока `page` точно ещё открыта.

    ДОПОЛНЕНО: падение именно на "setup" (например, recipients_modal упала
    внутри open_create_modal/wait_until_ready, не дойдя до теста) сначала
    всё равно оставалось без скриншота — см. _get_page_even_if_setup_failed
    выше за объяснением и проверкой.
    """
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)

    if report.when not in ("setup", "call") or not report.failed:
        return

    page = _get_page_even_if_setup_failed(item)
    if page is None:
        return

    try:
        allure.attach(
            page.screenshot(full_page=True),
            name="screenshot",
            attachment_type=allure.attachment_type.PNG,
        )
    except Exception:
        pass

    try:
        allure.attach(
            page.content(),
            name="page-source",
            attachment_type=allure.attachment_type.HTML,
        )
    except Exception:
        pass

    try:
        allure.attach(page.url, name="url", attachment_type=allure.attachment_type.TEXT)
    except Exception:
        pass


@pytest.fixture
def reminder_modal(issue_page: IssuePage, issue_key: str) -> ReminderModal:
    """
    Открывает страницу задачи, разворачивает секцию Reminder (если свёрнута)
    и открывает модалку создания ремайндера через кнопку Create.
    Возвращает готовый к использованию ReminderModal.

    Используется тестами блока When (test_reminder_when_field.py) и любыми
    другими тестами, которым нужна открытая форма "New reminder".
    """
    # Открываем страницу задачи и закрываем онбординг-оверлеи, если есть
    issue_page.open(issue_key)

    # Разворачиваем секцию, если она свёрнута (обычно уже развёрнута,
    # но на всякий случай — см. докстринг ReminderPanel про
    # aria-expanded="true" по умолчанию)
    issue_page.reminder_panel.expand()

    # Кликаем Create и ждём готовности формы.
    # ВАЖНО: open_create_modal() сам вызывает wait_until_ready(),
    # поэтому повторно ждать не нужно.
    return issue_page.reminder_panel.open_create_modal()