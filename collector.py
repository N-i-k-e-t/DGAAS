#!/usr/bin/env python3
"""VayaVia Demand Engine - Multi-Platform Collector v3.1
Auto-triggering, self-healing daemon. Collects from Reddit, Google News,
Weather (Open-Meteo), Google Trends. Each platform stored SEPARATELY
with platform-specific fields. Includes utilization layer for insights.
Stores ALL real data. Runs as systemd daemon with auto error recovery."""
import psycopg2, requests, json, time, re, logging, sys, traceback
from datetime import datetime, timedelta
import feedparser
from urllib.parse import quote_plus
import hashlib

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

SUBREDDITS = ['india', 'travel', 'wine', 'IndiaTravelAdvice', 'solotravel', 'digitalnomad', 'nashik', 'maharashtra', 'winemaking']
RSS_FEEDS = [
    'https://news.google.com/rss/search?q=nashik+wine+tourism&hl=en-IN&gl=IN',
    'https://news.google.com/rss/search?q=indian+winery+vineyard&hl=en-IN&gl=IN',
    'https://news.google.com/rss/search?q=nashik+travel+weekend&hl=en-IN&gl=IN',
    'https://news.google.com/rss/search?q=sula+vineyards+york+winery&hl=en-IN&gl=IN',
    'https://news.google.com/rss/search?q=wine+tourism+india&hl=en-IN&gl=IN',
]
SEARCH_KEYWORDS = [
    'nashik wine', 'nashik vineyard', 'nashik tourism', 'nashik weekend',
    'sula vineyards', 'york winery', 'wine tasting india',
    'nashik winery visit', 'maharashtra wine', 'grover zampa nashik',
]
HIGH_KW = ['nashik', 'wine', 'vineyard', 'winery', 'sula', 'york', 'grover', 'zampa', 'tasting', 'sommelier']
MED_KW = ['tourism', 'travel', 'weekend', 'getaway', 'maharashtra', 'resort', 'hotel', 'booking', 'trip', 'visit', 'cellar']
LOW_KW = ['india', 'holiday', 'experience', 'food', 'drink', 'luxury', 'retreat', 'adventure', 'explore']

SEGMENTS = {
    'Wine Enthusiast': ['wine', 'vineyard', 'winery', 'tasting', 'sommelier', 'cellar', 'grape', 'vintage'],
    'Weekend Getaway': ['weekend', 'getaway', 'trip', 'short break', 'escape', 'road trip'],
    'Luxury Seeker': ['luxury', 'premium', 'resort', 'spa', '5 star', 'boutique'],
    'Adventure Tourist': ['adventure', 'trek', 'hike', 'explore', 'backpack', 'outdoor'],
    'Corporate Group': ['corporate', 'team building', 'offsite', 'retreat', 'conference'],
    'Foodie': ['food', 'culinary', 'restaurant', 'dine', 'cuisine', 'gastronomy'],
    'Culture Explorer': ['culture', 'heritage', 'history', 'temple', 'festival', 'art'],
    'General Tourist': ['tourism', 'travel', 'visit', 'holiday', 'vacation'],
}

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
SESSION = requests.Session()
SESSION.headers.update({'User-Agent': UA})

# ============ DATABASE ============
def get_conn():
    for attempt in range(MAX_RETRIES):
        try:
            conn = psycopg2.connect(**DB)
            conn.autocommit = False
            return conn
        except Exception as e:
            log.warning(f'DB connect attempt {attempt+1} failed: {e}')
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
    raise Exception('Cannot connect to database after retries')

