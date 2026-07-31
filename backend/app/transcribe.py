"""Audio transcription with AssemblyAI API."""
from pathlib import Path
import logging
import os

import assemblyai as aai

logger = logging.getLogger(__name__)


def transcribe_audio(audio_path: Path) -> str:
    """Transcribe an audio file to Arabic text using AssemblyAI.

    Returns plain text.
    """
    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ASSEMBLYAI_API_KEY is not set. "
            "Get a free API key at https://www.assemblyai.com/"
        )
    aai.settings.api_key = api_key

    config = aai.TranscriptionConfig(language_code="ar")
    transcriber = aai.Transcriber(config=config)
    logger.info(f"Transcribing {audio_path} via AssemblyAI")
    transcript = transcriber.transcribe(str(audio_path))

    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(f"AssemblyAI error: {transcript.error}")

    return transcript.text.strip()
