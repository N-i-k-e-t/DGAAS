#!/usr/bin/env python3
"""VayaVia Browser Collector v3.0 - Requests-based Multi-Agent System
No Playwright, no Chromium, no greenlet issues. Pure requests+BeautifulSoup.
Each platform = 1 agent. All agents run sequentially per cycle (~5 min total).
"""
import os, sys, time, json, re, hashlib, logging, traceback, signal
import requests
from bs4 import BeautifulSoup
import psycopg2
from psycopg2 import pool
from urllib.parse import quote_plus, urljoin
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'dbname': os.getenv('DB_NAME', 'vayavia_agent'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres')
}

CYCLE_INTERVAL = 3600
REQUEST_TIMEOUT = 15
db_pool = None

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

QUERIES = [
    'Nashik wine tourism', 'Nashik vineyard visit', 'Nashik wine tasting experience',
    'Sula vineyards Nashik', 'York winery Nashik', 'Nashik wine tour packages',
    'Maharashtra wine country', 'Indian wine tourism', 'Nashik weekend getaway wine',
    'best wineries near Mumbai', 'Nashik grape stomping festival',
]

WINE_KEYWORDS = ['wine', 'vineyard', 'winery', 'grape', 'tasting', 'cellar', 'sommelier', 'vintage', 'sula', 'york', 'grover']
TOURISM_KEYWORDS = ['tourism', 'travel', 'visit', 'trip', 'tour', 'hotel', 'resort', 'getaway', 'weekend', 'holiday', 'booking']
COMPETITORS = ['sula', 'york winery', 'grover zampa', 'fratelli', 'charosa', 'soma vine village', 'vallonne']

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler('/var/log/vayavia-browser.log'), logging.StreamHandler()]
)
log = logging.getLogger('browser_v3')

# Graceful shutdown
shutdown_flag = False
def handle_signal(sig, frame):
    global shutdown_flag
    shutdown_flag = True
    log.info(f"Received signal {sig}, shutting down gracefully...")
signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

# ============================================================
# DATABASE HELPERS
# ============================================================
def init_db_pool():
    global db_pool
    db_pool = pool.SimpleConnectionPool(1, 5, **DB_CONFIG)
    log.info("DB pool initialized")

def get_conn():
    return db_pool.getconn()

def put_conn(conn):
    db_pool.putconn(conn)

def dedup_key(url, text):
    return hashlib.md5(f"{url}|{text[:200]}".encode()).hexdigest()

def store_raw_signal(conn, data):
    """Store into raw_signals table, return id or None if duplicate."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM raw_signals WHERE url=%s AND text_snippet=%s LIMIT 1",
            (data.get('url','')[:500], data.get('text_snippet','')[:500]))
        if cur.fetchone():
            return None
        cur.execute("""INSERT INTO raw_signals
            (source_site, url, text_snippet, metadata, platform, author,
            engagement_likes, engagement_comments, engagement_shares,
            hashtags, location, language)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (data.get('source_site',''), data.get('url','')[:500],
            data.get('text_snippet','')[:500],
            json.dumps(data.get('metadata',{})),
            data.get('platform',''), data.get('author',''),
            data.get('engagement_likes',0), data.get('engagement_comments',0),
            data.get('engagement_shares',0), data.get('hashtags',''),
            data.get('location','Nashik'), data.get('language','en')))
        pid = cur.fetchone()[0]
        conn.commit()
        return pid
    except Exception as e:
        conn.rollback()
        log.warning(f"Store raw_signal error: {e}")
        return None
    finally:
        cur.close()

