from aiogram import Bot
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import asyncio
import logging

from models import AdCampaign, AdStatus, Channel
from utils.balance import BalanceService
from config import config

logger = logging.getLogger(__name__)


class DeletionTracker:
    """Отслеживание удаления постов"""
    
    def __init__(self, bot: Bot, session_factory):
        self.bot = bot
        self.session_factory = session_factory
        self.balance_service = BalanceService(session_factory)
    
    async def on_message_deleted(self, channel_id: int, message_id: int):
        """Пост удален - применяем штраф"""
        async with self.session_factory() as session:
            result = await session.execute(
                select(AdCampaign)
                .where(
                    AdCampaign.channel_id == channel_id,
                    AdCampaign.channel_post_id == message_id,
                    AdCampaign.status == AdStatus.ACTIVE.value
                )
            )
            campaign = result.scalar_one_or_none()
            
            if not campaign:
                return
            
            penalty = await self.balance_service.apply_penalty(campaign.id)
            
            if penalty:
                channel = await session.get(Channel, channel_id)
                
                await self.bot.send_message(
                    channel.owner_id,
                    f"⚠️ **НАРУШЕНИЕ!**\n\nВы удалили пост до срока.\n💰 Заработано: ${penalty['earned']:.2f}\n💸 Штраф 50%: -${penalty['penalty']:.2f}\n💵 Баланс: ${penalty['owner_balance']:.2f}",
                    parse_mode="Markdown"
                )
                
                await self.bot.send_message(
                    campaign.advertiser_id,
                    f"✅ **Возврат средств!**\n\nВладелец удалил пост досрочно.\n💰 Вам возвращено: ${penalty['penalty']:.2f}",
                    parse_mode="Markdown"
                )
    
    async def start_polling(self):
        """Проверка каждую минуту"""
        logger.info("👀 Запуск отслеживания удалений...")
        
        while True:
            try:
                async with self.session_factory() as session:
                    result = await session.execute(
                        select(AdCampaign).where(AdCampaign.status == AdStatus.ACTIVE.value)
                    )
                    campaigns = result.scalars().all()
                    
                    for c in campaigns:
                        try:
                            if c.channel_post_id:
                                await self.bot.get_chat(chat_id=c.channel_id, message_id=c.channel_post_id)
                        except Exception as e:
                            if "message not found" in str(e).lower():
                                await self.on_message_deleted(c.channel_id, c.channel_post_id)
                        await asyncio.sleep(0.5)
                
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Ошибка: {e}")
                await asyncio.sleep(60)
