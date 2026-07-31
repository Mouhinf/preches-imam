"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { listPreches, type PrecheListItem } from "@/lib/api";

const statusLabels: Record<string, string> = {
  uploaded: "Audio reçu",
  transcribing: "Transcription…",
  transcribed: "Transcrit",
  translating_fr: "FR en cours…",
  translating_en: "EN en cours…",
  ready: "Prêt",
  error: "Erreur",
};

export default function HomePage() {
  const [preches, setPreches] = useState<PrecheListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<number | null>(null);

  async function load() {
    try {
      const data = await listPreches();
      setPreches(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 4000);
    return () => clearInterval(interval);
  }, []);

  async function handleDelete(id: number) {
    if (!confirm("Supprimer ce prêche ?")) return;
    setDeleting(id);
    try {
      await fetch(`/api/preches/${id}`, { method: "DELETE" });
      setPreches((prev) => prev.filter((p) => p.id !== id));
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div>
      <div className="editor-header">
        <div>
          <h1 className="page-title">Bibliothèque des prêches</h1>
          <p className="page-sub">
            {preches.length} prêche{preches.length > 1 ? "s" : ""} enregistré
            </p>
        </div>
        <Link href="/upload" className="btn btn-primary">
          + Nouveau prêche
        </Link>
      </div>

      {loading ? (
        <div className="empty">
          <p>Chargement…</p>
        </div>
      ) : preches.length === 0 ? (
        <div className="empty card">
          <p style={{ fontSize: "1.5rem", margin: "0 0 0.5rem" }}>🎙️</p>
          <p>Aucun prêche pour le moment.</p>
          <p>
            <Link href="/upload" className="btn btn-primary">
              Ajouter le premier prêche
            </Link>
          </p>
        </div>
      ) : (
        <div className="preche-grid">
          {preches.map((p) => (
            <div key={p.id} className="card preche-card">
              <div className="title">{p.title}</div>
              <div className="meta">
                {p.imam_name && <span>Imam {p.imam_name}</span>}
                {p.sermon_date && (
                  <span>
                    {" · "}
                    {new Date(p.sermon_date).toLocaleDateString("fr-FR", {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                    })}
                  </span>
                )}
              </div>
              <div>
                <span className={`status-pill status-${p.status}`}>
                  {statusLabels[p.status] ?? p.status}
                </span>
              </div>
              <div className="actions">
                <Link href={`/preche/${p.id}`} className="btn">
                  Ouvrir
                </Link>
                <button
                  className="btn btn-danger"
                  onClick={() => handleDelete(p.id)}
                  disabled={deleting === p.id}
                >
                  {deleting === p.id ? "…" : "Supprimer"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}