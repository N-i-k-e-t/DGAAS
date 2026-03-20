#!/usr/bin/env python3
"""VayaVia Demand Engine - Multi-Platform Collector v2.0
Auto-triggering, self-healing, collects from Reddit, X/Twitter,
Instagram, Facebook, Quora, Google News, Weather, Trends.
Each platform stored SEPARATELY with platform-specific fields.
Runs as systemd service with automatic error recovery."""
import psycopg2, requests, json, time, re, logging, sys, traceback
from datetime import datetime, timedelta
import feedparser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/collector.log')
    ]
)
log = logging.getLogger('collector')

DB = dict(dbname='vayavia_agent', user='postgres', password='postgres', host='localhost')
WEATHER_KEY = '2dce6b15be076925e81c0765e9a3a7e4'
CYCLE_INTERVAL = 3600  # 1 hour in seconds
time.sleep(min(wait, 10))
RETRY_DELAY = 5

# --- Platform configs ---
SUBREDDITS = ['india', 'travel', 'wine', 'IndiaTravelAdvice', 'solotravel', 'digitalnomad']
RSS_FEEDS = [
    'https://news.google.com/rss/search?q=nashik+wine+tourism&hl=en-IN&gl=IN',
    'https://news.google.com/rss/search?q=nashik+vineyard+stay&hl=en-IN&gl=IN',
    'https://news.google.com/rss/search?q=maharashtra+wine+resort&hl=en-IN&gl=IN',
]
TWITTER_QUERIES = ['nashik wine', 'nashik vineyard', 'sula vineyards', 'nashik tourism weekend', 'wine tasting india']
QUORA_TOPICS = ['nashik-wine', 'indian-wine-tourism', 'nashik-travel', 'sula-vineyards', 'maharashtra-weekend-getaway']
INSTA_HASHTAGS = ['nashikwine', 'sulavineyards', 'nashiktourism', 'winecountryindia', 'nashikdiaries', 'winetasting']
FB_PAGES = ['nashikwinelovers', 'sulavineyards', 'maharashtratourism', 'nashiktourismofficial']

KEYWORDS_HIGH = ['book', 'stay', 'visit', 'plan', 'recommend', 'looking for', 'want to go', 'trip to nashik', 'reserve', 'available', 'pricing']
KEYWORDS_MED = ['nashik', 'wine', 'vineyard', 'winery', 'sula', 'tourism', 'maharashtra', 'grover', 'york winery']
SEGMENT_KEYWORDS = {
    'Wine Enthusiast': ['wine tasting', 'winery', 'sula', 'vineyard tour', 'sommelier', 'grapes', 'vintage'],
    'Weekend Getaway': ['weekend', 'getaway', 'short trip', 'day trip', '2 days', 'quick escape'],
    'Luxury Seeker': ['luxury', 'premium', 'spa', 'resort', '5 star', 'boutique', 'exclusive'],
    'Couples/Romance': ['couple', 'romantic', 'honeymoon', 'anniversary', 'date', 'proposal'],
    'Family Vacation': ['family', 'kids', 'children', 'group trip', 'picnic'],
    'Corporate Group': ['corporate', 'team', 'offsite', 'conference', 'retreat', 'team building'],
    'Budget Traveler': ['budget', 'cheap', 'affordable', 'backpack', 'hostel', 'low cost'],
    'Seasonal Traveler': ['festival', 'season', 'harvest', 'grape stomping', 'winter', 'monsoon'],
}

# ============ DB HELPERS (self-healing) ============
def get_conn():
    for attempt in range(MAX_RETRIES):
        try:
            return psycopg2.connect(**DB)
        except Exception as e:
            log.error(f'DB connect attempt {attempt+1} failed: {e}')
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    raise Exception('DB connection failed after retries')

