from sqlalchemy import (
    Column, BigInteger, String, Float, DateTime, Boolean, 
    ForeignKey, Text, Integer, JSON
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import enum

Base = declarative_base()


class UserRole(str, enum.Enum):
    OWNER = "owner"
    ADVERTISER = "advertiser"
    BOTH = "both"


class ChannelStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    BLOCKED = "blocked"


class AdStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NEGOTIATING = "negotiating"
    DISPUTE = "dispute"
    VIOLATION = "violation"


class DailyPaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    PENALTY = "penalty"
    CANCELLED = "cancelled"


class WithdrawStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255))
    last_name = Column(String(255), nullable=True)
    role = Column(String(50), default=UserRole.BOTH.value)
    
    # Баланс
    balance = Column(Float, default=0.0)
    frozen_balance = Column(Float, default=0.0)
    
    # Статистика
    total_earned = Column(Float, default=0.0)
    total_withdrawn = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    channels = relationship("Channel", back_populates="owner", cascade="all, delete-orphan")
    ad_campaigns = relationship("AdCampaign", back_populates="advertiser", cascade="all, delete-orphan")
    payments = relationship("CryptoPayment", back_populates="user", cascade="all, delete-orphan")
    daily_payments_received = relationship("DailyPayment", foreign_keys="DailyPayment.owner_id", back_populates="owner")
    withdraw_requests = relationship("WithdrawRequest", back_populates="user", cascade="all, delete-orphan")
    reviews_written = relationship("Review", back_populates="author", cascade="all, delete-orphan")
    disputes_initiated = relationship("Dispute", foreign_keys="Dispute.initiator_id", back_populates="initiator")
    disputes_responded = relationship("Dispute", foreign_keys="Dispute.respondent_id", back_populates="respondent")


class Channel(Base):
    __tablename__ = "channels"

    id = Column(BigInteger, primary_key=True)
    owner_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    title = Column(String(255))
    username = Column(String(255), nullable=True)
    invite_link = Column(String(512), nullable=True)
    
    # Статистика
    subscribers = Column(Integer, default=0)
    avg_views_5 = Column(Integer, default=0)
    
    # Цены за 1 день
    price_post = Column(Float, default=0.0)
    price_pin = Column(Float, default=0.0)
    
    status = Column(String(50), default=ChannelStatus.PENDING.value)
    is_bot_admin = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)
    
    # Рекомендуемые цены
    suggested_price_post = Column(Float, nullable=True)
    suggested_price_pin = Column(Float, nullable=True)
    
    # Метрики качества
    err = Column(Float, default=0.0)
    quality_score = Column(Integer, default=0)
    quality_label = Column(String(50), default="Нет данных")
    suspicion_score = Column(Integer, default=0)
    is_suspicious = Column(Boolean, default=False)
    stats_updated_at = Column(DateTime, nullable=True)
    
    # Рейтинг
    total_reviews = Column(Integer, default=0)
    average_rating = Column(Float, default=0.0)
    completed_orders = Column(Integer, default=0)
    
    # Нарушения
    violation_count = Column(Integer, default=0)
    total_penalty_amount = Column(Float, default=0.0)
    
    # Связи
    owner = relationship("User", back_populates="channels")
    ads = relationship("AdCampaign", back_populates="channel", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="channel", cascade="all, delete-orphan")
    daily_payments = relationship("DailyPayment", back_populates="channel", cascade="all, delete-orphan")


