"""
BasePage — общая база для всех Page Object.
Содержит только технические обёртки (waits, клики, чтение текста, скриншоты).
Никаких assert здесь быть не должно — ассерты делаются в тестах.
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Optional, Union

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from config.settings import get_settings

_settings = get_settings()

# Иногда (сетевой/CDN-сбой на стороне Atlassian, не баг теста и не баг
# локатора) вместо ожидаемой страницы открывается страница с текстом
# "We tried to load scripts but something went wrong. Please make sure
# that your network settings allow you to download scripts from the
# following domain: https://identity-common-frontend...atl-paas.net" —
# Atlassian не смог подгрузить свою же статику с *.atl-paas.net.
# Лечится обычным повторным открытием страницы (см. BasePage.goto).
_SCRIPT_LOAD_ERROR_RE = re.compile(r"We tried to load scripts", re.IGNORECASE)

# Технический риск: точные тексты/локаторы всех возможных онбординг-оверлеев
# Jira (Quickstart-виджет, приглашение в Rovo, coachmark-тултипы продуктового
# тура, cookie-баннер и т.п.) не перечислить исчерпывающе — они появляются
# преимущественно на ПЕРВОМ визите в инстанс с нового браузерного профиля и
# могут меняться/A-B-тестироваться на стороне Atlassian. "Dismiss Quickstart"
# подтверждён живым прогоном (см. разведку локаторов секции Reminder);
# остальные — best-effort кандидаты по распространённым паттернам Atlassian UI.
#
# Регексы на "close" намеренно БЕЗ привязки к началу/концу строки (не "^close$") —
# у разных оверлеев это может быть "Close", "Close panel", "Close Rovo chat" и т.п.
#
# ИСПРАВЛЕНО (2026-11-25, по разметке правого сайдбара задачи, присланной
# пользователем — КРИТИЧНО): из списка УДАЛЁН кандидат
#   ("role_button", re.compile(r"collapse|minimize|свернуть", re.IGNORECASE))
# Он был угаданным best-effort паттерном и НИКОГДА не подтверждался вживую,
# но при этом ломал основной флоу: в актуальной разметке Jira Cloud кнопки
# сворачивания секций сайдбара имеют accessible name
#   aria-label="Collapse Details"
#   aria-label="Collapse Apps"
#   aria-label="Collapse "   (шеврон app-секции, напр. Reminder DEV)
# поэтому get_by_role("button", name=re.compile("collapse", re.I)) матчил их
# ВСЕ и кликал .first — то есть dismiss_onboarding_overlays() САМ сворачивал
# Details, а на следующем round — обёртку Apps, внутри которой лежит секция
# Reminder. Дальше тест не находил секцию и падал, хотя приложение было
# исправно. Это вторая (и более коварная) причина поломки помимо изначально
# свёрнутой обёртки Apps — см. находку 1 в докстринге
# pages/components/reminder_panel.py от 2026-11-25.
# Возвращать этот кандидат нельзя: любое "сворачивание" в этом UI — это
# продуктовый тоггл секции, а не закрытие онбординг-оверлея.
_ONBOARDING_DISMISS_CANDIDATES = [
    ("role_button", "Dismiss Quickstart"),
    ("role_button", re.compile(r"close", re.IGNORECASE)),
    ("aria_label", re.compile(r"close", re.IGNORECASE)),
    ("role_button", re.compile(r"got it|понятно", re.IGNORECASE)),
    ("role_button", re.compile(r"no,?\s thanks|нет,?\s спасибо", re.IGNORECASE)),
    ("role_button", re.compile(r"skip tour|пропустить тур", re.IGNORECASE)),
]

# Плавающая кнопка Rovo (AI-ассистент Jira) в правом нижнем углу — отдельный
# случай: это не разовый онбординг-баннер, а постоянный toggle-элемент
# ("Open Rovo Chat"), который может сам разворачиваться в панель чата и
# перекрывать/перехватывать клики в сайдбаре. Если она уже раскрыта —
# повторный клик по той же кнопке обычно её сворачивает (toggle).
_ROVO_TOGGLE_BUTTON_NAME = re.compile(r"Rovo", re.IGNORECASE)


class BasePage:
    """Базовый класс для Page Object. Принимает Playwright Page."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.timeout = _settings.default_timeout_ms

    # --- Навигация ---

    def goto(self, url: str, max_attempts: int = 3) -> None:
        """
        Переход по url с повторной попыткой при транзиентной странице-ошибке
        загрузки скриптов Atlassian (см. _SCRIPT_LOAD_ERROR_RE выше) — это
        сетевой/CDN-сбой на стороне Atlassian, не связанный с логикой теста,
        и обычно лечится простым повторным открытием страницы.
        """
        for attempt in range(1, max_attempts + 1):
            self.page.goto(url, wait_until="domcontentloaded")
            if not self._has_script_load_error():
                return
            if attempt == max_attempts:
                raise AssertionError(
                    "Atlassian показал страницу ошибки загрузки скриптов "
                    f"('We tried to load scripts...') после {max_attempts} попыток "
                    f"открыть {url!r}. Похоже на временный сетевой/CDN-сбой на стороне "
                    "Atlassian (домен identity-common-frontend...atl-paas.net), "
                    "а не на проблему теста — попробуйте перезапустить позже."
                )
            time.sleep(2)

    def _has_script_load_error(self, timeout_ms: int = 1_500) -> bool:
        try:
            self.page.get_by_text(_SCRIPT_LOAD_ERROR_RE).first.wait_for(
                state="visible", timeout=timeout_ms
            )
            return True
        except PlaywrightTimeoutError:
            return False

    def reload(self) -> None:
        self.page.reload(wait_until="domcontentloaded")

    @property
    def current_url(self) -> str:
        return self.page.url

    # --- Клики / ввод ---

    def click(self, locator: Locator) -> None:
        locator.wait_for(state="visible", timeout=self.timeout)
        locator.click()

    def click_if_visible(self, locator: Locator, timeout_ms: Optional[int] = None) -> bool:
        """
        Клик по элементу, если он появился за timeout_ms — иначе тихо продолжаем.
        Используется для необязательных диалогов (например, отказ от 2FA-промпта).
        Сам клик тоже ограничен таймаутом — чтобы не зависнуть на 30с по
        умолчанию, если элемент виден, но не кликабелен/пропал в процессе.
        """
        timeout = timeout_ms or 3_000
        try:
            locator.wait_for(state="visible", timeout=timeout)
            locator.click(timeout=timeout)
            return True
        except PlaywrightTimeoutError:
            return False

    def fill(self, locator: Locator, value: str) -> None:
        locator.wait_for(state="visible", timeout=self.timeout)
        locator.fill(value)

    def press(self, locator: Locator, key: str) -> None:
        locator.press(key)

    # --- Чтение состояния (без assert'ов — тест решает, что с этим делать) ---

    def is_visible(self, locator: Locator, timeout_ms: Optional[int] = None) -> bool:
        try:
            locator.wait_for(state="visible", timeout=timeout_ms or self.timeout)
            return True
        except PlaywrightTimeoutError:
            return False

    def get_text(self, locator: Locator) -> str:
        locator.wait_for(state="visible", timeout=self.timeout)
        return (locator.text_content() or "").strip()

    # --- Диагностика на падение ---

    def screenshot(self, path: Union[str, Path]) -> None:
        self.page.screenshot(path=str(path), full_page=True)

    # --- Онбординг-оверлеи (Quickstart, Rovo, coachmark-тултипы и т.п.) ---

    def dismiss_onboarding_overlays(self, rounds: int = 3) -> None:
        """
        Best-effort закрытие всплывающих окон онбординга, которые Jira может
        показывать на первом визите в инстанс с нового браузерного профиля
        (см. технический риск в комментарии к _ONBOARDING_DISMISS_CANDIDATES).
        Ни один из кандидатов не обязателен — отсутствие не считается ошибкой.

        rounds: сколько раз повторить проход по кандидатам — некоторые
        оверлеи появляются по очереди (один закрылся — показался следующий).

        ВАЖНО (2026-11-25): этот метод НЕ ДОЛЖЕН трогать продуктовые тогглы
        сворачивания секций сайдбара (Details / Apps / app-секции). Кандидат
        по "collapse|minimize" удалён именно поэтому — см. развёрнутый
        комментарий у _ONBOARDING_DISMISS_CANDIDATES. Если в будущем
        появится онбординг-оверлей, который реально нужно свернуть, для него
        нужен Узкий подтверждённый локатор (data-testid конкретного оверлея),
        а не общий глагол в accessible name.
        """
        try:
            self.page.keyboard.press("Escape")
        except Exception:
            pass

        for _ in range(rounds):
            clicked_any = False
            for kind, name in _ONBOARDING_DISMISS_CANDIDATES:
                if kind == "role_button":
                    locator = self.page.get_by_role("button", name=name)
                else:  # aria_label
                    locator = self.page.get_by_label(name)
                if self.click_if_visible(locator.first, timeout_ms=1_500):
                    clicked_any = True
            if not clicked_any:
                break

        self._collapse_rovo_if_expanded()

    def _collapse_rovo_if_expanded(self) -> None:
        """
        Плавающая кнопка Rovo (правый нижний угол) — toggle-элемент
        (aria-expanded). Если чат-панель уже раскрыта — кликаем по той же
        кнопке ещё раз, чтобы свернуть, и дополнительно жмём Escape (часть
        чат-панелей закрывается только так).

        Это ЕДИНСТВЕННОЕ место, где мы осознанно сворачиваем продуктовый
        toggle: Rovo-панель перекрывает сайдбар и перехватывает клики, а её
        локатор узкий (accessible name содержит "Rovo"), поэтому чужие
        секции под него не попадают.
        """
        rovo_button = self.page.get_by_role("button", name=_ROVO_TOGGLE_BUTTON_NAME).first
        try:
            rovo_button.wait_for(state="visible", timeout=1_500)
        except PlaywrightTimeoutError:
            return

        try:
            expanded = rovo_button.get_attribute("aria-expanded")
        except Exception:
            expanded = None

        if expanded == "true":
            try:
                rovo_button.click(timeout=2_000)
            except PlaywrightTimeoutError:
                pass
            try:
                self.page.keyboard.press("Escape")
            except Exception:
                pass