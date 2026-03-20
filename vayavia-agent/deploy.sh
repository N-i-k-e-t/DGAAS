#!/bin/bash
set -e

echo "=== VayaVia Demand Agent - VPS Deployment ==="
echo "Target: Hostinger KVM 2, Debian 13"
echo ""

# 1. System packages
echo "[1/7] Installing system packages..."
sudo apt update && sudo apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib curl git

# 2. PostgreSQL setup
echo "[2/7] Setting up PostgreSQL..."
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='postgres'" | grep -q 1 || sudo -u postgres createuser -s postgres
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';" 2>/dev/null || true
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='vayavia_agent'" | grep -q 1 || sudo -u postgres createdb vayavia_agent
echo "Running schema migration..."
sudo -u postgres psql -d vayavia_agent -f /opt/vayavia-agent/agent/models.sql

# 3. Clone/update repo
echo "[3/7] Setting up agent code..."
if [ -d /opt/vayavia-agent ]; then
    cd /opt/vayavia-agent && git pull
else
    git clone https://github.com/N-i-k-e-t/DGAAS.git /tmp/dgaas-deploy
    cp -r /tmp/dgaas-deploy/vayavia-agent /opt/vayavia-agent
    rm -rf /tmp/dgaas-deploy
fi

# 4. Python venv
echo "[4/7] Setting up Python environment..."
cd /opt/vayavia-agent
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. Ollama + model
echo "[5/7] Installing Ollama and pulling model..."
if ! command -v ollama &> /dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
fi
systemctl enable ollama
systemctl start ollama
sleep 5
ollama pull qwen2.5:1.5b

# 6. Create .env file
echo "[6/7] Creating environment config..."
cat > /opt/vayavia-agent/.env << 'EOF'
DB_NAME=vayavia_agent
DB_USER=postgres
DB_PASS=postgres
DB_HOST=localhost
DB_PORT=5432
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:1.5b
API_HOST=0.0.0.0
API_PORT=8090
EOF

# 7. Install systemd services
echo "[7/7] Installing systemd services..."
sudo cp /opt/vayavia-agent/systemd/vayavia-api.service /etc/systemd/system/
sudo cp /opt/vayavia-agent/systemd/vayavia-collector.service /etc/systemd/system/
sudo cp /opt/vayavia-agent/systemd/vayavia-classifier.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable vayavia-api vayavia-collector vayavia-classifier
sudo systemctl restart vayavia-api
sudo systemctl restart vayavia-collector
sudo systemctl restart vayavia-classifier

echo ""
echo "=== Deployment Complete ==="
echo "API running on port 8090"
echo "Check: curl http://localhost:8090/api/health"
echo "Services: systemctl status vayavia-api vayavia-collector vayavia-classifier"
