"""
ReminderModal — модалка "New reminder" (создание ремайндера), открывается
кнопкой Create в ReminderPanel (см. pages/components/reminder_panel.py) либо
с других экранов (My reminders и т.п. — там переиспользуется тот же компонент).

Покрывает: Recipients, Message/submit, Date & time, ошибку про получателей без
доступа к задаче, блок When (+ Repeat и настройки повторения), Privacy
(+ Allow edit), Linked item (+ Condition/JQL).

============================================================================
ИСТОРИЯ И НАХОДКИ (сохранять при рефакторинге)
============================================================================

ИСПРАВЛЕНО (2026-11-13, раунд 1 — НЕВЕРНЫЙ, оставлен для истории): по DevTools
был сделан вывод, что модалка рендерится MUI-формой прямо в хост-документе, без
iframe и без role="dialog". Это сломало wait_until_ready.

ИСПРАВЛЕНО (2026-11-13, раунд 2 — актуальная версия): проверка через
page.pause() в сессии автотеста показала, что раунд 1 сделан с консолью
DevTools, переключённой ВНУТРЬ iframe модалки. В TOP-контексте заголовка
"New reminder" среди h2 нет; два iframe с одинаковым title="Embedded app
content for <extension_id>" — панель и модалка; цепочка предков крупного:
iframe -> div-обёртки -> section[role="dialog"] -> div.atlaskit-portal ->
body#jira.adg3. role="dialog" ЕСТЬ, он оборачивает iframe, а не форму.
self.frame = page.get_by_role("dialog").frame_locator("iframe").
Различать iframe панели и модалки — по контейнеру, не по title.

--- Recipients ---
Custom multi-select, группировка по секциям ("Users", "Groups", при правах —
видимо и "Roles"). Поиск серверный: "Loading...", затем опции или
"No recipients found". По умолчанию в поле тег текущего пользователя.
Тексты подтверждены: placeholder "Type to search users or groups…"; tooltip
"If you have the necessary permissions, you can select Jira groups or roles";
валидация "At least one recipient should be selected"; "No recipients found".
Поведение: chips с кнопкой удаления; при опустошении — ошибка и Create
disabled; повторный клик по опции СНИМАЕТ выбор; в "Users" первыми Assignee и
Reporter, в "Groups" — Watchers; поиск регистронезависимый, фильтрует секции.

ОПРОВЕРГНУТО (2026-11-16): ArrowDown+Enter на пустом нефильтрованном списке
не отмечает ни одной строки.
ТЕХНИЧЕСКИЙ РИСК: порядок нефильтрованного списка не алфавитный; секция
"Roles" на CPR1 не появилась; role/name иконки-тултипа и кнопки очистки
целиком не подтверждены через accessibility tree.

ИСПРАВЛЕНО (2026-11-14): звёздочка ВНУТРИ <label>, textContent = "Recipients *".
exact=True не совпадал, exact=False цеплял "No recipients found" → regex с
якорями.
ИСПРАВЛЕНО (2026-11-15): тег — MUI Chip, внешний div сам role="button" с именем
тега; прежний локатор кликал ПО ЧИПУ. remove_tag() ищет чип по точному тексту и
кликает вложенную кнопку.

ТЕХНИЧЕСКИЙ РИСК (2026-11-25): _options_listbox ищется как
frame.get_by_role("listbox") без скоупа. При открытом попапе Condition в iframe
появляется ЕЩЁ ОДИН listbox — автокомплит JQL
(data-testid="jql-editor-autocomplete"). В этом состоянии option()/select()
для Recipients могут дать strict-mode violation. Тесты ОБЯЗАНЫ закрывать
попап Condition перед работой с Recipients.

--- Message / submit ---
fill_message() делегирует в MessageEditor (Quill,
div.ql-editor[role="textbox"][aria-labelledby="reminder-message-label"]).
ИСПРАВЛЕНО (2026-11-16): get_by_role("textbox") без уточнения матчил и input
Recipients (implicit role) → strict mode violation; исправлено анкеровкой.
submit() после клика best-effort ждёт закрытия модалки (гонка со спиннером).
ИСПРАВЛЕНО (2026-11-24): is_message_length_error_visible() перенесён в блок
Message; добавлена MESSAGE_LENGTH_ERROR_TEXT (REMCL-1031: ввод >255 больше НЕ
блокируется, появляется ошибка и Create деактивируется).

ВАЖНО (2026-11-25): обязательность Message зависит от типа привязки — при
"Work item" необязателен, при "Link" ОБЯЗАТЕЛЕН, без него Create задизейблена.

--- Date & time ---
Значение "DD/Mon/YY HH:MM"; поле НЕ редактируется с клавиатуры — только клики
по попапу; минуты ТОЛЬКО с шагом 5. select_minute()/set_specific_datetime()
бросают ValueError на невалидной минуте, а не округляют молча.
ИСПРАВЛЕНО (2026-11-23): контейнер data-testid="when-specific-date", кнопки
aria-label="Choose date"/"Clear".
ИСПРАВЛЕНО (2026-11-23, живой прогон): реальное сообщение "Date & time can't be
empty" БЕЗ точки в конце (в кейсах — с точкой). Точка опциональна, пробелы
заменены на пробельные классы. То же для сообщения о прошедшем времени.
ИСПРАВЛЕНО (2026-11-23, живой прогон): поле — <input>, text_content() всегда
пуст → date_time_field_text() использует input_value().
ТЕХНИЧЕСКИЙ РИСК: role/name ячеек календаря и пунктов списков угаданы;
пересечение текстов "00"/"05"/"10"/"15"/"20" между списками не проверено;
смена месяца не реализована.

--- Ошибка про доступ к задаче (REMCL-2736) ---
ИСПРАВЛЕНО (2026-11-19): апостроф в "don't" на форме типографский (U+2019) →
regex с "." вместо апострофа + IGNORECASE.
ИСПРАВЛЕНО (2026-11-19): при добавлении нескольких получателей React
переотрисовывает текст; однократный снимок ловил переходное состояние →
access_error_locator() для auto-retrying expect().

--- Блок When (+ Repeat) ---
Реализован ВНУТРИ класса (решение пользователя 2026-11-23). data-testid
"when-specific-date"/"when-repeat"; поле When — по лейблу + role="combobox".
ИСПРАВЛЕНО (2026-11-24): is_when_dropdown_open() проверял listbox Recipients
вместо When → переписан на aria-expanded.
НАБЛЮДЕНИЕ (2026-11-23): один Space открывает дропдаун со всеми опциями;
второй Space вводит пробел → "No options" (корректное поведение формы).
Настройки повторения: data-testid "repeat-ends"/"repeat-end-date", Frequency
по inputmode="numeric".

--- Privacy ---
Появляется ТОЛЬКО когда среди Recipients есть кто-то кроме создателя.
ИСПРАВЛЕНО (2026-11-24, живой прогон): текст тултипа лежит в aria-label на
<span>-обёртке иконки; отдельного role="tooltip" при hover НЕ появляется →
читаем aria-label, hover оставлен фоллбеком.

--- Allow edit (2026-11-27, по разметке обоих состояний) ---
ДОБАВЛЕНО для блока кейсов "Creation - Allow edit (v.2.X.X)"
(REMCL-1019/1020/1333-1338).

НАХОДКА 1: тултип — в атрибуте aria-label на КОНТЕЙНЕРЕ
<span data-testid="allow-edit-toggle">, а не в отдельном role="tooltip":
  * Privacy = Public (тоггл disabled) →
    aria-label="Editing of public reminders is controlled by project-level
    permissions." (дословно текст REMCL-1020);
  * Privacy = Private (тоггл активен) → aria-label="" (ПУСТОЙ).
  Тот же паттерн, что у Privacy-тултипа (2026-11-24): hover не нужен, читаем
  атрибут. Пустота атрибута в активном состоянии — сама по себе проверяемый
  факт ("тултип только в неактивном состоянии").

НАХОДКА 2: <label>Allow edit</label> НЕ имеет атрибута for/htmlFor, т.е. НЕ
связан с чекбоксом программно. get_by_label("Allow edit") НЕ найдёт input —
единственный путь к чекбоксу через контейнер data-testid="allow-edit-toggle"
(приоритет №1). Сам input — визуально скрытый MUI Switch input (opacity:0),
но для Playwright он VISIBLE (ненулевой bounding box) и кликабельный.

НАХОДКА 3: признаки disabled разложены по ДВУМ уровням:
  * на родителе input (span.MuiSwitch-switchBase) — aria-disabled="true",
    tabindex="-1", класс Mui-disabled;
  * на самом input — атрибут disabled.
  Проверять нужно оба; allow_edit_switch_base_locator() отдаёт родителя
  структурно (xpath=.. от найденного input), без опоры на MUI-класс.

ЛОВУШКА ВЗАИМОДЕЙСТВИЯ: обычный toggle_allow_edit() кликает чекбокс; на
disabled-элементе Playwright auto-waiting ждёт enabled до дефолтных 30с и
тест висит. Для доказательства "недоступен для взаимодействия" (REMCL-1335)
добавлен try_toggle_allow_edit() — best-effort клик с КОРОТКИМ таймаутом,
возвращает bool, не бросает.

--- Linked item ---
НАХОДКА 1 (2026-11-25): при создании из задачи поле задачи предзаполнено И
ЗАБЛОКИРОВАНО. РЕШЕНИЕ ПОЛЬЗОВАТЕЛЯ (2026-11-25): REMCL-1046/1053/1054/1055
отложены до реализации открытия формы НЕ из задачи; факт блокировки закреплён
тестом-стражем.
ИСПРАВЛЕНО (2026-11-25): обёртку <span data-testid="condition-button-disabled">
в актуальной сборке убрали — локатор по префиксу testid не находил ничего.
Кнопка Condition ищется по роли + accessible name ("Condition").
aria-haspopup="dialog" в одиночку НЕ годится — тот же атрибут у "Choose date".

--- Condition / JQL: попап ---
Подтверждено разметкой окна (2026-11-25):
* контейнер — <div role="dialog" aria-label="Condition"> ВНУТРИ того же iframe;
* поле JQL — Atlaskit JQL-editor на ProseMirror:
  <div contenteditable="true" data-testid="jql-editor-input" role="combobox"
       aria-label="JQL query" class="ProseMirror"><p><br></p></div>
  → input_value() на нём БРОСАЕТ ошибку, значение читается text_content();
* плейсхолдера "Enter valid JQL" на форме НЕТ; вместо него подсказка
  "Enter to add a new line" и примечание role="note";
* маркер валидации — data-testid="jql-validation-tooltip";
* автокомплит — data-testid="jql-editor-autocomplete" с <ul role="listbox">.

ИСПРАВЛЕНО (2026-11-27, по решению пользователя — пересматривает решение от
2026-11-25): требование про ПХ "Enter valid JQL" УДАЛЕНО из тест-кейсов,
соответствующий тест-расхождение удалён пользователем. Константа
JQL_PLACEHOLDER_TEXT убрана, get_jql_placeholder() оставлен ТОЛЬКО как
диагностика (см. его докстринг) — это не забытый TODO, а осознанный разворот.

ИСПРАВЛЕНО (2026-11-25, по падению test_invalid_jql_disables_create — три
независимые причины, все три исправлены):
1. ГОНКА СОСТОЯНИЯ Create. Валидация JQL асинхронная (в попапе есть
   role="status" aria-live="polite" и jql-validation-tooltip), Create
   дизейблится не в тот же тик. Одноразовый is_create_enabled() ловил
   "ещё активна" → добавлен create_button_locator() для auto-retrying
   expect(...).to_be_disabled().
2. Escape ОТМЕНЯЛ ЧЕРНОВИК. close_condition() теперь сначала клик ВНЕ попапа
   (до двух попыток), Escape — только последний резерв.
3. insert_text() НЕ ШЛЁТ КЛАВИАТУРНЫХ СОБЫТИЙ. fill_jql() переведён на
   press_sequentially() с задержкой JQL_TYPING_DELAY_MS.

ТЕХНИЧЕСКИЙ РИСК (остался): committing-способ закрытия попапа Condition по
разметке не определить (кнопок Save/Close внутри нет) — порядок "клик вне,
потом Escape" обоснованная гипотеза. Содержимое jql-validation-tooltip при
невалидном JQL не снято.
"""
from __future__ import annotations

