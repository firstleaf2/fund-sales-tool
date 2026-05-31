from pydantic import BaseModel
from datetime import date
from typing import Optional


class FundBase(BaseModel):
    code: str
    name: str
    type: str
    nav: float
    daily_change: Optional[float] = None
    risk_level: str
    manager: Optional[str] = None
    status: str = "active"


class FundListItem(FundBase):
    id: int

    model_config = {"from_attributes": True}


class FundDetail(FundBase):
    id: int
    established_date: Optional[date] = None
    management_fee: Optional[float] = None
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class FundListResponse(BaseModel):
    data: list[FundListItem]
    total: int


class NAVHistoryItem(BaseModel):
    date: date
    nav: float
    daily_change: Optional[float] = None

    model_config = {"from_attributes": True}


class NAVHistoryResponse(BaseModel):
    fund_id: int
    data: list[NAVHistoryItem]