def store_post(conn, data):
    """Store into posts table, return id or None."""
    cur = conn.cursor()
    try:
        text = data.get('text','')[:1000]
        url = data.get('url','')[:500]
        cur.execute("SELECT id FROM posts WHERE url=%s LIMIT 1", (url,))
        if cur.fetchone():
            return None
        rel = compute_relevance(text)
        urg = compute_urgency(text)
        cat = detect_intent(text)
        is_comp = is_competitor_mention(text)
        cur.execute("""INSERT INTO posts
            (platform, url, author, text, engagement_likes, engagement_comments,
            engagement_shares, relevance_score, intent, is_competitor,
            urgency, source_collector)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (data.get('platform',''), url, data.get('author',''), text,
            data.get('likes',0), data.get('comments',0), data.get('shares',0),
            rel, cat, is_comp, urg, 'browser_agent'))
        pid = cur.fetchone()[0]
        conn.commit()
        return pid
    except Exception as e:
        conn.rollback()
        log.warning(f"Store post error: {e}")
        return None
    finally:
        cur.close()

def store_lead(conn, post_id, data):
    """Generate lead from a high-relevance post."""
    if not post_id:
        return
    cur = conn.cursor()
    try:
        cur.execute("""INSERT INTO leads
            (post_id, username, platform, profile_url,
            lead_score, category, intent, post_url, outreach_template)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (post_id, data.get('author','unknown'), data.get('platform',''),
            data.get('profile_url',''), data.get('lead_score',50),
            data.get('category','General Tourist'), data.get('intent','general'),
            data.get('url',''),
            f"Hi {data.get('author','')}, noticed your interest in Nashik wine tourism!"))
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        cur.close()

# ============================================================
# SCORING & ANALYSIS HELPERS
# ============================================================
def detect_intent(text):
    t = text.lower()
    if any(w in t for w in ['book', 'reserve', 'price', 'cost', 'how much', 'available']):
        return 'booking'
    if any(w in t for w in ['plan', 'itinerary', 'schedule', 'when to visit']):
        return 'planning'
    if any(w in t for w in ['review', 'experience', 'visited', 'went to', 'loved']):
        return 'review'
    if any(w in t for w in ['compare', 'vs', 'better', 'difference', 'which']):
        return 'comparison'
    return 'general'

def compute_relevance(text):
    t = text.lower()
    score = 30
    for kw in WINE_KEYWORDS:
        if kw in t: score += 5
    for kw in TOURISM_KEYWORDS:
        if kw in t: score += 3
    if 'nashik' in t: score += 15
    if 'vayavia' in t.replace(' ','') or 'vaya via' in t: score += 20
    return min(score, 100)

def compute_urgency(text):
    t = text.lower()
    if any(w in t for w in ['this weekend', 'tomorrow', 'today', 'urgent', 'asap']):
        return 'high'
    if any(w in t for w in ['planning', 'soon', 'next month', 'upcoming']):
        return 'medium'
    return 'low'

def is_competitor_mention(text):
    t = text.lower()
    return any(c in t for c in COMPETITORS)

def safe_get(url, headers=None, timeout=REQUEST_TIMEOUT):
    """Safe HTTP GET with retry."""
    h = headers or HEADERS.copy()
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=h, timeout=timeout, allow_redirects=True)
            if resp.status_code == 200:
                return resp
            if resp.status_code == 429:
                wait = min(30, 5 * (attempt + 1))
                log.warning(f"Rate limited on {url[:60]}, waiting {wait}s")
                time.sleep(wait)
                continue
            log.warning(f"HTTP {resp.status_code} for {url[:80]}")
            return None
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
            else:
                log.warning(f"Request failed: {url[:60]} - {e}")
    return None

# ============================================================
# AGENT 1: YOUTUBE (via Invidious API - no browser needed)
# ============================================================
def agent_youtube():
    """Collect YouTube videos about Nashik wine tourism via Invidious API."""
    log.info("[YouTube Agent] Starting...")
    found = stored = leads = 0
    conn = get_conn()
    INVIDIOUS_INSTANCES = [
        'https://vid.puffyan.us',
        'https://invidious.snopyta.org',
        'https://yewtu.be',
        'https://inv.tux.pizza',
    ]
    try:
        for query in QUERIES[:6]:
            if shutdown_flag: break
            for instance in INVIDIOUS_INSTANCES:
                try:
                    url = f"{instance}/api/v1/search?q={quote_plus(query)}&type=video&sort=relevance"
                    resp = safe_get(url)
                    if not resp: continue
                    videos = resp.json() if resp else []
                    for v in videos[:8]:
                        found += 1
                        title = v.get('title','')
                        vid_id = v.get('videoId','')
                        author = v.get('author','')
                        views = v.get('viewCount',0)
                        desc = v.get('description','')
                        text = f"{title}. {desc[:300]}"
                        data = {
                            'platform': 'YouTube', 'url': f'https://youtube.com/watch?v={vid_id}',
                            'author': author, 'text': text, 'likes': views // 100,
                            'comments': v.get('commentCount',0) or 0, 'shares': 0,
                            'source_site': 'youtube.com', 'text_snippet': text,
                            'metadata': {'videoId': vid_id, 'query': query, 'views': views},
                            'engagement_likes': views // 100
                        }
                        pid = store_post(conn, data)
                        if pid:
                            stored += 1
                            store_raw_signal(conn, data)
                            if compute_relevance(text) >= 60:
                                store_lead(conn, pid, data)
                                leads += 1
                    break
                except Exception as e:
                    continue
            time.sleep(1)
    finally:
        put_conn(conn)
    log.info(f"[YouTube Agent] found={found} stored={stored} leads={leads}")
    return {'found': found, 'stored': stored, 'leads': leads}

