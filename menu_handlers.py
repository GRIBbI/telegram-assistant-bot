import logging
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import ContextTypes
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from database import SessionLocal, Task
from openai_integration import get_gpt_response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Главное меню (кнопки)
MAIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Добавить задачу"), KeyboardButton("Список задач")],
        [KeyboardButton("GPT-чат")]
    ],
    resize_keyboard=True
)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показываем пользователю главное меню."""
    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=MAIN_MENU
    )

async def handle_menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор пользователя в главном меню."""
    user_text = update.message.text.strip()

    if user_text == "Добавить задачу":
        await update.message.reply_text("Введите название задачи:")
        context.user_data["action"] = "adding_task_title"

    elif user_text == "Список задач":
        await list_tasks(update, context)

    elif user_text == "GPT-чат":
        await update.message.reply_text("Напишите свой вопрос:")
        context.user_data["action"] = "gpt_chat"

    else:
        await process_user_action(update, context, user_text)

async def process_user_action(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str):
    """Обрабатывает ввод текста в зависимости от текущего действия пользователя."""
    action = context.user_data.get("action")

    if action == "adding_task_title":
        context.user_data["new_task_title"] = user_text
        context.user_data["action"] = "adding_task_description"
        await update.message.reply_text("Введите описание задачи (или нажмите Enter, чтобы пропустить).")

    elif action == "adding_task_description":
        title = context.user_data.get("new_task_title", "Без названия")
        description = user_text if user_text.strip() else "Без описания"

        try:
            with SessionLocal() as db:
                new_task = Task(title=title, description=description)
                db.add(new_task)
                db.commit()

            await update.message.reply_text(f"✅ Задача '{title}' добавлена!")
        except SQLAlchemyError as e:
            logger.error(f"Ошибка базы данных: {e}")
            await update.message.reply_text("❌ Ошибка при добавлении задачи.")

        # Сброс данных пользователя и возврат в меню
        context.user_data.clear()
        await show_main_menu(update, context)

    elif action == "gpt_chat":
        try:
            gpt_reply = get_gpt_response(user_text)
            await update.message.reply_text(gpt_reply)
        except Exception as e:
            logger.error(f"Ошибка OpenAI: {e}")
            await update.message.reply_text("⚠️ Ошибка при работе с GPT. Попробуйте позже.")

    else:
        await show_main_menu(update, context)

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображает список задач пользователя."""
    try:
        with SessionLocal() as db:
            tasks = db.query(Task).all()

        if not tasks:
            await update.message.reply_text("📭 Список задач пуст.")
        else:
            task_list = "\n".join([f" - {t.id}: {t.title} ({t.description})" for t in tasks])
            await update.message.reply_text(f"📋 Список задач:\n{task_list}")

    except SQLAlchemyError as e:
        logger.error(f"Ошибка базы данных: {e}")
        await update.message.reply_text("❌ Ошибка при загрузке задач.")

    await show_main_menu(update, context)
