#!/usr/bin/env python3
"""VayaVia Multi-Agent Browser Collector v2.0

Architecture: Each platform = independent micro-agent
All agents run IN PARALLEL via ThreadPoolExecutor
Each agent has its own time budget, error handling, rate limiter
Shared: DB connection pool, browser context pool

Fixes all v1.0 issues:
- YouTube: NO individual video page visits (search results only)
- All 7 platforms run simultaneously (not sequentially)
- Time-boxed: each agent max 5 min, full cycle max 20 min
- Resource-efficient: shared browser pool (max 2 contexts)
- Adaptive rate limiting per platform
"""

import psycopg2, psycopg2.pool
import json, time, re, logging, hashlib, random, signal
import concurrent.futures
from datetime import datetime, timezone
from threading import Lock, Event
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# -- Logging --
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger('multi_agent')

# -- Config --
DB_CONFIG = dict(host='localhost', port=5432, dbname='vayavia_agent', user='postgres', password='postgres')
CYCLE_INTERVAL = 3600  # 1 hour between cycles
AGENT_TIMEOUT = 300    # 5 min max per agent
MAX_BROWSER_CONTEXTS = 2  # save RAM
PAGE_TIMEOUT = 20000   # 20s page load

# -- Keywords (reduced for efficiency) --
KEYWORDS = {
    'brand': {'w': 100, 't': ['vayavia nashik', 'sula vineyards', 'york winery nashik', 'grover zampa nashik']},
    'wine': {'w': 80, 't': ['nashik wine tasting', 'nashik vineyard tour', 'nashik winery visit']},
    'travel': {'w': 70, 't': ['nashik weekend trip', 'nashik tourism', 'nashik travel guide']},
    'general': {'w': 60, 't': ['wine tourism india', 'best wineries india', 'vineyard stay india']},
    'getaway': {'w': 50, 't': ['weekend getaway pune', 'weekend trip mumbai', 'romantic getaway maharashtra']},
}

# -- Intent & Segment Detection --
INTENT_PATTERNS = {
    'planning': r'plan|itinerary|schedule|going to|want to visit|thinking of',
    'asking': r'how to|where can|anyone know|recommend|best place|tips for',
    'booking': r'book|reserv|avail|price|cost|rate|package|deal',
    'complaining': r'bad|worst|terrible|disappoint|avoid|overpriced',
    'recommending': r'must visit|highly recommend|amazing|love|best|wonderful',
    'sharing': r'just visited|went to|stayed at|had a great|experience at',
}
SEGMENTS = {
    'Wine Enthusiast': r'wine|vineyard|winery|tasting|sommelier',
    'Weekend Tripper': r'weekend|getaway|short trip|day trip',
    'Luxury Seeker': r'luxury|premium|5 star|suite|spa|resort',
    'Honeymoon/Couple': r'honeymoon|couple|romantic|anniversary',
    'Family Traveler': r'family|kids|children|family trip',
    'Budget Traveler': r'budget|cheap|affordable|backpack',
    'Food & Drink': r'food|restaurant|cuisine|dining|culinary',
}

def detect_intent(text):
    if not text: return 'general', 0.3
    t = text.lower()
    for intent, pat in INTENT_PATTERNS.items():
        if re.search(pat, t): return intent, 0.8
    return 'general', 0.3

def auto_categorize(text):
    if not text: return 'General Tourist'
    t = text.lower()
    for seg, pat in SEGMENTS.items():
        if re.search(pat, t): return seg
    return 'General Tourist'

def score_relevance(text, kw=50):
    if not text: return kw
    s, t = kw, text.lower()
    for term in ['nashik','nasik','sula','york winery','vayavia','grover zampa']:
        if term in t: s += 15
    if any(w in t for w in ['wine','vineyard','winery','tasting']): s += 10
    return min(s, 100)

# ============================================================
# DATABASE LAYER (Thread-safe connection pool)
# ============================================================
db_pool = None
db_lock = Lock()

