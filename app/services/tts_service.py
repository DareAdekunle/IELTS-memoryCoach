import os
import sys
import hashlib
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer
from dotenv import load_dotenv

load_dotenv()

dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

# ─── TTS Model Configuration ──────────────────────────────────────────────────
# qwen3-tts-flash is nearly quota-exhausted — use the dated variant.
# If this one runs low, check the DashScope console for other
# qwen3-tts-* variants with remaining free quota.
TTS_MODEL = "qwen3-tts-flash-2025-11-27"
TTS_VOICE = "Cherry"

# ─── Audio Cache ──────────────────────────────────────────────────────────────
# Generated audio is cached to disk to avoid redundant API calls.
# Listening track scripts never change, so their audio is cached
# permanently. Speaking feedback is NOT cached (unique per session).
#
# Cache lives outside the Docker container's ephemeral layer via
# the Docker volume mount, so it persists across restarts.

TTS_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "tts_cache"
)
os.makedirs(TTS_CACHE_DIR, exist_ok=True)


def _get_cache_key(text: str, voice: str = TTS_VOICE) -> str:
    """Generates a stable cache key from text + voice combination."""
    content = f"{voice}:{text}"
    return hashlib.md5(content.encode()).hexdigest()


def _get_cached_audio(cache_key: str) -> bytes | None:
    """Returns cached audio bytes if available, None otherwise."""
    cache_path = os.path.join(TTS_CACHE_DIR, f"{cache_key}.wav")
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            return f.read()
    return None


def _save_to_cache(cache_key: str, audio_bytes: bytes) -> None:
    """Saves audio bytes to the disk cache."""
    cache_path = os.path.join(TTS_CACHE_DIR, f"{cache_key}.wav")
    with open(cache_path, "wb") as f:
        f.write(audio_bytes)


def _call_tts_api(text: str) -> dict:
    """
    Makes the actual DashScope TTS API call.
    Returns a dict with success, audio_bytes, and error fields.

    DashScope TTS returns a URL to the generated WAV file.
    The audio field in the response is always empty — we must
    download from the URL. This is a known DashScope quirk.
    """
    try:
        synthesizer = SpeechSynthesizer(
            model=TTS_MODEL,
            voice=TTS_VOICE
        )
        response = synthesizer.call(text)

        if response is None:
            return {
                "success": False,
                "audio_bytes": None,
                "error": "TTS API returned None"
            }

        # DashScope TTS returns a URL — download the actual audio
        audio_url = None
        if hasattr(response, 'output') and response.output:
            audio_data = response.output.get("audio", {})
            audio_url = audio_data.get("url")

        if not audio_url:
            return {
                "success": False,
                "audio_bytes": None,
                "error": "No audio URL in TTS response"
            }

        # Download the WAV file from the URL
        wav_response = requests.get(audio_url, timeout=30)
        if wav_response.status_code != 200:
            return {
                "success": False,
                "audio_bytes": None,
                "error": f"Failed to download audio: HTTP {wav_response.status_code}"
            }

        return {
            "success": True,
            "audio_bytes": wav_response.content,
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "audio_bytes": None,
            "error": str(e)
        }


def examiner_speak(text: str, use_cache: bool = False) -> dict:
    """
    Converts text to speech using Cherry's voice via DashScope TTS.

    For unique per-session content (Speaking Coach feedback):
        use_cache=False — always generates fresh audio

    For static content (Listening track scripts):
        use_cache=True — checks disk cache first,
        generates and caches only on first request.
        Subsequent requests return instantly at zero API cost.

    Returns:
        {
            "success": bool,
            "audio_bytes": bytes | None,
            "from_cache": bool,
            "error": str | None
        }
    """
    if use_cache:
        cache_key = _get_cache_key(text)
        cached = _get_cached_audio(cache_key)
        if cached:
            return {
                "success": True,
                "audio_bytes": cached,
                "from_cache": True,
                "error": None
            }

    result = _call_tts_api(text)
    result["from_cache"] = False

    # Cache the result if caching was requested and generation succeeded
    if use_cache and result["success"] and result["audio_bytes"]:
        cache_key = _get_cache_key(text)
        _save_to_cache(cache_key, result["audio_bytes"])

    return result


def generate_listening_audio(track: dict) -> dict:
    """
    Generates TTS audio for a listening track script.
    Always uses cache — Listening track scripts never change,
    so the first generation is cached permanently.

    This means:
    - First time: ~15-20s generation, costs TTS quota
    - Every subsequent time: ~10ms disk read, costs nothing

    Returns same shape as examiner_speak().
    """
    script = track.get("script", "")
    if not script:
        return {
            "success": False,
            "audio_bytes": None,
            "from_cache": False,
            "error": "Track has no script"
        }
    return examiner_speak(script, use_cache=True)
