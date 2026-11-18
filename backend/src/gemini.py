"""Shared Gemini client and one helper for structured answers about a screenshot."""
import logging
import os
import time
from functools import lru_cache

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()  # local dev reads backend/.env; on Lambda the key is a real env var
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("No Gemini API key found in environment (set GEMINI_API_KEY in .env)")
    return genai.Client(api_key=api_key)


def ask_about_screen(prompt, image, schema, timeout_ms):
    """Send screenshot bytes (JPEG or PNG, already resized by the client) + prompt.

    Returns a parsed `schema` instance, or None. The bytes stay in memory only (NFR-03).
    """
    mime_type = "image/png" if image.startswith(b"\x89PNG") else "image/jpeg"
    t0 = time.perf_counter()
    response = _client().models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=image, mime_type=mime_type),
            prompt,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            http_options=types.HttpOptions(timeout=timeout_ms),
        ),
    )
    log.info("[gemini] %s took %.2fs", schema.__name__, time.perf_counter() - t0)
    log.debug("[gemini] raw: %s", response.text)
    return response.parsed
