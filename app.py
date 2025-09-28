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
# EVM API
# ----------------------------
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

# ----------------------------
# BoQ JSON
# ----------------------------
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

# ----------------------------
# BoQ CSV Upload
# ----------------------------
@app.post("/api/boq/upload")
async def boq_upload(file: UploadFile = File(...)):
    try:
        content = await file.read()
        df = pd.read_csv(io.BytesIO(content))
        cols = {c.lower(): c for c in df.columns}
        if "qty" not in cols or "unit_price" not in cols:
            raise HTTPException(status_code=422, detail={"error":"InvalidColumns","need":["qty","unit_price"]})
        total = float((df[cols["qty"]] * df[cols["unit_price"]]).sum())
        return {"rows": int(len(df)), "total": round(total, 6)}
    except Exception as ex:
        raise HTTPException(status_code=400, detail={"error":"ParseError","details": str(ex)})

# ----------------------------
# Agent endpoints
# ----------------------------
class PlanReq(BaseModel):
    goal: str

@app.post("/api/agent/plan")
def plan(body: PlanReq):
    g = body.goal.lower()
    if "evm" in g or "earned value" in g: steps = ["parse EVM inputs", "compute EVM", "summarize"]
    elif "boq" in g or "bill of quantities" in g: steps = ["parse BoQ", "sum totals", "summarize"]
    else: steps = ["analyze goal", "choose skill", "execute", "summarize"]
    return {"goal": body.goal, "steps": steps}

class RunReq(BaseModel):
    type: str
    data: Dict[str, Any]

@app.post("/api/agent/run")
def run(body: RunReq):
    t = (body.type or "").lower()
    if t == "evm":
        PV = float(body.data.get("PV", 0)); EV = float(body.data.get("EV", 0))
        AC = float(body.data.get("AC", 0)); BAC = body.data.get("BAC", None)
        CPI = (EV/AC) if AC>0 else None
        SPI = (EV/PV) if PV>0 else None
        EAC = (float(BAC)/CPI) if (BAC is not None and CPI and CPI>0) else None
        ETC = (EAC-AC) if EAC is not None else None
        return {"skill":"evm","result":{"SPI":SPI,"CPI":CPI,"EAC":EAC,"ETC":ETC}}
    if t == "boq":
        items = body.data.get("items", [])
        total = sum((float(i.get("qty",0))*float(i.get("unit_price",0))) for i in items)
        return {"skill":"boq","result":{"total": total}}
    if t == "chat":
        msgs = body.data.get("messages", [])
        return {"skill":"chat","result":{"reply": f"(Stub Agent) استلمت {len(msgs)} رسالة."}}
    return {"error":"unknown_task","hint":"type=evm|boq|chat"}

# ----------------------------
# Memory (SQLite)
# ----------------------------
DB_PATH = os.getenv("NIKOLA_DB","/tmp/nikola.sqlite3")

@app.on_event("startup")
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS kvstore(
        k TEXT PRIMARY KEY, v TEXT NOT NULL, meta TEXT, updated_at TEXT NOT NULL
    )""")
    conn.commit(); conn.close()

class PutReq(BaseModel):
    key: str
    value: Any
    meta: Optional[Dict] = None

@app.post("/api/memory/put")
def mem_put(body: PutReq):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    c.execute("REPLACE INTO kvstore (k,v,meta,updated_at) VALUES (?,?,?,?)",
              (body.key, json.dumps(body.value, ensure_ascii=False),
               json.dumps(body.meta or {}, ensure_ascii=False), ts))
    conn.commit(); conn.close()
    return {"ok": True, "key": body.key, "updated_at": ts}

@app.get("/api/memory/get")
def mem_get(key: str):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT v, meta, updated_at FROM kvstore WHERE k=?",(key,))
    row = c.fetchone(); conn.close()
    if not row: raise HTTPException(status_code=404, detail={"error":"NotFound","key":key})
    v, meta, updated = row
    return {"key": key, "value": json.loads(v), "meta": json.loads(meta or "{}"), "updated_at": updated}