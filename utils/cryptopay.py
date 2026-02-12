from cryptopay import CryptoPay
from cryptopay.types import Invoice
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging
from typing import Optional

from config import config
from models import CryptoPayment

logger = logging.getLogger(__name__)

cp = CryptoPay(token=config.CRYPTO_PAY_TOKEN)


async def create_invoice(amount: float, currency: str = "USDT", description: str = "") -> Optional[Invoice]:
    """Создание инвойса для оплаты"""
    try:
        invoice = await cp.create_invoice(
            amount=amount,
            asset=currency,
            description=description or "Оплата рекламы",
            expires_in=3600,
            paid_btn_name="openChannel",
            paid_btn_url="https://t.me/ad_bot",
            allow_comments=False,
            allow_anonymous=False
        )
        return invoice
    except Exception as e:
        logger.error(f"Ошибка создания инвойса: {e}")
        return None


async def create_payment(session: AsyncSession, campaign_id: int, user_id: int, amount: float) -> Optional[CryptoPayment]:
    """Создание платежа"""
    try:
        amount_with_commission = round(amount * (1 + config.BOT_COMMISSION), 2)
        
        invoice = await create_invoice(
            amount=amount_with_commission,
            currency="USDT",
            description=f"Реклама #{campaign_id}"
        )
        
        if not invoice:
            return None
        
        payment = CryptoPayment(
            campaign_id=campaign_id,
            user_id=user_id,
            amount=amount,
            amount_with_commission=amount_with_commission,
            currency="USDT",
            crypto_pay_invoice_id=invoice.invoice_id,
            pay_url=invoice.pay_url,
            status="active"
        )
        
        session.add(payment)
        await session.commit()
        await session.refresh(payment)
        return payment
        
    except Exception as e:
        logger.error(f"Ошибка создания платежа: {e}")
        await session.rollback()
        return None


async def check_invoice_status(invoice_id: int) -> str:
    """Проверка статуса оплаты"""
    try:
        invoices = await cp.get_invoices(invoice_ids=[invoice_id])
        if invoices and invoices[0]:
            return invoices[0].status
        return "not_found"
    except Exception as e:
        logger.error(f"Ошибка проверки статуса: {e}")
        return "error"
