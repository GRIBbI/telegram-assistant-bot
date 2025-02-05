import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram_bot_calendar import DetailedTelegramCalendar
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from database import SessionLocal, Task

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
        ["➕ Добавить задачу", "📋 Список задач"],
        ["⏰ Уведомления"]
    ],
    resize_keyboard=True
)

# 🎛 Меню при просмотре задач
TASKS_MENU = ReplyKeyboardMarkup(
    [
        ["❌ Удалить задачу", "🗑 Очистить все"],
        ["🔙 Назад"]
    ],
    resize_keyboard=True
)

# 🎛 Меню при добавлении задачи
ADD_TASK_MENU = ReplyKeyboardMarkup(
    [
        ["⏩ Пропустить описание"]
    ],
    resize_keyboard=True
)

# 🔹 Запускаем `apscheduler`
scheduler = BackgroundScheduler()
scheduler.start()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Стартовое сообщение"""
    logger.info(f"✅ Команда /start вызвана | update_id: {update.update_id}")
    context.user_data.clear()
    await update.message.reply_text("👋 Привет! Я бот-менеджер задач. Выберите действие:", reply_markup=MAIN_MENU)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения"""
    user_text = update.message.text.strip()
    action = context.user_data.get("action")

    logger.info(f"📝 Получено сообщение: {user_text} | Действие: {action}")

    # 🟢 Если пользователь НЕ находится в режиме ввода задачи, перенаправляем в `handle_menu`
    if not action:
        await handle_menu(update, context)
        return

    # 🚨 Блокируем кнопки в заголовке и описании задачи
    if user_text in ["➕ Добавить задачу", "📋 Список задач", "⏰ Уведомления", "❌ Удалить задачу", "🗑 Очистить все", "🔙 Назад"]:
        await update.message.reply_text("⚠️ Используйте меню для выбора действия.")
        return

    # 🟢 Ожидаем заголовок задачи
    if action == "adding_task_title":
        context.user_data["new_task_title"] = user_text
        context.user_data["action"] = "adding_task_description"
        await update.message.reply_text("📝 Введите описание задачи (или нажмите '⏩ Пропустить')", reply_markup=ADD_TASK_MENU)

    # 🟢 Ожидаем описание задачи
    elif action == "adding_task_description":
        if user_text == "⏩ Пропустить":
            context.user_data["new_task_description"] = None
        else:
            context.user_data["new_task_description"] = user_text

        context.user_data["action"] = "adding_task_deadline"
        await send_calendar(update, context)

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команды из меню"""
    user_text = update.message.text.strip()

    logger.info(f"📩 Меню выбрано: {user_text}")

    if user_text == "➕ Добавить задачу":
        context.user_data["action"] = "adding_task_title"
        await update.message.reply_text("✏️ Введите название задачи:")

    elif user_text == "📋 Список задач":
        await list_tasks(update, context)

    elif user_text == "❌ Удалить задачу":
        await delete_task(update, context)

    elif user_text == "🗑 Очистить все":
        await clear_all_tasks(update, context)

    elif user_text == "🔙 Назад":
        await update.message.reply_text("🔙 Возвращаемся в главное меню", reply_markup=MAIN_MENU)

async def send_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет календарь Telegram для выбора даты"""
    calendar, step = DetailedTelegramCalendar().build()
    await update.message.reply_text(f"📆 Выберите дату дедлайна:", reply_markup=calendar)

async def calendar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатие на календарь"""
    query = update.callback_query
    result, key, step = DetailedTelegramCalendar().process(query.data)

    if not result and key:
        await query.message.edit_text(f"📆 Выберите дату дедлайна:", reply_markup=key)
    elif result:
        deadline = datetime.strptime(str(result), "%Y-%m-%d")
        await save_task(update, context, deadline)

async def save_task(update: Update, context: ContextTypes.DEFAULT_TYPE, deadline):
    """Сохраняем задачу в базу данных"""
    title = context.user_data.get("new_task_title", "Без названия")
    details = context.user_data.get("new_task_description", None)

    with SessionLocal() as db:
        new_task = Task(title=title, details=details, deadline=deadline)
        db.add(new_task)
        db.commit()

    task_info = f"✅ Задача добавлена:\n📌 *{title}*" + (f"\n📝 {details}" if details else "") + (f"\n⏳ {deadline.strftime('%d.%m.%Y')}" if deadline else "")

    await update.message.reply_text(task_info, reply_markup=MAIN_MENU, parse_mode="Markdown")

    # Запланировать уведомление
    if deadline:
        scheduler.add_job(send_reminder, "date", run_date=deadline, args=[update, context, title])

    context.user_data.clear()

async def send_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE, task_title):
    """Отправляет уведомление о дедлайне"""
    await update.message.reply_text(f"⏰ Напоминание! Время выполнить задачу: *{task_title}*", parse_mode="Markdown")

def main():
    """Запускает Telegram-бота"""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(calendar_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == "__main__":
    main()
