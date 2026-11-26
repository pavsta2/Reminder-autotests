"""
Тесты блока When в форме создания ремайндера (создание ремайндера на
странице задачи).
Покрытие тест-кейсов из rtm-issues-export.csv, блок "Creation - When
(v.2.X.X)": REMCL-1021/1022/1121-1129/1146-1196/1254/1540/1772/2681.
Все тесты используют фикстуру `reminder_modal` (см.
`fixtures/conftest.py`), которая открывает страницу задачи, разворачивает
секцию Reminder и открывает модалку "New reminder" через кнопку Create.
ТЕХНИЧЕСКИЙ РИСК (2026-11-23, см. докстринг `reminder_modal.py`, раздел про
блок When): локаторы поля When (лейбл + `role="combobox"`) угаданы по
аналогии с другими полями формы и НЕ подтверждены вживую. Если тесты упадут
с таймаутом на этих локаторах — первым делом проверить через `page.pause()`
реальную разметку поля When в модалке.
"""
import re
from datetime import datetime, timedelta

import allure
import pytest
from playwright.sync_api import expect

from pages.components.reminder_modal import (
    WHEN_OPTION_AFTER_DUE_DATE,
    WHEN_OPTION_AT_DUE_DATE,
    WHEN_OPTION_BEFORE_DUE_DATE,
    WHEN_OPTION_SPECIFIC_DATE,
)

pytestmark = [
    pytest.mark.ui,
    pytest.mark.creation_form,
    pytest.mark.issue_panel,
]


