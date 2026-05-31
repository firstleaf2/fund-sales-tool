from sqlalchemy import Column, Integer, String, Numeric, DateTime, Text
from datetime import datetime
from app.db.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    phone = Column(String(20))
    email = Column(String(100))
    risk_preference = Column(String(20), nullable=False)  # conservative/moderate/aggressive
    total_assets = Column(Numeric(14, 2), default=0)
    created_at = Column(DateTime, default=datetime.now)
    notes = Column(Text)
