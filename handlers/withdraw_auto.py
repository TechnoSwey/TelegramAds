from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging

from models import User, WithdrawRequest, WithdrawStatus
from keyboards import withdraw_currency_keyboard, withdraw_confirmation_keyboard, withdraw_history_keyboard
from utils.cryptopay_withdraw import CryptoPayWithdraw
from config import config

router = Router()
logger = logging.getLogger(__name__)


class WithdrawStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_currency = State()
    waiting_for_confirmation = State()


@router.callback_query(F.data == "withdraw_start")
async def withdraw_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начало вывода"""
    user = await session.get(User, callback.from_user.id)
    
    # Считаем доступный баланс
    result = await session.execute(
        select(WithdrawRequest)
        .where(
            WithdrawRequest.user_id == callback.from_user.id,
            WithdrawRequest.status == WithdrawStatus.PENDING.value
        )
    )
    pending = result.scalars().all()
    pending_amount = sum(w.amount for w in pending)
    available = user.balance - user.frozen_balance - pending_amount
    
    if available < 1:
        await callback.answer("❌ Минимальная сумма $1", show_alert=True)
        return
    
    await state.update_data(available_balance=available)
    
    await callback.message.edit_text(
        f"💸 **Вывод средств**\n\n"
        f"💰 Доступно: **${available:.2f}**\n"
        f"📉 Мин: $1\n\n"
        f"💎 Бот создаст чек в Crypto Pay\n"
        f"Вы получите ссылку → активируете в @CryptoBot\n\n"
        f"Введите сумму в USD:",
        parse_mode="Markdown"
    )
    await state.set_state(WithdrawStates.waiting_for_amount)
    await callback.answer()


@router.message(WithdrawStates.waiting_for_amount)
async def process_amount(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка суммы"""
    try:
        amount = float(message.text.replace(',', '.'))
        data = await state.get_data()
        available = data['available_balance']
        
        if amount < 1:
            await message.answer("❌ Минимум $1")
            return
        
        if amount > available:
            await message.answer(f"❌ Доступно только ${available:.2f}")
            return
        
        # Доступные валюты
        currencies = await CryptoPayWithdraw.get_available_currencies(amount)
        
        if not currencies:
            await message.answer("❌ Нет доступных валют для этой суммы")
            return
        
        await state.update_data(amount=amount)
        
        text = f"💰 **Сумма: ${amount:.2f}**\n\n🌐 **Выберите валюту:**\n\n"
        for c in currencies:
            text += f"• `{c['currency']}` — **{c['amount']}**\n"
        
        await message.answer(text, parse_mode="Markdown", reply_markup=withdraw_currency_keyboard(currencies, amount))
        await state.set_state(WithdrawStates.waiting_for_currency)
        
    except ValueError:
        await message.answer("❌ Введите число")


@router.callback_query(F.data.startswith("withdraw_currency_"), WithdrawStates.waiting_for_currency)
async def process_currency(callback: CallbackQuery, state: FSMContext):
    """Выбор валюты"""
    currency = callback.data.split("_")[2]
    data = await state.get_data()
    amount = data['amount']
    
    currencies = await CryptoPayWithdraw.get_available_currencies(amount)
    selected = next((c for c in currencies if c['currency'] == currency), None)
    
    await state.update_data(currency=currency, amount_crypto=selected['amount'])
    
    await callback.message.edit_text(
        f"✅ **Подтверждение**\n\n"
        f"💰 Сумма: `${amount:.2f}`\n"
        f"💱 Валюта: `{currency}`\n"
        f"📤 Получите: `{selected['amount']} {currency}`\n\n"
        f"⚠️ С баланса спишется `${amount:.2f}`\n"
        f"✅ Подтвердить?",
        parse_mode="Markdown",
        reply_markup=withdraw_confirmation_keyboard()
    )
    await state.set_state(WithdrawStates.waiting_for_confirmation)
    await callback.answer()


