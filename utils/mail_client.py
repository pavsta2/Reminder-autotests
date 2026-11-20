"""
Клиент для проверки РЕАЛЬНОЙ отправки email-уведомлений плагином Reminder —
поверх библиотеки imap-tools (см. requirements.txt). Используется тестами
с меткой @pytest.mark.email (REMCL-1114 и т.п., см. tests/ui/
test_reminder_recipients.py) через фикстуру mail_client в
fixtures/conftest.py — честно skip'ается там же, если MAIL_IMAP_* не
заданы в .env (см. Settings.has_mail_imap_credentials).

ВАЖНО (read-only): подключение к ящику ТОЛЬКО на чтение — mark_seen=False
на каждом fetch(). Тест не должен помечать письма прочитанными, удалять их
или как-либо иначе изменять состояние реального почтового ящика (см.
Project Instructions).

ТЕХНИЧЕСКИЙ РИСК: этот модуль написан по документации imap-tools
(сигнатуры MailBox.login/fetch, AND(date_gte=...), атрибуты MailMessage —
проверены локально через `python -c "import imap_tools; ..."`), но НЕ
подтверждён живым подключением к реальному ящику — на момент написания в
.env ещё не заданы MAIL_IMAP_HOST/_LOGIN/_PASSWORD (см. .env в репозитории
пользователя, не .env.example — см. README). При первом реальном прогоне
с настоящими кредами стоит перепроверить это предположение, особенно:
  - поведение AND(date_gte=...) на конкретном IMAP-сервере (mail.ru/
    inbox.ru, см. Project Instructions про пароль приложения для IMAP);
  - кодировку/формат msg.subject на письмах от Atlassian (на случай,
    если тема приходит в MIME encoded-word форме, которую imap-tools не
    раскодирует сам — тогда понадобится доп. decode).

ДОБАВЛЕНО (2026-11-18, для REMCL-1114 — см. tests/ui/test_reminder_
recipients.py): поиск по умолчанию проверяет совпадение `contains` И в
теме письма, И в тексте/HTML тела — а не только в теме, как было раньше.
ТЕХНИЧЕСКИЙ РИСК: НЕ подтверждено вживую, кладёт ли плагин Reminder
введённый пользователем текст Message в ТЕМУ письма, в ТЕЛО, или и туда,
и туда — поиск по обоим местам сразу выбран как более надёжный вариант по
умолчанию (достаточно совпадения хотя бы в одном), но после первого
реального прогона стоит сузить его до фактически подтверждённого места,
если окажется, что совпадение в "неправильном" месте даёт ложные
срабатывания (например, если тема письма по какой-то причине содержит
текст ДРУГОГО, более старого письма).

ИСПРАВЛЕНО (2026-11-19, по живому прогону test_single_reminder_when_
recipient_selected_via_multiple_paths): шаг проверки письма либо падал с
`imaplib.IMAP4.abort: command: LOGOUT => socket error: EOF`, либо
зависал настолько долго, что требовалось вручную останавливать прогон.
Причина — ДВЕ связанные вещи:
  1. `MailBox(...)` создавался без `timeout` — у imaplib по умолчанию
     таймаут сокета не задан (блокирует НАВСЕГДА); если провайдер
     (mail.ru/inbox.ru) молча не отвечает на сокет-операцию, процесс
     зависает без шанса сработать по дедлайну `wait_for_email` — именно
     это и давало "зависает очень долго, ручная остановка".
  2. `_search()` открывает НОВОЕ IMAP-соединение (login...logout) на
     КАЖДОЙ попытке поллинга (по умолчанию каждые MAIL_POLL_INTERVAL_S=5
     сек) — частые login/logout подряд — известный триггер анти-абузных
     эвристик бесплатных почтовых провайдеров, которые могут оборвать
     соединение сервером ещё до того, как клиент успел корректно
     разлогиниться; клиент в этот момент пытается отправить LOGOUT в уже
     мёртвый сокет -> `imaplib.IMAP4.abort: ... socket error: EOF`
     (именно это и наблюдалось в реальном прогоне).
Исправлено: (a) `MailBox(..., timeout=settings.mail_imap_timeout_s)` —
теперь любая отдельная сокет-операция ограничена по времени (см.
Settings.mail_imap_timeout_s в config/settings.py, по умолчанию 20 сек)
вместо бесконечного блокирования; (b) весь `with MailBox(...) as
mailbox:` обёрнут в try/except по `(OSError, imaplib.IMAP4.abort,
imaplib.IMAP4.error)` — транзиентный сбой соединения (включая новый
socket.timeout от (a), который в Python 3.10+ является подклассом
OSError) теперь тихо считается "эта попытка поллинга не удалась",
`wait_for_email` просто повторит попытку на следующей итерации, вместо
того чтобы ронять весь тест или зависать навсегда.

ДОБАВЛЕНО (2026-11-19, по живому прогону): list_recent_subjects() и
диагностика в wait_for_email() показали 0 писем в окне since — хотя
письмо, по словам пользователя, точно пришло. Пользователь предположил,
что причина — часовой пояс (письма в вебе почты показываются в
UTC+03:00, а since/сравнение — в UTC). ТЕХНИЧЕСКИ это предположение само
по себе НЕ обязательно верно: Python корректно сравнивает timezone-aware
datetime по абсолютному моменту независимо от того, в каком поясе каждый
из них выражен (date_gte=since_date тоже передаётся в IMAP как
календарная дата в UTC — "SINCE 19-Nov-2026" — что было бы проблемой
только вблизи полуночи по границе суток, а не в середине дня). РЕАЛЬНЫЙ
риск в другом месте — см. parse_email_date в imap_tools: если Date-
заголовок письма почему-то НЕ содержит зону (редкий, но возможный
случай), msg.date возвращается NAIVE, и наш код (см. _search/
list_recent_subjects) безусловно доклеивает к нему tzinfo=UTC — то есть
ПРЕДПОЛАГАЕТ, что наивные часы/минуты уже были в UTC. Если на самом деле
сервер отправителя писал их в своём локальном поясе (например, MSK), это
совершенно реальный источник рассинхронизации именно того типа, который
предположил пользователь — просто механизм чуть другой (не "мы сравниваем
не в том поясе", а "мы не можем понять, в каком поясе были часы, если
сам заголовок зону не указал").
Добавлен debug_snapshot() — ОДНИМ запросом показывает: текущую папку,
общее число писем в ней (вне зависимости от даты/текста) и RAW Date-
заголовок (msg.date_str, без парсинга) + распарсенную дату (msg.date,
с её фактическим tzinfo или None) для нескольких последних писем — чтобы
окончательно, не теоретически, увидеть: (a) мы вообще в той папке/ящике,
где лежат письма от Jira; (b) что реально написано в их Date-заголовке и
есть ли там зона. См. scripts/debug_mail_subjects.py.
"""

