from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import os, requests, asyncio, aiohttp

app = FastAPI()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
EXIT_WORDS = {"done", "finish", "bye", "thank you", "thanks", "no that is all"}

def should_end(text: str) -> bool:
    t = (text or "").lower()
    return any(w in t for w in EXIT_WORDS)

async def fetch_bytes(url: str) -> bytes:
    async with aiohttp.ClientSession() as s:
        async with s.get(url) as r:
            r.raise_for_status()
            return await r.read()

def fetch_sync(url: str) -> bytes:
    return asyncio.get_event_loop().run_until_complete(fetch_bytes(url))

def transcribe_with_groq(url: str) -> str:
    if not GROQ_API_KEY:
        return "(demo: no transcription)"
    files = {"file": ("audio.wav", fetch_sync(url), "audio/wav")}
    data = {"model": "whisper-large-v3"}
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    r = requests.post("https://api.groq.com/openai/v1/audio/transcriptions",
                      headers=headers, data=data, files=files, timeout=60)
    r.raise_for_status()
    return r.json().get("text", "(empty)"

def exoml_say_record(prompt: str, base: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>{prompt}</Say>
  <Record action="{base}/exotel/next" method="POST" maxLength="5" timeout="4" playBeep="true"/>
</Response>"""

def exoml_hangup(msg: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>{msg}</Say>
  <Hangup/>
</Response>"""

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.post("/exotel/start")
async def exotel_start(_: Request):
    base = os.getenv("BASE_URL", "")
    return PlainTextResponse(exoml_say_record("Hello! How can I help you today?", base),
                             media_type="application/xml")

@app.post("/exotel/next")
async def exotel_next(request: Request):
    form = await request.form()
    rec = form.get("RecordingUrl", "")
    text = transcribe_with_groq(rec)
    if should_end(text):
        return PlainTextResponse(exoml_hangup(f"You said: {text}. Goodbye."),
                                 media_type="application/xml")
    base = os.getenv("BASE_URL", "")
    reply = f"You said: {text}. Anything else?"
    return PlainTextResponse(exoml_say_record(reply, base),
                             media_type="application/xml")