@router.callback_query(F.data == "withdraw_confirm", WithdrawStates.waiting_for_confirmation)
async def confirm_withdraw(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    """Подтверждение - создаем чек и списываем"""
    data = await state.get_data()
    user = await session.get(User, callback.from_user.id)
    
    # Финальная проверка баланса
    result = await session.execute(
        select(WithdrawRequest)
        .where(
            WithdrawRequest.user_id == callback.from_user.id,
            WithdrawRequest.status == WithdrawStatus.PENDING.value
        )
    )
    pending = result.scalars().all()
    pending_amount = sum(w.amount for w in pending)
    available = user.balance - user.frozen_balance - pending_amount
    
    if available < data['amount']:
        await callback.message.edit_text("❌ Баланс изменился. Попробуйте снова.")
        await state.clear()
        return
    
    # Создаем заявку
    withdraw = WithdrawRequest(
        user_id=callback.from_user.id,
        amount=data['amount'],
        amount_crypto=data['amount_crypto'],
        currency=data['currency'],
        status=WithdrawStatus.PENDING.value
    )
    session.add(withdraw)
    await session.commit()
    await session.refresh(withdraw)
    
    # Обрабатываем вывод (чек + списание)
    success = await CryptoPayWithdraw.process_withdrawal(session, withdraw.id)
    
    if not success:
        withdraw.status = WithdrawStatus.REJECTED.value
        await session.commit()
        await callback.message.edit_text("❌ Ошибка создания чека. Попробуйте другую валюту.")
        await state.clear()
        return
    
    # Отправляем чек пользователю
    await callback.message.delete()
    
    await callback.message.answer(
        f"✅ **Вывод выполнен!**\n\n"
        f"💰 Списано: `${data['amount']:.2f}`\n"
        f"💎 Получено: `{data['amount_crypto']} {data['currency']}`\n\n"
        f"🔗 **Ваш чек:**\n`{withdraw.cheque_url}`\n\n"
        f"📌 Нажмите ссылку → активируйте в @CryptoBot",
        parse_mode="Markdown",
        disable_web_page_preview=False
    )
    
    # Кнопка с чеком
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text=f"💎 АКТИВИРОВАТЬ {data['currency']}", url=withdraw.cheque_url)
    
    await callback.message.answer(
        f"🎁 **Чек на {data['amount_crypto']} {data['currency']}**",
        reply_markup=builder.as_markup()
    )
    
    # Уведомление админам
    for admin_id in config.ADMIN_IDS:
        await bot.send_message(
            admin_id,
            f"💰 **Выплата**\n👤 @{callback.from_user.username}\n💵 ${data['amount']:.2f} → {data['amount_crypto']} {data['currency']}\n🔗 {withdraw.cheque_url}",
            disable_web_page_preview=True
        )
    
    await state.clear()
    await callback.answer("✅ Чек создан!", show_alert=False)


@router.callback_query(F.data == "withdraw_cancel", WithdrawStates.waiting_for_confirmation)
async def cancel_withdraw(callback: CallbackQuery, state: FSMContext):
    """Отмена"""
    await callback.message.edit_text("❌ Вывод отменен")
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "withdraw_history")
async def withdraw_history_handler(callback: CallbackQuery, session: AsyncSession, page: int = 0):
    """История выводов"""
    result = await session.execute(
        select(WithdrawRequest)
        .where(WithdrawRequest.user_id == callback.from_user.id)
        .order_by(desc(WithdrawRequest.created_at))
    )
    withdraws = result.scalars().all()
    
    if not withdraws:
        await callback.message.edit_text("📋 У вас нет выводов", reply_markup=withdraw_history_keyboard([], page))
        await callback.answer()
        return
    
    per_page = 5
    start = page * per_page
    end = start + per_page
    
    text = "📋 **История выводов:**\n\n"
    
    for w in withdraws[start:end]:
        status_emoji = {"completed": "✅", "pending": "⏳", "rejected": "❌", "cancelled": "🚫"}.get(w.status, "⏳")
        text += f"{status_emoji} **#{w.id}** {w.created_at.strftime('%d.%m.%Y')}\n   💰 `${w.amount}` → `{w.amount_crypto} {w.currency}`\n   📊 {w.status}\n\n"
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=withdraw_history_keyboard(withdraws, page))
    await callback.answer()


@router.callback_query(F.data.startswith("withdraw_history_page_"))
async def withdraw_history_page(callback: CallbackQuery, session: AsyncSession):
    """Пагинация"""
    page = int(callback.data.split("_")[3])
    await withdraw_history_handler(callback, session, page)
