"""
Тесты всплывающих уведомлений плагина Reminder (AtlasKit Flag): заголовок,
текст, тип, кнопка закрытия.

Page Object — pages/components/notification.py (Notification), доступен
как issue_page.notification.

КЛЮЧЕВОЕ ОГРАНИЧЕНИЕ (подтверждено пользователем 2026-11-25): флаг живёт
~5 секунд. Поэтому во всех тестах этого файла проверка уведомления идёт
СРАЗУ после действия, ДО проверок контента секции Reminder (они долгие и
съели бы всё окно). Для негативных сценариев, где модалка не закрывается,
submit() вызывается с settle_timeout_ms=500 — иначе его ожидание закрытия
(до 20с) гарантированно пропустит флаг.

Тесты, которые создают ремайндер, оставляют на инстансе по одной записи с
уникальным текстом (метода delete в репозитории нет) — тот же trade-off,
что в test_reminder_create_cancel.py.
"""
from __future__ import annotations

from datetime import datetime, timezone

import allure
import pytest
from faker import Faker
from playwright.sync_api import expect

from pages.components.notification import (
    FLAG_KIND_ERROR,
    FLAG_KIND_SUCCESS,
    FLAG_KIND_WARNING,
    REMINDER_CREATED_SUCCESS_TEXT,
)
from pages.issue_page import IssuePage

pytestmark = [
    pytest.mark.ui,
    pytest.mark.creation_form,
    pytest.mark.issue_panel,
]

_faker = Faker()


def _unique_message(tag: str) -> str:
    return (
        f"{_faker.sentence(nb_words=4).rstrip('.')} "
        f"[autotest-{tag} {datetime.now(timezone.utc).isoformat(timespec='seconds')}]"
    )


@allure.feature("Creation Form")
@allure.story("Notifications")
class TestSuccessNotification:
    """Уведомление об успешном создании ремайндера."""

    @allure.title(
        "После создания ремайндера появляется уведомление Success "
        "с заголовком и текстом"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-1038")
    @pytest.mark.functional
    def test_success_notification_after_reminder_created(
        self, issue_page: IssuePage, issue_key: str
    ) -> None:
        """
        ДОПОЛНИТЕЛЬНОЕ наблюдение сверх текста REMCL-1038: сам кейс требует
        только «окно закрывается и ремайндер появляется в секции Reminder»,
        про уведомление в нём ничего нет. Тег поставлен как на связанный
        кейс, а не как на покрытие его требования — отдельного RTM-кейса на
        success-уведомление в присланных экспортах нет.

        Разметка и тексты подтверждены HTML 2026-11-25: иконка
        role="img" aria-label="Success", заголовок <h2>Success</h2>,
        тело "A new reminder was added".
        """
        unique_message = _unique_message("notify-success")

        with allure.step("Открыть задачу и форму создания ремайндера"):
            issue_page.open(issue_key)
            assert issue_page.has_reminder_section(), (
                "Секция Reminder не найдена на странице задачи"
            )
            issue_page.reminder_panel.expand()
            modal = issue_page.reminder_panel.open_create_modal()
            assert modal.is_open(), "Предусловие не выполнено: модалка не открыта"

        with allure.step(f"Ввести уникальный текст Message: {unique_message!r}"):
            modal.fill_message(unique_message)

        with allure.step("Нажать Create"):
            modal.submit()

        notification = issue_page.notification

        # Проверка уведомления — ПЕРВАЯ после действия: флаг живёт ~5с.
        with allure.step("Появилось уведомление об успешном создании"):
            expect(notification.locator(FLAG_KIND_SUCCESS)).to_be_visible()

        with allure.step("Заголовок уведомления = 'Success'"):
            expect(notification.title_locator(FLAG_KIND_SUCCESS)).to_have_text(
                FLAG_KIND_SUCCESS
            )

        with allure.step(
            f"Текст уведомления = {REMINDER_CREATED_SUCCESS_TEXT!r}"
        ):
            expect(notification.body_locator(FLAG_KIND_SUCCESS)).to_have_text(
                REMINDER_CREATED_SUCCESS_TEXT
            )

        with allure.step("Тип уведомления определяется по иконке как Success"):
            assert notification.kind(FLAG_KIND_SUCCESS) == FLAG_KIND_SUCCESS

        with allure.step("Уведомление закрывается кнопкой Dismiss"):
            assert notification.dismiss(FLAG_KIND_SUCCESS), (
                "Кнопка Dismiss не найдена внутри уведомления"
            )

        # Долгая проверка контента — ПОСЛЕ проверки уведомления.
        with allure.step("Ремайндер с этим текстом есть в секции Reminder"):
            assert issue_page.reminder_panel.has_reminder_with_text(
                unique_message
            ), "Созданный ремайндер не найден в секции Reminder"


@allure.feature("Creation Form")
@allure.story("Notifications")
class TestWarningNotification:
    """Предупреждение о видимости задачи получателями (REMCL-2734/2735)."""

    @allure.title(
        "REMCL-2734: после создания ремайндера для Reporter появляется "
        "предупреждение о видимости задачи"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("REMCL-2734")
    @pytest.mark.functional
    def test_warning_notification_about_recipients_visibility(
        self, issue_page: IssuePage, issue_key: str
    ) -> None:
        """
        REMCL-2734. Проверяет тип/заголовок уведомления через новый
        компонент, а не только наличие текста (как делал прежний
        IssuePage.has_recipients_visibility_warning_flag()).

        ТЕХНИЧЕСКИЙ РИСК: kind="Warning" опирается на скриншот
        REMCL-2734/2735 (жёлтый треугольник + заголовок "Warning"), точный
        aria-label иконки вживую не снят. Если тип не совпадёт — тест
        упадёт на проверке заголовка, и это будет полезная находка:
        поправить _KNOWN_KINDS/FLAG_KIND_WARNING по факту.
        """
        from pages.issue_page import RECIPIENTS_VISIBILITY_WARNING_TEXT

        unique_message = _unique_message("notify-warning")

        with allure.step("Открыть задачу и форму создания ремайндера"):
            issue_page.open(issue_key)
            assert issue_page.has_reminder_section(), (
                "Секция Reminder не найдена на странице задачи"
            )
            issue_page.reminder_panel.expand()
            modal = issue_page.reminder_panel.open_create_modal()

        with allure.step("Оставить единственным получателем Reporter"):
            modal.open_dropdown()
            modal.clear_all()
            modal.search("Reporter")
            modal.wait_for_search_to_settle()
            modal.select_in_users_section("Reporter")
            modal.close_dropdown_by_clicking_outside()

        with allure.step(f"Ввести уникальный текст Message: {unique_message!r}"):
            modal.fill_message(unique_message)

        with allure.step("Нажать Create"):
            modal.submit()

        notification = issue_page.notification

        with allure.step("Появилось предупреждающее уведомление"):
            expect(
                notification.page.get_by_text(
                    RECIPIENTS_VISIBILITY_WARNING_TEXT, exact=False
                ).first
            ).to_be_visible()

        with allure.step("Заголовок уведомления = 'Warning'"):
            expect(notification.title_locator(FLAG_KIND_WARNING)).to_have_text(
                FLAG_KIND_WARNING
            )


# =============================================================================
# Honest skip: кейс подтверждён по разметке, но заблокирован отсутствующим
# Page Object (см. причину).
# =============================================================================