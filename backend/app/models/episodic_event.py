from sqlalchemy import Column, Integer, String, Text, Float, DateTime
from datetime import datetime
from app.db.database import Base


class EpisodicEvent(Base):
    __tablename__ = "episodic_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), nullable=False, index=True)
    conversation_id = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    event_type = Column(String(30), nullable=False)  # intent/follow_up/decision/feedback
    entities = Column(Text)  # JSON: ["李明", "华夏成长混合"]
    importance = Column(Float, default=0.5)
    created_at = Column(DateTime, default=datetime.now)