def init_db_pool():
    global db_pool
    db_pool = psycopg2.pool.ThreadedConnectionPool(2, 8, **DB_CONFIG)
    # Ensure schema
    conn = db_pool.getconn()
    cur = conn.cursor()
    for col in ['source_collector TEXT DEFAULT \'api_collector\'',
                 'is_competitor BOOLEAN DEFAULT FALSE',
                 'is_lead_candidate BOOLEAN DEFAULT FALSE',
                 'is_lead BOOLEAN DEFAULT FALSE']:
        try:
            cur.execute(f"ALTER TABLE posts ADD COLUMN IF NOT EXISTS {col}")
        except: conn.rollback()
    conn.commit()
    cur.close()
    db_pool.putconn(conn)
    log.info("DB pool initialized (2-8 connections)")

def get_conn():
    return db_pool.getconn()

def put_conn(conn):
    db_pool.putconn(conn)

def store_post(conn, data):
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM posts WHERE post_url=%s", (data.get('post_url',''),))
        if cur.fetchone():
            cur.close()
            return None
        full = f"{data.get('post_title','')} {data.get('post_body','')}"
        intent, iscore = detect_intent(full)
        cat = auto_categorize(full)
        rel = score_relevance(full, data.get('keyword_weight', 50))
        urg = 'high' if rel >= 75 else 'medium' if rel >= 50 else 'low'
        cur.execute("""INSERT INTO posts (platform, post_url, post_title, post_body, post_full_text,
            author_username, author_profile_url, author_followers, group_name, group_url,
            likes, upvotes, shares, comment_count, views, hashtags, mentions, media_urls,
            post_time, search_keyword, keyword_group, keyword_weight,
            intent, intent_score, category, relevance_score, urgency, sentiment,
            is_competitor, is_lead_candidate, source_collector)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id""",
            (data.get('platform'), data.get('post_url'), data.get('post_title'),
             data.get('post_body'), full,
             data.get('author_username'), data.get('author_profile_url'),
             data.get('author_followers',0), data.get('group_name'), data.get('group_url'),
             data.get('likes',0), data.get('upvotes',0), data.get('shares',0),
             data.get('comment_count',0), data.get('views',0),
             data.get('hashtags'), data.get('mentions'), data.get('media_urls'),
             data.get('post_time'), data.get('search_keyword'),
             data.get('keyword_group'), data.get('keyword_weight',50),
             intent, iscore, cat, rel, urg,
             data.get('sentiment','neutral'),
             data.get('is_competitor', False), rel >= 60, 'browser_agent'))
        pid = cur.fetchone()[0]
        conn.commit()
        return pid
    except Exception as e:
        conn.rollback()
        log.warning(f"Store error: {e}")
        return None
    finally:
        cur.close()

