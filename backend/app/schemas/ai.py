from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None


class SourceItem(BaseModel):
    type: str
    id: int
    name: str


class ChartData(BaseModel):
    title: str
    option: dict


class ChatResponse(BaseModel):
    reply: str
    sources: list[SourceItem] = []
    conversation_id: str
    chart: Optional[ChartData] = None