import re
from datetime import datetime

from playwright.sync_api import FrameLocator, Locator, Page

from pages.components.message_editor import MessageEditor
from pages.components.notification import FLAG_KIND_ERROR, Notification

DIALOG_HEADING_RE = re.compile(r"^New reminder$")

DATE_TIME_LABEL_RE = re.compile(r"^Date & time\s*\*?\s*$")
RECIPIENTS_LABEL_RE = re.compile(r"^Recipients\s*\*?\s*$")

PLACEHOLDER_RE = re.compile(r"Type to search users or groups", re.IGNORECASE)
PLACEHOLDER_TEXT = "Type to search users or groups…"

TOOLTIP_TEXT = (
    "If you have the necessary permissions, you can select Jira groups or roles"
)

REQUIRED_ERROR_TEXT = "At least one recipient should be selected"
NO_RESULTS_TEXT = "No recipients found"

ACCESS_ERROR_SUFFIX = (
    "don't have permission to view the work item. Unselect them to create reminder."
)
ACCESS_ERROR_SUFFIX_RE = re.compile(
    r"don.t have permission to view the work item.\s*"
    r"Unselect them to create reminder.",
    re.IGNORECASE,
)

USERS_SECTION_HEADER = "Users"
GROUPS_SECTION_HEADER = "Groups"

# --- Блок When ---
WHEN_OPTION_SPECIFIC_DATE = "Specific date"
WHEN_OPTION_AT_DUE_DATE = "At Due Date"
WHEN_OPTION_BEFORE_DUE_DATE = "Before Due Date"
WHEN_OPTION_AFTER_DUE_DATE = "After Due Date"
WHEN_LABEL_RE = re.compile(r"^When\s*\*?\s*$")

DATE_TIME_EMPTY_ERROR_RE = re.compile(
    r"Date\s*&\s*time\s+can.t\s+be\s+empty\.?", re.IGNORECASE
)
DATE_TIME_PAST_ERROR_RE = re.compile(
    r"Selected\s+date\s*&\s*time\s+can.t\s+be\s+in\s+the\s+past\.?", re.IGNORECASE
)

# --- Настройки повторения ---
REPEAT_FREQUENCY_LABEL = "Frequency"

# --- Message ---
MESSAGE_LENGTH_ERROR_TEXT = "Message must not exceed 255 characters"