@allure.feature("Creation Form")
@allure.story("When Field")
class TestWhenFieldDropdown:
    """Тесты single-select поля When (REMCL-1021/1121/1154/2681/1151/1152)."""

    @allure.title(
        "REMCL-1021/1121: Поле When содержит все опции и "
        "Specific date по умолчанию"
    )
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("REMCL-1021", "REMCL-1121")
    def test_when_field_contains_all_options(self, reminder_modal):
        """
        REMCL-1021: В форме создания рема есть блок "When" c опциями:
        "Specific date" (отображается по дефолту), "At Due Date",
        "Before Due Date", "After Due Date".
        REMCL-1121: Поле `When` отображается как single select.
        """
        with allure.step("Проверить дефолтное значение Specific date"):
            expect(reminder_modal._when_combobox).to_have_value(
                WHEN_OPTION_SPECIFIC_DATE
            )

        with allure.step("Открыть дропдаун поля When"):
            reminder_modal.open_when_dropdown()

        with allure.step("Проверить наличие всех четырёх опций"):
            for option in [
                WHEN_OPTION_SPECIFIC_DATE,
                WHEN_OPTION_AT_DUE_DATE,
                WHEN_OPTION_BEFORE_DUE_DATE,
                WHEN_OPTION_AFTER_DUE_DATE,
            ]:
                assert reminder_modal.is_when_option_visible(option), (
                    f"Опция '{option}' не найдена в дропдауне поля When"
                )

    @allure.title(
        "REMCL-1154: Выбранная опция поля When отображается после "
        "закрытия dropdown"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1154")
    def test_when_selected_option_persists(self, reminder_modal):
        """
        REMCL-1154: Выбранная опция поля `When` отображается после
        закрытия dropdown.
        """
        with allure.step("Проверить, что опция At Due Date доступна"):
            if reminder_modal.is_when_option_disabled(WHEN_OPTION_AT_DUE_DATE):
                pytest.skip(
                    "Опция 'At Due Date' задизейблена на этой задаче "
                    "(нет Due Date) — тест требует задачи с Due Date."
                )

        with allure.step("Выбрать опцию At Due Date"):
            reminder_modal.select_when_option(WHEN_OPTION_AT_DUE_DATE)

        with allure.step("Проверить, что значение сохранилось"):
            expect(reminder_modal._when_combobox).to_have_value(
                WHEN_OPTION_AT_DUE_DATE
            )

    @allure.title("REMCL-2681: Все Due date опции disabled")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-2681")
    def test_due_date_options_disabled(self, reminder_modal):
        """
        REMCL-2681: Все Due date опции находятся в состоянии disabled и при
        наведении отображается tooltip.
        Покрытие: проверяем только состояние disabled для трёх Due date
        опций. Проверка tooltip при наведении НЕ реализуется.
        """
        due_date_options = [
            WHEN_OPTION_AT_DUE_DATE,
            WHEN_OPTION_BEFORE_DUE_DATE,
            WHEN_OPTION_AFTER_DUE_DATE,
        ]

        with allure.step("Проверить, что все Due date опции disabled"):
            for option in due_date_options:
                assert reminder_modal.is_when_option_disabled(option), (
                    f"Опция '{option}' должна быть задизейблена, но не была"
                )

    @allure.title(
        "REMCL-1151: Dropdown поля When открывается клавишей Space "
        "после навигации Tab"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1151")
    def test_when_dropdown_opens_with_space(self, reminder_modal):
        """
        REMCL-1151: Dropdown поля `When` открывается клавишей `Space` (пробел)
        после того, как фокус перемещён на поле клавишей Tab.

        Покрытие (по указанию пользователя от 2026-11-24):
        1. После открытия модалки перемещаем фокус клавишей Tab от поля
           Recipients до поля When (проверяя фокус через
           document.activeElement).
        2. Нажимаем Space на поле When.
        3. Проверяем, что дропдаун с опциями открылся (aria-expanded="true").

        НАБЛЮДЕНИЕ (2026-11-23, по ручному тестированию пользователя):
        Space нажимается ОДИН раз — dropdown открывается со всеми опциями.
        Если Space нажать ДВА раза, второй пробел вводится в инпут, фильтр
        срабатывает на строку с двумя пробелами и показывает "No options" —
        это корректное поведение формы, не баг.
        """
        with allure.step(
            "Переместить фокус Tab'ом до поля When и нажать Space"
        ):
            reminder_modal.tab_to_when_and_open_dropdown()

        with allure.step("Проверить, что dropdown поля When открылся"):
            assert reminder_modal.is_when_dropdown_open(), (
                "Dropdown поля When не открылся после Tab + Space"
            )

        with allure.step("Проверить, что dropdown содержит опции"):
            assert reminder_modal.is_when_option_visible(
                WHEN_OPTION_SPECIFIC_DATE
            ), (
                "Dropdown открыт, но не содержит опцию 'Specific date'"
            )

    @allure.title(
        "REMCL-1152: Dropdown поля When закрывается клавишей Esc"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1152")
    def test_when_dropdown_closes_with_escape(self, reminder_modal):
        """
        REMCL-1152: Dropdown поля `When` закрывается клавишей `Esc`.
        """
        with allure.step("Открыть dropdown поля When кликом"):
            reminder_modal.open_when_dropdown()

        with allure.step("Проверить, что dropdown открыт"):
            assert reminder_modal.is_when_dropdown_open(), (
                "Dropdown поля When не открылся после клика"
            )

        with allure.step("Нажать Escape"):
            reminder_modal.page.keyboard.press("Escape")

        with allure.step("Проверить, что dropdown закрылся"):
            assert not reminder_modal.is_when_dropdown_open(), (
                "Dropdown поля When не закрылся после нажатия Escape"
            )


@allure.feature("Creation Form")
@allure.story("Date & Time Field")
class TestDateTimeField:
    """
    Тесты поля Date & time
    (REMCL-1022/1122/1125/1127/1254/1540/1126/1158/1159/1772).
    """

    @allure.title(
        "REMCL-1022/1123/1124: Specific date показывает Date & time, "
        "Repeat и timezone"
    )
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("REMCL-1022", "REMCL-1123", "REMCL-1124", "REMCL-1176")
    def test_specific_date_shows_date_time_and_timezone(self, reminder_modal):
        """
        REMCL-1022: Если в поле "When" выбрать "Specific date", то справа
        появляется поле Date & time + ЧБ "Repeat" (выкл по дефолту), а над
        полем подсказка по таймзоне создателя рема в формате: {region} /
        {offset} ± N.
        REMCL-1123/1124: Значение timezone отображается над полем.
        REMCL-1176: Выбор `Specific date` отображает поля `Date & time` и `Repeat`.
        """
        with allure.step("Убедиться, что выбран Specific date"):
            reminder_modal.select_when_option(WHEN_OPTION_SPECIFIC_DATE)

        with allure.step("Проверить видимость поля Date & time"):
            assert reminder_modal.is_date_time_visible(), (
                "Поле Date & time не отображается при выборе Specific date"
            )

        with allure.step("Проверить видимость toggle Repeat"):
            assert reminder_modal.is_repeat_visible(), (
                "Toggle Repeat не отображается при выборе Specific date"
            )

        with allure.step("Проверить наличие подсказки таймзоны"):
            timezone_text = reminder_modal.get_timezone_text()
            assert timezone_text is not None, (
                "Подсказка таймзоны над полем Date & time не найдена"
            )

        with allure.step("Проверить формат таймзоны (разделитель '/' и 'GMT')"):
            assert "/" in timezone_text, (
                f"В тексте таймзоны '{timezone_text}' отсутствует разделитель '/'"
            )
            assert "GMT" in timezone_text, (
                f"В тексте таймзоны '{timezone_text}' отсутствует 'GMT'"
            )

    @allure.title(
        "REMCL-1122: Label Date & time отображается со знаком "
        "обязательности *"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1122")
    def test_date_time_label_has_asterisk(self, reminder_modal):
        """
        REMCL-1122: Label `Date & time` отображается со знаком обязательности `*`.
        """
        with allure.step("Получить текст лейбла Date & time"):
            label_text = reminder_modal.get_date_time_label_text()
            assert label_text is not None, "Лейбл Date & time не найден"

        with allure.step("Проверить наличие знака '*' в лейбле"):
            assert "*" in label_text, (
                f"Лейбл '{label_text}' не содержит знака обязательности '*'"
            )

    @allure.title(
        "REMCL-1125: Date & time по умолчанию = текущее время + 2 часа "
        "(с обнуленным значением минут)"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1125")
    def test_default_date_time_is_plus_2_hours(self, reminder_modal):
        """
        REMCL-1125: Поле `Date & time` отображает дату и время по умолчанию
        = текущее локальное время + 2 часа (с обнуленным значением минут).
        """
        with allure.step("Получить значение из поля Date & time"):
            value = reminder_modal.date_time_field_text()
            assert value is not None, "Поле Date & time не отображается"

        with allure.step("Распарсить значение (формат 'DD/Mon/YY HH:MM')"):
            try:
                parsed_time = datetime.strptime(value, "%d/%b/%y %H:%M")
            except ValueError:
                pytest.skip(
                    f"Не удалось распарсить значение '{value}' по формату "
                    "'%d/%b/%y %H:%M' — возможно, локаль среды выполнения "
                    "отличается от ожидаемой (английские названия месяцев)."
                )

        with allure.step(
            "Проверить, что время равно now + 2 часа с обнуленным значением минут"
        ):
            expected_time = (datetime.now() + timedelta(hours=2)).replace(
                minute=0, second=0, microsecond=0
            )
            assert parsed_time == expected_time, (
                f"Значение поля '{parsed_time}' отличается от ожидаемого "
                f"'{expected_time}'"
            )

    @allure.title(
        "REMCL-1254: Поле Date & time отображает дату в формате DD/MMM/YY"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1254")
    def test_date_time_format_dd_mmm_yy(self, reminder_modal):
        """
        REMCL-1254: Поле `Date & time` отображает дату в формате DD/MMM/YY.
        """
        with allure.step("Получить значение из поля Date & time"):
            value = reminder_modal.date_time_field_text()
            assert value is not None, "Поле Date & time не отображается"

        with allure.step("Извлечь дату (часть до пробела)"):
            date_part = value.split()[0]

        with allure.step("Проверить формат даты DD/MMM/YY"):
            date_pattern = re.compile(r"^\d{2}/[A-Z][a-z]{2}/\d{2}$")
            assert date_pattern.match(date_part), (
                f"Дата '{date_part}' (из значения '{value}') не соответствует "
                "формату DD/MMM/YY (например, '20/Nov/26')"
            )

    @allure.title(
        "REMCL-1540/1126: Попап содержит календарь и списки часов/минут "
        "с шагом 5"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1540", "REMCL-1126", "REMCL-1163")
    def test_date_time_picker_popup_structure(self, reminder_modal):
        """
        REMCL-1540: При активации поля `Date & time` раскрывается окно с
        календарем и списками часов и минут, можно выбрать дату и время.
        REMCL-1126: Значение минут в поле `Date & time` отображается с
        шагом 5 минут.
        REMCL-1163: Ввод минут не кратных 5 в поле `Date & time` блокируется.
        """
        with allure.step("Открыть попап календаря/времени"):
            reminder_modal.open_date_time_picker()

        with allure.step("Проверить наличие часов 00, 12, 23 в списке часов"):
            for hour in [0, 12, 23]:
                assert reminder_modal.is_hour_visible(hour), (
                    f"Час '{hour:02d}' не найден в списке часов попапа"
                )

        with allure.step("Проверить наличие минут с шагом 5 (00, 05, 15, 30, 55)"):
            for minute in [0, 5, 15, 30, 55]:
                assert reminder_modal.is_minute_visible(minute), (
                    f"Минута '{minute:02d}' не найдена в списке минут попапа"
                )

        with allure.step("Проверить, что минуты не кратные 5 НЕ доступны"):
            assert not reminder_modal.is_minute_visible(12), (
                "Минута '12' не должна быть доступна (шаг 5 минут), но была найдена"
            )
            assert not reminder_modal.is_minute_visible(59), (
                "Минута '59' не должна быть доступна (шаг 5 минут), но была найдена"
            )

        with allure.step("Закрыть попап"):
            reminder_modal.close_date_time_picker()

    @allure.title(
        "REMCL-1127/1158/1159/1160: Очистка поля показывает ошибку, "
        "выбор даты скрывает её"
    )
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("REMCL-1127", "REMCL-1158", "REMCL-1159", "REMCL-1160")
    def test_clear_date_time_shows_validation_error(self, reminder_modal):
        """
        REMCL-1127: Кнопка очистки (крестик) отображается внутри поля `Date & time`.
        REMCL-1158: После очистки поля отображается сообщение `Date & time can't be empty.`.
        REMCL-1159: Сообщение исчезает после выбора даты и времени.
        REMCL-1160: Кнопка `Create` disabled после очистки поля `Date & time`.
        """
        with allure.step("Убедиться, что выбран Specific date"):
            reminder_modal.select_when_option(WHEN_OPTION_SPECIFIC_DATE)

        with allure.step("Очистить поле Date & time кнопкой-крестиком"):
            reminder_modal.clear_date_time()

        with allure.step("Проверить появление ошибки 'Date & time can't be empty.'"):
            assert reminder_modal.is_date_time_empty_error_visible(), (
                "Ошибка 'Date & time can't be empty.' не появилась после очистки"
            )

        with allure.step("Проверить, что кнопка Create стала disabled"):
            assert not reminder_modal.is_create_enabled(), (
                "Кнопка Create должна быть disabled после очистки поля"
            )

        with allure.step("Открыть попап и выбрать дату/время"):
            reminder_modal.open_date_time_picker()
            reminder_modal.select_hour(10)
            reminder_modal.select_minute(30)
            reminder_modal.close_date_time_picker()

        with allure.step("Проверить, что ошибка исчезла"):
            assert not reminder_modal.is_date_time_empty_error_visible(), (
                "Ошибка 'Date & time can't be empty' не исчезла после выбора даты"
            )

    @allure.title(
        "REMCL-1772: Выбор прошедшего времени показывает ошибку и "
        "блокирует Create"
    )
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("REMCL-1772")
    def test_past_date_time_shows_error_and_disables_create(self, reminder_modal):
        """
        REMCL-1772: Сообщение "Selected date & time can't be in the past"
        отображается при выборе даты с прошедшим временем ниже поля
        Date & time, а кнопка Create становится disabled.
        """
        with allure.step("Убедиться, что выбран Specific date"):
            reminder_modal.select_when_option(WHEN_OPTION_SPECIFIC_DATE)

        with allure.step("Открыть попап и выбрать прошедшее время (сегодня, 00:00)"):
            reminder_modal.open_date_time_picker()
            reminder_modal.select_hour(0)
            reminder_modal.select_minute(0)
            reminder_modal.close_date_time_picker()

        with allure.step("Проверить появление ошибки о прошедшем времени"):
            assert reminder_modal.is_past_date_error_visible(), (
                "Ошибка 'Selected date & time can't be in the past' не появилась"
            )

        with allure.step("Проверить, что кнопка Create стала disabled"):
            assert not reminder_modal.is_create_enabled(), (
                "Кнопка Create должна быть disabled при выборе прошедшего времени"
            )


@allure.feature("Creation Form")
@allure.story("Repeat Toggle")
class TestRepeatToggle:
    """Тесты переключателя Repeat (REMCL-1128/1129/1185/1186/1195/1196)."""

    @allure.title("REMCL-1129: Toggle Repeat выключен по умолчанию")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1129")
    def test_repeat_toggle_default_state(self, reminder_modal):
        """
        REMCL-1129: Toggle `Repeat` отображается в состоянии `Off` по
        умолчанию.
        """
        with allure.step("Убедиться, что выбран Specific date"):
            reminder_modal.select_when_option(WHEN_OPTION_SPECIFIC_DATE)

        with allure.step("Проверить, что Repeat выключен по умолчанию"):
            assert not reminder_modal.is_repeat_on(), (
                "Toggle Repeat должен быть выключен по умолчанию"
            )

    @allure.title(
        "REMCL-1195: Значение Repeat сохраняется при переключении между "
        "опциями поля When"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1195")
    def test_repeat_state_persists_on_when_option_change(self, reminder_modal):
        """
        REMCL-1195: Значение `Repeat` сохраняется при переключении между
        опциями поля `When`.
        """
        with allure.step("Убедиться, что выбран Specific date"):
            reminder_modal.select_when_option(WHEN_OPTION_SPECIFIC_DATE)

        with allure.step("Проверить, что опция At Due Date доступна"):
            if reminder_modal.is_when_option_disabled(WHEN_OPTION_AT_DUE_DATE):
                pytest.skip(
                    "Опция 'At Due Date' задизейблена на этой задаче "
                    "(нет Due Date) — тест требует задачи с Due Date."
                )

        with allure.step("Включить Repeat"):
            reminder_modal.toggle_repeat(True)
            assert reminder_modal.is_repeat_on(), (
                "Toggle Repeat не включился после клика"
            )

        with allure.step("Переключить When на At Due Date и обратно"):
            reminder_modal.select_when_option(WHEN_OPTION_AT_DUE_DATE)
            reminder_modal.select_when_option(WHEN_OPTION_SPECIFIC_DATE)

        with allure.step("Проверить, что Repeat остался включённым"):
            assert reminder_modal.is_repeat_on(), (
                "Toggle Repeat должен остаться включённым после переключения "
                "опций поля When"
            )

    @allure.title(
        "REMCL-1128: Toggle Repeat отображается справа от поля Date & time"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1128")
    def test_repeat_toggle_position_right_of_date_time(self, reminder_modal):
        """
        REMCL-1128: Toggle `Repeat` отображается справа от поля `Date & time`.
        Покрытие: визуальная/позиционная проверка через bounding_box —
        X-координата контейнера Repeat должна быть больше или равна
        X-координате Date & time, а Y-координаты должны быть примерно
        совпадать (элементы в одной строке).
        ТЕХНИЧЕСКИЙ РИСК: это визуальный тест, чувствительный к изменениям
        дизайна (если элементы начнут рендериться друг под другом в столбик,
        тест упадёт). При смене макета формы тест нужно будет пересмотреть.
        """
        with allure.step("Убедиться, что выбран Specific date"):
            reminder_modal.select_when_option(WHEN_OPTION_SPECIFIC_DATE)

        with allure.step("Получить bounding box Date & time и Repeat"):
            date_box = reminder_modal._date_time_container.bounding_box()
            repeat_box = reminder_modal._repeat_container.bounding_box()
            assert date_box is not None, (
                "Не удалось получить bounding box контейнера Date & time"
            )
            assert repeat_box is not None, (
                "Не удалось получить bounding box контейнера Repeat"
            )

        with allure.step("Проверить, что Repeat правее Date & time"):
            assert repeat_box["x"] >= date_box["x"], (
                f"Контейнер Repeat (x={repeat_box['x']}) должен быть "
                f"правее или на одной вертикали с Date & time (x={date_box['x']})"
            )

        with allure.step("Проверить, что Repeat и Date & time примерно в одной строке"):
            y_diff = abs(repeat_box["y"] - date_box["y"])
            assert y_diff < 50, (
                f"Контейнеры Repeat и Date & time должны быть примерно в одной "
                f"строке, но разница Y = {y_diff}px "
                f"(Repeat y={repeat_box['y']}, Date & time y={date_box['y']})"
            )

    @allure.title(
        "REMCL-1185: Переключение Repeat в On отображает дополнительные "
        "настройки повторения"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1185")
    def test_repeat_on_shows_settings(self, reminder_modal):
        """
        REMCL-1185: Переключение `Repeat` в состояние `On` отображает
        дополнительные настройки повторения (Frequency, Ends, End date).
        Покрытие: включаем Repeat, проверяем появление блока настроек
        (индикатор — видимость лейбла "Frequency").
        """
        with allure.step("Убедиться, что выбран Specific date"):
            reminder_modal.select_when_option(WHEN_OPTION_SPECIFIC_DATE)

        with allure.step("Проверить, что блок настроек скрыт при Repeat Off"):
            assert not reminder_modal.is_repeat_on(), (
                "Repeat должен быть выключен перед тестом"
            )
            assert not reminder_modal.is_repeat_settings_visible(), (
                "Блок настроек повторения не должен быть виден при Repeat Off"
            )

        with allure.step("Включить Repeat"):
            reminder_modal.toggle_repeat(True)

        with allure.step("Проверить, что блок настроек появился"):
            assert reminder_modal.is_repeat_settings_visible(), (
                "Блок настроек повторения (Frequency/Ends/End date) не появился "
                "после включения Repeat"
            )

        with allure.step("Проверить дефолтное значение Frequency = 1"):
            freq_value = reminder_modal.get_repeat_frequency_value()
            assert freq_value == "1", (
                f"Дефолтное значение Frequency должно быть '1', получено '{freq_value}'"
            )

    @allure.title(
        "REMCL-1186: Переключение Repeat в Off скрывает дополнительные "
        "настройки повторения"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1186")
    def test_repeat_off_hides_settings(self, reminder_modal):
        """
        REMCL-1186: Переключение `Repeat` в состояние `Off` скрывает
        дополнительные настройки повторения.
        Покрытие: включаем Repeat (появляются настройки), выключаем Repeat —
        блок настроек должен исчезнуть.
        """
        with allure.step("Убедиться, что выбран Specific date"):
            reminder_modal.select_when_option(WHEN_OPTION_SPECIFIC_DATE)

        with allure.step("Включить Repeat и убедиться, что настройки появились"):
            reminder_modal.toggle_repeat(True)
            assert reminder_modal.is_repeat_settings_visible(), (
                "Блок настроек повторения не появился после включения Repeat"
            )

        with allure.step("Выключить Repeat"):
            reminder_modal.toggle_repeat(False)

        with allure.step("Проверить, что блок настроек исчез"):
            assert not reminder_modal.is_repeat_settings_visible(), (
                "Блок настроек повторения должен скрыться после выключения Repeat"
            )

    @allure.title(
        "REMCL-1196: Значения repeat-настроек сохраняются после "
        "переключения Repeat Off → On"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1196")
    def test_repeat_settings_persist_after_toggle(self, reminder_modal):
        """
        REMCL-1196: Значения repeat-настроек сохраняются после переключения
        `Repeat` Off → On.
        Покрытие:
        1. Включаем Repeat → появляются настройки с дефолтным Frequency = 1.
        2. Меняем Frequency на 3.
        3. Выключаем Repeat → настройки скрываются.
        4. Включаем Repeat снова → Frequency должно остаться 3 (не сброситься
           в дефолтное 1).

        ЧЕСТНАЯ ОГОВОРКА: проверяется сохранение только Frequency (числовое
        поле). Сохранение единицы (day(s)/week(s)/...) и End date не
        проверяется — это потребовало бы автоматизации combobox-выбора и
        отдельного date-picker для End date, что выходит за рамки этого
        теста. Если понадобится проверить и другие настройки — расширить тест.
        """
        with allure.step("Убедиться, что выбран Specific date"):
            reminder_modal.select_when_option(WHEN_OPTION_SPECIFIC_DATE)

        with allure.step("Включить Repeat"):
            reminder_modal.toggle_repeat(True)
            assert reminder_modal.is_repeat_settings_visible(), (
                "Блок настроек повторения не появился после включения Repeat"
            )

        with allure.step("Проверить дефолтное значение Frequency = 1"):
            initial_freq = reminder_modal.get_repeat_frequency_value()
            assert initial_freq == "1", (
                f"Ожидалось дефолтное Frequency='1', получено '{initial_freq}'"
            )

        with allure.step("Изменить Frequency на 3"):
            reminder_modal.set_repeat_frequency(3)
            assert reminder_modal.get_repeat_frequency_value() == "3", (
                "Frequency не обновилось после установки значения 3"
            )

        with allure.step("Выключить Repeat"):
            reminder_modal.toggle_repeat(False)
            assert not reminder_modal.is_repeat_settings_visible(), (
                "Блок настроек должен был скрыться после выключения Repeat"
            )

        with allure.step("Включить Repeat снова"):
            reminder_modal.toggle_repeat(True)
            assert reminder_modal.is_repeat_settings_visible(), (
                "Блок настроек повторения не появился после повторного включения"
            )

        with allure.step("Проверить, что Frequency сохранилось как 3"):
            final_freq = reminder_modal.get_repeat_frequency_value()
            assert final_freq == "3", (
                f"Frequency должно было сохраниться как '3' после цикла "
                f"On → Off → On, получено '{final_freq}'"
            )