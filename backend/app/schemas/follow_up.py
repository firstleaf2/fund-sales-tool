from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class FollowUpCreate(BaseModel):
    customer_id: int
    contact_method: str
    content: str
    follow_date: Optional[datetime] = None


class FollowUpResponse(BaseModel):
    id: int
    customer_id: int
    contact_method: str
    content: str
    follow_date: datetime
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class FollowUpListResponse(BaseModel):
    data: list[FollowUpResponse]
    total: int