# ============================================================
# AGENT 2: GOOGLE/DUCKDUCKGO SEARCH
# ============================================================
def agent_search():
    """Collect search results via DuckDuckGo HTML (no API key needed)."""
    log.info("[Search Agent] Starting...")
    found = stored = leads = 0
    conn = get_conn()
    try:
        for query in QUERIES[:8]:
            if shutdown_flag: break
            try:
                url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
                resp = safe_get(url)
                if not resp: continue
                soup = BeautifulSoup(resp.text, 'html.parser')
                results = soup.select('.result__body')
                for r in results[:10]:
                    found += 1
                    title_el = r.select_one('.result__title a')
                    snippet_el = r.select_one('.result__snippet')
                    if not title_el: continue
                    title = title_el.get_text(strip=True)
                    link = title_el.get('href','')
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ''
                    text = f"{title}. {snippet}"
                    data = {
                        'platform': 'Google Search', 'url': link,
                        'author': '', 'text': text, 'likes': 0,
                        'comments': 0, 'shares': 0,
                        'source_site': 'duckduckgo.com', 'text_snippet': text,
                        'metadata': {'query': query, 'title': title},
                        'engagement_likes': 0
                    }
                    pid = store_post(conn, data)
                    if pid:
                        stored += 1
                        store_raw_signal(conn, data)
                        if compute_relevance(text) >= 60:
                            store_lead(conn, pid, data)
                            leads += 1
            except Exception as e:
                log.warning(f"Search error for '{query}': {e}")
            time.sleep(2)
    finally:
        put_conn(conn)
    log.info(f"[Search Agent] found={found} stored={stored} leads={leads}")
    return {'found': found, 'stored': stored, 'leads': leads}

# ============================================================
# AGENT 3: TRIPADVISOR
# ============================================================
def agent_tripadvisor():
    """Collect TripAdvisor listings via search page scraping."""
    log.info("[TripAdvisor Agent] Starting...")
    found = stored = leads = 0
    conn = get_conn()
    ta_queries = ['Nashik+wine+tours', 'Nashik+vineyard', 'Sula+vineyards', 'Nashik+winery+visit']
    try:
        for q in ta_queries:
            if shutdown_flag: break
            try:
                url = f"https://www.tripadvisor.com/Search?q={q}"
                resp = safe_get(url)
                if not resp: continue
                soup = BeautifulSoup(resp.text, 'html.parser')
                for card in soup.select('[data-test-target], .result-title, .listing_title a, a[href*="Attraction_Review"], a[href*="Hotel_Review"]')[:10]:
                    found += 1
                    title = card.get_text(strip=True)
                    href = card.get('href', '')
                    if href and not href.startswith('http'):
                        href = f"https://www.tripadvisor.com{href}"
                    text = title
                    data = {
                        'platform': 'TripAdvisor', 'url': href or f'https://tripadvisor.com/search?q={q}',
                        'author': '', 'text': text, 'likes': 0,
                        'comments': 0, 'shares': 0,
                        'source_site': 'tripadvisor.com', 'text_snippet': text,
                        'metadata': {'query': q}, 'engagement_likes': 0
                    }
                    pid = store_post(conn, data)
                    if pid:
                        stored += 1
                        store_raw_signal(conn, data)
                        if compute_relevance(text) >= 55:
                            store_lead(conn, pid, data)
                            leads += 1
            except Exception as e:
                log.warning(f"TripAdvisor error: {e}")
            time.sleep(3)
    finally:
        put_conn(conn)
    log.info(f"[TripAdvisor Agent] found={found} stored={stored} leads={leads}")
    return {'found': found, 'stored': stored, 'leads': leads}

