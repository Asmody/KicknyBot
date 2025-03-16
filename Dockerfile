FROM python:3.10-slim

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