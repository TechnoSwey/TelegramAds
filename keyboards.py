from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict
from models import Channel


def main_menu(user_role: str) -> InlineKeyboardMarkup:
    """Главное меню"""
    builder = InlineKeyboardBuilder()
    
    if user_role in ["owner", "both"]:
        builder.button(text="📢 Мои каналы", callback_data="my_channels")
        builder.button(text="➕ Добавить канал", callback_data="add_channel")
        builder.button(text="💰 Мой баланс", callback_data="my_balance")
    
    if user_role in ["advertiser", "both"]:
        builder.button(text="🔍 Найти рекламу", callback_data="find_ads")
        builder.button(text="📋 Мои кампании", callback_data="my_campaigns")
    
    builder.button(text="❓ Помощь", callback_data="help")
    builder.adjust(2)
    return builder.as_markup()


def channels_list(channels: List[Channel], page: int = 0) -> InlineKeyboardMarkup:
    """Список каналов владельца"""
    builder = InlineKeyboardBuilder()
    per_page = 5
    start = page * per_page
    end = start + per_page
    
    for channel in channels[start:end]:
        status = "✅" if channel.status == "active" else "⏳"
        rating = f"⭐ {channel.average_rating:.1f}" if channel.total_reviews > 0 else "⭐ нет отзывов"
        builder.button(
            text=f"{status} {channel.title} | {rating}",
            callback_data=f"channel_{channel.id}"
        )
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"channels_page_{page-1}"))
    if end < len(channels):
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"channels_page_{page+1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.button(text="➕ Добавить канал", callback_data="add_channel")
    builder.button(text="🔙 Главное меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def channel_actions(channel_id: int) -> InlineKeyboardMarkup:
    """Управление каналом"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data=f"channel_stats_{channel_id}")
    builder.button(text="💰 Изменить цены", callback_data=f"set_prices_{channel_id}")
    builder.button(text="🔄 Обновить данные", callback_data=f"refresh_channel_{channel_id}")
    builder.button(text="📋 Заказы", callback_data=f"channel_orders_{channel_id}")
    builder.button(text="📝 Отзывы", callback_data=f"channel_reviews_{channel_id}")
    builder.button(text="🔙 Назад", callback_data="my_channels")
    builder.adjust(2)
    return builder.as_markup()


def ad_offers(channels_data: List[Dict], page: int = 0) -> InlineKeyboardMarkup:
    """Список каналов для рекламы"""
    builder = InlineKeyboardBuilder()
    per_page = 5
    start = page * per_page
    end = start + per_page
    
    for data in channels_data[start:end]:
        channel = data['channel']
        text = f"{channel.title} | 👥 {channel.subscribers:,} | 👀 {channel.avg_views_5:,} | ⭐ {channel.average_rating:.1f}"
        builder.button(text=text, callback_data=f"view_channel_{channel.id}")
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"offers_page_{page-1}"))
    if end < len(channels_data):
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"offers_page_{page+1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def channel_offer(channel_id: int, username: str = None) -> InlineKeyboardMarkup:
    """Предложение канала"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Заказать пост", callback_data=f"order_post_{channel_id}")
    builder.button(text="📌 Заказать закреп", callback_data=f"order_pin_{channel_id}")
    builder.button(text="💬 Предложить цену", callback_data=f"negotiate_{channel_id}")
    
    if username:
        builder.button(text="🔗 Перейти в канал", url=f"https://t.me/{username}")
    
    builder.button(text="🔙 К списку", callback_data="find_ads")
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def negotiate_keyboard(campaign_id: int, is_owner: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура торгов"""
    builder = InlineKeyboardBuilder()
    
    if is_owner:
        builder.button(text="✅ Принять", callback_data=f"accept_offer_{campaign_id}")
        builder.button(text="💰 Предложить свою", callback_data=f"offer_price_{campaign_id}")
        builder.button(text="❌ Отказаться", callback_data=f"reject_offer_{campaign_id}")
    else:
        builder.button(text="💰 Предложить цену", callback_data=f"make_offer_{campaign_id}")
        builder.button(text="❌ Отменить", callback_data=f"cancel_offer_{campaign_id}")
    
    builder.adjust(1)
    return builder.as_markup()


def moderation_keyboard(campaign_id: int) -> InlineKeyboardMarkup:
    """Модерация поста"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ ПРИНЯТЬ", callback_data=f"approve_post_{campaign_id}")
    builder.button(text="❌ ОТКЛОНИТЬ", callback_data=f"reject_post_{campaign_id}")
    builder.button(text="📝 ЗАМЕЧАНИЕ", callback_data=f"comment_post_{campaign_id}")
    builder.adjust(1)
    return builder.as_markup()


def payment_keyboard(pay_url: str, invoice_id: int) -> InlineKeyboardMarkup:
    """Оплата рекламы"""
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Оплатить USDT", url=pay_url)
    builder.button(text="✅ Проверить оплату", callback_data=f"check_payment_{invoice_id}")
    builder.button(text="❌ Отменить", callback_data=f"cancel_order_{invoice_id}")
    builder.adjust(1)
    return builder.as_markup()


def rating_keyboard(campaign_id: int) -> InlineKeyboardMarkup:
    """Оценка 1-5"""
    builder = InlineKeyboardBuilder()
    for i in range(1, 6):
        builder.button(text=f"{'⭐' * i}", callback_data=f"rate_{i}_{campaign_id}")
    builder.adjust(5)
    return builder.as_markup()


def withdraw_currency_keyboard(currencies: list, amount_usd: float) -> InlineKeyboardMarkup:
    """Выбор валюты для вывода"""
    builder = InlineKeyboardBuilder()
    
    for c in currencies:
        builder.button(
            text=f"{c['currency']} - {c['amount']} {c['currency']}",
            callback_data=f"withdraw_currency_{c['currency']}"
        )
    
    builder.button(text="🔙 Назад", callback_data="withdraw_start")
    builder.adjust(1)
    return builder.as_markup()


def withdraw_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Подтверждение вывода"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ ПОДТВЕРДИТЬ", callback_data="withdraw_confirm")
    builder.button(text="❌ ОТМЕНА", callback_data="withdraw_cancel")
    builder.adjust(1)
    return builder.as_markup()


def withdraw_history_keyboard(withdraws: list, page: int = 0) -> InlineKeyboardMarkup:
    """История выводов"""
    builder = InlineKeyboardBuilder()
    
    per_page = 5
    total_pages = (len(withdraws) + per_page - 1) // per_page
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"withdraw_history_page_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"withdraw_history_page_{page+1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.button(text="💸 Новый вывод", callback_data="withdraw_start")
    builder.button(text="🔙 Назад", callback_data="my_balance")
    builder.adjust(1)
    return builder.as_markup()
