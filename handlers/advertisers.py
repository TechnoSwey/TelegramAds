from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from models import User, Channel, AdCampaign, AdStatus
from database import get_session
from keyboards import ad_offers, channel_offer, negotiate_keyboard, payment_keyboard
from utils.analytics import calculate_total_price
from utils.cryptopay import create_payment

router = Router()


class CreateAdStates(StatesGroup):
    waiting_for_days = State()
    waiting_for_text = State()
    waiting_for_media = State()
    waiting_for_button_text = State()
    waiting_for_button_url = State()
    waiting_for_custom_price = State()


@router.callback_query(F.data == "find_ads")
async def find_ads(callback: CallbackQuery, session: AsyncSession):
    result = await session.execute(
        select(Channel)
        .where(Channel.status == "active", Channel.is_suspicious == False)
        .order_by(desc(Channel.average_rating), desc(Channel.quality_score))
    )
    channels = result.scalars().all()
    
    channels_data = [{'channel': c} for c in channels]
    
    await callback.message.edit_text(
        "🔍 **Доступные каналы**\n👥 подписчики | 👀 просмотры | ⭐ рейтинг",
        parse_mode="Markdown",
        reply_markup=ad_offers(channels_data)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("view_channel_"))
async def view_channel(callback: CallbackQuery, session: AsyncSession):
    channel_id = int(callback.data.split("_")[2])
    channel = await session.get(Channel, channel_id)
    
    text = (
        f"📢 **{channel.title}**\n\n"
        f"👥 Подписчики: {channel.subscribers:,}\n"
        f"👀 Просмотры: {channel.avg_views_5:,}\n"
        f"📈 ERR: {channel.err:.1f}%\n"
        f"⭐ Рейтинг: {channel.average_rating:.1f}/5.0\n"
        f"✅ Заказов: {channel.completed_orders}\n\n"
        f"💰 **Цены за 1 день:**\n"
        f"📝 Пост: ${channel.price_post:.2f}\n"
        f"📌 Закреп: ${channel.price_pin:.2f}\n\n"
        f"💎 **Оплата поденно**\n"
        f"🛡 **Гарантия: возврат 50% при удалении**\n\n"
        f"Выберите тип:"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=channel_offer(channel.id, channel.username)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("order_"))
async def order_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    parts = callback.data.split("_")
    ad_type = parts[1]
    channel_id = int(parts[2])
    
    channel = await session.get(Channel, channel_id)
    price_per_day = channel.price_pin if ad_type == "pin" else channel.price_post
    
    await state.update_data(
        channel_id=channel_id,
        is_pinned=(ad_type == "pin"),
        price_per_day=price_per_day
    )
    
    await callback.message.edit_text(
        f"📢 **Канал:** {channel.title}\n"
        f"💰 **Цена за 1 день:** ${price_per_day:.2f}\n\n"
        f"📅 **Введите количество дней** (1-30):",
        parse_mode="Markdown"
    )
    await state.set_state(CreateAdStates.waiting_for_days)
    await callback.answer()


@router.message(CreateAdStates.waiting_for_days)
async def process_days(message: Message, state: FSMContext):
    try:
        days = int(message.text)
        if days < 1 or days > 30:
            await message.answer("❌ От 1 до 30 дней")
            return
        
        data = await state.get_data()
        total_price = calculate_total_price(data['price_per_day'], days)
        
        await state.update_data(duration_days=days, duration_hours=days*24, total_price=total_price)
        await message.answer(
            f"📝 **Создание поста**\n\n📅 Срок: {days} дн.\n💰 Сумма: ${total_price:.2f}\n💳 К оплате: ${total_price*1.03:.2f}\n\nОтправьте **текст** поста:",
            parse_mode="Markdown"
        )
        await state.set_state(CreateAdStates.waiting_for_text)
    except ValueError:
        await message.answer("❌ Введите целое число")


@router.message(CreateAdStates.waiting_for_text)
async def process_text(message: Message, state: FSMContext):
    await state.update_data(message_text=message.text or message.caption)
    await message.answer("📎 Отправьте фото/видео/GIF или 'пропустить'")
    await state.set_state(CreateAdStates.waiting_for_media)


