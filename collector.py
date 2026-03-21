#!/usr/bin/env python3
"""VayaVia Demand Engine - Multi-Platform Collector v3.2
Auto-triggering, self-healing daemon. Collects from Reddit, Google News,
Weather (Open-Meteo), Google Trends, Twitter/X (via Nitter), Quora.
Each platform stored SEPARATELY with platform-specific fields.
Stores ALL real data. Runs as systemd daemon with auto error recovery."""
import psycopg2, requests, json, time, re, logging, sys, traceback
from datetime import datetime, timedelta
import feedparser
from urllib.parse import quote_plus
import hashlib
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('/tmp/collector.log')]
)
log = logging.getLogger('collector')

DB = dict(dbname='vayavia_agent', user='postgres', password='postgres', host='localhost')
CYCLE_INTERVAL = 3600
MAX_RETRIES = 3
RETRY_DELAY = 10
MIN_SCORE_LEAD = 30

SUBREDDITS = ['india', 'travel', 'wine', 'IndiaTravelAdvice', 'solotravel', 'digitalnomad', 'nashik', 'maharashtra', 'winery', 'incredibleindia']
RSS_FEEDS = [
    'https://news.google.com/rss/search?q=nashik+wine+tourism&hl=en-IN&gl=IN',
    'https://news.google.com/rss/search?q=nashik+vineyard+visit&hl=en-IN&gl=IN',
    'https://news.google.com/rss/search?q=maharashtra+wine+tourism&hl=en-IN&gl=IN',
    'https://news.google.com/rss/search?q=sula+vineyards+nashik&hl=en-IN&gl=IN',
    'https://news.google.com/rss/search?q=nashik+travel+destination&hl=en-IN&gl=IN',
]

NITTER_INSTANCES = [
    'https://nitter.privacydev.net',
    'https://nitter.poast.org',
    'https://nitter.woodland.cafe',
    'https://nitter.1d4.us',
]
TWITTER_QUERIES = ['nashik wine', 'nashik vineyard', 'sula vineyards', 'nashik tourism', 'wine tourism india']

QUORA_QUERIES = ['nashik+wine+tourism', 'nashik+vineyards+visit', 'wine+tasting+india', 'nashik+travel+guide']

KEYWORDS = ['nashik','wine','vineyard','winery','sula','york','soma','grover','tourism',
            'travel','visit','trip','weekend','getaway','tasting','grape','cellar',
            'maharashtra','india wine','wine tour','wine region']

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def get_db():
    for attempt in range(MAX_RETRIES):
        try:
            conn = psycopg2.connect(**DB)
            conn.autocommit = True
            return conn
        except Exception as e:
            log.warning(f'DB connect attempt {attempt+1} failed: {e}')
            time.sleep(RETRY_DELAY)
    raise Exception('Failed to connect to database')

def make_hash(text):
    return hashlib.md5(text.encode()).hexdigest()[:16]

def score_text(text):
    if not text: return 0
    t = text.lower()
    return sum(2 if kw in t else 0 for kw in KEYWORDS)

def safe_request(url, timeout=15):
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            log.warning(f'Request attempt {attempt+1} failed for {url[:80]}: {e}')
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    return None

def store_signal(conn, platform, title, body, url, score, meta=None):
    sig_hash = make_hash(f'{platform}:{url or title}')
    try:
        cur = conn.cursor()
        cur.execute('SELECT id FROM signals WHERE sig_hash=%s', (sig_hash,))
        if cur.fetchone():
            return False
        cur.execute(
            'INSERT INTO signals (platform, title, body, url, score, sig_hash, meta, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,NOW())',
            (platform, title[:500] if title else '', body[:2000] if body else '', url or '', score, sig_hash, json.dumps(meta or {}))
        )
        return True
    except Exception as e:
        log.error(f'Store signal error: {e}')
        return False

