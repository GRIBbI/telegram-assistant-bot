import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram_bot_calendar import DetailedTelegramCalendar, LSTEP
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from database import SessionLocal, Task, init_db

# 🔹 Включаем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🔹 Загружаем переменные окружения
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN не найден! Проверь .env")
    exit(1)

# 🎛 Главное меню
MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["Добавить задачу", "Список задач"],
        ["⏰ Уведомления"]
    ],
    resize_keyboard=True
)

# 🔹 Запускаем `apscheduler`
scheduler = BackgroundScheduler()
scheduler.start()

# 🔹 Инициализация БД
init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Стартовое сообщение"""
    logger.info(f"✅ Команда /start вызвана | update_id: {update.update_id}")
    context.user_data.clear()
    await update.message.reply_text("👋 Привет! Я бот-менеджер задач. Выберите действие:", reply_markup=MAIN_MENU)

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команды из главного меню"""
    user_text = update.message.text.strip().lower()
    logger.info(f"📩 Пользователь выбрал: {user_text}")

    if user_text == "добавить задачу":
        context.user_data["action"] = "adding_task_title"
        logger.info(f"📌 Состояние изменено: {context.user_data['action']}")
        await update.message.reply_text("✏️ Введите название задачи:")

    elif user_text == "список задач":
        await update.message.reply_text("📜 Ваши задачи: (Здесь пока пусто)")

    elif user_text == "уведомления":
        await update.message.reply_text("🔔 Здесь будут показываться уведомления!")

    else:
        await update.message.reply_text("⚠️ Я не понимаю эту команду. Выберите действие из меню.", reply_markup=MAIN_MENU)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод пользователя (название задачи, описание, кастомное время и т.д.)"""
    user_text = update.message.text.strip()
    action = context.user_data.get("action")

    logger.info(f"📝 Введён текст: {user_text} | Текущий action: {action}")

    if action == "adding_task_title":
        context.user_data["new_task_title"] = user_text
        context.user_data["action"] = "adding_task_description"
        logger.info(f"📌 Название задачи сохранено: {user_text}")
        await update.message.reply_text("📝 Введите описание задачи (или нажмите '⏩ Пропустить')", 
                                        reply_markup=ReplyKeyboardMarkup([["⏩ Пропустить"]], resize_keyboard=True))

    elif action == "adding_task_description":
        context.user_data["new_task_description"] = None if user_text == "⏩ Пропустить" else user_text
        context.user_data["action"] = "adding_task_deadline"
        await send_calendar(update, context)

    elif action == "adding_custom_time":
        try:
            deadline_date = context.user_data.get("deadline_date")
            if not deadline_date:
                logger.error("❌ Ошибка: дата дедлайна не найдена!")
                await update.message.reply_text("⚠️ Ошибка! Дата не найдена. Попробуйте заново.")
                return

            deadline = datetime.combine(deadline_date, datetime.strptime(user_text, "%H:%M").time())
            await save_task(update, context, deadline)
        except ValueError:
            await update.message.reply_text("⚠️ Ошибка! Введите время в формате ЧЧ:ММ (например, 14:30)")

async def send_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет календарь Telegram для выбора даты"""
    calendar, step = DetailedTelegramCalendar().build()
    await update.message.reply_text(f"📆 Выберите {LSTEP[step]}:", reply_markup=calendar)

async def time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатие на выбор времени"""
    query = update.callback_query
    await query.answer()

    logger.info(f"⏰ Callback получен: {query.data}")

    if query.data == "custom_time":
        context.user_data["action"] = "adding_custom_time"
        await query.message.reply_text("⌛ Введите своё время в формате ЧЧ:ММ (например, 14:30)", reply_markup=ForceReply())
    else:
        selected_time = query.data.split("_")[1]
        deadline_date = context.user_data.get("deadline_date")

        if not deadline_date:
            logger.error("❌ Ошибка: дата дедлайна не найдена!")
            await query.message.reply_text("⚠️ Ошибка! Дата не найдена. Попробуйте заново.")
            return

        deadline = datetime.combine(deadline_date, datetime.strptime(selected_time, "%H:%M").time())

        await query.message.edit_text(f"⏳ Время выбрано: {selected_time} ✅")
        await save_task(update, context, deadline)

def main():
    """Запускает Telegram-бота"""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex("^(Добавить задачу|Список задач|⏰ Уведомления)$"), handle_menu))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(time_callback, pattern="^time_[0-9]{2}:[0-9]{2}|custom_time"))

    application.run_polling()

if __name__ == "__main__":
    main()
