import os
import logging
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Читаем URL базы данных
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///database.db")

# Исправляем URL для PostgreSQL, если нужно
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Подключение к базе данных
try:
    engine = create_engine(DATABASE_URL, echo=False, future=True)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    logger.info("✅ Подключение к базе данных успешно!")
except SQLAlchemyError as e:
    logger.error(f"❌ Ошибка подключения к базе данных: {e}")
    exit(1)

# Определение базы
Base = declarative_base()

# Модель Task
class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)

# Функция для создания таблиц
def init_db():
    """Создает таблицы в базе данных."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Таблицы успешно созданы!")
    except SQLAlchemyError as e:
        logger.error(f"❌ Ошибка создания таблиц: {e}")

# Инициализируем базу при запуске
init_db()
