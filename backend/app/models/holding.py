from sqlalchemy import Column, Integer, Numeric, Date, ForeignKey
from app.db.database import Base


class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    fund_id = Column(Integer, ForeignKey("funds.id"), nullable=False)
    shares = Column(Numeric(12, 2), nullable=False)
    cost_price = Column(Numeric(10, 4), nullable=False)
    purchase_date = Column(Date, nullable=False)