from __future__ import annotations

import imaplib
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from imap_tools import AND, MailBox

from config.settings import Settings

logger = logging.getLogger(__name__)

# Транзиентные сбои IMAP-соединения (обрыв сокета, таймаут, неудачный
# LOGOUT/LOGIN) — см. ИСПРАВЛЕНО (2026-11-19) в докстринге модуля выше.
# socket.timeout/TimeoutError в Python 3.10+ — подклассы OSError, поэтому
# отдельно их ловить не нужно.
_TRANSIENT_IMAP_ERRORS = (OSError, imaplib.IMAP4.abort, imaplib.IMAP4.error)


@dataclass(frozen=True)
class MatchedEmail:
    """Снимок найденного письма — то немногое, что нужно тестам/Allure."""

    subject: str
    from_: str
    date: datetime
    text: str


@dataclass(frozen=True)
class LatestMessageInfo:
    """
    ДОБАВЛЕНО (2026-11-19): диагностический снимок ОДНОГО письма для
    MailClient.debug_snapshot() — RAW Date-заголовок БЕЗ парсинга
    (date_str) рядом с тем, как его распарсил imap_tools (date, со своим
    tzinfo или без), чтобы можно было визуально увидеть, есть ли в
    заголовке зона вообще (см. ИСПРАВЛЕНО 2026-11-19 в докстринге модуля
    про предположение пользователя о часовом поясе).
    """

    subject: str
    date_str: str
    date: datetime


