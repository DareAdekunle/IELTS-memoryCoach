import os
import sys
import hashlib
import requests
import tempfile

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer
from dotenv import load_dotenv

load_dotenv()

dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
dashscope.base_http_api_url = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://ws-65ggehps6g6aqox2.ap-southeast-1.maas.aliyuncs.com/api/v1"
)

# ─── TTS Model Configuration ──────────────────────────────────────────────────
TTS_MODEL = "qwen3-tts-flash-2025-11-27"
TTS_VOICE = "Cherry"

# ─── OSS Configuration ────────────────────────────────────────────────────────
OSS_ACCESS_KEY_ID     = os.getenv("OSS_ACCESS_KEY_ID")
OSS_ACCESS_KEY_SECRET = os.getenv("OSS_ACCESS_KEY_SECRET")
OSS_BUCKET            = os.getenv("OSS_BUCKET", "ielts-memorycoach-audio")
OSS_ENDPOINT          = os.getenv("OSS_ENDPOINT", "oss-ap-southeast-1.aliyuncs.com")

# OSS available flag — gracefully degrade to disk cache if OSS not configured
_OSS_AVAILABLE = all([OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET])

if _OSS_AVAILABLE:
    try:
        import oss2
        _oss_auth   = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
        _oss_bucket = oss2.Bucket(_oss_auth, f"https://{OSS_ENDPOINT}", OSS_BUCKET)
        print(f"OSS configured: {OSS_BUCKET} @ {OSS_ENDPOINT}")
    except ImportError:
        _OSS_AVAILABLE = False
        print("oss2 not installed — falling back to disk cache")
else:
    print("OSS credentials not set — using disk cache")

# ─── Disk cache fallback ──────────────────────────────────────────────────────
TTS_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "tts_cache"
)
os.makedirs(TTS_CACHE_DIR, exist_ok=True)


def _get_cache_key(text: str, voice: str = TTS_VOICE) -> str:
    """Stable cache key from text + voice."""
    return hashlib.md5(f"{voice}:{text}".encode()).hexdigest()


def _get_oss_key(cache_key: str) -> str:
    """OSS object key for a given cache key."""
    return f"tts/{cache_key}.wav"


def _get_signed_url(oss_key: str, expires: int = 3600) -> str:
    """
    Returns a pre-signed URL for the OSS object.
    Valid for `expires` seconds (default 1 hour).
    The React frontend uses this URL directly to play audio —
    audio is served from Alibaba Cloud OSS CDN, not from ECS.
    """
    return _oss_bucket.sign_url('GET', oss_key, expires)


def _check_oss_exists(oss_key: str) -> bool:
    """Check if an object exists in OSS."""
    try:
        _oss_bucket.get_object_meta(oss_key)
        return True
    except Exception:
        return False


def _upload_to_oss(audio_bytes: bytes, oss_key: str) -> bool:
    """Upload audio bytes to OSS. Returns True on success."""
    try:
        _oss_bucket.put_object(oss_key, audio_bytes)
        return True
    except Exception as e:
        print(f"OSS upload failed: {e}")
        return False


def _get_disk_cached(cache_key: str) -> bytes | None:
    """Returns cached audio bytes from disk if available."""
    path = os.path.join(TTS_CACHE_DIR, f"{cache_key}.wav")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    return None


def _save_to_disk(cache_key: str, audio_bytes: bytes) -> None:
    """Saves audio bytes to disk cache."""
    path = os.path.join(TTS_CACHE_DIR, f"{cache_key}.wav")
    with open(path, "wb") as f:
        f.write(audio_bytes)


