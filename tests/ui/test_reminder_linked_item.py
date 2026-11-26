"""
Тесты блока Linked item — верхнего блока формы создания ремайндера.

Источник: rtm-issues-export.csv, RTM Node "Creation - Linked item (v.2.X.X)".

РЕШЕНИЕ ПОЛЬЗОВАТЕЛЯ (2026-11-25): REMCL-1046/1053/1054/1055 отложены до
реализации открытия формы НЕ из задачи. Тесты Condition реализованы и делают
RUNTIME-skip на инстансе без Advanced.

НАХОДКА 1 (2026-11-25): при типе Link поле Message ОБЯЗАТЕЛЬНО.
НАХОДКА 2 (2026-11-25): Link-ремайндер НЕ виден в секции Reminder на странице
задачи — успех подтверждается Success-флагом.
НАХОДКА 3 (2026-11-25): ошибка невалидного URL — AtlasKit Flag в TOP-документе,
живёт ~5с; проверка идёт СРАЗУ после submit(settle_timeout_ms=500).

НАХОДКА 5 (2026-11-25, по падению test_invalid_jql_disables_create):
порядок шагов в тесте был правильный (ввод → закрытие → проверка Create),
но проверка не видела дизейбл по трём независимым причинам:
  a) состояние Create проверялось ОДНОРАЗОВЫМ is_create_enabled() сразу
     после закрытия попапа, а валидация JQL АСИНХРОННАЯ (в попапе есть
     role="status" aria-live="polite" и jql-validation-tooltip) — снимок
     ловил "ещё активна". Теперь expect(create_button_locator())
     .to_be_disabled() с авто-retry (правило проекта "Гонка с ре-рендером
     React после клика");
  b) close_condition() жал Escape первым — Escape в таких редакторах
     отменяет черновик. Теперь закрытие кликом ВНЕ попапа;
  c) fill_jql() использовал insert_text() без клавиатурных событий —
     ProseMirror мог не зарегистрировать ввод. Теперь press_sequentially().
Добавлен ПРОМЕЖУТОЧНЫЙ ассерт "запрос действительно в редакторе" ДО закрытия
попапа — чтобы больше никогда молча не проверять "пустой JQL дизейблит Create".
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import allure
import pytest
from faker import Faker
from playwright.sync_api import expect

from pages.components.notification import (
    FLAG_KIND_ERROR,
    FLAG_KIND_SUCCESS,
    REMINDER_CREATED_SUCCESS_TEXT,
    Notification,
)
from pages.components.reminder_modal import (
    INVALID_URL_ERROR_TEXT,
    LINK_URL_PLACEHOLDER_TEXT,
    LINKED_TYPE_LINK,
    LINKED_TYPE_WORK_ITEM,
    ReminderModal,
)
from pages.issue_page import IssuePage

pytestmark = [
    pytest.mark.ui,
    pytest.mark.creation_form,
    pytest.mark.issue_panel,
]

_faker = Faker()
MAX_LINK_LENGTH = 4096

# Невалидный JQL из колонки Input кейса REMCL-1062 (дословно).
INVALID_JQL_QUERY = "reporter ="
# tolerant-проверка, что запрос попал в редактор: \s переживает неразрывный
# пробел, который редактор может подставить вместо обычного.
INVALID_JQL_PRESENT_RE = re.compile(r"reporter\s*=")

# Таймаут ожидания смены состояния Create после закрытия попапа Condition.
# Валидация JQL асинхронная (возможно, с серверным запросом) — 10с с запасом,
# вместо одноразового снимка состояния.
CREATE_STATE_TIMEOUT_MS = 10_000


def _unique_message(tag: str) -> str:
    return (
        f"{_faker.sentence(nb_words=4).rstrip('.')} "
        f"[autotest-{tag} {datetime.now(timezone.utc).isoformat(timespec='seconds')}]"
    )


def _fill_required_message(modal: ReminderModal, tag: str) -> str:
    """Заполняет Message (при типе Link обязателен) и возвращает текст."""
    text = _unique_message(tag)
    with allure.step(f"Заполнить обязательный при типе Link Message: {text!r}"):
        modal.fill_message(text)
    return text


def _skip_if_condition_unavailable(modal: ReminderModal) -> None:
    if not modal.is_condition_enabled():
        pytest.skip(
            "Кнопка Condition неактивна на этом инстансе (признак отсутствия "
            f"Advanced-подписки: data-testid={modal.condition_wrapper_testid()!r}). "
            "Кейс требует инстанс с активной Advanced-подпиской."
        )


def _attach_condition_diagnostics(modal: ReminderModal) -> None:
    """Прикладывает реальное состояние попапа Condition/JQL к Allure."""
    allure.attach(
        modal.condition_popup_html(),
        name="HTML слоёв-порталов (iframe + top)",
        attachment_type=allure.attachment_type.HTML,
    )
    allure.attach(
        json.dumps(modal.form_field_placeholders(), ensure_ascii=False, indent=2),
        name="Placeholder'ы всех полей iframe",
        attachment_type=allure.attachment_type.JSON,
    )
    allure.attach(
        f"condition_open={modal.is_condition_open()}\n"
        f"dialog_visible={modal.is_condition_dialog_visible()}\n"
        f"jql_visible={modal.is_jql_input_visible()}\n"
        f"jql_value={modal.get_jql_value()!r}\n"
        f"jql_editor_html={modal.jql_editor_html()!r}\n"
        f"jql_placeholder={modal.get_jql_placeholder()!r}\n"
        f"jql_hint={modal.jql_hint_text()!r}\n"
        f"jql_note={modal.jql_note_text()!r}\n"
        f"jql_validation={modal.jql_validation_message()!r}\n"
        f"condition_class={modal.condition_button_class()!r}\n"
        f"condition_color={modal.condition_button_color()!r}\n"
        f"create_enabled={modal.is_create_enabled()}",
        name="Состояние Condition/JQL/Create",
        attachment_type=allure.attachment_type.TEXT,
    )


@allure.feature("Creation Form")
@allure.story("Linked item")
class TestLinkedItemBlock:
    """Наличие блока, тип привязки, предзаполнение задачи."""

    @allure.title(
        "REMCL-1013/1014: блок Linked item содержит селект типа привязки "
        "и селект задачи"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1013", "REMCL-1014")
    def test_linked_item_block_has_type_and_work_item_selectors(
        self, reminder_modal: ReminderModal
    ) -> None:
        with allure.step("Блок Linked item с лейблом и селектом типа виден"):
            assert reminder_modal.is_linked_item_block_visible(), (
                "Блок Linked item не найден"
            )
        with allure.step("Селект задачи виден рядом"):
            assert reminder_modal.is_work_item_visible(), (
                "Поле задачи (data-testid=reminder-work-item) не найдено"
            )

    @allure.title(
        "REMCL-1045: тип привязки по умолчанию Work item, в дропдауне "
        "есть Work item и Link"
    )
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("REMCL-1045")
    @pytest.mark.functional
    def test_linked_type_default_is_work_item_and_offers_link(
        self, reminder_modal: ReminderModal
    ) -> None:
        with allure.step("Дефолтное значение типа привязки — Work item"):
            expect(reminder_modal._linked_type_combobox).to_have_value(
                LINKED_TYPE_WORK_ITEM
            )
        with allure.step("Открыть дропдаун типа привязки"):
            reminder_modal.open_linked_type_dropdown()
            assert reminder_modal.is_linked_type_dropdown_open(), (
                "Дропдаун типа привязки не открылся"
            )
        with allure.step("В списке есть Work item и Link"):
            for option in (LINKED_TYPE_WORK_ITEM, LINKED_TYPE_LINK):
                assert reminder_modal.is_linked_type_option_visible(option), (
                    f"Опция '{option}' не найдена в дропдауне типа привязки"
                )
        with allure.step("Закрыть дропдаун"):
            reminder_modal.page.keyboard.press("Escape")

    @allure.title(
        "REMCL-1051: при создании из задачи поле задачи предзаполнено "
        "в формате {issuekey} - {summary}"
    )
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("REMCL-1051")
    @pytest.mark.functional
    def test_work_item_prefilled_with_issue_key_and_summary(
        self, reminder_modal: ReminderModal, issue_key: str
    ) -> None:
        with allure.step("Получить значение поля задачи"):
            value = reminder_modal.get_work_item_value()
            assert value is not None, "Поле задачи не отображается"
        with allure.step(f"Формат '{issue_key} - <summary>'"):
            pattern = re.compile(rf"^{re.escape(issue_key)}\s+-\s+\S.*$")
            assert pattern.match(value), (
                f"Значение {value!r} не соответствует формату "
                f"'{issue_key} - <summary>'"
            )

    @allure.title(
        "REMCL-1051 (страж): поле задачи заблокировано при создании из задачи"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1051")
    def test_work_item_field_is_locked_when_created_from_issue_page(
        self, reminder_modal: ReminderModal
    ) -> None:
        """
        Делает skip-причины отложенных кейсов ПРОВЕРЯЕМЫМИ: когда поле станет
        редактируемым, тест упадёт и просигналит пересмотреть их.
        """
        with allure.step("Поле задачи видно"):
            assert reminder_modal.is_work_item_visible(), "Поле задачи не найдено"
        with allure.step("Поле задачи заблокировано (disabled)"):
            assert not reminder_modal.is_work_item_enabled(), (
                "Поле задачи стало РЕДАКТИРУЕМЫМ — пересмотрите отложенные "
                "кейсы REMCL-1046/1053/1054/1055"
            )


@allure.feature("Creation Form")
@allure.story("Linked item — Link")
class TestLinkedItemLink:
    """Поведение типа привязки Link (Message обязателен, успех — по флагу)."""

    @allure.title("REMCL-1056: при типе Link появляется поле URL с плейсхолдером")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1056")
    def test_link_type_shows_url_input_with_placeholder(
        self, reminder_modal: ReminderModal
    ) -> None:
        with allure.step("Переключить тип привязки на Link"):
            reminder_modal.select_linked_type(LINKED_TYPE_LINK)
        with allure.step("Поле ввода URL появилось"):
            assert reminder_modal.is_link_url_input_visible(), (
                "Поле ввода URL не появилось при выборе типа Link"
            )
        with allure.step("Плейсхолдер совпадает с текстом кейса"):
            placeholder = reminder_modal.get_link_url_placeholder()
            assert placeholder == LINK_URL_PLACEHOLDER_TEXT, (
                f"Плейсхолдер {placeholder!r} != {LINK_URL_PLACEHOLDER_TEXT!r}"
            )

    @allure.title(
        "REMCL-1058: поле URL принимает текст до 4096 символов "
        "(схема из латинских букв + двоеточие)"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1058")
    @pytest.mark.validation
    @pytest.mark.parametrize(
        ("payload", "length"),
        [
            pytest.param("https://example.com/reminder", None, id="https-url"),
            pytest.param("mailto:someone@example.com", None, id="custom-scheme"),
            pytest.param("x:", MAX_LINK_LENGTH, id="max-length-4096"),
        ],
    )
    def test_link_url_accepts_text_up_to_4096_chars(
        self, reminder_modal: ReminderModal, payload: str, length: int | None
    ) -> None:
        """
        ЧАСТИЧНО ПОКРЫТ: приём валидных строк ≤4096 проверен; поведение при
        вводе БОЛЬШЕ 4096 не assert'ится — механизм ограничения не снят.
        """
        text = payload
        if length is not None:
            text = payload + "a" * (length - len(payload))
            assert len(text) == length

        with allure.step("Переключить тип привязки на Link"):
            reminder_modal.select_linked_type(LINKED_TYPE_LINK)
        with allure.step(f"Ввести значение длиной {len(text)} символов"):
            reminder_modal.fill_link_url(text)
        with allure.step("Значение в поле совпадает с введённым"):
            actual = reminder_modal.get_link_url_value()
            assert actual == text, (
                f"Длина значения в поле {len(actual or '')}, ожидалось {len(text)}"
            )

    @allure.title(
        "REMCL-2717: ссылка без схемы вызывает уведомление Error "
        "с текстом Invalid URL"
    )
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("REMCL-2717")
    @pytest.mark.validation
    @pytest.mark.negative
    def test_link_without_scheme_shows_invalid_url_error(
        self, issue_page: IssuePage, issue_key: str
    ) -> None:
        """
        REMCL-2717. Ошибка — AtlasKit Flag в TOP-документе (~5с), модалка при
        ошибке не закрывается → submit(settle_timeout_ms=500). Message при
        типе Link обязателен. Заголовок и тело флага проверяются раздельно.
        """
        notification = Notification(issue_page.page)

        with allure.step("Открыть задачу и форму создания ремайндера"):
            issue_page.open(issue_key)
            assert issue_page.has_reminder_section(), (
                "Секция Reminder не найдена на странице задачи"
            )
            issue_page.reminder_panel.expand()
            modal = issue_page.reminder_panel.open_create_modal()
            assert modal.is_open(), "Предусловие не выполнено: модалка не открыта"

        with allure.step("Переключить тип привязки на Link"):
            modal.select_linked_type(LINKED_TYPE_LINK)
            assert modal.is_link_url_input_visible(), "Поле URL не появилось"

        with allure.step("Ввести ссылку без схемы: example.com"):
            modal.fill_link_url("example.com")

        _fill_required_message(modal, "2717")

        with allure.step("Предусловие: кнопка Create активна"):
            expect(modal.create_button_locator()).to_be_enabled()

        with allure.step("Нажать Create (короткое ожидание закрытия модалки)"):
            modal.submit(settle_timeout_ms=500)

        with allure.step("Появилось уведомление об ошибке"):
            expect(notification.locator(FLAG_KIND_ERROR)).to_be_visible()

        with allure.step("Заголовок уведомления = 'Error'"):
            expect(notification.title_locator(FLAG_KIND_ERROR)).to_have_text(
                FLAG_KIND_ERROR
            )

        with allure.step("Текст уведомления дословно совпадает с ожидаемым"):
            expect(notification.body_locator(FLAG_KIND_ERROR)).to_have_text(
                INVALID_URL_ERROR_TEXT
            )

        with allure.step("Тип уведомления определяется по иконке как Error"):
            assert notification.kind(FLAG_KIND_ERROR) == FLAG_KIND_ERROR

        with allure.step("Модалка осталась открытой (ремайндер не создан)"):
            assert modal.is_open(), (
                "Модалка закрылась при невалидном URL — ремайндер мог "
                "сохраниться, это противоречит кейсу"
            )

        with allure.step("Закрыть уведомление (best-effort, не ассерт)"):
            notification.dismiss(FLAG_KIND_ERROR)

    @allure.title(
        "REMCL-1059: ремайндер с пустой ссылкой сохраняется "
        "(подтверждается Success-уведомлением)"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1059")
    @pytest.mark.functional
    def test_empty_link_can_be_saved(
        self, issue_page: IssuePage, issue_key: str
    ) -> None:
        """
        REMCL-1059. Link-ремайндер не виден в секции задачи → успех
        подтверждаем Success-флагом.

        ЧЕСТНАЯ ОГОВОРКА: подтверждается ФАКТ сохранения, но не то, что URL
        сохранился именно пустым — Page Object для My Reminders/редактирования
        пока нет.
        """
        notification = Notification(issue_page.page)

        with allure.step("Открыть задачу и форму создания ремайндера"):
            issue_page.open(issue_key)
            assert issue_page.has_reminder_section(), (
                "Секция Reminder не найдена на странице задачи"
            )
            issue_page.reminder_panel.expand()
            modal = issue_page.reminder_panel.open_create_modal()
            assert modal.is_open(), "Предусловие не выполнено: модалка не открыта"

        with allure.step("Тип Link, URL оставить пустым"):
            modal.select_linked_type(LINKED_TYPE_LINK)
            assert modal.is_link_url_input_visible(), "Поле URL не появилось"
            assert modal.get_link_url_value() == "", (
                "Поле URL должно быть пустым по умолчанию"
            )

        _fill_required_message(modal, "1059")

        with allure.step("Предусловие: кнопка Create активна"):
            expect(modal.create_button_locator()).to_be_enabled()

        with allure.step("Нажать Create"):
            modal.submit()

        with allure.step("Появилось уведомление об успешном создании"):
            expect(notification.locator(FLAG_KIND_SUCCESS)).to_be_visible()

        with allure.step("Заголовок уведомления = 'Success'"):
            expect(notification.title_locator(FLAG_KIND_SUCCESS)).to_have_text(
                FLAG_KIND_SUCCESS
            )

        with allure.step(f"Текст уведомления = {REMINDER_CREATED_SUCCESS_TEXT!r}"):
            expect(notification.body_locator(FLAG_KIND_SUCCESS)).to_have_text(
                REMINDER_CREATED_SUCCESS_TEXT
            )

        with allure.step("Форма создания закрылась (ремайндер сохранён)"):
            assert modal.is_closed(), (
                "Модалка не закрылась после успешного сохранения"
            )

        with allure.step("Закрыть уведомление (best-effort, не ассерт)"):
            notification.dismiss(FLAG_KIND_SUCCESS)


@allure.feature("Creation Form")
@allure.story("Linked item — Condition")
class TestLinkedItemCondition:
    """Кнопка Condition и поле JQL (REMCL-1060/1061/1062)."""

    @allure.title("REMCL-1060: кнопка Condition присутствует в блоке Linked item")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1060")
    def test_condition_button_is_present(
        self, reminder_modal: ReminderModal
    ) -> None:
        with allure.step("Кнопка Condition видна"):
            assert reminder_modal.is_condition_visible(), (
                "Кнопка Condition не найдена в блоке Linked item"
            )
        with allure.step("Зафиксировать состояние кнопки в отчёт"):
            allure.attach(
                f"enabled={reminder_modal.is_condition_enabled()}\n"
                f"data-testid={reminder_modal.condition_wrapper_testid()!r}\n"
                f"class={reminder_modal.condition_button_class()!r}\n"
                f"color={reminder_modal.condition_button_color()!r}",
                name="Состояние кнопки Condition",
                attachment_type=allure.attachment_type.TEXT,
            )

    @allure.title(
        "REMCL-1060: Condition disabled + tooltip, когда ремайндер "
        "не связан с задачей"
    )
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("REMCL-1060")
    def test_condition_disabled_when_not_linked_to_work_item(
        self, reminder_modal: ReminderModal
    ) -> None:
        with allure.step("Переключить тип привязки на Link"):
            reminder_modal.select_linked_type(LINKED_TYPE_LINK)
        with allure.step("Кнопка Condition НЕ активна"):
            assert not reminder_modal.is_condition_enabled(), (
                "Condition должна быть disabled без привязки к задаче"
            )
        with allure.step("Тултип объясняет причину (нет связи с задачей)"):
            tooltip = reminder_modal.get_condition_tooltip_text()
            assert tooltip is not None, "Тултип кнопки Condition не найден"
            allure.attach(
                tooltip,
                name="Тултип Condition (без привязки)",
                attachment_type=allure.attachment_type.TEXT,
            )
            lowered = tooltip.lower()
            assert "work item" in lowered and "only available" in lowered, (
                f"Тултип не про отсутствие привязки к задаче: {tooltip!r}"
            )

    @allure.title("REMCL-1060: Condition disabled + tooltip про Advanced-подписку")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1060")
    def test_condition_disabled_without_advanced_subscription(
        self, reminder_modal: ReminderModal
    ) -> None:
        with allure.step("Тип привязки — Work item"):
            expect(reminder_modal._linked_type_combobox).to_have_value(
                LINKED_TYPE_WORK_ITEM
            )
        with allure.step("Проверить, что ветка воспроизводима"):
            if reminder_modal.is_condition_enabled():
                pytest.skip(
                    "Condition активна при привязке к задаче — Advanced есть, "
                    "ветка 'нет подписки' не воспроизводится."
                )
        with allure.step("Тултип объясняет отсутствие Advanced-подписки"):
            tooltip = reminder_modal.get_condition_tooltip_text()
            assert tooltip is not None, "Тултип кнопки Condition не найден"
            allure.attach(
                tooltip,
                name="Тултип Condition (нет Advanced)",
                attachment_type=allure.attachment_type.TEXT,
            )
            assert "advanced subscription" in tooltip.lower(), (
                f"Тултип не про Advanced-подписку: {tooltip!r}"
            )

    @allure.title(
        "REMCL-1061: клик по Condition открывает необязательное поле JQL"
    )
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("REMCL-1061")
    @pytest.mark.functional
    def test_condition_opens_optional_jql_field(
        self, reminder_modal: ReminderModal
    ) -> None:
        """
        REMCL-1061, рабочая часть: попап открывается, JQL-редактор виден и
        редактируем, поле НЕобязательное (пустой JQL не блокирует Create).
        """
        _skip_if_condition_unavailable(reminder_modal)

        with allure.step("Кликнуть Condition"):
            reminder_modal.open_condition()

        with allure.step("Попап Condition открылся"):
            if not reminder_modal.is_condition_dialog_visible():
                _attach_condition_diagnostics(reminder_modal)
                pytest.fail(
                    "Попап Condition (role=dialog aria-label='Condition') не "
                    "найден — см. вложения с реальной разметкой порталов."
                )

        with allure.step("Поле ввода JQL открылось и редактируемо"):
            if not reminder_modal.is_jql_input_visible():
                _attach_condition_diagnostics(reminder_modal)
                pytest.fail(
                    "JQL-редактор (data-testid='jql-editor-input') не найден — "
                    "см. вложения."
                )
            expect(reminder_modal.jql_input_locator()).to_be_editable()

        with allure.step("Поле необязательное: пустой JQL не блокирует Create"):
            reminder_modal.clear_jql()
            reminder_modal.close_condition()
            expect(reminder_modal.create_button_locator()).to_be_enabled(
                timeout=CREATE_STATE_TIMEOUT_MS
            )

    @allure.title("REMCL-1062: невалидный JQL деактивирует кнопку Create")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("REMCL-1062")
    @pytest.mark.validation
    @pytest.mark.negative
    def test_invalid_jql_disables_create(
        self, reminder_modal: ReminderModal
    ) -> None:
        """
        REMCL-1062 — ЧАСТИЧНО ПОКРЫТ.

        Шаги кейса: открыть форму (Create активна) → открыть Condition →
        ввести невалидный запрос "reporter =" и ЗАКРЫТЬ поле → кнопка
        Condition окрашена в красный, Create НЕактивна.

        ИСПРАВЛЕНО (2026-11-25, находка 5 в докстринге модуля). Порядок шагов
        был правильным и раньше, но проверка не видела дизейбл по трём
        причинам — все три устранены:
          a) состояние Create читалось одноразовым is_create_enabled() сразу
             после закрытия попапа, а валидация JQL асинхронная → теперь
             expect(create_button_locator()).to_be_disabled() с авто-retry;
          b) close_condition() жал Escape первым и мог отменять черновик →
             теперь закрытие кликом ВНЕ попапа;
          c) fill_jql() вставлял текст без клавиатурных событий → теперь
             press_sequentially().
        Плюс добавлен промежуточный ассерт: запрос ДОЛЖЕН быть в редакторе
        ещё ДО закрытия попапа. Без него тест мог молча проверять "пустой JQL
        дизейблит Create" и падать по неверной причине.

        НЕ assert'ится: "кнопка Condition окрашена в красный" — стабильного
        маркера нет; class/цвет/скриншот прикладываются к отчёту.
        """
        _skip_if_condition_unavailable(reminder_modal)

        with allure.step("Предусловие: кнопка Create активна"):
            expect(reminder_modal.create_button_locator()).to_be_enabled()

        with allure.step("Открыть поле Condition"):
            reminder_modal.open_condition()
            if not reminder_modal.is_jql_input_visible():
                _attach_condition_diagnostics(reminder_modal)
                pytest.fail("JQL-редактор не найден — см. вложения.")

        with allure.step(f"Ввести невалидный запрос {INVALID_JQL_QUERY!r}"):
            reminder_modal.fill_jql(INVALID_JQL_QUERY)

        with allure.step(
            "Запрос действительно попал в редактор (проверка ДО закрытия попапа)"
        ):
            allure.attach(
                f"jql_value={reminder_modal.get_jql_value()!r}\n"
                f"jql_editor_html={reminder_modal.jql_editor_html()!r}\n"
                f"jql_validation={reminder_modal.jql_validation_message()!r}",
                name="Состояние JQL сразу после ввода (попап ещё открыт)",
                attachment_type=allure.attachment_type.TEXT,
            )
            try:
                expect(reminder_modal.jql_input_locator()).to_contain_text(
                    INVALID_JQL_PRESENT_RE, timeout=5_000
                )
            except AssertionError:
                _attach_condition_diagnostics(reminder_modal)
                raise AssertionError(
                    f"Невалидный запрос {INVALID_JQL_QUERY!r} НЕ попал в "
                    "JQL-редактор — дальше проверять состояние Create "
                    "бессмысленно (пустой JQL ничего не дизейблит). Смотри "
                    "вложение 'Состояние JQL сразу после ввода': jql_value и "
                    "jql_editor_html покажут, что реально оказалось в "
                    "редакторе (пусто / текст / токены-пиллы)."
                )

        with allure.step("Закрыть поле Condition кликом вне попапа"):
            reminder_modal.close_condition()
            assert not reminder_modal.is_condition_open(), (
                "Попап Condition не закрылся — состояние Create проверяется "
                "только после закрытия, как требует кейс"
            )

        with allure.step("Кнопка Create стала НЕактивной"):
            try:
                expect(reminder_modal.create_button_locator()).to_be_disabled(
                    timeout=CREATE_STATE_TIMEOUT_MS
                )
            except AssertionError:
                _attach_condition_diagnostics(reminder_modal)
                raise AssertionError(
                    "Create осталась активной после ввода невалидного JQL и "
                    "закрытия попапа (ждали "
                    f"{CREATE_STATE_TIMEOUT_MS} мс с авто-retry). Смотри "
                    "вложения: сохранился ли запрос после закрытия "
                    "(jql_value/jql_editor_html) и что вернул валидатор "
                    "(jql_validation)."
                )

        with allure.step("Диагностика 'красной' кнопки Condition (не ассерт)"):
            allure.attach(
                f"data-testid={reminder_modal.condition_wrapper_testid()!r}\n"
                f"class={reminder_modal.condition_button_class()!r}\n"
                f"color={reminder_modal.condition_button_color()!r}",
                name="Признаки ошибки на кнопке Condition",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                reminder_modal._condition_button.screenshot(),
                name="Кнопка Condition после невалидного JQL",
                attachment_type=allure.attachment_type.PNG,
            )


# =============================================================================
# Отложено по решению пользователя (2026-11-25)
# =============================================================================

_DEFERRED_REASON = (
    "ОТЛОЖЕНО по решению пользователя (2026-11-25). При создании ремайндера "
    "кнопкой Create из секции Reminder НА СТРАНИЦЕ ЗАДАЧИ поле задачи "
    "заблокировано (подтверждено разметкой и закреплено тестом "
    "test_work_item_field_is_locked_when_created_from_issue_page). Кейс "
    "будет реализован вместе с открытием формы НЕ из задачи (My reminders, "
    "хоткей R, другие кнопки) — там поле задачи активно."
)


@pytest.mark.skip(reason=f"REMCL-1046: {_DEFERRED_REASON}")
@allure.tag("REMCL-1046")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.creation_form
def test_work_item_dropdown_lists_available_issues() -> None:
    """REMCL-1046 — см. skip."""


@pytest.mark.skip(reason=f"REMCL-1053: {_DEFERRED_REASON}")
@allure.tag("REMCL-1053")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.creation_form
def test_work_item_dropdown_shows_at_most_20_issues() -> None:
    """REMCL-1053 — см. skip."""


@pytest.mark.skip(reason=f"REMCL-1054: {_DEFERRED_REASON}")
@allure.tag("REMCL-1054")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.creation_form
def test_work_item_search_not_found_shows_error() -> None:
    """REMCL-1054 — см. skip."""


@pytest.mark.skip(reason=f"REMCL-1055: {_DEFERRED_REASON}")
@allure.tag("REMCL-1055")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.creation_form
def test_create_disabled_when_work_item_empty() -> None:
    """REMCL-1055 — см. skip."""


@pytest.mark.skip(
    reason=(
        "REMCL-1057: нужны три точки входа (хоткей R, My Reminders, Create на "
        "странице задачи); реализована только третья. Отложено вместе с "
        "REMCL-1046/1053/1054/1055 (решение пользователя 2026-11-25)."
    )
)
@allure.tag("REMCL-1057")
@pytest.mark.ui
@pytest.mark.creation_form
def test_linked_item_available_from_all_entry_points() -> None:
    """REMCL-1057 — см. skip."""