from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timedelta
import logging

from models import User, Channel, AdCampaign, DailyPayment, DailyPaymentStatus, AdStatus
from config import config

logger = logging.getLogger(__name__)


class BalanceService:
    """Сервис балансов и поденных выплат"""
    
    def __init__(self, session_factory):
        self.session_factory = session_factory
    
    async def create_daily_payments(self, campaign: AdCampaign):
        """Создает поденные выплаты на каждый день"""
        async with self.session_factory() as session:
            channel = await session.get(Channel, campaign.channel_id)
            
            for day in range(1, campaign.duration_days + 1):
                payment_date = campaign.start_date.replace(hour=12, minute=0) + timedelta(days=day-1)
                
                daily = DailyPayment(
                    campaign_id=campaign.id,
                    channel_id=campaign.channel_id,
                    owner_id=channel.owner_id,
                    day_number=day,
                    amount=campaign.price_per_day,
                    payment_date=payment_date,
                    status=DailyPaymentStatus.PENDING.value
                )
                session.add(daily)
            
            await session.commit()
            logger.info(f"✅ Создано {campaign.duration_days} выплат для кампании #{campaign.id}")
    
    async def process_daily_payouts(self):
        """Ежедневные выплаты в 12:00"""
        async with self.session_factory() as session:
            today = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)
            
            result = await session.execute(
                select(DailyPayment)
                .where(
                    DailyPayment.payment_date <= today,
                    DailyPayment.status == DailyPaymentStatus.PENDING.value
                )
            )
            payments = result.scalars().all()
            
            for payment in payments:
                campaign = await session.get(AdCampaign, payment.campaign_id)
                
                if campaign.status != AdStatus.ACTIVE.value:
                    payment.status = DailyPaymentStatus.CANCELLED.value
                    continue
                
                owner = await session.get(User, payment.owner_id)
                owner.balance += payment.amount
                owner.total_earned = (owner.total_earned or 0) + payment.amount
                
                payment.status = DailyPaymentStatus.PAID.value
                payment.paid_at = datetime.utcnow()
                
                logger.info(f"💰 Выплата ${payment.amount} владельцу {owner.id}")
            
            await session.commit()
    
    async def apply_penalty(self, campaign_id: int) -> dict:
        """Штраф 50% за досрочное удаление"""
        async with self.session_factory() as session:
            campaign = await session.get(AdCampaign, campaign_id)
            channel = await session.get(Channel, campaign.channel_id)
            owner = await session.get(User, channel.owner_id)
            
            # Считаем уже выплаченное
            result = await session.execute(
                select(DailyPayment)
                .where(
                    DailyPayment.campaign_id == campaign_id,
                    DailyPayment.status == DailyPaymentStatus.PAID.value
                )
            )
            paid = result.scalars().all()
            earned = sum(p.amount for p in paid)
            
            penalty = earned * config.PENALTY_PERCENT
            
            if owner.balance >= penalty:
                owner.balance -= penalty
                
                advertiser = await session.get(User, campaign.advertiser_id)
                advertiser.balance += penalty
                
                # Отменяем будущие выплаты
                await session.execute(
                    update(DailyPayment)
                    .where(
                        DailyPayment.campaign_id == campaign_id,
                        DailyPayment.status == DailyPaymentStatus.PENDING.value
                    )
                    .values(status=DailyPaymentStatus.CANCELLED.value)
                )
                
                campaign.is_violated = True
                campaign.violated_at = datetime.utcnow()
                campaign.penalty_amount = penalty
                campaign.status = AdStatus.VIOLATION.value
                
                channel.violation_count += 1
                channel.total_penalty_amount += penalty
                
                await session.commit()
                
                return {
                    "penalty": penalty,
                    "earned": earned,
                    "owner_balance": owner.balance,
                    "advertiser_balance": advertiser.balance
                }
            
            return None
    
    async def get_owner_stats(self, owner_id: int) -> dict:
        """Статистика владельца"""
        async with self.session_factory() as session:
            result = await session.execute(
                select(DailyPayment)
                .where(
                    DailyPayment.owner_id == owner_id,
                    DailyPayment.status == DailyPaymentStatus.PAID.value
                )
            )
            payments = result.scalars().all()
            total_earned = sum(p.amount for p in payments)
            
            channels = await session.execute(
                select(Channel).where(Channel.owner_id == owner_id)
            )
            channels = channels.scalars().all()
            
            total_penalties = sum(c.total_penalty_amount for c in channels)
            total_violations = sum(c.violation_count for c in channels)
            
            return {
                "total_earned": round(total_earned, 2),
                "total_penalties": round(total_penalties, 2),
                "total_violations": total_violations,
                "net_income": round(total_earned - total_penalties, 2)
            }
