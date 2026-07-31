"""Translation using googletrans (free Google Translate web API wrapper).

Note: googletrans uses Google's public translation endpoint. For production
usage, switch to the official Google Cloud Translation API.
"""
import logging
import re
from bs4 import BeautifulSoup, NavigableString

logger = logging.getLogger(__name__)

_translator = None


def _get_translator():
    global _translator
    if _translator is None:
        from googletrans import Translator
        _translator = Translator()
    return _translator


def _translate_text(text: str, target: str, source: str = "ar") -> str:
    if not text or not text.strip():
        return ""
    translator = _get_translator()
    # googletrans v4 is async-style with sync wrapper; handle both
    try:
        result = translator.translate(text, src=source, dest=target)
        # In some versions result is a coroutine - handle both
        if hasattr(result, "__await__"):
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(result)
        return result.text
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        raise


def translate_html(html: str, target: str, source: str = "ar") -> str:
    """Translate text nodes inside an HTML string while preserving the structure."""
    if not html or not html.strip():
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # Collect text nodes
    text_nodes = [
        node for node in soup.find_all(string=True)
        if isinstance(node, NavigableString) and node.strip()
    ]

    if not text_nodes:
        return html

    # Batch into a single string separated by a unique marker to limit API calls
    marker = "\n<<<§§§>>>\n"
    joined = marker.join(str(n) for n in text_nodes)

    # Google's endpoint has limits (~5000 chars). Chunk if needed.
    translated_parts: list[str] = []
    chunks = _chunk_by_marker(joined, marker, max_len=4500)
    for chunk in chunks:
        translated = _translate_text(chunk, target=target, source=source)
        translated_parts.append(translated)

    translated_joined = "".join(translated_parts)
    translated_nodes = translated_joined.split(marker)

    # Some endpoints may merge whitespace; pad with empty strings if needed
    if len(translated_nodes) < len(text_nodes):
        translated_nodes += [""] * (len(text_nodes) - len(translated_nodes))

    for original, translated in zip(text_nodes, translated_nodes):
        original.replace_with(translated)

    return str(soup)


def _chunk_by_marker(text: str, marker: str, max_len: int = 4500) -> list[str]:
    """Split text into chunks <= max_len characters, splitting at the marker boundary."""
    if len(text) <= max_len:
        return [text]

    pieces = text.split(marker)
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        candidate = piece if not current else current + marker + piece
        if len(candidate) > max_len and current:
            chunks.append(current)
            current = piece
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks
