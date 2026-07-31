"""Translation using MyMemory API (free, no key) or OpenRouter (optional).

MyMemory is free for up to 5000 chars/day per IP.
Set OPENROUTER_API_KEY to use OpenRouter free models for better quality.
"""
import logging
import os
import re
import urllib.parse
import urllib.request
import json

from bs4 import BeautifulSoup, NavigableString

logger = logging.getLogger(__name__)

MOTOR_URL = "https://api.mymemory.translated.net/get"


def _translate_text(text: str, target: str, source: str = "ar") -> str:
    if not text or not text.strip():
        return ""
    if os.environ.get("OPENROUTER_API_KEY"):
        try:
            return _translate_openrouter(text, target, source)
        except Exception as e:
            logger.warning(f"OpenRouter translation failed, falling back to MyMemory: {e}")
    return _translate_mymemory(text, target, source)


def _translate_mymemory(text: str, target: str, source: str = "ar") -> str:
    params = urllib.parse.urlencode({
        "q": text,
        "langpair": f"{source}|{target}",
    })
    req = urllib.request.Request(f"{MOTOR_URL}?{params}", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    status = data.get("responseStatus")
    if status != 200:
        raise RuntimeError(f"MyMemory error {status}: {data.get('responseDetails')}")
    translated = data.get("responseData", {}).get("translatedText", "")
    # MyMemory wraps errors in QUERY FORMAT ERROR / MYMEMORY WARNING markers
    if not translated or "QUERY FORMAT ERROR" in translated.upper():
        raise RuntimeError(f"MyMemory returned no translation: {translated!r}")
    return translated


def _translate_openrouter(text: str, target: str, source: str = "ar") -> str:
    import urllib.request as u

    lang_name = {"fr": "français", "en": "anglais"}.get(target, target)
    src_name = {"ar": "arabe"}.get(source, source)

    payload = json.dumps({
        "model": "mistralai/mistral-7b-instruct:free",
        "messages": [{
            "role": "user",
            "content": (
                f"Traduis le texte {src_name} suivant en {lang_name}. "
                f"Réponds UNIQUEMENT avec la traduction, sans commentaire.\n\n{text}"
            ),
        }],
        "temperature": 0.3,
    }).encode("utf-8")

    req = u.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json",
        },
    )
    with u.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


def translate_html(html: str, target: str, source: str = "ar") -> str:
    """Translate text nodes inside an HTML string while preserving the structure."""
    if not html or not html.strip():
        return ""

    soup = BeautifulSoup(html, "html.parser")

    text_nodes = [
        node for node in soup.find_all(string=True)
        if isinstance(node, NavigableString) and node.strip()
    ]

    if not text_nodes:
        return html

    # Translate each text node separately: MyMemory truncates large batched
    # requests, so per-node calls are more reliable.
    for node in text_nodes:
        original = str(node)
        pieces = _split_long_text(original)
        translated_pieces: list[str] = []
        ok = True
        for piece in pieces:
            try:
                translated = _translate_text(piece, target=target, source=source)
            except Exception as e:
                logger.warning(f"Translation failed for {piece[:80]!r}: {e}")
                ok = False
                break
            if translated and translated.strip():
                translated_pieces.append(translated)
            else:
                ok = False
                break
        if ok and translated_pieces:
            node.replace_with("".join(translated_pieces))

    return str(soup)


def _split_long_text(text: str, max_len: int = 450) -> list[str]:
    """Split text longer than max_len at sentence boundaries.

    MyMemory rejects requests over ~500 chars (HTTP 414), so long
    paragraphs (typical of ASR transcripts) are split into sentences.
    """
    if len(text) <= max_len:
        return [text]

    import re
    parts = re.split(r"(?<=[.!؟،:]) +", text)
    if len(parts) == 1:
        # No punctuation found: cut at word boundaries (ASR transcripts often
        # contain no punctuation at all).
        words = text.split()
        parts = []
        line = ""
        for w in words:
            if len(line) + len(w) + 1 > max_len:
                parts.append(line)
                line = w
            else:
                line = (line + " " + w) if line else w
        if line:
            parts.append(line)

    chunks: list[str] = []
    current = ""
    for part in parts:
        if len(current) + len(part) + 1 > max_len and current:
            chunks.append(current)
            current = part
        else:
            current = (current + " " + part) if current else part
    if current:
        chunks.append(current)
    return chunks
