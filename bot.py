import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from config import config
from database import init_db, AsyncSessionLocal
from handlers import owners, advertisers, publishing, withdraw_auto
from utils.balance import BalanceService
from utils.cryptopay_withdraw import CryptoPayWithdraw
from handlers.auto_cleanup import DeletionTracker
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="🏠 Главное меню"),
        BotCommand(command="balance", description="💰 Мой баланс"),
        BotCommand(command="my_channels", description="📢 Мои каналы"),
        BotCommand(command="find_ads", description="🔍 Найти рекламу"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())


async def daily_payout_job():
    """Ежедневные выплаты в 12:00"""
    logger.info("💰 Запуск ежедневных выплат...")
    balance_service = BalanceService(AsyncSessionLocal)
    await balance_service.process_daily_payouts()


async def main():
    logger.info("🚀 Запуск бота...")
    
    bot = Bot(token=config.BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Инициализация БД
    await init_db()
    
    # Сервисы
    balance_service = BalanceService(AsyncSessionLocal)
    publishing.balance_service = balance_service
    
    # Планировщик выплат
    scheduler = AsyncIOScheduler()
    scheduler.add_job(daily_payout_job, CronTrigger(hour=12, minute=0), id="daily_payouts")
    scheduler.start()
    
    # Отслеживание удалений
    tracker = DeletionTracker(bot, AsyncSessionLocal)
    asyncio.create_task(tracker.start_polling())
    
    # Регистрация роутеров
    dp.include_router(owners.router)
    dp.include_router(advertisers.router)
    dp.include_router(publishing.router)
    dp.include_router(withdraw_auto.router)
    
    # Команды
    await set_commands(bot)
    
    logger.info("✅ Бот готов!")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