def _call_tts_api(text: str) -> dict:
    """
    Makes the actual DashScope TTS API call.
    DashScope TTS returns a URL to the generated WAV file —
    the audio field in the response is always empty.
    """
    try:
        synthesizer = SpeechSynthesizer(model=TTS_MODEL, voice=TTS_VOICE)
        response = synthesizer.call(text)

        if response is None:
            return {"success": False, "audio_bytes": None, "error": "TTS API returned None"}

        audio_url = None
        if hasattr(response, 'output') and response.output:
            audio_data = response.output.get("audio", {})
            audio_url = audio_data.get("url")

        if not audio_url:
            return {"success": False, "audio_bytes": None, "error": "No audio URL in TTS response"}

        wav_response = requests.get(audio_url, timeout=30)
        if wav_response.status_code != 200:
            return {
                "success": False,
                "audio_bytes": None,
                "error": f"Failed to download audio: HTTP {wav_response.status_code}"
            }

        return {"success": True, "audio_bytes": wav_response.content, "error": None}

    except Exception as e:
        return {"success": False, "audio_bytes": None, "error": str(e)}


def examiner_speak(text: str, use_cache: bool = False) -> dict:
    """
    Converts text to speech using Cherry's voice via DashScope TTS.

    For unique per-session content (Speaking Coach feedback):
        use_cache=False — always generates fresh audio, returns bytes

    For static content (Listening track scripts):
        use_cache=True — checks OSS first, then disk cache, then generates.
        On cache hit: returns signed OSS URL (zero DashScope cost).
        On cache miss: generates, uploads to OSS, returns signed URL.

    Returns:
        {
            "success": bool,
            "audio_bytes": bytes | None,   # for streaming to client
            "audio_url": str | None,        # OSS signed URL (when cached)
            "from_cache": bool,
            "storage": "oss" | "disk" | "generated",
            "error": str | None
        }
    """
    if use_cache:
        cache_key = _get_cache_key(text)

        # Try OSS first (production path)
        if _OSS_AVAILABLE:
            oss_key = _get_oss_key(cache_key)
            if _check_oss_exists(oss_key):
                signed_url = _get_signed_url(oss_key)
                return {
                    "success": True,
                    "audio_bytes": None,
                    "audio_url": signed_url,
                    "from_cache": True,
                    "storage": "oss",
                    "error": None
                }

        # Try disk cache (fallback / local dev)
        cached_bytes = _get_disk_cached(cache_key)
        if cached_bytes:
            return {
                "success": True,
                "audio_bytes": cached_bytes,
                "audio_url": None,
                "from_cache": True,
                "storage": "disk",
                "error": None
            }

    # Generate fresh audio
    result = _call_tts_api(text)
    if not result["success"] or not result["audio_bytes"]:
        return {
            "success": False,
            "audio_bytes": None,
            "audio_url": None,
            "from_cache": False,
            "storage": None,
            "error": result["error"]
        }

    audio_bytes = result["audio_bytes"]

    if use_cache:
        cache_key = _get_cache_key(text)

        # Try to upload to OSS
        if _OSS_AVAILABLE:
            oss_key = _get_oss_key(cache_key)
            if _upload_to_oss(audio_bytes, oss_key):
                signed_url = _get_signed_url(oss_key)
                return {
                    "success": True,
                    "audio_bytes": audio_bytes,
                    "audio_url": signed_url,
                    "from_cache": False,
                    "storage": "oss",
                    "error": None
                }

        # Fall back to disk cache
        _save_to_disk(cache_key, audio_bytes)

    return {
        "success": True,
        "audio_bytes": audio_bytes,
        "audio_url": None,
        "from_cache": False,
        "storage": "disk" if use_cache else "generated",
        "error": None
    }


def generate_listening_audio(track: dict) -> dict:
    """
    Generates TTS audio for a listening track script.
    Always uses cache — Listening track scripts never change.

    On first call: generates via DashScope, uploads to OSS,
                   returns signed URL
    On subsequent calls: returns signed OSS URL instantly
                         (zero DashScope API cost)

    Audio is served directly from Alibaba Cloud OSS,
    not from ECS — reducing ECS bandwidth usage.
    """
    script = track.get("script", "")
    if not script:
        return {
            "success": False,
            "audio_bytes": None,
            "audio_url": None,
            "from_cache": False,
            "storage": None,
            "error": "Track has no script"
        }
    return examiner_speak(script, use_cache=True)
