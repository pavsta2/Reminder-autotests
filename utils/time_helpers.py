"""
Хелперы для вычисления времени исполнения ремайндера в тестах (REMCL-1114/
1115/1116/1118/1119, см. tests/ui/test_reminder_recipients.py).

Поле "Date & time" в модалке New reminder (см. pages/components/
reminder_modal.py, п.13 докстринга модуля — set_specific_datetime/
select_minute) позволяет выбрать минуту ТОЛЬКО с шагом 5 (00, 05, 10, ...,
55) — подтверждено живым просмотром через built-in browser 2026-11-18
(прямой ввод цифр с клавиатуры в поле не меняет значение; единственный
рабочий способ — клик по пункту скроллируемого списка в открытом попапе).
round_up_to_next_five_minutes() даёт вызывающему тесту ближайшее БУДУЩЕЕ
время, кратное 5 минутам, которое реально можно выставить через UI.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Поле "Date & time" в модалке показывает время в Europe/Moscow — см.
# tests/ui/test_reminder_recipients.py (там та же константа объявлена
# локально; ДОБАВЛЕНО сюда 2026-11-20, чтобы email-тесты других полей —
# tests/ui/test_reminder_message.py — не копировали её).
MOSCOW_TZ = ZoneInfo("Europe/Moscow")

# Запас на задержку срабатывания ремайндера на сервере ПОСЛЕ наступления
# запланированного момента (не измерен — см. подробное обоснование у
# _PLUGIN_SCHEDULE_POLL_BUFFER_S в tests/ui/test_reminder_recipients.py).
PLUGIN_SCHEDULE_POLL_BUFFER_S = 5 * 60


def round_up_to_next_five_minutes(
    moment: datetime, min_buffer: timedelta = timedelta(minutes=1)
) -> datetime:
    """
    Округляет `moment` + `min_buffer` ВВЕРХ до ближайшей минуты, кратной 5,
    обнуляя секунды/микросекунды.

    `min_buffer` — минимальный запас на то, что между вычислением времени
    в тесте (например, datetime.now(timezone_...)) и реальным кликом
    Create в модалке пройдёт какое-то (небольшое) время: без этого запаса
    "сейчас + округление" иногда могло бы округлиться НАЗАД к уже
    прошедшей минуте (например, если сейчас 12:04:59.9 — округление без
    буфера дало бы 12:05:00, что технически ещё не прошло, но крайне
    близко к границе; буфер в 1 минуту по умолчанию даёт более безопасный
    запас). Для REMCL-1114 и т.п. ("ремайндер на несколько минут вперёд")
    вызывающий тест обычно передаёт свой собственный `moment` уже со
    сдвигом на нужное число минут, а `min_buffer` оставляет дефолтным —
    тогда итоговое время будет "не раньше, чем moment + N минут + запас,
    округлённое вверх до кратного 5".

    Пример: moment=12:01:00, min_buffer=1 мин -> 12:02:00 -> округление
    вверх до кратного 5 -> 12:05:00.
    """
    target = (moment + min_buffer).replace(second=0, microsecond=0)
    remainder = target.minute % 5
    if remainder:
        target += timedelta(minutes=5 - remainder)
    return target