@router.message(CreateAdStates.waiting_for_media)
async def process_media(message: Message, state: FSMContext):
    if message.text and message.text.lower() == 'пропустить':
        await state.update_data(media_file_id=None, media_type=None)
        await message.answer("🔘 Добавить inline кнопку? (да/нет)")
        await state.set_state(CreateAdStates.waiting_for_button_text)
        return
    
    media_type = None
    file_id = None
    
    if message.photo:
        media_type = "photo"
        file_id = message.photo[-1].file_id
    elif message.video:
        media_type = "video"
        file_id = message.video.file_id
    elif message.animation:
        media_type = "animation"
        file_id = message.animation.file_id
    else:
        await message.answer("❌ Отправьте фото/видео/GIF или 'пропустить'")
        return
    
    await state.update_data(media_file_id=file_id, media_type=media_type)
    await message.answer("🔘 Добавить inline кнопку? (да/нет)")
    await state.set_state(CreateAdStates.waiting_for_button_text)


@router.message(CreateAdStates.waiting_for_button_text)
async def process_button_choice(message: Message, state: FSMContext):
    if message.text and message.text.lower() == 'да':
        await message.answer("Введите **текст** кнопки:", parse_mode="Markdown")
        await state.set_state(CreateAdStates.waiting_for_button_url)
    else:
        await state.update_data(inline_button_text=None, inline_button_url=None)
        await create_campaign(message, state)


@router.message(CreateAdStates.waiting_for_button_url)
async def process_button_text(message: Message, state: FSMContext):
    await state.update_data(inline_button_text=message.text)
    await message.answer("Введите **ссылку** для кнопки (https://):", parse_mode="Markdown")
    await state.set_state(CreateAdStates.waiting_for_button_text_final)


@router.message(CreateAdStates.waiting_for_button_text_final)
async def process_button_url(message: Message, state: FSMContext, session: AsyncSession):
    url = message.text.strip()
    if not url.startswith(('https://', 'http://', 'tg://')):
        await message.answer("❌ Ссылка должна начинаться с https://")
        return
    
    await state.update_data(inline_button_url=url)
    await create_campaign(message, state, session)


async def create_campaign(message: Message, state: FSMContext, session: AsyncSession = None):
    data = await state.get_data()
    
    campaign = AdCampaign(
        advertiser_id=message.from_user.id,
        channel_id=data['channel_id'],
        is_pinned=data['is_pinned'],
        message_text=data['message_text'],
        media_file_id=data.get('media_file_id'),
        media_type=data.get('media_type'),
        inline_button_text=data.get('inline_button_text'),
        inline_button_url=data.get('inline_button_url'),
        duration_days=data['duration_days'],
        duration_hours=data['duration_hours'],
        price_per_day=data['price_per_day'],
        total_price=data['total_price'],
        status=AdStatus.PENDING.value
    )
    
    session.add(campaign)
    await session.commit()
    await session.refresh(campaign)
    
    payment = await create_payment(session, campaign.id, message.from_user.id, campaign.total_price)
    
    if not payment:
        await message.answer("❌ Ошибка создания платежа")
        return
    
    channel = await session.get(Channel, data['channel_id'])
    
    await message.answer(
        f"✅ **Заказ создан!**\n\n"
        f"📢 Канал: {channel.title}\n"
        f"📅 Срок: {campaign.duration_days} дн.\n"
        f"💰 За день: ${campaign.price_per_day:.2f}\n"
        f"💵 Всего: ${campaign.total_price:.2f}\n"
        f"💳 Комиссия: +${campaign.total_price * 0.03:.2f}\n"
        f"💎 **Итого: ${payment.amount_with_commission:.2f}**\n\n"
        f"📌 При удалении поста - возврат 50%\n\n"
        f"👇 **Оплатите сейчас:**",
        parse_mode="Markdown",
        reply_markup=payment_keyboard(payment.pay_url, payment.crypto_pay_invoice_id)
    )
    
    await state.clear()


