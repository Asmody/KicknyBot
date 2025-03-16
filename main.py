from dotenv import load_dotenv
import os
import asyncio
import threading
import uvicorn
import logging
from bot import KicknyBot
from api import create_api

load_dotenv()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Функция для запуска FastAPI сервера
def run_api_server(app, host="0.0.0.0", port=8000):
    """Запускает FastAPI сервер"""
    uvicorn.run(app, host=host, port=port)

# Управляющая функция для запуска бота и API
async def main():
    # Создание экземпляра бота
    bot = KicknyBot()
    
    # Создание API с передачей экземпляра бота
    app = create_api(bot)
    
    # получение хоста и порта из переменных окружения
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    # Запуск API сервера в отдельном потоке
    api_thread = threading.Thread(target=run_api_server, args=(app, host, port))
    api_thread.daemon = True
    api_thread.start()
    
    # Автоматический запуск бота при старте приложения
    await bot.start_bot()
    
    try:
        # Бесконечный цикл для поддержания работы основного потока
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        # Корректное завершение при получении сигнала остановки
        await bot.stop_bot()

if __name__ == "__main__":
    asyncio.run(main())