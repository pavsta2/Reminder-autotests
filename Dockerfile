# Версия тега образа ДОЛЖНА совпадать с версией playwright из requirements.txt —
# иначе Playwright внутри контейнера не найдёт нужные браузерные бинарники
# (они жёстко привязаны к конкретному релизу). Если в requirements.txt
# изменится версия playwright — поменяйте и тег здесь.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble

WORKDIR /app

# Сначала только requirements.txt — чтобы Docker кешировал слой с pip install
# и не переустанавливал зависимости при каждом изменении кода тестов.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Браузеры (chromium/firefox/webkit) уже установлены в базовом образе вместе
# со всеми системными зависимостями — playwright install делать не нужно.
CMD ["pytest", "-v"]