def ensure_tables():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS raw_signals (
        id SERIAL PRIMARY KEY, source_site TEXT, url TEXT UNIQUE, text_snippet TEXT,
        platform TEXT, author TEXT DEFAULT '', author_followers INT DEFAULT 0,
        engagement_likes INT DEFAULT 0, engagement_comments INT DEFAULT 0,
        engagement_shares INT DEFAULT 0, hashtags TEXT DEFAULT '',
        location TEXT DEFAULT '', collected_at TIMESTAMP DEFAULT NOW())''')
    cur.execute('''CREATE TABLE IF NOT EXISTS signals (
        id SERIAL PRIMARY KEY, raw_signal_id INT REFERENCES raw_signals(id),
        segment TEXT, score INT, urgency TEXT, created_at TIMESTAMP DEFAULT NOW())''')
    cur.execute('''CREATE TABLE IF NOT EXISTS leads (
        id SERIAL PRIMARY KEY, signal_id INT REFERENCES signals(id),
        segment TEXT, score INT, urgency TEXT, platform TEXT, handle TEXT,
        likes INT DEFAULT 0, comments INT DEFAULT 0, shares INT DEFAULT 0,
        hashtags TEXT DEFAULT '', followers INT DEFAULT 0, location TEXT DEFAULT '',
        ai_message TEXT, original_url TEXT, status TEXT DEFAULT 'new',
        created_at TIMESTAMP DEFAULT NOW())''')
    cur.execute('''CREATE TABLE IF NOT EXISTS cycle_insights (
        id SERIAL PRIMARY KEY, cycle_time TIMESTAMP DEFAULT NOW(),
        total_raw INT, total_stored INT, total_leads INT,
        platforms_data JSONB, top_segment TEXT, top_action TEXT,
        weather_summary TEXT, trend_summary TEXT, insight_text TEXT)''')
    conn.commit()
    conn.close()
    log.info('DB tables ensured')

# ============ HELPERS ============
def safe_request(url, retries=MAX_RETRIES, delay=RETRY_DELAY, timeout=20):
    for attempt in range(retries):
        try:
            r = SESSION.get(url, timeout=timeout)
            if r.status_code == 429:
                wait = int(r.headers.get('Retry-After', delay * (attempt + 1) * 3))
                log.warning(f'Rate limited on {url[:80]}, waiting {wait}s')
                time.sleep(wait)
                continue
            if r.status_code >= 500:
                log.warning(f'Server error {r.status_code} on {url[:80]}, retry {attempt+1}')
                time.sleep(delay * (attempt + 1))
                continue
            r.raise_for_status()
            return r
        except requests.exceptions.Timeout:
            log.warning(f'Timeout on {url[:80]}, retry {attempt+1}')
            time.sleep(delay)
        except requests.exceptions.ConnectionError:
            log.warning(f'Connection error on {url[:80]}, retry {attempt+1}')
            time.sleep(delay * (attempt + 1))
        except Exception as e:
            log.warning(f'Request error on {url[:80]}: {e}, retry {attempt+1}')
            time.sleep(delay)
    return None

def content_hash(text):
    return hashlib.md5(text.strip().lower()[:200].encode()).hexdigest()

def keyword_score(text):
    t = text.lower()
    score = 0
    for k in HIGH_KW:
        if k in t: score += 20
    for k in MED_KW:
        if k in t: score += 10
    for k in LOW_KW:
        if k in t: score += 5
    score = min(100, max(1, score))
    seg, best = 'General Tourist', 0
    for s, kws in SEGMENTS.items():
        c = sum(1 for k in kws if k in t)
        if c > best: best, seg = c, s
    urg = 'high' if score >= 70 else ('medium' if score >= 40 else 'low')
    return {'segment': seg, 'score': score, 'urgency': urg, 'reasoning': f'Keyword match score {score}'}

def insert_raw(cur, src, url, txt, platform, author='', followers=0, likes=0, comments=0, shares=0, hashtags='', location=''):
    try:
        cur.execute('SELECT id FROM raw_signals WHERE url=%s', (url,))
        if cur.fetchone(): return None
        cur.execute(
            '''INSERT INTO raw_signals (source_site, url, text_snippet, platform, author,
                author_followers, engagement_likes, engagement_comments, engagement_shares,
                hashtags, location) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (src, url, txt[:500], platform, author[:100], followers, likes, comments, shares, hashtags[:300], location[:100]))
        return cur.fetchone()[0]
    except Exception as e:
        log.warning(f'Insert error for {url[:60]}: {e}')
        return None

