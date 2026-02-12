from aiogram import Bot
from datetime import datetime
from typing import List, Dict
import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from models import Channel
from utils.analytics import calculate_recommended_price, calculate_err

logger = logging.getLogger(__name__)


class ChannelStatsCollector:
    """Сборщик реальной статистики каналов"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
    
    async def get_channel_subscribers(self, channel_id: int) -> int:
        """Реальные подписчики"""
        try:
            return await self.bot.get_chat_member_count(channel_id)
        except Exception as e:
            logger.error(f"Ошибка подписчиков {channel_id}: {e}")
            return 0
    
    async def get_recent_posts_views(self, channel_id: int, limit: int = 5) -> List[int]:
        """Реальные просмотры последних постов"""
        views = []
        try:
            messages = []
            async for msg in self.bot.get_chat_history(chat_id=channel_id, limit=limit + 10):
                if msg.text or msg.caption or msg.photo or msg.video:
                    messages.append(msg)
                    if len(messages) >= limit:
                        break
            
            for msg in messages[:limit]:
                if hasattr(msg, 'views') and msg.views:
                    views.append(msg.views)
                else:
                    views.append(0)
        except Exception as e:
            logger.error(f"Ошибка постов {channel_id}: {e}")
        
        while len(views) < limit:
            views.append(0)
        return views[:limit]
    
    async def analyze_channel(self, channel_id: int) -> Dict:
        """Анализ канала"""
        subscribers = await self.get_channel_subscribers(channel_id)
        views = await self.get_recent_posts_views(channel_id)
        
        avg_views = int(sum(views) / len(views)) if views else 0
        err = calculate_err(subscribers, avg_views)
        
        # Оценка качества
        quality_score = 0
        quality_label = "Низкое"
        
        if subscribers > 10000:
            if err > 25:
                quality_score = 95
                quality_label = "Топ"
            elif err > 15:
                quality_score = 80
                quality_label = "Отличное"
            elif err > 10:
                quality_score = 65
                quality_label = "Хорошее"
            elif err > 5:
                quality_score = 45
                quality_label = "Среднее"
            else:
                quality_score = 25
                quality_label = "Низкое"
        else:
            if err > 40:
                quality_score = 85
                quality_label = "Отличное"
            elif err > 25:
                quality_score = 70
                quality_label = "Хорошее"
            elif err > 15:
                quality_score = 50
                quality_label = "Среднее"
            else:
                quality_score = 30
                quality_label = "Низкое"
        
        # Детектор накрутки
        suspicion_score = 0
        
        if err > 70:
            suspicion_score += 50
        elif err > 50:
            suspicion_score += 30
        
        if len(set(views)) == 1 and views[0] > 0:
            suspicion_score += 40
        
        if subscribers > 20000 and err < 3:
            suspicion_score += 35
        
        recommended = calculate_recommended_price(subscribers, avg_views)
        
        return {
            "subscribers": subscribers,
            "avg_views": avg_views,
            "err": round(err, 2),
            "quality_score": quality_score,
            "quality_label": quality_label,
            "suspicion_score": suspicion_score,
            "is_suspicious": suspicion_score > 50,
            "recommended_price_post": recommended["post"],
            "recommended_price_pin": recommended["pin"]
        }
    
    async def update_channel_stats(self, session: AsyncSession, channel_id: int) -> Dict:
        """Обновление статистики в БД"""
        try:
            stats = await self.analyze_channel(channel_id)
            
            await session.execute(
                update(Channel)
                .where(Channel.id == channel_id)
                .values(
                    subscribers=stats["subscribers"],
                    avg_views_5=stats["avg_views"],
                    err=stats["err"],
                    quality_score=stats["quality_score"],
                    quality_label=stats["quality_label"],
                    suspicion_score=stats["suspicion_score"],
                    is_suspicious=stats["is_suspicious"],
                    suggested_price_post=stats["recommended_price_post"],
                    suggested_price_pin=stats["recommended_price_pin"],
                    stats_updated_at=datetime.utcnow()
                )
            )
            await session.commit()
            return stats
        except Exception as e:
            logger.error(f"Ошибка обновления {channel_id}: {e}")
            await session.rollback()
            raise