# --- Privacy ---
PRIVACY_OPTION_PRIVATE = "Private"
PRIVACY_OPTION_PUBLIC = "Public"
PRIVACY_LABEL_RE = re.compile(r"^Privacy\s*\*?\s*$")
PRIVACY_TOOLTIP_TEXT = (
    "Privacy defines who can see and manage the reminder: the creator always "
    "has full access, recipients can see assigned reminders, private reminders "
    "are editable only if the creator allows it, and non-private ones follow "
    "app permission settings."
)
PRIVACY_REQUIRED_ERROR_TEXT = "Privacy level is required"

# --- Allow edit (добавлено 2026-11-27) ---
ALLOW_EDIT_LABEL_TEXT = "Allow edit"
# Дословный текст тултипа из REMCL-1020 — ПОДТВЕРЖДЁН разметкой disabled-
# состояния (aria-label на контейнере), не угадан.
ALLOW_EDIT_DISABLED_TOOLTIP_TEXT = (
    "Editing of public reminders is controlled by project-level permissions."
)

# --- Linked item ---
LINKED_ITEM_LABEL_RE = re.compile(r"^Linked item\s*\*?\s*$")
LINKED_TYPE_WORK_ITEM = "Work item"
LINKED_TYPE_LINK = "Link"

LINK_URL_PLACEHOLDER_RE = re.compile(r"Enter a link", re.IGNORECASE)
LINK_URL_PLACEHOLDER_TEXT = "Enter a link, such as https://example.com"

LINKED_WORK_ITEM_NOT_FOUND_ERROR_RE = re.compile(
    r"Can.t find .+Try searching for another work item", re.IGNORECASE
)

INVALID_URL_ERROR_RE = re.compile(
    r"Invalid\s+URL\.?\s*Enter\s+the\s+full\s+website\s+address", re.IGNORECASE
)
INVALID_URL_ERROR_TEXT = (
    "Invalid URL. Enter the full website address, including http:// or "
    "https://, for example: https://example.com"
)

# --- Condition / JQL ---
_CONDITION_BUTTON_NAME = re.compile(r"^Condition$", re.IGNORECASE)
JQL_DIALOG_NAME_RE = re.compile(r"^Condition$", re.IGNORECASE)
JQL_HINT_TEXT = "Enter to add a new line"
JQL_NOTE_TEXT = (
    "Reminder is sent only if the work item matches the JQL condition at send time"
)
CONDITION_TOOLTIP_NOT_LINKED_TEXT = (
    "JQL conditions are only available for reminders linked to a work item"
)
CONDITION_TOOLTIP_NO_ADVANCED_TEXT = (
    "JQL conditions are available only with an active Advanced subscription. "
    "Please contact your administrator to enable it"
)
JQL_TYPING_DELAY_MS = 30

_PORTAL_LAYER_SELECTORS = (
    "[role='dialog']",
    ".MuiModal-root",
    ".MuiPopover-root",
    ".MuiPopper-root",
)


