import logging

# Включаем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_gpt_response(user_text: str) -> str:
    """
    ⚠️ OpenAI API временно отключён.
    Если хочешь использовать AI-ответы, раскомментируй код и добавь API-ключ.
    """
    # import openai
    # import os
    # openai.api_key = os.getenv("OPENAI_API_KEY")

    # try:
    #     response = openai.ChatCompletion.create(
    #         model="gpt-3.5-turbo",
    #         messages=[{"role": "user", "content": user_text}],
    #         max_tokens=200
    #     )
    #     return response["choices"][0]["message"]["content"].strip()
    # except Exception as e:
    #     logger.error(f"Ошибка OpenAI: {e}")
    #     return "⚠️ Ошибка при работе с GPT. Попробуйте позже."

    return "🤖 AI-чат временно отключён. Включите OpenAI API, если хотите использовать AI-ответы."