# ============ PLATFORM COLLECTORS ============

def collect_reddit():
    """Collect from Reddit JSON API with full engagement fields."""
    signals = []
    for sub in SUBREDDITS:
        for kw in SEARCH_KEYWORDS[:5]:
            url = f'https://www.reddit.com/r/{sub}/search.json?q={quote_plus(kw)}&sort=new&limit=25&restrict_sr=on&t=week'
            r = safe_request(url)
            if not r: continue
            try:
                data = r.json()
                for post in data.get('data', {}).get('children', []):
                    d = post.get('data', {})
                    title = d.get('title', '')
                    body = d.get('selftext', '')
                    text = f"{title} {body}".strip()
                    if not text: continue
                    signals.append({
                        'source': f'r/{sub}', 'platform': 'reddit',
                        'url': f"https://reddit.com{d.get('permalink', '')}",
                        'text': text,
                        'author': f"u/{d.get('author', '')}",
                        'followers': 0,
                        'likes': d.get('ups', 0) or 0,
                        'comments': d.get('num_comments', 0) or 0,
                        'shares': d.get('num_crossposts', 0) or 0,
                        'hashtags': '',
                        'location': d.get('subreddit_name_prefixed', ''),
                    })
            except Exception as e:
                log.warning(f'Reddit parse error r/{sub}: {e}')
            time.sleep(2)
    log.info(f'Reddit: {len(signals)} signals')
    return signals

def collect_news():
    """Collect from Google News RSS feeds."""
    signals = []
    for feed_url in RSS_FEEDS:
        r = safe_request(feed_url, retries=2, timeout=15)
        if not r: continue
        try:
            feed = feedparser.parse(r.content)
            for entry in feed.entries[:15]:
                title = entry.get('title', '')
                summary = re.sub(r'<[^>]+>', '', entry.get('summary', ''))[:200]
                text = f"{title} {summary}".strip()
                src = entry.get('source', {}).get('title', 'google_news') if isinstance(entry.get('source'), dict) else 'google_news'
                signals.append({
                    'source': src, 'platform': 'google_news',
                    'url': entry.get('link', ''),
                    'text': text,
                    'author': src,
                    'followers': 0, 'likes': 0, 'comments': 0, 'shares': 0,
                    'hashtags': '', 'location': '',
                })
        except Exception as e:
            log.warning(f'News RSS parse error: {e}')
        time.sleep(2)
    log.info(f'News: {len(signals)} signals')
    return signals

def collect_weather():
    """Collect weather from Open-Meteo (FREE, no API key needed)."""
    signals = []
    url = 'https://api.open-meteo.com/v1/forecast?latitude=19.9975&longitude=73.7898&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode&timezone=Asia/Kolkata&forecast_days=7'
    r = safe_request(url, retries=2)
    if r and r.status_code == 200:
        try:
            data = r.json()
            daily = data.get('daily', {})
            dates = daily.get('time', [])
            tmax = daily.get('temperature_2m_max', [])
            tmin = daily.get('temperature_2m_min', [])
            rain = daily.get('precipitation_sum', [])
            codes = daily.get('weathercode', [])
            weather_desc = {0:'Clear', 1:'Mainly clear', 2:'Partly cloudy', 3:'Overcast',
                45:'Fog', 51:'Light drizzle', 61:'Light rain', 63:'Moderate rain',
                65:'Heavy rain', 80:'Rain showers', 95:'Thunderstorm'}
            for i in range(len(dates)):
                dt = dates[i]
                hi = tmax[i] if i < len(tmax) else 0
                lo = tmin[i] if i < len(tmin) else 0
                pr = rain[i] if i < len(rain) else 0
                wc = codes[i] if i < len(codes) else 0
                desc = weather_desc.get(wc, f'Code {wc}')
                is_good = hi >= 20 and hi <= 35 and pr < 5
                tourism_note = 'Great for wine tours!' if is_good else ('Indoor activities recommended' if pr > 10 else 'Moderate conditions')
                text = f"Nashik {dt}: {hi}C/{lo}C, {desc}, Rain:{pr}mm - {tourism_note}"
                signals.append({
                    'source': 'open_meteo', 'platform': 'weather',
                    'url': f'https://open-meteo.com/en/docs?latitude=19.9975&longitude=73.7898&date={dt}',
                    'text': text,
                    'author': 'Open-Meteo', 'followers': 0,
                    'likes': 0, 'comments': 0, 'shares': 0,
                    'hashtags': '#weather #nashik #tourism',
                    'location': 'Nashik, Maharashtra',
                })
        except Exception as e:
            log.warning(f'Weather parse error: {e}')
    log.info(f'Weather: {len(signals)} signals')
    return signals

