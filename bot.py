import os
import logging
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
from sqlalchemy.orm import Session
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
        ["❌ Удалить задачу", "🗑 Очистить все"]
    ],
    resize_keyboard=True
)

# 🎛 Меню подтверждения удаления
CONFIRM_DELETE_MENU = ReplyKeyboardMarkup(
    [
        ["✅ Да", "❌ Нет"]
    ],
    resize_keyboard=True
)

# 🎛 Меню с возможностью пропуска описания
SKIP_DESCRIPTION_MENU = ReplyKeyboardMarkup(
    [
        ["⏩ Пропустить"]
    ],
    resize_keyboard=True
)

# 🔹 Храним обработанные update_id
processed_updates = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет стартовое сообщение и показывает меню."""
    logger.info(f"✅ Команда /start вызвана | update_id: {update.update_id}")
    context.user_data.clear()
    await update.message.reply_text("👋 Привет! Я бот-менеджер задач. Выберите действие:", reply_markup=MAIN_MENU)

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выводит список задач."""
    with SessionLocal() as db:
        tasks = db.query(Task).all()

    if not tasks:
        await update.message.reply_text("📭 У вас пока нет задач.", reply_markup=MAIN_MENU)
        return

    task_list = "\n".join([f"📌 {t.id}: {t.title}" + (f" - {t.description}" if t.description else "") for t in tasks])
    await update.message.reply_text(f"📋 Ваши задачи:\n{task_list}", reply_markup=MAIN_MENU)

async def delete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Позволяет пользователю выбрать задачу для удаления."""
    with SessionLocal() as db:
        tasks = db.query(Task).all()

    if not tasks:
        await update.message.reply_text("📭 У вас нет задач для удаления.", reply_markup=MAIN_MENU)
        return

    task_list = "\n".join([f"{t.id}: {t.title}" for t in tasks])
    await update.message.reply_text(f"🗑 Введите номера задач для удаления (через запятую):\n{task_list}")
    context.user_data["action"] = "confirm_delete_task"

async def confirm_delete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрашивает подтверждение удаления."""
    user_text = update.message.text.strip()
    if not user_text.replace(",", "").isdigit():
        await update.message.reply_text("⚠️ Введите номера задач через запятую, например: `1,2,3`", reply_markup=MAIN_MENU)
        return

    context.user_data["tasks_to_delete"] = [int(i) for i in user_text.split(",") if i.isdigit()]
    await update.message.reply_text(f"🗑 Подтвердите удаление задач: {user_text}", reply_markup=CONFIRM_DELETE_MENU)
    context.user_data["action"] = "process_delete_task"

async def process_delete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет выбранные задачи после подтверждения."""
    user_text = update.message.text.strip()
    if user_text == "✅ Да":
        tasks_to_delete = context.user_data.get("tasks_to_delete", [])

        with SessionLocal() as db:
            for task_id in tasks_to_delete:
                task = db.query(Task).filter(Task.id == task_id).first()
                if task:
                    db.delete(task)
            db.commit()

        await update.message.reply_text(f"✅ Удалены задачи: {', '.join(map(str, tasks_to_delete))}", reply_markup=MAIN_MENU)
    else:
        await update.message.reply_text("❌ Удаление отменено.", reply_markup=MAIN_MENU)

    context.user_data.clear()

async def clear_all_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очищает все задачи."""
    with SessionLocal() as db:
        db.query(Task).delete()
        db.commit()

    await update.message.reply_text("✅ Все задачи удалены!", reply_markup=MAIN_MENU)

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команды из меню."""
    user_text = update.message.text.strip()

    if is_duplicate(update, allow_menu=True):
        return

    logger.info(f"📩 Меню выбрано: {user_text} | update_id: {update.update_id}")

    if user_text == "➕ Добавить задачу":
        context.user_data["action"] = "adding_task_title"
        await update.message.reply_text("✏️ Введите название задачи:")

    elif user_text == "📋 Список задач":
        await list_tasks(update, context)

    elif user_text == "❌ Удалить задачу":
        await delete_task(update, context)

    elif user_text == "🗑 Очистить все":
        await clear_all_tasks(update, context)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод текста."""
    if is_duplicate(update):
        return

    user_text = update.message.text.strip()
    action = context.user_data.get("action", None)

    logger.info(f"📥 Получено сообщение: {user_text} | Действие: {action}")

    if user_text in ["➕ Добавить задачу", "📋 Список задач", "❌ Удалить задачу", "🗑 Очистить все"]:
        await handle_menu(update, context)
        return

    if action == "confirm_delete_task":
        await confirm_delete_task(update, context)
    elif action == "process_delete_task":
        await process_delete_task(update, context)
    elif action == "adding_task_title":
        context.user_data["new_task_title"] = user_text
        context.user_data["action"] = "adding_task_description"
        await update.message.reply_text("📝 Введите описание задачи (или нажмите '⏩ Пропустить'):", reply_markup=SKIP_DESCRIPTION_MENU)
    elif action == "adding_task_description":
        if user_text == "⏩ Пропустить":
            await save_task(update, context, None)
        else:
            await save_task(update, context, user_text)

async def save_task(update: Update, context: ContextTypes.DEFAULT_TYPE, description: str):
    """Сохраняет задачу в базу данных."""
    title = context.user_data.get("new_task_title", "Без названия")
    with SessionLocal() as db:
        new_task = Task(title=title, description=description if description else None)
        db.add(new_task)
        db.commit()

    await update.message.reply_text(
        f"✅ Задача добавлена:\n📌 *{title}*" + (f"\n📝 {description}" if description else ""),
        reply_markup=MAIN_MENU,
        parse_mode="Markdown"
    )

    context.user_data.clear()

def is_duplicate(update: Update, allow_menu=False) -> bool:
    """Фильтрует дубликаты сообщений."""
    chat_id = update.effective_chat.id
    update_id = update.update_id

    if chat_id not in processed_updates:
        processed_updates[chat_id] = set()

    if update_id in processed_updates[chat_id]:
        return not allow_menu

    processed_updates[chat_id].add(update_id)
    return False

def main():
    """Запускает Telegram-бота."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CommandHandler("start", start))
    application.run_polling()

if __name__ == "__main__":
    main()
