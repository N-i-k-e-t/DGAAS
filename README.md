# VayaVia Demand Engine

VayaVia Demand Engine is a high-performance marketing intelligence platform for the hospitality and tourism sector, focused on Nashik. It acts as an AI-driven command center connecting real-world data (weather, pollution, trends) to automated marketing actions.

## 🚀 Quick Start

### 1. Local Development
```bash
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) to view the app.

### 2. Live Deployment (Vercel)
This app is optimized for Vercel. To deploy:
1. Push this repo to GitHub.
2. Connect the repo to Vercel.
3. Configure the following **Environment Variables** in Vercel:
   - `VITE_N8N_CAMPAIGN_WEBHOOK`: Your n8n campaign trigger URL.
   - `VITE_N8N_LEADS_WEBHOOK`: Your n8n lead feedback URL.
   - `VITE_N8N_BASE_URL`: (Optional) Base URL for n8n API.

## 🧠 Core Pillar Modules

- **Demand Intelligence ("Brain")**: Real-time signal tracking and intent scoring.
- **Scenario Automation ("Action")**: Automated campaign triggering via n8n.
- **Data Hub & CRM ("Foundation")**: Local-first database (Dexie.js) mirroring Excel data for instant access and CSV import.

## 🛠 Tech Stack

- **Frontend**: React + TypeScript + Vite
- **Styling**: Tailwind CSS + Framer Motion
- **Database**: Dexie.js (IndexedDB)
- **Automation**: n8n Webhooks

## 📂 Project Structure

- `src/pages/`: Main application routes (Dashboard, Leads, Signals, etc.)
- `src/components/`: Reusable UI components categorized by module.
- `src/db/`: Dexie.js database schema and seeding logic.
- `src/lib/`: Client libraries for n8n and CSV processing.

## 📄 License
Private/Proprietary for VayaVia Nashik.
