-- SQL schema for VayaVia Agent PostgreSQL tables

CREATE TABLE IF NOT EXISTS raw_signals (
  id SERIAL PRIMARY KEY,
  source_site TEXT NOT NULL,
  url TEXT NOT NULL,
  url_hash TEXT NOT NULL UNIQUE,
  text_snippet TEXT NOT NULL,
  found_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
  classified BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS signals (
  id SERIAL PRIMARY KEY,
  raw_signal_id INTEGER REFERENCES raw_signals(id),
  segment TEXT,
  score INTEGER,
  urgency TEXT,
  created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS leads (
  id SERIAL PRIMARY KEY,
  signal_id INTEGER REFERENCES signals(id),
  platform TEXT,
  handle TEXT,
  segment TEXT,
  score INTEGER,
  urgency TEXT,
  status TEXT DEFAULT 'new',
  ai_message TEXT,
  original_url TEXT,
  created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_health (
  id SERIAL PRIMARY KEY,
  check_time TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
  collector_ok BOOLEAN,
  classifier_ok BOOLEAN,
  db_ok BOOLEAN,
  errors_last_hour INTEGER,
  notes TEXT
);

-- Index for performance
CREATE INDEX IF NOT EXISTS idx_raw_signals_classified ON raw_signals(classified);
CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
