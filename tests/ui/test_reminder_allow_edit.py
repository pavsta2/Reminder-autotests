"""
Тесты тоггла Allow edit в форме создания ремайндера (модалка "New reminder").

Источник test-кейсов: rtm-issues-export.csv, RTM Node
"Creation - Allow edit (v.2.X.X)" — 8 кейсов:
REMCL-1019/1020/1333/1334/1335/1336/1337/1338.

Page Object — pages/components/reminder_modal.py (блок Allow edit).

ПРЕДУСЛОВИЕ ДЛЯ ВСЕХ ТЕСТОВ: поле Privacy (а значит и Allow edit) появляется
ТОЛЬКО когда среди Recipients есть кто-то кроме создателя. Поэтому каждый
тест сначала добавляет стороннего получателя — системный пункт "Reporter",
гарантированно присутствующий в секции Users.

НАХОДКИ ПО РАЗМЕТКЕ (2026-11-27, оба состояния присланы пользователем):
1. Тултип — aria-label на контейнере data-testid="allow-edit-toggle":
   при Public содержит текст REMCL-1020, при Private ПУСТОЙ. Отдельного
   role="tooltip" при hover нет — hover не нужен.
2. <label>Allow edit</label> БЕЗ for/htmlFor → get_by_label не найдёт чекбокс;
   путь к нему только через контейнер.
3. disabled разложен по двум уровням: aria-disabled="true" на родителе
   (switchBase), атрибут disabled на самом input.

ЛОВУШКА: клик по disabled-тогглу обычным toggle_allow_edit() висит на
auto-waiting Playwright до 30с — для REMCL-1335 используется
try_toggle_allow_edit() с коротким таймаутом.

ИСПРАВЛЕНО (2026-11-27, по корректировке кейса пользователем — пересматривает
первоначальную редакцию теста от 2026-11-27): в обновлённом REMCL-1333
Expected result подпись "Allow edit" расположена НАД тогглом ("над тогглом
видна подпись Allow edit"), а не СЛЕВА от него ("слева от тоггла видна
подпись" в предыдущей редакции экспорта). Ассерт на горизонтальное
расположение подписи заменён на вертикальное. Остальные две проверки кейса
(тоггл правее Privacy, в одной строке с ним) не изменились. Это не забытый
TODO, а осознанный разворот вслед за изменением требования.

ТЕХНИЧЕСКИЙ РИСК (не снят): фактическое взаимное расположение подписи и
тоггла вживую не замерялось — в разметке они sibling-и внутри
div.css-1yhkpz9, направление flex по хешированному классу не определить.
Координаты всех трёх элементов прикладываются к Allure ДО ассертов, чтобы
расхождение было видно из отчёта за один прогон.

DRY-ОГОВОРКА: helper _add_third_party_recipient дублирует одноимённый из
tests/ui/test_reminder_privacy.py. Осознанно оставлен локальным, чтобы не
править fixtures/conftest.py вслепую (его актуальное содержимое не снималось);
вынести в общую фикстуру — отдельной задачей.
"""
from __future__ import annotations

import json

import allure
import pytest
from playwright.sync_api import expect

from pages.components.reminder_modal import (
    ALLOW_EDIT_DISABLED_TOOLTIP_TEXT,
    ALLOW_EDIT_LABEL_TEXT,
    PRIVACY_OPTION_PRIVATE,
    PRIVACY_OPTION_PUBLIC,
    ReminderModal,
)

pytestmark = [
    pytest.mark.ui,
    pytest.mark.creation_form,
    pytest.mark.issue_panel,
]

# Системный пункт, всегда присутствующий в секции Users (подтверждено ранее).
THIRD_PARTY_RECIPIENT = "Reporter"

# Допуск "в одной строке" для позиционной проверки (REMCL-1333).
ROW_Y_TOLERANCE_PX = 50
# Допуск на границах элементов (субпиксельное округление bounding_box).
EDGE_TOLERANCE_PX = 1


def _add_third_party_recipient(modal: ReminderModal) -> None:
    """Предусловие: добавить стороннего получателя, чтобы Privacy появился."""
    with allure.step(
        f"Добавить стороннего получателя ({THIRD_PARTY_RECIPIENT}) в Recipients"
    ):
        modal.open_dropdown()
        modal.clear_all()
        modal.search(THIRD_PARTY_RECIPIENT)
        modal.wait_for_search_to_settle()
        modal.select_in_users_section(THIRD_PARTY_RECIPIENT)
        modal.close_dropdown_by_clicking_outside()


