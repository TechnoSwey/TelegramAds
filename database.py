from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from config import config

engine = create_async_engine(
    config.DATABASE_URL,
    echo=False,
    poolclass=NullPool,
    connect_args={"check_same_thread": False}
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()


async def init_db():
    """Создание таблиц"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session():
    """Получение сессии БД"""
    async with AsyncSessionLocal() as session:
        yield session
