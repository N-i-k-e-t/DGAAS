from fastapi import FastAPI, HTTPException
from . import db
from datetime import datetime

app = FastAPI(title="VayaVia Agent API")

@app.get("/health")
async def health():
    health_data = db.get_latest_health()
    if not health_data:
        return {"status": "unknown", "message": "No health records found"}
    return health_data

@app.get("/stats/today")
async def stats_today():
    try:
        stats = db.get_today_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/leads/latest")
async def latest_leads(limit: int = 50):
    try:
        leads = db.get_latest_leads(limit)
        return leads
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    from . import config
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)
