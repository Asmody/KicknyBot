import os
import logging
from dotenv import load_dotenv
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
#    JobQueue,
    filters,
    MessageHandler,
)

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

class KicknyBot:
    def __init__(self):
        # Получение токена из переменных окружения
        self.api_key = os.getenv("TELEGRAM_API_KEY")
        if not self.api_key:
            raise ValueError("TELEGRAM_API_KEY не найден в .env файле")
        
        # Хранение данных
        self.active_votes = {}
        self.chat_settings = {}
        
        # Создание приложения
        self.application = None
        self.app_thread = None
        self.is_running = False
    
    async def is_admin(self, chat_id: int, user_id: int, context: CallbackContext) -> bool:
        """Проверяет, является ли пользователь администратором чата"""
        try:
            admins = await context.bot.get_chat_administrators(chat_id)
            return any(admin.user.id == user_id for admin in admins)
        except Exception as e:
            logger.error(f"Ошибка проверки администратора: {e}")
            return False

    async def help_command(self, update: Update, context: CallbackContext) -> None:
        """Выводит справочное сообщение о командах бота"""
        help_text = f"""
        Этот бот позволяет наказывать пользователя временным запретом писать или баном навсегда через голосование с возможностью отмены. Тех. поддержка https://github.com/tormozit/KicknyBot
        Список команд:
        Ответьте на сообщение пользователя строкой @{context.bot.username} для начала голосования за его наказание
        /VotesLimit [количество] - Установить необходимое число голосов (только админы) = {self.get_votes_limit(update.effective_chat.id)}
        /VotesMonoLimit [количество] - Установить необходимое число голосов единогласно, т.е. при отсутствии голосов за другие варианты (только админы) = {self.get_votes_mono_limit(update.effective_chat.id)}
        /TimeLimit [минуты] - Установить время голосования (только админы) = {self.get_time_limit(update.effective_chat.id)/60}
        /help - Показать эту справку
        """
        await update.message.reply_text(help_text)

    async def set_votes_limit(self, update: Update, context: CallbackContext) -> None:
        """Устанавливает необходимое количество голосов для принятия решения"""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        if not await self.is_admin(chat_id, user_id, context):
            await update.message.reply_text("❌ Команда доступна только администраторам")
            return
        
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("⚠ Использование: /VotesLimit [число]")
            return
        
        votes_limit = int(context.args[0])
        self.chat_settings.setdefault(chat_id, {})["votes_limit"] = votes_limit
        await update.message.reply_text(f"✅ Лимит голосов установлен: {votes_limit}")

    async def set_votes_mono_limit(self, update: Update, context: CallbackContext) -> None:
        """Устанавливает необходимое количество голосов для единогласного принятия решения"""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        if not await self.is_admin(chat_id, user_id, context):
            await update.message.reply_text("❌ Команда доступна только администраторам")
            return
        
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("⚠ Использование: /VotesMonoLimit [число]")
            return
        
        votes_mono_limit = int(context.args[0])
        self.chat_settings.setdefault(chat_id, {})["votes_mono_limit"] = votes_mono_limit
        await update.message.reply_text(f"✅ Лимит единогласно голосов установлен: {votes_mono_limit}")

    async def set_time_limit(self, update: Update, context: CallbackContext) -> None:
        """Устанавливает максимальное время голосования в минутах"""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        if not await self.is_admin(chat_id, user_id, context):
            await update.message.reply_text("❌ Команда доступна только администраторам")
            return
        
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("⚠ Использование: /TimeLimit [минуты]")
            return
        
        minutes = int(context.args[0])
        time_limit = minutes * 60
        self.chat_settings.setdefault(chat_id, {})["time_limit"] = time_limit
        await update.message.reply_text(f"✅ Время голосования установлено: {minutes} мин")

    async def start_vote(self, update: Update, context: CallbackContext) -> None:
        """Начинает голосование при ответе на сообщение пользователя"""
        if not update.message.reply_to_message:
            return       
        bot_username = context.bot.username.lower()
        mentioned = any(
            entity.type == "mention" 
            and update.message.text[entity.offset:entity.offset+entity.length].lower() == f"@{bot_username}"
            for entity in update.message.entities or []
        )
        if not mentioned:
            return
        target_user = update.message.reply_to_message.from_user
        chat_id = update.effective_chat.id
        initiator_id = update.effective_user.id
        if initiator_id == target_user.id:
            await update.message.reply_text("Нельзя голосовать против себя.")
            return    
        if await self.is_admin(chat_id, target_user.id, context):
            await update.message.reply_text("Нельзя голосовать против администратора")
            return
        
        votes_limit = self.get_votes_limit(chat_id)
        votes_mono_limit = self.get_votes_mono_limit(chat_id)
        time_limit = self.get_time_limit(chat_id)
        
        keyboard = [
            [
                InlineKeyboardButton("⏳ Читатель 24ч", callback_data=f"vote:day:{target_user.id}"),
                InlineKeyboardButton("♾️ Бан навсегда", callback_data=f"vote:forever:{target_user.id}"),
                InlineKeyboardButton("Простить", callback_data=f"vote:forgive:{target_user.id}"),
            ],
            [InlineKeyboardButton("Отменить голосование", callback_data=f"vote:cancel:{target_user.id}")],
        ]
        message = await update.message.reply_text(
            self.titleText(
                userId=target_user.id,
                fullUserName=target_user.full_name,
                nickname=target_user.username,
                votes_mono_limit=votes_mono_limit,
                votes_limit=votes_limit
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        
        vote_id = (chat_id, message.message_id)
        self.active_votes[vote_id] = {
            "initiator_id": initiator_id,
            "target_user_id": target_user.id,
            "target_username": target_user.username,
            "target_full_name": target_user.full_name,
            "votes_day": 0,
            "votes_forever": 0,
            "votes_forgive": 0,
            "voters": {},
            "start_time": datetime.now(),
            "votes_limit": votes_limit,
            "votes_mono_limit": votes_mono_limit,
            "time_limit": time_limit,
            "original_message_id": update.message.reply_to_message.message_id,
        }
        
        context.job_queue.run_once(
            self.end_vote, time_limit, data=vote_id, name=str(vote_id)
        )

    def titleText(self, userId: int, fullUserName: str, nickname: str, votes_mono_limit: int, votes_limit: int) -> str:
        """Формирует заголовок сообщения о голосовании"""
        user_link = self.create_user_link(
            user_id=userId,
            fullUserName=fullUserName,
            nickname=nickname
        )
        return f"🔨 Голосуем за наказание пользователя {user_link} с лимитом {votes_limit} или единогласно {votes_mono_limit}.\n"

    def get_votes_limit(self, chat_id):
        """Получает установленный лимит голосов для чата или значение по умолчанию"""
        return self.chat_settings.get(chat_id, {}).get("votes_limit", 10)

    def get_votes_mono_limit(self, chat_id):
        """Получает установленный лимит единогласных голосов для чата или значение по умолчанию"""
        return self.chat_settings.get(chat_id, {}).get("votes_mono_limit", 6)

    def get_time_limit(self, chat_id):
        """Получает установленный лимит времени для чата или значение по умолчанию"""
        return self.chat_settings.get(chat_id, {}).get("time_limit", 3600)

    async def handle_vote(self, update: Update, context: CallbackContext) -> None:
        """Обрабатывает голоса и действия (голосование или отмена)"""
        query = update.callback_query
        await query.answer()
        
        data = query.data.split(":")
        if len(data) != 3 or data[0] != "vote":
            return
        
        action, target_user_id = data[1], int(data[2])
        vote_id = (query.message.chat_id, query.message.message_id)
        vote_data = self.active_votes.get(vote_id)
        
        if not vote_data or vote_data["target_user_id"] != target_user_id:
            await query.edit_message_text("Голосование остановлено по технической причине.")
            return
        
        user_id = query.from_user.id
        if user_id == target_user_id:
            await query.answer("Нельзя голосовать против себя.")
            return   
        if action == "cancel":
            if user_id != vote_data["initiator_id"]:
                await query.answer("Только инициатор может отменить")
                return
            
            for job in context.job_queue.get_jobs_by_name(str(vote_id)):
                job.schedule_removal()
            del self.active_votes[vote_id]
            await query.edit_message_text("Голосование отменено")
            return
        
        current_vote = vote_data["voters"].get(user_id)
        if current_vote == action:
            await query.answer("Вы уже проголосовали")
            return
        
        if current_vote:
            vote_data[f"votes_{current_vote}"] -= 1
        
        vote_data["voters"][user_id] = action
        vote_data[f"votes_{action}"] += 1
        
        remaining = (vote_data["time_limit"] - (datetime.now() - vote_data["start_time"]).total_seconds()) // 60
        
        # Обновляем текст всех кнопок
        keyboard = query.message.reply_markup.inline_keyboard
        new_keyboard = []
        for row in keyboard:
            new_row = []
            for button in row:
                # Убираем "+" из всех кнопок
                button_text = button.text.replace(" +", "")
                if button.callback_data == query.data:
                    # Добавляем "+" к выбранной кнопке
                    button_text = f"{button_text} +"
                new_button = InlineKeyboardButton(button_text, callback_data=button.callback_data)
                new_row.append(new_button)
            new_keyboard.append(new_row)
        
        await query.edit_message_text(
            self.FullStatus(vote_data, remaining), 
            reply_markup=InlineKeyboardMarkup(new_keyboard), 
            parse_mode="HTML"
        )
        
        if (False
            or vote_data["votes_day"] == vote_data["votes_limit"] 
            or vote_data["votes_day"] == vote_data["votes_mono_limit"] and vote_data["votes_forever"] == 0 and vote_data["votes_forgive"] == 0):
            result = "day"
        elif (False
            or vote_data["votes_forever"] == vote_data["votes_limit"] 
            or vote_data["votes_forever"] == vote_data["votes_mono_limit"] and vote_data["votes_day"] == 0 and vote_data["votes_forgive"] == 0):
            result = "forever"
        elif (False
            or vote_data["votes_forgive"] == vote_data["votes_limit"] 
            or vote_data["votes_forgive"] == vote_data["votes_mono_limit"] and vote_data["votes_day"] == 0 and vote_data["votes_forever"] == 0):
            result = 'forgive'
        else:
            result = None
        if result:
            vote_data["result"] = result
            for job in context.job_queue.get_jobs_by_name(str(vote_id)):
                job.schedule_removal()
            await self.end_vote(context, vote_id)

    def FullStatus(self, vote_data, remaining):
        """Формирует полный статус текущего голосования"""
        def format_votes(current, mono_limit, limit, other1, other2):
            if other1 == 0 and other2 == 0:
                return f"{current}/{mono_limit}"
            return f"{current}/{limit}"

        day_text = format_votes(
            vote_data['votes_day'],
            vote_data['votes_mono_limit'],
            vote_data['votes_limit'],
            vote_data['votes_forever'],
            vote_data['votes_forgive']
        )

        forever_text = format_votes(
            vote_data['votes_forever'],
            vote_data['votes_mono_limit'],
            vote_data['votes_limit'],
            vote_data['votes_day'],
            vote_data['votes_forgive']
        )

        forgive_text = format_votes(
            vote_data['votes_forgive'],
            vote_data['votes_mono_limit'],
            vote_data['votes_limit'],
            vote_data['votes_day'],
            vote_data['votes_forever']
        )

        text = (
            self.titleText(vote_data['target_user_id'], vote_data['target_full_name'], vote_data['target_username'], vote_data['votes_mono_limit'], vote_data['votes_limit']) +
            f"{day_text} за читателя (запрет писать) 24ч\n"
            f"{forever_text} за бан (лишить доступа) навсегда\n"
            f"{forgive_text} за прощение\n"
        )
        return text

    async def end_vote(self, context: CallbackContext, vote_id: tuple) -> None:
        """Завершает голосование и применяет результат"""
        vote_data = self.active_votes.pop(vote_id, None)
        if not vote_data:
            return
        chat_id, message_id = vote_id
        
        # Проверяем, был ли результат установлен
        result = vote_data.get("result")
        if not result:
            # Определяем результат по количеству голосов
            if vote_data["votes_day"] > vote_data["votes_forever"] and vote_data["votes_day"] > vote_data["votes_forgive"]:
                result = "day"
            elif vote_data["votes_forever"] > vote_data["votes_day"] and vote_data["votes_forever"] > vote_data["votes_forgive"]:
                result = "forever"
            else:
                result = "forgive"
        
        result_message = ""
        if result == 'forgive':
            result_message = "прощен"
        elif result == 'forever':
            await context.bot.ban_chat_member(chat_id, vote_data["target_user_id"])
            result_message = "забанен (лишен доступа) навсегда. Восстановить его может администратор в настройках группы."
            try:
                await context.bot.delete_message(chat_id, vote_data["original_message_id"])
            except Exception as e:
                logger.error(f"Ошибка удаления сообщения: {e}")
        else:
            until = datetime.now() + timedelta(days=1)
            result_message = "теперь читатель (запрещено писать) на 24ч"
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=vote_data["target_user_id"],
                permissions=ChatPermissions(
                    can_send_messages=False,  # Запрет на отправку сообщений
                ),
                until_date=until
            )
            try:
                await context.bot.delete_message(chat_id, vote_data["original_message_id"])
            except Exception as e:
                logger.error(f"Ошибка удаления сообщения: {e}")

        voters = []
        for user_id, vote_type in vote_data["voters"].items():
            if vote_type == result:
                try:
                    user = await context.bot.get_chat_member(chat_id, user_id)
                    voters.append(self.create_user_link(
                        user_id=user_id,
                        fullUserName=user.user.full_name,
                        nickname=user.user.username
                    ))
                except Exception as e:
                    logger.error(f"Ошибка получения пользователя {user_id}: {e}")
                    voters.append(self.create_user_link(
                        user_id=user_id,
                        fullUserName=f"id{user_id} (не в чате)",
                        nickname=None
                    ))

        voters_text = ", ".join(voters)
        userLink = self.create_user_link(vote_data['target_user_id'], vote_data['target_full_name'], vote_data['target_username'])
        await context.bot.edit_message_text(
            text=(
                f"Пользователь {userLink} {result_message}.\n"
                f"За это голосовали ({len(voters)}): {voters_text}"
            ),
            chat_id=chat_id,
            message_id=message_id,
            parse_mode="HTML"
        )

    def create_user_link(self, user_id: int, fullUserName: str, nickname: str) -> str:
        """Создает HTML-ссылку на профиль пользователя"""
        return f'<a href="tg://user?id={user_id}">{fullUserName or f"id{user_id}"}</a>'

    async def setup_handlers(self) -> Application:
        """Устанавливает обработчики команд и сообщений"""
        builder = Application.builder().token(self.api_key)
        app = builder.build()
        
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(CommandHandler("VotesLimit", self.set_votes_limit))
        app.add_handler(CommandHandler("VotesMonoLimit", self.set_votes_mono_limit))
        app.add_handler(CommandHandler("TimeLimit", self.set_time_limit))
        app.add_handler(
            MessageHandler(
                filters.ChatType.GROUPS 
                & filters.REPLY 
                & filters.Entity("mention"),
                self.start_vote
                )
        )
        app.add_handler(CallbackQueryHandler(self.handle_vote))
        
        return app
    
    async def start_bot(self):
        """Запускает бота"""
        if self.is_running:
            logger.info("Бот уже запущен")
            return {"status": "already_running"}
        
        self.application = await self.setup_handlers()
        await self.application.initialize()
        await self.application.start()
        self.is_running = True
        logger.info("Бот запущен")
        return {"status": "started"}
    
    async def stop_bot(self):
        """Останавливает бота"""
        if not self.is_running:
            logger.info("Бот не запущен")
            return {"status": "not_running"}
        
        if self.application:
            await self.application.stop()
            await self.application.shutdown()
            self.application = None
            self.is_running = False
            logger.info("Бот остановлен")
            return {"status": "stopped"}
        return {"status": "error", "message": "Не удалось остановить бота"}
    
    async def restart_bot(self):
        """Перезапускает бота"""
        await self.stop_bot()
        return await self.start_bot()