class AdCampaign(Base):
    __tablename__ = "ad_campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    advertiser_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    channel_id = Column(BigInteger, ForeignKey("channels.id", ondelete="CASCADE"))
    
    # Тип
    is_pinned = Column(Boolean, default=False)
    
    # Контент
    message_text = Column(Text)
    media_file_id = Column(String(512), nullable=True)
    media_type = Column(String(50), nullable=True)
    inline_button_text = Column(String(255), nullable=True)
    inline_button_url = Column(String(512), nullable=True)
    
    # Срок
    duration_days = Column(Integer, default=1)
    duration_hours = Column(Integer, default=24)
    
    # Время удаления
    scheduled_delete_time = Column(DateTime, nullable=True)
    delete_job_id = Column(String(255), nullable=True)
    
    # Цены
    price_per_day = Column(Float)
    total_price = Column(Float)
    total_price_with_commission = Column(Float, nullable=True)
    
    # Торги
    agreed_price_per_day = Column(Float, nullable=True)
    advertiser_price = Column(Float, nullable=True)
    owner_price = Column(Float, nullable=True)
    
    negotiation_stage = Column(Integer, default=0)
    negotiation_message_id = Column(Integer, nullable=True)
    
    # Даты
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Платеж
    payment_id = Column(Integer, nullable=True)
    payment_status = Column(String(50), default="pending")
    
    # Статус
    status = Column(String(50), default=AdStatus.PENDING.value)
    channel_post_id = Column(Integer, nullable=True)
    
    # Нарушение
    is_violated = Column(Boolean, default=False)
    violated_at = Column(DateTime, nullable=True)
    penalty_amount = Column(Float, default=0.0)
    
    # Связи
    advertiser = relationship("User", back_populates="ad_campaigns")
    channel = relationship("Channel", back_populates="ads")
    payment = relationship("CryptoPayment", back_populates="campaign", uselist=False, cascade="all, delete-orphan")
    daily_payments = relationship("DailyPayment", back_populates="campaign", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="campaign", cascade="all, delete-orphan")
    dispute = relationship("Dispute", back_populates="campaign", uselist=False, cascade="all, delete-orphan")


class DailyPayment(Base):
    __tablename__ = "daily_payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("ad_campaigns.id", ondelete="CASCADE"))
    channel_id = Column(BigInteger, ForeignKey("channels.id", ondelete="CASCADE"))
    owner_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    
    day_number = Column(Integer)
    amount = Column(Float)
    payment_date = Column(DateTime)
    
    status = Column(String(50), default=DailyPaymentStatus.PENDING.value)
    
    is_penalty = Column(Boolean, default=False)
    penalty_amount = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)
    
    campaign = relationship("AdCampaign", back_populates="daily_payments")
    channel = relationship("Channel", back_populates="daily_payments")
    owner = relationship("User", foreign_keys=[owner_id], back_populates="daily_payments_received")


class CryptoPayment(Base):
    __tablename__ = "crypto_payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("ad_campaigns.id", ondelete="CASCADE"))
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    
    amount = Column(Float)
    amount_with_commission = Column(Float)
    currency = Column(String(10))
    
    crypto_pay_invoice_id = Column(BigInteger)
    pay_url = Column(String(512))
    status = Column(String(50), default="active")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)
    
    campaign = relationship("AdCampaign", back_populates="payment")
    user = relationship("User", back_populates="payments")


class WithdrawRequest(Base):
    __tablename__ = "withdraw_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    
    amount = Column(Float)
    amount_crypto = Column(Float, nullable=True)
    currency = Column(String(10))
    
    # Crypto Pay cheque
    cheque_id = Column(BigInteger, nullable=True)
    cheque_url = Column(String(512), nullable=True)
    cheque_status = Column(String(50), default="active")
    
    status = Column(String(50), default=WithdrawStatus.PENDING.value)
    admin_note = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="withdraw_requests")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("ad_campaigns.id", ondelete="CASCADE"))
    channel_id = Column(BigInteger, ForeignKey("channels.id", ondelete="CASCADE"))
    author_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    
    rating = Column(Integer)
    text = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    campaign = relationship("AdCampaign", back_populates="reviews")
    channel = relationship("Channel", back_populates="reviews")
    author = relationship("User", back_populates="reviews_written")


class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("ad_campaigns.id", ondelete="CASCADE"))
    initiator_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    respondent_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    
    reason = Column(Text)
    evidence = Column(JSON, nullable=True)
    status = Column(String(50), default="open")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(BigInteger, nullable=True)
    
    admin_notes = Column(Text, nullable=True)
    resolution = Column(String(50), nullable=True)
    
    campaign = relationship("AdCampaign", back_populates="dispute")
    initiator = relationship("User", foreign_keys=[initiator_id], back_populates="disputes_initiated")
    respondent = relationship("User", foreign_keys=[respondent_id], back_populates="disputes_responded")