def ensure_tables():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS raw_signals (
            id SERIAL PRIMARY KEY,
            source_site TEXT NOT NULL,
            url TEXT,
            text_snippet TEXT,
            platform TEXT NOT NULL DEFAULT 'unknown',
            author TEXT,
            author_followers INT DEFAULT 0,
            engagement_likes INT DEFAULT 0,
            engagement_comments INT DEFAULT 0,
            engagement_shares INT DEFAULT 0,
            hashtags TEXT,
            location TEXT,
            language TEXT DEFAULT 'en',
            collected_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(url)
        );
        CREATE TABLE IF NOT EXISTS signals (
            id SERIAL PRIMARY KEY,
            raw_signal_id INT REFERENCES raw_signals(id),
            segment TEXT,
            score INT,
            urgency TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS leads (
            id SERIAL PRIMARY KEY,
            signal_id INT REFERENCES signals(id),
            segment TEXT,
            score INT,
            urgency TEXT,
            platform TEXT,
            handle TEXT,
            ai_message TEXT,
            original_url TEXT,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS collection_logs (
            id SERIAL PRIMARY KEY,
            cycle_time TIMESTAMP DEFAULT NOW(),
            platform TEXT,
            signals_found INT DEFAULT 0,
            signals_stored INT DEFAULT 0,
            leads_created INT DEFAULT 0,
            errors TEXT,
            duration_sec FLOAT DEFAULT 0
        );
    ''')
    # Add columns if missing (self-heal schema)
    for col, typ in [('platform','TEXT'),('author','TEXT'),('author_followers','INT'),
                      ('engagement_likes','INT'),('engagement_comments','INT'),
                      ('engagement_shares','INT'),('hashtags','TEXT'),('location','TEXT'),('language','TEXT')]:
        try:
            cur.execute(f"ALTER TABLE raw_signals ADD COLUMN IF NOT EXISTS {col} {typ}")
        except Exception:
            pass
    conn.commit()
    cur.close()
    conn.close()
    log.info('DB tables ensured')

def insert_raw(cur, src, url, txt, platform, author='', followers=0, likes=0, comments=0, shares=0, hashtags='', location=''):
    try:
        cur.execute('SELECT id FROM raw_signals WHERE url=%s', (url,))
        if cur.fetchone():
            return None
        cur.execute(
            '''INSERT INTO raw_signals (source_site, url, text_snippet, platform, author,
               author_followers, engagement_likes, engagement_comments, engagement_shares,
               hashtags, location) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (src, url, txt[:500], platform, author[:100], followers, likes, comments, shares, hashtags[:300], location[:100])
        )
        return cur.fetchone()[0]
    except Exception as e:
        log.warning(f'Insert error for {url}: {e}')
        return None

# ============ SCORING ============
def keyword_score(text):
    t = text.lower()
    score = 30
    for k in KEYWORDS_HIGH:
        if k in t: score += 15
    for k in KEYWORDS_MED:
        if k in t: score += 5
    score = min(100, score)
    seg, best = 'Unknown', 0
    for s, kws in SEGMENT_KEYWORDS.items():
        c = sum(1 for k in kws if k in t)
        if c > best: best, seg = c, s
    if seg == 'Unknown': seg = 'Wine Enthusiast'
    urg = 'high' if score >= 70 else ('medium' if score >= 50 else 'low')
    return {'segment': seg, 'score': score, 'urgency': urg, 'reasoning': f'Keyword match score {score}'}

def safe_request(url, headers=None, timeout=15):
    """HTTP GET with automatic retry and error handling"""
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, headers=headers or {}, timeout=timeout)
            if r.status_code == 200:
                return r
            if r.status_code == 429:
                wait = int(r.headers.get('Retry-After', 60))
                log.warning(f'Rate limited on {url}, waiting {wait}s')
                time.sleep(min(wait, 10))
                continue
            if r.status_code >= 500:
                log.warning(f'Server error {r.status_code} on {url}, retry {attempt+1}')
                time.sleep(RETRY_DELAY)
                continue
            return r
        except requests.exceptions.Timeout:
            log.warning(f'Timeout on {url}, retry {attempt+1}')
            time.sleep(1)
        except Exception as e:
            log.warning(f'Request error {url}: {e}')
            time.sleep(1)
    return None

