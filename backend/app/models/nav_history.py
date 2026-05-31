from sqlalchemy import Column, Integer, Numeric, Date, ForeignKey, UniqueConstraint
from app.db.database import Base


class NAVHistory(Base):
    __tablename__ = "nav_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(Integer, ForeignKey("funds.id"), nullable=False)
    date = Column(Date, nullable=False)
    nav = Column(Numeric(10, 4), nullable=False)
    daily_change = Column(Numeric(6, 4))

    __table_args__ = (
        UniqueConstraint("fund_id", "date", name="uq_fund_date"),
    )
