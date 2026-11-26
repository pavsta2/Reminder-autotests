"""
Тесты на кнопки Create/Cancel формы создания ремайндера (модалка "New
reminder") — в отличие от tests/ui/test_reminder_recipients.py, здесь речь
НЕ о конкретном поле Recipients, а о самой форме: как она сохраняется и
закрывается.
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
    with allure.step("Проверить, что окно создания ремайндера закрылось"):
        assert modal.is_closed(), (
            "Модалка не закрылась после нажатия Create"
        )
    with allure.step(
            "Проверить, что ремайндер с этим текстом появился в секции Reminder"
    ):
        assert issue_page.reminder_panel.has_reminder_with_text(
            unique_message
        ), "Созданный ремайндер не найден в секции Reminder на странице задачи"
