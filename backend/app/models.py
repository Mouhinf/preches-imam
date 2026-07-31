"""SQLAlchemy models for sermons (prêches)."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from .database import Base


class Preche(Base):
    __tablename__ = "preches"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, default="Prêche sans titre")
    imam_name = Column(String(255), nullable=True)
    sermon_date = Column(String(50), nullable=True)  # ISO date string
    audio_filename = Column(String(255), nullable=True)

    # Transcription / translations as HTML (TipTap output)
    text_ar = Column(Text, nullable=False, default="")
    text_fr = Column(Text, nullable=False, default="")
    text_en = Column(Text, nullable=False, default="")

    # Status: uploaded, transcribing, transcribed, translating, ready, error
    status = Column(String(50), nullable=False, default="uploaded")
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
