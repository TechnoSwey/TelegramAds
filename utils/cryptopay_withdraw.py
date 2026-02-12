from cryptopay import CryptoPay
from cryptopay.types import Cheque
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import logging
from typing import Optional

from config import config
from models import User, WithdrawRequest, WithdrawStatus

logger = logging.getLogger(__name__)

cp = CryptoPay(token=config.CRYPTO_PAY_TOKEN)


class CryptoPayWithdraw:
    """Автоматические выплаты через Crypto Pay Cheques"""
    
    SUPPORTED_CURRENCIES = {
        "USDT": {"asset": "USDT", "min_amount": 1.0, "decimals": 2},
        "TON": {"asset": "TON", "min_amount": 0.5, "decimals": 2},
        "BTC": {"asset": "BTC", "min_amount": 0.0001, "decimals": 8},
        "ETH": {"asset": "ETH", "min_amount": 0.001, "decimals": 6}
    }
    
    @staticmethod
    async def get_ton_price() -> float:
        """Курс TON/USDT"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get('https://tonapi.io/v2/rates?tokens=ton&currencies=usd') as resp:
                    data = await resp.json()
                    return float(data['rates']['TON']['prices']['USD'])
        except:
            return 2.3
    
    @staticmethod
    async def get_btc_price() -> float:
        """Курс BTC/USDT"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd') as resp:
                    data = await resp.json()
                    return float(data['bitcoin']['usd'])
        except:
            return 50000.0
    
    @staticmethod
    async def get_eth_price() -> float:
        """Курс ETH/USDT"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd') as resp:
                    data = await resp.json()
                    return float(data['ethereum']['usd'])
        except:
            return 3000.0
    
    @classmethod
    async def create_cheque(cls, user_id: int, amount_usd: float, currency: str = "USDT") -> Optional[Cheque]:
        """Создание чека на вывод"""
        try:
            if currency not in cls.SUPPORTED_CURRENCIES:
                return None
            
            # Конвертация
            if currency == "USDT":
                rate = 1.0
            elif currency == "TON":
                rate = await cls.get_ton_price()
            elif currency == "BTC":
                rate = await cls.get_btc_price()
            elif currency == "ETH":
                rate = await cls.get_eth_price()
            else:
                rate = 1.0
            
            amount_crypto = round(amount_usd / rate, cls.SUPPORTED_CURRENCIES[currency]["decimals"])
            min_amount = cls.SUPPORTED_CURRENCIES[currency]["min_amount"]
            
            if amount_crypto < min_amount:
                logger.error(f"Сумма {amount_crypto} {currency} меньше минимальной")
                return None
            
            # Создаем чек
            cheque = await cp.create_cheque(
                asset=cls.SUPPORTED_CURRENCIES[currency]["asset"],
                amount=amount_crypto,
                expires_in=86400  # 24 часа
            )
            
            logger.info(f"✅ Создан чек на {amount_crypto} {currency} для пользователя {user_id}")
            return cheque
            
        except Exception as e:
            logger.error(f"Ошибка создания чека: {e}")
            return None
    
    @classmethod
    async def process_withdrawal(cls, session: AsyncSession, withdraw_id: int) -> bool:
        """Обработка вывода - создание чека и списание баланса"""
        try:
            withdraw = await session.get(WithdrawRequest, withdraw_id)
            if not withdraw or withdraw.status != WithdrawStatus.PENDING.value:
                return False
            
            user = await session.get(User, withdraw.user_id)
            if not user or user.balance < withdraw.amount:
                withdraw.status = WithdrawStatus.REJECTED.value
                withdraw.admin_note = "Недостаточно средств"
                await session.commit()
                return False
            
            # Создаем чек
            cheque = await cls.create_cheque(
                user_id=user.id,
                amount_usd=withdraw.amount,
                currency=withdraw.currency
            )
            
            if not cheque:
                withdraw.status = WithdrawStatus.REJECTED.value
                withdraw.admin_note = "Ошибка создания чека"
                await session.commit()
                return False
            
            # Обновляем заявку
            withdraw.cheque_id = cheque.cheque_id
            withdraw.cheque_url = cheque.cheque_url
            withdraw.cheque_status = "active"
            withdraw.amount_crypto = cheque.amount
            withdraw.currency = cheque.asset
            withdraw.status = WithdrawStatus.COMPLETED.value
            withdraw.processed_at = datetime.utcnow()
            
            # СПИСЫВАЕМ БАЛАНС!
            user.balance -= withdraw.amount
            user.total_withdrawn = (user.total_withdrawn or 0) + withdraw.amount
            
            await session.commit()
            logger.info(f"✅ Выплата #{withdraw.id} обработана, баланс -${withdraw.amount}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка обработки вывода: {e}")
            await session.rollback()
            return False
    
    @classmethod
    async def get_available_currencies(cls, amount_usd: float) -> list:
        """Список доступных валют для суммы"""
        available = []
        
        for currency in cls.SUPPORTED_CURRENCIES:
            try:
                if currency == "USDT":
                    rate = 1.0
                elif currency == "TON":
                    rate = await cls.get_ton_price()
                elif currency == "BTC":
                    rate = await cls.get_btc_price()
                elif currency == "ETH":
                    rate = await cls.get_eth_price()
                else:
                    continue
                
                amount_crypto = amount_usd / rate
                min_amount = cls.SUPPORTED_CURRENCIES[currency]["min_amount"]
                
                if amount_crypto >= min_amount:
                    available.append({
                        "currency": currency,
                        "amount": round(amount_crypto, cls.SUPPORTED_CURRENCIES[currency]["decimals"]),
                        "min_amount": min_amount
                    })
                    
            except Exception as e:
                logger.error(f"Ошибка проверки {currency}: {e}")
                continue
        
        return available
