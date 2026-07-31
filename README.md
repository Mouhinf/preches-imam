# Plateforme de Prêches de l'Imam

Transcription audio → texte arabe (AssemblyAI), édition WYSIWYG, traduction FR/EN, export PDF professionnel.

## Architecture

```
preches-imam/
├── api/                # Vercel serverless entry point
│   └── index.py
├── backend/            # Python FastAPI
│   └── app/
│       ├── main.py          # Routes API + jobs bg
│       ├── database.py      # SQLite (local) / PostgreSQL (Vercel)
│       ├── models.py        # Modèle Preche
│       ├── schemas.py       # Pydantic schemas
│       ├── transcribe.py    # AssemblyAI API (AR→texte)
│       ├── translate.py     # Google Translate (AR→FR/EN)
│       └── pdf_generator.py # PDF stylisé (ReportLab)
├── frontend/           # Next.js 14 App Router
│   ├── vercel.json          # Config déploiement frontend
│   └── app/
│       ├── page.tsx          # Bibliothèque des prêches
│       ├── upload/page.tsx   # Upload audio
│       └── preche/[id]/page.tsx # Éditeur WYSIWYG TipTap
├── vercel.json         # Config déploiement backend
└── requirements.txt    # Dépendances Python (Vercel)
```

## Installation

### Backend

```bash
cd backend
pip install --break-system-packages -r requirements.txt

# Lancer le serveur (local)
ASSEMBLYAI_API_KEY="ta_clé" uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Ouvrir http://localhost:3000

## Configuration

### Variables d'environnement

| Variable | Description |
|---|---|
| `ASSEMBLYAI_API_KEY` | Clé API AssemblyAI (obligatoire) |
| `DATABASE_URL` | URL PostgreSQL (Vercel) — optionnel, SQLite par défaut |
| `BLOB_READ_WRITE_TOKEN` | Token Vercel Blob (Vercel) — optionnel, stockage local par défaut |
| `NEXT_PUBLIC_API_URL` | URL du backend pour le frontend |

## Déploiement Vercel

Deux projets distincts :

| Projet | URL | Dossier |
|---|---|---|
| Frontend (Next.js) | https://preches-imam.vercel.app | `frontend/` |
| Backend (FastAPI) | https://preches-imam-api.vercel.app | racine (`api/` + `backend/`) |

Variables d'environnement à configurer :
- **Frontend** : `NEXT_PUBLIC_API_URL=https://preches-imam-api.vercel.app`
- **Backend** : `ASSEMBLYAI_API_KEY`, `DATABASE_URL` (optionnel), `BLOB_READ_WRITE_TOKEN` (optionnel)

```bash
# Déployer le frontend
cd frontend
vercel --prod

# Déployer le backend
cd ..
vercel --prod
```

## Utilisation

1. **Upload** — Déposez un fichier audio (MP3, WAV, M4A, OGG)
2. **Transcription** — AssemblyAI transcrit en arabe en quelques secondes
3. **Édition** — Éditeur TipTap pour corriger le texte arabe
4. **Traduction** — Traduire en français ou anglais
5. **Export PDF** — PDF professionnel en arabe, français ou anglais

## Modèle de données

```
Preche
├── id, title, imam_name, sermon_date
├── text_ar, text_fr, text_en (HTML TipTap)
├── audio_filename, status, error_message
├── created_at, updated_at
```
