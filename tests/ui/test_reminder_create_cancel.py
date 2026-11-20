"""
Тесты на кнопки Create/Cancel формы создания ремайндера (модалка "New
reminder") — в отличие от tests/ui/test_reminder_recipients.py, здесь речь
НЕ о конкретном поле Recipients, а о самой форме: как она сохраняется и
закрывается.

Источник test-кейсов: RTM-экспорт "rtm-issues-export_17.zip" (4 кейса,
компонент "5.0. Creation form", все QA Label "F"):
    REMCL-1037 — Cancel (как link-button) ИЛИ Esc закрывает форму без
                 создания ремайндера
    REMCL-1038 — Create (синяя button) ИЛИ Enter сохраняет форму (создаёт
                 ремайндер)
    REMCL-1039 — состояния кнопки Cancel при взаимодействии (hover/pressed/
                 default)
    REMCL-1040 — состояния кнопки Create при взаимодействии (hover/pressed/
                 default)

Реализовано (2026-11-16):
    REMCL-1037 (ТОЛЬКО вариант "кнопка Cancel") — закрытие модалки кнопкой
    Cancel уже многократно подтверждено живыми прогонами (этой же кнопкой
    пользуется teardown фикстуры recipients_modal в test_reminder_
    recipients.py на протяжении всего файла) — здесь это оформлено отдельным
    явным тестом с проверкой состояния модалки до/после через is_open()/
    is_closed() (см. ДОБАВЛЕНО п.11 докстринга ReminderModal).

    REMCL-1038 (ТОЛЬКО вариант "кнопка Create") — по уточнению от автора
    кейсов: сохранение ремайндера можно подтвердить, НЕ открывая My
    reminders/Queue — созданный ремайндер отображается прямо в контекстной
    секции Reminder на странице задачи (см. ReminderPanel.
    has_reminder_with_text(), ДОБАВЛЕНО п.7 докстринга reminder_panel.py).
    Тест вводит заведомо уникальное сообщение (Faker + текущее время) в
    поле Message и ищет этот же текст в секции после клика Create. Это
    ПЕРВЫЙ тест, который реально сохраняет ремайндер на тестовом инстансе —
    он ничего не удаляет за собой (метода delete в репозитории пока нет),
    поэтому каждый прогон оставляет одну запись; уникальность сообщения —
    единственная защита от путаницы между прогонами, а не полноценный
    teardown.

    REMCL-1038 (ТОЛЬКО вариант "клавиша Enter", добавлено 2026-11-16 по
    запросу "доделать skip-тесты, раз кнопка Create теперь работает") —
    та же схема (уникальное сообщение + has_reminder_with_text()), но
    сабмит — нажатием Enter прямо в поле Message, без клика по Create. См.
    test_enter_key_in_message_field_saves_reminder и ТЕХНИЧЕСКИЙ РИСК в
    нём: природа поля (input vs contenteditable) не подтверждена, поэтому
    этот тест может честно упасть на первом прогоне — это будет полезной
    информацией, а не угадыванием.

НЕ реализовано — honest skip ниже, с конкретной причиной у каждого:
    REMCL-1037 (вариант "клавиша Esc")  — см. skip: найдено прямое
                                           противоречащее свидетельство в
                                           уже подтверждённых тестах
                                           REMCL-1085/1086.
    REMCL-1039, REMCL-1040              — исходные кейсы неоднозначны:
                                           Description содержит только
                                           заголовки состояний ("hover -",
                                           "pressed -", "default -") БЕЗ
                                           единого заполненного значения —
                                           ни цвета, ни конкретного визуального
                                           отличия не указано. Угадывать
                                           ожидаемый внешний вид не стали.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

import allure
import pytest
from faker import Faker

from pages.components.reminder_modal import ReminderModal
from pages.issue_page import IssuePage

_faker = Faker()


@pytest.fixture
def reminder_modal(issue_page: IssuePage, issue_key: str) -> Iterator[ReminderModal]:
    """Открывает задачу и модалку "New reminder", отдаёт готовый ReminderModal."""
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
        # Модалка уже закрыта самим тестом (например, именно это и
        # проверяется) — не мешаем отчёту падением в teardown.
        pass


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Create/Cancel buttons")
@allure.tag("REMCL-1037")
@pytest.mark.ui
@pytest.mark.functional
@pytest.mark.issue_panel
@pytest.mark.creation_form
def test_cancel_button_closes_form_without_creating_reminder(
    reminder_modal: ReminderModal,
) -> None:
    """
    REMCL-1037 (вариант "кнопка Cancel"): кнопка Cancel закрывает форму
    создания ремайндера, не сохраняя его.

    Вариант "клавиша Esc" из того же кейса реализован ОТДЕЛЬНО не был — см.
    honest skip ниже и докстринг модуля.
    """
    with allure.step("Форма создания ремайндера открыта"):
        assert reminder_modal.is_open(), "Предусловие не выполнено: модалка не открыта"

    with allure.step("Нажать Cancel"):
        reminder_modal.close()

    with allure.step("Проверить, что форма закрылась"):
        assert reminder_modal.is_closed(), "Модалка всё ещё открыта после Cancel"


# =====================================================================
# Заготовки для кейсов, которые НЕ реализованы в этом батче — честно
# помечены skip с причиной (см. docstring модуля), а не угаданы.
# =====================================================================


@pytest.mark.skip(
    reason=(
        "REMCL-1037 (вариант 'клавиша Esc'): нужно подтвердить вживую, "
        "закрывает ли Esc МОДАЛКУ ЦЕЛИКОМ, когда дропдаун поля Recipients "
        "уже закрыт (а не открыт). Прямое противоречащее свидетельство уже "
        "есть: REMCL-1085/REMCL-1086 (test_reminder_recipients.py) живым "
        "прогоном подтвердили, что Esc, нажатый при ОТКРЫТОМ дропдауне, "
        "закрывает ТОЛЬКО дропдаун — модалка остаётся открытой (иначе эти "
        "тесты не смогли бы продолжить вводить данные в поле сразу после "
        "Escape). Поведение Esc при закрытом дропдауне отдельно не "
        "проверялось и может отличаться — попытка проверить это вживую "
        "через built-in browser в этой сессии не удалась по независящей от "
        "конкретной кнопки причине (см. ДОБАВЛЕНО п.11 докстринга "
        "pages/components/reminder_modal.py) — нужен реальный прогон "
        "pytest (page.pause() или просто сам тест) на инстансе, чтобы не "
        "писать ассерт вслепую."
    )
)
@pytest.mark.functional
@pytest.mark.issue_panel
@pytest.mark.creation_form
def test_escape_key_closes_form_without_creating_reminder() -> None:
    """REMCL-1037 (вариант 'клавиша Esc')."""


@allure.severity(allure.severity_level.CRITICAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Create/Cancel buttons")
@allure.tag("REMCL-1038")
@allure.tag("REMCL-1275")
@pytest.mark.ui
@pytest.mark.functional
@pytest.mark.issue_panel
@pytest.mark.creation_form
@pytest.mark.message
def test_create_button_saves_reminder(issue_page: IssuePage, issue_key: str) -> None:
    """
    REMCL-1038 (вариант "кнопка Create"): кнопка Create сохраняет ремайндер.

    REMCL-1275 ("Введенный текст Message сохраняется после создания
    reminder", RTM-экспорт rtm-issues-export_22) — ДУБЛЬ по смыслу: этот
    тест уже вводит уникальный текст в Message и проверяет, что после
    Create ремайндер с этим текстом есть в секции Reminder. Поэтому второй
    тег, а не копия теста (добавлено 2026-11-20). Более сильная проверка
    (текст виден в форме редактирования) — REMCL-1287, tests/ui/
    test_reminder_message.py.

    По уточнению пользователя, My reminders/Queue для этого не нужны —
    факт сохранения подтверждается появлением ремайндера прямо в
    контекстной секции Reminder на странице задачи (см. ReminderPanel.
    has_reminder_with_text()).

    Не использует фикстуру reminder_modal, т.к. нужен доступ и к модалке, и
    к панели (issue_page.reminder_panel) одновременно, а teardown этой
    фикстуры был бы бессмысленным: после submit() модалка либо уже закрыта
    сама, либо закрывать её Cancel'ом означало бы неявно отменять только что
    сохранённый ремайндер (чего не происходит — Cancel здесь не нужен).

    ТЕХНИЧЕСКИЙ РИСК (не подтверждено вживую первым реальным прогоном — см.
    ДОБАВЛЕНО п.12 докстринга ReminderModal и п.7 докстринга ReminderPanel):
    точный локатор поля Message (role="textbox") и разметка строки
    созданного ремайндера в секции Reminder.

    Тест НИЧЕГО не удаляет за собой (метода delete в репозитории пока нет) —
    уникальный текст сообщения (Faker + UTC-таймстамп) защищает только от
    путаницы между прогонами, а не от накопления данных на тестовом
    инстансе. Это сознательный trade-off, см. docstring модуля.
    """
    unique_message = (
        f"{_faker.sentence(nb_words=4).rstrip('.')} "
        # datetime.UTC (ruff UP017) требует Python 3.11+ — в проекте нет
        # явно зафиксированной минимальной версии Python, поэтому
        # сознательно оставлен более переносимый timezone.utc.
        f"[autotest {datetime.now(timezone.utc).isoformat(timespec='seconds')}]"
    )

    with allure.step("Открыть задачу и форму создания ремайндера"):
        issue_page.open(issue_key)
        assert (
            issue_page.has_reminder_section()
        ), "Секция Reminder не найдена на странице задачи"
        issue_page.reminder_panel.expand()
        modal = issue_page.reminder_panel.open_create_modal()
        assert modal.is_open(), "Предусловие не выполнено: модалка не открыта"

    with allure.step(f"Ввести уникальный текст сообщения: {unique_message!r}"):
        modal.fill_message(unique_message)

    with allure.step("Нажать Create"):
        modal.submit()

    with allure.step(
        "Проверить, что ремайндер с этим текстом появился в секции Reminder"
    ):
        assert issue_page.reminder_panel.has_reminder_with_text(
            unique_message
        ), "Созданный ремайндер не найден в секции Reminder на странице задачи"


@allure.severity(allure.severity_level.NORMAL)
@allure.label("feature", "Reminder creation form")
@allure.label("story", "Create/Cancel buttons")
@allure.tag("REMCL-1038")
@pytest.mark.ui
@pytest.mark.functional
@pytest.mark.issue_panel
@pytest.mark.creation_form
def test_enter_key_in_message_field_saves_reminder(
    issue_page: IssuePage, issue_key: str
) -> None:
    """
    REMCL-1038 (вариант "клавиша Enter"): нажатие Enter в поле Message
    сохраняет ремайндер — так же, как и клик по кнопке Create (см.
    test_create_button_saves_reminder выше, использует тот же приём с
    уникальным сообщением и той же проверкой через ReminderPanel.
    has_reminder_with_text()).

    РЕАЛИЗОВАНО (2026-11-16, по итогам того, что test_create_button_saves_
    reminder стал реально рабочим): после fill_message() фокус остаётся в
    редакторе Message (fill() не снимает фокус) — это позволяет нажать
    Enter СРАЗУ туда же без дополнительного клика/локатора.

    ТЕХНИЧЕСКИЙ РИСК (не подтверждено вживую первым реальным прогоном):
    природа поля Message — обычный однострочный `<input>` или
    contenteditable rich-text редактор — не подтверждена (см. риск в
    fill_message(), reminder_modal.py). Если поле однострочный `<input>`,
    Enter по умолчанию (нативное поведение браузера) сабмитит форму — это
    ровно то поведение, которое здесь проверяется. Если же поле на деле
    contenteditable (многострочный rich-text), Enter, как правило, просто
    вставляет перенос строки и НЕ сабмитит форму — тогда этот тест будет
    честно падать, и это будет первое прямое живое подтверждение того,
    какой именно тип поля используется на самом деле (сейчас неизвестно).
    """
    unique_message = (
        f"{_faker.sentence(nb_words=4).rstrip('.')} "
        # datetime.UTC (ruff UP017) требует Python 3.11+ — см. тот же
        # комментарий в test_create_button_saves_reminder.
        f"[autotest-enter {datetime.now(timezone.utc).isoformat(timespec='seconds')}]"
    )

    with allure.step("Открыть задачу и форму создания ремайндера"):
        issue_page.open(issue_key)
        assert (
            issue_page.has_reminder_section()
        ), "Секция Reminder не найдена на странице задачи"
        issue_page.reminder_panel.expand()
        modal = issue_page.reminder_panel.open_create_modal()
        assert modal.is_open(), "Предусловие не выполнено: модалка не открыта"

    with allure.step(f"Ввести уникальный текст сообщения: {unique_message!r}"):
        modal.fill_message(unique_message)

    with allure.step("Нажать Enter в поле Message (не кликая Create)"):
        modal.page.keyboard.press("Enter")

    with allure.step(
        "Проверить, что ремайндер с этим текстом появился в секции Reminder"
    ):
        assert issue_page.reminder_panel.has_reminder_with_text(
            unique_message
        ), "Созданный ремайндер не найден в секции Reminder на странице задачи"


@pytest.mark.skip(
    reason=(
        "REMCL-1039: исходный кейс неоднозначен — Description содержит "
        "только заголовки состояний кнопки Cancel ('hover -', 'pressed -', "
        "'default -') без единого заполненного значения: не указано, чем "
        "именно должно отличаться каждое состояние (цвет текста/фона, "
        "подчёркивание и т.п. — кнопка оформлена как link-button, см. "
        "REMCL-1037). Угадывать ожидаемый визуальный вид — значит писать "
        "тест под собственное предположение, а не под то, что реально "
        "описано в кейсе. Нужно уточнение у автора кейсов: какие конкретно "
        "визуальные изменения ожидаются в каждом состоянии."
    )
)
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.creation_form
def test_cancel_button_visual_states() -> None:
    """REMCL-1039."""


@pytest.mark.skip(
    reason=(
        "REMCL-1040: та же проблема, что и у REMCL-1039 (см. выше), только "
        "для кнопки Create — Description содержит только заголовки "
        "состояний ('hover -', 'pressed -', 'default -') без заполненных "
        "значений. Нужно то же уточнение у автора кейсов."
    )
)
@pytest.mark.ui
@pytest.mark.issue_panel
@pytest.mark.creation_form
def test_create_button_visual_states() -> None:
    """REMCL-1040."""
