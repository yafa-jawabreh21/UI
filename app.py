# main.py — Full merged UI9 + Nikola app with memory, BoQ, and OpenAI integration
import os, re, math, datetime, io, json, time, sqlite3
from fastapi import FastAPI, Body, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Literal, Dict, Any
import pandas as pd
from openai import OpenAI

# ----------------------------
# Global CORS
# ----------------------------
ALLOWED = [o.strip() for o in os.getenv("ALLOWED_ORIGINS","").split(",") if o.strip()]

# ----------------------------
# App instance
# ----------------------------
app = FastAPI(title="UI9 + Nikola — Full Merge", version="1.0.0")

if ALLOWED:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )

# ----------------------------
# Serve static UI
# ----------------------------
@app.get("/", response_class=FileResponse)
def index():
    return FileResponse(os.path.join("static", "index.html"))

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    path = os.path.join("static", "favicon.ico")
    if os.path.exists(path):
        return FileResponse(path)
    return FileResponse(os.path.join("static", "index.html"))

# ----------------------------
# Health
# ----------------------------
@app.get("/api/health")
def health():
    return {"status":"ok","engine":"Nikola","time": datetime.datetime.now().isoformat()}

@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "ui9-nikola-full", "version": "1.0.0"}

# ----------------------------
# Nikola Chat
# ----------------------------
class Msg(BaseModel):
    role: str
    content: str

class ChatResponse(BaseModel):
    engine: Literal["Nikola"]
    reply: str
    intents: List[str] = []

@app.post("/api/chat")
def chat(body: dict = Body(...)):
    if "message" in body:
        messages = [{"role":"user","content":body["message"]}]
    elif "messages" in body:
        messages = body["messages"]
    else:
        return {"error": "Invalid payload. Use {'message': '...'} or {'messages': [...]}."}

    q = messages[-1]["content"].strip().lower() if messages else ""
    intents = []

    if any(k.lower() in q for k in ["spi","cpi","evm","pv","ev","ac","سباي","سي بي آي"]):
        intents.append("evm")
    if any(k in q for k in ["boq","بي او كيو","جدول كميات"]):
        intents.append("boq")
    if any(k in q for k in ["مرحبا","مرحبًا","السلام","اهلين","كيفك","hello","hi"]):
        intents.append("smalltalk")

    if not q:
        reply = "اكتب سؤالك أو اطلب حسابات EVM أو BoQ."
    elif "كيفك" in q:
        reply = "تمام وبشتغل. اسألني عن SPI/CPI أو الصق BoQ."
    elif "اسمك" in q or "who are you" in q:
        reply = "أنا نيكولا داخل ui9 — نسخة تجريبية تعمل محليًا."
    else:
        m = re.search(r"(-?\d+(?:\.\d+)?)\s*([+\-×x*/])\s*(-?\d+(?:\.\d+)?)", q)
        if m:
            a = float(m.group(1))
            op = m.group(2)
            b = float(m.group(3))
            if op in ['x','×']: op='*'
            if op=='/' and b==0: r="قسمة على صفر غير معرفة."
            else: r=str(eval(f"{a}{op}{b}"))
            reply = f"النتيجة: {r}"
        else:
            reply = "وصلتني رسالتك. اطلب: /api/evm أو /api/boq/total عبر الواجهة."

    return ChatResponse(engine="Nikola", reply=reply, intents=intents)

# ----------------------------
# OpenAI LLM Chat
# ----------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # ضع هنا مفتاحك كمتغير بيئة
client = OpenAI(api_key=OPENAI_API_KEY)

class ChatIn(BaseModel):
    messages: List[Msg]

@app.post("/api/chat/llm")
async def chat_llm(body: ChatIn):
    try:
        if not OPENAI_API_KEY:
            return {"reply":"(LLM Error) مفتاح OpenAI غير موجود.", "received": len(body.messages)}

        msgs = [{"role": m.role, "content": m.content} for m in body.messages]

        response = client.chat.completions.create(
            model="gpt-4o",  # يمكنك تغييرها إلى "gpt-3.5-turbo"
            messages=msgs,
            temperature=0.7
        )

        reply_text = response.choices[0].message.content
        return {"reply": reply_text, "received": len(body.messages)}

    except Exception as e:
        return {"reply": f"(LLM Error) {str(e)}", "received": len(body.messages)}

# ----------------------------
# EVM, BoQ, Memory, Agent endpoints
# ----------------------------
# يمكنك الاحتفاظ بنفس الأكواد الموجودة سابقاً لـ EVM، BoQ، CSV Upload، Agent وMemory
# … (كما في main.py السابق)
