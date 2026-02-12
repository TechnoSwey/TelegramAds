import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    # Токены (ОБЯЗАТЕЛЬНО ЗАМЕНИТЬ!)
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
    CRYPTO_PAY_TOKEN: str = os.getenv("CRYPTO_PAY_TOKEN", "YOUR_CRYPTO_PAY_TOKEN")
    
    # База данных SQLite
    BASE_DIR: Path = Path(__file__).parent
    DATABASE_URL: str = f"sqlite+aiosqlite:///{BASE_DIR}/bot_database.db"
    
    # ID админов (кто получает уведомления)
    ADMIN_IDS: list = None
    
    # Комиссия бота 3%
    BOT_COMMISSION: float = 0.03
    
    # Штраф за досрочное удаление 50%
    PENALTY_PERCENT: float = 0.5
    
    # Доступные валюты для оплаты/вывода
    CRYPTO_CURRENCIES: list = None
    
    # Webhook для Crypto Pay (если нужен)
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "https://your-domain.com/cryptopay-webhook")
    WEBHOOK_PORT: int = 8080
    WEBHOOK_HOST: str = "0.0.0.0"

    def __post_init__(self):
        if self.ADMIN_IDS is None:
            self.ADMIN_IDS = [123456789]  # ЗАМЕНИТЬ!
        if self.CRYPTO_CURRENCIES is None:
            self.CRYPTO_CURRENCIES = ["USDT", "TON", "BTC", "ETH"]


config = Config()