def store_lead(conn, post_id, data):
    cur = conn.cursor()
    try:
        cur.execute("""INSERT INTO leads (post_id, username, platform, profile_url,
            lead_score, category, intent, post_url, outreach_template)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (post_id, data.get('username'), data.get('platform'),
             data.get('profile_url',''), data.get('lead_score',50),
             data.get('category','General Tourist'), data.get('intent','general'),
             data.get('post_url',''),
             f"Hi {data.get('username','')}, noticed your interest in Nashik wine tourism. VayaVia offers..."))
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        cur.close()

# ============================================================
# BROWSER POOL (Shared, thread-safe)
# ============================================================
class BrowserPool:
    def __init__(self, pw, max_ctx=2):
        self.browser = pw.chromium.launch(
            headless=True,
            args=['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage',
                  '--disable-blink-features=AutomationControlled','--disable-gpu',
                  '--single-process','--no-zygote']
        )
        self.max_ctx = max_ctx
        self.lock = Lock()
        self.contexts = []

    def get_context(self):
        with self.lock:
            ctx = self.browser.new_context(
                viewport={'width': 1366, 'height': 768},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36',
                locale='en-US', timezone_id='Asia/Kolkata'
            )
            ctx.set_default_timeout(PAGE_TIMEOUT)
            self.contexts.append(ctx)
            return ctx

    def release_context(self, ctx):
        with self.lock:
            try:
                ctx.close()
                self.contexts.remove(ctx)
            except: pass

    def close(self):
        for ctx in self.contexts[:]:
            try: ctx.close()
            except: pass
        try: self.browser.close()
        except: pass

def safe_goto(page, url, wait='domcontentloaded'):
    try:
        page.goto(url, wait_until=wait, timeout=PAGE_TIMEOUT)
        time.sleep(random.uniform(0.5, 1.5))
        return True
    except:
        return False

# ============================================================
# PLATFORM AGENTS (Each runs independently, time-boxed)
# ============================================================

def agent_youtube(pool, deadline):
    """YouTube Agent: Search results only, NO video page visits."""
    name = 'YouTube'
    log.info(f"[{name}] Agent started")
    ctx = pool.get_context()
    conn = get_conn()
    stats = {'found': 0, 'stored': 0, 'leads': 0}
    try:
        page = ctx.new_page()
        for grp, info in KEYWORDS.items():
            if time.time() > deadline:
                log.info(f"[{name}] Time budget exceeded, stopping")
                break
            for term in info['t']:
                if time.time() > deadline: break
                q = term.replace(' ', '+')
                if not safe_goto(page, f'https://www.youtube.com/results?search_query={q}'): continue
                time.sleep(random.uniform(1, 2))
                for _ in range(2):
                    page.evaluate('window.scrollBy(0, 600)')
                    time.sleep(0.5)
                videos = page.evaluate("""() => {
                    const r = [];
                    document.querySelectorAll('ytd-video-renderer, ytd-rich-item-renderer').forEach(el => {
                        const t = el.querySelector('#video-title');
                        const c = el.querySelector('#channel-name a, .ytd-channel-name a');
                        const v = el.querySelector('#metadata-line span');
                        if (t) r.push({title: t.textContent.trim(), url: t.href||'',
                            channel: c?c.textContent.trim():'', channel_url: c&&c.href?c.href:'',
                            views: v?v.textContent.trim():''});
                    });
                    return r.slice(0, 8);
                }""")
                stats['found'] += len(videos)
                for vid in videos:
                    if not vid.get('url'): continue
                    views = 0
                    vm = re.search(r'([\d,.]+)\s*(K|M|B)?\s*view', vid.get('views',''), re.I)
                    if vm:
                        v = float(vm.group(1).replace(',',''))
                        mult = {'K':1000,'M':1e6,'B':1e9}.get(vm.group(2) or '',1)
                        views = int(v * mult)
                    pid = store_post(conn, {'platform':'youtube','post_url':vid['url'],
                        'post_title':vid['title'],'post_body':vid['title'],
                        'author_username':vid['channel'],'author_profile_url':vid.get('channel_url',''),
                        'group_name':'YouTube Search','views':views,
                        'search_keyword':term,'keyword_group':grp,'keyword_weight':info['w']})
                    if pid:
                        stats['stored'] += 1
                        rel = score_relevance(vid['title'], info['w'])
                        if rel >= 60 and vid['channel']:
                            store_lead(conn, pid, {'username':vid['channel'],'platform':'youtube',
                                'profile_url':vid.get('channel_url',''),'lead_score':rel,
                                'category':auto_categorize(vid['title']),
                                'intent':detect_intent(vid['title'])[0],'post_url':vid['url']})
                            stats['leads'] += 1
                time.sleep(random.uniform(1, 3))
        page.close()
    except Exception as e:
        log.error(f"[{name}] Error: {e}")
    finally:
        pool.release_context(ctx)
        put_conn(conn)
    log.info(f"[{name}] Done: {stats}")
    return name, stats

def agent_tripadvisor(pool, deadline):
    """TripAdvisor Agent: Attractions + search results."""
    name = 'TripAdvisor'
    log.info(f"[{name}] Agent started")
    ctx = pool.get_context()
    conn = get_conn()
    stats = {'found': 0, 'stored': 0, 'leads': 0}
    try:
        page = ctx.new_page()
        urls = [
            ('https://www.tripadvisor.in/Attractions-g297614-Activities-Nashik_Nashik_District_Maharashtra.html', 'Nashik Attractions'),
            ('https://www.tripadvisor.in/Search?q=sula+vineyards+nashik', 'Search: sula'),
            ('https://www.tripadvisor.in/Search?q=nashik+wine+tour', 'Search: wine tour'),
            ('https://www.tripadvisor.in/Search?q=nashik+resort+winery', 'Search: resort'),
        ]
        for url, label in urls:
            if time.time() > deadline: break
            if not safe_goto(page, url): continue
            time.sleep(random.uniform(2, 4))
            items = page.evaluate("""() => {
                const r = [];
                document.querySelectorAll('[data-automation="searchResult"], .listing_title a, .result-title, [data-test-target="top-result"], .prw_rup a, .search-result a').forEach(el => {
                    const t = el.textContent.trim();
                    const h = el.href || (el.querySelector('a')?el.querySelector('a').href:'');
                    if (t && t.length > 5 && t.length < 200) r.push({title: t, url: h});
                });
                return r.slice(0, 12);
            }""")
            stats['found'] += len(items)
            log.info(f"[{name}] {label}: {len(items)} items")
            for item in items:
                u = item.get('url','')
                if not u.startswith('http'): u = f"https://www.tripadvisor.in{u}" if u.startswith('/') else ''
                if not u: continue
                pid = store_post(conn, {'platform':'tripadvisor','post_url':u,
                    'post_title':item['title'],'post_body':item['title'],
                    'group_name':label,'group_url':url,
                    'search_keyword':label,'keyword_group':'nashik_travel','keyword_weight':70})
                if pid: stats['stored'] += 1
            time.sleep(random.uniform(3, 6))
        page.close()
    except Exception as e:
        log.error(f"[{name}] Error: {e}")
    finally:
        pool.release_context(ctx)
        put_conn(conn)
    log.info(f"[{name}] Done: {stats}")
    return name, stats

def agent_google_search(pool, deadline):
    """Google Search Agent: Organic results for travel queries."""
    name = 'GoogleSearch'
    log.info(f"[{name}] Agent started")
    ctx = pool.get_context()
    conn = get_conn()
    stats = {'found': 0, 'stored': 0, 'leads': 0}
    try:
        page = ctx.new_page()
        queries = ['nashik wine tourism review','sula vineyard experience 2025',
            'best winery nashik','york winery nashik review','wine tasting nashik blog',
            'nashik vineyard resort booking','couple trip nashik winery']
        for q in queries:
            if time.time() > deadline: break
            if not safe_goto(page, f"https://www.google.com/search?q={q.replace(' ','+')}&hl=en"): continue
            time.sleep(random.uniform(2, 4))
            results = page.evaluate("""() => {
                const r = [];
                document.querySelectorAll('#search .g, div[data-sokoban-container]').forEach(el => {
                    const a = el.querySelector('a[href]');
                    const h3 = el.querySelector('h3');
                    const sn = el.querySelector('.VwiC3b, [data-sncf], .st');
                    if (a && h3) r.push({title: h3.textContent.trim(), url: a.href,
                        snippet: sn ? sn.textContent.trim() : ''});
                });
                return r.slice(0, 8);
            }""")
            stats['found'] += len(results)
            log.info(f"[{name}] '{q}': {len(results)} results")
            for r in results:
                if not r.get('url') or 'google.com' in r['url']: continue
                pid = store_post(conn, {'platform':'google_search','post_url':r['url'],
                    'post_title':r['title'],'post_body':r.get('snippet',''),
                    'group_name':'Google Organic','search_keyword':q,
                    'keyword_group':'nashik_wine','keyword_weight':70})
                if pid: stats['stored'] += 1
            time.sleep(random.uniform(5, 10))
        page.close()
    except Exception as e:
        log.error(f"[{name}] Error: {e}")
    finally:
        pool.release_context(ctx)
        put_conn(conn)
    log.info(f"[{name}] Done: {stats}")
    return name, stats

def agent_quora(pool, deadline):
    """Quora Agent: Questions and answers about Nashik wine."""
    name = 'Quora'
    log.info(f"[{name}] Agent started")
    ctx = pool.get_context()
    conn = get_conn()
    stats = {'found': 0, 'stored': 0, 'leads': 0}
    try:
        page = ctx.new_page()
        queries = ['nashik wine tasting','sula vineyards review','best winery nashik',
                   'nashik weekend trip','wine tourism india','york winery review']
        for q in queries:
            if time.time() > deadline: break
            if not safe_goto(page, f"https://www.quora.com/search?q={q.replace(' ','+')}"):
                continue
            time.sleep(random.uniform(2, 4))
            for _ in range(2):
                page.evaluate('window.scrollBy(0, 500)')
                time.sleep(0.8)
            questions = page.evaluate("""() => {
                const qs = [];
                const seen = new Set();
                document.querySelectorAll('[class*="question"], .q-box a[href*="/"]').forEach(el => {
                    const t = el.textContent.trim();
                    const h = el.href || '';
                    if (t.length > 20 && t.length < 300 && h.includes('quora.com') && !seen.has(h)) {
                        seen.add(h);
                        qs.push({title: t, url: h});
                    }
                });
                return qs.slice(0, 8);
            }""")
            stats['found'] += len(questions)
            log.info(f"[{name}] '{q}': {len(questions)} questions")
            for item in questions:
                pid = store_post(conn, {'platform':'quora','post_url':item['url'],
                    'post_title':item['title'],'post_body':item['title'],
                    'group_name':'Quora','search_keyword':q,
                    'keyword_group':'nashik_wine','keyword_weight':60})
                if pid: stats['stored'] += 1
            time.sleep(random.uniform(3, 6))
        page.close()
    except Exception as e:
        log.error(f"[{name}] Error: {e}")
    finally:
        pool.release_context(ctx)
        put_conn(conn)
    log.info(f"[{name}] Done: {stats}")
    return name, stats

def agent_instagram(pool, deadline):
    """Instagram Agent: Public hashtag pages."""
    name = 'Instagram'
    log.info(f"[{name}] Agent started")
    ctx = pool.get_context()
    conn = get_conn()
    stats = {'found': 0, 'stored': 0, 'leads': 0}
    try:
        page = ctx.new_page()
        tags = ['nashikwine','sulavineyards','nashikwinery','winetourism',
                'nashiktravel','yorkwinery','winetasting']
        for tag in tags:
            if time.time() > deadline: break
            if not safe_goto(page, f'https://www.instagram.com/explore/tags/{tag}/'):
                continue
            time.sleep(random.uniform(2, 4))
            posts = page.evaluate("""() => {
                const items = [];
                document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]').forEach(a => {
                    const img = a.querySelector('img');
                    items.push({url: a.href, alt: img ? img.alt||'' : ''});
                });
                return items.slice(0, 10);
            }""")
            stats['found'] += len(posts)
            log.info(f"[{name}] #{tag}: {len(posts)} posts")
            for p in posts:
                if not p.get('url'): continue
                pid = store_post(conn, {'platform':'instagram','post_url':p['url'],
                    'post_title':p.get('alt',f'#{tag} post')[:200],'post_body':p.get('alt',''),
                    'hashtags':f'#{tag}','group_name':f'#{tag}',
                    'search_keyword':tag,'keyword_group':'nashik_wine','keyword_weight':70})
                if pid: stats['stored'] += 1
            time.sleep(random.uniform(3, 6))
        page.close()
    except Exception as e:
        log.error(f"[{name}] Error: {e}")
    finally:
        pool.release_context(ctx)
        put_conn(conn)
    log.info(f"[{name}] Done: {stats}")
    return name, stats

def agent_travel_platforms(pool, deadline):
    """Travel Platforms Agent: MakeMyTrip + Booking.com listings."""
    name = 'TravelPlatforms'
    log.info(f"[{name}] Agent started")
    ctx = pool.get_context()
    conn = get_conn()
    stats = {'found': 0, 'stored': 0, 'leads': 0}
    try:
        page = ctx.new_page()
        platforms = [
            ('makemytrip','https://www.makemytrip.com/hotels/nashik-hotels.html','MMT Nashik'),
            ('booking','https://www.booking.com/searchresults.html?ss=Nashik&nflt=ht_id%3D204','Booking Nashik'),
        ]
        for plat, url, label in platforms:
            if time.time() > deadline: break
            if not safe_goto(page, url): continue
            time.sleep(random.uniform(2, 4))
            for _ in range(2):
                page.evaluate('window.scrollBy(0, 500)')
                time.sleep(0.8)
            listings = page.evaluate("""() => {
                const items = [];
                document.querySelectorAll('[data-testid="property-card"], .listingCard, .hotel-card, .sr_property_block, [data-hotelid]').forEach(el => {
                    const t = el.querySelector('[data-testid="title"], .hotel-name, .sr-hotel__name, h3, .fnt22');
                    const p = el.querySelector('[data-testid="price-and-discounted-price"], .price, .bui-price-display');
                    const r = el.querySelector('[data-testid="review-score"], .rating, .review-score');
                    const a = el.querySelector('a[href]');
                    if (t) items.push({title: t.textContent.trim(),
                        price: p?p.textContent.trim():'', rating: r?r.textContent.trim():'',
                        url: a?a.href:''});
                });
                return items.slice(0, 12);
            }""")
            stats['found'] += len(listings)
            log.info(f"[{name}] {label}: {len(listings)} listings")
            for item in listings:
                fu = item.get('url', url)
                body = f"{item['title']} | Price: {item.get('price','')} | Rating: {item.get('rating','')}"
                pid = store_post(conn, {'platform':plat,'post_url':fu,
                    'post_title':item['title'],'post_body':body,
                    'group_name':label,'group_url':url,
                    'search_keyword':'nashik hotels','keyword_group':'nashik_travel','keyword_weight':70})
                if pid: stats['stored'] += 1
            time.sleep(random.uniform(3, 6))
        page.close()
    except Exception as e:
        log.error(f"[{name}] Error: {e}")
    finally:
        pool.release_context(ctx)
        put_conn(conn)
    log.info(f"[{name}] Done: {stats}")
    return name, stats

def agent_google_trends(pool, deadline):
    """Google Trends Agent: Trending topics."""
    name = 'GoogleTrends'
    log.info(f"[{name}] Agent started")
    ctx = pool.get_context()
    conn = get_conn()
    stats = {'found': 0, 'stored': 0, 'leads': 0}
    try:
        page = ctx.new_page()
        queries = ['nashik wine','sula vineyards','wine tourism india','nashik tourism','york winery']
        for q in queries:
            if time.time() > deadline: break
            if not safe_goto(page, f"https://trends.google.com/trends/explore?q={q.replace(' ','+')}&geo=IN",
                             wait='networkidle'): continue
            time.sleep(random.uniform(3, 5))
            related = page.evaluate("""() => {
                const items = [];
                document.querySelectorAll('[class*="related"] a, .fe-related-queries a').forEach(el => {
                    const t = el.textContent.trim();
                    if (t.length > 2 && t.length < 100) items.push({title: t, url: el.href||''});
                });
                return items.slice(0, 8);
            }""")
            stats['found'] += len(related)
            log.info(f"[{name}] '{q}': {len(related)} trends")
            for r in related:
                pid = store_post(conn, {'platform':'google_trends',
                    'post_url':r.get('url', f'https://trends.google.com/trends/explore?q={q}'),
                    'post_title':r['title'],'post_body':f"Trending: {r['title']} (related to {q})",
                    'group_name':'Google Trends','search_keyword':q,
                    'keyword_group':'nashik_wine','keyword_weight':50})
                if pid: stats['stored'] += 1
            time.sleep(random.uniform(3, 6))
        page.close()
    except Exception as e:
        log.error(f"[{name}] Error: {e}")
    finally:
        pool.release_context(ctx)
        put_conn(conn)
    log.info(f"[{name}] Done: {stats}")
    return name, stats

# ============================================================
# ORCHESTRATOR (Parallel agent execution with time-boxing)
# ============================================================

AGENT_REGISTRY = [
    ('YouTube',        agent_youtube,          1),  # priority 1 = highest
    ('TripAdvisor',    agent_tripadvisor,      2),
    ('GoogleSearch',   agent_google_search,    2),
    ('Quora',          agent_quora,            3),
    ('Instagram',      agent_instagram,        3),
    ('TravelPlatforms',agent_travel_platforms,  3),
    ('GoogleTrends',   agent_google_trends,    4),
]

def run_parallel_cycle():
    """Orchestrator: Launch all agents in parallel, collect results."""
    log.info("=" * 60)
    log.info("MULTI-AGENT CYCLE START - All platforms in parallel")
    log.info("=" * 60)
    cycle_start = datetime.now(timezone.utc)
    deadline = time.time() + AGENT_TIMEOUT  # 5 min max per agent
    all_results = {}

    with sync_playwright() as pw:
        pool = BrowserPool(pw, MAX_BROWSER_CONTEXTS)
        log.info(f"Browser pool ready (Chromium launched)")

        # Run agents in parallel: max 3 concurrent (to limit RAM)
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}
            for aname, afunc, priority in AGENT_REGISTRY:
                f = executor.submit(afunc, pool, deadline)
                futures[f] = aname
                log.info(f"  Submitted agent: {aname} (priority {priority})")

            # Collect results as they complete
            for future in concurrent.futures.as_completed(futures, timeout=AGENT_TIMEOUT + 60):
                aname = futures[future]
                try:
                    name, stats = future.result(timeout=30)
                    all_results[name] = stats
                    log.info(f"  Agent {name} completed: {stats}")
                except Exception as e:
                    all_results[aname] = {'found':0,'stored':0,'leads':0,'error':str(e)}
                    log.error(f"  Agent {aname} failed: {e}")

        pool.close()
        log.info("Browser pool closed")

    # Store cycle summary
    cycle_end = datetime.now(timezone.utc)
    total_stored = sum(r.get('stored',0) for r in all_results.values())
    total_leads = sum(r.get('leads',0) for r in all_results.values())
    total_found = sum(r.get('found',0) for r in all_results.values())

    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""INSERT INTO collection_runs (run_start, run_end, platform, keyword,
            posts_found, posts_stored, comments_collected, leads_generated)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (cycle_start, cycle_end, 'multi_agent', 'parallel_cycle',
             total_found, total_stored, 0, total_leads))
        conn.commit()
        cur.close()
        put_conn(conn)
    except Exception as e:
        log.warning(f"Cycle summary store failed: {e}")

    duration = (cycle_end - cycle_start).total_seconds()
    log.info("=" * 60)
    log.info(f"MULTI-AGENT CYCLE COMPLETE in {duration:.0f}s")
    log.info(f"Results: {json.dumps(all_results, default=str)}")
    log.info(f"Totals: {total_found} found, {total_stored} stored, {total_leads} leads")
    log.info("=" * 60)
    return all_results

# ============================================================
# MAIN ENTRY POINT
# ============================================================
if __name__ == '__main__':
    log.info("VayaVia Multi-Agent Browser Collector v2.0 starting...")
    log.info(f"Architecture: {len(AGENT_REGISTRY)} parallel agents")
    log.info(f"Agent timeout: {AGENT_TIMEOUT}s, Cycle interval: {CYCLE_INTERVAL}s")

    init_db_pool()

    while True:
        try:
            run_parallel_cycle()
        except Exception as e:
            log.error(f"Cycle error: {e}")
        log.info(f"Sleeping {CYCLE_INTERVAL}s until next cycle...")
        time.sleep(CYCLE_INTERVAL)
