import os
import sys
import base64
import requests
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from dotenv import load_dotenv
load_dotenv()

# ─── ASR Configuration ────────────────────────────────────────────────────────
# Route through Model Studio workspace DashScope-native endpoint (HTTP).
# The old code used dashscope-intl.aliyuncs.com which rejects sk-ws- keys.
#
# IMPORTANT: DashScope-native endpoint is /api/v1, NOT /compatible-mode/v1.
ASR_MODEL   = "qwen3-asr-flash"
ASR_API_KEY = os.getenv("DASHSCOPE_API_KEY")

# Build workspace DashScope-native URL from MODEL_STUDIO_ENDPOINT
_model_studio = os.getenv(
    "MODEL_STUDIO_ENDPOINT",
    "https://ws-65ggehps6g6aqox2.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
)
_workspace_base = _model_studio.replace("/compatible-mode/v1", "")
ASR_URL = f"{_workspace_base}/api/v1/services/aigc/multimodal-generation/generation"

print(f"ASR configured: {ASR_MODEL} via {ASR_URL}")


def transcribe_audio_bytes(audio_bytes: bytes, audio_format: str = "wav") -> dict:
    """
    Transcribes audio bytes to text using Qwen ASR via HTTP POST
    to the DashScope-native multimodal-generation endpoint.

    Replaces the old dashscope.MultiModalConversation.call() approach
    which pointed at dashscope-intl.aliyuncs.com — that endpoint
    rejects sk-ws- workspace keys.

    Returns a dict with:
    - success (bool)
    - text (str) — the transcription
    - language (str) — detected language
    - error (str) — error message if failed
    """
    if not audio_bytes:
        return {
            "success": False,
            "text": "",
            "language": "",
            "error": "No audio data received"
        }

    try:
        # Convert bytes to base64 data URI
        b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
        data_uri = f"data:audio/{audio_format};base64,{b64_audio}"

        headers = {
            "Authorization": f"Bearer {ASR_API_KEY}",
            "Content-Type": "application/json",
        }

        # DashScope-native multimodal format
        payload = {
            "model": ASR_MODEL,
            "input": {
                "messages": [
                    {
                        "role": "system",
                        "content": [
                            {
                                "text": (
                                    "You are transcribing IELTS speaking practice responses. "
                                    "Transcribe exactly what is said in English. "
                                    "Do not translate. Do not summarise. "
                                    "Return the exact words spoken."
                                )
                            }
                        ]
                    },
                    {
                        "role": "user",
                        "content": [
                            {"audio": data_uri}
                        ]
                    }
                ]
            },
            "parameters": {
                "result_format": "message"
            }
        }

        print(f"ASR HTTP request → {ASR_URL} "
              f"(model={ASR_MODEL}, audio={len(audio_bytes)} bytes, format={audio_format})")

        response = requests.post(ASR_URL, json=payload, headers=headers, timeout=60)

        if response.status_code != 200:
            error_detail = response.text[:500]
            print(f"ASR HTTP error {response.status_code}: {error_detail}")
            return {
                "success": False,
                "text": "",
                "language": "",
                "error": f"ASR API error {response.status_code}: {error_detail}"
            }

        data = response.json()

        # Extract transcription from DashScope response:
        # {"output": {"choices": [{"message": {"content": [{"text": "..."}]}}]}}
        transcription = ""
        try:
            content = data["output"]["choices"][0]["message"]["content"]
            for item in content:
                if "text" in item:
                    transcription += item["text"]
        except (KeyError, IndexError) as e:
            print(f"ASR response parsing error: {e}")
            print(f"ASR raw response: {json.dumps(data)[:500]}")
            return {
                "success": False,
                "text": "",
                "language": "",
                "error": f"Could not parse ASR response: {e}"
            }

        # Extract detected language if available
        language = "en"
        try:
            annotations = data["output"]["choices"][0]["message"].get("annotations", [])
            for ann in annotations:
                if "language" in ann:
                    language = ann["language"]
                    break
        except (KeyError, IndexError):
            pass

        print(f"ASR success: transcribed {len(transcription)} chars")
        return {
            "success": True,
            "text": transcription.strip(),
            "language": language,
            "error": ""
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "text": "",
            "language": "",
            "error": "ASR request timed out (60s)"
        }
    except Exception as e:
        return {
            "success": False,
            "text": "",
            "language": "",
            "error": f"ASR exception: {str(e)}"
        }


def transcribe_audio_file(file_path: str) -> dict:
    """
    Transcribes an audio file at a given path.
    Reads the file and calls transcribe_audio_bytes.
    """
    try:
        ext = os.path.splitext(file_path)[1].lower().strip(".")
        if ext not in ["wav", "mp3", "m4a", "webm", "ogg"]:
            ext = "wav"

        with open(file_path, "rb") as f:
            audio_bytes = f.read()

        return transcribe_audio_bytes(audio_bytes, audio_format=ext)
    except Exception as e:
        return {
            "success": False,
            "text": "",
            "language": "",
            "error": f"Could not read audio file: {str(e)}"
        }


def transcribe_uploaded_file(uploaded_file) -> dict:
    """
    Transcribes a Streamlit uploaded file object.
    Handles reading bytes and detecting format from filename.
    """
    try:
        filename = uploaded_file.name.lower()
        if filename.endswith(".wav"):
            fmt = "wav"
        elif filename.endswith(".mp3"):
            fmt = "mp3"
        elif filename.endswith(".m4a"):
            fmt = "m4a"
        elif filename.endswith(".webm"):
            fmt = "webm"
        elif filename.endswith(".ogg"):
            fmt = "ogg"
        else:
            fmt = "wav"

        audio_bytes = uploaded_file.read()

        return transcribe_audio_bytes(audio_bytes, audio_format=fmt)
    except Exception as e:
        return {
            "success": False,
            "text": "",
            "language": "",
            "error": f"Could not process uploaded file: {str(e)}"
        }
