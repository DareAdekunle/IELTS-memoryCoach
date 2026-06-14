import os
import dashscope
import urllib.request
from dotenv import load_dotenv

load_dotenv()

dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"

print("Testing TTS — downloading from URL...")

response = dashscope.audio.qwen_tts.SpeechSynthesizer.call(
    model="qwen3-tts-flash",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    text="Hello, this is your IELTS examiner. Your speaking response was excellent. You demonstrated a wide range of vocabulary and your ideas were well developed.",
    voice="Cherry",
)

if response.status_code == 200:
    audio = response.output.get("audio", {})
    audio_url = audio.get("url", "")

    print(f"Audio URL: {audio_url[:80]}...")

    if audio_url:
        # Download the wav file from the URL
        output_path = "test_tts_final.wav"
        urllib.request.urlretrieve(audio_url, output_path)
        print(f"✅ Downloaded and saved to {output_path}")
        print("Open test_tts_final.wav in your music player to hear Cherry speak!")
    else:
        print("❌ No URL in response")
else:
    print(f"❌ Failed: {response.message}")