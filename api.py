import logging
from fastapi import (FastAPI
#                    , HTTPException
)
from pydantic import BaseModel

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

class StatusResponse(BaseModel):
    status: str
    message: str = None

def create_api(bot_instance):
    """Создает FastAPI приложение с указанным экземпляром бота"""
    app = FastAPI(title="KicknyBot API", description="API для управления ботом голосования")
    
    @app.get("/api/status", response_model=StatusResponse)
    async def get_status():
        """Получить статус бота"""
        if bot_instance.is_running:
            return {"status": "running"}
        return {"status": "stopped"}
    
    @app.post("/api/start", response_model=StatusResponse)
    async def start_api():
        """Запустить бота"""
        try:
            result = await bot_instance.start_bot()
            return {"status": result["status"]}
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")
            return {"status": "error", "message": str(e)}
    
    @app.post("/api/stop", response_model=StatusResponse)
    async def stop_api():
        """Остановить бота"""
        try:
            result = await bot_instance.stop_bot()
            return {"status": result["status"]}
        except Exception as e:
            logger.error(f"Ошибка при остановке бота: {e}")
            return {"status": "error", "message": str(e)}
    
    @app.post("/api/restart", response_model=StatusResponse)
    async def restart_api():
        """Перезапустить бота"""
        try:
            result = await bot_instance.restart_bot()
            return {"status": result["status"]}
        except Exception as e:
            logger.error(f"Ошибка при перезапуске бота: {e}")
            return {"status": "error", "message": str(e)}
    
    return app