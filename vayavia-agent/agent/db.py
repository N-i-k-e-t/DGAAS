import psycopg2
from psycopg2.extras import RealDictCursor
from . import config
import hashlib
from datetime import datetime

def get_conn():
    return psycopg2.connect(
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASS,
        host=config.DB_HOST,
        port=config.DB_PORT
    )

def insert_raw_signal(source_site, url, text_snippet):
    url_hash = hashlib.md5(url.encode()).hexdigest()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO raw_signals (source_site, url, url_hash, text_snippet)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (url_hash) DO NOTHING
            """,
            (source_site, url, url_hash, text_snippet)
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

def fetch_unclassified_signals(limit=10):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            "SELECT * FROM raw_signals WHERE classified = FALSE ORDER BY found_at ASC LIMIT %s",
            (limit,)
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

def mark_raw_signal_classified(raw_signal_id):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE raw_signals SET classified = TRUE WHERE id = %s",
            (raw_signal_id,)
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

def insert_signal_and_lead(raw_signal_id, segment, score, urgency, text_snippet, source_url, platform):
    conn = get_conn()
    cur = conn.cursor()
    try:
        # Insert into signals
        cur.execute(
            """
            INSERT INTO signals (raw_signal_id, segment, score, urgency)
            VALUES (%s, %s, %s, %s) RETURNING id
            """,
            (raw_signal_id, segment, score, urgency)
        )
        signal_id = cur.fetchone()[0]

        # Insert into leads if score >= 50
        if score >= 50:
            cur.execute(
                """
                INSERT INTO leads (signal_id, platform, segment, score, urgency, ai_message, original_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (signal_id, platform, segment, score, urgency, text_snippet[:200], source_url)
            )
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

def write_health(collector_ok, classifier_ok, db_ok, errors_last_hour, notes=""):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO agent_health (collector_ok, classifier_ok, db_ok, errors_last_hour, notes)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (collector_ok, classifier_ok, db_ok, errors_last_hour, notes)
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

def get_latest_health():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT * FROM agent_health ORDER BY check_time DESC LIMIT 1")
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()

def get_today_stats():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT 
                (SELECT COUNT(*) FROM signals WHERE created_at >= CURRENT_DATE) as signals_today,
                (SELECT COUNT(*) FROM leads WHERE created_at >= CURRENT_DATE) as leads_today,
                (SELECT COUNT(*) FROM leads WHERE created_at >= CURRENT_DATE AND score >= 70) as hot_leads_today,
                (SELECT segment FROM signals WHERE created_at >= CURRENT_DATE GROUP BY segment ORDER BY COUNT(*) DESC LIMIT 1) as top_segment_today
        """)
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()

def get_latest_leads(limit=50):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT id, segment, score, urgency, status, original_url, created_at FROM leads ORDER BY created_at DESC LIMIT %s", (limit,))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()
