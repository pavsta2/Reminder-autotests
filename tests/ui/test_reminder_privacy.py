"""
Тесты поля Privacy в форме создания ремайндера (модалка "New reminder").

"""
import allure
import pytest

from pages.components.reminder_modal import ReminderModal
from pages.components.reminder_modal import (
    PRIVACY_OPTION_PRIVATE,
    PRIVACY_OPTION_PUBLIC
)

pytestmark = [
    pytest.mark.ui,
    pytest.mark.creation_form,
    pytest.mark.issue_panel,
]


def add_third_party_recipient(modal: ReminderModal) -> None:
    """
    Вспомогательный шаг: добавляет стороннего пользователя ("Reporter")
    в поле Recipients, чтобы спровоцировать появление поля Privacy в форме.
    """
    with allure.step("Добавить стороннего пользователя (Reporter) в Recipients"):
        modal.open_dropdown()
        # Очищаем, чтобы гарантировать, что создатель не является "единственным"
        # и мы проверяем именно наличие стороннего получателя.
        modal.clear_all()
        modal.search("Reporter")
        modal.wait_for_search_to_settle()
        modal.select_in_users_section("Reporter")
        modal.close_dropdown_by_clicking_outside()


@allure.feature("Creation Form")
@allure.story("Privacy Field")
class TestPrivacyVisibility:
    """Тесты видимости поля Privacy в зависимости от состава Recipients."""

    @allure.title("REMCL-1322: Privacy скрыто, если единственный получатель — создатель")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1322")
    def test_privacy_hidden_when_only_creator_in_recipients(self, reminder_modal: ReminderModal) -> None:
        """
        По умолчанию при открытии формы в Recipients стоит создатель.
        В этом состоянии поле Privacy должно отсутствовать.
        """
        with allure.step("Проверить, что поле Privacy НЕ видно (по умолчанию только создатель)"):
            assert not reminder_modal.is_privacy_visible(), (
                "Поле Privacy не должно быть видно, когда единственный получатель — создатель"
            )

    @allure.title("REMCL-1323: Privacy скрыто, когда Recipients полностью пусто")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1323")
    def test_privacy_hidden_when_recipients_empty(self, reminder_modal: ReminderModal) -> None:
        """
        Если очистить поле Recipients, поле Privacy также должно исчезнуть.
        """
        with allure.step("Очистить поле Recipients полностью"):
            reminder_modal.clear_all()
            reminder_modal.close_dropdown_by_clicking_outside()

        with allure.step("Проверить, что поле Privacy НЕ видно"):
            assert not reminder_modal.is_privacy_visible(), (
                "Поле Privacy не должно быть видно, когда Recipients пусты"
            )

    @allure.title("REMCL-1316: Privacy появляется при добавлении стороннего пользователя")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("REMCL-1316")
    def test_privacy_appears_when_third_party_added(self, reminder_modal: ReminderModal) -> None:
        """
        Как только в Recipients добавляется пользователь, отличный от создателя,
        поле Privacy должно стать видимым.
        """
        add_third_party_recipient(reminder_modal)

        with allure.step("Проверить, что поле Privacy стало видимым"):
            assert reminder_modal.is_privacy_visible(), (
                "Поле Privacy должно появиться после добавления стороннего получателя"
            )