# ============ PLATFORM: REDDIT ============
def collect_reddit():
    signals = []
    hdrs = {'User-Agent': 'VayaVia-DemandBot/2.0'}
    for sub in SUBREDDITS:
        for kw in ['nashik', 'wine+tourism+india', 'vineyard+stay', 'maharashtra+weekend']:
            try:
                url = f'https://www.reddit.com/r/{sub}/search.json?q={kw}&sort=new&t=week&limit=10'
                r = safe_request(url, headers=hdrs)
                if r and r.status_code == 200:
                    for p in r.json().get('data', {}).get('children', []):
                        d = p.get('data', {})
                        t = d.get('title', '') + ' ' + d.get('selftext', '')[:200]
                        link = 'https://reddit.com' + d.get('permalink', '')
                        if any(k in t.lower() for k in ['nashik', 'wine', 'vineyard', 'sula', 'maharashtra', 'winery']):
                            signals.append({
                                'source': 'reddit', 'platform': 'reddit',
                                'url': link, 'text': t[:500],
                                'author': 'u/' + d.get('author', 'unknown'),
                                'likes': d.get('ups', 0),
                                'comments': d.get('num_comments', 0),
                                'shares': 0, 'hashtags': '', 'followers': 0,
                                'location': d.get('subreddit', sub)
                            })
                time.sleep(2)
            except Exception as e:
                log.warning(f'Reddit r/{sub} {kw}: {e}')
    log.info(f'Reddit: {len(signals)} signals')
    return signals

# ============ PLATFORM: X / TWITTER ============
def collect_twitter():
    signals = []
    hdrs = {'User-Agent': 'VayaVia-DemandBot/2.0'}
    for query in TWITTER_QUERIES:
        try:
            # Nitter instances for public Twitter scraping
            for nitter in ['https://nitter.poast.org']:
                try:
                    url = f'{nitter}/search?q={query.replace(" ", "+")}&f=tweets'
                    r = safe_request(url, headers=hdrs, timeout=10)
                    if r and r.status_code == 200:
                        # Parse tweets from HTML
                        tweets = re.findall(r'class="tweet-content[^"]*">([^<]+)</div>', r.text)
                        usernames = re.findall(r'class="username"[^>]*>@([^<]+)<', r.text)
                        links = re.findall(r'href="(/[^/]+/status/\d+)"', r.text)
                        for i, tweet_text in enumerate(tweets[:10]):
                            if any(k in tweet_text.lower() for k in ['nashik', 'wine', 'vineyard', 'sula', 'winery']):
                                user = usernames[i] if i < len(usernames) else 'unknown'
                                link = f'https://x.com{links[i]}' if i < len(links) else f'https://x.com/search?q={query}'
                                signals.append({
                                    'source': 'twitter', 'platform': 'twitter',
                                    'url': link, 'text': tweet_text[:500],
                                    'author': f'@{user}',
                                    'likes': 0, 'comments': 0, 'shares': 0,
                                    'hashtags': ','.join(re.findall(r'#(\w+)', tweet_text)),
                                    'followers': 0, 'location': ''
                                })
                        if tweets:
                            break
                except Exception:
                    continue
            time.sleep(1)
        except Exception as e:
            log.warning(f'Twitter {query}: {e}')
    log.info(f'Twitter/X: {len(signals)} signals')
    return signals

# ============ PLATFORM: INSTAGRAM ============
def collect_instagram():
    signals = []
    hdrs = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)'}
    for tag in INSTA_HASHTAGS:
        try:
            # Try public hashtag pages and Bibliogram/Imginn mirrors
            for mirror in ['https://imginn.com/tag/', 'https://www.picuki.com/tag/']:
                try:
                    url = f'{mirror}{tag}'
                    r = safe_request(url, headers=hdrs, timeout=10)
                    if r and r.status_code == 200:
                        # Extract post descriptions
                        descs = re.findall(r'class="[^"]*description[^"]*">([^<]{20,300})', r.text)
                        post_links = re.findall(r'href="([^"]*(?:post|media|p/)[^"]+)"', r.text)
                        for i, desc in enumerate(descs[:5]):
                            if any(k in desc.lower() for k in ['nashik', 'wine', 'vineyard', 'sula', 'winery', 'nashikdiaries']):
                                link = post_links[i] if i < len(post_links) else f'{mirror}{tag}'
                                if not link.startswith('http'):
                                    link = mirror.rstrip('/') + link
                                tags_found = re.findall(r'#(\w+)', desc)
                                signals.append({
                                    'source': 'instagram', 'platform': 'instagram',
                                    'url': link, 'text': desc[:500],
                                    'author': '', 'likes': 0, 'comments': 0, 'shares': 0,
                                    'hashtags': ','.join(tags_found[:10]),
                                    'followers': 0, 'location': ''
                                })
                        if descs:
                            break
                except Exception:
                    continue
            time.sleep(1)
        except Exception as e:
            log.warning(f'Instagram #{tag}: {e}')
    log.info(f'Instagram: {len(signals)} signals')
    return signals

