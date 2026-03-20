from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from . import db
from datetime import datetime

app = FastAPI(title="VayaVia Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    try:
        health_data = db.get_latest_health()
        stats = db.get_today_stats()
        return {
            "status": "healthy" if health_data else "unknown",
            "db_ok": True,
            "signals": stats.get("signals_today", 0) if stats else 0,
            "leads": stats.get("leads_today", 0) if stats else 0,
        }
    except Exception as e:
        return {"status": "error", "db_ok": False, "signals": 0, "leads": 0}

@app.get("/api/stats")
async def stats():
    try:
        data = db.get_full_stats()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/signals")
async def signals(limit: int = Query(50)):
    try:
        result = db.get_latest_signals(limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/leads")
async def leads(limit: int = Query(50)):
    try:
        result = db.get_latest_leads(limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    from . import config
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)
