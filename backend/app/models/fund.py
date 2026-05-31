from sqlalchemy import Column, Integer, String, Numeric, Date, Text
from app.db.database import Base


class Fund(Base):
    __tablename__ = "funds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    type = Column(String(20), nullable=False)  # stock/bond/mixed/money
    nav = Column(Numeric(10, 4), nullable=False)
    daily_change = Column(Numeric(6, 4))
    risk_level = Column(String(10), nullable=False)  # low/medium/high
    manager = Column(String(50))
    established_date = Column(Date)
    management_fee = Column(Numeric(4, 4))
    description = Column(Text)
    status = Column(String(10), default="active")
