"""
Конфигурация тестового фреймворка.

Значения читаются из переменных окружения / файла .env (см. .env).
Используем pydantic-settings, чтобы конфиг был валидирован и типизирован,
а не разбросан по os.environ в разных модулях.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
AUTH_DIR = PROJECT_ROOT / "auth"


class Settings(BaseSettings):
    """Единая точка конфигурации для всех Page Object / fixtures / тестов."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Jira Cloud instance ---
    jira_host: str = Field(..., description="Базовый URL тестового инстанса Jira Cloud")

    # --- Обычный тестовый пользователь ---
    jira_user_email: str
    jira_user_password: SecretStr
    # Отображаемое имя обычного тестового пользователя — ровно так, как оно
    # показывается в теге Recipients (подтверждено живым прогоном для
    # REMCL-1063: по умолчанию при открытии формы в Recipients уже стоит тег
    # создателя ремайндера). НЕ совпадает с email. Опционально: если не
    # задано, test_default_recipient_is_reminder_creator honestly skip'ается,
    # а не падает неожиданно у тех, кто ещё не прописал его в .env.
    jira_user_display_name: str | None = Field(
        default=None,
        description=(
            "Отображаемое имя обычного тестового пользователя, как оно "
            "показывается в теге Recipients при открытии формы (REMCL-1063)."
        ),
    )

    # --- Реальные тестовые группы (для multi-group кейсов, REMCL-2856 и
    # будущих) ---
    # Список РЕАЛЬНО существующих на тестовом инстансе групп, через запятую
    # (минимум 3 — см. JIRA_TEST_GROUP_NAMES в .env.example). В отличие от
    # "Watchers" (единственная ЗАКРЕПЛЁННАЯ первой опция секции Groups, не
    # зависящая от тестовых данных — см. п.6 докстринга ReminderModal),
    # эти группы — ОБЫЧНЫЕ строки списка, которые нужно искать через
    # search()/option(), как и любое другое не закреплённое имя (ровно та
    # же логика, что уже применяется к "creator" — см. test_reminder_
    # created_successfully_with_user_or_group_recipient). Опционально:
    # если не задано (или задано меньше групп, чем требует конкретный
    # тест), соответствующий multi-group кейс honestly skip'ается через
    # jira_test_group_names_list, а не падает неожиданно.
    jira_test_group_names: str | None = Field(
        default=None,
        description=(
            "Список РЕАЛЬНО существующих на тестовом инстансе групп через "
            "запятую, минимум 3 — например: "
            "JIRA_TEST_GROUP_NAMES=site-admins,jira-software-users,confluence-users"
        ),
    )

    # --- Группа, реально содержащая обычного тестового пользователя
    # (REMCL-1114 — дедупликация получателей) ---
    # ОТДЕЛЬНАЯ от jira_test_group_names переменная, а не group1/group2/
    # group3 оттуда — см. подробный разбор в docstring test_single_
    # reminder_when_recipient_selected_via_multiple_paths в tests/ui/
    # test_reminder_recipients.py: REMCL-1114 нужна группа, про которую
    # ТОЧНО известно, что в неё входит обычный тестовый пользователь
    # (JIRA_USER_EMAIL) — иначе тест рискует отправить РЕАЛЬНОЕ письмо
    # посторонним людям, если группа содержит ещё кого-то. Reporter/
    # Assignee/Watchers задачи CPR1-10 для этой цели НЕ подходят —
    # живым просмотром 2026-11-18 подтверждено, что это другие люди, не
    # совпадающие с JIRA_USER_DISPLAY_NAME.
    #
    # ИСПРАВЛЕНО (2026-11-19, по живому прогону): REMCL-1114 больше НЕ
    # использует эту переменную — см. mail_test_recipient_display_name и
    # jira_test_group_containing_mail_recipient ниже. Причина: обычный
    # тестовый пользователь (JIRA_USER_EMAIL/JIRA_USER_DISPLAY_NAME) — это
    # аккаунт, под которым тест ЛОГИНИТСЯ, но его почтовый ящик оказался
    # недоступен/не тем, что нужно проверять по IMAP (см. ИСПРАВЛЕНО
    # 2026-11-19 про MAIL_IMAP_LOGIN выше) — тест, который реально ждёт и
    # считает письма, не может одновременно требовать "тот же человек,
    # что залогинен" И "тот же человек, чей ящик мы читаем по IMAP", если
    # на тестовом инстансе это разные удобства. Переменная оставлена (не
    # удалена) — может понадобиться другому тесту, где важен именно
    # creator, а не IMAP-доступный получатель.
    jira_test_group_containing_creator: str | None = Field(
        default=None,
        description=(
            "Имя РЕАЛЬНОЙ группы на тестовом инстансе, членом которой "
            "точно является обычный тестовый пользователь (JIRA_USER_"
            "EMAIL)."
        ),
    )

    # --- Отдельный получатель для тестов, проверяющих РЕАЛЬНУЮ доставку
    # письма (REMCL-1114 и т.п.) — ДОБАВЛЕНО (2026-11-19, по живому
    # прогону) ---
    # НЕ совпадает с обычным тестовым пользователем (JIRA_USER_EMAIL/
    # JIRA_USER_DISPLAY_NAME, под которым тест логинится) — это ОТДЕЛЬНЫЙ
    # реальный пользователь тестового инстанса, чей почтовый ящик совпадает
    # с MAIL_IMAP_LOGIN (см. MAIL_IMAP_* выше) — то есть ровно тот, чьё
    # письмо мы реально можем прочитать по IMAP. Нужны ОБЕ переменные —
    # отображаемое имя (чтобы выбрать его recipient'ом в дропдауне) и
    # группа, которая точно его содержит (та же логика, что у
    # jira_test_group_containing_creator выше, но для ЭТОГО пользователя,
    # а не для creator'а) — иначе рискуем снова отправить письмо
    # посторонним людям, если группа содержит кого-то ещё.
    mail_test_recipient_display_name: str | None = Field(
        default=None,
        description=(
            "Отображаемое имя РЕАЛЬНОГО пользователя тестового инстанса, "
            "чей почтовый ящик указан в MAIL_IMAP_LOGIN — используется "
            "как recipient в тестах, которые реально проверяют доставку "
            "письма по IMAP (REMCL-1114 и т.п.), вместо обычного "
            "тестового пользователя (JIRA_USER_DISPLAY_NAME)."
        ),
    )
    jira_test_group_containing_mail_recipient: str | None = Field(
        default=None,
        description=(
            "Имя РЕАЛЬНОЙ группы на тестовом инстансе, членом которой "
            "точно является MAIL_TEST_RECIPIENT_DISPLAY_NAME выше — нужна "
            "ТОЛЬКО для REMCL-1114 (дедупликация получателей: тот же "
            "человек выбран и напрямую, и через группу — должно прийти "
            "ровно одно письмо)."
        ),
    )

    # --- Группы для REMCL-1118 (ДОБАВЛЕНО 2026-11-19) ---
    # ОТДЕЛЬНАЯ от jira_test_group_names/jira_test_group_containing_
    # mail_recipient переменная — список (через запятую) из НЕСКОЛЬКИХ
    # реальных групп, в КАЖДУЮ из которых явно добавлен MAIL_TEST_
    # RECIPIENT_DISPLAY_NAME (по решению пользователя 2026-11-19— ранее
    # test_all_group_or_role_members_receive_reminder только создавал
    # ремайндер и НЕ проверял доставку, т.к. группа могла содержать людей,
    # чьи ящики нам недоступны; теперь, когда известный пользователь
    # явно состоит во ВСЕХ этих группах, можно реально проверить, что
    # письмо дошло ДО НЕГО по IMAP при выборе recipient'ом каждой из этих
    # групп). ВАЖНО: это НЕ доказывает, что письмо дошло до ВСЕХ
    # участников группы — только до этого одного известного участника;
    # честная формулировка — см. docstring теста.
    jira_test_groups_containing_mail_recipient: str | None = Field(
        default=None,
        description=(
            "Список РЕАЛЬНЫХ групп через запятую, в каждую из которых "
            "явно добавлен MAIL_TEST_RECIPIENT_DISPLAY_NAME — нужен для "
            "REMCL-1118 (проверка реальной доставки письма по IMAP при "
            "выборе recipient'ом группы), например: "
            "JIRA_TEST_GROUPS_CONTAINING_MAIL_RECIPIENT=group-a,group-b"
        ),
    )

    # --- Второй/третий тестовые пользователи с ограниченными правами
    # (задел на будущее — пока ни один тест эти переменные не использует) ---
    jira_user_without_group_reminder_permission_display_name: str | None = Field(
        default=None,
        description=(
            "Отображаемое имя тестового пользователя БЕЗ права 'Ability to "
            "create reminders for groups or roles' (см. REMCL-1076/1079 и "
            "сопутствующий комментарий в docstring tests/ui/test_reminder_"
            "recipients.py)."
        ),
    )
    # Email/пароль этого пользователя — ОБЯЗАТЕЛЬНЫ, чтобы реально залогиниться
    # под ним и получить отдельный storage_state (одного отображаемого имени
    # выше для этого недостаточно). Опционально на уровне Settings: если не
    # заданы — test_groups_and_roles_hidden_for_user_without_rights honestly
    # skip'ается через фикстуру user_without_group_reminder_permission_page
    # (см. fixtures/conftest.py), а не падает у тех, кто ещё не завёл этого
    # пользователя в .env.
    jira_user_without_group_reminder_permission_email: str | None = Field(
        default=None,
        description=(
            "Email тестового пользователя БЕЗ права 'Ability to create "
            "reminders for groups or roles' — нужен для отдельного логина/"
            "storage_state (см. REMCL-1076/1079/1065)."
        ),
    )
    jira_user_without_group_reminder_permission_password: SecretStr | None = Field(
        default=None,
        description=(
            "Пароль тестового пользователя БЕЗ права 'Ability to create "
            "reminders for groups or roles' (см. JIRA_USER_WITHOUT_GROUP_"
            "REMINDER_PERMISSION_EMAIL выше)."
        ),
    )
    # --- Пользователи БЕЗ доступа к тестовой задаче (REMCL-2736) ---
    # В отличие от jira_user_without_group_reminder_permission_* выше,
    # ОТДЕЛЬНАЯ storage_state-сессия здесь НЕ нужна: по смыслу RTM
    # test-кейса (rtm-issues-export_20.zip, см. docstring
    # test_reminder_not_created_for_user_without_issue_access в tests/ui/
    # test_reminder_recipients.py) ограниченный пользователь — это НЕ тот,
    # под кем логинится тест, а просто ЕЩЁ ОДИН recipient, выбираемый в
    # поле Recipients ОБЫЧНЫМ тестовым пользователем (у которого доступ к
    # задаче как раз ЕСТЬ) — нужны только отображаемые имена, которые
    # можно найти через search() в дропдауне, как и любое другое не
    # закреплённое имя. Список через запятую (минимум 4 — второй шаг
    # кейса одновременно выбирает 4 таких юзера), та же логика, что у
    # jira_test_group_names/jira_test_group_names_list выше.
    jira_users_without_issue_access_display_names: str | None = Field(
        default=None,
        description=(
            "Отображаемые имена РЕАЛЬНЫХ пользователей тестового "
            "инстанса БЕЗ доступа к тестовой задаче, через запятую, "
            "минимум 4 (см. REMCL-2736) — например: "
            "JIRA_USERS_WITHOUT_ISSUE_ACCESS_DISPLAY_NAMES=User1,User2,"
            "User3,User4"
        ),
    )

    # --- Админ (для Permissions/Queue), опционально ---
    jira_admin_email: str | None = None
    jira_admin_password: SecretStr | None = None

    # --- Плагин Reminder ---
    reminder_app_path: str | None = Field(
        default=None,
        description="Путь приложения в Jira для My reminders: {jira_host}/jira/apps/{reminder_app_path}",
    )

    # --- Браузер / запуск ---
    browser: Literal["chromium", "firefox", "webkit"] = "chromium"
    headless: bool = True
    default_timeout_ms: int = 10_000
    # Канал установленного в системе браузера (chrome / msedge / chrome-beta / ...),
    # чтобы Playwright водил уже стоящий в ОС Google Chrome / Edge вместо
    # скачивания своего бандлованного Chromium. Нужно, когда playwright install
    # отказывается ставить бандлованный браузер из-за старой версии ОС
    # (см. README -> "Старая macOS / playwright install падает").
    browser_channel: str | None = None

    # --- Почта (опционально, см. README) — используется для ДВУХ разных
    # целей одним и тем же ящиком обычного тестового пользователя:
    #   1) получение email-кода подтверждения при логине (scripts/
    #      generate_storage_state.py, см. EMAIL_OTP_CODE);
    #   2) проверка РЕАЛЬНОЙ отправки письма самим плагином Reminder через
    #      utils/mail_client.py (MailClient) — REMCL-1114/1115/1116 и т.п.
    #      Подключение ТОЛЬКО на чтение (mark_seen=False) — тест не должен
    #      портить реальный почтовый ящик.
    #
    # ВАЖНО (2026-11-19, по живому прогону): MAIL_IMAP_LOGIN должен
    # указывать РОВНО на ящик того пользователя, которому ПЛАГИН
    # фактически отправит письмо в конкретном тесте — обычно это тот же
    # ящик, что и JIRA_USER_EMAIL, но НЕ ВСЕГДА (например если тест явно
    # выбирает получателем кого-то другого). Если MAIL_IMAP_LOGIN указывает
    # не на тот ящик — wait_for_email() честно отработает весь таймаут и
    # упадёт, хотя письмо реально придёт, просто не в проверяемый ящик
    # (диагностика такого случая — см. MailClient.debug_snapshot()/
    # list_folders() и scripts/debug_mail_subjects.py).
    mail_imap_host: str | None = None
    mail_imap_port: int = 993
    mail_imap_login: str | None = None
    mail_imap_password: SecretStr | None = None
    # Таймаут/интервал поллинга почты в MailClient.wait_for_email (секунды).
    # Дефолт 90/5 подобран с запасом поверх наблюдаемого на тестовом
    # инстансе времени доставки (обычно до ~1 минуты) — см. README. Если на
    # практике письма идут дольше, увеличьте MAIL_WAIT_TIMEOUT_S в .env.
    mail_wait_timeout_s: int = 90
    mail_poll_interval_s: int = 5
    # ДОБАВЛЕНО (2026-11-19, по живому прогону — "imaplib.IMAP4.abort:
    # command: LOGOUT => socket error: EOF" и зависания теста на этом шаге
    # без этого таймаута): таймаут (сек) на КАЖДУЮ отдельную сокет-операцию
    # IMAP-соединения (connect/login/fetch/logout), передаётся в
    # imap_tools.MailBox(..., timeout=...) -> imaplib. По умолчанию у
    # imaplib таймаут не задан (блокирует НАВСЕГДА) — если почтовый
    # провайдер (mail.ru/inbox.ru) решит придержать ответ или молча
    # оборвать соединение (например из-за частых login/logout подряд при
    # поллинге — см. MAIL_POLL_INTERVAL_S), без этого таймаута тест
    # зависает и требует ручной остановки, а не падает по понятному
    # исключению. С таймаутом — та же ситуация превращается в socket.
    # timeout, пойманный в MailClient._search() (см. utils/mail_client.py)
    # и обработанный как "эта попытка поллинга не удалась, попробовать
    # следующую", а не в бесконечное зависание или падение всего теста.
    mail_imap_timeout_s: int = 20

    def has_group_containing_creator(self) -> bool:
        """
        True, если в .env задана JIRA_TEST_GROUP_CONTAINING_CREATOR.

        ИСПРАВЛЕНО (2026-11-19): REMCL-1114 больше НЕ использует этот
        метод — см. has_mail_test_recipient_and_group() ниже. Оставлен
        для другого теста, которому важен именно creator.
        """
        return bool(self.jira_test_group_containing_creator)

    def has_mail_test_recipient_and_group(self) -> bool:
        """
        ДОБАВЛЕНО (2026-11-19): True, если в .env заданы ОБЕ переменные —
        MAIL_TEST_RECIPIENT_DISPLAY_NAME и JIRA_TEST_GROUP_CONTAINING_
        MAIL_RECIPIENT. Используется test_single_reminder_when_recipient_
        selected_via_multiple_paths (REMCL-1114) для honest skip, пока обе
        не заданы, вместо того чтобы угадывать получателя/группу и
        рисковать отправить реальное письмо посторонним людям (см.
        описание полей выше и ИСПРАВЛЕНО 2026-11-19 про MAIL_IMAP_LOGIN).
        """
        return bool(
            self.mail_test_recipient_display_name
            and self.jira_test_group_containing_mail_recipient
        )

    def has_mail_imap_credentials(self) -> bool:
        """
        True, если в .env заданы все данные для подключения к ящику по
        IMAP. Используется фикстурой mail_client в fixtures/conftest.py для
        honest skip тестов с меткой @pytest.mark.email, пока эти переменные
        не заданы — аналогично has_user_without_group_reminder_permission_
        credentials выше.
        """
        return bool(
            self.mail_imap_host and self.mail_imap_login and self.mail_imap_password
        )

    @property
    def jira_test_group_names_list(self) -> list[str]:
        """
        Разбирает jira_test_group_names по запятой (обрезая пробелы вокруг
        каждого имени, пропуская пустые элементы — на случай висячей
        запятой в конце строки .env). Пустой список, если переменная не
        задана — вызывающий код (см. test_reminder_created_successfully_
        with_user_or_group_recipient, кейс multi-group) сам решает,
        skip'ить тест или падать, если нужного количества групп не хватило.
        """
        if not self.jira_test_group_names:
            return []
        return [
            name.strip()
            for name in self.jira_test_group_names.split(",")
            if name.strip()
        ]

    @property
    def jira_users_without_issue_access_display_names_list(self) -> list[str]:
        """
        Разбирает jira_users_without_issue_access_display_names по запятой
        (та же логика, что и у jira_test_group_names_list выше — обрезка
        пробелов вокруг каждого имени, пропуск пустых элементов). Пустой
        список, если переменная не задана — test_reminder_not_created_for_
        user_without_issue_access сам решает, skip'ить тест или падать,
        если нужного количества имён (минимум 4) не хватило.
        """
        if not self.jira_users_without_issue_access_display_names:
            return []
        return [
            name.strip()
            for name in self.jira_users_without_issue_access_display_names.split(",")
            if name.strip()
        ]

    @property
    def jira_test_groups_containing_mail_recipient_list(self) -> list[str]:
        """
        ДОБАВЛЕНО (2026-11-19): разбирает jira_test_groups_containing_
        mail_recipient по запятой (та же логика, что и у jira_test_
        group_names_list выше). Пустой список, если переменная не
        задана — test_group_recipient_reminder_delivered_to_known_member
        (REMCL-1118) сам решает, skip'ить параметризованный кейс группы
        или нет, если нужного индекса не хватило (см. docstring теста и
        _resolve_mail_recipient_group_spec в tests/ui/test_reminder_
        recipients.py).
        """
        if not self.jira_test_groups_containing_mail_recipient:
            return []
        return [
            name.strip()
            for name in self.jira_test_groups_containing_mail_recipient.split(",")
            if name.strip()
        ]

    @property
    def storage_state_path(self) -> Path:
        """Файл сохранённой сессии обычного пользователя."""
        return AUTH_DIR / "user_state.json"

    @property
    def admin_storage_state_path(self) -> Path:
        """Файл сохранённой сессии администратора."""
        return AUTH_DIR / "admin_state.json"

    @property
    def without_group_reminder_permission_storage_state_path(self) -> Path:
        """
        Файл сохранённой сессии пользователя БЕЗ права 'Ability to create
        reminders for groups or roles' (см. REMCL-1076/1079/1065). Отдельный
        от storage_state_path файл — у этого пользователя своя, независимая
        сессия (другой аккаунт), её нельзя переиспользовать/смешивать с
        сессией обычного тестового пользователя.
        """
        return AUTH_DIR / "user_without_group_reminder_permission_state.json"

    def has_user_without_group_reminder_permission_credentials(self) -> bool:
        """
        True, если в .env заданы и email, и пароль этого пользователя —
        т.е. достаточно данных, чтобы реально залогиниться под ним (одного
        отображаемого имени для этого недостаточно). Используется фикстурой
        user_without_group_reminder_permission_page в fixtures/conftest.py
        для honest skip, пока эти переменные не заданы.
        """
        return bool(
            self.jira_user_without_group_reminder_permission_email
            and self.jira_user_without_group_reminder_permission_password
        )

    def issue_url(self, issue_key: str) -> str:
        return f"{self.jira_host.rstrip('/')}/browse/{issue_key}"

    @property
    def my_reminders_url(self) -> str:
        app_path = self.reminder_app_path or ""
        return f"{self.jira_host.rstrip('/')}/jira/apps/{app_path}"


@lru_cache
def get_settings() -> Settings:
    """Settings — синглтон на процесс, чтобы .env читался один раз."""
    return Settings()  # type: ignore[call-arg]
