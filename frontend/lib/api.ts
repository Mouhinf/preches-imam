export const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

export type PrecheListItem = {
  id: number;
  title: string;
  imam_name: string | null;
  sermon_date: string | null;
  status: string;
  created_at: string;
};

export type Preche = PrecheListItem & {
  audio_filename: string | null;
  text_ar: string;
  text_fr: string;
  text_en: string;
  error_message: string | null;
  updated_at: string;
};

export async function listPreches(): Promise<PrecheListItem[]> {
  const res = await fetch(`${API_URL}/api/preches`, { cache: "no-store" });
  if (!res.ok) throw new Error("Erreur de chargement");
  return res.json();
}

export async function getPreche(id: number): Promise<Preche> {
  const res = await fetch(`${API_URL}/api/preches/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Erreur de chargement");
  return res.json();
}

export async function uploadPreche(form: FormData): Promise<Preche> {
  const res = await fetch(`${API_URL}/api/preches/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error("Échec de l'upload");
  return res.json();
}

export async function updatePreche(
  id: number,
  data: Partial<Preche>
): Promise<Preche> {
  const res = await fetch(`${API_URL}/api/preches/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Échec de la mise à jour");
  return res.json();
}

export async function deletePreche(id: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/preches/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Échec de la suppression");
}

export async function translatePreche(
  id: number,
  target: "fr" | "en"
): Promise<Preche> {
  const res = await fetch(`${API_URL}/api/preches/${id}/translate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target }),
  });
  if (!res.ok) throw new Error("Échec du lancement de la traduction");
  return res.json();
}

export async function transcribePreche(id: number): Promise<Preche> {
  const res = await fetch(`${API_URL}/api/preches/${id}/transcribe`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Échec du lancement de la transcription");
  return res.json();
}

export function pdfUrl(id: number, lang: "ar" | "fr" | "en"): string {
  return `${API_URL}/api/preches/${id}/pdf?lang=${lang}`;
}