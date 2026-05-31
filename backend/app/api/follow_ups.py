from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.db.database import get_db
from app.models.follow_up import FollowUp
from app.models.customer import Customer
from app.schemas.follow_up import FollowUpCreate, FollowUpResponse, FollowUpListResponse

router = APIRouter(prefix="/api/follow-ups", tags=["follow-ups"])


@router.get("/{customer_id}", response_model=FollowUpListResponse)
async def get_follow_ups(customer_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FollowUp)
        .where(FollowUp.customer_id == customer_id)
        .order_by(FollowUp.follow_date.desc())
    )
    records = result.scalars().all()
    return FollowUpListResponse(
        data=[FollowUpResponse.model_validate(r) for r in records],
        total=len(records),
    )


@router.post("", response_model=FollowUpResponse, status_code=201)
async def create_follow_up(data: FollowUpCreate, db: AsyncSession = Depends(get_db)):
    # 验证客户存在
    result = await db.execute(select(Customer).where(Customer.id == data.customer_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Customer not found")

    record = FollowUp(
        customer_id=data.customer_id,
        contact_method=data.contact_method,
        content=data.content,
        follow_date=data.follow_date or datetime.now(),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return FollowUpResponse.model_validate(record)


@router.delete("/{follow_up_id}", status_code=204)
async def delete_follow_up(follow_up_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FollowUp).where(FollowUp.id == follow_up_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Follow-up record not found")
    await db.delete(record)
    await db.commit()