@allure.feature("Creation Form")
@allure.story("Allow edit")
class TestAllowEditPresence:
    """Наличие, расположение и дефолтное состояние тоггла."""

    @allure.title(
        "REMCL-1333/1019: тоггл Allow edit справа от Privacy в той же строке, "
        "подпись над тогглом"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1333", "REMCL-1019")
    def test_allow_edit_is_right_of_privacy_in_same_row(
        self, reminder_modal: ReminderModal
    ) -> None:
        """
        REMCL-1333: тоггл Allow edit расположен в той же строке, что и поле
        Privacy, справа от него; НАД тогглом видна подпись "Allow edit".

        ИСПРАВЛЕНО (2026-11-27, по корректировке кейса пользователем):
        в предыдущей редакции экспорта Expected result требовал подпись
        СЛЕВА от тоггла, и тест ассертил горизонтальное расположение
        (label.x + label.width <= toggle.x). В актуальной редакции —
        "над тогглом видна подпись", поэтому ассерт заменён на вертикальный
        (label.y + label.height <= toggle.y). Две другие проверки кейса
        не изменились.

        REMCL-1019 — ДУБЛЬ по смыслу ("в форме есть ЧБ Allow edit справа от
        поля Privacy"): второй тег, а не копия теста. Часть REMCL-1019 про
        "выкл по дефолту" покрыта тестом test_allow_edit_is_off_by_default
        (там тоже стоит тег REMCL-1019).

        Позиционная проверка через bounding_box — чувствительна к смене
        макета (если элементы начнут рендериться в столбик, тест упадёт);
        это осознанный визуальный тест, а не скрытая подгонка. Координаты
        прикладываются к отчёту ДО ассертов — фактическая геометрия вживую
        не замерялась, и при расхождении это видно сразу.
        """
        _add_third_party_recipient(reminder_modal)

        with allure.step("Выбрать Privacy = Private"):
            reminder_modal.select_privacy_option(PRIVACY_OPTION_PRIVATE)

        with allure.step("Тоггл и подпись Allow edit видны"):
            assert reminder_modal.is_allow_edit_visible(), (
                "Тоггл Allow edit или его подпись не отображаются"
            )
            expect(reminder_modal.allow_edit_label_locator()).to_have_text(
                ALLOW_EDIT_LABEL_TEXT
            )

        with allure.step("Получить координаты Privacy, тоггла и подписи"):
            privacy_box = reminder_modal.privacy_combobox_locator().bounding_box()
            toggle_box = reminder_modal.allow_edit_container_locator().bounding_box()
            label_box = reminder_modal.allow_edit_label_locator().bounding_box()
            allure.attach(
                json.dumps(
                    {
                        "privacy_combobox": privacy_box,
                        "allow_edit_toggle": toggle_box,
                        "allow_edit_label": label_box,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                name="Координаты Privacy / тоггла / подписи",
                attachment_type=allure.attachment_type.JSON,
            )
            assert privacy_box and toggle_box and label_box, (
                "Не удалось получить размеры Privacy / тоггла / подписи"
            )

        with allure.step("Тоггл правее поля Privacy"):
            assert (
                toggle_box["x"]
                >= privacy_box["x"] + privacy_box["width"] - EDGE_TOLERANCE_PX
            ), (
                f"Тоггл (x={toggle_box['x']}) должен быть правее Privacy "
                f"(x={privacy_box['x']}, width={privacy_box['width']})"
            )

        with allure.step("Тоггл и Privacy в одной строке"):
            y_diff = abs(toggle_box["y"] - privacy_box["y"])
            assert y_diff < ROW_Y_TOLERANCE_PX, (
                f"Тоггл и Privacy должны быть в одной строке, разница Y={y_diff}px"
            )

        with allure.step("Подпись Allow edit НАД тогглом"):
            assert (
                label_box["y"] + label_box["height"]
                <= toggle_box["y"] + EDGE_TOLERANCE_PX
            ), (
                f"Подпись (y={label_box['y']}, height={label_box['height']}) "
                f"должна быть НАД тогглом (y={toggle_box['y']}). "
                "Если по координатам во вложении подпись на самом деле слева — "
                "это расхождение кейса с реализацией, нужно решение автора кейсов."
            )

    @allure.title(
        "REMCL-1334/1019: тоггл Allow edit по умолчанию в состоянии Off"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1334", "REMCL-1019")
    def test_allow_edit_is_off_by_default(
        self, reminder_modal: ReminderModal
    ) -> None:
        """
        REMCL-1334: открыть форму, добавить стороннего получателя, выбрать
        Privacy = Private → тоггл Allow edit визуально Off.

        REMCL-1019 — второй тег (часть "выкл по дефолту"), см. его докстринг
        в test_allow_edit_is_right_of_privacy_in_same_row.

        "Визуально Off" проверяется через состояние нативного чекбокса
        (checked=false) — именно он управляет положением MUI Switch; отдельный
        CSS-ассерт на позицию thumb не делается (хрупко и не описано кейсом).
        """
        _add_third_party_recipient(reminder_modal)

        with allure.step("Выбрать Privacy = Private"):
            reminder_modal.select_privacy_option(PRIVACY_OPTION_PRIVATE)

        with allure.step("Тоггл Allow edit виден и активен"):
            assert reminder_modal.is_allow_edit_visible(), "Тоггл не отображается"
            expect(reminder_modal.allow_edit_checkbox_locator()).to_be_enabled()

        with allure.step("Тоггл в состоянии Off (чекбокс не отмечен)"):
            expect(reminder_modal.allow_edit_checkbox_locator()).not_to_be_checked()


@allure.feature("Creation Form")
@allure.story("Allow edit")
class TestAllowEditDisabledState:
    """Поведение тоггла при Privacy = Public."""

    @allure.title(
        "REMCL-1335: при Privacy = Public тоггл Allow edit disabled "
        "и недоступен для взаимодействия"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1335")
    def test_allow_edit_disabled_when_privacy_public(
        self, reminder_modal: ReminderModal
    ) -> None:
        """
        REMCL-1335: тоггл визуально в состоянии disabled и недоступен для
        взаимодействия.

        Проверяются ОБА уровня признака disabled (находка 3): атрибут
        disabled на input и aria-disabled="true" на обёртке switchBase.
        "Недоступен для взаимодействия" доказывается best-effort кликом с
        коротким таймаутом: обычный toggle_allow_edit() на disabled-элементе
        висел бы на auto-waiting Playwright до 30с.
        """
        _add_third_party_recipient(reminder_modal)

        with allure.step("Выбрать Privacy = Public"):
            reminder_modal.select_privacy_option(PRIVACY_OPTION_PUBLIC)

        with allure.step("Input тоггла задизейблен"):
            expect(reminder_modal.allow_edit_checkbox_locator()).to_be_disabled()

        with allure.step("Обёртка switchBase помечена aria-disabled=true"):
            expect(reminder_modal.allow_edit_switch_base_locator()).to_have_attribute(
                "aria-disabled", "true"
            )

        with allure.step("Попытка клика не проходит (элемент неинтерактивен)"):
            assert not reminder_modal.try_toggle_allow_edit(), (
                "Клик по тогглу прошёл, хотя при Privacy = Public он должен "
                "быть недоступен для взаимодействия"
            )

        with allure.step("Состояние тоггла осталось Off"):
            expect(reminder_modal.allow_edit_checkbox_locator()).not_to_be_checked()

    @allure.title(
        "REMCL-1020: тултип неактивного тоггла Allow edit содержит текст "
        "о проектных правах"
    )
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("REMCL-1020")
    @pytest.mark.functional
    def test_allow_edit_tooltip_when_disabled(
        self, reminder_modal: ReminderModal
    ) -> None:
        """
        REMCL-1020: при наведении на неактивный ЧБ "Allow edit" появляется
        тултип "Editing of public reminders is controlled by project-level
        permissions."

        РЕАЛИЗАЦИЯ (2026-11-27, по разметке обоих состояний): тултип — это
        aria-label на контейнере data-testid="allow-edit-toggle"; отдельного
        элемента role="tooltip" при hover НЕ появляется (тот же паттерн, что
        у Privacy). Поэтому hover не нужен, текст читается из атрибута и
        сравнивается ДОСЛОВНО — он подтверждён разметкой, а не угадан.

        Дополнительно проверяется обратная сторона утверждения кейса
        ("в НЕактивном состоянии"): при Privacy = Private атрибут пустой,
        т.е. тултип привязан именно к disabled-состоянию.
        """
        _add_third_party_recipient(reminder_modal)

        with allure.step("Выбрать Privacy = Private (тоггл активен)"):
            reminder_modal.select_privacy_option(PRIVACY_OPTION_PRIVATE)

        with allure.step("В активном состоянии тултипа нет (aria-label пустой)"):
            expect(reminder_modal.allow_edit_container_locator()).to_have_attribute(
                "aria-label", ""
            )

        with allure.step("Выбрать Privacy = Public (тоггл становится неактивным)"):
            reminder_modal.select_privacy_option(PRIVACY_OPTION_PUBLIC)

        with allure.step("Тултип содержит дословный текст из кейса"):
            expect(reminder_modal.allow_edit_container_locator()).to_have_attribute(
                "aria-label", ALLOW_EDIT_DISABLED_TOOLTIP_TEXT
            )


@allure.feature("Creation Form")
@allure.story("Allow edit")
class TestAllowEditKeyboard:
    """Клавиатурное управление тогглом (REMCL-1336/1337/1338)."""

    @allure.title(
        "REMCL-1336: активный тоггл Allow edit получает фокус при переходе по Tab"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1336")
    def test_allow_edit_reachable_by_tab(
        self, reminder_modal: ReminderModal
    ) -> None:
        """
        REMCL-1336 — ЧАСТИЧНО ПОКРЫТ: проверяется, что активный тоггл
        достижим с клавиатуры и получает фокус. ВИЗУАЛЬНЫЙ focus-индикатор
        (рамка/тень) НЕ assert'ится — как именно он выглядит, не снято с
        реальной формы; вместо ассерта прикладывается скриншот в фокусе.
        Тот же приём, что в REMCL-1325 (Privacy) и REMCL-1261 (Message).
        """
        _add_third_party_recipient(reminder_modal)

        with allure.step("Выбрать Privacy = Private"):
            reminder_modal.select_privacy_option(PRIVACY_OPTION_PRIVATE)

        with allure.step("Нажимать Tab, пока фокус не попадёт в тоггл Allow edit"):
            tab_count = reminder_modal.tab_to_allow_edit()
            assert tab_count is not None, (
                "Тоггл Allow edit не получил фокус по Tab за 25 нажатий "
                "(при Privacy = Private он должен быть достижим)"
            )
            allure.attach(
                str(tab_count),
                name="Нажатий Tab до Allow edit",
                attachment_type=allure.attachment_type.TEXT,
            )

        with allure.step("Фокус действительно на чекбоксе тоггла"):
            expect(reminder_modal.allow_edit_checkbox_locator()).to_be_focused()

        with allure.step("Скриншот тоггла в фокусе (focus state — визуально)"):
            allure.attach(
                reminder_modal.allow_edit_container_locator().screenshot(),
                name="Allow edit в фокусе",
                attachment_type=allure.attachment_type.PNG,
            )

    @allure.title("REMCL-1337: тоггл Allow edit переключается в On клавишей Space")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("REMCL-1337")
    @pytest.mark.functional
    def test_allow_edit_turns_on_by_space(
        self, reminder_modal: ReminderModal
    ) -> None:
        """
        REMCL-1337: выбрать Privacy = Private, перейти к тогглу клавишей Tab
        (тоггл получает фокус), нажать Space → тоггл в состоянии On.
        """
        _add_third_party_recipient(reminder_modal)

        with allure.step("Выбрать Privacy = Private"):
            reminder_modal.select_privacy_option(PRIVACY_OPTION_PRIVATE)

        with allure.step("Перейти к тогглу клавишей Tab — тоггл получает фокус"):
            assert reminder_modal.tab_to_allow_edit() is not None, (
                "Тоггл не получил фокус по Tab"
            )
            expect(reminder_modal.allow_edit_checkbox_locator()).to_be_focused()

        with allure.step("Исходно тоггл Off"):
            expect(reminder_modal.allow_edit_checkbox_locator()).not_to_be_checked()

        with allure.step("Нажать Space"):
            reminder_modal.toggle_allow_edit_by_space()

        with allure.step("Тоггл переключился в On"):
            expect(reminder_modal.allow_edit_checkbox_locator()).to_be_checked()

    @allure.title(
        "REMCL-1338: тоггл Allow edit переключается в Off повторным Space"
    )
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("REMCL-1338")
    @pytest.mark.functional
    def test_allow_edit_turns_off_by_second_space(
        self, reminder_modal: ReminderModal
    ) -> None:
        """
        REMCL-1338: Privacy = Private, Tab к тогглу, Space → On,
        повторный Space → Off.
        """
        _add_third_party_recipient(reminder_modal)

        with allure.step("Выбрать Privacy = Private"):
            reminder_modal.select_privacy_option(PRIVACY_OPTION_PRIVATE)

        with allure.step("Перейти к тогглу клавишей Tab"):
            assert reminder_modal.tab_to_allow_edit() is not None, (
                "Тоггл не получил фокус по Tab"
            )
            expect(reminder_modal.allow_edit_checkbox_locator()).to_be_focused()

        with allure.step("Первое нажатие Space — тоггл в состоянии On"):
            reminder_modal.toggle_allow_edit_by_space()
            expect(reminder_modal.allow_edit_checkbox_locator()).to_be_checked()

        with allure.step("Повторное нажатие Space — тоггл в состоянии Off"):
            reminder_modal.toggle_allow_edit_by_space()
            expect(reminder_modal.allow_edit_checkbox_locator()).not_to_be_checked()