# ============================================================
# AGENT 4: QUORA
# ============================================================
def agent_quora():
    """Collect Quora questions about Nashik wine tourism."""
    log.info("[Quora Agent] Starting...")
    found = stored = leads = 0
    conn = get_conn()
    quora_queries = ['Nashik wine tourism', 'Nashik vineyard visit', 'Sula winery experience', 'best winery Nashik']
    try:
        for query in quora_queries:
            if shutdown_flag: break
            try:
                url = f"https://html.duckduckgo.com/html/?q=site:quora.com+{quote_plus(query)}"
                resp = safe_get(url)
                if not resp: continue
                soup = BeautifulSoup(resp.text, 'html.parser')
                for r in soup.select('.result__body')[:8]:
                    found += 1
                    title_el = r.select_one('.result__title a')
                    snippet_el = r.select_one('.result__snippet')
                    if not title_el: continue
                    title = title_el.get_text(strip=True)
                    link = title_el.get('href','')
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ''
                    text = f"{title}. {snippet}"
                    if 'quora.com' not in link: continue
                    data = {
                        'platform': 'Quora', 'url': link,
                        'author': '', 'text': text, 'likes': 0,
                        'comments': 0, 'shares': 0,
                        'source_site': 'quora.com', 'text_snippet': text,
                        'metadata': {'query': query}, 'engagement_likes': 0
                    }
                    pid = store_post(conn, data)
                    if pid:
                        stored += 1
                        store_raw_signal(conn, data)
                        if compute_relevance(text) >= 55:
                            store_lead(conn, pid, data)
                            leads += 1
            except Exception as e:
                log.warning(f"Quora error: {e}")
            time.sleep(2)
    finally:
        put_conn(conn)
    log.info(f"[Quora Agent] found={found} stored={stored} leads={leads}")
    return {'found': found, 'stored': stored, 'leads': leads}

# ============================================================
# AGENT 5: GOOGLE TRENDS (via related queries API)
# ============================================================
def agent_google_trends():
    """Collect Google Trends data for wine tourism keywords."""
    log.info("[Google Trends Agent] Starting...")
    found = stored = leads = 0
    conn = get_conn()
    try:
        for query in QUERIES[:5]:
            if shutdown_flag: break
            try:
                url = f"https://trends.google.com/trends/api/dailytrends?hl=en-IN&tz=-330&geo=IN&ns=15"
                resp = safe_get(url)
                if resp:
                    try:
                        text_data = resp.text
                        if text_data.startswith(')]}'):
                            text_data = text_data[4:]
                        trends_data = json.loads(text_data)
                        stories = trends_data.get('default',{}).get('trendingSearchesDays',[])
                        for day in stories[:2]:
                            for ts in day.get('trendingSearches',[])[:10]:
                                title = ts.get('title',{}).get('query','')
                                traffic = ts.get('formattedTraffic','')
                                t_lower = title.lower()
                                if any(kw in t_lower for kw in ['wine','nashik','tourism','travel','vineyard','winery']):
                                    found += 1
                                    text = f"Trending: {title} ({traffic})"
                                    data = {
                                        'platform': 'GoogleTrends', 'url': f'https://trends.google.com/trends/explore?q={quote_plus(title)}&geo=IN',
                                        'author': '', 'text': text, 'likes': 0,
                                        'comments': 0, 'shares': 0,
                                        'source_site': 'trends.google.com', 'text_snippet': text,
                                        'metadata': {'query': title, 'traffic': traffic},
                                        'engagement_likes': 0
                                    }
                                    pid = store_post(conn, data)
                                    if pid:
                                        stored += 1
                                        store_raw_signal(conn, data)
                    except json.JSONDecodeError:
                        pass
                url2 = f"https://trends.google.com/trends/api/autocomplete/{quote_plus(query)}?hl=en-IN"
                resp2 = safe_get(url2)
                if resp2:
                    try:
                        td = resp2.text
                        if td.startswith(')]}'):
                            td = td[4:]
                        auto = json.loads(td)
                        for topic in auto.get('default',{}).get('topics',[]):
                            found += 1
                            mid = topic.get('mid','')
                            title = topic.get('title','')
                            ttype = topic.get('type','')
                            text = f"Related trend: {title} ({ttype})"
                            data = {
                                'platform': 'GoogleTrends', 'url': f'https://trends.google.com/trends/explore?q={quote_plus(title)}&geo=IN',
                                'author': '', 'text': text, 'likes': 0,
                                'comments': 0, 'shares': 0,
                                'source_site': 'trends.google.com', 'text_snippet': text,
                                'metadata': {'mid': mid, 'type': ttype, 'query': query},
                                'engagement_likes': 0
                            }
                            pid = store_post(conn, data)
                            if pid:
                                stored += 1
                                store_raw_signal(conn, data)
                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                log.warning(f"Trends error: {e}")
            time.sleep(2)
    finally:
        put_conn(conn)
    log.info(f"[Google Trends Agent] found={found} stored={stored} leads={leads}")
    return {'found': found, 'stored': stored, 'leads': leads}

