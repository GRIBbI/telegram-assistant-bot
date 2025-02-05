from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///database.db"

engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    details = Column(String, nullable=True)  # 🔹 Поле details ДОЛЖНО быть здесь!
    deadline = Column(DateTime, nullable=True)  # 🔹 Поле deadline ДОЛЖНО быть здесь!

def init_db():
    """Создаёт таблицы в БД"""
    Base.metadata.create_all(bind=engine)