@allure.feature("Creation Form")
@allure.story("Privacy Field UI")
class TestPrivacyFieldUI:
    """Тесты UI-элементов поля Privacy (требуется наличие стороннего получателя)."""

    @allure.title(
        "REMCL-1325: Поле Privacy получает видимый focus-индикатор "
        "при переходе по Tab"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1325")
    def test_privacy_focus_indicator_on_tab(self, reminder_modal):
        """
        REMCL-1325: Поле Privacy получает видимый focus-индикатор при
        переходе по Tab.

        Покрытие:
        1. Добавляем стороннего пользователя в Recipients (чтобы Privacy
           появилось).
        2. Закрываем дропдаун Recipients.
        3. Нажимаем Tab до тех пор, пока фокус не окажется на поле Privacy.
        4. Проверяем, что фокус дошёл (метод tab_to_privacy() вернул число).

        Визуальный focus-индикатор (рамка/тень) НЕ assert'ится — как именно
        он выглядит, ещё не снято с реальной формы. Вместо этого делаем
        скриншот поля в фокусе для Allure-отчёта.
        """
        # Шаг 1: Добавляем стороннего пользователя, чтобы Privacy появилось.
        with allure.step("Добавить стороннего пользователя (Reporter) в Recipients"):
            add_third_party_recipient(reminder_modal)

        # Шаг 2: Проверяем, что Privacy видимо.
        with allure.step("Проверить, что поле Privacy появилось"):
            assert reminder_modal.is_privacy_visible(), (
                "Поле Privacy не появилось после добавления стороннего пользователя"
            )

        # Шаг 3: Табулируем до поля Privacy.
        with allure.step("Нажимать Tab, пока фокус не попадёт в Privacy"):
            tab_count = reminder_modal.tab_to_privacy()
            assert tab_count is not None, (
                "Поле Privacy не получило фокус по Tab за 20 нажатий"
            )
            allure.attach(
                str(tab_count),
                name="Нажатий Tab до Privacy",
                attachment_type=allure.attachment_type.TEXT,
            )

        # Шаг 4: Скриншот поля в фокусе (focus state — визуально).
        with allure.step("Скриншот поля Privacy в фокусе (focus state)"):
            screenshot = reminder_modal._privacy_combobox.screenshot()
            allure.attach(
                screenshot,
                name="Privacy combobox в фокусе",
                attachment_type=allure.attachment_type.PNG,
            )

    @allure.title("REMCL-1320: Дропдаун Privacy содержит ровно две опции: Private и Public")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1320")
    def test_privacy_dropdown_has_two_options(self, reminder_modal: ReminderModal) -> None:
        add_third_party_recipient(reminder_modal)

        with allure.step("Открыть дропдаун Privacy"):
            reminder_modal.open_privacy_dropdown()

        with allure.step("Проверить наличие опций 'Private' и 'Public'"):
            assert reminder_modal.is_privacy_option_visible(PRIVACY_OPTION_PRIVATE), (
                "Опция 'Private' не найдена в дропдауне Privacy"
            )
            assert reminder_modal.is_privacy_option_visible(PRIVACY_OPTION_PUBLIC), (
                "Опция 'Public' не найдена в дропдауне Privacy"
            )

        with allure.step("Закрыть дропдаун"):
            reminder_modal.page.keyboard.press("Escape")

    @allure.title("REMCL-1321: Рядом с подписью Privacy отображается иконка вопроса (?)")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1321")
    def test_privacy_has_tooltip_icon(self, reminder_modal: ReminderModal) -> None:
        add_third_party_recipient(reminder_modal)

        with allure.step("Проверить видимость иконки тултипа рядом с лейблом Privacy"):
            assert reminder_modal._privacy_tooltip_icon.is_visible(), (
                "Иконка вопроса (?) рядом с лейблом Privacy не видна"
            )

    @allure.title("REMCL-1018: Тултип Privacy содержит текст о приватности")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1018")
    def test_privacy_tooltip_text(self, reminder_modal):
        """
        REMCL-1018: При наведении курсора на иконку с вопросительным знаком
        в круге справа от названия поля "Privacy" появляется Тултип с текстом:
        "Privacy defines who can see and manage the reminder: ..."
        """
        # Для проверки тултипа нужно, чтобы поле Privacy было видимо —
        # добавляем стороннего пользователя в Recipients.
        add_third_party_recipient(reminder_modal)

        with allure.step("Получить текст тултипа из атрибута aria-label иконки"):
            tooltip_text = reminder_modal.get_privacy_tooltip_text()
            assert tooltip_text is not None, (
                "Текст тултипа Privacy не найден в атрибуте aria-label"
            )

        with allure.step("Проверить, что текст содержит ключевые фразы"):
            assert "Privacy defines who can see" in tooltip_text, (
                f"Текст тултипа не содержит ожидаемую фразу: {tooltip_text!r}"
            )
            assert "creator always has full access" in tooltip_text, (
                f"Текст тултипа не содержит ожидаемую фразу: {tooltip_text!r}"
            )
            assert "recipients can see assigned reminders" in tooltip_text, (
                f"Текст тултипа не содержит ожидаемую фразу: {tooltip_text!r}"
            )

    @allure.title("REMCL-1317: Поле Privacy расположено под Recipients и над When")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1317")
    def test_privacy_position_between_recipients_and_when(self, reminder_modal: ReminderModal) -> None:
        add_third_party_recipient(reminder_modal)

        with allure.step("Получить координаты блоков Recipients, Privacy и When"):
            recipients_box = reminder_modal._field.bounding_box()
            privacy_box = reminder_modal._privacy_label.bounding_box()
            when_box = reminder_modal._when_label.bounding_box()

            assert recipients_box and privacy_box and when_box, (
                "Не удалось получить размеры одного из полей для проверки позиционирования"
            )

        with allure.step("Проверить, что Privacy находится ниже Recipients и выше When"):
            assert privacy_box["y"] > recipients_box["y"], (
                f"Privacy (y={privacy_box['y']}) должен быть ниже Recipients (y={recipients_box['y']})"
            )
            assert privacy_box["y"] < when_box["y"], (
                f"Privacy (y={privacy_box['y']}) должен быть выше When (y={when_box['y']})"
            )


@allure.feature("Creation Form")
@allure.story("Privacy Field Logic")
class TestPrivacyFieldLogic:
    """Тесты логики взаимодействия Privacy с другими элементами формы."""

    @allure.title("REMCL-1331 / REMCL-1332: Переключение Privacy влияет на состояние тоггла Allow edit")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("REMCL-1331", "REMCL-1332")
    def test_privacy_allow_edit_toggle_behavior(self, reminder_modal: ReminderModal) -> None:
        """
        REMCL-1331: Выбор Private активирует тоггл Allow edit.
        REMCL-1332: Выбор Public переводит тоггл Allow edit в disabled и сбрасывает в Off.
        """
        add_third_party_recipient(reminder_modal)

        with allure.step("Выбрать Privacy = Public"):
            reminder_modal.select_privacy_option("Public")

        with allure.step("Проверить, что Allow edit disabled и выключен (Off)"):
            assert reminder_modal.is_allow_edit_disabled(), (
                "Тоггл Allow edit должен быть disabled при Privacy = Public"
            )
            assert not reminder_modal.is_allow_edit_on(), (
                "Тоггл Allow edit должен быть в состоянии Off при Privacy = Public"
            )

        with allure.step("Изменить Privacy на Private"):
            reminder_modal.select_privacy_option("Private")

        with allure.step("Проверить, что Allow edit стал активным (не disabled)"):
            assert not reminder_modal.is_allow_edit_disabled(), (
                "Тоггл Allow edit должен перестать быть disabled при Privacy = Private"
            )
