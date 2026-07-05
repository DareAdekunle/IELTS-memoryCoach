import os
import sys
import urllib.request

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import dashscope
from dotenv import load_dotenv

load_dotenv()

dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"

TTS_MODEL = "qwen3-tts-flash-2025-11-27"

# Cherry is a clear natural English voice
# good for an IELTS examiner persona
DEFAULT_VOICE = "Cherry"


def text_to_speech(text: str, voice: str = DEFAULT_VOICE) -> dict:
    """
    Converts examiner feedback text to speech using Qwen TTS.

    Steps:
    1. Send text to qwen3-tts-flash
    2. Get back a URL to the generated audio file
    3. Download the audio from the URL
    4. Return the audio bytes so Streamlit can play them

    Returns a dict with:
    - success (bool)
    - audio_bytes (bytes) — the audio data
    - audio_url (str) — the original URL
    - error (str) — error message if failed
    """
    if not text or not text.strip():
        return {
            "success": False,
            "audio_bytes": None,
            "audio_url": "",
            "error": "No text provided for TTS"
        }

    # TTS works best with shorter chunks
    # Truncate very long feedback to avoid timeouts
    if len(text) > 2000:
        text = text[:2000] + "..."

    try:
        response = dashscope.audio.qwen_tts.SpeechSynthesizer.call(
            model=TTS_MODEL,
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            text=text,
            voice=voice
        )

        if response.status_code != 200:
            return {
                "success": False,
                "audio_bytes": None,
                "audio_url": "",
                "error": f"TTS API error: {response.message}"
            }

        # Extract the audio URL from the response
        audio = response.output.get("audio", {})
        audio_url = audio.get("url", "")

        if not audio_url:
            return {
                "success": False,
                "audio_bytes": None,
                "audio_url": "",
                "error": "No audio URL in TTS response"
            }

        # Download the audio file from the URL
        audio_bytes = _download_audio(audio_url)

        if audio_bytes is None:
            return {
                "success": False,
                "audio_bytes": None,
                "audio_url": audio_url,
                "error": "Failed to download audio from URL"
            }

        return {
            "success": True,
            "audio_bytes": audio_bytes,
            "audio_url": audio_url,
            "error": ""
        }

    except Exception as e:
        return {
            "success": False,
            "audio_bytes": None,
            "audio_url": "",
            "error": f"TTS exception: {str(e)}"
        }


def _download_audio(url: str) -> bytes | None:
    """
    Downloads audio bytes from a URL.
    Returns None if download fails.
    """
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read()
    except Exception as e:
        print(f"Failed to download audio from {url}: {e}")
        return None


def examiner_speak(feedback_text: str) -> dict:
    """
    Convenience function specifically for examiner feedback.
    Uses the Cherry voice and adds a brief examiner introduction.
    """
    return text_to_speech(feedback_text, voice=DEFAULT_VOICE)