def store_lead(conn, name, source, score, details=None):
    lead_hash = make_hash(f'{source}:{name}')
    try:
        cur = conn.cursor()
        cur.execute('SELECT id FROM leads WHERE lead_hash=%s', (lead_hash,))
        if cur.fetchone():
            return False
        cur.execute(
            'INSERT INTO leads (name, source, score, details, lead_hash, created_at) VALUES (%s,%s,%s,%s,%s,NOW())',
            (name[:300], source, score, json.dumps(details or {}), lead_hash)
        )
        return True
    except Exception as e:
        log.error(f'Store lead error: {e}')
        return False

# --- REDDIT COLLECTOR ---
def collect_reddit(conn):
    raw, stored = 0, 0
    for sub in SUBREDDITS:
        try:
            url = f'https://www.reddit.com/r/{sub}/search.json?q=nashik+OR+wine+OR+vineyard+OR+sula+OR+tourism&sort=new&t=week&limit=25'
            r = safe_request(url)
            if not r: continue
            data = r.json()
            posts = data.get('data', {}).get('children', [])
            for post in posts:
                d = post.get('data', {})
                title = d.get('title', '')
                body = d.get('selftext', '')
                text = f'{title} {body}'
                sc = score_text(text)
                raw += 1
                meta = {
                    'subreddit': d.get('subreddit', ''),
                    'author': d.get('author', ''),
                    'upvotes': d.get('ups', 0),
                    'comments': d.get('num_comments', 0),
                    'created_utc': d.get('created_utc', 0),
                }
                purl = f"https://reddit.com{d.get('permalink', '')}"
                if store_signal(conn, 'reddit', title, body, purl, sc, meta):
                    stored += 1
                if sc >= MIN_SCORE_LEAD and d.get('author') not in ['[deleted]','AutoModerator']:
                    store_lead(conn, d.get('author',''), 'reddit', sc, {'post_title': title, 'subreddit': sub})
            time.sleep(2)
        except Exception as e:
            log.error(f'Reddit r/{sub} error: {e}')
    log.info(f'Reddit: {raw} raw, {stored} stored')
    return raw, stored

# --- GOOGLE NEWS COLLECTOR ---
def collect_google_news(conn):
    raw, stored = 0, 0
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:20]:
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                link = entry.get('link', '')
                text = f'{title} {summary}'
                sc = score_text(text)
                raw += 1
                pub = entry.get('published', '')
                meta = {'source': entry.get('source', {}).get('title', ''), 'published': pub}
                if store_signal(conn, 'google_news', title, summary, link, sc, meta):
                    stored += 1
            time.sleep(1)
        except Exception as e:
            log.error(f'Google News feed error: {e}')
    log.info(f'Google News: {raw} raw, {stored} stored')
    return raw, stored

# --- WEATHER COLLECTOR ---
def collect_weather(conn):
    raw, stored = 0, 0
    try:
        url = 'https://api.open-meteo.com/v1/forecast?latitude=19.9975&longitude=73.7898&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code&timezone=Asia/Kolkata&forecast_days=7'
        r = safe_request(url)
        if r:
            data = r.json()
            current = data.get('current', {})
            daily = data.get('daily', {})
            temp = current.get('temperature_2m', 0)
            humidity = current.get('relative_humidity_2m', 0)
            weather_code = current.get('weather_code', 0)
            conditions = {0:'Clear',1:'Mainly clear',2:'Partly cloudy',3:'Overcast',
                         45:'Foggy',51:'Light drizzle',61:'Slight rain',63:'Moderate rain',
                         65:'Heavy rain',80:'Slight showers',95:'Thunderstorm'}
            condition = conditions.get(weather_code, f'Code {weather_code}')
            is_good = weather_code <= 3 and 15 <= temp <= 35
            score = 8 if is_good else 3
            title = f'Nashik Weather: {temp}C, {condition}'
            body = f'Humidity: {humidity}%. '
            if daily.get('time'):
                forecasts = []
                for i, day in enumerate(daily['time'][:7]):
                    tmax = daily['temperature_2m_max'][i] if daily.get('temperature_2m_max') else '?'
                    tmin = daily['temperature_2m_min'][i] if daily.get('temperature_2m_min') else '?'
                    rain = daily['precipitation_sum'][i] if daily.get('precipitation_sum') else 0
                    forecasts.append(f'{day}: {tmin}-{tmax}C, rain:{rain}mm')
                body += ' | '.join(forecasts)
            meta = {'temp': temp, 'humidity': humidity, 'condition': condition, 'tourism_friendly': is_good}
            raw += 1
            if store_signal(conn, 'weather', title, body, '', score, meta):
                stored += 1
    except Exception as e:
        log.error(f'Weather error: {e}')
    log.info(f'Weather: {raw} raw, {stored} stored')
    return raw, stored

