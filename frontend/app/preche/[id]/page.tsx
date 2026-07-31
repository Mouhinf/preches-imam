"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import TextAlign from "@tiptap/extension-text-align";
import Underline from "@tiptap/extension-underline";
import TextStyle from "@tiptap/extension-text-style";
import Color from "@tiptap/extension-color";
import Placeholder from "@tiptap/extension-placeholder";
import { getPreche, updatePreche, translatePreche, pdfUrl, transcribePreche, type Preche } from "@/lib/api";

type Tab = "ar" | "fr" | "en";

const LANG_LABELS: Record<Tab, { label: string; dir: string; placeholder: string }> = {
  ar: { label: "العربية", dir: "rtl", placeholder: "اكتب نص الخطبة هنا…" },
  fr: { label: "Français", dir: "ltr", placeholder: "Rédigez le texte en français…" },
  en: { label: "English", dir: "ltr", placeholder: "Write the text in English here…" },
};

function ToolbarButton({
  onClick,
  active,
  title,
  children,
}: {
  onClick: () => void;
  active?: boolean;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onMouseDown={(e) => { e.preventDefault(); onClick(); }}
      title={title}
      className={active ? "is-active" : ""}
    >
      {children}
    </button>
  );
}

export default function PrechePage({ params }: { params: { id: string } }) {
  const id = Number(params.id);
  const router = useRouter();
  const [preche, setPreche] = useState<Preche | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("ar");
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [translating, setTranslating] = useState(false);
  const [transMsg, setTransMsg] = useState("");
  const [transcribing, setTranscribing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);
  const [metaDirty, setMetaDirty] = useState(false);
  const [metaTitle, setMetaTitle] = useState("");
  const [metaImam, setMetaImam] = useState("");
  const [metaDate, setMetaDate] = useState("");
  const autoSaveRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function load() {
    try {
      const p = await getPreche(id);
      setPreche(p);
      setMetaTitle(p.title);
      setMetaImam(p.imam_name ?? "");
      setMetaDate(p.sermon_date ?? "");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [id]);
  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    if (!preche) return;
    if (preche.status === "transcribing" || preche.status === "uploaded") {
      const interval = setInterval(() => {
        getPreche(id).then(p => setPreche(p)).catch(() => {});
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [preche?.status, id]);

  function getContent(tab: Tab): string {
    if (!preche) return "";
    return tab === "ar" ? preche.text_ar : tab === "fr" ? preche.text_fr : preche.text_en;
  }

  function setContent(tab: Tab, html: string) {
    if (!preche) return;
    const updated = { ...preche };
    if (tab === "ar") updated.text_ar = html;
    else if (tab === "fr") updated.text_fr = html;
    else if (tab === "en") updated.text_en = html;
    setPreche(updated);
  }

  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      TextStyle,
      Color,
      TextAlign.configure({ types: ["heading", "paragraph"] }),
    ],
    content: preche ? getContent(activeTab) : "",
    immediatelyRender: false,
    onUpdate({ editor: ed }) {
      setContent(activeTab, ed.getHTML());
      scheduleSave();
    },
  });

  useEffect(() => {
    if (editor && preche) {
      const html = getContent(activeTab);
      if (editor.getHTML() !== html) {
        editor.commands.setContent(html, false);
      }
    }
  }, [activeTab, preche, editor]);

  const scheduleSave = useCallback(() => {
    if (autoSaveRef.current) clearTimeout(autoSaveRef.current);
    setSaveStatus("saving");
    autoSaveRef.current = setTimeout(() => saveContent(), 1500);
  }, []);

  async function saveContent() {
    if (!preche) return;
    setSaving(true);
    try {
      const updated = await updatePreche(id, {
        title: metaTitle,
        imam_name: metaImam || undefined,
        sermon_date: metaDate || undefined,
        text_ar: preche.text_ar,
        text_fr: preche.text_fr,
        text_en: preche.text_en,
      });
      setPreche(updated);
      setMetaDirty(false);
      setSaveStatus("saved");
      setTimeout(() => setSaveStatus("idle"), 2500);
    } catch {
      setSaveStatus("error");
    } finally {
      setSaving(false);
    }
  }

  async function handleTranslate(target: "fr" | "en") {
    if (!preche) return;
    const msg =
      target === "fr" ? "Traduction en français en cours…" : "Translation to English in progress…";
    setTransMsg(msg);
    setTranslating(true);
    try {
      const updated = await translatePreche(id, target);
      setPreche(updated);
      setTransMsg("");
    } catch {
      setTransMsg("Échec de la traduction.");
    } finally {
      setTranslating(false);
    }
  }

  async function handleTranscribe() {
    setTranscribing(true);
    try {
      const updated = await transcribePreche(id);
      setPreche(updated);
    } catch {
      setTransMsg("Échec du lancement de la transcription.");
    } finally {
      setTranscribing(false);
    }
  }

  if (loading) return <div className="empty"><p>Chargement…</p></div>;
  if (!preche) return <div className="empty"><p>Prêche introuvable.</p><Link href="/" className="btn">Retour</Link></div>;

  const langInfo = LANG_LABELS[activeTab];
  const isRtl = activeTab === "ar";

  return (
    <div>
      <div className="editor-header">
        <div>
          <Link href="/" className="btn" style={{ marginBottom: "0.75rem", display: "inline-flex" }}>
            ← Bibliothèque
          </Link>
          <h1 className="page-title">{preche.title}</h1>
          {preche.imam_name && (
            <p className="page-sub">Imam {preche.imam_name}</p>
          )}
          {preche.error_message && (
            <div className="alert alert-error" style={{ marginTop: "0.5rem" }}>
              ⚠️ {preche.error_message}
            </div>
          )}
        </div>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
          <span className={`save-indicator ${saveStatus}`}>
            {saveStatus === "saving" && "Enregistrement…"}
            {saveStatus === "saved" && "✓ Enregistré"}
            {saveStatus === "error" && "✗ Erreur d&apos;enregistrement"}
          </span>
          {["ar", "fr", "en"].map((lang) => (
            <a
              key={lang}
              href={pdfUrl(id, lang as "ar" | "fr" | "en")}
              target="_blank"
              rel="noopener noreferrer"
              className="btn"
            >
              PDF {lang.toUpperCase()}
            </a>
          ))}
        </div>
      </div>

      <div className="card" style={{ padding: "1.5rem", marginBottom: "1.25rem" }}>
        <div className="editor-meta-form" style={{ marginBottom: 0 }}>
          <div className="form-row" style={{ marginBottom: 0 }}>
            <label>Titre</label>
            <input
              type="text"
              value={metaTitle}
              onChange={(e) => { setMetaTitle(e.target.value); setMetaDirty(true); }}
            />
          </div>
          <div className="form-row" style={{ marginBottom: 0 }}>
            <label>Imam</label>
            <input
              type="text"
              value={metaImam}
              onChange={(e) => { setMetaImam(e.target.value); setMetaDirty(true); }}
            />
          </div>
          <div className="form-row" style={{ marginBottom: 0 }}>
            <label>Date</label>
            <input
              type="date"
              value={metaDate}
              onChange={(e) => { setMetaDate(e.target.value); setMetaDirty(true); }}
            />
          </div>
        </div>
        {metaDirty && (
          <button
            className="btn btn-accent"
            onClick={saveContent}
            style={{ marginTop: "0.75rem" }}
          >
            Enregistrer les métadonnées
          </button>
        )}
      </div>

      {transMsg && <div className="alert alert-info">{transMsg}</div>}

      <div className="tabs-bar">
        <div className="tabs">
          {(Object.keys(LANG_LABELS) as Tab[]).map((tab) => (
            <button
              key={tab}
              type="button"
              className={`tab${activeTab === tab ? " active" : ""}`}
              onClick={() => setActiveTab(tab)}
            >
              {LANG_LABELS[tab].label}
              {!getContent(tab) && (
                <span style={{ color: "#d97706", marginLeft: "4px" }}>*</span>
              )}
            </button>
          ))}
        </div>

        <div className="tab-actions">
          {(!preche.text_ar || preche.status === "error") && preche.audio_filename && (
            <button className="btn btn-accent" onClick={handleTranscribe} disabled={transcribing}>
              🎙️ {transcribing ? "Transcription en cours…" : "Relancer la transcription"}
            </button>
          )}
          {activeTab === "ar" && preche.text_ar && (
            <>
              <button
                className="btn"
                onClick={() => handleTranslate("fr")}
                disabled={translating}
              >
                🌍 Traduire FR
              </button>
              <button
                className="btn"
                onClick={() => handleTranslate("en")}
                disabled={translating}
              >
                🌍 Traduire EN
              </button>
            </>
          )}
        </div>
      </div>

      {mounted && editor && (
        <div>
          <div className={`toolbar${isRtl ? " editor-rtl" : ""}`} dir="ltr">
            <ToolbarButton
              onClick={() => editor.chain().focus().toggleBold().run()}
              active={editor.isActive("bold")}
              title="Gras"
            >
              B
            </ToolbarButton>
            <ToolbarButton
              onClick={() => editor.chain().focus().toggleItalic().run()}
              active={editor.isActive("italic")}
              title="Italique"
            >
              <em>I</em>
            </ToolbarButton>
            <ToolbarButton
              onClick={() => editor.chain().focus().toggleUnderline().run()}
              active={editor.isActive("underline")}
              title="Souligné"
            >
              <u>U</u>
            </ToolbarButton>
            <span className="sep" />
            <ToolbarButton
              onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
              active={editor.isActive("heading", { level: 1 })}
              title="Titre 1"
            >
              H1
            </ToolbarButton>
            <ToolbarButton
              onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
              active={editor.isActive("heading", { level: 2 })}
              title="Titre 2"
            >
              H2
            </ToolbarButton>
            <ToolbarButton
              onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
              active={editor.isActive("heading", { level: 3 })}
              title="Titre 3"
            >
              H3
            </ToolbarButton>
            <span className="sep" />
            <ToolbarButton
              onClick={() => editor.chain().focus().toggleBulletList().run()}
              active={editor.isActive("bulletList")}
              title="Liste à puces"
            >
              •
            </ToolbarButton>
            <ToolbarButton
              onClick={() => editor.chain().focus().toggleOrderedList().run()}
              active={editor.isActive("orderedList")}
              title="Liste numérotée"
            >
              1.
            </ToolbarButton>
            <span className="sep" />
            <ToolbarButton
              onClick={() => editor.chain().focus().setTextAlign(isRtl ? "right" : "left").run()}
              active={editor.isActive({ textAlign: isRtl ? "right" : "left" })}
              title="Aligné à gauche"
            >
              ≡L
            </ToolbarButton>
            <ToolbarButton
              onClick={() => editor.chain().focus().setTextAlign("center").run()}
              active={editor.isActive({ textAlign: "center" })}
              title="Centré"
            >
              ≡C
            </ToolbarButton>
            <ToolbarButton
              onClick={() => editor.chain().focus().setTextAlign(isRtl ? "left" : "right").run()}
              active={editor.isActive({ textAlign: isRtl ? "left" : "right" })}
              title="Aligné à droite"
            >
              ≡R
            </ToolbarButton>
            <span className="sep" />
            <ToolbarButton
              onClick={() => editor.chain().focus().toggleBlockquote().run()}
              active={editor.isActive("blockquote")}
              title="Citation"
            >
              &ldquo;&rdquo;
            </ToolbarButton>
            <ToolbarButton
              onClick={() => editor.chain().focus().undo().run()}
              title="Annuler"
            >
              ↩
            </ToolbarButton>
            <ToolbarButton
              onClick={() => editor.chain().focus().redo().run()}
              title="Rétablir"
            >
              ↪
            </ToolbarButton>
          </div>

          <div
            className={`editor-content${isRtl ? " editor-rtl" : ""}`}
            dir={langInfo.dir}
          >
            <EditorContent editor={editor} />
          </div>
        </div>
      )}

      <div style={{ marginTop: "1rem", display: "flex", gap: "0.75rem" }}>
        {["ar", "fr", "en"].map((lang) => (
          <a
            key={lang}
            href={pdfUrl(id, lang as "ar" | "fr" | "en")}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-accent"
          >
            📄 Télécharger PDF {lang.toUpperCase()}
          </a>
        ))}
      </div>
    </div>
  );
}