def collect_trends():
    """Collect Google Trends via daily trending searches RSS + related queries."""
    signals = []
    # Method 1: Google Trends daily trending (India)
    trends_url = 'https://trends.google.com/trending/rss?geo=IN'
    r = safe_request(trends_url, retries=2, timeout=15)
    if r and r.status_code == 200:
        try:
            feed = feedparser.parse(r.content)
            for entry in feed.entries[:50]:
                title = entry.get('title', '').lower()
                if any(k in title for k in ['wine', 'nashik', 'tourism', 'travel', 'maharashtra', 'vineyard', 'winery', 'weekend', 'getaway', 'resort']):
                    text = f"Trending in India: {entry.get('title', '')}"
                    signals.append({
                        'source': 'google_trends', 'platform': 'google_trends',
                        'url': entry.get('link', ''),
                        'text': text,
                        'author': 'Google Trends', 'followers': 0,
                        'likes': 0, 'comments': 0, 'shares': 0,
                        'hashtags': f'#trending',
                        'location': 'India',
                    })
        except Exception as e:
            log.warning(f'Trends RSS parse error: {e}')

    # Method 2: Google Trends explore via suggestions API
    for kw in ['nashik wine', 'wine tourism india', 'nashik travel']:
        turl = f'https://trends.google.com/trends/api/autocomplete/{quote_plus(kw)}?hl=en-IN'
        r = safe_request(turl, retries=1, timeout=10)
        if r and r.status_code == 200:
            try:
                clean = r.text.lstrip(')]}\',\n')
                data = json.loads(clean)
                topics = data.get('default', {}).get('topics', [])
                for topic in topics[:5]:
                    title = topic.get('title', '')
                    mid = topic.get('mid', '')
                    text = f"Trending topic: {title} (related to {kw})"
                    signals.append({
                        'source': 'google_trends_explore', 'platform': 'google_trends',
                        'url': f'https://trends.google.com/trends/explore?q={quote_plus(kw)}&geo=IN',
                        'text': text,
                        'author': 'Google Trends', 'followers': 0,
                        'likes': 0, 'comments': 0, 'shares': 0,
                        'hashtags': '#trending',
                        'location': 'India',
                    })
            except Exception as e:
                log.warning(f'Trends explore parse: {e}')
        time.sleep(2)
    log.info(f'Trends: {len(signals)} signals')
    return signals

# ============ PROCESSING & STORAGE ============

COLLECTORS = {
    'reddit': collect_reddit,
    'google_news': collect_news,
    'weather': collect_weather,
    'google_trends': collect_trends,
}

