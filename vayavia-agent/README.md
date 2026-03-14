# VayaVia Demand Agent Pilot

A production-ready 24×7 marketing intelligence agent for a Linux VPS. It scrapes social media signals, classifies them using a local Ollama LLM, and exposes an API for n8n.

## 🚀 VPS Installation

### 1. Prerequisites
- **Python 3.9+**
- **PostgreSQL** (running on port 5432)
- **Ollama** (running on port 11434 with `qwen2.5:1.5b` pulled)

### 2. Setup Files
```bash
sudo mkdir -p /opt/vayavia-agent
sudo chown -R $USER:$USER /opt/vayavia-agent
# Sync your code to /opt/vayavia-agent/
```

### 3. Install Dependencies
```bash
cd /opt/vayavia-agent
pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium
```

### 4. Configuration
Create a `.env` file in `/opt/vayavia-agent/`:
```env
DB_NAME=vayavia_agent
DB_USER=postgres
DB_PASS=your_password
DB_HOST=localhost
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:1.5b
```

### 5. Initialize Database
```bash
python scripts/init_db.py
```

## 🛠 Manual Testing
- **Collector**: `python scripts/run_collector_once.py`
- **Classifier**: `python scripts/run_classifier_once.py`
- **API**: `python -m agent.api_service` (Accessible at http://localhost:8000)

## 🔄 Systemd Service Configuration
To run the agent 24/7, install the provided services:
```bash
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vayavia-collector vayavia-classifier vayavia-api
```

## 📊 API Endpoints (For n8n / Dashboard)
- `GET /health`: Agent health and cycle status.
- `GET /stats/today`: Daily aggregation of signals and leads.
- `GET /leads/latest`: Latest 50 hot leads for the dashboard.

---
**Privacy Note**: This pilot uses local processing only. No data leaves the VPS.
