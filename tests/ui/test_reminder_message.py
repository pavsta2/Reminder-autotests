"""
Тесты на поле Message формы создания ремайндера (модалка "New reminder").

Источник test-кейсов: RTM-экспорт "rtm-issues-export_22.zip" (38 кейсов,
компонент "5.0. Creation form", RTM Node "Creation - Message (v.2.X.X)").
Page Object поля — pages/components/message_editor.py (MessageEditor,
доступен как ReminderModal.message). Разметка поля (Quill) подтверждена
DOM-снимком реальной формы 2026-11-20, см. докстринг message_editor.py.

Реализовано в этом файле (раунд 1, 2026-11-20):
    UI:          REMCL-1255, 1256, 1257 (+1030 дубль), 1258, 1259, 1261
                 (частично), 1263, 1264
    Ввод/BVA:    REMCL-1031, 1268, 1269, 1032, 1270, 1271, 1273 (частично)
    Формат:      REMCL-1276, 1277, 1278, 1279, 1280, 1281, 1282
    Доставка:    REMCL-1283 (@pytest.mark.email)
Вне этого файла:
    REMCL-1275 — дубль REMCL-1038: вторым тегом на test_create_button_
                 saves_reminder в tests/ui/test_reminder_create_cancel.py.
Ждут раунда 2 разведки локаторов (в коде пока НЕТ, ни тестом, ни skip):
    REMCL-1265, 1266, 1267, 1286, 1274, 1285, 1262 — зависимость от Linked
                 item (опции дропдауна Linked item, отображение
                 обязательности и текст ошибки ещё не сняты);
    REMCL-1287 — текст Message в форме РЕДАКТИРОВАНИЯ созданного
                 ремайндера (по уточнению пользователя), нужен локатор
                 открытия редактирования из секции Reminder;
    REMCL-1272 — многострочный текст: Enter сабмитит форму, способ
                 переноса строки не подтверждён.
Skip по решению/с причиной — см. конец файла: REMCL-1260, REMCL-1284.

Все тесты, которые НЕ сохраняют ремайндер, закрывают модалку Cancel'ом в
teardown фикстуры message_modal. Тесты, которые сохраняют, оставляют на
инстансе по одному ремайндеру с уникальным текстом (метода delete в
репозитории пока нет — тот же trade-off, что в test_reminder_create_
cancel.py).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import datetime, timezone

import allure
import pytest
from faker import Faker
from playwright.sync_api import Dialog, Page, expect

from config.settings import Settings
from pages.components.message_editor import MESSAGE_LABEL_RE
from pages.components.reminder_modal import ReminderModal
from pages.issue_page import IssuePage
from utils.mail_client import MailClient
from utils.time_helpers import (
    MOSCOW_TZ,
    PLUGIN_SCHEDULE_POLL_BUFFER_S,
    round_up_to_next_five_minutes,
)

_faker = Faker()

MAX_MESSAGE_LENGTH = 255

# Класс, который Quill ставит пустому редактору (= placeholder виден).
_QL_BLANK_RE = re.compile(r"\bql-blank\b")

# Ожидаемый placeholder — ДОСЛОВНО из REMCL-1257/REMCL-1030.
# ВНИМАНИЕ: на реальной форме (DOM-снимок 2026-11-20) атрибут
# data-placeholder = "A short reminder message (max. 255 symbols)" — БЕЗ
# "optional, ". Тест сознательно проверяет требование из кейса, а не
# фактический текст: расхождение = либо баг, либо устаревший кейс; решение
# за автором кейсов (вопрос задан в чате 2026-11-20).
EXPECTED_PLACEHOLDER = "A short reminder message (optional, max. 255 symbols)"

# Кнопки, которые требуются кейсами на форматирование (REMCL-1276..1282).
# Size picker и Blockquote в toolbar тоже есть, но ни одним кейсом не
# описаны — в REMCL-1259 не assert'ятся.
REQUIRED_TOOLBAR_BUTTONS = (
    "bold",
    "italic",
    "underline",
    "strike",
    "ordered_list",
    "bullet_list",
    "link",
)


def _unique_suffix(tag: str) -> str:
    # timezone.utc вместо datetime.UTC — см. комментарий в
    # test_reminder_create_cancel.py (переносимость на Python < 3.11).
    return (
        f"[autotest-{tag} {datetime.now(timezone.utc).isoformat(timespec='seconds')}]"
    )


@pytest.fixture
def message_modal(issue_page: IssuePage, issue_key: str) -> Iterator[ReminderModal]:
    """Открывает задачу и модалку "New reminder"; в teardown закрывает Cancel."""
    issue_page.open(issue_key)
    assert (
        issue_page.has_reminder_section()
    ), "Секция Reminder не найдена на странице задачи"
    issue_page.reminder_panel.expand()
    modal = issue_page.reminder_panel.open_create_modal()
    yield modal
    try:
        if modal.is_open(timeout_ms=1_000):
            modal.close()
    except Exception:
        # Тест мог уже сам закрыть модалку (submit) — не мешаем отчёту.
        pass


@pytest.fixture
def js_dialogs(page: Page) -> list[str]:
    """
    Собирает тексты всех JS-диалогов (alert/confirm/prompt) со страницы,
    включая iframe-ы, и сразу их закрывает — для XSS-проверок (REMCL-1273).
    Playwright шлёт событие "dialog" на Page для любого фрейма страницы.
    """
    messages: list[str] = []

    def _on_dialog(dialog: Dialog) -> None:
        messages.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", _on_dialog)
    return messages


def _save_and_check_in_panel(
    issue_page: IssuePage, modal: ReminderModal, expected_text: str
) -> None:
    """Общий хвост "сохранить и найти текст в секции Reminder"."""
    with allure.step("Нажать Create"):
        modal.submit()
    with allure.step("Проверить, что ремайндер с этим текстом есть в секции Reminder"):
        assert issue_page.reminder_panel.has_reminder_with_text(
            expected_text
        ), f"Ремайндер с текстом {expected_text!r} не найден в секции Reminder"


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------


@allure.title("Поле Message отображается с label 'Message'")
@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Message")
@allure.tag("REMCL-1255")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.message
def test_message_field_has_label(message_modal: ReminderModal) -> None:
    """
    REMCL-1255. Кроме видимости лейбла, проверяется, что он программно
    связан с редактором (accessible name редактора = "Message" через
    aria-labelledby) — т.е. это лейбл именно этого поля, а не просто текст
    рядом.
    """
    message = message_modal.message
    with allure.step("Лейбл 'Message' виден над полем"):
        expect(message.label_locator()).to_be_visible()
        expect(message.label_locator()).to_have_text(MESSAGE_LABEL_RE)
    with allure.step("Лейбл связан с редактором (accessible name)"):
        expect(message.editor_locator()).to_have_accessible_name(MESSAGE_LABEL_RE)


@allure.title("Поле Message отображается как WYSIWYG text field")
@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Message")
@allure.tag("REMCL-1256")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.message
def test_message_field_is_wysiwyg_editor(message_modal: ReminderModal) -> None:
    """
    REMCL-1256. "WYSIWYG" проверяется как: редактируемое многострочное
    rich-text поле (contenteditable, role=textbox, aria-multiline) с
    видимым toolbar форматирования.
    """
    editor = message_modal.message.editor_locator()
    with allure.step("Поле — редактируемый rich-text (contenteditable) textbox"):
        expect(editor).to_be_visible()
        expect(editor).to_be_editable()
        expect(editor).to_have_attribute("contenteditable", "true")
        expect(editor).to_have_attribute("aria-multiline", "true")
    with allure.step("У поля есть toolbar форматирования"):
        expect(message_modal.message.toolbar_locator()).to_be_visible()


@allure.title("Placeholder отображается в пустом поле Message")
@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Message")
@allure.tag("REMCL-1257")
@allure.tag("REMCL-1030")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.message
def test_message_placeholder_shown_in_empty_field(message_modal: ReminderModal) -> None:
    """
    REMCL-1257 (+ REMCL-1030 — дубль: тот же placeholder, QA Label тот же
    "Ui", отдельный тест не пишем — второй тег).

    Placeholder у Quill — CSS ::before c content: attr(data-placeholder),
    который показывается, пока у редактора есть класс ql-blank (см.
    докстринг message_editor.py). Поэтому "виден" = ql-blank + текст
    атрибута.

    ОЖИДАЕМО КРАСНЫЙ на момент написания (2026-11-20): фактический текст
    без "optional, " — см. EXPECTED_PLACEHOLDER выше.
    """
    message = message_modal.message
    with allure.step("Поле пустое (Quill-класс ql-blank — placeholder виден)"):
        assert message.is_blank(), "Поле Message не пустое при открытии формы"
    with allure.step(f"Текст placeholder = {EXPECTED_PLACEHOLDER!r}"):
        expect(message.editor_locator()).to_have_attribute(
            "data-placeholder", EXPECTED_PLACEHOLDER
        )


@allure.title("Placeholder скрывается после ввода текста в поле Message")
@allure.severity(allure.severity_level.MINOR)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Message")
@allure.tag("REMCL-1264")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.message
def test_message_placeholder_hidden_after_input(message_modal: ReminderModal) -> None:
    """REMCL-1264. Плюс обратная проверка: после очистки placeholder возвращается."""
    message = message_modal.message
    editor = message.editor_locator()
    with allure.step("До ввода placeholder виден"):
        expect(editor).to_have_class(_QL_BLANK_RE)
    with allure.step("Ввести текст — placeholder скрыт"):
        message.type_text("x")
        expect(editor).not_to_have_class(_QL_BLANK_RE)
    with allure.step("Очистить поле — placeholder снова виден"):
        message.clear()
        expect(editor).to_have_class(_QL_BLANK_RE)


@allure.title("Toolbar форматирования отображается над полем ввода Message")
@allure.severity(allure.severity_level.MINOR)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Message")
@allure.tag("REMCL-1258")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.message
def test_message_toolbar_is_above_input(message_modal: ReminderModal) -> None:
    message = message_modal.message
    with allure.step("Toolbar виден"):
        expect(message.toolbar_locator()).to_be_visible()
    with allure.step("Нижний край toolbar не ниже верхнего края области ввода"):
        toolbar, container = message.toolbar_box(), message.container_box()
        assert toolbar and container, "Не удалось получить размеры toolbar/поля"
        assert (
            toolbar["y"] + toolbar["height"] <= container["y"] + 1
        ), f"Toolbar не над полем ввода: toolbar={toolbar}, field={container}"


@allure.title("Кнопки форматирования отображаются в toolbar поля Message")
@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Message")
@allure.tag("REMCL-1259")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.message
def test_message_toolbar_has_formatting_buttons(message_modal: ReminderModal) -> None:
    """
    REMCL-1259. Сам кейс не перечисляет кнопки — список взят из кейсов на
    форматирование (REMCL-1276..1282), см. REQUIRED_TOOLBAR_BUTTONS. Все
    кнопки проверяются в одном тесте (одна идея — "кнопки есть"), но
    недостающие собираются в список, чтобы одна не маскировала остальные.
    """
    message = message_modal.message
    with allure.step(f"В toolbar видны кнопки: {', '.join(REQUIRED_TOOLBAR_BUTTONS)}"):
        missing = [
            name
            for name in REQUIRED_TOOLBAR_BUTTONS
            if not message.format_button(name).is_visible()
        ]
        assert not missing, f"В toolbar не видны кнопки: {missing}"


@allure.title("Поле Message получает фокус при переходе Tab")
@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Message")
@allure.tag("REMCL-1261")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.message
def test_message_field_reachable_by_tab(message_modal: ReminderModal) -> None:
    """
    REMCL-1261 — ЧАСТИЧНО ПОКРЫТ: проверяется, что поле достижимо с
    клавиатуры и получает фокус. Визуальный "focus state" (рамка/тень) НЕ
    assert'ится — как именно он выглядит, ещё не снято с реальной формы
    (раунд 2 разведки); вместо assert'а прикладывается скриншот поля в
    фокусе.

    Старт — поле Recipients: клик открывает дропдаун, Escape закрывает
    только его (подтверждено REMCL-1085/1086), фокус остаётся в Recipients.
    """
    message = message_modal.message
    with allure.step("Поставить фокус в поле Recipients (выше Message)"):
        message_modal.open_dropdown()
        message_modal.page.keyboard.press("Escape")
    with allure.step("Нажимать Tab, пока фокус не попадёт в Message"):
        presses = message.focus_via_tab()
        assert presses is not None, "Поле Message не получило фокус по Tab"
        allure.attach(
            str(presses),
            name="Нажатий Tab",
            attachment_type=allure.attachment_type.TEXT,
        )
    with allure.step("Скриншот поля в фокусе (focus state — визуально)"):
        allure.attach(
            message.field_screenshot(),
            name="Message в фокусе",
            attachment_type=allure.attachment_type.PNG,
        )


@allure.title("Поле Message не выходит за границы модального окна")
@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Message")
@allure.tag("REMCL-1263")
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.message
@pytest.mark.parametrize(
    "content",
    [
        pytest.param("W" * MAX_MESSAGE_LENGTH, id="one-long-word"),
        pytest.param(
            ("lorem ipsum " * 30)[:MAX_MESSAGE_LENGTH], id="long-text-with-spaces"
        ),
    ],
)
def test_message_field_stays_inside_modal(
    message_modal: ReminderModal, content: str
) -> None:
    """
    REMCL-1263. Худшие случаи — максимальная длина одним словом без
    пробелов (риск горизонтального переполнения) и обычным текстом
    (поле растёт по высоте).
    """
    message = message_modal.message
    with allure.step("Ввести текст максимальной длины"):
        message.fill(content)
    with allure.step("Поле целиком внутри модалки и без горизонтального переполнения"):
        field, dialog = message.field_box(), message.dialog_box()
        assert field and dialog, "Не удалось получить размеры поля/модалки"
        assert field["x"] >= dialog["x"] - 1 and (
            field["x"] + field["width"] <= dialog["x"] + dialog["width"] + 1
        ), f"Поле выходит за модалку по ширине: field={field}, dialog={dialog}"
        assert (
            not message.has_horizontal_overflow()
        ), "Текст выходит за видимую ширину поля (горизонтальное переполнение)"


# ---------------------------------------------------------------------------
# Ввод / граничные значения
# ---------------------------------------------------------------------------


@allure.title("Поле Message расширяется по высоте по мере ввода")
@allure.severity(allure.severity_level.MINOR)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Message")
@allure.tag("REMCL-1031")
@pytest.mark.ui
@pytest.mark.functional
@pytest.mark.issue_panel
@pytest.mark.message
def test_message_field_grows_in_height_with_input(message_modal: ReminderModal) -> None:
    """
    REMCL-1031, первая часть ("расширяется по высоте"). Вторая часть кейса
    ("не более 255 символов") — в test_message_input_beyond_max_length_is_
    blocked (там второй тег REMCL-1031).

    Многострочность получаем переносом длинного текста по ширине — не
    Enter'ом (Enter сабмитит форму, см. докстринг message_editor.py).
    Высота НЕ проверяется сверху: у обёртки есть maxcontentheight=200px,
    т.е. дальше, видимо, появляется скролл — вживую не проверено.
    """
    message = message_modal.message
    height_before = message.container_height()
    with allure.step("Ввести длинный текст, который переносится на несколько строк"):
        message.fill(("lorem ipsum dolor " * 20)[:MAX_MESSAGE_LENGTH])
    with allure.step("Высота поля увеличилась"):
        height_after = message.container_height()
        assert (
            height_after > height_before
        ), f"Высота поля не изменилась: до={height_before}, после={height_after}"


@allure.title("Ввод более 255 символов в поле Message блокируется")
@allure.severity(allure.severity_level.CRITICAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Message")
@allure.tag("REMCL-1268")
@allure.tag("REMCL-1031")
@pytest.mark.ui
@pytest.mark.validation
@pytest.mark.issue_panel
@pytest.mark.message
def test_message_input_beyond_max_length_is_blocked(
    message_modal: ReminderModal,
) -> None:
    """
    REMCL-1268 (+ вторая часть REMCL-1031). Символы НАБИРАЮТСЯ посимвольно
    (type_text), а не вставляются одной операцией: "блокируется ввод" —
    про реакцию на каждый лишний символ. Ожидаем, что в поле остались
    РОВНО первые 255 символов.

    ТЕХНИЧЕСКИЙ РИСК: как именно плагин ограничивает длину (обрезка,
    отказ во вставке, счётчик с ошибкой) — не подтверждено; первый прогон
    покажет. Вариант "вставка 300 символов из буфера" здесь не проверяется.
    """
    message = message_modal.message
    text = "".join(str(i % 10) for i in range(MAX_MESSAGE_LENGTH + 45))
    with allure.step(f"Набрать {len(text)} символов"):
        message.type_text(text)
    with allure.step(f"В поле ровно {MAX_MESSAGE_LENGTH} первых символов"):
        actual = message.text()
        assert (
            len(actual) == MAX_MESSAGE_LENGTH
        ), f"Длина текста в поле {len(actual)}, ожидалось {MAX_MESSAGE_LENGTH}"
        assert actual == text[:MAX_MESSAGE_LENGTH]


@allure.title("Поле Message принимает ровно 255 символов")
@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Message")
@allure.tag("REMCL-1269")
@pytest.mark.ui
@pytest.mark.validation
@pytest.mark.issue_panel
@pytest.mark.message
def test_message_accepts_exactly_max_length(
    issue_page: IssuePage, message_modal: ReminderModal
) -> None:
    """REMCL-1269. 255 символов (с уникальным хвостом внутри лимита) сохраняются."""
    suffix = _unique_suffix("1269")
    text = suffix + "x" * (MAX_MESSAGE_LENGTH - len(suffix))
    assert len(text) == MAX_MESSAGE_LENGTH
    message = message_modal.message
    with allure.step("Ввести ровно 255 символов"):
        message.fill(text)
    with allure.step("Весь текст в поле, кнопка Create активна"):
        assert message.text() == text, "Текст в поле обрезан или изменён"
        assert message_modal.is_create_enabled(), "Create disabled при 255 символах"
    _save_and_check_in_panel(issue_page, message_modal, suffix)


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Message")
@pytest.mark.ui
@pytest.mark.functional
@pytest.mark.issue_panel
@pytest.mark.message
@pytest.mark.parametrize(
    ("payload", "cases"),
    [
        pytest.param("1234567890", ("REMCL-1032",), id="digits"),
        pytest.param(
            "±!@#$%^&*()_+=|\\<>?", ("REMCL-1032", "REMCL-1270"), id="special-chars"
        ),
        pytest.param("Русский текст", ("REMCL-1032",), id="cyrillic"),
        pytest.param("Latin text", ("REMCL-1032",), id="latin"),
        pytest.param("我们喜欢学习", ("REMCL-1032",), id="cjk"),
        pytest.param("ز س ش ص ض ط", ("REMCL-1032",), id="arabic"),
        pytest.param("🙂‍↕️", ("REMCL-1271",), id="emoji-zwj"),
    ],
)
def test_message_accepts_and_saves_charset(
    issue_page: IssuePage,
    message_modal: ReminderModal,
    payload: str,
    cases: tuple[str, ...],
) -> None:
    """
    REMCL-1032 (цифры, спецсимволы, кириллица, латиница, иероглифы,
    арабская вязь), REMCL-1270 (спецсимволы), REMCL-1271 (emoji
    "вставляется в том же виде и сохраняется"). Один параметр = один
    класс символов (отдельный PASSED/FAILED в Allure).

    Ввод — fill() (вставка одной операцией, как "скопировать и вставить" в
    REMCL-1271). Проверки: текст в поле совпадает с введённым, после
    сохранения — тот же текст в секции Reminder.
    """
    for case in cases:
        allure.dynamic.tag(case)
    allure.dynamic.title(f"Поле Message принимает и сохраняет: {payload}")
    text = f"{payload} {_unique_suffix('charset')}"
    message = message_modal.message
    with allure.step(f"Ввести {payload!r}"):
        message.fill(text)
    with allure.step("Текст в поле совпадает с введённым"):
        assert message.text() == text, f"В поле {message.text()!r}, ожидалось {text!r}"
    _save_and_check_in_panel(issue_page, message_modal, text)


@allure.title("HTML/script теги в Message не выполняются")
@allure.severity(allure.severity_level.CRITICAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Message")
@allure.tag("REMCL-1273")
@pytest.mark.ui
@pytest.mark.validation
@pytest.mark.negative
@pytest.mark.issue_panel
@pytest.mark.message
def test_message_html_and_script_are_not_executed(
    issue_page: IssuePage, message_modal: ReminderModal, js_dialogs: list[str]
) -> None:
    """
    REMCL-1273 — ЧАСТИЧНО ПОКРЫТ: проверяется ввод и отображение
    сохранённого ремайндера в секции Reminder. Шаг кейса "Открыть снова
    ремайндер" (форма редактирования) — НЕ реализован, ждёт локатора
    открытия редактирования (тот же, что нужен для REMCL-1287).

    Все 4 варианта из кейса вводятся в ОДИН ремайндер (через пробел) —
    так кейс и сформулирован ("последовательно варианты кода").
    """
    payloads = [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert(1)>",
        "<b>bold</b>",
        '<a href="javascript:alert(1)">click</a>',
    ]
    text = f"{' '.join(payloads)} {_unique_suffix('1273')}"
    injected = "script, img, b, a[href^='javascript']"
    message = message_modal.message

    with allure.step("Ввести в Message HTML/JS варианты"):
        message.fill(text)
    with allure.step("В редакторе это обычный текст, а не разметка"):
        assert message.text() == text
        assert (
            message.count_elements(injected) == 0
        ), f"В редакторе появились элементы из введённого HTML: {message.html()!r}"
    _save_and_check_in_panel(issue_page, message_modal, text)
    with allure.step("В секции Reminder нет внедрённых элементов, alert не всплыл"):
        assert (
            issue_page.reminder_panel.count_elements(
                "img[src='x'], a[href^='javascript']"
            )
            == 0
        ), "Введённый HTML отрендерился в секции Reminder как разметка"
        assert not js_dialogs, f"Всплыли JS-диалоги: {js_dialogs}"


# ---------------------------------------------------------------------------
# Форматирование
# ---------------------------------------------------------------------------


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Message")
@pytest.mark.ui
@pytest.mark.functional
@pytest.mark.issue_panel
@pytest.mark.message
@pytest.mark.parametrize(
    ("fmt", "case"),
    [
        pytest.param("bold", "REMCL-1276", id="bold"),
        pytest.param("italic", "REMCL-1277", id="italic"),
        pytest.param("underline", "REMCL-1278", id="underline"),
        pytest.param("strike", "REMCL-1279", id="strikethrough"),
    ],
)
def test_message_inline_format_applies_to_selection(
    message_modal: ReminderModal, fmt: str, case: str
) -> None:
    """
    REMCL-1276/1277/1278/1279. Вводим "Hello world", выделяем только
    "world", применяем формат: отформатирован ровно выделенный фрагмент,
    остальной текст — нет, кнопка формата подсвечена (ql-active).
    Проверка на уровне редактора; отображение формата после сохранения
    (в секции/письме) кейсы не описывают.
    """
    allure.dynamic.tag(case)
    allure.dynamic.title(
        f"Форматирование {fmt} применяется к выделенному тексту Message"
    )
    message = message_modal.message
    with allure.step("Ввести 'Hello world' и выделить 'world'"):
        message.fill("Hello world")
        message.select_last_chars(len("world"))
    with allure.step(f"Нажать кнопку {fmt} в toolbar"):
        message.apply_format(fmt)  # type: ignore[arg-type]
    with allure.step("Отформатирован только выделенный фрагмент"):
        fragments = message.fragments_with_format(fmt)  # type: ignore[arg-type]
        assert fragments == ["world"], (
            f"Ожидался один фрагмент 'world' с форматом {fmt}, найдено {fragments}; "
            f"HTML: {message.html()!r}"
        )
        assert message.text() == "Hello world"
    with allure.step("Кнопка формата активна"):
        assert message.is_format_active(fmt), f"Кнопка {fmt} не подсвечена (ql-active)"  # type: ignore[arg-type]


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Message")
@pytest.mark.ui
@pytest.mark.functional
@pytest.mark.issue_panel
@pytest.mark.message
@pytest.mark.parametrize(
    ("button", "kind", "case"),
    [
        pytest.param("bullet_list", "bullet", "REMCL-1280", id="bulleted"),
        pytest.param("ordered_list", "ordered", "REMCL-1281", id="numbered"),
    ],
)
def test_message_list_formatting(
    message_modal: ReminderModal, button: str, kind: str, case: str
) -> None:
    """
    REMCL-1280/1281 — ЧАСТИЧНО ПОКРЫТЫ: список из ОДНОГО пункта. Для
    нескольких пунктов нужен перенос строки, а Enter сабмитит форму —
    способ (Shift+Enter?) не подтверждён (вопрос в чате 2026-11-20).
    """
    allure.dynamic.tag(case)
    allure.dynamic.title(f"Список ({kind}) корректно отображается в Message")
    message = message_modal.message
    with allure.step("Ввести текст пункта"):
        message.fill("First item")
    with allure.step(f"Нажать кнопку {button}"):
        message.apply_format(button)  # type: ignore[arg-type]
    with allure.step("Текст стал пунктом списка нужного типа"):
        items = message.list_items()
        assert items == [
            {"text": "First item", "kind": kind}
        ], f"Ожидался один пункт {kind}-списка, получено {items}; HTML: {message.html()!r}"
        assert message.is_format_active(button)  # type: ignore[arg-type]


@allure.title("Ссылка корректно добавляется в Message")
@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Message")
@allure.tag("REMCL-1282")
@pytest.mark.ui
@pytest.mark.functional
@pytest.mark.issue_panel
@pytest.mark.message
def test_message_link_is_added(message_modal: ReminderModal) -> None:
    """
    REMCL-1282 (связан с REMCL-2726 через link "identify" — вероятно, баг
    про ссылки; содержимое не смотрели). Выделяем текст, кнопка Link,
    вводим URL в попап Quill, Save.
    """
    url = "https://example.com/reminder-autotest"
    message = message_modal.message
    with allure.step("Ввести текст и выделить его"):
        message.fill("Open site")
        message.select_all()
    with allure.step(f"Добавить ссылку {url}"):
        message.add_link_to_selection(url)
    with allure.step("Текст стал ссылкой с нужным href"):
        links = message.links()
        assert links == [
            {"text": "Open site", "href": url}
        ], f"Ожидалась одна ссылка, получено {links}; HTML: {message.html()!r}"


# ---------------------------------------------------------------------------
# Доставка
# ---------------------------------------------------------------------------


@allure.title("Текст Message отображается получателю reminder")
@allure.severity(allure.severity_level.CRITICAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Message")
@allure.tag("REMCL-1283")
@pytest.mark.ui
@pytest.mark.functional
@pytest.mark.email
@pytest.mark.issue_panel
@pytest.mark.message
def test_message_text_delivered_to_recipient(
    message_modal: ReminderModal, settings: Settings, mail_client: MailClient
) -> None:
    """
    REMCL-1283. Получатель — MAIL_TEST_RECIPIENT_DISPLAY_NAME (чей ящик
    слушает MAIL_IMAP_LOGIN), НЕ залогиненный создатель — см. Project
    Instructions "кто получатель, чей ящик мы читаем". Уникальный текст
    Message ищется в теме или теле письма (MailClient.wait_for_email).
    """
    recipient = settings.mail_test_recipient_display_name
    if recipient is None:
        pytest.skip("MAIL_TEST_RECIPIENT_DISPLAY_NAME не задан в .env")
    text = f"Message delivery check {_unique_suffix('1283')}"

    with allure.step(f"Оставить единственным получателем {recipient!r}"):
        message_modal.open_dropdown()
        message_modal.clear_all()
        message_modal.search(recipient)
        message_modal.wait_for_search_to_settle()
        expect(message_modal.option_in_users_section(recipient)).to_be_visible(
            timeout=10_000
        )
        message_modal.select_in_users_section(recipient)
    with allure.step(f"Ввести уникальный текст Message: {text!r}"):
        message_modal.fill_message(text)

    now_moscow = datetime.now(MOSCOW_TZ)
    target_time = round_up_to_next_five_minutes(now_moscow)
    seconds_until_target = (target_time - now_moscow).total_seconds()
    since = datetime.now(timezone.utc)  # фиксируем ДО сабмита
    with allure.step(f"Дата/время {target_time.isoformat()} (Europe/Moscow), Create"):
        message_modal.set_specific_datetime(target_time)
        message_modal.submit()

    with allure.step("Письмо получателю содержит текст Message"):
        email = mail_client.wait_for_email(
            text,
            since=since,
            timeout_s=int(
                seconds_until_target
                + settings.mail_wait_timeout_s
                + PLUGIN_SCHEDULE_POLL_BUFFER_S
            ),
        )
        allure.attach(
            f"from={email.from_!r}\ndate={email.date.isoformat()}\nsubject={email.subject!r}",
            name="Найденное письмо",
            attachment_type=allure.attachment_type.TEXT,
        )


# ---------------------------------------------------------------------------
# Skip с причиной
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason=(
        "REMCL-1260: отложено по решению пользователя (2026-11-20). Кроме "
        "панели на задаче, для других форм создания (My reminders, "
        "dashboard-гаджет и т.п.) нет Page Object."
    )
)
@allure.tag("REMCL-1260")
@pytest.mark.ui
@pytest.mark.message
def test_message_field_present_in_all_creation_forms() -> None:
    """REMCL-1260 — см. skip."""


@pytest.mark.skip(
    reason=(
        "REMCL-1284: нужны отдельная сессия Jira Admin (storage_state под "
        "админа, по аналогии с юзером без прав на группы в fixtures/"
        "conftest.py) и Page Object админской Reminder queue — ни того, ни "
        "другого в репозитории пока нет."
    )
)
@allure.tag("REMCL-1284")
@pytest.mark.ui
@pytest.mark.queue
@pytest.mark.message
def test_admin_does_not_see_private_reminder_message_in_queue() -> None:
    """REMCL-1284 — см. skip."""
