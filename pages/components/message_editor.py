"""
MessageEditor — поле Message в форме создания/редактирования ремайндера
(модалка "New reminder", см. pages/components/reminder_modal.py).

Вынесено в отдельный компонент, а не дописано в reminder_modal.py: это
самостоятельный rich-text редактор со своим toolbar, который, судя по всему,
будет переиспользоваться и в форме редактирования ремайндера (REMCL-1287).
ReminderModal инстанцирует его как `modal.message`.

ПОДТВЕРЖДЕНО (2026-11-20, DOM-снимок, снятый пользователем из консоли
DevTools, переключённой ВНУТРЬ iframe модалки — через "Inspect" по самому
полю, см. докстринг reminder_modal.py про top-контекст vs контекст iframe):

  <div class="MuiBox-root ...">
    <label id="reminder-message-label">Message</label>
    <div ... maxcontentheight="200px">
      <div id="reminder-message" class="quill">
        <div class="ql-toolbar ql-snow">
          size-picker | ql-bold ql-italic ql-underline ql-strike ql-blockquote
          | ql-list[value=ordered] ql-list[value=bullet] | ql-link
        </div>
        <div class="ql-container ql-snow">
          <div class="ql-editor ql-blank" contenteditable="true"
               role="textbox" aria-multiline="true"
               aria-labelledby="reminder-message-label"
               data-placeholder="A short reminder message (max. 255 symbols)">
            <p><br></p>
          </div>
          <div class="ql-clipboard" contenteditable="true" tabindex="-1">
          <div class="ql-tooltip ql-hidden"> (input + a.ql-action/ql-remove)
        </div>
      </div>
    </div>
  </div>

Выводы, на которые опираются локаторы ниже:
  1. Редактор — Quill (тема "snow"). Класс `ql-blank` на `.ql-editor`
     ставит сам Quill, когда документ пуст — placeholder рисуется CSS-
     псевдоэлементом `::before { content: attr(data-placeholder) }`, т.е.
     "placeholder виден" == "у редактора есть класс ql-blank".
  2. У редактора есть role="textbox" и accessible name через
     aria-labelledby -> "Message", поэтому основной локатор — get_by_role
     (приоритет 2), скоупнутый на контейнер #reminder-message.
     ВАЖНО: в документе ДВА contenteditable — второй служебный
     (`.ql-clipboard`, tabindex=-1). Искать редактор по [contenteditable]
     нельзя.
  3. Кнопки toolbar — `<button type="button" class="ql-...">` БЕЗ
     aria-label/title/текста (только SVG) — ни get_by_role(name=...), ни
     get_by_title неприменимы. Используем классы Quill (`ql-bold` и т.д.):
     это стабильные семантические классы библиотеки, а не сгенерированные
     emotion-классы `css-xxxx` (приоритет 6 из Project Instructions).
     ПРЕДЛОЖЕНИЕ разработчикам плагина: добавить aria-label на кнопки
     toolbar ("Bold", "Italic", ...) — это и a11y, и более устойчивые
     локаторы через get_by_role.
  4. Активный формат Quill подсвечивает классом `ql-active` на кнопке.
  5. id `reminder-message` / `reminder-message-label` выглядят заданными
     вручную (в отличие от генерируемых React `:r1:`). ТЕХНИЧЕСКИЙ РИСК
     (низкий): стабильность между перезагрузками явно не перепроверялась.
  6. Enter в редакторе САБМИТИТ форму (подтверждено прохождением
     test_enter_key_in_message_field_saves_reminder) — поэтому методы ниже
     НИКОГДА не жмут Enter внутри редактора. Как вводится многострочный
     текст (Shift+Enter?) — НЕ подтверждено (см. REMCL-1272).

НЕ подтверждено вживую (ТЕХНИЧЕСКИЙ РИСК до первого прогона):
  - точная HTML-разметка, которую Quill выдаёт для форматов: в Quill 1.x
    bold/italic/underline/strike -> <strong>/<em>/<u>/<s>, списки ->
    <ol>/<ul><li>; в Quill 2.x списки -> <ol><li data-list="ordered|bullet">.
    Версия Quill в плагине неизвестна, поэтому list_items() поддерживает
    обе разметки явно (а не угадывает одну);
  - поведение встроенного попапа ссылки (.ql-tooltip) внутри формы.
"""

from __future__ import annotations

import re
from typing import Literal

from playwright.sync_api import FloatRect, FrameLocator, Locator

# Лейбл поля. Звёздочка допускается: при Linked item = Link поле, по
# кейсам REMCL-1265/1286, становится обязательным — как именно это
# отображается, ещё не подтверждено (см. раунд 2 разведки).
MESSAGE_LABEL_RE = re.compile(r"^Message\s*\*?\s*$")

