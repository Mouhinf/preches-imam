"""FastAPI app: upload audio, transcribe, translate, edit, export PDF."""
import io
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import List

from fastapi import (
    FastAPI, UploadFile, File, Form, Depends, HTTPException,
    BackgroundTasks,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from . import models, schemas
from .database import engine, get_db, init_db, SessionLocal
from .transcribe import transcribe_audio, text_to_html
from .translate import translate_html
from .pdf_generator import generate_pdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
AUDIO_DIR = STORAGE_DIR / "audio"
PDF_DIR = STORAGE_DIR / "pdf"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
PDF_DIR.mkdir(parents=True, exist_ok=True)


def _use_blob() -> bool:
    return bool(os.environ.get("BLOB_READ_WRITE_TOKEN"))


def _save_file(data: bytes, filename: str, subdir: str = "audio") -> str:
    """Save a file to Vercel Blob or local disk. Returns the filename."""
    if _use_blob():
        try:
            from vercel_blob import put
            key = f"{subdir}/{filename}"
            put(key, data, {"access": "public"})
        except Exception as e:
            logger.warning(f"Blob put failed, falling back to local: {e}")
            (STORAGE_DIR / subdir / filename).write_bytes(data)
    else:
        (STORAGE_DIR / subdir / filename).write_bytes(data)
    return filename


def _read_file(filename: str, subdir: str = "audio") -> bytes | None:
    """Read a file from Vercel Blob or local disk."""
    if _use_blob():
        try:
            from vercel_blob import get
            resp = get(f"{subdir}/{filename}")
            return resp.content if hasattr(resp, "content") else resp.read()
        except Exception:
            return None
    path = STORAGE_DIR / subdir / filename
    return path.read_bytes() if path.exists() else None


def _delete_file(filename: str, subdir: str = "audio"):
    if _use_blob():
        try:
            from vercel_blob import delete
            delete(f"{subdir}/{filename}")
        except Exception:
            pass
    else:
        try:
            (STORAGE_DIR / subdir / filename).unlink(missing_ok=True)
        except Exception:
            pass


init_db()

app = FastAPI(title="Prêches de l'Imam — API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Background jobs ----------

def _run_transcription(preche_id: int, audio_path: str):
    db = SessionLocal()
    try:
        preche = db.query(models.Preche).filter(models.Preche.id == preche_id).first()
        if not preche:
            return
        preche.status = "transcribing"
        db.commit()
        try:
            text = transcribe_audio(Path(audio_path))
            preche.text_ar = text_to_html(text)
            preche.status = "transcribed"
            preche.error_message = None
        except Exception as e:
            logger.exception(f"Transcription failed for {audio_path}")
            preche.status = "error"
            preche.error_message = f"Transcription: {e}"
        db.commit()
    finally:
        db.close()


def _run_translation(preche_id: int, target: str):
    db = SessionLocal()
    try:
        preche = db.query(models.Preche).filter(models.Preche.id == preche_id).first()
        if not preche or not preche.text_ar:
            return
        preche.status = f"translating_{target}"
        db.commit()
        try:
            translated = translate_html(preche.text_ar, target=target, source="ar")
            if target == "fr":
                preche.text_fr = translated
            elif target == "en":
                preche.text_en = translated
            preche.status = "ready"
            preche.error_message = None
        except Exception as e:
            logger.exception("Translation failed")
            preche.status = "error"
            preche.error_message = f"Traduction {target}: {e}"
        db.commit()
    finally:
        db.close()


# ---------- Routes ----------

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/preches", response_model=List[schemas.PrecheListItem])
def list_preches(db: Session = Depends(get_db)):
    return db.query(models.Preche).order_by(models.Preche.created_at.desc()).all()


@app.get("/api/preches/{preche_id}", response_model=schemas.PrecheOut)
def get_preche(preche_id: int, db: Session = Depends(get_db)):
    preche = db.query(models.Preche).filter(models.Preche.id == preche_id).first()
    if not preche:
        raise HTTPException(404, "Prêche introuvable")
    return preche


@app.post("/api/preches/upload", response_model=schemas.PrecheOut)
async def upload_preche(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    title: str = Form("Prêche sans titre"),
    imam_name: str = Form(""),
    sermon_date: str = Form(""),
    db: Session = Depends(get_db),
):
    ext = Path(audio.filename or "audio.mp3").suffix.lower() or ".mp3"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    data = await audio.read()
    _save_file(data, unique_name, "audio")

    preche = models.Preche(
        title=title or "Prêche sans titre",
        imam_name=imam_name or None,
        sermon_date=sermon_date or None,
        audio_filename=unique_name,
        status="uploaded",
    )
    db.add(preche)
    db.commit()
    db.refresh(preche)

    audio_path = STORAGE_DIR / "audio" / unique_name
    background_tasks.add_task(_run_transcription, preche.id, str(audio_path))
    return preche


@app.patch("/api/preches/{preche_id}", response_model=schemas.PrecheOut)
def update_preche(
    preche_id: int,
    payload: schemas.PrecheUpdate,
    db: Session = Depends(get_db),
):
    preche = db.query(models.Preche).filter(models.Preche.id == preche_id).first()
    if not preche:
        raise HTTPException(404, "Prêche introuvable")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(preche, k, v)
    db.commit()
    db.refresh(preche)
    return preche


@app.post("/api/preches/{preche_id}/translate", response_model=schemas.PrecheOut)
def trigger_translation(
    preche_id: int,
    req: schemas.TranslateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    preche = db.query(models.Preche).filter(models.Preche.id == preche_id).first()
    if not preche:
        raise HTTPException(404, "Prêche introuvable")
    if req.target not in ("fr", "en"):
        raise HTTPException(400, "target doit être 'fr' ou 'en'")
    if not preche.text_ar.strip():
        raise HTTPException(400, "Le texte arabe est vide. Transcrire d'abord.")

    background_tasks.add_task(_run_translation, preche_id, req.target)
    return preche


@app.post("/api/preches/{preche_id}/transcribe", response_model=schemas.PrecheOut)
def retry_transcription(
    preche_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    preche = db.query(models.Preche).filter(models.Preche.id == preche_id).first()
    if not preche:
        raise HTTPException(404, "Prêche introuvable")
    if not preche.audio_filename:
        raise HTTPException(400, "Pas de fichier audio associé")
    audio_data = _read_file(preche.audio_filename, "audio")
    if not audio_data:
        raise HTTPException(400, f"Fichier audio introuvable")

    audio_path = AUDIO_DIR / preche.audio_filename
    audio_path.write_bytes(audio_data)

    logger.info(f"Manual transcription requested for preche {preche_id}")
    background_tasks.add_task(_run_transcription, preche_id, str(audio_path))
    preche.status = "transcribing"
    preche.error_message = None
    db.commit()
    db.refresh(preche)
    return preche


@app.delete("/api/preches/{preche_id}")
def delete_preche(preche_id: int, db: Session = Depends(get_db)):
    preche = db.query(models.Preche).filter(models.Preche.id == preche_id).first()
    if not preche:
        raise HTTPException(404, "Prêche introuvable")
    if preche.audio_filename:
        _delete_file(preche.audio_filename, "audio")
    for lang in ("ar", "fr", "en"):
        _delete_file(f"preche_{preche_id}_{lang}.pdf", "pdf")
    db.delete(preche)
    db.commit()
    return {"ok": True}


@app.get("/api/preches/{preche_id}/pdf")
def export_pdf(preche_id: int, lang: str = "ar", db: Session = Depends(get_db)):
    if lang not in ("ar", "fr", "en"):
        raise HTTPException(400, "lang doit être 'ar', 'fr' ou 'en'")
    preche = db.query(models.Preche).filter(models.Preche.id == preche_id).first()
    if not preche:
        raise HTTPException(404, "Prêche introuvable")

    html = {"ar": preche.text_ar, "fr": preche.text_fr, "en": preche.text_en}[lang]
    pdf_path = PDF_DIR / f"preche_{preche_id}_{lang}.pdf"
    generate_pdf(
        title=preche.title,
        imam_name=preche.imam_name,
        sermon_date=preche.sermon_date,
        html_content=html,
        language=lang,
        output_path=pdf_path,
    )

    safe_title = "".join(c for c in preche.title if c.isalnum() or c in "-_ ").strip() or "preche"

    if _use_blob():
        pdf_data = pdf_path.read_bytes()
        _save_file(pdf_data, f"preche_{preche_id}_{lang}.pdf", "pdf")
        return Response(content=pdf_data, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{safe_title}_{lang}.pdf"'})

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"{safe_title}_{lang}.pdf",
    )
