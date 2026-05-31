from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.db.database import get_db
from app.models.customer import Customer
from app.models.transaction import Transaction
from app.models.holding import Holding
from app.models.fund import Fund
from app.schemas.dashboard import (
    DashboardSummary, SalesTrendItem, SalesTrendResponse,
    ProductDistributionItem, ProductDistributionResponse,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def get_summary(db: AsyncSession = Depends(get_db)):
    # Total sales (sum of all buy transactions)
    result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(Transaction.type == "buy")
    )
    total_sales = float(result.scalar())

    # Total customers
    result = await db.execute(select(func.count(Customer.id)))
    total_customers = result.scalar() or 0

    # Total AUM (sum of all holdings market value)
    result = await db.execute(select(Holding, Fund).join(Fund, Holding.fund_id == Fund.id))
    rows = result.all()
    total_aum = sum(float(h.Holding.shares) * float(h.Fund.nav) for h in rows)

    # Monthly sales (last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(Transaction.type == "buy")
        .where(Transaction.trade_date >= thirty_days_ago)
    )
    monthly_sales = float(result.scalar())

    return DashboardSummary(
        total_sales=round(total_sales, 2),
        total_customers=total_customers,
        total_aum=round(total_aum, 2),
        monthly_sales=round(monthly_sales, 2),
    )


@router.get("/sales-trend", response_model=SalesTrendResponse)
async def get_sales_trend(
    period: str = Query("day", description="day/week/month"),
    days: int = Query(30, description="查询范围天数"),
    db: AsyncSession = Depends(get_db),
):
    start_date = datetime.now() - timedelta(days=days)
    result = await db.execute(
        select(Transaction)
        .where(Transaction.type == "buy")
        .where(Transaction.trade_date >= start_date)
        .order_by(Transaction.trade_date)
    )
    transactions = result.scalars().all()

    # Group by period
    grouped: dict[str, float] = {}
    for t in transactions:
        trade_dt = t.trade_date
        if period == "day":
            key = trade_dt.strftime("%Y-%m-%d")
        elif period == "week":
            week_start = trade_dt - timedelta(days=trade_dt.weekday())
            key = week_start.strftime("%Y-%m-%d")
        else:
            key = trade_dt.strftime("%Y-%m")

        grouped[key] = grouped.get(key, 0) + float(t.amount)

    data = [SalesTrendItem(date=k, amount=round(v, 2)) for k, v in sorted(grouped.items())]

    return SalesTrendResponse(period=period, data=data)


@router.get("/product-distribution", response_model=ProductDistributionResponse)
async def get_product_distribution(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Transaction, Fund)
        .join(Fund, Transaction.fund_id == Fund.id)
        .where(Transaction.type == "buy")
    )
    rows = result.all()

    type_totals: dict[str, float] = {}
    grand_total = 0.0
    for row in rows:
        fund_type = row.Fund.type
        amount = float(row.Transaction.amount)
        type_totals[fund_type] = type_totals.get(fund_type, 0) + amount
        grand_total += amount

    type_labels = {"stock": "股票型", "bond": "债券型", "mixed": "混合型", "money": "货币型"}

    data = []
    for t, amount in sorted(type_totals.items(), key=lambda x: -x[1]):
        data.append(ProductDistributionItem(
            type=t,
            label=type_labels.get(t, t),
            amount=round(amount, 2),
            percentage=round(amount / grand_total, 4) if grand_total > 0 else 0,
        ))

    return ProductDistributionResponse(data=data)