def process_and_store(signals, platform_name):
    if not signals: return 0, 0
    conn = get_conn()
    cur = conn.cursor()
    ns = nl = 0
    for sig in signals:
        try:
            rid = insert_raw(cur, sig['source'], sig['url'], sig['text'], sig['platform'],
                author=sig.get('author',''), followers=sig.get('followers',0),
                likes=sig.get('likes',0), comments=sig.get('comments',0),
                shares=sig.get('shares',0), hashtags=sig.get('hashtags',''),
                location=sig.get('location',''))
            if not rid: continue
            ns += 1
            ai = keyword_score(sig['text'])
            cur.execute('INSERT INTO signals (raw_signal_id, segment, score, urgency) VALUES (%s,%s,%s,%s) RETURNING id',
                (rid, ai['segment'], ai['score'], ai['urgency']))
            sid = cur.fetchone()[0]
            if ai['score'] >= MIN_SCORE_LEAD:
                handle = sig.get('author','') or sig['source']
                cur.execute('''INSERT INTO leads (signal_id, segment, score, urgency, platform, handle,
                    likes, comments, shares, hashtags, followers, location,
                    ai_message, original_url, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (sid, ai['segment'], ai['score'], ai['urgency'], sig['platform'], handle[:100],
                     sig.get('likes',0), sig.get('comments',0), sig.get('shares',0),
                     sig.get('hashtags','')[:300], sig.get('followers',0),
                     sig.get('location','')[:100], ai['reasoning'][:300], sig['url'],
                     'new' if ai['score'] >= 70 else 'nurturing'))
                nl += 1
        except Exception as e:
            log.error(f'Store error: {e}')
            try: conn.rollback()
            except: pass
    try: conn.commit()
    except Exception as e: log.error(f'Commit error: {e}')
    conn.close()
    return ns, nl

# ============ UTILIZATION & INSIGHTS ============

ACTION_MAP = {
    'Wine Enthusiast': 'Send wine tasting event invites, partner with Sula/York for cross-promotion, create vineyard tour packages',
    'Weekend Getaway': 'Push weekend packages on social media, create 2-night stay deals, target Mumbai/Pune audiences',
    'Luxury Seeker': 'Highlight premium amenities, create exclusive wine+dine experiences, partner with luxury travel agents',
    'Adventure Tourist': 'Promote trekking+wine combos, partner with adventure sports providers, create outdoor activity packages',
    'Corporate Group': 'Create team building packages, offer conference+wine tour combos, reach out to HR managers',
    'Foodie': 'Partner with food bloggers, create wine+food pairing events, list on Zomato/Swiggy experiences',
    'Culture Explorer': 'Highlight Nashik temples+wine tours, create heritage walks, partner with cultural tourism boards',
    'General Tourist': 'Broad marketing campaigns, list on MakeMyTrip/Goibibo, create all-inclusive packages',
}

def generate_insights(platform_stats, weather_signals):
    """Generate actionable insights from collected data."""
    conn = get_conn()
    cur = conn.cursor()
    
    # Get segment distribution from recent leads
    cur.execute("SELECT segment, count(*) as cnt FROM leads WHERE created_at > NOW() - INTERVAL '24 hours' GROUP BY segment ORDER BY cnt DESC")
    seg_rows = cur.fetchall()
    top_seg = seg_rows[0][0] if seg_rows else 'General Tourist'
    
    # Get total counts
    cur.execute("SELECT count(*) FROM leads WHERE created_at > NOW() - INTERVAL '24 hours'")
    recent_leads = cur.fetchone()[0]
    
    cur.execute("SELECT count(*) FROM raw_signals WHERE collected_at > NOW() - INTERVAL '24 hours'")
    recent_signals = cur.fetchone()[0]
    
    # Get high-score leads
    cur.execute("SELECT handle, score, platform, segment FROM leads WHERE score >= 70 AND created_at > NOW() - INTERVAL '24 hours' ORDER BY score DESC LIMIT 5")
    hot_leads = cur.fetchall()
    
    # Weather summary
    weather_summary = 'No weather data'
    for sig in weather_signals:
        if 'Great for wine tours' in sig.get('text', ''):
            weather_summary = sig['text'][:150]
            break
    if weather_summary == 'No weather data':
        for sig in weather_signals:
            weather_summary = sig.get('text', '')[:150]
            break
    
    # Build insight text
    top_action = ACTION_MAP.get(top_seg, 'Run general marketing campaigns')
    
    seg_breakdown = ', '.join([f"{s[0]}: {s[1]}" for s in seg_rows[:5]]) if seg_rows else 'No data yet'
    hot_leads_text = ', '.join([f"{h[0]}(score:{h[1]},{h[2]})" for h in hot_leads]) if hot_leads else 'None yet'
    
    insight = f"""=== DEMAND INTELLIGENCE REPORT ===
Period: Last 24 hours
Signals collected: {recent_signals}
Leads generated: {recent_leads}
Top segment: {top_seg}
Segment breakdown: {seg_breakdown}
Hot leads (score>=70): {hot_leads_text}
Weather: {weather_summary}

=== RECOMMENDED ACTIONS ===
1. PRIORITY: {top_action}
2. Weather-based: {'Push outdoor wine tour promotions - weather is ideal!' if 'Great' in weather_summary else 'Consider indoor wine tasting event promotions'}
3. Content: Create content targeting {top_seg} segment on Reddit and news outlets
4. Outreach: Contact hot leads directly with personalized offers
"""
    
    # Store insight
    try:
        total_raw = sum(s.get('raw', 0) for s in platform_stats.values())
        total_stored = sum(s.get('stored', 0) for s in platform_stats.values())
        total_leads_count = sum(s.get('leads', 0) for s in platform_stats.values())
        cur.execute('''INSERT INTO cycle_insights (total_raw, total_stored, total_leads,
            platforms_data, top_segment, top_action, weather_summary, insight_text)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
            (total_raw, total_stored, total_leads_count,
             json.dumps(platform_stats), top_seg, top_action[:200],
             weather_summary[:200], insight[:1000]))
        conn.commit()
    except Exception as e:
        log.error(f'Insight store error: {e}')
    conn.close()
    
    log.info(f'\n{insight}')
    return insight