# ============================================================
# AGENT 6: TRAVEL PLATFORMS (MakeMyTrip, Booking.com via search)
# ============================================================
def agent_travel_platforms():
    """Collect from MakeMyTrip, Booking, Goibibo via DuckDuckGo."""
    log.info("[Travel Platforms Agent] Starting...")
    found = stored = leads = 0
    conn = get_conn()
    searches = [
        ('site:makemytrip.com Nashik wine', 'MakeMyTrip'),
        ('site:booking.com Nashik vineyard', 'Booking.com'),
        ('site:goibibo.com Nashik wine tourism', 'Goibibo'),
        ('site:makemytrip.com Nashik vineyard resort', 'MakeMyTrip'),
        ('site:booking.com Sula vineyard Nashik', 'Booking.com'),
    ]
    try:
        for search_q, platform in searches:
            if shutdown_flag: break
            try:
                url = f"https://html.duckduckgo.com/html/?q={quote_plus(search_q)}"
                resp = safe_get(url)
                if not resp: continue
                soup = BeautifulSoup(resp.text, 'html.parser')
                for r in soup.select('.result__body')[:6]:
                    found += 1
                    title_el = r.select_one('.result__title a')
                    snippet_el = r.select_one('.result__snippet')
                    if not title_el: continue
                    title = title_el.get_text(strip=True)
                    link = title_el.get('href','')
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ''
                    text = f"{title}. {snippet}"
                    data = {
                        'platform': platform, 'url': link,
                        'author': '', 'text': text, 'likes': 0,
                        'comments': 0, 'shares': 0,
                        'source_site': platform.lower().replace('.com','').replace(' ',''),
                        'text_snippet': text,
                        'metadata': {'query': search_q, 'platform': platform},
                        'engagement_likes': 0
                    }
                    pid = store_post(conn, data)
                    if pid:
                        stored += 1
                        store_raw_signal(conn, data)
                        if compute_relevance(text) >= 50:
                            store_lead(conn, pid, data)
                            leads += 1
            except Exception as e:
                log.warning(f"Travel platform error: {e}")
            time.sleep(3)
    finally:
        put_conn(conn)
    log.info(f"[Travel Platforms Agent] found={found} stored={stored} leads={leads}")
    return {'found': found, 'stored': stored, 'leads': leads}

# ============================================================
# AGENT 7: GOOGLE NEWS / RSS FEEDS
# ============================================================
def agent_news():
    """Collect news articles about Nashik wine tourism from Google News RSS."""
    log.info("[News Agent] Starting...")
    found = stored = leads = 0
    conn = get_conn()
    news_queries = ['Nashik wine tourism', 'Nashik vineyard', 'India wine industry', 'Sula vineyards']
    try:
        for query in news_queries:
            if shutdown_flag: break
            try:
                rss_url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-IN&gl=IN&ceid=IN:en"
                resp = safe_get(rss_url)
                if not resp: continue
                soup = BeautifulSoup(resp.text, 'xml')
                items = soup.find_all('item')
                for item in items[:8]:
                    found += 1
                    title = item.find('title').get_text(strip=True) if item.find('title') else ''
                    link = item.find('link').get_text(strip=True) if item.find('link') else ''
                    desc = item.find('description').get_text(strip=True) if item.find('description') else ''
                    pub_date = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ''
                    source = item.find('source').get_text(strip=True) if item.find('source') else ''
                    text = f"{title}. {desc[:200]}"
                    data = {
                        'platform': 'Google News', 'url': link,
                        'author': source, 'text': text, 'likes': 0,
                        'comments': 0, 'shares': 0,
                        'source_site': 'news.google.com', 'text_snippet': text,
                        'metadata': {'query': query, 'pub_date': pub_date, 'source': source},
                        'engagement_likes': 0
                    }
                    pid = store_post(conn, data)
                    if pid:
                        stored += 1
                        store_raw_signal(conn, data)
                        if compute_relevance(text) >= 55:
                            store_lead(conn, pid, data)
                            leads += 1
            except Exception as e:
                log.warning(f"News error for '{query}': {e}")
            time.sleep(2)
    finally:
        put_conn(conn)
    log.info(f"[News Agent] found={found} stored={stored} leads={leads}")
    return {'found': found, 'stored': stored, 'leads': leads}