# ============ PLATFORM: FACEBOOK ============
def collect_facebook():
    signals = []
    hdrs = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    fb_search_queries = ['nashik wine tourism', 'nashik vineyard visit', 'sula vineyards experience', 'nashik winery weekend']
    for query in fb_search_queries:
        try:
            # Use Google to find public FB posts
            gurl = f'https://www.google.com/search?q=site:facebook.com+{query.replace(" ", "+")}&tbs=qdr:w'
            r = safe_request(gurl, headers=hdrs, timeout=10)
            if r and r.status_code == 200:
                # Extract FB links and snippets from Google results
                fb_links = re.findall(r'href="(https://(?:www\.)?facebook\.com/[^"&]+)"', r.text)
                snippets = re.findall(r'<span[^>]*>([^<]{30,300})</span>', r.text)
                for i, link in enumerate(fb_links[:5]):
                    txt = snippets[i] if i < len(snippets) else query
                    if any(k in txt.lower() for k in ['nashik', 'wine', 'vineyard', 'sula', 'winery', 'tourism']):
                        signals.append({
                            'source': 'facebook', 'platform': 'facebook',
                            'url': link, 'text': txt[:500],
                            'author': '', 'likes': 0, 'comments': 0, 'shares': 0,
                            'hashtags': '', 'followers': 0, 'location': ''
                        })
            time.sleep(1)
        except Exception as e:
            log.warning(f'Facebook {query}: {e}')
    # Also try FB page RSS via RSS bridges
    for page in FB_PAGES:
        try:
            rss_url = f'https://fetchrss.com/rss/facebook/{page}'
            r = safe_request(rss_url, headers=hdrs, timeout=10)
            if r and r.status_code == 200:
                feed = feedparser.parse(r.text)
                for entry in feed.entries[:5]:
                    t = entry.get('title', '') + ' ' + entry.get('summary', '')[:200]
                    if any(k in t.lower() for k in ['nashik', 'wine', 'vineyard', 'sula']):
                        signals.append({
                            'source': 'facebook', 'platform': 'facebook',
                            'url': entry.get('link', ''), 'text': t[:500],
                            'author': page, 'likes': 0, 'comments': 0, 'shares': 0,
                            'hashtags': '', 'followers': 0, 'location': ''
                        })
        except Exception:
            pass
    log.info(f'Facebook: {len(signals)} signals')
    return signals

# ============ PLATFORM: QUORA ============
def collect_quora():
    signals = []
    hdrs = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    quora_queries = ['nashik wine tourism', 'best vineyards nashik', 'sula vineyards visit', 'nashik winery experience', 'wine tasting india']
    for query in quora_queries:
        try:
            # Search Google for Quora posts
            gurl = f'https://www.google.com/search?q=site:quora.com+{query.replace(" ", "+")}&tbs=qdr:m'
            r = safe_request(gurl, headers=hdrs, timeout=10)
            if r and r.status_code == 200:
                quora_links = re.findall(r'href="(https://(?:www\.)?quora\.com/[^"&]+)"', r.text)
                snippets = re.findall(r'<span[^>]*>([^<]{30,300})</span>', r.text)
                for i, link in enumerate(quora_links[:5]):
                    txt = snippets[i] if i < len(snippets) else query
                    if any(k in txt.lower() for k in ['nashik', 'wine', 'vineyard', 'sula', 'winery', 'tourism']):
                        signals.append({
                            'source': 'quora', 'platform': 'quora',
                            'url': link, 'text': txt[:500],
                            'author': '', 'likes': 0, 'comments': 0, 'shares': 0,
                            'hashtags': '', 'followers': 0, 'location': ''
                        })
            time.sleep(1)
        except Exception as e:
            log.warning(f'Quora {query}: {e}')
    log.info(f'Quora: {len(signals)} signals')
    return signals

