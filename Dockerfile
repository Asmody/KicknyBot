FROM python:3-slim

ARG API_HOST
ARG API_PORT

# Установка переменных окружения
ENV API_HOST=${API_HOST}
ENV API_PORT=${API_PORT}

# Установка рабочей директории
WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY api.py .
COPY bot.py .
COPY main.py .
COPY .env .

# Открытие порта для Web API
EXPOSE 8000

# Запуск приложения
CMD ["python", "main.py"]