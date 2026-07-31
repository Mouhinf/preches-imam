"""Pydantic schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class PrecheBase(BaseModel):
    title: Optional[str] = "Prêche sans titre"
    imam_name: Optional[str] = None
    sermon_date: Optional[str] = None


class PrecheUpdate(BaseModel):
    title: Optional[str] = None
    imam_name: Optional[str] = None
    sermon_date: Optional[str] = None
    text_ar: Optional[str] = None
    text_fr: Optional[str] = None
    text_en: Optional[str] = None


class PrecheOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    imam_name: Optional[str]
    sermon_date: Optional[str]
    audio_filename: Optional[str]
    text_ar: str
    text_fr: str
    text_en: str
    status: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime


class PrecheListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    imam_name: Optional[str]
    sermon_date: Optional[str]
    status: str
    created_at: datetime


class TranslateRequest(BaseModel):
    target: str  # 'fr' or 'en'
    source_text: Optional[str] = None  # optional override; otherwise uses text_ar