# ============ PLATFORM: GOOGLE NEWS ============
def collect_news():
    signals = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                t = entry.get('title', '') + ' ' + entry.get('summary', '')[:200]
                if any(k in t.lower() for k in ['nashik', 'wine', 'vineyard', 'winery', 'tourism']):
                    signals.append({
                        'source': 'google_news', 'platform': 'google_news',
                        'url': entry.get('link', ''), 'text': t[:500],
                        'author': entry.get('author', ''),
                        'likes': 0, 'comments': 0, 'shares': 0,
                        'hashtags': '', 'followers': 0, 'location': ''
                    })
        except Exception as e:
            log.warning(f'News feed error: {e}')
    log.info(f'News: {len(signals)} signals')
    return signals

# ============ PLATFORM: WEATHER ============
def collect_weather():
    signals = []
    try:
        r = safe_request(f'https://api.openweathermap.org/data/2.5/weather?q=Nashik,IN&appid={WEATHER_KEY}&units=metric')
        if r:
            w = r.json()
            temp = w['main']['temp']
            desc = w['weather'][0]['description']
            if 20 <= temp <= 32 and 'rain' not in desc.lower():
                signals.append({
                    'source': 'weather', 'platform': 'weather',
                    'url': 'https://openweathermap.org/city/1261529',
                    'text': f'Nashik weather ideal for tourism: {temp}C, {desc}. Perfect for vineyard visits.',
                    'author': 'OpenWeatherMap', 'likes': 0, 'comments': 0, 'shares': 0,
                    'hashtags': '', 'followers': 0, 'location': 'Nashik'
                })
    except Exception: pass
    for city, cid in [('Mumbai','1275339'),('Pune','1259229'),('Delhi','1273294')]:
        try:
            r = safe_request(f'https://api.openweathermap.org/data/2.5/weather?q={city},IN&appid={WEATHER_KEY}&units=metric')
            if r:
                w = r.json()
                temp = w['main']['temp']
                desc = w['weather'][0]['description']
                if temp > 35 or 'haze' in desc.lower() or 'smoke' in desc.lower():
                    signals.append({
                        'source': 'weather', 'platform': 'weather',
                        'url': f'https://openweathermap.org/city/{cid}',
                        'text': f'{city} {desc} at {temp}C - escape demand to Nashik vineyards.',
                        'author': 'OpenWeatherMap', 'likes': 0, 'comments': 0, 'shares': 0,
                        'hashtags': '', 'followers': 0, 'location': city
                    })
        except Exception: pass
    log.info(f'Weather: {len(signals)} signals')
    return signals

# ============ PLATFORM: GOOGLE TRENDS ============
def collect_trends():
    signals = []
    try:
        from pytrends.request import TrendReq
        pt = TrendReq(hl='en-IN', tz=330, timeout=(10, 25))
        kws = ['nashik wine', 'nashik winery', 'wine tasting nashik']
        pt.build_payload(kws, timeframe='now 7-d', geo='IN')
        df = pt.interest_over_time()
        if not df.empty:
            for kw in kws:
                v = int(df[kw].iloc[-1])
                if v > 30:
                    signals.append({
                        'source': 'google_trends', 'platform': 'google_trends',
                        'url': f'https://trends.google.com/trends/explore?q={kw.replace(" ", "+")}&geo=IN',
                        'text': f'Google Trends spike: "{kw}" at {v}/100 interest in India.',
                        'author': 'Google Trends', 'likes': 0, 'comments': 0, 'shares': 0,
                        'hashtags': '', 'followers': 0, 'location': 'India'
                    })
    except Exception as e:
        log.warning(f'Trends error: {e}')
    log.info(f'Trends: {len(signals)} signals')
    return signals

# ============ MAIN COLLECTION CYCLE ============
PLATFORM_COLLECTORS = {
    'reddit': collect_reddit,
    'twitter': collect_twitter,
    'instagram': collect_instagram,
    'facebook': collect_facebook,
    'quora': collect_quora,
    'google_news': collect_news,
    'weather': collect_weather,
    'google_trends': collect_trends,
}

