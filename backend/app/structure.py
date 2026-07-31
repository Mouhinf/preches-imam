"""Structure raw ASR transcript into a presentable TipTap-compatible HTML.

Uses an OpenRouter LLM (Claude/GPT/DeepSeek) when OPENROUTER_API_KEY is set,
with a local heuristic fallback so the feature degrades gracefully.

The LLM marks up sermons like a real khutbah: paragraphs, section headings,
Quranic verses (green), hadiths (blue), important words in bold.
"""
import json
import logging
import os
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

from .translate import _fetch_json, _mark_openrouter_down, _openrouter_available

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "google/gemma-4-26b-a4b-it:free"
FREE_FALLBACK_MODELS = [
    "openai/gpt-oss-20b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "inclusionai/ling-3.0-flash:free",
]

# Budgets to stay inside Vercel's 60s maxDuration (transcription ~10-15s)
STRUCTURE_BUDGET_SECONDS = int(os.environ.get("STRUCTURE_BUDGET_SECONDS", "20"))
CHUNK_CHARS = 800
MAX_WORKERS = 3

# Colors used in markup (also referenced by frontend styles)
QURAN_COLOR = "#0e7c5a"   # deep green
HADITH_COLOR = "#1d4ed8"  # blue

_QURAN_HINT = "القرآن"
_HADITH_HINT = "الحديث"

SYSTEM_PROMPT = """Tu es un spécialiste de la mise en forme de prêches islamiques (khutbah) en arabe classique.

Ta mission : transformer une transcription brute (sortie de reconnaissance vocale, sans ponctuation ni structure) en HTML propre et structuré, prêt pour un éditeur riche de type TipTap.

Règles strictes :
1. NE JAMAIS inventer, ajouter, corriger ou reformuler le contenu. Tu dois uniquement découper, ponctuer, et marquer le texte existant. Tout mot doit rester exactement tel qu'il a été transcrit (même les fautes d'usage oral).
2. Ponctuer le texte (., ؟، ،) et le découper en paragraphes logiques <p>.
3. Détecter les grandes parties du prêche (introduction, rappel, exhortation, invocation finale...) et les introduire avec un titre <h2>.
4. Les versets coraniques cités doivent être placés dans <blockquote> avec le texte dans un <span style="color:#0e7c5a">...</span> (vert).
5. Les hadiths cités dans <blockquote> avec <span style="color:#1d4ed8">...</span> (bleu).
6. Mettre en <strong> les formules de bénédiction (صلى الله عليه وسلم...) et les mots-clés religieux importants (الله، الرسول، الصلاة، التقوى...).
7. Utiliser <em> pour les emphase mineures uniquement.
8. Répondre UNIQUEMENT avec le HTML (aucun texte avant/après, aucun commentaire, aucun code fence)."""


def structure_html(text: str, language: str = "ar") -> str:
    """Return presentable HTML for a raw transcript.

    Uses an OpenRouter LLM (with per-chunk parallelism and a global time
    budget) when a key is set, otherwise a heuristic formatter.
    """
    if not text or not text.strip():
        return ""

    if os.environ.get("OPENROUTER_API_KEY") and _openrouter_available():
        try:
            html = _structure_llm_bounded(text, language)
            if _validate_html(html):
                return html
            logger.warning("LLM returned invalid HTML, using fallback")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                _mark_openrouter_down()
        except Exception as e:
            logger.warning(f"LLM structuring failed, using fallback: {e}")

    return _structure_heuristic(text, language)


def _structure_llm_bounded(text: str, language: str) -> str:
    """Structure text by LLM in parallel chunks within a time budget."""
    chunks = _chunk_text(text, CHUNK_CHARS)

    if len(chunks) == 1:
        return _structure_with_llm(chunks[0], language)

    results: dict[int, str] = {}
    failures: list[str] = []

    executor = ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(chunks)))
    futures = {
        executor.submit(_structure_with_llm, chunk, language): i
        for i, chunk in enumerate(chunks)
    }
    try:
        for future in as_completed(futures, timeout=STRUCTURE_BUDGET_SECONDS):
            index = futures[future]
            try:
                results[index] = future.result()
            except Exception as e:
                failures.append(str(e))
    except TimeoutError:
        logger.warning(f"Structuration dépassée ({STRUCTURE_BUDGET_SECONDS}s), chunks traités: {len(results)}/{len(chunks)}")
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    if not results and failures:
        raise RuntimeError(f"Tous les segments ont échoué : {'; '.join(failures[:2])}")

    # Fall back to heuristic formatting for chunks the LLM failed to process
    ordered = []
    for i, chunk in enumerate(chunks):
        if i in results:
            ordered.append(results[i])
        else:
            ordered.append(_structure_heuristic(chunk, language))
    return "".join(ordered)


def _chunk_text(text: str, max_chars: int) -> list[str]:
    """Split long transcripts into balanced chunks at paragraph-like breaks."""
    if len(text) <= max_chars:
        return [text]
    # prefer splitting at common oral section markers
    markers = ["\n", "اللهم", "عباد الله", "أيها المسلمون", "أما بعد", "وصلى الله"]
    parts: list[str] = []
    remaining = text
    while len(remaining) > max_chars:
        head, tail = remaining[:max_chars], remaining[max_chars:]
        split_at = -1
        for marker in markers:
            if not marker or marker == "\n":
                continue
            pos = head.rfind(marker)
            if pos > max_chars // 2:
                split_at = pos
                break
        if split_at == -1:
            # fall back to sentence/word boundary
            pos = max(head.rfind("."), head.rfind("؟"), head.rfind("،"))
            if pos > max_chars // 2:
                split_at = pos
        if split_at == -1:
            split_at = max_chars
        split_at += 1
        parts.append(head[:split_at].strip())
        remaining = (head[split_at:] + tail).strip()
    if remaining:
        parts.append(remaining)
    return [p for p in parts if p]


