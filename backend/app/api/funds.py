from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.database import get_db
from app.models.fund import Fund
from app.models.nav_history import NAVHistory
from app.schemas.fund import FundListItem, FundListResponse, FundDetail, NAVHistoryItem, NAVHistoryResponse

router = APIRouter(prefix="/api/funds", tags=["funds"])


@router.get("", response_model=FundListResponse)
async def get_funds(
    type: Optional[str] = Query(None, description="基金类型: stock/bond/mixed/money"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    status: Optional[str] = Query(None, description="产品状态: raising/active/liquidated"),
    db: AsyncSession = Depends(get_db),
):
    query = select(Fund)

    if status:
        query = query.where(Fund.status == status)
    else:
        query = query.where(Fund.status != "liquidated")

    if type:
        query = query.where(Fund.type == type)

    if keyword:
        query = query.where(
            (Fund.name.contains(keyword)) | (Fund.code.contains(keyword))
        )

    result = await db.execute(query)
    funds = result.scalars().all()

    return FundListResponse(
        data=[FundListItem.model_validate(f) for f in funds],
        total=len(funds),
    )


@router.get("/{fund_id}", response_model=FundDetail)
async def get_fund_detail(fund_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Fund).where(Fund.id == fund_id))
    fund = result.scalar_one_or_none()
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")
    return FundDetail.model_validate(fund)


@router.get("/{fund_id}/nav-history", response_model=NAVHistoryResponse)
async def get_nav_history(
    fund_id: int,
    days: int = Query(180, description="查询天数"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Fund).where(Fund.id == fund_id))
    fund = result.scalar_one_or_none()
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")

    query = (
        select(NAVHistory)
        .where(NAVHistory.fund_id == fund_id)
        .order_by(NAVHistory.date.desc())
        .limit(days)
    )
    result = await db.execute(query)
    records = result.scalars().all()

    return NAVHistoryResponse(
        fund_id=fund_id,
        data=[NAVHistoryItem.model_validate(r) for r in reversed(records)],
    )
