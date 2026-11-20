"""
Тесты на поле Recipients в модалке "New reminder" (форма создания
ремайндера), открываемой из ReminderPanel на странице задачи.

Источник test-кейсов: RTM-экспорт "rtm-issues-export-recievers.zip"
(66 кейсов, компонент "5.0. Creation form", все с префиксом "[Recipients]").
У 63 из 66 кейсов нет расписанных Action/Input/Expected result — весь смысл
кейса зашит в Summary (однострочный заголовок), поэтому шаги в allure.step
ниже сформулированы по смыслу Summary, а не скопированы из структурированных
полей RTM.

Дополнительно (2026-11-15): REMCL-2852 добавлен отдельным, более поздним
RTM-экспортом ("rtm-issues-export_15.zip", 1 кейс, QA Label "Valid") — это
переоформленная версия REMCL-1063 ("[Recipients] В поле по дефолту введен
юзер, который создает ремайндер", у REMCL-1063 QA Label "F", поэтому он сам
по правилу выше НЕ входит в батч, а REMCL-2852 — входит).

Реализовано (по договорённости с автором кейсов) ТОЛЬКО подмножество с
QA Labels "UI" и "Valid" ("Ui" для REMCL-1015), и только то, что удалось
подтвердить живым прогоном (см. docstring pages/components/reminder_modal.py
для полного разбора найденных локаторов/текстов/поведения и рисков).

НЕ реализовано (оформлено как pytest.mark.skip с honest-причиной в самом
низу файла) — требует либо данных/окружения, которых нет на тестовом
инстансе, либо второго пользователя без права "Ability to create reminders
for groups or roles":
    REMCL-1079                     — Roles для пользователя без прав (см.
                                      ОБНОВЛЕНО 2026-11-17 ниже: 1076/1065
                                      реализованы, 1079 остаётся пропуском)
    REMCL-1078, REMCL-1091,
    REMCL-1095, REMCL-1096         — на тестовом проекте CPR1 секция "Roles"
                                      ни разу не появилась в дропдауне (см.
                                      технический риск в reminder_modal.py, п.8)
    REMCL-1082, REMCL-1083         — живой прогон НЕ подтвердил строгую
                                      алфавитную сортировку (см. технический
                                      риск в reminder_modal.py, п.7) — нужна
                                      сверка с продуктовой командой, прежде
                                      чем писать ассерт
    REMCL-1084                     — нужно >20 пользователей/групп на
                                      тестовом инстансе, таких данных нет
    REMCL-1081 (JSM-часть)         — на тестовом инстансе нет JSM-проекта,
                                      Jira-часть (Watchers первыми) реализована

Функциональные кейсы (QA Labels "F": создание рема с конкретным
recipient'ом, получение письма, дедупликация получателей между
user/group/role и т.п.) сознательно не входят в этот батч — по
договорённости делаются отдельно.

Дополнительно (2026-11-16): по отдельному запросу разобраны все 34 кейса с
QA Label "F" (полный список — см. таблицу покрытия "Recipients Test
Coverage"). Из них:
  - REMCL-1063, REMCL-1067, REMCL-1109, REMCL-1111 — по смыслу ДУБЛИРУЮТ уже
    реализованные UI/Valid-кейсы (REMCL-2852, REMCL-1080, REMCL-1069 x2) —
    отдельных тестов не писали, тег добавлен к уже существующему тесту, см.
    докстринг соответствующего теста.
  - REMCL-1064, REMCL-1066, REMCL-1107, REMCL-1108, REMCL-1110, REMCL-1112 —
    реализованы как новые тесты ниже (чисто UI-проверки, не требуют ни
    второго пользователя, ни реального сохранения ремайндера).
  - Остальные 24 (REMCL-1065, 1098, 1100-1104, 1106, 1113-1119, 1248-1253,
    2734-2736) — honest skip в самом низу файла. Общая причина для
    большинства из них на момент написания этого абзаца: у ReminderModal не
    было метода, который реально САБМИТИТ форму, и не было способа
    подтвердить, что ремайндер реально создался и сохранился. Часть вдобавок
    требует проверки письма (IMAP/MailClient — см. Project Instructions, в
    коде пока не реализован) и/или второго пользователя с иными правами/
    доступом. Конкретная причина у каждого — в соответствующем skip ниже.

    ОБНОВЛЕНО (2026-11-16, по запросу "доделать skip-тесты, раз кнопка
    Create теперь работает" — см. ReminderModal.submit()/fill_message() и
    ReminderPanel.has_reminder_with_text(), добавленные для REMCL-1038 в
    tests/ui/test_reminder_create_cancel.py): инфраструктурный пробел
    "нет сабмита формы" закрыт — это разблокировало РОВНО те кейсы из
    батча, чьим ЕДИНСТВЕННЫМ блокером был именно он:
      - REMCL-1100/REMCL-1101 (recipient = юзер/группа) — реализованы, см.
        test_reminder_created_successfully_with_user_or_group_recipient
        ниже. СУЖЕНО относительно исходной формулировки: проверяется
        только успешность создания, а не то, что сам recipient виден в
        сохранённой записи (разметка строки ремайндера в ReminderPanel
        по-прежнему не подтверждена, см. test_create_button_saves_
        reminder) — REMCL-1102 (роль) и REMCL-1113/1117 (формулировка не
        разобрана отдельно) в это сужение не вошли, остаются skip.
      - REMCL-1098, REMCL-2736 — сабмит формы для них тоже больше не
        блокер, но у каждого остался СВОЙ отдельный блокер (контролируемое
        состояние assignee/watchers задачи; второй пользователь без
        доступа к задаче соответственно) — reason каждого skip обновлён,
        чтобы это отразить, но сами тесты остаются skip.
      - REMCL-2734/2735 — ОБНОВЛЕНО (2026-11-16, по присланному по прямой
        просьбе живому скриншоту): блокер "неподтверждённый локатор toast-
        уведомления" снят — см. test_warning_flag_shown_after_creating_
        reminder и IssuePage.has_recipients_visibility_warning_flag в
        pages/issue_page.py. Реализован (не skip); риск по REMCL-2735
        (текст для recipient-группы подтверждён по аналогии, а не
        отдельным скриншотом) задокументирован в докстринге самого теста.
    Остальные (1065, 1103/1104, 1106, 1114-1119, 1248-1253) не входят в
    это обновление — их блокеры (второй пользователь, IMAP/mail_client,
    секция Roles, отдельный Page Object для флоу без привязки к задаче,
    тестовые данные с конкретными именами) submit-инфраструктурой не
    закрываются.

    ОБНОВЛЕНО (2026-11-17, по запросу — пользователь без права на групповые
    ремайндеры заведён в .env через JIRA_USER_WITHOUT_GROUP_REMINDER_
    PERMISSION_DISPLAY_NAME): REMCL-1076/1065 реализованы как
    test_groups_hidden_and_search_users_only_for_user_without_rights —
    используют новую, полностью независимую от основной сессию (см.
    fixtures/conftest.py: user_without_group_reminder_permission_page /
    issue_page_as_user_without_group_reminder_permission /
    scripts/generate_storage_state.py --as=without_group_reminder_
    permission). ВАЖНО: для реального прогона этого теста (а не honest
    skip) в .env должны быть заданы JIRA_USER_WITHOUT_GROUP_REMINDER_
    PERMISSION_EMAIL и _PASSWORD — одного отображаемого имени
    недостаточно, т.к. нужен живой логин под этим аккаунтом. REMCL-1079
    (Roles) в это обновление НЕ вошёл — см. docstring самого теста,
    почему это сознательный пропуск, а не упущение.

    ОБНОВЛЕНО (2026-11-18, по согласованному с пользователем дизайну
    проверки писем — см. историю сессии): REMCL-1114 и REMCL-1118 больше
    не honest skip:
      - REMCL-1114 реализован как test_single_reminder_when_recipient_
        selected_via_multiple_paths — РЕАЛЬНО создаёт ремайндер и
        дожидается письма по IMAP через новые utils/mail_client.py
        (MailClient) и фикстуру mail_client (fixtures/conftest.py).
        Требует JIRA_TEST_GROUP_CONTAINING_CREATOR в .env (новая
        переменная, см. config/settings.py) — honest skip без неё.
        REMCL-1115/1116 (тот же дедуп через РОЛЬ) остаются skip — секция
        Roles по-прежнему не подтверждена.
      - REMCL-1118 реализован как test_all_group_or_role_members_receive_
        reminder — но НЕ как полноценная проверка доставки (это
        принципиально невозможно без доступа к чужим почтовым ящикам):
        тест реально создаёт ремайндер с recipients-группой и
        ДИНАМИЧЕСКИ скипует себя В КОНЦЕ (после создания, не декоратором)
        с описанием, что нужно проверить вручную — итоговый статус
        SKIPPED ("нейтральный", по формулировке пользователя), не
        PASSED/FAILED. REMCL-1119 (вариант с РОЛЬЮ) остаётся отдельным
        необработанным случаем — секция Roles не подтверждена.
      Новые методы ReminderModal для поля Date & time (set_specific_
      datetime и т.п., см. п.13 докстринга reminder_modal.py) и утилита
      utils/time_helpers.round_up_to_next_five_minutes — тоже добавлены
      этим обновлением, локаторы внутри них угаданы и явно помечены как
      требующие подтверждения первым реальным прогоном.

    ОБНОВЛЕНО (2026-11-19, по откорректированному test-кейсу REMCL-2736
    из rtm-issues-export_20.zip и предоставленным пользователем 4 именам
    пользователей без доступа к тестовой задаче): REMCL-2736 больше не
    honest skip — реализован как test_reminder_not_created_for_user_
    without_issue_access. Выяснилось, что отдельная storage_state-сессия
    здесь НЕ нужна (в отличие от того, что предполагал прежний reason
    skip) — ограниченный пользователь просто выбирается recipient'ом в
    поле Recipients обычным тестовым пользователем. Требует
    JIRA_USERS_WITHOUT_ISSUE_ACCESS_DISPLAY_NAMES в .env (новая
    переменная, минимум 4 имени через запятую, см. config/settings.py) —
    honest skip без неё. Новые ACCESS_ERROR_SUFFIX/access_error_text()/
    has_access_error() в reminder_modal.py (п.14 докстринга модуля) —
    точный текст/порядок перечисления имён в сообщении об ошибке не
    подтверждены вживую.

Дополнительно (2026-11-16, фикс гонки после живых прогонов у пользователя):
test_user_found_by_partial_name / test_group_found_by_partial_name /
test_search_is_case_insensitive падали на реальном инстансе с "Loading..."
всё ещё видимым в дропдауне в момент ассерта — несмотря на вызов
wait_for_search_to_settle() перед ним. Причина в ДВА слоя:
  1. Сам wait_for_search_to_settle() раньше делал голый `wait_for(state=
     "hidden")` без предварительного ожидания "visible" — чинилось
     отдельно, см. докстринг этого метода в reminder_modal.py.
  2. Даже после фикса (1) ПОЛНОСТЬЮ не защищает от случая, когда "Loading"
     показывается НЕСКОЛЬКО раз подряд (например, юзеры и группы
     подгружаются/фильтруются отдельными циклами) — между двумя такими
     циклами есть короткое "hidden"-окно, в которое `wait_for(state=
     "hidden")` может попасть и вернуться раньше времени. Поэтому финальный
     ассерт на `.option(name).is_visible()` (однократный снимок состояния,
     БЕЗ поллинга) всё ещё мог поймать промежуточное состояние.
  Исправлено заменой `.option(name).is_visible()` на `expect(.option(name))
  .to_be_visible(timeout=10_000)` в этих трёх тестах — `expect()` активно
  поллит сам локатор опции до её появления (или до таймаута), а не
  полагается на точную синхронизацию с индикатором "Loading...", поэтому
  устойчив к любому числу промежуточных циклов. Воспроизведено и
  подтверждено на синтетическом моке с намеренно смоделированным двойным
  циклом Loading (группы подгружаются вторым, более медленным циклом) —
  старый паттерн `.is_visible()` ловил гонку, `expect()` проходил стабильно
  в повторных прогонах.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import allure
import pytest
from faker import Faker
from playwright.sync_api import expect

from config.settings import Settings
from pages.components.reminder_modal import PLACEHOLDER_TEXT, ReminderModal
from pages.issue_page import RECIPIENTS_VISIBILITY_WARNING_TEXT, IssuePage
from utils.mail_client import MailClient
from utils.time_helpers import round_up_to_next_five_minutes

_faker = Faker()

# Поле "Date & time" в модалке показывает время в Europe/Moscow (ссылка
# "Moscow / GMT+3" рядом с лейблом, см. п.13 докстринга reminder_modal.py)
# — тот же часовой пояс, что уже используется в Playwright context fixtures
# (locale="ru-RU", timezone_id="Europe/Moscow"). Целевое время для REMCL-
# 1114/1118 считается в этом поясе, чтобы день/час/минута, переданные в
# ReminderModal.set_specific_datetime(), совпадали с тем, что реально
# показывает попап календаря.
_MOSCOW_TZ = ZoneInfo("Europe/Moscow")

# ТЕХНИЧЕСКИЙ РИСК (не подтверждено вживую): сколько времени плагин
# Reminder может ждать ПОСЛЕ наступления запланированного момента, прежде
# чем реально отправить письмо (например, если проверка просроченных
# ремайндеров на сервере идёт по собственному расписанию/крону, а не
# мгновенно) — отдельно от уже известной задержки самой почтовой доставки
# (settings.mail_wait_timeout_s, см. README). Этот буфер — ЗАПАС "на всякий
# случай", подобранный произвольно (не измерен), пока не будет первого
# реального прогона: если ремайндер сработает заметно медленнее, здесь
# нужно увеличить константу (а если есть способ узнать точный интервал
# проверки на сервере — заменить константу на него).
_PLUGIN_SCHEDULE_POLL_BUFFER_S = 5 * 60

# Issue key теперь задаётся через CLI-флаг --issue-key (см. pytest_addoption
# в fixtures/conftest.py), а не хардкодится здесь. Дефолт флага — "CPR1-10":
# задача с подтверждённым наличием секции Reminder и правом текущего
# пользователя на выбор групп/ролей (см. tests/ui/test_login.py). Чтобы
# прогнать этот файл на другой задаче/инстансе: `pytest --issue-key=PKP-5
# --app-env=stg tests/ui/test_reminder_recipients.py`.


@pytest.fixture
def recipients_modal(issue_page: IssuePage, issue_key: str) -> Iterator[ReminderModal]:
    """Открывает задачу и модалку "New reminder", отдаёт готовый ReminderModal."""
    issue_page.open(issue_key)
    assert (
        issue_page.has_reminder_section()
    ), "Секция Reminder не найдена на странице задачи"
    issue_page.reminder_panel.expand()
    modal = issue_page.reminder_panel.open_create_modal()
    yield modal
    try:
        modal.close()
    except Exception:
        # Тест мог уже закрыть/сломать модалку сам (например, негативный
        # сценарий с disabled Create) — не мешаем отчёту падением в teardown.
        pass


def _select_two_recipients(modal: ReminderModal) -> None:
    """Хелпер: выбирает Assignee и Reporter — стабильные пункты, есть всегда."""
    modal.open_dropdown()
    modal.select("Assignee")
    modal.select("Reporter")


@pytest.fixture
def recipients_modal_as_user_without_group_reminder_permission(
    issue_page_as_user_without_group_reminder_permission: IssuePage,
    issue_key: str,
) -> Iterator[ReminderModal]:
    """
    То же самое, что recipients_modal выше, но открывает форму ПОД
    ВТОРЫМ тестовым пользователем — без права 'Ability to create reminders
    for groups or roles' (см. REMCL-1076/1079/1065 и fixtures/conftest.py:
    issue_page_as_user_without_group_reminder_permission). Honestly
    skip'ается на уровне нижележащей фикстуры user_without_group_reminder_
    permission_page, если JIRA_USER_WITHOUT_GROUP_REMINDER_PERMISSION_EMAIL/
    _PASSWORD не заданы в .env — отдельно тут ничего не проверяем.
    """
    issue_page_as_user_without_group_reminder_permission.open(issue_key)
    assert (
        issue_page_as_user_without_group_reminder_permission.has_reminder_section()
    ), "Секция Reminder не найдена на странице задачи (под вторым пользователем)"
    issue_page_as_user_without_group_reminder_permission.reminder_panel.expand()
    modal = (
        issue_page_as_user_without_group_reminder_permission.reminder_panel.open_create_modal()
    )
    yield modal
    try:
        modal.close()
    except Exception:
        pass


# --- REMCL-1015 / REMCL-1017: лейбл, required-маркер, тултип ---


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1015")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_recipients_field_present_with_tooltip_icon(
    recipients_modal: ReminderModal,
) -> None:
    """REMCL-1015: в форме создания рема есть поле Recipients с иконкой-тултипом."""
    with allure.step("Открыть форму создания ремайндера"):
        pass  # форма уже открыта фикстурой recipients_modal

    with allure.step("Проверить, что поле Recipients отображается"):
        assert (
            recipients_modal.is_recipients_label_visible()
        ), "Лейбл поля Recipients не найден"

    with allure.step("Проверить, что справа от лейбла есть иконка-тултип"):
        assert (
            recipients_modal.is_tooltip_icon_visible()
        ), "Иконка-тултип рядом с Recipients не найдена"


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1017")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_recipients_tooltip_shows_expected_text_on_hover(
    recipients_modal: ReminderModal,
) -> None:
    """REMCL-1017: при наведении на иконку-тултип появляется ожидаемый текст подсказки."""
    with allure.step("Навести курсор на иконку-тултип рядом с полем Recipients"):
        recipients_modal.hover_tooltip_icon()

    with allure.step("Проверить текст тултипа"):
        text = recipients_modal.tooltip_text()
        assert text is not None, "Тултип не появился по наведению"
        assert (
            "necessary permissions" in text and "groups or roles" in text
        ), f"Неожиданный текст тултипа: {text!r}"


# --- REMCL-1063: дефолтное значение поля при открытии формы ---


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-2852")
@allure.tag("REMCL-1063")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_default_recipient_is_reminder_creator(
    recipients_modal: ReminderModal, settings: Settings
) -> None:
    """
    REMCL-2852: при открытии формы создания ремайндера поле Recipients уже
    заполнено одним тегом — создателем ремайндера (текущим пользователем).

    Это тот же смысловой кейс, что и более старый REMCL-1063 ("[Recipients]
    В поле по дефолту введен юзер, который создает ремайндер", QA Label
    "F") — поэтому REMCL-1063 помечен тут же тегом, а не отдельным тестом:
    проверка буквально идентична, дублировать её незачем (см. также
    докстринг модуля о батче 2026-11-16 по QA Label "F").

    Имя тестового пользователя зависит от окружения, поэтому сравниваем с
    settings.jira_user_display_name (JIRA_USER_DISPLAY_NAME в .env), а не с
    хардкоженной строкой — см. config/settings.py.
    """
    if settings.jira_user_display_name is None:
        pytest.skip(
            "JIRA_USER_DISPLAY_NAME не задан в .env — без него нельзя "
            "проверить, что дефолтный тег в Recipients — это именно текущий "
            "пользователь, а не просто какой-то один тег (см. .env и "
            "config/settings.py)."
        )

    with allure.step("Открыть форму создания ремайндера"):
        pass  # форма уже открыта фикстурой recipients_modal, другие recipients не добавлялись

    with allure.step(
        "Проверить, что в поле Recipients по умолчанию ровно один тег — "
        "текущий пользователь (создатель ремайндера)"
    ):
        tags = recipients_modal.selected_tags()
        assert tags == [settings.jira_user_display_name], (
            f"Ожидался ровно один дефолтный тег с именем текущего "
            f"пользователя {settings.jira_user_display_name!r}, "
            f"получено: {tags!r}"
        )


# --- REMCL-1069 / 1070 / 1071: теги, placeholder, кнопка очистки ---


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1069")
@allure.tag("REMCL-1109")
@allure.tag("REMCL-1111")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_selected_recipients_shown_as_tags(recipients_modal: ReminderModal) -> None:
    """
    REMCL-1069: выбранные recipients отображаются в виде тегов/chips внутри поля.

    Этим же тестом покрыты (QA Label "F", дубликаты по смыслу — см.
    докстринг модуля о батче 2026-11-16):
      - REMCL-1109 "Значение отображается внутри поля Recipients после
        выбора recipient" — то же самое утверждение, что и REMCL-1069.
      - REMCL-1111 "Все выбранные recipients сохраняются после выбора
        нескольких recipients" — подтверждается тем, что ОБА тега
        (Assignee и Reporter) видны одновременно после выбора обоих.
    """
    with allure.step("Выбрать Assignee и Reporter в поле Recipients"):
        _select_two_recipients(recipients_modal)

    with allure.step("Проверить, что оба recipient'а отображаются как теги"):
        tags = recipients_modal.selected_tags()
        assert "Assignee" in tags, f"Тег 'Assignee' не найден среди {tags!r}"
        assert "Reporter" in tags, f"Тег 'Reporter' не найден среди {tags!r}"


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1070")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_placeholder_disappears_after_selecting_recipient(
    recipients_modal: ReminderModal,
) -> None:
    """REMCL-1070: placeholder поля Recipients исчезает после выбора recipient."""
    with allure.step(
        "Убедиться, что изначально показан placeholder (recipients пусты)"
    ):
        recipients_modal.clear_all()
        assert (
            recipients_modal.is_placeholder_visible()
        ), "Placeholder не отображается на пустом поле"

    with allure.step("Выбрать recipient Assignee"):
        recipients_modal.open_dropdown()
        recipients_modal.select("Assignee")

    with allure.step("Проверить, что placeholder исчез"):
        assert not recipients_modal.is_placeholder_visible(
            timeout_ms=1_500
        ), "Placeholder всё ещё виден после выбора recipient"


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1071")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_clear_all_button_appears_after_selecting_recipient(
    recipients_modal: ReminderModal,
) -> None:
    """REMCL-1071: кнопка очистки поля появляется после выбора recipient."""
    with allure.step("Выбрать recipient Assignee"):
        recipients_modal.open_dropdown()
        recipients_modal.select("Assignee")

    with allure.step("Проверить, что кнопка очистки поля отображается"):
        assert (
            recipients_modal.is_clear_all_visible()
        ), "Кнопка очистки поля Recipients не появилась"


# --- REMCL-1072 / 1087 / 1073+1088: error state ---


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1072")
@pytest.mark.ui
@pytest.mark.validation
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_empty_recipients_shows_required_error_and_disables_create(
    recipients_modal: ReminderModal,
) -> None:
    """REMCL-1072: очистка поля Recipients переводит его в error state, Create — disabled."""
    with allure.step("Очистить поле Recipients кнопкой очистки"):
        recipients_modal.clear_all()

    with allure.step(
        "Проверить сообщение 'At least one recipient should be selected' под полем"
    ):
        assert (
            recipients_modal.has_required_error()
        ), "Сообщение об обязательности поля не появилось"

    with allure.step("Проверить, что кнопка Create стала disabled"):
        assert (
            not recipients_modal.is_create_enabled()
        ), "Кнопка Create не стала disabled"


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1087")
@pytest.mark.validation
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_required_error_appears_after_removing_all_recipients_one_by_one(
    recipients_modal: ReminderModal,
) -> None:
    """
    REMCL-1087: сообщение об обязательности поля появляется после удаления
    дефолтного recipient'а (текущего пользователя, уже стоящего в поле при
    открытии формы — см. п.4 докстринга ReminderModal, REMCL-2852).

    Переделано (2026-11-16): раньше тест сначала добавлял Assignee/Reporter
    и затем удалял ВСЕ теги по одному, включая дефолтный — тут оставлен
    только минимальный сценарий без лишнего шага с добавлением recipient'ов,
    т.к. поле и так не пустое с одним дефолтным тегом.
    """
    with allure.step(
        "Форма создания ремайндера открыта (см. фикстуру recipients_modal)"
    ):
        default_tags = recipients_modal.selected_tags()
        assert (
            default_tags
        ), "Предусловие не выполнено: дефолтный recipient не найден в поле"

    with allure.step("Удалить дефолтного recipient'а из поля Recipients"):
        # Имя дефолтного recipient'а (текущего тестового пользователя)
        # зависит от окружения, поэтому берём его из selected_tags(), а не
        # хардкодим — см. REMCL-2852.
        recipients_modal.remove_tag(default_tags[0])

    with allure.step("Проверить сообщение 'At least one recipient should be selected'"):
        assert (
            recipients_modal.has_required_error()
        ), "Сообщение об обязательности поля не появилось после удаления дефолтного recipient'а"


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1088")
@allure.tag("REMCL-1073")
@pytest.mark.ui
@pytest.mark.validation
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_required_error_disappears_after_selecting_recipient(
    recipients_modal: ReminderModal,
) -> None:
    """
    REMCL-1088 / REMCL-1073 (дублирующие друг друга по смыслу кейсы RTM):
    сообщение об обязательности поля исчезает после выбора recipient.
    """
    with allure.step("Очистить поле Recipients и убедиться, что показана ошибка"):
        recipients_modal.clear_all()
        assert (
            recipients_modal.has_required_error()
        ), "Предусловие не выполнено: ошибка не появилась"

    with allure.step("Выбрать recipient Assignee"):
        recipients_modal.open_dropdown()
        recipients_modal.select("Assignee")

    with allure.step("Проверить, что сообщение об ошибке исчезло"):
        assert not recipients_modal.has_required_error(
            timeout_ms=1_500
        ), "Сообщение об ошибке всё ещё видно после выбора recipient"

    with allure.step("Проверить, что кнопка Create снова активна"):
        assert recipients_modal.is_create_enabled(), "Кнопка Create не стала активной"


# --- REMCL-1074 / 1075 / 1077 / 1080 / 1081: структура дропдауна ---


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1074")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_dropdown_overlays_other_form_fields(recipients_modal: ReminderModal) -> None:
    """REMCL-1074: выпадающий список поля Recipients отображается поверх остальных полей формы."""
    with allure.step("Открыть дропдаун поля Recipients"):
        recipients_modal.open_dropdown()

    with allure.step(
        "Проверить, что список опций виден (не обрезан нижележащими полями)"
    ):
        assert (
            recipients_modal.is_users_section_visible()
        ), "Секция Users дропдауна не видна — похоже, список перекрыт другими полями формы"


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1075")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_users_section_visible_in_dropdown(recipients_modal: ReminderModal) -> None:
    """REMCL-1075: в дропдауне поля Recipients отображается секция Users."""
    with allure.step("Открыть дропдаун поля Recipients"):
        recipients_modal.open_dropdown()

    with allure.step("Проверить наличие заголовка секции 'Users'"):
        assert (
            recipients_modal.is_users_section_visible()
        ), "Секция 'Users' не найдена в дропдауне"


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1077")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_groups_section_visible_for_user_with_rights(
    recipients_modal: ReminderModal,
) -> None:
    """
    REMCL-1077: секция Groups отображается в дропдауне для пользователя с
    правом "Ability to create reminders for groups or roles".

    Негативная часть (секция Groups СКРЫТА для пользователя БЕЗ этого
    права, REMCL-1076/1079) требует отдельного storage_state без этого
    права и сюда не входит — см. docstring модуля.
    """
    with allure.step("Открыть дропдаун поля Recipients"):
        recipients_modal.open_dropdown()

    with allure.step("Проверить наличие заголовка секции 'Groups'"):
        assert recipients_modal.is_groups_section_visible(), (
            "Секция 'Groups' не найдена — ожидалась, т.к. у текущего тестового "
            "пользователя есть право 'Ability to create reminders for groups or roles'"
        )


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1080")
@allure.tag("REMCL-1067")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_assignee_and_reporter_listed_first_in_users_section(
    recipients_modal: ReminderModal,
) -> None:
    """
    REMCL-1080: значения Assignee и Reporter отображаются первыми в секции Users.

    REMCL-1067 (QA Label "F") формулирует то же самое шире: "...первые в
    списке Assignee, Reporter, далее пользователи по возрастанию A-Z,
    0-9" — тег добавлен сюда, но проверяется ТОЛЬКО закреплённая первой
    пара Assignee/Reporter (то, что реально подтверждено). Хвост про
    строгую алфавитную сортировку остальных пользователей — та же
    неподтверждённая претензия, что у REMCL-1082/1083 (см. honest skip
    test_users_and_groups_sorted_alphabetically ниже) — здесь он
    сознательно НЕ assert'ится.
    """
    with allure.step("Открыть дропдаун поля Recipients"):
        recipients_modal.open_dropdown()

    with allure.step("Проверить, что пункты 'Assignee' и 'Reporter' видны в списке"):
        assert recipients_modal.option(
            "Assignee"
        ).is_visible(), "Пункт 'Assignee' не найден"
        assert recipients_modal.option(
            "Reporter"
        ).is_visible(), "Пункт 'Reporter' не найден"


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1081")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_watchers_listed_first_in_groups_section_for_jira_project(
    recipients_modal: ReminderModal,
) -> None:
    """
    REMCL-1081 (Jira-часть): значение Watchers отображается первым в секции
    Groups для обычного Jira-проекта. Вариант с "Request participants" для
    JSM-проекта вживую не проверен — на тестовом инстансе нет JSM-проекта
    (см. docstring модуля).
    """
    with allure.step("Открыть дропдаун поля Recipients"):
        recipients_modal.open_dropdown()

    with allure.step("Проверить, что пункт 'Watchers' виден в секции Groups"):
        assert recipients_modal.option(
            "Watchers"
        ).is_visible(), "Пункт 'Watchers' не найден"


# --- REMCL-1085 / 1086: клавиатурная навигация ---

# Сколько раз максимум нажимать Shift+Tab, добиваясь, чтобы фокус вышел из
# поля Recipients целиком (см. _exit_recipients_field_via_shift_tab ниже и
# её докстринг про ИСПРАВЛЕНИЕ 2026-11-16).
_MAX_SHIFT_TAB_PRESSES_TO_EXIT_RECIPIENTS = 5


def _exit_recipients_field_via_shift_tab(
    modal: ReminderModal, max_presses: int = _MAX_SHIFT_TAB_PRESSES_TO_EXIT_RECIPIENTS
) -> None:
    """
    Нажимает Shift+Tab, пока фокус не выйдет из поля Recipients целиком
    (is_field_focused() не станет False), но не больше max_presses раз.

    ИСПРАВЛЕНО (2026-11-16, по скриншоту живого прогона
    test_tab_moves_focus_into_recipients_field): прежняя версия делала
    РОВНО ОДИН Shift+Tab и сразу проверяла, что фокус уже снаружи поля —
    это предположение верно только если единственный фокусируемый элемент
    внутри поля — сам search-input. На живом прогоне в поле Recipients
    уже был ОДИН дефолтный recipient ("szczególnie na etapie
    początkującym" — см. скриншот), а is_field_focused() считает фокус
    "внутри поля", если он попал в том числе на КНОПКУ УДАЛЕНИЯ ЭТОГО
    ТЕГА (см. её собственный докстринг: "Tab последовательно заходит
    сначала на кнопки удаления тегов, затем на инпут") — то есть кнопка
    удаления тега идёт ПЕРЕД input в tab-порядке, и один Shift+Tab от
    input просто переставляет фокус на неё же, но фокус всё ещё формально
    "внутри поля" → предусловие падало ещё ДО шага с основным Tab.

    Подтверждено на моке (mock_site_v10_tab_focus, с заранее выбранным
    дефолтным тегом + отдельной tooltip-иконкой "?" рядом с лейблом,
    которая тоже, по разметке _field из ReminderModal.__init__, попадает
    внутрь той же "ограничивающей рамки" поля): реально требуется НЕСКОЛЬКО
    Shift+Tab подряд (количество зависит от того, сколько
    вспомогательных элементов — тегов, tooltip-иконки — стоит перед
    input), 3/3 прогона устойчиво выходили не более чем за
    _MAX_SHIFT_TAB_PRESSES_TO_EXIT_RECIPIENTS нажатий.

    Намеренно НЕ делается clear_all() перед этим — тест проверяет общее
    поведение Tab-навигации, а не состояние Recipients, и не должен
    менять уже выбранных recipients ради своей механики (кроме того,
    clear_all() сам кликает по кнопке и тем самым тоже переносит фокус,
    что только усложнило бы рассуждение о точном количестве нажатий —
    проверено отдельно на том же моке).
    """
    for _ in range(max_presses):
        modal.page.keyboard.press("Shift+Tab")
        if not modal.is_field_focused():
            return
    raise AssertionError(
        f"Предусловие не выполнено: фокус остался в поле Recipients даже "
        f"после {max_presses} Shift+Tab"
    )


@allure.severity(allure.severity_level.CRITICAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1086")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_tab_moves_focus_into_recipients_field(recipients_modal: ReminderModal) -> None:
    """
    REMCL-1086: фокус переходит на поле Recipients после нажатия Tab.

    ИСПРАВЛЕНО (2026-11-16, по скриншоту живого прогона — см. докстринг
    _exit_recipients_field_via_shift_tab выше): предусловие "фокус вне
    поля" теперь добивается ЦИКЛОМ Shift+Tab (ограниченным), а не ровно
    одним нажатием — старая версия ложно падала на предусловии, когда в
    поле уже был выбран дефолтный recipient.
    """
    with allure.step(
        "Установить фокус на поле Recipients и выйти из него назад через Shift+Tab"
    ):
        recipients_modal.open_dropdown()
        recipients_modal.page.keyboard.press("Escape")
        _exit_recipients_field_via_shift_tab(recipients_modal)

    with allure.step("Нажать Tab"):
        recipients_modal.page.keyboard.press("Tab")

    with allure.step("Проверить, что фокус вернулся на поле Recipients"):
        assert (
            recipients_modal.is_field_focused()
        ), "Фокус не перешёл на поле Recipients после Tab"


@allure.severity(allure.severity_level.CRITICAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1085")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_recipients_field_usable_with_keyboard_only(
    recipients_modal: ReminderModal,
) -> None:
    """
    REMCL-1085: поле Recipients доступно через keyboard-only navigation —
    перемещение по списку опций (ArrowDown) и сам выбор опции (Enter)
    можно выполнить без мыши.

    ПЕРЕРАБОТАНО ВТОРОЙ РАЗ (2026-11-16, по скриншоту живого прогона
    предыдущей версии — см. историю изменений файла ниже для первой
    переработки). Скриншот показал: после clear_all() (поле точно пустое,
    placeholder виден) -> открытие кликом -> 2x ArrowDown -> Enter, список
    остался открытым с НИ ОДНОЙ подсвеченной/активной строкой (ни один
    checkbox не отмечен, кнопка Create по-прежнему disabled) — то есть
    ArrowDown по ПУСТОМУ, НЕотфильтрованному списку визуально НЕ двигает
    фокус ни на один пункт вообще, вопреки тому, что было записано как
    "подтверждено" в п.6 докстринга ReminderModal ("ArrowDown на
    сфокусированном поле ... двигает фокус по опциям") — см. ИСПРАВЛЕНО в
    том докстринге, этот пункт впредь считается НЕподтверждённым для
    пустого списка. Это согласуется и с ПЕРВОЙ (ещё более ранней) версией
    теста: там тоже в итоге оказался отмечен только ИЗНАЧАЛЬНО уже
    выбранный дефолтный recipient — то есть тоже ничего нового клавиатурой
    выбрано не было, просто это не сразу было очевидно.

    Новый подход — не угадывать семантику ArrowDown по пустому списку в
    третий раз, а опереться на уже независимо подтверждённое работающее
    поведение (серверный поиск, см. test_user_found_by_partial_name и
    соседние тесты): сузить список до РОВНО ОДНОГО пункта через search()
    (это тоже "без мыши" — клавиатурный ввод, а не клик), и только потом
    использовать ArrowDown/Enter, когда навигировать нужно ровно на один
    шаг. Если даже это не сработает (поле останется пустым) — это будет
    означать, что Enter вообще не выбирает опции на этом виджете ни в
    каком состоянии, и тест стоит честно пометить skip с этой находкой,
    а не продолжать гадать дальше.

        1. Подготовка (клик мышью, НЕ часть проверяемого сценария): поле
           открывается кликом и ПОЛНОСТЬЮ очищается через clear_all() —
           убирает дефолтный recipient и что бы ещё ни было выбрано по
           умолчанию, чтобы не зависеть от исходного состояния поля.
        2. Поиск "Reporter" (search() + wait_for_search_to_settle(),
           keyboard-ввод, не мышь) сужает список до ровно одного пункта —
           проверяется через expect(...).to_be_visible() ПЕРЕД навигацией,
           чтобы не перепутать "поиск не нашёл ничего" с "ArrowDown/Enter
           не сработали". Дальше — ОДИН ArrowDown (переход на
           единственный оставшийся пункт) + Enter (toggle_via_keyboard) —
           без мыши.
        3. Проверяется, что в поле выбран РОВНО один recipient — Reporter.
    """
    with allure.step("Открыть поле Recipients кликом и удалить дефолтное значение"):
        recipients_modal.open_dropdown()
        recipients_modal.clear_all()

    with allure.step("Найти Reporter поиском (ввод с клавиатуры, не клик)"):
        recipients_modal.search("Reporter")
        recipients_modal.wait_for_search_to_settle()
        # Активный поллинг (а не is_visible()) — та же причина, что и в
        # остальных search-тестах этого файла: один-единственный .is_visible()
        # сразу после settle() может попасть на промежуточное состояние.
        expect(recipients_modal.option("Reporter")).to_be_visible(timeout=10_000)

    with allure.step(
        "Перейти на единственный найденный пункт клавишей ArrowDown и "
        "выбрать его клавишей Enter"
    ):
        recipients_modal.toggle_via_keyboard(times_down=1)

    with allure.step("Проверить, что в поле выбрана ровно опция Reporter"):
        tags = recipients_modal.selected_tags()
        assert tags == ["Reporter"], (
            f"Ожидался ровно один выбранный клавиатурой recipient "
            f"'Reporter', получено: {tags!r}"
        )


# --- REMCL-1089 / 1090 / 1092 / 1093+1094 / 1097: поиск ---


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1089")
@pytest.mark.validation
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_user_found_by_partial_name(recipients_modal: ReminderModal) -> None:
    """REMCL-1089: пользователь отображается в dropdown после ввода части имени."""
    with allure.step("Ввести часть имени пользователя 'Aleksey' (-> Aleksey Mitin)"):
        recipients_modal.search("Aleks")
        recipients_modal.wait_for_search_to_settle()

    with allure.step("Проверить, что пользователь найден"):
        # expect(...) вместо .is_visible() — именно здесь (а не только в
        # wait_for_search_to_settle()) нужен АКТИВНЫЙ поллинг: если у
        # поиска несколько циклов "Loading..." подряд (см. 2026-11-16,
        # находка по REMCL-1090 ниже), то один-единственный .is_visible()
        # сразу после settle() всё ещё может попасть на промежуточное
        # состояние.
        expect(recipients_modal.option("Aleksey Mitin")).to_be_visible(timeout=10_000)


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1090")
@pytest.mark.validation
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_group_found_by_partial_name(recipients_modal: ReminderModal) -> None:
    """REMCL-1090: группа отображается в dropdown после ввода части названия."""
    with allure.step("Ввести часть названия группы 'watch' (-> Watchers)"):
        recipients_modal.search("watch")
        recipients_modal.wait_for_search_to_settle()

    with allure.step("Проверить, что группа найдена"):
        # expect(...) вместо .is_visible() — см. 2026-11-16 ниже и
        # комментарий в test_user_found_by_partial_name: живым прогоном
        # (по репорту с пользователем) подтверждено, что одного ожидания
        # исчезновения "Loading..." НЕДОСТАТОЧНО — результат может прийти
        # уже ПОСЛЕ того, как wait_for_search_to_settle() вернул управление
        # (похоже на повторный цикл "Loading..." именно для групп/серверной
        # части поиска). expect() активно поллит локатор вместо одного
        # снимка состояния — устойчив к любому числу таких циклов.
        expect(recipients_modal.option("Watchers")).to_be_visible(timeout=10_000)


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1092")
@pytest.mark.validation
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_search_is_case_insensitive(recipients_modal: ReminderModal) -> None:
    """REMCL-1092: результаты поиска отображаются после ввода строки в другом регистре."""
    with allure.step("Ввести имя пользователя ВЕРХНИМ регистром: 'ALEKSEY'"):
        recipients_modal.search("ALEKSEY")
        recipients_modal.wait_for_search_to_settle()

    with allure.step("Проверить, что пользователь найден несмотря на регистр"):
        # expect(...) вместо .is_visible() — см. комментарий в
        # test_user_found_by_partial_name выше.
        expect(recipients_modal.option("Aleksey Mitin")).to_be_visible(timeout=10_000)


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1093")
@allure.tag("REMCL-1094")
@pytest.mark.validation
@pytest.mark.parametrize(
    "query",
    [
        pytest.param("qwzxcvqwzxcv", id="no-matches"),  # REMCL-1093
        pytest.param("   ", id="whitespace-only"),  # REMCL-1094
    ],
)
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_empty_result_state_shown(recipients_modal: ReminderModal, query: str) -> None:
    """
    REMCL-1093 (строка без совпадений) и REMCL-1094 (строка из одних
    пробелов) — живым прогоном подтверждено, что оба случая показывают
    ОДИНАКОВЫЙ текст 'No recipients found' (отдельного текста "No option",
    упомянутого в Summary исходного кейса, обнаружено не было).
    """
    with allure.step(f"Ввести в поле Recipients строку {query!r}"):
        recipients_modal.search(query)
        recipients_modal.wait_for_search_to_settle()

    with allure.step("Проверить сообщение 'No recipients found'"):
        assert (
            recipients_modal.has_no_results_message()
        ), f"Сообщение о пустом результате не появилось для запроса {query!r}"


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1097")
@pytest.mark.validation
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_no_duplicate_tag_after_reselecting_same_user(
    recipients_modal: ReminderModal,
) -> None:
    """REMCL-1097: duplicate-тег не появляется после повторного выбора одного и того же пользователя."""
    with allure.step("Выбрать Assignee"):
        recipients_modal.open_dropdown()
        recipients_modal.select("Assignee")
        assert recipients_modal.selected_tags().count("Assignee") == 1

    with allure.step(
        "Повторно открыть список и ещё раз нажать на уже выбранного Assignee"
    ):
        recipients_modal.select("Assignee")

    with allure.step(
        "Проверить, что дубликат тега НЕ появился (повторный клик снимает выбор)"
    ):
        assert (
            recipients_modal.selected_tags().count("Assignee") == 0
        ), "Повторный выбор того же recipient создал дубликат тега вместо снятия выбора"


# =====================================================================
# QA Label "F" (2026-11-16): новые тесты, которые НЕ требуют ни второго
# пользователя, ни реального сохранения ремайндера — см. докстринг модуля.
# =====================================================================


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1064")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_placeholder_exact_text_when_field_empty(
    recipients_modal: ReminderModal,
) -> None:
    """
    REMCL-1064 (QA Label "F"): если очистить поле Recipients, в нём
    отображается плейсхолдер с текстом "Type to search users or groups…".

    Дополняет REMCL-1070 (который проверяет только факт видимости
    плейсхолдера) точной проверкой его текста.
    """
    with allure.step("Очистить поле Recipients"):
        recipients_modal.clear_all()

    with allure.step(f"Проверить точный текст плейсхолдера: {PLACEHOLDER_TEXT!r}"):
        actual = recipients_modal.placeholder_text()
        assert actual == PLACEHOLDER_TEXT, f"Неожиданный текст плейсхолдера: {actual!r}"


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1066")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_search_covers_users_and_groups_for_user_with_rights(
    recipients_modal: ReminderModal,
) -> None:
    """
    REMCL-1066 (QA Label "F"): пользователь с правом "Ability to create
    reminders for groups or roles" может искать по юзерам И группам (И
    ролям — но см. ниже) в поле Recipients.

    Роли здесь НЕ проверяются: секция "Roles" ни разу не появилась на
    тестовом инстансе (см. REMCL-1091 ниже — тот же технический риск, п.8
    докстринга reminder_modal.py). Утверждать что-то про Roles без живого
    подтверждения значило бы угадывать, поэтому проверены только Users и
    Groups — то, что реально подтверждено.

    Не требует второго пользователя: текущий тестовый пользователь уже
    обладает нужным правом (см. REMCL-1077).
    """
    with allure.step("Открыть дропдаун поля Recipients без фильтра"):
        recipients_modal.open_dropdown()

    with allure.step("Проверить, что видны секции Users и Groups"):
        assert (
            recipients_modal.is_users_section_visible()
        ), "Секция 'Users' не найдена — поиск по пользователям недоступен"
        assert (
            recipients_modal.is_groups_section_visible()
        ), "Секция 'Groups' не найдена — поиск по группам недоступен"


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1107")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_dropdown_results_update_as_search_query_changes(
    recipients_modal: ReminderModal,
) -> None:
    """
    REMCL-1107 (QA Label "F"): список результатов дропдауна Recipients
    обновляется после ввода нового поискового запроса, а не остаётся от
    предыдущего.

    Доказываем это сменой запроса, после которой видимый набор секций
    РЕАЛЬНО меняется: запрос "watch" (-> группа Watchers) даёт только
    секцию Groups без Users (см. п.6 докстринга reminder_modal.py — поиск
    фильтрует и сами секции), а следующий запрос "Aleks" (-> пользователь
    Aleksey Mitin) даёт уже Users без Groups. Если бы список результатов не
    обновлялся — второй запрос продолжил бы показывать результат первого.
    """
    with allure.step("Ввести запрос 'watch' (совпадение только по группе)"):
        recipients_modal.search("watch")
        recipients_modal.wait_for_search_to_settle()
        assert (
            recipients_modal.is_groups_section_visible()
        ), "Секция 'Groups' не найдена по запросу 'watch'"
        assert not recipients_modal.is_users_section_visible(
            timeout_ms=1_500
        ), "Секция 'Users' неожиданно видна по запросу 'watch'"

    with allure.step("Сменить запрос на 'Aleks' (совпадение только по пользователю)"):
        recipients_modal.search("Aleks")
        recipients_modal.wait_for_search_to_settle()

    with allure.step(
        "Проверить, что результат обновился: теперь видна секция Users, а не Groups"
    ):
        assert (
            recipients_modal.is_users_section_visible()
        ), "Секция 'Users' не найдена по запросу 'Aleks' — похоже, результат не обновился"
        assert not recipients_modal.is_groups_section_visible(
            timeout_ms=1_500
        ), "Секция 'Groups' всё ещё видна после смены запроса на 'Aleks'"


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1108")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_dropdown_closes_on_outside_click(recipients_modal: ReminderModal) -> None:
    """
    REMCL-1108 (QA Label "F"): дропдаун поля Recipients закрывается при
    клике по области ВНЕ поля.

    Исходный кейс допускает ДВА способа закрытия — "по шеврону ИЛИ по
    области вне поля". Реализован только второй: точный локатор
    кнопки-шеврона поля Recipients не подтверждён вживую (см. п.9
    докстринга reminder_modal.py) — угадывать его не стали (см. также
    ReminderModal.close_dropdown_by_clicking_outside).
    """
    with allure.step("Открыть дропдаун поля Recipients"):
        recipients_modal.open_dropdown()
        assert (
            recipients_modal.is_dropdown_open()
        ), "Предусловие не выполнено: дропдаун не открылся"

    with allure.step("Кликнуть по области вне поля Recipients"):
        recipients_modal.close_dropdown_by_clicking_outside()

    with allure.step("Проверить, что дропдаун закрылся"):
        assert not recipients_modal.is_dropdown_open(
            timeout_ms=2_000
        ), "Дропдаун всё ещё открыт после клика вне поля"


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1110")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_recipient_tag_disappears_after_removing_recipient(
    recipients_modal: ReminderModal,
) -> None:
    """
    REMCL-1110 (QA Label "F"): тег recipient'а исчезает из поля Recipients
    после его удаления.
    """
    with allure.step("Выбрать Assignee"):
        recipients_modal.open_dropdown()
        recipients_modal.select("Assignee")
        assert (
            "Assignee" in recipients_modal.selected_tags()
        ), "Предусловие не выполнено: тег 'Assignee' не появился после выбора"

    with allure.step("Удалить тег 'Assignee'"):
        recipients_modal.remove_tag("Assignee")

    with allure.step("Проверить, что тег исчез"):
        assert (
            "Assignee" not in recipients_modal.selected_tags()
        ), "Тег 'Assignee' всё ещё виден после удаления recipient'а"


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1112")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_selected_recipient_persists_after_closing_dropdown(
    recipients_modal: ReminderModal,
) -> None:
    """
    REMCL-1112 (QA Label "F"): выбранное значение в поле Recipients
    сохраняется после закрытия дропдауна (тег не пропадает просто от
    закрытия списка опций).
    """
    with allure.step("Выбрать Assignee"):
        recipients_modal.open_dropdown()
        recipients_modal.select("Assignee")

    with allure.step("Закрыть дропдаун кликом вне поля"):
        recipients_modal.close_dropdown_by_clicking_outside()
        assert not recipients_modal.is_dropdown_open(
            timeout_ms=2_000
        ), "Предусловие не выполнено: дропдаун не закрылся"

    with allure.step("Проверить, что тег 'Assignee' всё ещё виден"):
        assert (
            "Assignee" in recipients_modal.selected_tags()
        ), "Тег 'Assignee' пропал после закрытия дропдауна"


# =====================================================================
# Заготовки для кейсов, которые НЕ реализованы в этом батче — честно
# помечены skip с причиной (см. docstring модуля), а не угаданы.
# =====================================================================


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1076")
@allure.tag("REMCL-1065")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_groups_hidden_and_search_users_only_for_user_without_rights(
    recipients_modal_as_user_without_group_reminder_permission: ReminderModal,
) -> None:
    """
    REMCL-1076: секция Groups СКРЫТА в дропдауне поля Recipients для
    пользователя БЕЗ права "Ability to create reminders for groups or
    roles" (негативный сценарий — позитивный, для пользователя С этим
    правом, см. test_groups_section_visible_for_user_with_rights выше).

    REMCL-1065 (QA Label "F"): для такого пользователя поиск/список в
    Recipients доступен ТОЛЬКО по Users — проверяется той же парой
    ассертов (Users видна, Groups не видна) на незафильтрованном
    дропдауне, по аналогии с тем, как позитивный случай для обоих типов
    сразу проверен в test_search_covers_users_and_groups_for_user_with_
    rights (там же объяснение, почему без текстового фильтра этого
    достаточно: видимость заголовка секции и есть то, что определяет,
    попадают ли её элементы в результат).

    REMCL-1079 (из исходной группы REMCL-1076/1079/1065) формулирует то же
    самое ещё и про секцию Roles — но секция "Roles" ни разу не появлялась
    на тестовом проекте CPR1 ДАЖЕ для пользователя С правом на групповые/
    ролевые ремайндеры (см. test_roles_section_behavior ниже и технический
    риск, reminder_modal.py п.8). Без видимого "до" (Roles не скрыта, а
    просто никогда не показывалась) невозможно честно подтвердить, что
    ИМЕННО отсутствие права — причина отсутствия секции у этого
    пользователя, а не то же самое окруж. ограничение (не настроены project
    roles на CPR1 / Roles не поддерживаются для team-managed проекта).
    Поэтому Roles здесь сознательно НЕ assert'ится — REMCL-1079 остаётся
    неподтверждённым до прояснения с продуктовой командой по
    REMCL-1078/1091/1095/1096.
    """
    with allure.step(
        "Открыть дропдаун поля Recipients под пользователем без права на группы"
    ):
        recipients_modal_as_user_without_group_reminder_permission.open_dropdown()

    with allure.step("Проверить, что секция 'Users' видна"):
        assert (
            recipients_modal_as_user_without_group_reminder_permission.is_users_section_visible()
        ), "Секция 'Users' не найдена — поиск по пользователям должен быть доступен в любом случае"

    with allure.step("Проверить, что секция 'Groups' СКРЫТА"):
        assert not (
            recipients_modal_as_user_without_group_reminder_permission.is_groups_section_visible(
                timeout_ms=3_000
            )
        ), (
            "Секция 'Groups' отображается, хотя у текущего пользователя НЕТ "
            "права 'Ability to create reminders for groups or roles'"
        )


@pytest.mark.skip(
    reason=(
        "REMCL-1078/1091/1095/1096: завязаны на секцию 'Roles' в дропдауне "
        "поля Recipients, которая ни разу не появилась на тестовом проекте "
        "CPR1 несмотря на наличие нужного права у пользователя (см. "
        "технический риск, pages/components/reminder_modal.py, п.8). Нужно "
        "уточнить у продуктовой команды: на этом инстансе у проекта CPR1 "
        "просто не настроены project roles, или Roles не поддерживаются "
        "для team-managed проектов — и подобрать/настроить подходящий "
        "проект для этих кейсов."
    )
)
@pytest.mark.validation
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_roles_section_behavior() -> None:
    """REMCL-1078 / REMCL-1091 / REMCL-1095 / REMCL-1096."""


@pytest.mark.skip(
    reason=(
        "REMCL-1082/REMCL-1083: исходный кейс ожидает строгую сортировку "
        "A-Z 0-9 для пользователей/групп (кроме закреплённых первыми "
        "Assignee/Reporter/Watchers). Живой прогон на тестовом инстансе "
        "ПОКАЗАЛ порядок, который НЕ выглядит алфавитным (например, в "
        "секции Groups 'new group' шёл раньше 'jira-users'). Это либо "
        "расхождение с ожиданием кейса, либо сортировка на деле идёт по "
        "другому полю (дата создания, активность и т.п.) — нужно уточнить "
        "у продуктовой/дев команды фактическое правило сортировки, прежде "
        "чем писать ассерт, который либо всегда красный, либо проверяет "
        "не то, что заявлено в кейсе."
    )
)
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_users_and_groups_sorted_alphabetically() -> None:
    """REMCL-1082 / REMCL-1083."""


@pytest.mark.skip(
    reason=(
        "REMCL-1084: чтобы проверить лимит 'не более 20 опций в дропдауне', "
        "нужно свыше 20 пользователей/групп, подходящих под один и тот же "
        "поисковый запрос (или под пустой запрос). На тестовом инстансе "
        "столько тестовых данных нет — нужно либо отдельно засеять, либо "
        "подобрать запрос, под который реально попадает >20 опций."
    )
)
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_dropdown_shows_at_most_20_options() -> None:
    """REMCL-1084."""


@pytest.mark.skip(
    reason=(
        "REMCL-1081 (JSM-часть): вариант этого кейса про 'Request "
        "participants' первыми в секции Groups относится к JSM-проекту. "
        "На тестовом инстансе нет JSM-проекта — Jira-часть (Watchers "
        "первыми) реализована в test_watchers_listed_first_in_groups_"
        "section_for_jira_project выше."
    )
)
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_request_participants_listed_first_for_jsm_project() -> None:
    """REMCL-1081 (JSM-часть)."""


# =====================================================================
# QA Label "F" (2026-11-16), батч ниже: все эти кейсы требуют либо
# реального сохранения ремайндера (submit), либо проверки почты, либо
# и того, и другого. У ReminderModal пока нет метода сабмита формы (кнопка
# "Create" внутри модалки ни разу не кликалась ни одним тестом), в
# репозитории нет MyRemindersPage/QueuePage для проверки, что ремайндер
# реально создан, и нет mail_client.py/IMAP-интеграции для проверки
# письма (см. docstring модуля, раздел "Инфраструктурный пробел"). Без
# этой инфраструктуры писать такие тесты — значит угадывать поведение,
# поэтому все они честно помечены skip с указанием конкретной причины.
# =====================================================================


_PINNED_RECIPIENT_SPECS = frozenset({"Reporter", "Watchers", "Assignee"})


def _resolve_recipient_spec(spec: str, settings: Settings) -> str:
    """
    Резолвит один элемент recipient_specs (см. test_reminder_created_
    successfully_with_user_or_group_recipient) в реальное видимое имя
    опции в дропдауне Recipients.

    "Reporter"/"Watchers"/"Assignee" — уже видимые имена закреплённых
    первыми пунктов, возвращаются как есть. "creator" — резолвится через
    settings.jira_user_display_name (с honest skip, если не задан —
    тот же паттерн, что в test_default_recipient_is_reminder_creator).
    "group1"/"group2"/"group3" — резолвятся через settings.jira_test_
    group_names_list[N] (REMCL-2856, добавлено 2026-11-16 по отдельному
    запросу на multi-group кейс — "Watchers" для этого не подходит, это
    единственная ЗАКРЕПЛЁННАЯ группа, а нужны минимум ДВЕ РАЗНЫЕ обычные
    группы; см. JIRA_TEST_GROUP_NAMES в .env.example и config/settings.py).
    """
    if spec == "creator":
        if settings.jira_user_display_name is None:
            pytest.skip(
                "JIRA_USER_DISPLAY_NAME не задан в .env — без него нельзя "
                "выбрать recipient'ом самого создателя ремайндера по "
                "имени (см. .env и config/settings.py, тот же паттерн, "
                "что в test_default_recipient_is_reminder_creator)."
            )
        return settings.jira_user_display_name
    if spec.startswith("group") and spec[len("group") :].isdigit():
        index = int(spec[len("group") :]) - 1
        groups = settings.jira_test_group_names_list
        if index >= len(groups):
            pytest.skip(
                f"JIRA_TEST_GROUP_NAMES в .env не содержит "
                f"{index + 1}-ю реальную группу (сейчас задано "
                f"{len(groups)}) — без неё нечего выбрать для "
                f"multi-group кейса REMCL-2856 (см. .env.example и "
                f"config/settings.py: jira_test_group_names_list)."
            )
        return groups[index]
    return spec


def _select_recipient_spec(modal: ReminderModal, spec: str, actual_name: str) -> None:
    """
    Выбирает ОДНОГО recipient'а по уже резолвленному видимому имени
    (actual_name), не трогая ранее выбранных recipients (см. вызывающий
    код — тут НЕТ clear_all(), только добавление очередного тега).

    "Reporter"/"Watchers"/"Assignee" — закреплённые первыми пункты, видны
    сразу в неотфильтрованном списке -> select() напрямую (как и раньше).
    Любое другое имя ("creator", "group1"/"group2"/"group3") — обычная
    строка списка, которую сначала нужно НАЙТИ через search()
    (иначе риск REMCL-1084, "не более 20 опций в дропдауне без фильтра").

    Для "creator" дополнительно используется option_in_users_section()/
    select_in_users_section(), а не обычный option()/select() — см. их
    докстринги в reminder_modal.py и ИСПРАВЛЕНО (2026-11-16, по скриншоту
    живого прогона [chromium-creator]) ниже в докстринге теста: имя
    создателя на тестовом инстансе совпало с именем некой ГРУППЫ,
    из-за чего обычный option(name) переставал быть уникальным
    локатором. Для group1/group2/group3 такой неоднозначности не
    предполагается (это заведомо РАЗНЫЕ, явно заданные пользователем в
    .env группы, не совпадающие по тексту с именами пользователей) —
    там используется обычный option()/select().
    """
    if spec in _PINNED_RECIPIENT_SPECS:
        modal.select(actual_name)
        return
    modal.search(actual_name)
    modal.wait_for_search_to_settle()
    if spec == "creator":
        expect(modal.option_in_users_section(actual_name)).to_be_visible(timeout=10_000)
        modal.select_in_users_section(actual_name)
    else:
        expect(modal.option(actual_name)).to_be_visible(timeout=10_000)
        modal.select(actual_name)


@allure.severity(allure.severity_level.CRITICAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1100")
@allure.tag("REMCL-1101")
@allure.tag("REMCL-2854")
@allure.tag("REMCL-2855")
@allure.tag("REMCL-2856")
@pytest.mark.functional
@pytest.mark.issue_panel
@pytest.mark.recipients
@pytest.mark.parametrize(
    "recipient_specs",
    [
        ("Reporter",),
        ("Watchers",),
        ("creator",),
        ("Assignee", "creator"),
        ("group1", "creator"),
        ("group1", "group2"),
    ],
    ids=[
        "user",
        "group",
        "creator",
        "multiple_users",
        "user_and_group",
        "multiple_groups",
    ],
)
def test_reminder_created_successfully_with_user_or_group_recipient(
    recipients_modal: ReminderModal,
    issue_page: IssuePage,
    recipient_specs: tuple[str, ...],
    settings: Settings,
) -> None:
    """
    REMCL-1100 (recipient типа "юзер") / REMCL-1101 (recipient типа
    "группа") / REMCL-2854 (один юзер + одна группа) / REMCL-2855
    (несколько юзеров) / REMCL-2856 (несколько групп): ремайндер реально
    создаётся (сохраняется), если выбран один ИЛИ НЕСКОЛЬКО recipients —
    пользователь(и), группа(ы) или сам создатель ремайндера ("creator").

    РЕАЛИЗОВАНО (2026-11-16, по запросу "доделать skip-тесты, раз кнопка
    Create теперь работает") — та же схема, что в test_create_button_
    saves_reminder (tests/ui/test_reminder_create_cancel.py): уникальное
    сообщение + ReminderModal.submit() + ReminderPanel.has_reminder_with_
    text(). РАСШИРЕНО (2026-11-16, по отдельному запросу — три новых
    кейса из RTM-экспорта "rtm-issues-export_19.zip") с одиночного
    recipient'а на recipient_specs — КОРТЕЖ из одного или нескольких
    спецификаторов, резолвимых через _resolve_recipient_spec() и
    выбираемых по очереди через _select_recipient_spec() (см. их
    докстринги выше):
      - "Reporter"/"Assignee" — закреплённые первыми пункты секции Users,
        есть всегда, не зависят от тестовых данных;
      - "Watchers" — закреплённый первым пункт секции Groups (см. п.6
        докстринга ReminderModal);
      - "creator" — САМ текущий тестовый пользователь (создатель
        ремайндера) по имени, из settings.jira_user_display_name
        (JIRA_USER_DISPLAY_NAME в .env) — тот же источник, что и в
        test_default_recipient_is_reminder_creator, а не хардкодится;
      - "group1"/"group2" — РЕАЛЬНЫЕ (не закреплённые) группы с
        тестового инстанса, из settings.jira_test_group_names_list
        (JIRA_TEST_GROUP_NAMES в .env) — нужны минимум 2 штуки для
        multi-group кейса (REMCL-2856), honest skip если их не хватает.

    ПЕРЕСМОТРЕНО (2026-11-16, по отдельному запросу — "что конкретно
    выбирать в multiple_users/user_and_group") комбинации под
    multiple_users/user_and_group:
      - REMCL-2855 (multiple_users) = ("Assignee", "creator") — юзер
        Assignee + сам текущий тестовый пользователь (создатель
        ремайндера), а не Assignee+Reporter, как было раньше;
      - REMCL-2854 (user_and_group) = ("group1", "creator") — первая
        группа из JIRA_TEST_GROUP_NAMES + сам текущий тестовый
        пользователь, а не Reporter+Watchers, как было раньше.
    multiple_groups (REMCL-2856) не изменился — по-прежнему ("group1",
    "group2").

    ИСПРАВЛЕНО (2026-11-16, по скриншоту живого прогона [chromium-
    creator]): на тестовом инстансе по имени settings.jira_user_display_
    name после search() находятся ДВЕ опции с ОДИНАКОВЫМ видимым текстом
    — одна в секции "Users", другая в секции "Groups" (на инстансе,
    по-видимому, существует группа с тем же именем, что и пользователь-
    создатель). Обычный option(name)/select(name) в этом случае — не
    уникальный локатор: на скриншоте видно обе строки с НЕотмеченными
    чекбоксами и disabled Create — значит expect(...).to_be_visible()
    либо click() спотыкались об эту неоднозначность (strict-mode
    violation), и исходный клик либо не происходил вовсе, либо рисковал
    отметить не ту (Groups) строку. Поэтому для ветки "creator"
    используются option_in_users_section()/select_in_users_section()
    (см. их докстринги в reminder_modal.py) — осознанная опора на уже
    подтверждённый порядок секций (Users идёт раньше Groups), а не
    "пропуск" неоднозначности угадыванием. Для остальных спецификаторов
    эта неоднозначность не предполагается (они не совпадают текстом ни с
    чем другим на момент реализации), поэтому там используется обычный
    option()/select().

    СУЖЕНО по сравнению с исходной формулировкой skip (не угадываю то, что
    не могу подтвердить):
      - REMCL-1102 (recipient типа "роль") здесь НЕ реализован — секция
        "Roles" ни разу не появилась на тестовом инстансе (см.
        test_roles_section_behavior выше).
      - REMCL-1113 / REMCL-1117 из того же исходного skip тоже не
        реализованы отдельно: точные формулировки этих двух кейсов не
        разобраны отдельно в докстринге модуля, и приписывать им именно
        эту проверку значило бы угадывать, что в них на самом деле
        заявлено.
      - Проверяется ТОЛЬКО то, что создание ремайндера с такими
        recipients УСПЕШНО (ремайндер появляется в секции Reminder) — а
        НЕ то, что сами выбранные recipients видны или названы где-то
        внутри сохранённой записи, и НЕ то, что происходит дедупликация
        получателей при пересечении (REMCL-1114/1115/1116, см. test_
        single_reminder_when_recipient_selected_via_multiple_paths выше —
        остаётся отдельным skip). Разметка строки созданного ремайндера
        в секции Reminder до сих пор не подтверждена вживую (см.
        ТЕХНИЧЕСКИЙ РИСК, п.7 докстринга reminder_panel.py).

    Как и test_create_button_saves_reminder, ничего не удаляет за собой —
    каждый параметр прогона оставляет в тестовом инстансе одну запись.
    """
    actual_names = [_resolve_recipient_spec(spec, settings) for spec in recipient_specs]

    slug = "-".join(spec.lower() for spec in recipient_specs)
    unique_message = (
        f"{_faker.sentence(nb_words=4).rstrip('.')} "
        # datetime.UTC (ruff UP017) требует Python 3.11+ — см. тот же
        # комментарий в test_reminder_create_cancel.py.
        f"[autotest-{slug} "
        f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}]"
    )

    with allure.step(f"Выбрать recipient'ами: {actual_names!r}"):
        recipients_modal.open_dropdown()
        recipients_modal.clear_all()
        for spec, actual_name in zip(recipient_specs, actual_names, strict=True):
            _select_recipient_spec(recipients_modal, spec, actual_name)
        tags = recipients_modal.selected_tags()
        assert sorted(tags) == sorted(actual_names), (
            f"Предусловие не выполнено: ожидались теги {sorted(actual_names)!r}, "
            f"получено {sorted(tags)!r}"
        )

    with allure.step(f"Ввести уникальный текст сообщения: {unique_message!r}"):
        recipients_modal.fill_message(unique_message)

    with allure.step("Нажать Create"):
        recipients_modal.submit()

    with allure.step(
        "Проверить, что ремайндер с этим текстом появился в секции Reminder"
    ):
        assert issue_page.reminder_panel.has_reminder_with_text(
            unique_message
        ), "Созданный ремайндер не найден в секции Reminder на странице задачи"


@pytest.mark.skip(
    reason=(
        "REMCL-1103/1104: проверяют дропдаун Recipients при создании "
        "ремайндера БЕЗ привязки к задаче (Assignee/Reporter/Roles должны "
        "быть скрыты). В репозитории есть только Page Object для секции "
        "Reminder НА странице задачи (IssuePage/ReminderPanel) — флоу "
        "создания ремайндера без задачи (например, из 'My reminders' или "
        "из дашборд-гаджета) пока не реализован ни одним Page Object."
    )
)
@pytest.mark.functional
@pytest.mark.recipients
def test_assignee_reporter_and_roles_hidden_without_issue_context() -> None:
    """REMCL-1103 / REMCL-1104."""


@pytest.mark.skip(
    reason=(
        "REMCL-1106: проверяет, что роль 'Participants' НЕ отображается в "
        "дропдауне Recipients для задачи не из JSM-проекта. Секция 'Roles' "
        "в принципе ни разу не появилась на тестовом инстансе под текущим "
        "пользователем (см. технический риск, pages/components/"
        "reminder_modal.py, п.8, и test_roles_section_behavior выше) — "
        "нельзя отличить 'роли скрыты потому что проект не JSM' от 'роли "
        "скрыты потому что секция Roles вообще не работает на этом "
        "инстансе', поэтому кейс пропущен до уточнения причины отсутствия "
        "секции Roles."
    )
)
@pytest.mark.functional
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_participants_role_not_shown_for_non_jsm_issue() -> None:
    """REMCL-1106."""


@allure.severity(allure.severity_level.CRITICAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1114")
@pytest.mark.functional
@pytest.mark.email
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_single_reminder_when_recipient_selected_via_multiple_paths(
    recipients_modal: ReminderModal,
    settings: Settings,
    mail_client: MailClient,
) -> None:
    """
    REMCL-1114: пользователь, выбранный РЕКОМ одновременно И напрямую, И
    через группу (пересечение путей выбора получателя), должен получить
    РОВНО ОДНО письмо — дедупликация получателей на стороне плагина, а не
    два отдельных письма.

    REMCL-1115/1116 (то же пересечение, но через РОЛЬ) здесь НЕ
    реализованы — секция "Roles" ни разу не появилась на тестовом
    инстансе под текущим пользователем (см. test_roles_section_behavior,
    п.8 докстринга reminder_modal.py) — не на чем это проверить, пока эта
    секция не подтвердится живым прогоном под другим пользователем/
    проектом.

    ДИЗАЙН ПРОВЕРКИ (согласовано с пользователем 2026-11-18, по итогам
    обсуждения первоначальной идеи "ручное Yes/No подтверждение по
    письму" — см. историю сессии): создаём ремайндер на ближайшее
    будущее время (округлённое вверх до кратных 5 минут — поле
    "Date & time" физически не позволяет выбрать произвольную минуту, см.
    п.13 докстринга reminder_modal.py) с уникальным текстом в Message и
    recipients = [получатель напрямую, группа-содержащая-этого-же-
    получателя], затем РЕАЛЬНО дожидаемся письма по IMAP (mail_client.
    wait_for_email) и считаем, сколько писем с этим текстом пришло
    (mail_client.count_matching) — ожидается РОВНО 1.

    ИСПРАВЛЕНО (2026-11-19, по живому прогону): получатель здесь — это
    MAIL_TEST_RECIPIENT_DISPLAY_NAME, а НЕ обычный тестовый пользователь
    (JIRA_USER_DISPLAY_NAME, под которым тест логинится). Изначально
    получателем выбирался именно creator (JIRA_USER_DISPLAY_NAME) — но
    реальным прогоном выяснилось, что почтовый ящик, доступный нам по
    IMAP (MAIL_IMAP_LOGIN), принадлежит ДРУГОМУ реальному пользователю
    тестового инстанса, а не обычному тестовому пользователю — то есть
    тест, который выбирал creator'а recipient'ом, реально отправлял письмо
    в ящик, который MailClient не читает (отсюда ложные таймауты
    wait_for_email, хотя письмо приходило — просто не туда, куда смотрели
    по IMAP, см. историю сессии и ИСПРАВЛЕНО 2026-11-19 про MAIL_IMAP_LOGIN
    в config/settings.py). Теперь recipient'ом выбирается именно тот
    пользователь, чей ящик мы реально читаем — семантика дедупликации
    (тот же человек выбран и напрямую, и через группу) при этом не
    меняется, просто это не обязательно должен быть сам creator.

    ПОЧЕМУ НЕ Reporter/Assignee/Watchers самой задачи (CPR1-10) в
    качестве "группы, куда входит получатель" (самый очевидный кандидат,
    не требующий отдельной переменной в .env): живым просмотром через
    built-in browser 2026-11-18 подтверждено, что Reporter ("Бьорн ...")
    и Assignee ("Селезнёва Рита-") этой задачи — ДРУГИЕ люди (проверялось
    тогда ещё относительно creator'а, но по факту они не совпадают ни с
    одним из известных тестовых пользователей); а поле Watchers в
    сайдбаре Details вообще не нашлось (0 вочеров или не в Details — не
    выяснялось отдельно). Выбирать "Watchers" или любую группу из
    JIRA_TEST_GROUP_NAMES (REMCL-2856) вслепую — реальный риск отправить
    письмо ПОСТОРОННИМ людям, если группа содержит кого-то ещё кроме
    нужного получателя (та же проблема, из-за которой REMCL-1118/1119
    ниже сознательно НЕ проверяют доставку вообще). Поэтому этот тест
    требует ОТДЕЛЬНУЮ, явно заданную в .env переменную JIRA_TEST_GROUP_
    CONTAINING_MAIL_RECIPIENT — honest skip, если не задана, а не
    угаданная группа (см. config/settings.py).

    ТЕХНИЧЕСКИЙ РИСК (не подтверждено вживую, помимо рисков, уже
    перечисленных в reminder_modal.py п.13 и utils/mail_client.py):
      - сколько времени плагин может ждать ПОСЛЕ наступления
        запланированного момента, прежде чем реально отправить письмо
        (_PLUGIN_SCHEDULE_POLL_BUFFER_S выше — произвольный запас, не
        измеренный);
      - кладёт ли плагин текст Message в тему письма, в тело, или и туда,
        и туда (см. ДОБАВЛЕНО 2026-11-18 в докстринге utils/mail_client.py
        — поиск сейчас проверяет оба места).
    """
    if not settings.has_mail_test_recipient_and_group():
        pytest.skip(
            "MAIL_TEST_RECIPIENT_DISPLAY_NAME и/или JIRA_TEST_GROUP_"
            "CONTAINING_MAIL_RECIPIENT не заданы в .env — нужен отдельный "
            "получатель, чей почтовый ящик совпадает с MAIL_IMAP_LOGIN, и "
            "группа, про которую точно известно, что она его содержит, "
            "иначе тест рискует отправить реальное письмо посторонним "
            "людям (см. docstring и config/settings.py)."
        )

    recipient_name = settings.mail_test_recipient_display_name
    group_name = settings.jira_test_group_containing_mail_recipient

    with allure.step(
        f"Выбрать recipient'ами одновременно '{recipient_name}' (напрямую, "
        f"секция Users) и группу '{group_name}' (содержащую того же "
        "человека)"
    ):
        recipients_modal.open_dropdown()
        recipients_modal.clear_all()

        recipients_modal.search(recipient_name)
        recipients_modal.wait_for_search_to_settle()
        expect(recipients_modal.option_in_users_section(recipient_name)).to_be_visible(
            timeout=10_000
        )
        recipients_modal.select_in_users_section(recipient_name)

        recipients_modal.search(group_name)
        recipients_modal.wait_for_search_to_settle()
        expect(recipients_modal.option(group_name)).to_be_visible(timeout=10_000)
        recipients_modal.select(group_name)

        tags = recipients_modal.selected_tags()
        expected_tags = sorted([recipient_name, group_name])
        assert sorted(tags) == expected_tags, (
            f"Предусловие не выполнено: ожидались теги {expected_tags!r}, "
            f"получено {sorted(tags)!r}"
        )

    unique_message = (
        f"{_faker.sentence(nb_words=4).rstrip('.')} "
        f"[autotest-dedup-1114 "
        f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}]"
    )
    with allure.step(f"Ввести уникальный текст сообщения: {unique_message!r}"):
        recipients_modal.fill_message(unique_message)

    now_moscow = datetime.now(_MOSCOW_TZ)
    target_time = round_up_to_next_five_minutes(now_moscow)
    seconds_until_target = (target_time - now_moscow).total_seconds()
    # Момент "до" действия — фиксируется ПЕРЕД сабмитом (см. Project
    # Instructions: since должен быть зафиксирован до отправки, иначе
    # рискуем словить старое письмо с похожим текстом из прошлых прогонов).
    since = datetime.now(timezone.utc)
    with allure.step(
        f"Выставить дату/время на ближайшее будущее "
        f"({target_time.isoformat()}, Europe/Moscow) и нажать Create"
    ):
        recipients_modal.set_specific_datetime(target_time)
        recipients_modal.submit()

    allure.attach(
        f"recipients={expected_tags!r}\n"
        f"message={unique_message!r}\n"
        f"scheduled_at={target_time.isoformat()} (Europe/Moscow)",
        name="Что было создано",
        attachment_type=allure.attachment_type.TEXT,
    )

    with allure.step(
        "Дождаться письма по IMAP (с учётом времени до наступления "
        "запланированного момента) и убедиться, что пришло РОВНО одно"
    ):
        wait_timeout_s = int(
            seconds_until_target
            + settings.mail_wait_timeout_s
            + _PLUGIN_SCHEDULE_POLL_BUFFER_S
        )
        email = mail_client.wait_for_email(
            unique_message, since=since, timeout_s=wait_timeout_s
        )
        allure.attach(
            f"from={email.from_!r}\ndate={email.date.isoformat()}\n"
            f"subject={email.subject!r}",
            name="Найденное письмо",
            attachment_type=allure.attachment_type.TEXT,
        )
        count = mail_client.count_matching(unique_message, since=since)
        assert count == 1, (
            f"Ожидалось РОВНО одно письмо, содержащее {unique_message!r} "
            f"(дедупликация получателей: '{recipient_name}' выбран и "
            f"напрямую, и через группу '{group_name}'), но найдено "
            f"{count}"
        )


def _resolve_mail_recipient_group_spec(spec: str, settings: Settings) -> str:
    """
    ДОБАВЛЕНО (2026-11-19): резолвит один элемент parametrize для
    test_group_recipient_reminder_delivered_to_known_member (REMCL-1118)
    в реальное имя группы — "group1".."group5" через settings.
    jira_test_groups_containing_mail_recipient_list[N] (та же логика
    индексации, что у _resolve_recipient_spec выше, но ОТДЕЛЬНЫЙ список:
    здесь группа должна содержать MAIL_TEST_RECIPIENT_DISPLAY_NAME, а не
    просто быть "любой тестовой группой"). Фиксированный потолок в 5
    групп — если понадобится больше, расширить и parametrize, и этот
    резолвер.
    """
    index = int(spec[len("group") :]) - 1
    groups = settings.jira_test_groups_containing_mail_recipient_list
    if index >= len(groups):
        pytest.skip(
            "JIRA_TEST_GROUPS_CONTAINING_MAIL_RECIPIENT не задан (или "
            f"задано меньше групп, чем требует {spec!r}, сейчас "
            f"{len(groups)}) в .env — нужна РЕАЛЬНАЯ группа, в которую "
            "явно добавлен MAIL_TEST_RECIPIENT_DISPLAY_NAME (см. "
            "config/settings.py и REMCL-1118)."
        )
    return groups[index]


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-1118")
@pytest.mark.functional
@pytest.mark.email
@pytest.mark.issue_panel
@pytest.mark.recipients
@pytest.mark.parametrize(
    "group_spec", ["group1", "group2", "group3", "group4", "group5"]
)
def test_group_recipient_reminder_delivered_to_known_member(
    recipients_modal: ReminderModal,
    settings: Settings,
    mail_client: MailClient,
    group_spec: str,
) -> None:
    """
    REMCL-1118: ремайндер, отправленный recipient'ом-группой, реально
    доходит по почте хотя бы до ОДНОГО заведомо известного участника
    этой группы (дедуплицируясь в точности как для одного получателя —
    ожидается РОВНО одно письмо).

    ИСПРАВЛЕНО (2026-11-19, по решению пользователя — пересматривает
    решение от 2026-11-18, см. история сессии): РАНЬШЕ этот тест только
    создавал ремайндер и НИКАК не проверял доставку (группа могла
    содержать людей, чьи ящики нам недоступны — честный SKIPPED с
    просьбой проверить почту вручную). Пользователь решил добавить
    MAIL_TEST_RECIPIENT_DISPLAY_NAME ЯВНО во КАЖДУЮ из групп, заданных в
    JIRA_TEST_GROUPS_CONTAINING_MAIL_RECIPIENT — то есть теперь для
    каждой такой группы точно известен как минимум один её участник, чей
    ящик мы читаем по IMAP (MAIL_IMAP_LOGIN), и можно реально проверить
    доставку, а не создавать и пропускать.

    ЧЕСТНАЯ ОГОВОРКА (сохраняется из предыдущей версии теста): это
    ПРОВЕРЯЕТ, что письмо дошло ДО ЭТОГО ОДНОГО известного участника —
    это НЕ доказывает, что оно дошло до ВСЕХ участников группы (ящики
    остальных участников нам всё так же недоступны). Если группа
    содержит кого-то ещё, кому письмо не должно было прийти или пришло
    не так, как ожидается — этот тест этого не увидит.

    Параметризован через group1..group5 (резолвятся в REAL имена через
    _resolve_mail_recipient_group_spec -> settings.jira_test_groups_
    containing_mail_recipient_list[N], honest skip для неконфигурированных
    индексов) — та же логика, что у group1/group2 в test_reminder_
    created_successfully_with_user_or_group_recipient, но ОТДЕЛЬНЫЙ
    список групп (здесь группа обязана содержать MAIL_TEST_RECIPIENT_
    DISPLAY_NAME, что НЕ гарантируется для JIRA_TEST_GROUP_NAMES).
    Параметризация, а не ручной цикл по списку (см. Project Instructions
    про @pytest.mark.parametrize для однотипных проверок) — так каждая
    группа получает свой независимый PASSED/FAILED/SKIPPED в Allure,
    вместо одного падения, маскирующего остальные группы.

    REMCL-1119 (вариант с РОЛЬЮ вместо группы) здесь не реализован —
    секция "Roles" ни разу не появилась на тестовом инстансе (см.
    test_roles_section_behavior) — не из чего выбрать recipient-роль.
    """
    if settings.mail_test_recipient_display_name is None:
        pytest.skip(
            "MAIL_TEST_RECIPIENT_DISPLAY_NAME не задан в .env — без него "
            "неизвестно, чьё письмо искать по IMAP (см. config/"
            "settings.py)."
        )
    group_name = _resolve_mail_recipient_group_spec(group_spec, settings)

    unique_message = (
        f"{_faker.sentence(nb_words=4).rstrip('.')} "
        f"[autotest-group-1118-{group_spec} "
        f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}]"
    )

    with allure.step(f"Выбрать recipient'ом группу: {group_name!r}"):
        recipients_modal.open_dropdown()
        recipients_modal.clear_all()
        recipients_modal.search(group_name)
        recipients_modal.wait_for_search_to_settle()
        expect(recipients_modal.option(group_name)).to_be_visible(timeout=10_000)
        recipients_modal.select(group_name)

    with allure.step(f"Ввести уникальный текст сообщения: {unique_message!r}"):
        recipients_modal.fill_message(unique_message)

    now_moscow = datetime.now(_MOSCOW_TZ)
    target_time = round_up_to_next_five_minutes(now_moscow)
    seconds_until_target = (target_time - now_moscow).total_seconds()
    # Момент "до" действия — фиксируется ПЕРЕД сабмитом (см. Project
    # Instructions про since/REMCL-1114 выше — та же причина).
    since = datetime.now(timezone.utc)
    with allure.step(
        f"Выставить дату/время ({target_time.isoformat()}, Europe/Moscow) "
        "и нажать Create"
    ):
        recipients_modal.set_specific_datetime(target_time)
        recipients_modal.submit()

    allure.attach(
        f"recipients={[group_name]!r}\n"
        f"message={unique_message!r}\n"
        f"scheduled_at={target_time.isoformat()} (Europe/Moscow)\n"
        f"known_member={settings.mail_test_recipient_display_name!r}",
        name="Что было создано",
        attachment_type=allure.attachment_type.TEXT,
    )

    with allure.step(
        "Дождаться письма по IMAP (с учётом времени до наступления "
        "запланированного момента) и убедиться, что пришло РОВНО одно"
    ):
        wait_timeout_s = int(
            seconds_until_target
            + settings.mail_wait_timeout_s
            + _PLUGIN_SCHEDULE_POLL_BUFFER_S
        )
        email = mail_client.wait_for_email(
            unique_message, since=since, timeout_s=wait_timeout_s
        )
        allure.attach(
            f"from={email.from_!r}\ndate={email.date.isoformat()}\n"
            f"subject={email.subject!r}",
            name="Найденное письмо",
            attachment_type=allure.attachment_type.TEXT,
        )
        count = mail_client.count_matching(unique_message, since=since)
        assert count == 1, (
            f"Ожидалось РОВНО одно письмо, содержащее {unique_message!r} "
            f"для известного участника группы {group_name!r} "
            f"({settings.mail_test_recipient_display_name!r}), но найдено "
            f"{count}"
        )


@pytest.mark.skip(
    reason=(
        "REMCL-1248/1249/1250/1251/1252/1253: проверяют создание и "
        "доставку ремайндера для юзера/группы с кириллицей, иероглифами/"
        "арабской вязью или пунктуацией/спецсимволами в имени. Требует "
        "сабмита формы, mail_client.py/IMAP (ни того, ни другого пока нет "
        "в репозитории) и — главное — реальных тестовых юзеров/групп с "
        "такими именами на тестовом инстансе, которых сейчас не существует "
        "(нужно либо завести, либо подобрать среди имеющихся)."
    )
)
@pytest.mark.functional
@pytest.mark.email
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_reminder_for_recipient_with_special_characters_in_name() -> None:
    """REMCL-1248 / REMCL-1249 / REMCL-1250 / REMCL-1251 / REMCL-1252 / REMCL-1253."""


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Create/Cancel buttons")
@allure.tag("REMCL-2734")
@allure.tag("REMCL-2735")
@pytest.mark.functional
@pytest.mark.issue_panel
@pytest.mark.recipients
@pytest.mark.parametrize(
    "recipient_name",
    ["Reporter", "Watchers"],
    ids=["user", "group"],
)
def test_warning_flag_shown_after_creating_reminder(
    recipients_modal: ReminderModal, issue_page: IssuePage, recipient_name: str
) -> None:
    """
    REMCL-2734 (recipient типа "юзер": Assignee/Reporter/Watchers-как-
    юзер... здесь — "Reporter") / REMCL-2735 (recipient типа "группа":
    "Watchers"): после успешного создания ремайндера появляется
    предупреждающий flag о том, что получат ремайндер только те
    recipients, у кого есть доступ к задаче на момент отправки.

    РЕАЛИЗОВАНО (2026-11-16, по скриншоту живого прогона, присланному по
    прямой просьбе — см. IssuePage.has_recipients_visibility_warning_flag
    и RECIPIENTS_VISIBILITY_WARNING_TEXT в pages/issue_page.py). Раньше
    этот тест был skip: сам toast/flag — короткоживущий элемент, и его
    разметку/текст нельзя было подсмотреть постфактум через
    has_reminder_with_text() (та проверяет СЕКЦИЮ Reminder, а не flag) —
    требовался отдельный живой скриншот именно в момент появления этого
    окна, угадывать не стали.

    НАЙДЕНО по тому же скриншоту: flag — это НЕ просто "информационное
    окно об успехе", как было сформулировано в исходном skip по
    описанию кейса, а именно ПРЕДУПРЕЖДЕНИЕ (иконка Warning, заголовок
    "Warning") про видимость задачи для recipients — см. точный текст в
    RECIPIENTS_VISIBILITY_WARNING_TEXT.

    ТЕХНИЧЕСКИЙ РИСК (см. также докстринг has_recipients_visibility_
    warning_flag): текст flag'а скриншотом подтверждён только для
    recipient'а-пользователя (REMCL-2734, здесь — параметр "Reporter").
    Для recipient'а-группы (REMCL-2735, параметр "Watchers") используется
    ТОТ ЖЕ локатор/текст по аналогии (сам текст не завязан на конкретного
    recipient'а), отдельным скриншотом для группы это не подтверждено.
    """
    unique_message = (
        f"{_faker.sentence(nb_words=4).rstrip('.')} "
        # datetime.UTC (ruff UP017) требует Python 3.11+ — см. тот же
        # комментарий в test_reminder_create_cancel.py.
        f"[autotest-warning-flag-{recipient_name.lower()} "
        f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}]"
    )

    with allure.step(f"Выбрать единственным recipient'ом '{recipient_name}'"):
        recipients_modal.open_dropdown()
        recipients_modal.clear_all()
        recipients_modal.select(recipient_name)
        assert recipients_modal.selected_tags() == [recipient_name], (
            f"Предусловие не выполнено: ожидался единственный тег "
            f"{recipient_name!r}, получено "
            f"{recipients_modal.selected_tags()!r}"
        )

    with allure.step(f"Ввести уникальный текст сообщения: {unique_message!r}"):
        recipients_modal.fill_message(unique_message)

    with allure.step("Нажать Create"):
        recipients_modal.submit()

    with allure.step(
        "Проверить, что появился предупреждающий flag о видимости recipients"
    ):
        assert issue_page.has_recipients_visibility_warning_flag(), (
            "Предупреждающий flag "
            f"({RECIPIENTS_VISIBILITY_WARNING_TEXT!r}) не появился после "
            "создания ремайндера"
        )


@allure.severity(allure.severity_level.CRITICAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Recipients field")
@allure.tag("REMCL-2736")
@pytest.mark.functional
@pytest.mark.validation
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_reminder_not_created_for_user_without_issue_access(
    recipients_modal: ReminderModal,
    settings: Settings,
) -> None:
    """
    REMCL-2736 (откорректированный кейс из rtm-issues-export_20.zip, QA
    Label "F"): ремайндер для пользователя(ей), у которых НЕТ доступа к
    задаче, не создаётся — под полем Recipients появляется сообщение об
    ошибке, кнопка Create становится неактивной. Один тест на оба шага
    исходного кейса (см. Project Instructions про объединение шагов с
    проверками в один тест через несколько allure.step):
      1. Выбрать ОДНОГО получателя без доступа к задаче -> под полем
         ошибка "{Username} don't have permission to view the work item.
         Unselect them to create reminder." (именно "don't", не "doesn't",
         даже для одного пользователя — так в самой формулировке кейса),
         Create неактивна.
      2. Добавить ещё троих получателей без доступа (итого четыре
         выбранных) -> та же ошибка, перечисляющая уже все четыре имени,
         Create по-прежнему неактивна.

    ВАЖНО: ограниченный пользователь здесь — НЕ тот, под кем залогинен
    сам тест (в отличие от jira_user_without_group_reminder_permission_*
    в config/settings.py) — отдельная storage_state-сессия НЕ нужна. Это
    просто ЕЩЁ ОДИН recipient, выбираемый в поле Recipients ОБЫЧНЫМ
    тестовым пользователем (у которого доступ к задаче как раз есть) —
    см. settings.jira_users_without_issue_access_display_names_list и
    п.14 докстринга reminder_modal.py.

    ТЕХНИЧЕСКИЙ РИСК (см. ACCESS_ERROR_SUFFIX и п.14 докстринга
    reminder_modal.py): ни точный текст/пунктуация сообщения, ни порядок
    перечисления имён при НЕСКОЛЬКИХ выбранных пользователях не
    подтверждены вживую — на шаге с четырьмя пользователями проверяется
    только то, что КАЖДОЕ имя встречается в тексте ошибки, без фиксации
    порядка перечисления.

    ИСПРАВЛЕНО (2026-11-19, по живому наблюдению пользователя при первом
    прогоне): ошибка под полем Recipients НЕ видна, пока открыт дропдаун
    опций (тот же эффект, что и в REMCL-1074 — "дропдаун отображается
    поверх остальных полей формы", см. test_dropdown_overlays_other_
    form_fields, — судя по всему, перекрывает и зону ПОД полем, где
    рендерится эта ошибка). Поэтому после каждого select() дропдаун явно
    закрывается кликом вне поля (close_dropdown_by_clicking_outside() —
    уже подтверждённый метод, см. REMCL-1108/1110) ПЕРЕД проверкой ошибки.

    ИСПРАВЛЕНО (2026-11-19, по второму скриншоту + логу живого прогона,
    уже после фикса выше — см. п.14 докстринга reminder_modal.py): после
    выбора ВСЕХ четырёх получателей финальная проверка читала текст
    ошибки ОДНИМ снимком (access_error_text()) сразу после закрытия
    дропдауна и иногда ловила его в ПЕРЕХОДНОМ состоянии — лог падения
    показал текст с обрывом ровно посередине слова "reminder" (React
    переписывает текстовый узел несколько раз, пока список имён растёт с
    1 до 4). Исправлено: финальная проверка теперь использует
    `expect(recipients_modal.access_error_locator()).to_contain_text(name,
    ...)` на каждое имя — это auto-retrying проверка Playwright, которая
    сама поллит DOM, пока текст не станет ожидаемым (а не однократное
    чтение) — access_error_text() вызывается ТОЛЬКО после того, как все
    expect()-проверки уже прошли, то есть текст гарантированно стабилен,
    и используется лишь для сообщения об ошибке/Allure, а не для самой
    проверки.
    """
    names = settings.jira_users_without_issue_access_display_names_list
    if len(names) < 4:
        pytest.skip(
            "JIRA_USERS_WITHOUT_ISSUE_ACCESS_DISPLAY_NAMES не задан (или "
            f"задано меньше 4 имён, сейчас {len(names)}) в .env — нужны "
            "минимум 4 реальных пользователя тестового инстанса без "
            "доступа к тестовой задаче (см. config/settings.py и "
            "REMCL-2736)."
        )

    first_name, *rest_names = names[:4]

    with allure.step(
        f"Выбрать ОДНОГО recipient'а без доступа к задаче: {first_name!r}"
    ):
        recipients_modal.open_dropdown()
        recipients_modal.clear_all()
        recipients_modal.search(first_name)
        recipients_modal.wait_for_search_to_settle()
        expect(recipients_modal.option(first_name)).to_be_visible(timeout=10_000)
        recipients_modal.select(first_name)

    with allure.step("Закрыть дропдаун (ошибка под полем не видна, пока он открыт)"):
        recipients_modal.close_dropdown_by_clicking_outside()

    with allure.step(
        "Проверить ошибку под полем с ОДНИМ именем и неактивную кнопку Create"
    ):
        # expect(...).to_contain_text(...) вместо однократного
        # access_error_text() — auto-retrying проверка Playwright сама
        # поллит DOM, пока текст не станет ожидаемым (см. ИСПРАВЛЕНО
        # 2026-11-19 выше и access_error_locator() в reminder_modal.py).
        expect(recipients_modal.access_error_locator()).to_contain_text(
            first_name, timeout=10_000
        )
        error_text = recipients_modal.access_error_text()
        assert not recipients_modal.is_create_enabled(), (
            "Кнопка Create должна быть неактивна, пока выбран получатель "
            f"без доступа к задаче (текст ошибки: {error_text!r})"
        )

    with allure.step(
        f"Добавить ещё троих recipient'ов без доступа: {rest_names!r} "
        "(итого четыре выбранных)"
    ):
        for name in rest_names:
            recipients_modal.search(name)
            recipients_modal.wait_for_search_to_settle()
            expect(recipients_modal.option(name)).to_be_visible(timeout=10_000)
            recipients_modal.select(name)
        tags = recipients_modal.selected_tags()
        assert sorted(tags) == sorted(names[:4]), (
            f"Предусловие не выполнено: ожидались теги {sorted(names[:4])!r}, "
            f"получено {sorted(tags)!r}"
        )

    with allure.step("Закрыть дропдаун (ошибка под полем не видна, пока он открыт)"):
        recipients_modal.close_dropdown_by_clicking_outside()

    with allure.step(
        "Проверить ошибку под полем со ВСЕМИ четырьмя именами и "
        "неактивную кнопку Create"
    ):
        # Каждое имя проверяется СВОИМ expect(...).to_contain_text(...) —
        # React может переписывать текстовый узел несколько раз, пока
        # список имён растёт с 1 до 4 (см. ИСПРАВЛЕНО 2026-11-19 выше), и
        # auto-retrying expect() переживает это, а однократный снимок
        # текста — нет. Порядок перечисления имён в самом сообщении
        # намеренно не проверяется (см. ТЕХНИЧЕСКИЙ РИСК в docstring).
        for name in names[:4]:
            expect(recipients_modal.access_error_locator()).to_contain_text(
                name, timeout=10_000
            )
        error_text = recipients_modal.access_error_text()
        assert not recipients_modal.is_create_enabled(), (
            "Кнопка Create должна быть неактивна, пока выбраны получатели "
            f"без доступа к задаче (текст ошибки: {error_text!r})"
        )


@pytest.mark.skip(
    reason=(
        "REMCL-1098: проверяет, что ремайндер можно создать, даже если на "
        "момент создания роль/список получателей пуст (например нет "
        "watchers/assignee) — получатели определяются в момент отправки, "
        "а не в момент создания. ОБНОВЛЕНО (2026-11-16): метод сабмита "
        "формы теперь есть (ReminderModal.submit()) — это больше не "
        "блокер сам по себе. Но поле Recipients ОБЯЗАТЕЛЬНОЕ (при полном "
        "опустошении кнопка Create становится disabled, см. п.3 "
        "докстринга ReminderModal) — значит 'пустой список получателей' "
        "здесь не может означать 'вообще ничего не выбрано', а должно "
        "означать 'выбрана группа/роль, которая СЕЙЧАС резолвится в 0 "
        "человек' (например Assignee на задаче без назначенного "
        "исполнителя). Подтвердить вживую, что это именно так понимается "
        "в исходном кейсе, и проконтролировать/узнать текущее состояние "
        "assignee/watchers тестовой задачи, пока не удалось — поэтому "
        "честнее оставить как есть, чем угадывать оба момента сразу."
    )
)
@pytest.mark.functional
@pytest.mark.issue_panel
@pytest.mark.recipients
def test_reminder_can_be_created_with_empty_recipients_at_creation_time() -> None:
    """REMCL-1098."""
