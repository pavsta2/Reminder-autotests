# pages/components/when_fields.py
from __future__ import annotations

import re
from typing import TYPE_CHECKING

import allure
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from pages.components.reminder_modal import ReminderModal


class WhenFieldsComponent:
    """
    Компонент блока "When" в модалке создания/редактирования ремайндера.
    Включает single-select поле When, date-time picker и toggle Repeat.

    ТЕХНИЧЕСКИЙ РИСК (2026-11-23): Поле Date & time (MUI DatePicker) не
    поддерживает свободный ввод с клавиатуры. Валидация форматов и ограничений
    (например, шаг 5 минут) обеспечивается отсутствием невалидных опций в UI-попапе,
    а не блокировкой onKeyPress.
    """

    # Константы опций поля When
    OPTION_SPECIFIC_DATE = "Specific date"
    OPTION_AT_DUE_DATE = "At Due Date"
    OPTION_BEFORE_DUE_DATE = "Before Due Date"
    OPTION_AFTER_DUE_DATE = "After Due Date"

    def __init__(self, page: Page, modal_root_locator):
        self._page = page
        # Скоупим поиск внутри модалки, чтобы не пересечься с другими формами на странице
        self._root = modal_root_locator

        # --- Локаторы внутри модалки ---
        # MUI Autocomplete обычно связывает label с input через id/for
        self._when_combobox = self._root.get_by_role("combobox", name="When")

        self._date_time_input = self._root.get_by_label("Date & time")
        self._date_time_picker_btn = self._root.get_by_role("button", name="Choose date")
        self._date_time_clear_btn = self._root.get_by_role("button", name="Clear")
        self._timezone_container = self._root.locator("#date-picker-label-container")

        self._date_time_error_empty = self._root.get_by_text("Date & time can’t be empty.")
        self._date_time_error_past = self._root.get_by_text("Selected date & time can’t be in the past")

        # Toggle Repeat (используем data-testid родителя для надежности)
        self._repeat_toggle_checkbox = self._root.locator('[data-testid="when-repeat"] input[type="checkbox"]')
        self._repeat_toggle_label = self._root.get_by_label("Repeat")

        # --- Локаторы попапов (рендерятся в body, вне модалки!) ---
        # MUI Autocomplete listbox
        self._when_listbox = self._page.get_by_role("listbox").filter(has=self._page.get_by_role("option"))

        # DatePicker попапы (часы и минуты)
        self._hours_list = self._page.get_by_role("listbox", name="Select hours")
        self._minutes_list = self._page.get_by_role("listbox", name="Select minutes")

    # ==================== МЕТОДЫ ВЗАИМОДЕЙСТВИЯ ====================

    @allure.step("Выбрать опцию '{option}' в поле When")
    def select_when_option(self, option: str) -> None:
        self._when_combobox.click()
        option_locator = self._when_listbox.get_by_role("option", name=option)
        option_locator.click()
        # Ждем закрытия дропдауна
        expect(option_locator).to_be_hidden()

    @allure.step("Получить текущее значение поля When")
    def get_when_value(self) -> str:
        return self._when_combobox.input_value()

    @allure.step("Открыть попап Date & time")
    def open_date_time_picker(self) -> None:
        self._date_time_picker_btn.click()
        expect(self._hours_list).to_be_visible()

    @allure.step("Закрыть попап Date & time")
    def close_date_time_picker(self) -> None:
        self._page.keyboard.press("Escape")
        expect(self._hours_list).to_be_hidden()

    @allure.step("Очистить поле Date & time")
    def clear_date_time(self) -> None:
        self._date_time_clear_btn.click()

    @allure.step("Получить строковое значение из input Date & time")
    def get_date_time_input_value(self) -> str:
        return self._date_time_input.input_value()

    @allure.step("Переключить Repeat в состояние {state}")
    def set_repeat(self, state: bool) -> None:
        is_checked = self._repeat_toggle_checkbox.is_checked()
        if is_checked != state:
            self._repeat_toggle_label.click()

    @allure.step("Выбрать час '{hour}' в попапе")
    def select_hour(self, hour: str) -> None:
        self._hours_list.get_by_role("option", name=f"{hour} hours").click()

    @allure.step("Выбрать минуту '{minute}' в попапе")
    def select_minute(self, minute: str) -> None:
        self._minutes_list.get_by_role("option", name=f"{minute} minutes").click()

    # ==================== ПРОВЕРКИ (EXPECTS) ====================

    def expect_when_options_disabled(self, options: list[str]) -> None:
        self._when_combobox.click()
        for opt in options:
            opt_loc = self._when_listbox.get_by_role("option", name=opt)
            expect(opt_loc).to_have_attribute("aria-disabled", "true")
        self._page.keyboard.press("Escape")

    def expect_date_time_error_empty_visible(self, visible: bool = True) -> None:
        if visible:
            expect(self._date_time_error_empty).to_be_visible()
        else:
            expect(self._date_time_error_empty).to_be_hidden()

    def expect_date_time_error_past_visible(self, visible: bool = True) -> None:
        if visible:
            expect(self._date_time_error_past).to_be_visible()
        else:
            expect(self._date_time_error_past).to_be_hidden()

    def expect_timezone_contains(self, text: str) -> None:
        expect(self._timezone_container).to_contain_text(text)