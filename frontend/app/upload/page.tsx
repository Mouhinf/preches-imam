"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { uploadPreche } from "@/lib/api";

export default function UploadPage() {
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [drag, setDrag] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [title, setTitle] = useState("");
  const [imamName, setImamName] = useState("");
  const [sermonDate, setSermonDate] = useState("");

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDrag(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) setFile(dropped);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      setError("Veuillez sélectionner un fichier audio.");
      return;
    }
    setError("");
    setUploading(true);
    try {
      const form = new FormData();
      form.append("audio", file);
      form.append("title", title || "Prêche sans titre");
      form.append("imam_name", imamName);
      form.append("sermon_date", sermonDate);
      const preche = await uploadPreche(form);
      router.push(`/preche/${preche.id}`);
    } catch (err) {
      setError("Échec de l'upload. Vérifiez le serveur backend.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div>
      <div className="editor-header">
        <div>
          <h1 className="page-title">Nouveau prêche</h1>
          <p className="page-sub">Déposez un fichier audio pour lancer la transcription.</p>
        </div>
        <Link href="/" className="btn">
          ← Retour
        </Link>
      </div>

      <form onSubmit={handleSubmit} className="card" style={{ padding: "2rem" }}>
        <div className="form-row">
          <label>Titre du prêche</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Ex: Sermon du vendredi — Ramadan 1446"
          />
        </div>

        <div className="editor-meta-form">
          <div className="form-row">
            <label>Nom de l&apos;imam</label>
            <input
              type="text"
              value={imamName}
              onChange={(e) => setImamName(e.target.value)}
              placeholder="Ex: Cheikh Mohammed"
            />
          </div>
          <div className="form-row">
            <label>Date du prêche</label>
            <input
              type="date"
              value={sermonDate}
              onChange={(e) => setSermonDate(e.target.value)}
            />
          </div>
        </div>

        <div className="form-row">
          <label>Fichier audio</label>
          <div
            className={`dropzone${drag ? " drag" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={handleDrop}
            onClick={() => fileRef.current?.click()}
          >
            <div className="icon">
              {file ? "🎵" : "📁"}
            </div>
            {file ? (
              <div>
                <strong>{file.name}</strong>
                <div className="file-info">
                  {(file.size / 1024 / 1024).toFixed(1)} Mo
                  <button
                    type="button"
                    style={{ marginLeft: "0.75rem", textDecoration: "underline", background: "none", border: "none", cursor: "pointer", color: "var(--danger)" }}
                    onClick={(e) => { e.stopPropagation(); setFile(null); }}
                  >
                    Supprimer
                  </button>
                </div>
              </div>
            ) : (
              <div>
                <strong>Glissez-déposez</strong> un fichier audio ou cliquez pour choisir
                <div className="file-info">MP3, WAV, M4A, OGG — recommandé &lt; 200 Mo</div>
              </div>
            )}
          </div>
          <input
            ref={fileRef}
            type="file"
            accept="audio/*"
            style={{ display: "none" }}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) setFile(f); }}
          />
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        <div style={{ marginTop: "1.5rem", display: "flex", gap: "0.75rem" }}>
          <button type="submit" className="btn btn-accent" disabled={uploading}>
            {uploading ? "Upload en cours…" : "Transcrire ce prêche"}
          </button>
          <Link href="/" className="btn">Annuler</Link>
        </div>
      </form>
    </div>
  );
}