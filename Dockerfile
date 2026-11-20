# Базовый образ должен совпадать с версией playwright из requirements.txt.
# Проверить версию можно так:
#   grep "^playwright==" requirements.txt
#
# Сейчас там:
#   playwright==1.65.2
FROM mcr.microsoft.com/playwright/python:v1.65.2-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Сначала копируем только requirements.txt, чтобы Docker мог кешировать
# слой с зависимостями. Если код меняется, а requirements.txt остаётся прежним,
# зависимости не будут переустанавливаться.
COPY requirements.txt .

# requirements.txt уже содержит хеши пакетов.
# Дополнительно указывать --require-hashes не обязательно.
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# Копируем сам проект.
COPY . .

# Папки для результатов Allure и storage_state.
# auth нужен для сохранённых сессий, если они будут создаваться внутри контейнера.
RUN mkdir -p allure-results auth

# Точка входа по умолчанию.
# При запуске контейнера можно передавать дополнительные аргументы pytest,
# например: -m "not email" или --headed=false.
ENTRYPOINT ["python3", "-m", "pytest"]

# Аргументы по умолчанию.
CMD ["-v", "--alluredir=allure-results"]