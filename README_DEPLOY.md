
# ui9 + Nikola — Quick Deploy

## Local Test (Linux/Mac/WSL)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py
# open http://127.0.0.1:8000/
```
If you prefer uvicorn directly:
```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

## Windows (PowerShell)
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
py run.py
# open http://127.0.0.1:8000/
```

## Smoke Tests
```bash
curl -s http://127.0.0.1:8000/api/health
curl -s -X POST http://127.0.0.1:8000/api/evm -H "Content-Type: application/json" -d "{"PV":100,"EV":120,"AC":110}"
curl -s -X POST http://127.0.0.1:8000/api/boq/total -H "Content-Type: application/json" -d "{"items":[{"item":"Excavation","qty":120,"unit_price":15},{"item":"Concrete","qty":30,"unit_price":220},{"item":"Rebar","qty":1.8,"unit_price":2800}]}"
```

## Production (Ubuntu + Nginx, no Docker)
Create systemd service and Nginx reverse proxy (see chat instructions). Then:
```bash
sudo systemctl restart ui9
```

## Common Gotchas
- **Opened HTML from file://** → لن يعمل. يجب تشغيل الخادم ثم فتح الرابط http://127.0.0.1:8000/ (الواجهة تُقدَّم من نفس الخادم).
- **Port 8000 محجوز** → استخدم منفذًا آخر في run.py أو uvicorn.
- **جدار ناري/شركة** → اسمح بالمنفذ أو استخدم 127.0.0.1 محليًا.