# ============================================================
# AGENT REGISTRY & ORCHESTRATOR
# ============================================================
AGENT_REGISTRY = [
    ('YouTube', agent_youtube),
    ('Search', agent_search),
    ('TripAdvisor', agent_tripadvisor),
    ('Quora', agent_quora),
    ('GoogleTrends', agent_google_trends),
    ('TravelPlatforms', agent_travel_platforms),
    ('News', agent_news),
]

def run_cycle():
    """Run all agents sequentially in one cycle."""
    log.info("=" * 60)
    log.info("CYCLE STARTING - Running all 7 platform agents")
    log.info("=" * 60)
    cycle_start = time.time()
    results = {}
    total_found = total_stored = total_leads = 0

    for name, agent_fn in AGENT_REGISTRY:
        if shutdown_flag:
            log.info("Shutdown requested, stopping cycle")
            break
        try:
            start = time.time()
            r = agent_fn()
            elapsed = time.time() - start
            r['time'] = f"{elapsed:.1f}"
            results[name] = r
            total_found += r.get('found', 0)
            total_stored += r.get('stored', 0)
            total_leads += r.get('leads', 0)
        except Exception as e:
            log.error(f"Agent {name} failed: {e}")
            log.error(traceback.format_exc())
            results[name] = {'found': 0, 'stored': 0, 'leads': 0, 'error': str(e)}

    cycle_time = time.time() - cycle_start

    # Store cycle run in collection_runs
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""INSERT INTO collection_runs
            (collector_type, status, posts_found, posts_stored, comments_collected,
            started_at, finished_at, metadata)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            ('browser_agent', 'completed', total_found, total_stored, 0,
            datetime.utcnow(), datetime.utcnow(),
            json.dumps({'results': {k: {kk: vv for kk, vv in v.items()} for k, v in results.items()}, 'cycle_seconds': cycle_time})))
        conn.commit()
        cur.close()
        put_conn(conn)
    except Exception as e:
        log.warning(f"Failed to store cycle run: {e}")

    log.info("=" * 60)
    log.info(f"CYCLE COMPLETE: {total_found} found, {total_stored} stored, {total_leads} leads in {cycle_time:.0f}s")
    for name, r in results.items():
        log.info(f"  {name}: found={r.get('found',0)} stored={r.get('stored',0)} leads={r.get('leads',0)} time={r.get('time','?')}s")
    log.info("=" * 60)
    return results

# ============================================================
# MAIN ENTRY POINT
# ============================================================
if __name__ == '__main__':
    log.info("VayaVia Browser Collector v3.0 starting...")
    log.info(f"Agents: {[n for n,_ in AGENT_REGISTRY]}")
    log.info(f"Cycle interval: {CYCLE_INTERVAL}s ({CYCLE_INTERVAL//60} min)")
    log.info("Mode: requests+BeautifulSoup (no Playwright/Chromium)")

    init_db_pool()

    while not shutdown_flag:
        try:
            run_cycle()
        except Exception as e:
            log.error(f"Cycle error: {e}")
            log.error(traceback.format_exc())

        if shutdown_flag:
            break
        log.info(f"Sleeping {CYCLE_INTERVAL}s until next cycle...")
        # Sleep in small increments for graceful shutdown
        for _ in range(CYCLE_INTERVAL):
            if shutdown_flag:
                break
            time.sleep(1)

    log.info("Browser Collector v3.0 shutdown complete.")
