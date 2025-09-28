
from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict
import math, datetime

app = FastAPI(title="ui9 — Nikola Demo", version="0.1.0")

# CORS for local file testing (optional)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static UI
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

class ChatRequest(BaseModel):
    message: str = Field(..., description="User message in Arabic or English")

class ChatResponse(BaseModel):
    engine: Literal["Nikola"]
    reply: str
    intents: List[str] = []

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    q = (req.message or "").strip()

    intents = []
    # very small intent parsing
    if any(k in q for k in ["SPI","CPI","EVM","PV","EV","AC","سباي","سي بي آي"]):
        intents.append("evm")
    if "boq" in q.lower() or "بي او كيو" in q or "جدول كميات" in q:
        intents.append("boq")
    if any(k in q for k in ["مرحبا","مرحبًا","السلام","اهلين","كيفك","hello","hi"]):
        intents.append("smalltalk")

    # rule-based replies (stub for Nikola core)
    if not q:
        return ChatResponse(engine="Nikola", reply="اكتب سؤالك أو اطلب حسابات EVM أو BoQ.", intents=intents)
    if "كيفك" in q:
        return ChatResponse(engine="Nikola", reply="تمام وبشتغل. اسألني عن SPI/CPI أو الصق BoQ.", intents=intents)
    if "اسمك" in q or "who are you" in q.lower():
        return ChatResponse(engine="Nikola", reply="أنا نيكولا داخل ui9 — نسخة تجريبية تعمل محليًا.", intents=intents)

    # simple arithmetic
    import re
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*([+\-×x*/])\s*(-?\d+(?:\.\d+)?)", q)
    if m:
        a=float(m.group(1)); op=m.group(2); b=float(m.group(3))
        if op in ['x','×']: op='*'
        if op=='/' and b==0: r="قسمة على صفر غير معرفة."
        else: r=str(eval(f"{a}{op}{b}"))
        return ChatResponse(engine="Nikola", reply=f"النتيجة: {r}", intents=intents)

    # fallback
    return ChatResponse(engine="Nikola", reply="وصلتني رسالتك. اطلب: /api/evm أو /api/boq/total عبر الواجهة.", intents=intents)

class EVMRequest(BaseModel):
    PV: float
    EV: float
    AC: Optional[float] = None

class EVMResponse(BaseModel):
    SPI: float
    CPI: Optional[float] = None
    status: str

@app.post("/api/evm", response_model=EVMResponse)
def evm(req: EVMRequest):
    spi = req.EV / req.PV if req.PV != 0 else math.nan
    cpi = (req.EV / req.AC) if (req.AC is not None and req.AC != 0) else None
    status = "On Track" if spi>=1.0 else "Behind"
    return EVMResponse(SPI=round(spi,3), CPI=(round(cpi,3) if cpi is not None else None), status=status)

class BoQItem(BaseModel):
    item: str
    qty: float
    unit_price: float

class BoQTotalResponse(BaseModel):
    total: float
    breakdown: List[Dict[str, float]]

class BoQRequest(BaseModel):
    items: List[BoQItem]

@app.post("/api/boq/total", response_model=BoQTotalResponse)
def boq_total(req: BoQRequest):
    total = 0.0
    breakdown = []
    for it in req.items:
        cost = it.qty * it.unit_price
        total += cost
        breakdown.append({"item": it.item, "cost": round(cost,2)})
    return BoQTotalResponse(total=round(total,2), breakdown=breakdown)

@app.get("/api/health")
def health():
    return {"status":"ok","engine":"Nikola","time": datetime.datetime.now().isoformat()}

from fastapi.responses import FileResponse
import os

@app.get("/", response_class=FileResponse)
def index():
    return FileResponse(os.path.join("static", "index.html"))
