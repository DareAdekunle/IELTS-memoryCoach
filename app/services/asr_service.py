import os
import sys
import base64
import tempfile

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import dashscope
from dotenv import load_dotenv

load_dotenv()

dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"

ASR_MODEL = "qwen3-asr-flash"


def transcribe_audio_bytes(audio_bytes: bytes, audio_format: str = "wav") -> dict:
    """
    Transcribes audio bytes to text using Qwen ASR.

    Accepts raw audio bytes (from browser recording or file upload)
    and returns the transcribed text.

    Steps:
    1. Convert bytes to base64 data URI
    2. Send to Qwen ASR via MultiModalConversation
    3. Extract and return transcription text

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
        # This is how we send local audio to the API
        b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
        data_uri = f"data:audio/{audio_format};base64,{b64_audio}"

        messages = [
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

        response = dashscope.MultiModalConversation.call(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            model=ASR_MODEL,
            messages=messages,
            result_format="message",
            asr_options={
                "enable_lid": True,
                "enable_itn": False
            }
        )

        if response.status_code != 200:
            return {
                "success": False,
                "text": "",
                "language": "",
                "error": f"ASR API error: {response.message}"
            }

        # Extract transcription from response
        content = response.output.choices[0].message.content
        transcription = ""
        for item in content:
            if "text" in item:
                transcription += item["text"]

        # Extract detected language
        language = "en"
        annotations = response.output.choices[0].message.get("annotations", [])
        for ann in annotations:
            if "language" in ann:
                language = ann["language"]
                break

        return {
            "success": True,
            "text": transcription.strip(),
            "language": language,
            "error": ""
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
        # Detect format from extension
        ext = os.path.splitext(file_path)[1].lower().strip(".")
        if ext not in ["wav", "mp3", "m4a", "webm", "ogg"]:
            ext = "wav"  # default

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

    Streamlit's file uploader returns a special object.
    This function handles reading bytes from it and
    detecting the format from the filename.
    """
    try:
        # Get the file extension
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
            fmt = "wav"  # default fallback

        audio_bytes = uploaded_file.read()
        return transcribe_audio_bytes(audio_bytes, audio_format=fmt)

    except Exception as e:
        return {
            "success": False,
            "text": "",
            "language": "",
            "error": f"Could not process uploaded file: {str(e)}"
        }