# ============ MAIN DAEMON ============

def run_cycle():
    start = time.time()
    total_raw = total_stored = total_leads = 0
    platform_stats = {}
    weather_signals = []

    for name, collector_fn in COLLECTORS.items():
        log.info(f'--- Collecting: {name} ---')
        try:
            signals = collector_fn()
            if name == 'weather':
                weather_signals = signals
            stored, leads = process_and_store(signals, name)
            platform_stats[name] = {'raw': len(signals), 'stored': stored, 'leads': leads}
            total_raw += len(signals)
            total_stored += stored
            total_leads += leads
            log.info(f'{name}: {len(signals)} raw -> {stored} stored, {leads} leads')
        except Exception as e:
            log.error(f'PLATFORM ERROR {name}: {e}')
            log.error(traceback.format_exc())
            platform_stats[name] = {'raw': 0, 'stored': 0, 'leads': 0, 'error': str(e)}

    elapsed = round(time.time() - start, 1)
    log.info(f'CYCLE DONE: {total_raw} raw -> {total_stored} signals, {total_leads} leads in {elapsed}s')
    
    # Generate utilization insights
    try:
        generate_insights(platform_stats, weather_signals)
    except Exception as e:
        log.error(f'Insight generation error: {e}')
    
    return total_stored, total_leads

def main():
    log.info('='*60)
    log.info('VayaVia Demand Engine v3.1 starting')
    log.info(f'Platforms: {", ".join(COLLECTORS.keys())}')
    log.info(f'Cycle interval: {CYCLE_INTERVAL}s')
    log.info('='*60)

    for attempt in range(MAX_RETRIES):
        try:
            ensure_tables()
            break
        except Exception as e:
            log.error(f'DB init attempt {attempt+1} failed: {e}')
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                log.critical('Cannot initialize database, exiting')
                sys.exit(1)

    while True:
        try:
            run_cycle()
        except Exception as e:
            log.error(f'CYCLE FATAL ERROR: {e}')
            log.error(traceback.format_exc())
            log.info('Self-healing: will retry next cycle')

        next_run = datetime.now() + timedelta(seconds=CYCLE_INTERVAL)
        log.info(f'Next cycle at {next_run.strftime("%H:%M:%S")}')
        time.sleep(CYCLE_INTERVAL)

if __name__ == '__main__':
    main()