# --- GOOGLE TRENDS COLLECTOR ---
def collect_trends(conn):
    raw, stored = 0, 0
    queries = ['nashik wine', 'nashik tourism', 'sula vineyards', 'wine tasting india', 'nashik vineyard visit']
    for q in queries:
        try:
            url = f'https://trends.google.com/trends/api/autocomplete/{quote_plus(q)}?hl=en-IN'
            r = safe_request(url)
            if not r: continue
            text = r.text
            if text.startswith(')]}'): text = text[4:]
            data = json.loads(text)
            topics = data.get('default', {}).get('topics', [])
            for topic in topics[:5]:
                title = topic.get('title', '')
                topic_type = topic.get('type', '')
                mid = topic.get('mid', '')
                sc = score_text(title) + 4
                raw += 1
                meta = {'query': q, 'type': topic_type, 'mid': mid}
                if store_signal(conn, 'google_trends', f'Trend: {title}', f'Related to: {q}. Type: {topic_type}', f'https://trends.google.com/trends/explore?q={quote_plus(q)}', sc, meta):
                    stored += 1
            time.sleep(1)
        except Exception as e:
            log.error(f'Trends error for {q}: {e}')
    log.info(f'Google Trends: {raw} raw, {stored} stored')
    return raw, stored

# --- TWITTER/X COLLECTOR (via Nitter) ---
def collect_twitter(conn):
    raw, stored = 0, 0
    for query in TWITTER_QUERIES:
        for nitter_url in NITTER_INSTANCES:
            try:
                search_url = f'{nitter_url}/search?f=tweets&q={quote_plus(query)}'
                r = safe_request(search_url, timeout=10)
                if not r or r.status_code != 200: continue
                soup = BeautifulSoup(r.text, 'html.parser')
                tweets = soup.select('.timeline-item, .tweet-body')
                if not tweets:
                    tweets = soup.select('[class*="tweet"]')
                for tweet in tweets[:10]:
                    content_el = tweet.select_one('.tweet-content, .tweet-body, p')
                    if not content_el: continue
                    content = content_el.get_text(strip=True)
                    if not content: continue
                    user_el = tweet.select_one('.username, .tweet-header a')
                    username = user_el.get_text(strip=True) if user_el else 'unknown'
                    link_el = tweet.select_one('a[href*="/status/"]')
                    tweet_url = f'{nitter_url}{link_el["href"]}' if link_el and link_el.get('href') else ''
                    sc = score_text(content)
                    raw += 1
                    meta = {'username': username, 'nitter_instance': nitter_url, 'query': query}
                    if store_signal(conn, 'twitter', content[:200], content, tweet_url, sc, meta):
                        stored += 1
                    if sc >= MIN_SCORE_LEAD and username != 'unknown':
                        store_lead(conn, username, 'twitter', sc, {'tweet': content[:200], 'query': query})
                if stored > 0 or raw > 0:
                    break
                time.sleep(2)
            except Exception as e:
                log.warning(f'Nitter {nitter_url} failed for {query}: {e}')
                continue
        time.sleep(1)
    log.info(f'Twitter/X: {raw} raw, {stored} stored')
    return raw, stored

# --- QUORA COLLECTOR ---
def collect_quora(conn):
    raw, stored = 0, 0
    for query in QUORA_QUERIES:
        try:
            url = f'https://www.quora.com/search?q={query}'
            r = safe_request(url, timeout=10)
            if not r: continue
            soup = BeautifulSoup(r.text, 'html.parser')
            questions = soup.select('a[href*="/"]')
            seen = set()
            for q_el in questions:
                text = q_el.get_text(strip=True)
                href = q_el.get('href', '')
                if len(text) < 20 or len(text) > 500: continue
                if text in seen: continue
                kw_count = sum(1 for kw in KEYWORDS if kw.lower() in text.lower())
                if kw_count == 0: continue
                seen.add(text)
                sc = score_text(text)
                raw += 1
                q_url = f'https://www.quora.com{href}' if href.startswith('/') else href
                meta = {'search_query': query}
                if store_signal(conn, 'quora', text, '', q_url, sc, meta):
                    stored += 1
            time.sleep(2)
        except Exception as e:
            log.error(f'Quora error for {query}: {e}')
    log.info(f'Quora: {raw} raw, {stored} stored')
    return raw, stored

