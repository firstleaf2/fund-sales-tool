from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class CustomerBase(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    risk_preference: str
    notes: Optional[str] = None


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    risk_preference: Optional[str] = None
    notes: Optional[str] = None


class CustomerResponse(CustomerBase):
    id: int
    total_assets: float = 0
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CustomerListResponse(BaseModel):
    data: list[CustomerResponse]
    total: int


class HoldingItem(BaseModel):
    id: int
    fund_id: int
    fund_name: str
    fund_code: str
    shares: float
    cost_price: float
    current_nav: float
    market_value: float
    profit_loss: float
    profit_rate: float
    purchase_date: str


class HoldingsResponse(BaseModel):
    customer_id: int
    customer_name: str
    holdings: list[HoldingItem]
    total_market_value: float
    total_profit_loss: float
