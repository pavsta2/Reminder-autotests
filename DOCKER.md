# Запуск через Docker Desktop (macOS 12 и другие случаи, когда `playwright install` не ставит бандлованный браузер)

Используем официальный образ `mcr.microsoft.com/playwright/python` — в нём уже
есть Python, все браузеры (chromium/firefox/webkit) и системные зависимости
для них. Внутри Linux-контейнера версия macOS хоста роли не играет, поэтому
ограничение Playwright "does not support chromium on mac12" здесь не
применяется вообще — `BROWSER_CHANNEL` из `.env` для Docker-сценария не нужен
(оставьте его пустым или не задавайте).

## 0. Что нужно на маке

- Docker Desktop запущен (иконка кита в менюбаре — "Engine running").
- Репозиторий `reminder-autotests` распакован в рабочую папку.

## 1. Проверить версию playwright, которая у вас реально установилась

`requirements.txt` задаёт только МИНИМАЛЬНУЮ версию (`playwright>=1.45`), а не
точный пин — pip сам подбирает совместимую с вашим Python. Поэтому перед
сборкой образа узнайте, какая версия встала фактически:

```
python3 -m pip show playwright | grep Version
```

Тег образа в `Dockerfile` (`FROM mcr.microsoft.com/playwright/python:vX.Y.Z-noble`)
**должен совпадать** с этой версией — иначе Playwright внутри контейнера не
найдёт нужные браузерные бинарники (они жёстко привязаны к релизу). Сейчас
там `v1.63.0-noble` — это было верно для окружения, где собирался этот
репозиторий, но у вас локально может встать другая версия. Поправьте тег в
`Dockerfile` под вывод команды выше, если он отличается.

## 2. Заполнить .env

```
cp .env.example .env
```

Впишите `JIRA_HOST`, `JIRA_USER_EMAIL`, `JIRA_USER_PASSWORD`. `BROWSER_CHANNEL`
для Docker-сценария оставьте пустым — это был обходной путь только для
локального запуска без Docker на старой macOS.

`.env` специально в `.dockerignore` — он не попадёт внутрь образа при сборке
(секреты не запекаются в слои), а передаётся в контейнер отдельно при каждом
запуске через `--env-file .env` (или `env_file:` в docker-compose.yml).

## 3. Собрать образ

```
docker build -t reminder-autotests:local .
```

Первая сборка качает базовый образ (~1-2 ГБ, там браузеры) — может занять
несколько минут в зависимости от интернета. Повторные сборки после правок в
коде тестов — быстрые (кешируется слой с `pip install`, если requirements.txt
не менялся).

Эквивалент через docker-compose (то же самое, но короче в будущем):

```
docker compose build
```

## 4. Один раз сгенерировать storage_state (обходит email-код на каждом прогоне)

Контейнер интерактивный (`-it`), чтобы можно было ввести код подтверждения
из письма, если Atlassian его запросит:

```
docker run --rm -it --ipc=host --env-file .env \
  -v "$(pwd)/auth:/app/auth" \
  reminder-autotests:local \
  python -m scripts.generate_storage_state
```

или через compose:

```
docker compose run --rm tests python -m scripts.generate_storage_state
```

Если Atlassian пришлёт код на почту — скрипт попросит его через `input()`
прямо в терминале (можно также передать заранее: добавьте
`-e EMAIL_OTP_CODE=ABC123` к `docker run`). После успешного прогона файл
`auth/user_state.json` появится у вас на маке (volume смонтирован) — его
подхватят обычные тесты.

## 5. Прогнать тест

```
docker run --rm -it --ipc=host --env-file .env \
  -v "$(pwd)/auth:/app/auth" \
  -v "$(pwd)/allure-results:/app/allure-results" \
  reminder-autotests:local \
  pytest tests/ui/test_login.py -v --alluredir=allure-results
```

Если `EMAIL_OTP_CODE` нужен и для этого теста (он логинится явно, не через
storage_state) — добавьте `-e EMAIL_OTP_CODE=...` либо примите скип теста с
понятным сообщением.

Через compose — ещё короче (volume'ы и env_file уже прописаны в
docker-compose.yml):

```
docker compose run --rm tests pytest tests/ui/test_login.py -v --alluredir=allure-results
```

Запуск headed-браузера (увидеть, что происходит) внутри Linux-контейнера
без X11/VNC не получится просмотреть глазами так же просто, как на маке —
для отладки локаторов проще гонять `--headed` локально через
`BROWSER_CHANNEL=chrome` (см. предыдущий совет), а Docker использовать для
стабильных headless-прогонов.

## 6. Посмотреть Allure-отчёт

Отчёт генерируется из `allure-results/`, который примонтирован наружу —
сам CLI `allure` для него не обязателен внутри контейнера, запускайте на
хосте (у вас уже стоит `~/allure-2.25.0`):

```
allure serve allure-results
```

## Частые проблемы

- **"Cannot connect to the Docker daemon"** — Docker Desktop не запущен,
  откройте приложение и дождитесь "Engine running".
- **Playwright не находит браузер / version mismatch** — тег образа в
  Dockerfile разъехался с версией playwright в requirements.txt (см. шаг 1).
- **Платформа ARM (Apple Silicon, M1/M2/M3)** — образ мультиархитектурный,
  Docker сам подберёт нужный вариант; специальных флагов не требуется.
- **Permission denied на auth/ или allure-results/ после прогона** —
  на Docker Desktop для Mac обычно не возникает (файловая система
  виртуализирована), но если всё же случится: `chmod -R u+rwX auth allure-results`
  на хосте.
