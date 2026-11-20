"""
ДОБАВЛЕНО (2026-11-19): разовый диагностический скрипт — показывает RAW
(через repr(), чтобы были видны невидимые байты — лишний пробел вместо
"+", мягкий перенос строки от MIME encoded-word и т.п.) темы писем,
реально лежащих в INBOX ящика MAIL_IMAP_* за последние N минут.

Зачем: MailClient.wait_for_email() (см. utils/mail_client.py) может
поллить ящик долгими минутами (таймаут берётся из MAIL_WAIT_TIMEOUT_S/
явного timeout_s в самом тесте — для REMCL-1114 и т.п. он сознательно
большой, см. docstring соответствующего теста), и ждать весь этот
таймаут только для того, чтобы увидеть RAW-темы писем в сообщении об
ошибке — медленно, если нужно быстро понять, что реально происходит с
письмом ПРЯМО СЕЙЧАС (например, пока связанный автотест ещё выполняется
или уже остановлен вручную). Этот скрипт делает ТОЛЬКО то, что делает
MailClient.list_recent_subjects() — без content-фильтра и без поллинга —
и выводит результат немедленно.

Запуск из корня проекта:
    python -m scripts.debug_mail_subjects
    python -m scripts.debug_mail_subjects --minutes 10

По умолчанию ищет письма за последние 15 минут (по часам ЭТОЙ машины,
в UTC). Подключение, как и везде в MailClient, ТОЛЬКО на чтение
(mark_seen=False) — скрипт не помечает письма прочитанными и не
изменяет состояние ящика.

ДОБАВЛЕНО (2026-11-19): сначала выводится MailClient.debug_snapshot() —
текущая папка, общее число писем в ней и RAW Date-заголовок (БЕЗ
парсинга — видно, есть ли там часовой пояс вообще) нескольких последних
писем, НЕЗАВИСИМО от какого-либо фильтра по дате. Это позволяет сразу
отличить "мы вообще не в той папке/ящике" от "письмо есть, но дата/текст
не совпадают" — см. ИСПРАВЛЕНО (2026-11-19) в докстринге utils/
mail_client.py (включая разбор, почему расхождение часовых поясов само
по себе не обязано ломать сравнение, но отсутствие зоны в самом
Date-заголовке — вполне реальная причина).

ДОБАВЛЕНО (2026-11-19, по живому прогону): если письмо визуально видно
во "Входящих" в вебе почты, но debug_snapshot() по INBOX его не находит
— используйте --list-folders, чтобы увидеть ВСЕ папки на сервере и
число писем в каждой (у некоторых провайдеров автоматические/массовые
письма, к которым относятся и уведомления Jira, попадают НЕ в INBOX, а
в отдельную папку, хотя в вебе это визуально выглядит одной лентой). Как
только нужная папка найдена — передайте её явно через --folder, чтобы
посмотреть её содержимое тем же способом, что и INBOX.

    python -m scripts.debug_mail_subjects --list-folders
    python -m scripts.debug_mail_subjects --folder "Рассылки" --minutes 30
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from config.settings import get_settings
from utils.mail_client import MailClient


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--minutes",
        type=int,
        default=15,
        help="За сколько минут назад искать письма (по умолчанию 15).",
    )
    parser.add_argument(
        "--folder",
        type=str,
        default=None,
        help="Папка для проверки вместо INBOX (имя — как показывает --list-folders).",
    )
    parser.add_argument(
        "--list-folders",
        action="store_true",
        help=(
            "Вместо снимка INBOX — показать ВСЕ папки на сервере и число "
            "писем в каждой (диагностика 'не та папка/ящик')."
        ),
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.has_mail_imap_credentials():
        raise SystemExit(
            "MAIL_IMAP_HOST/MAIL_IMAP_LOGIN/MAIL_IMAP_PASSWORD не заданы "
            "в .env — см. README -> 'Проверка email-уведомлений'."
        )

    client = MailClient(settings)

    if args.list_folders:
        folders = client.list_folders()
        print("Папки на сервере и число писем в каждой:")
        if not folders:
            print("  (не удалось получить список папок — см. предупреждение выше)")
        for name, count in folders:
            print(f"  {name!r}: {count if count is not None else '?'}")
        return

    snapshot = client.debug_snapshot(latest_limit=5, folder=args.folder)
    print(f"Текущая папка: {snapshot.folder!r}")
    print(f"Всего писем в этой папке (без фильтра): {snapshot.total_messages!r}")
    print("Последние письма (RAW Date-заголовок, без парсинга):")
    if not snapshot.latest:
        print(
            "  (папка пуста или снимок не удалось получить — см. "
            "предупреждение выше, если оно было)"
        )
    for info in snapshot.latest:
        print(f"  subject={info.subject!r}")
        print(f"    date_str (RAW)={info.date_str!r}")
        print(f"    date (распарсенный, tzinfo={info.date.tzinfo!r})={info.date!r}")
    print()

    since = datetime.now(timezone.utc) - timedelta(minutes=args.minutes)
    subjects = client.list_recent_subjects(since, limit=20, folder=args.folder)

    folder_label = args.folder or "INBOX"
    print(
        f"Письма в {folder_label!r} с {since.isoformat()} (по часам этой машины, UTC):"
    )
    if not subjects:
        print(
            "  (ничего не найдено за это окно — сравните с 'последние "
            "письма' выше: если там тоже ничего похожего — скорее всего, "
            "это не та папка/ящик; если похожее письмо ТАМ есть, но не "
            "попало сюда — смотрите на его date_str/date выше, особенно "
            "наличие часового пояса в RAW Date-заголовке)."
        )
    for subject in subjects:
        print(f"  {subject!r}")


if __name__ == "__main__":
    main()