FormatName = Literal[
    "bold",
    "italic",
    "underline",
    "strike",
    "blockquote",
    "ordered_list",
    "bullet_list",
    "link",
]

# Кнопки toolbar Quill (см. п.3 докстринга модуля — aria-label у них нет).
_FORMAT_BUTTON_SELECTORS: dict[str, str] = {
    "bold": "button.ql-bold",
    "italic": "button.ql-italic",
    "underline": "button.ql-underline",
    "strike": "button.ql-strike",
    "blockquote": "button.ql-blockquote",
    "ordered_list": "button.ql-list[value='ordered']",
    "bullet_list": "button.ql-list[value='bullet']",
    "link": "button.ql-link",
}

# HTML-тег, который Quill (1.x и 2.x одинаково) генерирует для inline-
# форматов — см. "НЕ подтверждено вживую" в докстринге модуля.
INLINE_FORMAT_TAGS: dict[str, str] = {
    "bold": "strong",
    "italic": "em",
    "underline": "u",
    "strike": "s",
}


class MessageEditor:
    """Компонент: rich-text (Quill) поле Message внутри формы ремайндера."""

    def __init__(self, frame: FrameLocator, dialog: Locator) -> None:
        # frame — iframe модалки (ReminderModal.frame), dialog — корневой
        # section[role="dialog"] в TOP-документе (ReminderModal._dialog):
        # нужен для проверки "поле не выходит за границы модалки".
        self._frame = frame
        self._dialog = dialog
        # Корневой контейнер Quill: <div id="reminder-message" class="quill">
        self._root: Locator = frame.locator("#reminder-message")
        # <label id="reminder-message-label">Message</label>
        self._label: Locator = frame.locator("#reminder-message-label")
        # Собственно редактор (.ql-editor): role=textbox + aria-labelledby.
        self._editor: Locator = self._root.get_by_role("textbox", name=MESSAGE_LABEL_RE)
        self._toolbar: Locator = self._root.locator(".ql-toolbar")
        # .ql-container — обёртка редактора, по её высоте меряем "поле
        # растёт по мере ввода" (REMCL-1031).
        self._container: Locator = self._root.locator(".ql-container")
        # Встроенный попап Quill для ввода URL ссылки.
        self._link_tooltip: Locator = self._root.locator(".ql-tooltip")
        self._link_input: Locator = self._link_tooltip.locator("input[type='text']")
        # "Save" в попапе — <a class="ql-action">, текст рисуется CSS ::before
        # (текстового узла нет), поэтому только по классу.
        self._link_save: Locator = self._link_tooltip.locator("a.ql-action")

    # --- Локаторы для expect() в тестах (только чтение) ---

    def label_locator(self) -> Locator:
        return self._label

    def editor_locator(self) -> Locator:
        return self._editor

    def toolbar_locator(self) -> Locator:
        return self._toolbar

    def format_button(self, name: FormatName) -> Locator:
        return self._toolbar.locator(_FORMAT_BUTTON_SELECTORS[name])

    # --- Ввод ---

    def fill(self, text: str) -> MessageEditor:
        """
        Заменяет содержимое редактора текстом `text` одной операцией
        (Playwright fill() на contenteditable = выделить всё + insertText —
        по эффекту ближе всего к ВСТАВКЕ из буфера, а не к посимвольному
        набору). Enter не нажимается (см. п.6 докстринга модуля).
        """
        self._editor.fill(text)
        return self

    def type_text(self, text: str, delay_ms: float = 0) -> MessageEditor:
        """
        Посимвольно "набирает" текст с клавиатуры в конец редактора —
        нужен там, где важна реакция на КАЖДЫЙ символ (ограничение 255
        символов, REMCL-1268), в отличие от fill().
        """
        self._editor.click()
        self._editor.press("ControlOrMeta+End")
        self._editor.press_sequentially(text, delay=delay_ms)
        return self

    def clear(self) -> MessageEditor:
        """Очищает редактор с клавиатуры: Ctrl/Cmd+A, Backspace."""
        self._editor.click()
        self._editor.press("ControlOrMeta+a")
        self._editor.press("Backspace")
        return self

    def select_all(self) -> MessageEditor:
        self._editor.click()
        self._editor.press("ControlOrMeta+a")
        return self

    def select_last_chars(self, count: int) -> MessageEditor:
        """
        Выделяет последние `count` символов текста (курсор в конец
        документа, затем Shift+ArrowLeft x count). Рассчитано на простой
        однострочный текст без суррогатных пар/emoji.
        """
        self._editor.click()
        self._editor.press("ControlOrMeta+End")
        for _ in range(count):
            self._editor.press("Shift+ArrowLeft")
        return self

    def apply_format(self, name: FormatName) -> MessageEditor:
        """Кликает кнопку форматирования в toolbar."""
        self.format_button(name).click()
        return self

    def add_link_to_selection(self, url: str) -> MessageEditor:
        """
        Превращает ВЫДЕЛЕННЫЙ текст в ссылку через кнопку Link и встроенный
        попап Quill. Сохраняем кликом по "Save" (a.ql-action), а не Enter —
        Enter в форме сабмитит ремайндер (п.6 докстринга модуля), и не
        подтверждено, что попап перехватывает его раньше формы.
        """
        self.apply_format("link")
        self._link_input.wait_for(state="visible")
        self._link_input.fill(url)
        self._link_save.click()
        return self

    def focus_via_tab(self, max_presses: int = 40) -> int | None:
        """
        Жмёт Tab (с ТЕКУЩЕГО фокуса), пока фокус не окажется в редакторе.
        Возвращает число нажатий или None, если за max_presses не дошли.
        Между предыдущим полем и редактором стоят кнопки toolbar (обычные
        <button>, они тоже в tab-порядке) — отсюда запас по max_presses.
        """
        keyboard = self._editor.page.keyboard
        for presses in range(1, max_presses + 1):
            keyboard.press("Tab")
            if self.is_focused():
                return presses
        return None

    # --- Чтение состояния ---

    def text(self) -> str:
        """
        Видимый текст редактора. Quill всегда держит завершающий перевод
        строки у последнего абзаца — его отрезаем.
        """
        return self._editor.inner_text().rstrip("\n")

    def html(self) -> str:
        return self._editor.inner_html()

    def placeholder(self) -> str | None:
        """Текст placeholder (атрибут data-placeholder, см. п.1 докстринга)."""
        return self._editor.get_attribute("data-placeholder")

    def is_blank(self) -> bool:
        """True, если Quill считает документ пустым (класс ql-blank)."""
        return "ql-blank" in (self._editor.get_attribute("class") or "").split()

    def is_focused(self) -> bool:
        return bool(
            self._editor.evaluate("el => el === el.ownerDocument.activeElement")
        )

    def is_format_active(self, name: FormatName) -> bool:
        cls = self.format_button(name).get_attribute("class") or ""
        return "ql-active" in cls.split()

    def fragments_with_format(self, name: FormatName) -> list[str]:
        """Тексты всех inline-фрагментов с форматом name (bold/italic/...)."""
        tag = INLINE_FORMAT_TAGS[name]
        return self._editor.locator(tag).all_inner_texts()

    def list_items(self) -> list[dict[str, str]]:
        """
        Элементы списков в редакторе: [{"text": ..., "kind": "ordered" |
        "bullet"}]. Поддерживает обе известные разметки Quill (см.
        докстринг модуля): 2.x — li[data-list], 1.x — тип родителя ol/ul.
        """
        return self._editor.evaluate(
            """el => [...el.querySelectorAll('li')].map(li => ({
                text: li.innerText.trim(),
                kind: li.getAttribute('data-list')
                      || (li.parentElement.tagName === 'OL' ? 'ordered' : 'bullet'),
            }))"""
        )

    def links(self) -> list[dict[str, str]]:
        """Ссылки в редакторе: [{"text": ..., "href": ...}]."""
        return self._editor.evaluate("""el => [...el.querySelectorAll('a')].map(a => ({
                text: a.innerText.trim(), href: a.getAttribute('href') || '',
            }))""")

    def count_elements(self, css: str) -> int:
        """Сколько элементов по css внутри редактора (для XSS-проверок)."""
        return self._editor.locator(css).count()

    def has_horizontal_overflow(self) -> bool:
        """True, если содержимое редактора шире видимой области."""
        return bool(self._editor.evaluate("el => el.scrollWidth > el.clientWidth + 1"))

    def container_height(self) -> float:
        box = self._container.bounding_box()
        return box["height"] if box else 0.0

    # Боксы — в координатах ВЬЮПОРТА основной страницы (Playwright сам
    # пересчитывает координаты элементов внутри iframe), поэтому бокс
    # поля из iframe можно напрямую сравнивать с боксом dialog из TOP.
    def field_box(self) -> FloatRect | None:
        return self._root.bounding_box()

    def toolbar_box(self) -> FloatRect | None:
        return self._toolbar.bounding_box()

    def container_box(self) -> FloatRect | None:
        return self._container.bounding_box()

    def dialog_box(self) -> FloatRect | None:
        return self._dialog.bounding_box()

    def field_screenshot(self) -> bytes:
        """PNG-скриншот поля (toolbar + редактор) — для вложений в Allure."""
        return self._root.screenshot()