def _structure_with_llm(text: str, language: str) -> str:
    models = [os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)] + FREE_FALLBACK_MODELS
    last_error: Exception | None = None
    for model in models:
        try:
            return _chat_completion(model, text)
        except Exception as e:
            last_error = e
            logger.warning(f"Model {model} failed ({e}), trying next")
    raise last_error or RuntimeError("no model available")


def _chat_completion(model: str, text: str) -> str:
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Voici la transcription d'un prêche en arabe. "
                    f"Formate-la en HTML selon tes règles :\n\n{text}"
                ),
            },
        ],
        "temperature": 0.2,
        "max_tokens": 4000,
    }).encode("utf-8")

    data = _fetch_json(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json",
        },
        timeout=20,
        retries=0,
    )
    if data.get("error"):
        raise RuntimeError(f"OpenRouter error: {data['error']}")
    msg = data["choices"][0]["message"]
    content = msg.get("content")
    if not content or not content.strip():
        raise RuntimeError("Empty content from model")
    return _strip_code_fence(content.strip())


def _strip_code_fence(html: str) -> str:
    return re.sub(r"^```(?:html)?\s*|\s*```$", "", html, flags=re.MULTILINE | re.DOTALL).strip()


def _validate_html(html: str) -> bool:
    """Ensure the LLM output is a sane HTML fragment with balanced tags."""
    if not html or len(html) < 20:
        return False
    soup = BeautifulSoup(html, "html.parser")
    if soup.find(["script", "style", "iframe"]) is not None:
        return False
    text = soup.get_text(" ", strip=True)
    if len(text) < 30:
        return False
    # crude balance check: disallow unclosed block tags
    for tag in ("p", "h2", "h3", "blockquote", "div", "ul", "ol"):
        opens = html.count(f"<{tag}")
        closes = html.count(f"</{tag}>")
        if opens > 0 and opens != closes:
            return False
    return True


# ---------------------------------------------------------------------------
# Heuristic fallback (no LLM): paragraphs, section titles, bold key words
# ---------------------------------------------------------------------------

_SECTION_PATTERNS = [
    (r"بسم الله", "مقدمة"),
    (r"الحمد لله", "مقدمة"),
    (r"عباد الله", "الموعظة"),
    (r"أيها المسلمون", "الموعظة"),
    (r"إخوة الإسلام", "الموعظة"),
    (r"أما بعد", "الموعظة"),
    (r"اللهم", "الدعاء"),
    (r"وصلى الله", "الخاتمة"),
]

_QURAN_RE = re.compile(r"(إن الله|قال الله|قال تعالى|﴿|﴾|ألم يأن|وما خلقت|إنما المؤمنون|يا أيها الذين آمنوا)")
_HADITH_RE = re.compile(r"(قال رسول الله|قال النبي|عن أبي هريرة|عن ابن عباس|رواه البخاري|رواه مسلم|صلى الله عليه وسلم)")
_STRONG_RE = re.compile(
    r"(الله|الرحمن|الرحيم|رسول الله|النبي|القرآن|الصلاة|الصيام|الزكاة|الحج|التقوى|الجنة|النار|الشيطان|الإيمان|الإسلام|الموت|الآخرة|الدنيا|الدين|الشهادة|الهدى)"
)


def _structure_heuristic(text: str, language: str) -> str:
    if language != "ar":
        return "".join(f"<p>{_escape(p)}</p>" for p in text.split("\n") if p.strip())

    # Split into sentences at common oral pauses
    sentences = re.split(r"(?<=[.!؟،]) +", text.strip())
    if len(sentences) <= 1:
        sentences = re.split(r"\s+(?=\u0627\u0644\u062d\u0645\u062f|\u064a\u0627 \u0623\u064a\u0647\u0627|\u0639\u0628\u0627\u062f \u0627\u0644\u0644\u0647|\u0648\u0635\u0644\u0649 \u0627\u0644\u0644\u0647|\u0623\u0645\u0627 \u0628\u0639\u062f)", text.strip())

    paragraphs: list[str] = []
    current: list[str] = []
    last_section: str | None = None

    def flush():
        nonlocal current
        if current:
            paragraphs.append("".join(current))
            current = []

    for sentence in sentences:
        s = sentence.strip()
        if not s:
            continue
        section = None
        for pattern, name in _SECTION_PATTERNS:
            if re.search(pattern, s):
                section = name
                break
        if section and section != last_section:
            flush()
            paragraphs.append(f"<h2>{_escape(section)}</h2>")
            last_section = section
        current.append(_markup_sentence(s))
    flush()

    if not paragraphs:
        return f"<p>{_escape(text)}</p>"
    return "".join(paragraphs)


def _markup_sentence(sentence: str) -> str:
    """Return a full HTML block (p or blockquote) for one sentence."""
    s = _escape(sentence)

    if _QURAN_RE.search(sentence):
        return _wrap_quote(s, QURAN_COLOR)
    if _HADITH_RE.search(sentence):
        return _wrap_quote(s, HADITH_COLOR)

    # bold key religious words
    def bold(m):
        return f"<strong>{m.group(0)}</strong>"

    return f"<p>{_STRONG_RE.sub(bold, s)}</p>"


def _wrap_quote(content: str, color: str) -> str:
    return (
        f"<blockquote><span style=\"color:{color}\">{content}</span></blockquote>"
    )


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