def process_and_store(signals, platform_name):
    """Score signals and store in DB. Returns (stored, leads_created)."""
    if not signals:
        return 0, 0
    conn = get_conn()
    cur = conn.cursor()
    ns = nl = 0
    for sig in signals:
        try:
            rid = insert_raw(
                cur, sig['source'], sig['url'], sig['text'], sig['platform'],
                author=sig.get('author',''), followers=sig.get('followers',0),
                likes=sig.get('likes',0), comments=sig.get('comments',0),
                shares=sig.get('shares',0), hashtags=sig.get('hashtags',''),
                location=sig.get('location','')
            )
            if not rid:
                continue
            ns += 1
            ai = keyword_score(sig['text'])
            seg = ai['segment']
            sc = min(100, max(1, ai['score']))
            urg = ai['urgency']
            reason = ai['reasoning']
            cur.execute(
                'INSERT INTO signals (raw_signal_id, segment, score, urgency) VALUES (%s,%s,%s,%s) RETURNING id',
                (rid, seg, sc, urg)
            )
            sid = cur.fetchone()[0]
            if sc >= 50:
                handle = sig.get('author', '') or sig['source']
                cur.execute(
                    '''INSERT INTO leads (signal_id, segment, score, urgency, platform, handle,
                       ai_message, original_url, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (sid, seg, sc, urg, sig['platform'], handle[:100],
                     reason[:300], sig['url'], 'new' if sc >= 70 else 'nurturing')
                )
                nl += 1
        except Exception as e:
            log.error(f'Store error for {sig.get("url","?")}: {e}')
            try:
                conn.rollback()
            except Exception:
                pass
    try:
        conn.commit()
    except Exception as e:
        log.error(f'Commit error: {e}')
        conn.rollback()
    cur.close()
    conn.close()
    return ns, nl

def run_cycle():
    """Run one full collection cycle across ALL platforms."""
    cycle_start = datetime.now()
    log.info('=' * 60)
    log.info(f'COLLECTION CYCLE at {cycle_start}')
    log.info('=' * 60)
    total_signals = 0
    total_leads = 0
    total_raw = 0
    conn_log = get_conn()
    cur_log = conn_log.cursor()
    for platform_name, collector_fn in PLATFORM_COLLECTORS.items():
        plat_start = time.time()
        errors = ''
        raw_count = 0
        stored = 0
        leads = 0
        try:
            log.info(f'--- Collecting: {platform_name} ---')
            sigs = collector_fn()
            raw_count = len(sigs)
            total_raw += raw_count
            stored, leads = process_and_store(sigs, platform_name)
            total_signals += stored
            total_leads += leads
            log.info(f'{platform_name}: {raw_count} raw -> {stored} stored, {leads} leads')
        except Exception as e:
            errors = str(e)[:500]
            log.error(f'{platform_name} FAILED: {e}')
            log.error(traceback.format_exc())
        duration = time.time() - plat_start
        # Log per-platform stats
        try:
            cur_log.execute(
                '''INSERT INTO collection_logs (platform, signals_found, signals_stored, leads_created, errors, duration_sec)
                   VALUES (%s,%s,%s,%s,%s,%s)''',
                (platform_name, raw_count, stored, leads, errors[:500] if errors else None, round(duration, 2))
            )
        except Exception:
            pass
    try:
        conn_log.commit()
    except Exception:
        pass
    cur_log.close()
    conn_log.close()
    elapsed = (datetime.now() - cycle_start).total_seconds()
    log.info(f'CYCLE DONE: {total_raw} raw -> {total_signals} signals, {total_leads} leads in {elapsed:.1f}s')
    return total_signals

# ============ SELF-HEALING DAEMON ============
def run_daemon():
    """Continuously run collection cycles with automatic error recovery."""
    log.info('VayaVia Demand Engine v2.0 - Daemon Starting')
    log.info(f'Cycle interval: {CYCLE_INTERVAL}s ({CYCLE_INTERVAL//60}min)')
    log.info(f'Platforms: {list(PLATFORM_COLLECTORS.keys())}')
    ensure_tables()
    consecutive_errors = 0
    while True:
        try:
            run_cycle()
            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            log.error(f'CYCLE ERROR #{consecutive_errors}: {e}')
            log.error(traceback.format_exc())
            if consecutive_errors >= 5:
                log.critical(f'5 consecutive errors - waiting 5min before retry')
                time.sleep(300)
                consecutive_errors = 0
                # Re-ensure tables in case of schema issues
                try:
                    ensure_tables()
                except Exception:
                    pass
        # Wait for next cycle
        next_run = datetime.now() + timedelta(seconds=CYCLE_INTERVAL)
        log.info(f'Next cycle at {next_run.strftime("%H:%M:%S")}')
        time.sleep(CYCLE_INTERVAL)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        ensure_tables()
        run_cycle()
    else:
        run_daemon()