# --- INSIGHTS GENERATION ---
def generate_insights(conn, total_raw, total_stored, total_leads, platform_data):
    try:
        cur = conn.cursor()
        platforms_json = json.dumps(platform_data)
        top_segment = 'wine tourism enthusiasts'
        top_action = 'Target Reddit wine/travel communities and Google News trending topics'
        
        # Weather summary
        cur.execute("SELECT title, meta FROM signals WHERE platform='weather' ORDER BY created_at DESC LIMIT 1")
        weather_row = cur.fetchone()
        weather_summary = weather_row[0] if weather_row else 'No weather data'
        
        # Trend summary
        cur.execute("SELECT title FROM signals WHERE platform='google_trends' ORDER BY created_at DESC LIMIT 5")
        trend_rows = cur.fetchall()
        trend_summary = '; '.join([r[0] for r in trend_rows]) if trend_rows else 'No trends data'
        
        # Top signal
        cur.execute("SELECT platform, title, score FROM signals ORDER BY score DESC LIMIT 1")
        top_row = cur.fetchone()
        top_signal = f'{top_row[0]}: {top_row[1]} (score:{top_row[2]})' if top_row else 'None'
        
        insight_text = f'Cycle completed. Top signal: {top_signal}. Weather: {weather_summary}. Trends: {trend_summary[:300]}'
        
        cur.execute(
            """INSERT INTO cycle_insights (cycle_time, total_raw, total_stored, total_leads,
            platforms_data, top_segment, top_action, weather_summary, trend_summary, insight_text)
            VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (total_raw, total_stored, total_leads, platforms_json, top_segment, top_action,
             weather_summary, trend_summary[:500], insight_text[:1000])
        )
        log.info(f'Insights saved: {total_raw} raw, {total_stored} stored, {total_leads} leads')
    except Exception as e:
        log.error(f'Insights error: {e}')

# --- MAIN CYCLE ---
def run_cycle():
    log.info('=== CYCLE START ===')
    conn = get_db()
    total_raw, total_stored, total_leads = 0, 0, 0
    platform_data = {}
    
    collectors = [
        ('reddit', collect_reddit),
        ('google_news', collect_google_news),
        ('weather', collect_weather),
        ('google_trends', collect_trends),
        ('twitter', collect_twitter),
        ('quora', collect_quora),
    ]
    
    for name, func in collectors:
        try:
            raw, stored = func(conn)
            platform_data[name] = {'raw': raw, 'stored': stored}
            total_raw += raw
            total_stored += stored
        except Exception as e:
            log.error(f'Collector {name} failed: {e}\n{traceback.format_exc()}')
            platform_data[name] = {'raw': 0, 'stored': 0, 'error': str(e)}
    
    # Count leads
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM leads WHERE created_at > NOW() - INTERVAL '1 hour'")
        total_leads = cur.fetchone()[0]
    except: pass
    
    generate_insights(conn, total_raw, total_stored, total_leads, platform_data)
    conn.close()
    
    log.info(f'=== CYCLE DONE: {total_raw} raw -> {total_stored} signals, {total_leads} leads ===')
    return total_raw, total_stored

# --- DAEMON ---
def main():
    log.info('VayaVia Collector v3.2 starting as daemon...')
    while True:
        try:
            run_cycle()
        except Exception as e:
            log.error(f'Cycle error: {e}\n{traceback.format_exc()}')
        log.info(f'Sleeping {CYCLE_INTERVAL}s until next cycle...')
        time.sleep(CYCLE_INTERVAL)

if __name__ == '__main__':
    main()
