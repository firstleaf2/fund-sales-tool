from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.customer import Customer
from app.models.holding import Holding
from app.models.fund import Fund
from app.schemas.customer import (
    CustomerCreate, CustomerUpdate, CustomerResponse,
    CustomerListResponse, HoldingItem, HoldingsResponse,
)

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("", response_model=CustomerListResponse)
async def get_customers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Customer).order_by(Customer.created_at.desc()))
    customers = result.scalars().all()
    return CustomerListResponse(
        data=[CustomerResponse.model_validate(c) for c in customers],
        total=len(customers),
    )


@router.post("", response_model=CustomerResponse, status_code=201)
async def create_customer(data: CustomerCreate, db: AsyncSession = Depends(get_db)):
    customer = Customer(**data.model_dump())
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return CustomerResponse.model_validate(customer)


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(customer_id: int, data: CustomerUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(customer, key, value)

    await db.commit()
    await db.refresh(customer)
    return CustomerResponse.model_validate(customer)


@router.get("/{customer_id}/holdings", response_model=HoldingsResponse)
async def get_customer_holdings(customer_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    result = await db.execute(select(Holding).where(Holding.customer_id == customer_id))
    holdings = result.scalars().all()

    holding_items = []
    total_market_value = 0.0
    total_profit_loss = 0.0

    for h in holdings:
        fund_result = await db.execute(select(Fund).where(Fund.id == h.fund_id))
        fund = fund_result.scalar_one()

        current_nav = float(fund.nav)
        shares = float(h.shares)
        cost_price = float(h.cost_price)
        market_value = shares * current_nav
        cost_total = shares * cost_price
        profit_loss = market_value - cost_total
        profit_rate = profit_loss / cost_total if cost_total > 0 else 0

        total_market_value += market_value
        total_profit_loss += profit_loss

        holding_items.append(HoldingItem(
            id=h.id,
            fund_id=fund.id,
            fund_name=fund.name,
            fund_code=fund.code,
            shares=shares,
            cost_price=cost_price,
            current_nav=current_nav,
            market_value=round(market_value, 2),
            profit_loss=round(profit_loss, 2),
            profit_rate=round(profit_rate, 4),
            purchase_date=str(h.purchase_date),
        ))

    return HoldingsResponse(
        customer_id=customer_id,
        customer_name=customer.name,
        holdings=holding_items,
        total_market_value=round(total_market_value, 2),
        total_profit_loss=round(total_profit_loss, 2),
    )
