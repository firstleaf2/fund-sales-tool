from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from app.db.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    fund_id = Column(Integer, ForeignKey("funds.id"), nullable=False)
    type = Column(String(10), nullable=False)  # buy/redeem
    amount = Column(Numeric(14, 2), nullable=False)
    shares = Column(Numeric(12, 2), nullable=False)
    nav_at_trade = Column(Numeric(10, 4), nullable=False)
    trade_date = Column(DateTime, nullable=False)