@dataclass(frozen=True)
class MailboxSnapshot:
    """
    ДОБАВЛЕНО (2026-11-19): результат MailClient.debug_snapshot() —
    НЕ используется в проверках тестов, только для ручной диагностики
    (см. scripts/debug_mail_subjects.py) — отличить "письма вообще нет в
    этой папке/ящике" от "письмо есть, но не совпадает по дате/тексту".

    folder/total_messages — None, если снимок не удалось получить из-за
    транзиентного сбоя соединения (см. debug_snapshot ниже) — в этом
    случае latest будет пустым списком.
    """

    folder: str | None
    total_messages: int | None
    latest: list[LatestMessageInfo]


class MailClient:
    """
    Тонкая read-only обёртка над imap-tools для поллинга почтового ящика
    тестового пользователя (обычно того же, что и основной Jira-аккаунт —
    см. Settings.mail_imap_*).
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _search(self, contains: str, since: datetime) -> list[MatchedEmail]:
        """
        Одноразовый (без ожидания/поллинга) поиск писем, у которых `contains`
        встречается В ТЕМЕ ИЛИ В ТЕЛЕ (text/html) письма (см. ДОБАВЛЕНО
        2026-11-18 в докстринге модуля — какое именно поле реально
        использует плагин, не подтверждено вживую), пришедших не раньше
        `since`.

        `since` ОБЯЗАТЕЛЬНО timezone-aware (например, datetime.now(timezone.
        utc)) и должен быть зафиксирован ДО действия, которое присылает
        письмо — иначе можно словить старое письмо с похожим текстом из
        прошлых прогонов (см. Project Instructions).

        IMAP-критерий `date_gte` в imap-tools фильтрует по ДАТЕ (без
        времени), поэтому дополнительно сверяем точное время по msg.date —
        иначе в тот же календарный день могло бы пройти письмо, пришедшее
        РАНЬШЕ since, но в ту же дату.

        Транзиентные сбои соединения (таймаут сокета, обрыв во время
        LOGOUT и т.п. — см. ИСПРАВЛЕНО 2026-11-19 в докстринге модуля)
        НЕ пробрасываются наружу как исключение — эта попытка просто
        возвращает то, что успела собрать (обычно пустой список), и
        wait_for_email() повторит попытку на следующей итерации поллинга,
        как и в случае "письмо просто пока не пришло".
        """
        if since.tzinfo is None:
            raise ValueError(
                "since должен быть timezone-aware datetime (например, "
                "datetime.now(timezone.utc)) — naive datetime рискует "
                "некорректно сравниться с датой письма на сервере."
            )

        since_date = since.astimezone(timezone.utc).date()
        found: list[MatchedEmail] = []

        try:
            with MailBox(
                self._settings.mail_imap_host,
                self._settings.mail_imap_port,
                timeout=self._settings.mail_imap_timeout_s,
            ).login(
                self._settings.mail_imap_login,
                self._settings.mail_imap_password.get_secret_value(),
            ) as mailbox:
                for msg in mailbox.fetch(
                    AND(date_gte=since_date), mark_seen=False, reverse=True
                ):
                    body = msg.text or msg.html or ""
                    if contains not in (msg.subject or "") and contains not in body:
                        continue

                    msg_date = msg.date
                    if msg_date.tzinfo is None:
                        msg_date = msg_date.replace(tzinfo=timezone.utc)
                    if msg_date < since:
                        continue

                    found.append(
                        MatchedEmail(
                            subject=msg.subject or "",
                            from_=msg.from_ or "",
                            date=msg_date,
                            text=body,
                        )
                    )
        except _TRANSIENT_IMAP_ERRORS as exc:
            # Сбой мог произойти на ЛЮБОМ этапе: connect/login/fetch, или
            # даже на __exit__ (LOGOUT) уже ПОСЛЕ того, как fetch успел
            # собрать письма в found — в любом из этих случаев найденное
            # до сбоя не теряется, просто не считаем это провалом теста.
            logger.warning(
                "MailClient: транзиентный сбой IMAP-соединения на попытке "
                "поиска письма (%r) — считаем попытку неудачной, "
                "wait_for_email повторит её на следующем poll'е: %s",
                contains,
                exc,
            )

        return found

    def list_recent_subjects(
        self, since: datetime, limit: int = 10, folder: str | None = None
    ) -> list[str]:
        """
        ДОБАВЛЕНО (2026-11-19): диагностика для wait_for_email — RAW
        (без content-фильтра по `contains`) список msg.subject писем,
        пришедших не раньше `since` (та же логика even/less-than-since
        фильтрации по точному времени, что и в _search). Используется
        ТОЛЬКО для того, чтобы ПОКАЗАТЬ в AssertionError, что реально
        лежит в ящике в нужном окне времени, когда wait_for_email падает
        по таймауту, хотя по словам пользователя письмо точно пришло —
        см. ИСПРАВЛЕНО (2026-11-19) ниже в докстринге wait_for_email.

        `folder` — необязательное имя папки (по умолчанию "INBOX", как и
        везде в MailClient) — см. debug_snapshot()/list_folders() про
        автоматические/массовые письма, попадающие НЕ в INBOX у
        некоторых провайдеров.

        Темы возвращаются КАК ЕСТЬ (не через repr) — вызывающий код сам
        решает, как их показать; именно repr() в сообщении об ошибке
        делает видимыми невидимые различия (лишний пробел вместо "+",
        мягкий перенос строки от MIME encoded-word и т.п. — та же природа
        проблемы, что и апостроф в reminder_modal.py, см. его docstring).

        Транзиентный сбой соединения здесь НЕ фатален — это диагностика,
        а не часть проверки: любая ошибка просто возвращает то, что успели
        собрать (вплоть до пустого списка), чтобы не маскировать исходный
        AssertionError таймаута другим исключением.
        """
        if since.tzinfo is None:
            raise ValueError("since должен быть timezone-aware datetime (см. _search).")

        since_date = since.astimezone(timezone.utc).date()
        subjects: list[str] = []

        try:
            with MailBox(
                self._settings.mail_imap_host,
                self._settings.mail_imap_port,
                timeout=self._settings.mail_imap_timeout_s,
            ).login(
                self._settings.mail_imap_login,
                self._settings.mail_imap_password.get_secret_value(),
                initial_folder=folder or "INBOX",
            ) as mailbox:
                for msg in mailbox.fetch(
                    AND(date_gte=since_date), mark_seen=False, reverse=True
                ):
                    msg_date = msg.date
                    if msg_date.tzinfo is None:
                        msg_date = msg_date.replace(tzinfo=timezone.utc)
                    if msg_date < since:
                        continue
                    subjects.append(msg.subject or "")
                    if len(subjects) >= limit:
                        break
        except _TRANSIENT_IMAP_ERRORS as exc:
            logger.warning(
                "MailClient: не удалось получить диагностический список "
                "тем писем для сообщения об ошибке: %s",
                exc,
            )

        return subjects

    def debug_snapshot(
        self, latest_limit: int = 5, folder: str | None = None
    ) -> MailboxSnapshot:
        """
        ДОБАВЛЕНО (2026-11-19): диагностический снимок ящика ОДНИМ
        запросом, БЕЗ какого-либо фильтра по дате/тексту — текущая папка,
        общее число писем в ней и RAW Date-заголовок + распарсенная дата
        самых последних `latest_limit` писем (headers_only — быстрее,
        тело не нужно). См. scripts/debug_mail_subjects.py и ИСПРАВЛЕНО
        (2026-11-19) в докстринге модуля — нужен, чтобы РАЗЛИЧИТЬ две
        принципиально разные причины "письмо не найдено":
          (a) мы вообще не в той папке/ящике, где лежат письма от Jira —
              total_messages будет 0 или подозрительно маленьким, а
              latest будет содержать совсем не то, что ожидалось;
          (b) письмо есть, но не совпадает по дате/тексту — latest
              покажет РЕАЛЬНОЕ письмо с его RAW Date-заголовком, и будет
              видно, есть ли там часовой пояс (отсутствие зоны в
              Date-заголовке — реальный сценарий, в котором наивный
              msg.date некорректно доклеивается как UTC в _search/
              list_recent_subjects, а не просто "сравнение в другом
              поясе", которое сами по себе Python обрабатывает верно).

        `folder` — необязательное имя папки для подключения (по
        умолчанию "INBOX", как и везде в MailClient). ДОБАВЛЕНО
        (2026-11-19, по живому прогону): письмо, которое пользователь
        видел во входящих визуально, НЕ нашлось в INBOX по IMAP вообще —
        самое свежее письмо там оказалось не связанным с тестом (на 2+
        часа старше), хотя до этого пользователь был уверен, что видел
        письмо "только что". Вероятная причина — автоматические/массовые
        письма (к которым относятся и уведомления Jira) у некоторых
        провайдеров (mail.ru/inbox.ru) могут классифицироваться НЕ как
        INBOX, а в отдельную папку, которая в веб-интерфейсе визуально
        выглядит частью одной ленты "Входящие" (вкладки/категории), но на
        уровне IMAP — другая папка. См. list_folders() ниже — что
        показывает, в какой папке реально лежит письмо, после чего сюда
        можно передать её имя явно.

        НЕ используется в проверках тестов — только для ручной
        диагностики. Транзиентный сбой соединения не фатален: возвращает
        MailboxSnapshot с folder=None/total_messages=None/latest=[],
        не пробрасывая исключение.
        """
        result_folder: str | None = None
        total_messages: int | None = None
        latest: list[LatestMessageInfo] = []

        try:
            with MailBox(
                self._settings.mail_imap_host,
                self._settings.mail_imap_port,
                timeout=self._settings.mail_imap_timeout_s,
            ).login(
                self._settings.mail_imap_login,
                self._settings.mail_imap_password.get_secret_value(),
                initial_folder=folder or "INBOX",
            ) as mailbox:
                result_folder = mailbox.folder.get()
                try:
                    status = mailbox.folder.status()
                    total_messages = status.get("MESSAGES")
                except _TRANSIENT_IMAP_ERRORS:
                    pass  # не критично — latest всё равно покажет что-то полезное

                for msg in mailbox.fetch(
                    "ALL",
                    limit=latest_limit,
                    reverse=True,
                    headers_only=True,
                    mark_seen=False,
                ):
                    latest.append(
                        LatestMessageInfo(
                            subject=msg.subject or "",
                            date_str=msg.date_str or "",
                            date=msg.date,
                        )
                    )
        except _TRANSIENT_IMAP_ERRORS as exc:
            logger.warning(
                "MailClient: не удалось получить диагностический снимок ящика: %s",
                exc,
            )
            return MailboxSnapshot(folder=None, total_messages=None, latest=[])

        return MailboxSnapshot(
            folder=result_folder, total_messages=total_messages, latest=latest
        )

    def list_folders(self, limit: int = 20) -> list[tuple[str, int | None]]:
        """
        ДОБАВЛЕНО (2026-11-19): список ВСЕХ папок на сервере с числом
        писем в каждой — диагностика для случая, когда debug_snapshot()
        по INBOX не показывает ожидаемое письмо (см. ИСПРАВЛЕНО
        2026-11-19 выше и docstring debug_snapshot про автоматические/
        массовые письма, попадающие НЕ в INBOX у некоторых провайдеров).
        STATUS не требует переключения текущей папки (IMAP позволяет
        запрашивать статус любой папки без SELECT), так что соединение
        остаётся на INBOX — эта функция только СМОТРИТ на другие папки,
        не переключает в них рабочее соединение.

        count — None для папки, на которой STATUS не поддерживается
        сервером (например некоторые служебные папки) — не фатально,
        просто эта папка остаётся без количества. Ограничено `limit`
        папками, чтобы не зависать на ящиках с огромным числом папок.
        НЕ используется в проверках тестов. Транзиентный сбой соединения
        — пустой список, не исключение.
        """
        folders: list[tuple[str, int | None]] = []

        try:
            with MailBox(
                self._settings.mail_imap_host,
                self._settings.mail_imap_port,
                timeout=self._settings.mail_imap_timeout_s,
            ).login(
                self._settings.mail_imap_login,
                self._settings.mail_imap_password.get_secret_value(),
            ) as mailbox:
                for folder_info in mailbox.folder.list()[:limit]:
                    count: int | None = None
                    try:
                        status = mailbox.folder.status(
                            folder_info.name, options=["MESSAGES"]
                        )
                        count = status.get("MESSAGES")
                    except _TRANSIENT_IMAP_ERRORS:
                        count = None
                    folders.append((folder_info.name, count))
        except _TRANSIENT_IMAP_ERRORS as exc:
            logger.warning(
                "MailClient: не удалось получить список папок: %s",
                exc,
            )

        return folders

    def wait_for_email(
        self,
        contains: str,
        since: datetime,
        timeout_s: int | None = None,
        poll_interval_s: int | None = None,
    ) -> MatchedEmail:
        """
        Поллингом ждёт ПЕРВОЕ письмо, у которого `contains` встречается в
        теме или теле (см. _search), пришедшее не раньше `since`.
        Возвращает найденное письмо или падает с понятной AssertionError
        по таймауту.

        timeout_s/poll_interval_s по умолчанию берутся из settings.
        mail_wait_timeout_s / mail_poll_interval_s (90/5 сек — см. README),
        можно переопределить на конкретный вызов — например, в тесте,
        который ПЕРЕД этим ещё и ждёт наступления запланированного времени
        ремайндера (REMCL-1114 и т.п. — см. tests/ui/test_reminder_
        recipients.py), timeout_s обычно нужно явно увеличивать на это
        время ожидания.

        ИСПРАВЛЕНО (2026-11-19, по живому прогону — AssertionError по
        таймауту, хотя письмо, по словам пользователя, точно пришло ДО
        дедлайна): такой случай означает, что фильтр по `contains` не
        совпал ни с одним реально полученным письмом — то есть проблема
        НЕ во времени/поллинге, а в ТЕКСТОВОМ совпадении (неверная папка,
        расхождение часов между Jira-сервером и msg.date, невидимое
        отличие байтов — например " " вместо "+" после URL-декодирования,
        мягкий перенос строки от MIME encoded-word темы и т.п., — та же
        природа, что у исправленного ранее апострофа в ReminderModal).
        Чтобы не гадать вслепую при следующем падении, AssertionError по
        таймауту теперь дополнительно вызывает list_recent_subjects() и
        приводит в сообщении RAW (через repr()) темы ВСЕХ писем, которые
        реально лежат в ящике за это окно времени — это сразу покажет,
        то ли письма в ящике вообще нет (неверная папка/ящик/задержка
        сильнее MAIL_WAIT_TIMEOUT_S), то ли оно есть, но с другим текстом
        (видно будет, чем именно).
        """
        timeout = (
            timeout_s if timeout_s is not None else self._settings.mail_wait_timeout_s
        )
        interval = (
            poll_interval_s
            if poll_interval_s is not None
            else self._settings.mail_poll_interval_s
        )

        deadline = time.monotonic() + timeout
        attempts = 0
        while True:
            attempts += 1
            matches = self._search(contains, since)
            if matches:
                return matches[0]
            if time.monotonic() >= deadline:
                recent_subjects = self.list_recent_subjects(since, limit=10)
                if recent_subjects:
                    mailbox_hint = (
                        "В ящике за это время есть "
                        f"{len(recent_subjects)} письм(о/а), но ни одно не "
                        f"совпало по тексту — RAW темы (repr): "
                        f"{[repr(s) for s in recent_subjects]}. Если тема "
                        "похожа, но не совпадает — ищите невидимую разницу "
                        "в байтах (пробел вместо '+', мягкий перенос "
                        "строки от кодирования темы и т.п.)."
                    )
                else:
                    mailbox_hint = (
                        "В ящике за это время НЕ нашлось вообще НИ ОДНОГО "
                        "письма — проверьте, что письмо попадает именно в "
                        "INBOX (а не в Spam/другую папку или под другим "
                        "фильтром), что MAIL_IMAP_* подключается к тому же "
                        "ящику, куда шлёт Jira, и что часы между Jira-"
                        "сервером и тестовой машиной не рассинхронизированы "
                        "(since зафиксирован ПО ЧАСАМ ТЕСТОВОЙ МАШИНЫ)."
                    )
                raise AssertionError(
                    f"Письмо, содержащее {contains!r} (в теме или теле, не "
                    f"раньше {since.isoformat()}), не пришло за {timeout} "
                    f"сек ({attempts} попыт(ки/ка) поллинга). {mailbox_hint} "
                    "Проверьте также MAIL_IMAP_*/MAIL_WAIT_TIMEOUT_S в .env."
                )
            time.sleep(interval)

    def count_matching(self, contains: str, since: datetime) -> int:
        """
        Одноразовый (без ожидания) подсчёт писем, содержащих `contains` (в
        теме или теле, см. _search), пришедших не раньше `since`.
        Используется ПОСЛЕ wait_for_email — чтобы проверить дедупликацию
        получателей (ровно ОДНО письмо, а не два, REMCL-1114 и т.п., см.
        docstring соответствующего теста).

        ТЕХНИЧЕСКИЙ РИСК (см. ИСПРАВЛЕНО 2026-11-19 в докстринге модуля):
        _search() тихо проглатывает транзиентные сбои IMAP-соединения —
        если такой сбой произойдёт ПОСЛЕ того, как fetch() уже нашёл
        одно из двух писем, но ДО того, как нашёл второе, count_matching
        вернёт 1 вместо реальных 2, то есть дедуп-тест может ложно
        ПРОЙТИ при реальном дубликате письма. На практике маловероятно
        (единственный fetch-проход, без повторных login/logout — именно
        частые login/logout, а не сам fetch, провоцируют сбой), но это
        осознанный trade-off в пользу того, чтобы не зависать/не падать
        на временных сетевых сбоях у wait_for_email.
        """
        return len(self._search(contains, since))

    def assert_no_email(
        self, contains: str, since: datetime, wait_s: int | None = None
    ) -> None:
        """
        Для НЕГАТИВНЫХ кейсов ("письмо НЕ должно прийти"). Ждёт `wait_s`
        секунд (по умолчанию удвоенный mail_poll_interval_s — короткая
        пауза, а не полный mail_wait_timeout_s: мы не ждём событие, которое
        по кейсу не должно произойти, достаточно короткого окна) и падает,
        если письмо всё-таки нашлось.
        """
        wait = wait_s if wait_s is not None else self._settings.mail_poll_interval_s * 2
        time.sleep(wait)
        matches = self._search(contains, since)
        assert not matches, (
            f"Письмо, содержащее {contains!r}, пришло, хотя по кейсу не "
            f"должно было: {[m.subject for m in matches]!r}"
        )