class ReminderModal:
    """Компонент: модалка "New reminder" (создание/редактирование ремайндера)."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self._dialog: Locator = page.get_by_role("dialog")
        self.frame: FrameLocator = self._dialog.frame_locator("iframe")

        self.message: MessageEditor = MessageEditor(self.frame, self._dialog)

        # --- Recipients ---
        self._recipients_label: Locator = self.frame.get_by_text(RECIPIENTS_LABEL_RE)
        self._recipients_tooltip_icon: Locator = self._recipients_label.locator(
            "xpath=following-sibling::*[last()]"
        )
        self._field: Locator = self._recipients_label.locator(
            "xpath=ancestor::*[.//input][1]"
        )
        self._search_input: Locator = self._field.locator("input").first
        self._clear_all_button: Locator = self._field.get_by_role(
            "button", name=re.compile("clear", re.IGNORECASE)
        )
        self._options_listbox: Locator = self.frame.get_by_role("listbox")
        self._required_error: Locator = self.frame.get_by_text(
            REQUIRED_ERROR_TEXT, exact=True
        )
        self._no_results: Locator = self.frame.get_by_text(NO_RESULTS_TEXT, exact=True)
        self._access_error: Locator = self.frame.get_by_text(ACCESS_ERROR_SUFFIX_RE)
        self._create_button: Locator = self.frame.get_by_role(
            "button", name=re.compile(r"^Create$")
        )

        # --- Date & time ---
        self._date_time_label: Locator = self.frame.get_by_text(DATE_TIME_LABEL_RE)
        self._date_time_container: Locator = self.frame.locator(
            "[data-testid='when-specific-date']"
        )
        self._date_time_field: Locator = self._date_time_container.locator("input").first
        self._date_time_open_button: Locator = self._date_time_container.get_by_role(
            "button", name=re.compile("Choose date", re.IGNORECASE)
        )
        self._date_time_clear_button: Locator = self._date_time_container.get_by_role(
            "button", name=re.compile("Clear", re.IGNORECASE)
        )
        self._timezone_container: Locator = self._date_time_label.locator(
            "xpath=ancestor::*[.//a][1]"
        )
        self._date_time_error_empty: Locator = self.frame.get_by_text(
            DATE_TIME_EMPTY_ERROR_RE
        )
        self._date_time_error_past: Locator = self.frame.get_by_text(
            DATE_TIME_PAST_ERROR_RE
        )

        # --- Поле When ---
        self._when_label: Locator = self.frame.get_by_text(WHEN_LABEL_RE)
        self._when_combobox: Locator = self._when_label.locator(
            "xpath=following::*[@role='combobox'][1]"
        )

        # --- Toggle Repeat ---
        self._repeat_container: Locator = self.frame.locator("[data-testid='when-repeat']")
        self._repeat_checkbox: Locator = self._repeat_container.locator(
            "input[type='checkbox']"
        ).first

        # --- Privacy ---
        self._privacy_label: Locator = self.frame.get_by_text(PRIVACY_LABEL_RE)
        self._privacy_combobox: Locator = self._privacy_label.locator(
            "xpath=following::*[@role='combobox'][1]"
        )
        self._privacy_tooltip_icon: Locator = self._privacy_label.locator(
            "xpath=following-sibling::*[last()]"
        )
        self._privacy_options_listbox: Locator = self.frame.get_by_role("listbox")
        self._privacy_error: Locator = self.frame.get_by_text(
            PRIVACY_REQUIRED_ERROR_TEXT, exact=True
        )

        # --- Allow edit ---
        self._allow_edit_container: Locator = self.frame.locator(
            "[data-testid='allow-edit-toggle']"
        )
        self._allow_edit_checkbox: Locator = self._allow_edit_container.locator(
            "input[type='checkbox']"
        ).first
        self._allow_edit_label: Locator = self.frame.get_by_text(
            re.compile(rf"^{ALLOW_EDIT_LABEL_TEXT}\s*$")
        )
        # Обёртка switchBase — родитель input (там aria-disabled/tabindex=-1).
        # Структурная навигация от найденного элемента, не опора на MUI-класс.
        self._allow_edit_switch_base: Locator = self._allow_edit_checkbox.locator(
            "xpath=.."
        )

        # --- Linked item ---
        self._linked_item_label: Locator = self.frame.get_by_text(LINKED_ITEM_LABEL_RE)
        self._linked_type_combobox: Locator = self._linked_item_label.locator(
            "xpath=following::*[@role='combobox'][1]"
        )
        self._work_item_container: Locator = self.frame.locator(
            "[data-testid='reminder-work-item']"
        )
        self._work_item_combobox: Locator = self._work_item_container.get_by_role(
            "combobox"
        )
        self._link_url_input: Locator = self.frame.get_by_placeholder(
            LINK_URL_PLACEHOLDER_RE
        )

        # --- Condition / JQL ---
        self._condition_button: Locator = self.frame.get_by_role(
            "button", name=_CONDITION_BUTTON_NAME
        )
        self._condition_wrapper: Locator = self._condition_button.locator(
            "xpath=ancestor::*[@data-testid][1]"
        )
        self._condition_dialog: Locator = self.frame.get_by_role(
            "dialog", name=JQL_DIALOG_NAME_RE
        )
        self._jql_input: Locator = self.frame.locator("[data-testid='jql-editor-input']")
        self._jql_validation_tooltip: Locator = self.frame.locator(
            "[data-testid='jql-validation-tooltip']"
        )
        self._jql_note: Locator = self._condition_dialog.get_by_role("note")

    def wait_until_ready(self, timeout_ms: int = 15_000) -> None:
        """Дожидается реального рендера формы (заголовок ищется ВНУТРИ frame)."""
        self.frame.get_by_role("heading", name=DIALOG_HEADING_RE).wait_for(
            state="visible", timeout=timeout_ms
        )
        self._recipients_label.wait_for(state="visible", timeout=timeout_ms)

    # ==================== Recipients ====================

    def open_dropdown(self) -> None:
        """Кликает по полю Recipients, открывая список опций."""
        self._search_input.click()

    def search(self, text: str) -> None:
        """Вводит текст в поиск Recipients (поиск серверный)."""
        self.open_dropdown()
        self._search_input.fill(text)

    def wait_for_search_to_settle(self, timeout_ms: int = 10_000) -> None:
        """Ждёт исчезновения "Loading..." (сначала коротко ждём появления)."""
        loading = self.frame.get_by_text("Loading...", exact=True)
        try:
            loading.wait_for(state="visible", timeout=1_000)
        except Exception:
            pass
        try:
            loading.wait_for(state="hidden", timeout=timeout_ms)
        except Exception:
            pass

    def option(self, name: str) -> Locator:
        """
        Локатор опции Recipients по видимому тексту.
        ВНИМАНИЕ: при открытом попапе Condition в iframe есть второй listbox
        (JQL-автокомплит) — закрывайте Condition перед работой с Recipients.
        """
        return self._options_listbox.get_by_role(
            "option", name=re.compile(re.escape(name))
        )

    def select(self, name: str) -> None:
        """Выбирает (или снимает выбор) опцию по видимому тексту."""
        self.option(name).click()

    def option_in_users_section(self, name: str) -> Locator:
        """Первое совпадение в DOM-порядке — опция из секции Users."""
        return self.option(name).first

    def select_in_users_section(self, name: str) -> None:
        """Выбирает опцию строго из секции Users."""
        self.option_in_users_section(name).click()

    def toggle_via_keyboard(self, times_down: int, key: str = "Enter") -> None:
        """ArrowDown times_down раз, затем key."""
        for _ in range(times_down):
            self.page.keyboard.press("ArrowDown")
        self.page.keyboard.press(key)

    def remove_tag(self, name: str) -> None:
        """Удаляет recipient по тегу: чип по точному тексту → вложенная кнопка."""
        tag_text = self._field.get_by_text(re.compile(rf"^{re.escape(name)}$"))
        chip = tag_text.locator("xpath=ancestor::*[@role='button'][1]")
        chip.get_by_role("button").click()

    def clear_all(self) -> None:
        """Очищает поле Recipients одной кнопкой."""
        self._clear_all_button.click()

    def selected_tags(self) -> list[str]:
        """Тексты выбранных тегов (placeholder-реализация, см. риск)."""
        tags = self._field.locator("[role='button']")
        return [t.strip() for t in tags.all_text_contents() if t.strip()]

    def is_placeholder_visible(self, timeout_ms: int = 3_000) -> bool:
        try:
            self.frame.get_by_placeholder(PLACEHOLDER_RE).wait_for(
                state="visible", timeout=timeout_ms
            )
            return True
        except Exception:
            return False

    def placeholder_text(self, timeout_ms: int = 3_000) -> str | None:
        """Точный текст плейсхолдера инпута Recipients."""
        try:
            self._search_input.wait_for(state="visible", timeout=timeout_ms)
            return self._search_input.get_attribute("placeholder")
        except Exception:
            return None

    def is_clear_all_visible(self, timeout_ms: int = 3_000) -> bool:
        try:
            self._clear_all_button.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def has_required_error(self, timeout_ms: int = 5_000) -> bool:
        try:
            self._required_error.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def has_no_results_message(self, timeout_ms: int = 10_000) -> bool:
        try:
            self._no_results.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def access_error_text(self, timeout_ms: int = 5_000) -> str | None:
        """ОДНОКРАТНЫЙ снимок текста ошибки про доступ; для проверок — locator."""
        try:
            self._access_error.wait_for(state="visible", timeout=timeout_ms)
            return self._access_error.text_content()
        except Exception:
            return None

    def has_access_error(self, timeout_ms: int = 5_000) -> bool:
        try:
            self._access_error.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def access_error_locator(self) -> Locator:
        """Сырой Locator ошибки про доступ — для auto-retrying expect()."""
        return self._access_error

    def is_create_enabled(self) -> bool:
        """
        ОДНОКРАТНЫЙ снимок состояния кнопки Create.
        ВНИМАНИЕ (2026-11-25): для ПРОВЕРОК после действий использовать
        нельзя — состояние может меняться асинхронно. Используйте
        create_button_locator() + expect(...).to_be_disabled()/to_be_enabled().
        """
        return self._create_button.is_enabled()

    def create_button_locator(self) -> Locator:
        """Сырой Locator кнопки Create — для auto-retrying expect() в тесте."""
        return self._create_button

    def is_recipients_label_visible(self, timeout_ms: int = 5_000) -> bool:
        try:
            self._recipients_label.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def is_tooltip_icon_visible(self, timeout_ms: int = 5_000) -> bool:
        try:
            self._recipients_tooltip_icon.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def hover_tooltip_icon(self) -> None:
        self._recipients_tooltip_icon.hover()

    def tooltip_text(self, timeout_ms: int = 5_000) -> str | None:
        locator = self.frame.get_by_text(TOOLTIP_TEXT)
        try:
            locator.wait_for(state="visible", timeout=timeout_ms)
            return locator.text_content()
        except Exception:
            return None

    def is_field_focused(self) -> bool:
        """Фокус где-то внутри поля Recipients."""
        try:
            return self._field.evaluate("el => el.contains(document.activeElement)")
        except Exception:
            return False

    def is_users_section_visible(self, timeout_ms: int = 5_000) -> bool:
        try:
            self.frame.get_by_text(USERS_SECTION_HEADER, exact=True).wait_for(
                state="visible", timeout=timeout_ms
            )
            return True
        except Exception:
            return False

    def is_groups_section_visible(self, timeout_ms: int = 5_000) -> bool:
        try:
            self.frame.get_by_text(GROUPS_SECTION_HEADER, exact=True).wait_for(
                state="visible", timeout=timeout_ms
            )
            return True
        except Exception:
            return False

    def is_dropdown_open(self, timeout_ms: int = 2_000) -> bool:
        """Виден ли список опций Recipients."""
        try:
            self._options_listbox.first.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def close_dropdown_by_clicking_outside(self) -> None:
        """Закрывает дропдаун кликом по заголовку формы."""
        self.frame.get_by_role("heading", name=DIALOG_HEADING_RE).click()

    # ==================== Состояние модалки ====================

    def is_open(self, timeout_ms: int = 2_000) -> bool:
        try:
            self._dialog.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def is_closed(self, timeout_ms: int = 5_000) -> bool:
        try:
            self._dialog.wait_for(state="hidden", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def close(self) -> None:
        """Закрывает модалку кнопкой Cancel, не создавая ремайндер."""
        self.frame.get_by_role("button", name=re.compile(r"^Cancel$")).click()

    # ==================== Message / сабмит формы ====================

    _MESSAGE_LABEL_RE = re.compile(r"^Message\s*\*?\s*$")

    def fill_message(self, text: str) -> None:
        """Вводит текст в поле Message (делегирует в MessageEditor.fill)."""
        self.message.fill(text)

    def submit(self, settle_timeout_ms: int = 20_000) -> None:
        """
        Нажимает Create, затем best-effort ждёт закрытия модалки.
        При ОШИБКЕ модалка не закрывается — для негативных сценариев вызывать
        submit(settle_timeout_ms=500), иначе ожидание съест окно жизни флага.
        """
        self._create_button.click()
        self.is_closed(timeout_ms=settle_timeout_ms)

    def is_message_length_error_visible(self, timeout_ms: int = 3_000) -> bool:
        """Видимость ошибки "Message must not exceed 255 characters"."""
        try:
            self.frame.get_by_text(MESSAGE_LENGTH_ERROR_TEXT, exact=True).wait_for(
                state="visible", timeout=timeout_ms
            )
            return True
        except Exception:
            return False

    # ==================== Date & time ====================

    def open_date_time_picker(self) -> None:
        """Открывает инлайн-попап календаря кликом по полю."""
        self._date_time_field.click()

    def close_date_time_picker(self) -> None:
        """Закрывает попап календаря нажатием Escape."""
        self.page.keyboard.press("Escape")

    def select_calendar_day(self, day: int) -> None:
        """Кликает по дню в ОТКРЫТОМ попапе (текущий показанный месяц)."""
        self.frame.get_by_role("gridcell", name=str(day), exact=True).click()

    def select_hour(self, hour: int) -> None:
        """Кликает по часу (двузначный текст с ведущим нулём)."""
        hours_list = self.frame.get_by_role(
            "listbox", name=re.compile("hour", re.IGNORECASE)
        )
        hours_list.get_by_text(f"{hour:02d}", exact=True).click()

    def select_minute(self, minute: int) -> None:
        """Кликает по минуте; minute ОБЯЗАН быть кратен 5 (ограничение UI)."""
        if minute % 5 != 0:
            raise ValueError(
                f"minute={minute} не кратно 5 — поле Date & time позволяет "
                "выбрать минуту только с шагом 5 (00, 05, ..., 55). Округлите "
                "целевое время ПЕРЕД вызовом "
                "(utils.time_helpers.round_up_to_next_five_minutes)."
            )
        minutes_list = self.frame.get_by_role(
            "listbox", name=re.compile("minute", re.IGNORECASE)
        )
        minutes_list.get_by_text(f"{minute:02d}", exact=True).click()

    def set_specific_datetime(self, value: datetime) -> None:
        """Выставляет день текущего месяца, час и минуту (минута кратна 5)."""
        if value.minute % 5 != 0:
            raise ValueError(
                f"value.minute={value.minute} не кратно 5 — см. select_minute()."
            )
        self.open_date_time_picker()
        self.select_calendar_day(value.day)
        self.select_hour(value.hour)
        self.select_minute(value.minute)

    def date_time_field_text(self, timeout_ms: int = 5_000) -> str | None:
        """Значение поля Date & time (input_value(), поле — <input>)."""
        try:
            self._date_time_field.wait_for(state="visible", timeout=timeout_ms)
            return self._date_time_field.input_value()
        except Exception:
            return None

    def clear_date_time(self) -> None:
        """Очищает поле кнопкой-крестиком (aria-label="Clear")."""
        self._date_time_clear_button.click()

    def is_date_time_visible(self, timeout_ms: int = 3_000) -> bool:
        try:
            self._date_time_field.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def is_date_time_empty_error_visible(self, timeout_ms: int = 5_000) -> bool:
        try:
            self._date_time_error_empty.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def is_past_date_error_visible(self, timeout_ms: int = 5_000) -> bool:
        try:
            self._date_time_error_past.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def get_timezone_text(self, timeout_ms: int = 3_000) -> str | None:
        """Текст подсказки таймзоны над полем."""
        try:
            self._timezone_container.wait_for(state="visible", timeout=timeout_ms)
            return self._timezone_container.text_content()
        except Exception:
            return None

    def is_hour_visible(self, hour: int, timeout_ms: int = 3_000) -> bool:
        try:
            hours_list = self.frame.get_by_role(
                "listbox", name=re.compile("hour", re.IGNORECASE)
            )
            hours_list.get_by_text(f"{hour:02d}", exact=True).wait_for(
                state="visible", timeout=timeout_ms
            )
            return True
        except Exception:
            return False

    def is_minute_visible(self, minute: int, timeout_ms: int = 3_000) -> bool:
        try:
            minutes_list = self.frame.get_by_role(
                "listbox", name=re.compile("minute", re.IGNORECASE)
            )
            minutes_list.get_by_text(f"{minute:02d}", exact=True).wait_for(
                state="visible", timeout=timeout_ms
            )
            return True
        except Exception:
            return False

    def get_date_time_label_text(self, timeout_ms: int = 3_000) -> str | None:
        """Текст лейбла Date & time (REMCL-1122 — проверка звёздочки)."""
        try:
            self._date_time_label.wait_for(state="visible", timeout=timeout_ms)
            return self._date_time_label.text_content()
        except Exception:
            return None

    # ==================== Поле When ====================

    def is_when_dropdown_open(self) -> bool:
        """Открыт ли дропдаун When — по aria-expanded на combobox."""
        try:
            return self._when_combobox.get_attribute("aria-expanded") == "true"
        except Exception:
            return False

    def open_when_dropdown_by_keyboard(self) -> None:
        """Фокус на combobox + ОДИН Space (второй дал бы "No options")."""
        self._when_combobox.focus()
        self.page.keyboard.press("Space")

    def open_when_dropdown(self) -> None:
        """Открывает дропдаун When кликом."""
        self._when_combobox.click()

    def tab_to_when_and_open_dropdown(self, max_tabs: int = 10) -> None:
        """Tab от Recipients до combobox When, затем Space."""
        self._search_input.focus()
        for _ in range(max_tabs):
            self.page.keyboard.press("Tab")
            if self._when_combobox.evaluate("el => el === document.activeElement"):
                break
        self.page.keyboard.press("Space")

    def select_when_option(self, option: str) -> None:
        """Выбирает опцию When (регистронезависимый поиск)."""
        self._when_combobox.click()
        self.frame.get_by_role(
            "option", name=re.compile(re.escape(option), re.IGNORECASE)
        ).click()

    def get_when_value(self) -> str:
        return self._when_combobox.input_value()

    def is_when_option_visible(self, option: str, timeout_ms: int = 3_000) -> bool:
        """Видимость опции в ОТКРЫТОМ дропдауне When (сам не открывает)."""
        try:
            self.frame.get_by_role(
                "option", name=re.compile(re.escape(option), re.IGNORECASE)
            ).wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def is_when_option_disabled(self, option: str, timeout_ms: int = 3_000) -> bool:
        """Задизейблена ли опция When; закрывает дропдаун Escape в finally."""
        self._when_combobox.click()
        try:
            opt = self.frame.get_by_role(
                "option", name=re.compile(re.escape(option), re.IGNORECASE)
            )
            opt.wait_for(state="visible", timeout=timeout_ms)
            return opt.get_attribute("aria-disabled") == "true"
        finally:
            self.page.keyboard.press("Escape")

    # ==================== Toggle Repeat ====================

    def is_repeat_visible(self, timeout_ms: int = 3_000) -> bool:
        try:
            self._repeat_container.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def is_repeat_on(self) -> bool:
        return self._repeat_checkbox.is_checked()

    def toggle_repeat(self, on: bool) -> None:
        """Переключает Repeat, только если текущее состояние отличается."""
        if self.is_repeat_on() != on:
            self._repeat_checkbox.click()

    # ==================== Настройки повторения ====================

    def is_repeat_settings_visible(self, timeout_ms: int = 5_000) -> bool:
        """Видимость блока настроек по лейблу "Frequency"."""
        try:
            self.frame.get_by_text(
                re.compile(rf"^{REPEAT_FREQUENCY_LABEL}$")
            ).wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def get_repeat_frequency_value(self, timeout_ms: int = 3_000) -> str | None:
        """Значение числового поля Frequency (inputmode="numeric")."""
        locator = self.frame.locator("input[inputmode='numeric']").first
        try:
            locator.wait_for(state="visible", timeout=timeout_ms)
            return locator.input_value()
        except Exception:
            return None

    def set_repeat_frequency(self, value: int, timeout_ms: int = 3_000) -> None:
        locator = self.frame.locator("input[inputmode='numeric']").first
        locator.wait_for(state="visible", timeout=timeout_ms)
        locator.fill(str(value))

    def is_repeat_ends_on(self, timeout_ms: int = 3_000) -> bool:
        locator = self.frame.locator(
            "[data-testid='repeat-ends'] input[type='checkbox']"
        ).first
        try:
            locator.wait_for(state="attached", timeout=timeout_ms)
            return locator.is_checked()
        except Exception:
            return False

    def toggle_repeat_ends(self, on: bool, timeout_ms: int = 3_000) -> None:
        locator = self.frame.locator(
            "[data-testid='repeat-ends'] input[type='checkbox']"
        ).first
        locator.wait_for(state="visible", timeout=timeout_ms)
        if locator.is_checked() != on:
            locator.click()

    def get_repeat_end_date(self, timeout_ms: int = 3_000) -> str | None:
        locator = self.frame.locator("[data-testid='repeat-end-date'] input").first
        try:
            locator.wait_for(state="visible", timeout=timeout_ms)
            return locator.input_value()
        except Exception:
            return None

    # ==================== Privacy ====================

    def open_privacy_dropdown(self) -> None:
        self._privacy_combobox.click()

    def select_privacy_option(self, option: str) -> None:
        """Выбирает Private/Public (дропдаун Recipients должен быть закрыт)."""
        self._privacy_combobox.click()
        self.frame.get_by_role(
            "option", name=re.compile(re.escape(option), re.IGNORECASE)
        ).click()

    def get_privacy_value(self) -> str:
        return self._privacy_combobox.input_value()

    def privacy_combobox_locator(self) -> Locator:
        """
        Сырой Locator комбобокса Privacy — для expect()/bounding_box() в тесте.
        ДОБАВЛЕНО (2026-11-27) для проверки взаимного расположения Privacy и
        Allow edit (REMCL-1333), чтобы тест не лез в приватный атрибут.
        """
        return self._privacy_combobox

    def is_privacy_dropdown_open(self) -> bool:
        try:
            return self._privacy_combobox.get_attribute("aria-expanded") == "true"
        except Exception:
            return False

    def is_privacy_option_visible(self, option: str, timeout_ms: int = 3_000) -> bool:
        try:
            self.frame.get_by_role(
                "option", name=re.compile(re.escape(option), re.IGNORECASE)
            ).wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def get_privacy_tooltip_text(self, timeout_ms: int = 3_000) -> str | None:
        """
        Текст тултипа Privacy: СНАЧАЛА aria-label на обёртке иконки
        (подтверждено живым прогоном), hover-поиск — фоллбек.
        """
        try:
            self._privacy_tooltip_icon.wait_for(state="visible", timeout=timeout_ms)
            label = self._privacy_tooltip_icon.get_attribute("aria-label")
            if label:
                return label
        except Exception:
            pass
        try:
            self._privacy_tooltip_icon.hover()
            tooltip = self.page.get_by_role("tooltip")
            tooltip.wait_for(state="visible", timeout=timeout_ms)
            return tooltip.text_content()
        except Exception:
            return None

    def is_privacy_visible(self, timeout_ms: int = 3_000) -> bool:
        """Видимость Privacy (появляется только при стороннем получателе)."""
        try:
            self._privacy_label.wait_for(state="visible", timeout=timeout_ms)
            self._privacy_combobox.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def is_privacy_error_visible(self, timeout_ms: int = 3_000) -> bool:
        try:
            self._privacy_error.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def tab_to_privacy(self, max_tabs: int = 20) -> int | None:
        """Tab от Recipients до combobox Privacy; число нажатий либо None."""
        self._search_input.focus()
        for tab_count in range(1, max_tabs + 1):
            self.page.keyboard.press("Tab")
            if self._privacy_combobox.evaluate("el => el === document.activeElement"):
                return tab_count
        return None

    # ==================== Allow edit ====================

    def is_allow_edit_visible(self, timeout_ms: int = 3_000) -> bool:
        """Видимость тоггла Allow edit (контейнер + лейбл)."""
        try:
            self._allow_edit_container.wait_for(state="visible", timeout=timeout_ms)
            self._allow_edit_label.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def is_allow_edit_on(self) -> bool:
        """
        ОДНОКРАТНЫЙ снимок состояния тоггла. Для ПРОВЕРОК после действия
        используйте allow_edit_checkbox_locator() + expect().to_be_checked().
        """
        return self._allow_edit_checkbox.is_checked()

    def is_allow_edit_disabled(self) -> bool:
        """Задизейблен ли input тоггла (Privacy = Public)."""
        return self._allow_edit_checkbox.is_disabled()

    def toggle_allow_edit(self, on: bool) -> None:
        """
        Переключает тоггл кликом, только если состояние отличается.

        ВНИМАНИЕ: на DISABLED-тоггле (Privacy = Public) этот метод зависнет на
        auto-waiting Playwright до дефолтных 30с. Для проверки
        "недоступен для взаимодействия" используйте try_toggle_allow_edit().
        """
        if self.is_allow_edit_on() != on:
            self._allow_edit_checkbox.click()

    def try_toggle_allow_edit(self, timeout_ms: int = 1_500) -> bool:
        """
        Best-effort клик по тогглу с КОРОТКИМ таймаутом; True если клик прошёл.

        ДОБАВЛЕНО (2026-11-27) для REMCL-1335 ("недоступен для
        взаимодействия"): обычный toggle_allow_edit() на disabled-элементе
        ждёт enabled до дефолтных 30с и вешает тест. Этот метод не бросает и
        позволяет тесту доказать неинтерактивность за полторы секунды.
        """
        try:
            self._allow_edit_checkbox.click(timeout=timeout_ms)
            return True
        except Exception:
            return False

    def allow_edit_container_locator(self) -> Locator:
        """
        Сырой Locator контейнера тоггла (data-testid="allow-edit-toggle").
        На НЁМ лежит aria-label с тултипом (см. находку 1 в докстринге).
        """
        return self._allow_edit_container

    def allow_edit_checkbox_locator(self) -> Locator:
        """Сырой Locator чекбокса — для expect().to_be_checked()/to_be_focused()."""
        return self._allow_edit_checkbox

    def allow_edit_label_locator(self) -> Locator:
        """Сырой Locator лейбла "Allow edit" — для проверки расположения."""
        return self._allow_edit_label

    def allow_edit_switch_base_locator(self) -> Locator:
        """
        Сырой Locator обёртки switchBase (родитель input) — на ней
        aria-disabled="true"/tabindex="-1" в disabled-состоянии (находка 3).
        """
        return self._allow_edit_switch_base

    def allow_edit_tooltip_text(self, timeout_ms: int = 3_000) -> str | None:
        """
        Текст тултипа Allow edit (REMCL-1020) либо None.

        Читает aria-label с КОНТЕЙНЕРА. В активном состоянии (Privacy=Private)
        атрибут ПУСТОЙ → возвращаем None (это ожидаемо, а не ошибка поиска).
        Hover не нужен — отдельного role="tooltip" элемента нет.
        """
        try:
            self._allow_edit_container.wait_for(state="visible", timeout=timeout_ms)
            label = self._allow_edit_container.get_attribute("aria-label")
            return label or None
        except Exception:
            return None

    def tab_to_allow_edit(self, max_tabs: int = 25) -> int | None:
        """
        Tab от Recipients до чекбокса Allow edit; число нажатий либо None.

        ПРЕДУСЛОВИЕ: Privacy = Private. При Public чекбокс disabled и
        tabindex=-1 — фокус на него не попадёт НИКОГДА, метод вернёт None
        (это корректное поведение, а не баг навигации).

        max_tabs больше, чем у tab_to_privacy (20): Allow edit идёт в
        tab-порядке ПОСЛЕ Privacy.
        """
        self._search_input.focus()
        for tab_count in range(1, max_tabs + 1):
            self.page.keyboard.press("Tab")
            if self._allow_edit_checkbox.evaluate(
                "el => el === document.activeElement"
            ):
                return tab_count
        return None

    def toggle_allow_edit_by_space(self) -> None:
        """
        Одно нажатие Space — переключает тоггл (REMCL-1337/1338).

        ПРЕДУСЛОВИЕ: фокус уже на чекбоксе (см. tab_to_allow_edit). Нативный
        checkbox реагирует на Space; метод намеренно НЕ фокусирует сам, чтобы
        тест проверял именно клавиатурный сценарий из кейса.
        """
        self.page.keyboard.press("Space")

    # ==================== Linked item ====================

    def is_linked_item_block_visible(self, timeout_ms: int = 3_000) -> bool:
        """Виден ли блок Linked item (лейбл + селект типа привязки)."""
        try:
            self._linked_item_label.wait_for(state="visible", timeout=timeout_ms)
            self._linked_type_combobox.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def get_linked_type_value(self) -> str:
        return self._linked_type_combobox.input_value()

    def open_linked_type_dropdown(self) -> None:
        self._linked_type_combobox.click()

    def is_linked_type_dropdown_open(self) -> bool:
        try:
            return self._linked_type_combobox.get_attribute("aria-expanded") == "true"
        except Exception:
            return False

    def is_linked_type_option_visible(
        self, option: str, timeout_ms: int = 3_000
    ) -> bool:
        """Видимость опции в ОТКРЫТОМ дропдауне типа привязки (regex заякорен)."""
        try:
            self.frame.get_by_role(
                "option", name=re.compile(rf"^{re.escape(option)}$", re.IGNORECASE)
            ).wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def select_linked_type(self, option: str) -> None:
        """Выбирает тип привязки ("Work item" / "Link")."""
        self._linked_type_combobox.click()
        self.frame.get_by_role(
            "option", name=re.compile(rf"^{re.escape(option)}$", re.IGNORECASE)
        ).click()

    def is_work_item_visible(self, timeout_ms: int = 3_000) -> bool:
        try:
            self._work_item_combobox.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def get_work_item_value(self, timeout_ms: int = 3_000) -> str | None:
        try:
            self._work_item_combobox.wait_for(state="visible", timeout=timeout_ms)
            return self._work_item_combobox.input_value()
        except Exception:
            return None

    def is_work_item_enabled(self) -> bool:
        """Редактируемо ли поле задачи (при создании из задачи — False)."""
        try:
            return self._work_item_combobox.is_enabled()
        except Exception:
            return False

    def is_link_url_input_visible(self, timeout_ms: int = 3_000) -> bool:
        try:
            self._link_url_input.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def get_link_url_placeholder(self, timeout_ms: int = 3_000) -> str | None:
        try:
            self._link_url_input.wait_for(state="visible", timeout=timeout_ms)
            return self._link_url_input.get_attribute("placeholder")
        except Exception:
            return None

    def fill_link_url(self, value: str) -> None:
        """Вводит URL (тип привязки должен быть "Link")."""
        self._link_url_input.fill(value)

    def get_link_url_value(self, timeout_ms: int = 3_000) -> str | None:
        try:
            self._link_url_input.wait_for(state="visible", timeout=timeout_ms)
            return self._link_url_input.input_value()
        except Exception:
            return None

    def invalid_url_error_text(self, timeout_ms: int = 3_000) -> str | None:
        """
        Текст ошибки невалидного URL (REMCL-2717) либо None.
        Ошибка — AtlasKit Flag хоста Jira в TOP-документе, живёт ~5с.
        Делегирует в Notification; для проверок предпочтительнее напрямую
        Notification.locator()/title_locator()/body_locator().
        """
        notification = Notification(self.page)
        if not notification.has_with_text(INVALID_URL_ERROR_RE, timeout_ms=timeout_ms):
            return None
        return notification.body(FLAG_KIND_ERROR)

    # ==================== Condition / JQL ====================

    def is_condition_visible(self, timeout_ms: int = 3_000) -> bool:
        """Видна ли кнопка Condition (в любом состоянии — active/disabled)."""
        try:
            self._condition_button.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def is_condition_enabled(self) -> bool:
        """Активна ли кнопка Condition (False также если не найдена)."""
        try:
            return self._condition_button.is_enabled()
        except Exception:
            return False

    def condition_wrapper_testid(self) -> str | None:
        """Диагностический data-testid рядом с кнопкой (в новой вёрстке None)."""
        for locator in (self._condition_wrapper, self._condition_button):
            try:
                value = locator.get_attribute("data-testid")
            except Exception:
                value = None
            if value:
                return value
        return None

    def condition_button_color(self) -> str | None:
        """CSS-цвет текста кнопки — диагностика "окрашена в красный"."""
        try:
            return self._condition_button.evaluate("el => getComputedStyle(el).color")
        except Exception:
            return None

    def condition_button_class(self) -> str | None:
        """class кнопки Condition (в открытом состоянии есть Mui-selected)."""
        try:
            return self._condition_button.get_attribute("class")
        except Exception:
            return None

    def get_condition_tooltip_text(self, timeout_ms: int = 4_000) -> str | None:
        """
        Текст тултипа кнопки Condition (REMCL-1060) либо None.
        Hover по ОБЁРТКЕ, если она есть (disabled-кнопка не получает
        mouse-событий), иначе по самой кнопке.
        """
        hover_target = self._condition_button
        try:
            if self._condition_wrapper.count() > 0:
                hover_target = self._condition_wrapper
        except Exception:
            pass

        for locator in (hover_target, self._condition_button):
            for attr in ("aria-label", "title"):
                try:
                    value = locator.get_attribute(attr)
                except Exception:
                    value = None
                if value and "condition" in value.lower():
                    return value

        try:
            hover_target.hover()
        except Exception:
            return None

        for scope in (self.frame, self.page):
            for candidate in (
                scope.get_by_role("tooltip"),
                scope.get_by_text(re.compile(r"JQL conditions", re.IGNORECASE)),
            ):
                try:
                    candidate.first.wait_for(state="visible", timeout=timeout_ms)
                    return candidate.first.text_content()
                except Exception:
                    continue
        return None

    def is_condition_open(self) -> bool:
        """Открыт ли попап Condition — aria-expanded на кнопке."""
        try:
            return self._condition_button.get_attribute("aria-expanded") == "true"
        except Exception:
            return False

    def open_condition(self) -> None:
        """Открывает попап Condition (предусловие: кнопка активна)."""
        self._condition_button.click()

    def close_condition(self) -> None:
        """
        Закрывает попап Condition КЛИКОМ ВНЕ его — по заголовку формы.
        Две попытки: первая может уйти на закрытие автокомплита JQL.
        Escape — только последний резерв (в редакторах он отменяет черновик).
        """
        heading = self.frame.get_by_role("heading", name=DIALOG_HEADING_RE)
        for _ in range(2):
            if not self.is_condition_open():
                return
            heading.click()
        if self.is_condition_open():
            self.page.keyboard.press("Escape")

    def is_condition_dialog_visible(self, timeout_ms: int = 3_000) -> bool:
        """Виден ли сам попап (role="dialog" aria-label="Condition")."""
        try:
            self._condition_dialog.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def is_jql_input_visible(self, timeout_ms: int = 3_000) -> bool:
        """Виден ли JQL-редактор (data-testid="jql-editor-input")."""
        try:
            self._jql_input.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def jql_input_locator(self) -> Locator:
        """
        Сырой Locator JQL-редактора — для auto-retrying expect() в тесте.
        Проверять, что запрос попал в редактор, нужно ДО закрытия попапа.
        """
        return self._jql_input

    def get_jql_placeholder(self, timeout_ms: int = 3_000) -> str | None:
        """
        Атрибут placeholder JQL-редактора — ДИАГНОСТИКА.

        ИСПРАВЛЕНО (2026-11-27, по решению пользователя): требование про ПХ
        "Enter valid JQL" удалено из тест-кейсов, тест-расхождение удалено.
        Метод оставлен только чтобы видеть в отчёте, что атрибута на форме
        нет (редактор — ProseMirror); фактическая подсказка читается
        jql_hint_text(). Никакого теста на этот атрибут больше нет.
        """
        try:
            self._jql_input.wait_for(state="visible", timeout=timeout_ms)
            return self._jql_input.get_attribute("placeholder")
        except Exception:
            return None

    def jql_hint_text(self, timeout_ms: int = 3_000) -> str | None:
        """Фактическая подсказка под редактором ("Enter to add a new line")."""
        try:
            hint = self._condition_dialog.get_by_text(JQL_HINT_TEXT, exact=False)
            hint.first.wait_for(state="visible", timeout=timeout_ms)
            return hint.first.text_content()
        except Exception:
            return None

    def jql_note_text(self, timeout_ms: int = 3_000) -> str | None:
        """Текст примечания role="note" в попапе Condition."""
        try:
            self._jql_note.wait_for(state="visible", timeout=timeout_ms)
            return self._jql_note.text_content()
        except Exception:
            return None

    def fill_jql(self, value: str) -> None:
        """
        Вводит JQL-условие (попап Condition должен быть открыт).
        ProseMirror: реальные клавиатурные события через press_sequentially,
        а не insert_text (он не шлёт keydown/keypress).
        """
        editor = self._jql_input
        editor.click()
        self.page.keyboard.press("ControlOrMeta+A")
        self.page.keyboard.press("Delete")
        if value:
            editor.press_sequentially(value, delay=JQL_TYPING_DELAY_MS)

    def clear_jql(self) -> None:
        """Очищает JQL-редактор (см. fill_jql про ProseMirror)."""
        self._jql_input.click()
        self.page.keyboard.press("ControlOrMeta+A")
        self.page.keyboard.press("Delete")

    def get_jql_value(self, timeout_ms: int = 3_000) -> str | None:
        """Текст JQL-условия. text_content(), НЕ input_value() (contenteditable)."""
        try:
            self._jql_input.wait_for(state="visible", timeout=timeout_ms)
            return (self._jql_input.text_content() or "").strip()
        except Exception:
            return None

    def jql_editor_html(self) -> str | None:
        """innerHTML JQL-редактора — диагностика (текст vs токены/пиллы)."""
        try:
            return self._jql_input.evaluate("el => el.innerHTML")
        except Exception:
            return None

    def jql_validation_message(self, timeout_ms: int = 2_000) -> str | None:
        """Текст валидации JQL (data-testid="jql-validation-tooltip") или None."""
        try:
            self._jql_validation_tooltip.wait_for(
                state="attached", timeout=timeout_ms
            )
            text = (self._jql_validation_tooltip.text_content() or "").strip()
            return text or None
        except Exception:
            return None

    def jql_validation_tooltip_html(self) -> str | None:
        """HTML контейнера валидации JQL — диагностика."""
        try:
            return self._jql_validation_tooltip.evaluate("el => el.outerHTML")
        except Exception:
            return None

    # ==================== Диагностика попапа Condition ====================

    def condition_popup_html(self, max_chars: int = 20_000) -> str:
        """
        HTML всех слоёв-порталов внутри iframe И в TOP-документе — для
        Allure-вложения. ТОЛЬКО диагностика.
        """
        chunks: list[str] = []
        for label, scope in (("iframe", self.frame), ("top", self.page)):
            for selector in _PORTAL_LAYER_SELECTORS:
                try:
                    locator = scope.locator(selector)
                    count = locator.count()
                except Exception:
                    continue
                for index in range(min(count, 3)):
                    try:
                        html = locator.nth(index).evaluate("el => el.outerHTML")
                    except Exception:
                        continue
                    chunks.append(
                        f"--- {label} :: {selector}[{index}] ---\n"
                        f"{html[:max_chars]}"
                    )
        return "\n\n".join(chunks) or (
            "Слоёв-порталов не найдено ни в iframe, ни в TOP-документе."
        )

    def form_field_placeholders(self) -> list[dict]:
        """Placeholder'ы всех input/textarea внутри iframe — диагностика."""
        try:
            return self.frame.locator("input, textarea").evaluate_all(
                """els => els.map(e => ({
                    tag: e.tagName,
                    type: e.getAttribute('type'),
                    placeholder: e.getAttribute('placeholder'),
                    id: e.id,
                    ariaLabel: e.getAttribute('aria-label'),
                }))"""
            )
        except Exception:
            return []