@router.callback_query(F.data.startswith("negotiate_"))
async def negotiate_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    channel_id = int(callback.data.split("_")[1])
    channel = await session.get(Channel, channel_id)
    
    await state.update_data(channel_id=channel_id)
    await callback.message.edit_text(
        f"💬 **Торг с {channel.title}**\n\n💰 Цена владельца: ${channel.price_post:.2f}/день\n\nВведите **вашу цену** за 1 день:",
        parse_mode="Markdown"
    )
    await state.set_state(CreateAdStates.waiting_for_custom_price)
    await callback.answer()


@router.message(CreateAdStates.waiting_for_custom_price)
async def process_custom_price(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    try:
        price = float(message.text.replace(',', '.'))
        if price <= 0:
            raise ValueError
        
        data = await state.get_data()
        channel = await session.get(Channel, data['channel_id'])
        
        campaign = AdCampaign(
            advertiser_id=message.from_user.id,
            channel_id=channel.id,
            is_pinned=False,
            message_text="Ожидает согласования",
            duration_days=1,
            duration_hours=24,
            price_per_day=channel.price_post,
            total_price=0,
            advertiser_price=price,
            owner_price=channel.price_post,
            status=AdStatus.NEGOTIATING.value
        )
        
        session.add(campaign)
        await session.commit()
        
        await bot.send_message(
            channel.owner_id,
            f"💬 **Новое предложение!**\n\n📢 Канал: {channel.title}\n👤 Рекламодатель: @{message.from_user.username}\n💰 Ваша цена: ${channel.price_post:.2f}\n💵 Предложение: ${price:.2f}",
            parse_mode="Markdown",
            reply_markup=negotiate_keyboard(campaign.id, is_owner=True)
        )
        
        await message.answer(f"✅ **Предложение отправлено!**\n💰 Ваша цена: ${price:.2f}/день")
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите число больше 0")


@router.callback_query(F.data.startswith("accept_offer_"))
async def accept_offer(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    campaign_id = int(callback.data.split("_")[2])
    campaign = await session.get(AdCampaign, campaign_id)
    
    campaign.status = AdStatus.PAID.value
    campaign.agreed_price_per_day = campaign.advertiser_price
    campaign.price_per_day = campaign.advertiser_price
    await session.commit()
    
    await bot.send_message(
        campaign.advertiser_id,
        f"✅ **Владелец принял ваше предложение!**\n💰 Цена: ${campaign.advertiser_price:.2f}/день"
    )
    await callback.message.edit_text("✅ Предложение принято")
    await callback.answer()


@router.callback_query(F.data.startswith("reject_offer_"))
async def reject_offer(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    campaign_id = int(callback.data.split("_")[2])
    campaign = await session.get(AdCampaign, campaign_id)
    campaign.status = AdStatus.CANCELLED.value
    await session.commit()
    await bot.send_message(campaign.advertiser_id, "❌ Владелец отклонил предложение")
    await callback.message.edit_text("❌ Предложение отклонено")
    await callback.answer()


@router.callback_query(F.data.startswith("offer_price_"))
async def owner_counter_offer(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    campaign_id = int(callback.data.split("_")[2])
    await state.update_data(campaign_id=campaign_id)
    await callback.message.edit_text("💰 Введите **вашу цену** за 1 день:", parse_mode="Markdown")
    await state.set_state("waiting_for_owner_price")
    await callback.answer()


@router.message(F.text, F.state == "waiting_for_owner_price")
async def process_owner_counter_price(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    try:
        price = float(message.text.replace(',', '.'))
        data = await state.get_data()
        campaign = await session.get(AdCampaign, data['campaign_id'])
        
        campaign.owner_price = price
        await session.commit()
        
        await bot.send_message(
            campaign.advertiser_id,
            f"💬 **Владелец предложил свою цену**\n💰 Его цена: ${price:.2f}/день\n💰 Ваша цена: ${campaign.advertiser_price:.2f}/день",
            reply_markup=negotiate_keyboard(campaign.id, is_owner=False)
        )
        
        await message.answer(f"✅ Цена отправлена: ${price:.2f}/день")
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите число больше 0")
