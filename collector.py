#!/usr/bin/env python3
"""VayaVia Demand Engine v5.0 - Deep Collection Architecture

FLOW (same for ALL platforms):
1. Go to platform (Reddit, Twitter, YouTube, etc.)
2. Search with keywords + hooks
3. For each result, collect DEEP data:
   - Post full content / title / body
   - Author username + profile info
   - Post URL (direct link)
   - All comments (text + authors)
   - Post intent (asking, sharing, complaining, recommending, planning)
   - Engagement (likes, upvotes, shares, comment count)
   - Post timestamp (when it was posted)
   - Collection timestamp (when we scraped it)
   - Group/subreddit/channel name
   - Hashtags, mentions, media links
4. Auto-categorize into segments
5. Score relevance + urgency
6. Generate leads from high-intent posts
7. Store everything in PostgreSQL
"""

import psycopg2, requests, json, time, re, logging, hashlib
import os, smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
import feedparser
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

try:
    from textblob import TextBlob
    HAS_TEXTBLOB = True
except ImportError:
    HAS_TEXTBLOB = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('/tmp/collector.log')]
)
log = logging.getLogger('collector')

# ============================================================
# CONFIG
# ============================================================
DB = dict(dbname='vayavia_agent', user='postgres', password='postgres', host='localhost')
CYCLE_INTERVAL = 1800  # 30 min
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'

# ============================================================
# KEYWORD STRATEGY ENGINE
# Each keyword group has: terms, hooks (question patterns), platforms
# ============================================================
KEYWORD_STRATEGY = {
    'direct_brand': {
        'terms': ['vayavia', 'vaya via', 'vaya-via'],
        'weight': 100,
        'description': 'Direct brand mentions'
    },
    'nashik_wine_specific': {
        'terms': [
            'nashik wine', 'nashik winery', 'nashik vineyard',
            'sula vineyard', 'sula vineyards', 'york winery',
            'grover zampa nashik', 'wine tasting nashik',
            'nashik wine tour', 'nashik wine tourism',
            'nashik vineyard stay', 'nashik winery tour'
        ],
        'weight': 80,
        'description': 'Nashik wine tourism specific'
    },
    'nashik_travel': {
        'terms': [
            'nashik weekend getaway', 'nashik resort',
            'nashik trip', 'nashik travel', 'nashik hotel',
            'nashik stay', 'nashik things to do',
            'nashik itinerary', 'nashik visit',
            'pune to nashik', 'mumbai to nashik trip'
        ],
        'weight': 60,
        'description': 'Nashik travel intent'
    },
    'wine_tourism_india': {
        'terms': [
            'wine tourism india', 'indian wine', 'indian winery',
            'maharashtra wine', 'wine country india',
            'vineyard stay india', 'wine tasting india'
        ],
        'weight': 50,
        'description': 'Wine tourism in India general'
    },
    'weekend_getaway': {
        'terms': [
            'weekend getaway mumbai', 'weekend getaway pune',
            'short trip from mumbai', 'short trip from pune',
            'couples getaway maharashtra', 'family trip maharashtra',
            'road trip maharashtra'
        ],
        'weight': 40,
        'description': 'Weekend trip seekers from nearby cities'
    },
    'hooks_questions': {
        'terms': [
            'where to go for wine tasting',
            'best vineyard stay in india',
            'suggest wine tour',
            'planning trip to nashik',
            'recommend nashik',
            'honeymoon nashik',
            'corporate offsite nashik'
        ],
        'weight': 70,
        'description': 'Question/planning hooks - high intent'
    }
}

# Search queries built from strategy (platform-adapted)
def build_search_queries(platform='reddit'):
    queries = []
    for group_name, group in KEYWORD_STRATEGY.items():
        for term in group['terms']:
            queries.append({
                'term': term,
                'weight': group['weight'],
                'group': group_name,
                'description': group['description']
            })
    # Sort by weight (highest first)
    queries.sort(key=lambda x: x['weight'], reverse=True)
    return queries

# ============================================================
# INTENT DETECTION ENGINE
# ============================================================
INTENT_PATTERNS = {
    'planning': ['planning to', 'want to visit', 'thinking of going', 'looking for', 'suggest', 'recommend', 'any tips', 'itinerary', 'how to reach', 'best time to visit', 'should i go'],
    'asking': ['has anyone', 'is it worth', 'how is', 'what about', 'anyone been to', 'reviews of', 'experience at', 'opinions on', 'which is better'],
    'recommending': ['must visit', 'highly recommend', 'loved it', 'amazing experience', 'you should go', 'best place', 'dont miss', 'go for it'],
    'complaining': ['worst', 'terrible', 'waste of', 'overpriced', 'not worth', 'disappointed', 'avoid', 'bad experience', 'rip off', 'scam'],
    'sharing': ['just visited', 'back from', 'went to', 'had a great time', 'posting about', 'my trip to', 'photos from', 'experience at'],
    'booking': ['booking', 'reservation', 'availability', 'price for', 'cost of', 'package for', 'offer on', 'discount', 'deal on']
}

def detect_intent(text):
    t = text.lower()
    scores = {}
    for intent, patterns in INTENT_PATTERNS.items():
        scores[intent] = sum(1 for p in patterns if p in t)
    if max(scores.values()) == 0:
        return 'general', 0
    best = max(scores, key=scores.get)
    return best, scores[best]

# ============================================================
# AUTO-CATEGORIZATION
# ============================================================
CATEGORIES = {
    'Wine Enthusiast': ['wine', 'vineyard', 'winery', 'sula', 'york', 'grover', 'tasting', 'sommelier', 'grape', 'vintage', 'cellar'],
    'Weekend Tripper': ['weekend', 'getaway', 'escape', 'break', 'short trip', 'day trip', 'road trip'],
    'Luxury Seeker': ['luxury', 'premium', 'resort', '5 star', 'spa', 'fine dining', 'boutique', 'villa'],
    'Honeymoon/Couple': ['honeymoon', 'couple', 'romantic', 'anniversary', 'wedding', 'proposal'],
    'Family Traveler': ['family', 'kids', 'children', 'parents', 'family trip', 'family friendly'],
    'Culture Explorer': ['culture', 'heritage', 'temple', 'fort', 'history', 'local food', 'art', 'festival'],
    'Corporate/Group': ['corporate', 'team', 'offsite', 'conference', 'group', 'team building', 'retreat'],
    'Budget Traveler': ['budget', 'cheap', 'affordable', 'backpack', 'hostel', 'low cost'],
    'Food & Drink': ['food', 'restaurant', 'cuisine', 'dish', 'cafe', 'bar', 'brewery', 'cocktail']
}

def auto_categorize(text):
    t = text.lower()
    scores = {}
    for cat, keywords in CATEGORIES.items():
        scores[cat] = sum(1 for k in keywords if k in t)
    if max(scores.values()) == 0:
        return 'General Tourist'
    return max(scores, key=scores.get)

# ============================================================
# SUBREDDITS & PLATFORM TARGETS
# ============================================================
REDDIT_TARGETS = {
    'subreddits': [
        'india', 'mumbai', 'pune', 'travel', 'wine', 'IndiaTravel',
        'backpacking', 'solotravel', 'hotels', 'digitalnomad',
        'indiasocial', 'maharashtra', 'incredibleindia',
        'winemaking', 'foodtravel'
    ],
    'search_subs': ['all']  # Also search r/all with keywords
}

COMPETITORS = ['sula vineyards', 'york winery', 'grover zampa', 'fratelli wines', 'soma vine village', 'vallonne vineyards']

# ============================================================
# DATABASE
# ============================================================
def get_db():
    try:
        return psycopg2.connect(**DB)
    except Exception as e:
        log.error(f'DB connect failed: {e}')
        time.sleep(5)
        return psycopg2.connect(**DB)

def ensure_tables(conn):
    cur = conn.cursor()
    # Main posts table - stores DEEP data for every collected post
    cur.execute('''
    CREATE TABLE IF NOT EXISTS posts (
        id SERIAL PRIMARY KEY,
        platform TEXT NOT NULL,
        post_url TEXT UNIQUE NOT NULL,
        post_title TEXT,
        post_body TEXT,
        post_full_text TEXT,
        author_username TEXT,
        author_profile_url TEXT,
        author_followers INT DEFAULT 0,
        group_name TEXT,
        group_url TEXT,
        likes INT DEFAULT 0,
        upvotes INT DEFAULT 0,
        shares INT DEFAULT 0,
        comment_count INT DEFAULT 0,
        views INT DEFAULT 0,
        hashtags TEXT,
        mentions TEXT,
        media_urls TEXT,
        post_time TIMESTAMP,
        collected_at TIMESTAMP DEFAULT NOW(),
        search_keyword TEXT,
        keyword_group TEXT,
        intent TEXT DEFAULT 'general',
        intent_score INT DEFAULT 0,
        category TEXT DEFAULT 'General Tourist',
        relevance_score INT DEFAULT 0,
        urgency TEXT DEFAULT 'low',
        sentiment TEXT DEFAULT 'neutral',
        sentiment_score FLOAT DEFAULT 0,
        competitor_mentioned TEXT,
        is_lead BOOLEAN DEFAULT FALSE,
        lead_score INT DEFAULT 0,
        notes TEXT
    )''')
    # Comments table - linked to posts
    cur.execute('''
    CREATE TABLE IF NOT EXISTS post_comments (
        id SERIAL PRIMARY KEY,
        post_id INT REFERENCES posts(id) ON DELETE CASCADE,
        comment_text TEXT,
        comment_author TEXT,
        comment_likes INT DEFAULT 0,
        comment_time TIMESTAMP,
        collected_at TIMESTAMP DEFAULT NOW(),
        intent TEXT,
        sentiment TEXT DEFAULT 'neutral'
    )''')
    # Leads table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS leads (
        id SERIAL PRIMARY KEY,
        post_id INT REFERENCES posts(id),
        username TEXT,
        platform TEXT,
        profile_url TEXT,
        lead_score INT,
        category TEXT,
        intent TEXT,
        post_url TEXT,
        outreach_template TEXT,
        status TEXT DEFAULT 'new',
        created_at TIMESTAMP DEFAULT NOW()
    )''')
    # Collection runs log
    cur.execute('''
    CREATE TABLE IF NOT EXISTS collection_runs (
        id SERIAL PRIMARY KEY,
        run_start TIMESTAMP,
        run_end TIMESTAMP,
        platform TEXT,
        keyword TEXT,
        posts_found INT DEFAULT 0,
        posts_stored INT DEFAULT 0,
        comments_stored INT DEFAULT 0,
        leads_generated INT DEFAULT 0,
        errors TEXT
    )''')
    conn.commit()
    log.info('Database tables ensured (v5.0 schema)')

def safe_request(url, timeout=15, retries=3, delay=5):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers={'User-Agent': UA}, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            log.warning(f'Request {url[:60]}: {e} (attempt {attempt+1})')
            time.sleep(delay * (attempt + 1))
    return None

def make_hash(text):
    return hashlib.md5(text.strip().lower()[:200].encode()).hexdigest()

def get_sentiment(text):
    if HAS_TEXTBLOB:
        try:
            pol = TextBlob(text).sentiment.polarity
            if pol > 0.1: return 'positive', round(pol, 2)
            elif pol < -0.1: return 'negative', round(pol, 2)
            return 'neutral', round(pol, 2)
        except: pass
    return 'neutral', 0.0

def score_relevance(text, keyword_weight=50):
    t = text.lower()
    score = keyword_weight
    for term in KEYWORD_STRATEGY.get('direct_brand', {}).get('terms', []):
        if term in t: score += 30
    for term in KEYWORD_STRATEGY.get('nashik_wine_specific', {}).get('terms', []):
        if term in t: score += 15
    comp = next((c for c in COMPETITORS if c in t), '')
    return min(100, score), comp

# ============================================================
# CORE: store_post - Universal post storage
# ============================================================
def store_post(conn, data):
    """Store a post with all deep data. Returns post_id or None."""
    cur = conn.cursor()
    try:
        cur.execute('SELECT id FROM posts WHERE post_url=%s', (data['post_url'],))
        if cur.fetchone():
            return None  # Already exists
        
        full_text = f"{data.get('post_title','')} {data.get('post_body','')}"
        intent, intent_sc = detect_intent(full_text)
        category = auto_categorize(full_text)
        sentiment, sent_sc = get_sentiment(full_text)
        relevance, comp = score_relevance(full_text, data.get('keyword_weight', 50))
        urgency = 'high' if relevance >= 70 else ('medium' if relevance >= 40 else 'low')
        
        cur.execute('''INSERT INTO posts (
            platform, post_url, post_title, post_body, post_full_text,
            author_username, author_profile_url, author_followers,
            group_name, group_url,
            likes, upvotes, shares, comment_count, views,
            hashtags, mentions, media_urls,
            post_time, search_keyword, keyword_group,
            intent, intent_score, category, relevance_score, urgency,
            sentiment, sentiment_score, competitor_mentioned,
            is_lead, lead_score
        ) VALUES (
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        ) RETURNING id''', (
            data.get('platform',''), data['post_url'],
            data.get('post_title','')[:500], data.get('post_body','')[:5000],
            full_text[:5000],
            data.get('author','')[:200], data.get('author_profile',''),
            data.get('author_followers', 0),
            data.get('group_name','')[:200], data.get('group_url',''),
            data.get('likes',0), data.get('upvotes',0),
            data.get('shares',0), data.get('comment_count',0),
            data.get('views',0),
            data.get('hashtags','')[:500], data.get('mentions','')[:500],
            data.get('media_urls','')[:1000],
            data.get('post_time'), data.get('search_keyword','')[:200],
            data.get('keyword_group',''),
            intent, intent_sc, category, relevance, urgency,
            sentiment, sent_sc, comp,
            relevance >= 60, relevance
        ))
        row = cur.fetchone()
        post_id = row[0] if row else None
        conn.commit()
        return post_id
    except Exception as e:
        log.warning(f'store_post error: {e}')
        try: conn.rollback()
        except: pass
        return None

def store_comment(conn, post_id, comment_data):
    """Store a comment linked to a post."""
    cur = conn.cursor()
    try:
        intent, _ = detect_intent(comment_data.get('text',''))
        sentiment, _ = get_sentiment(comment_data.get('text',''))
        cur.execute('''INSERT INTO post_comments (
            post_id, comment_text, comment_author, comment_likes,
            comment_time, intent, sentiment
        ) VALUES (%s,%s,%s,%s,%s,%s,%s)''', (
            post_id, comment_data.get('text','')[:2000],
            comment_data.get('author','')[:200],
            comment_data.get('likes',0),
            comment_data.get('time'),
            intent, sentiment
        ))
        conn.commit()
        return True
    except Exception as e:
        try: conn.rollback()
        except: pass
        return False

def store_lead(conn, post_id, data):
    cur = conn.cursor()
    try:
        cur.execute('SELECT id FROM leads WHERE post_id=%s AND username=%s', (post_id, data.get('username','')))
        if cur.fetchone(): return None
        cur.execute('''INSERT INTO leads (post_id, username, platform, profile_url, lead_score, category, intent, post_url, outreach_template)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (post_id, data.get('username',''), data.get('platform',''),
             data.get('profile_url',''), data.get('lead_score',0),
             data.get('category',''), data.get('intent',''),
             data.get('post_url',''), data.get('outreach','')))
        row = cur.fetchone()
        conn.commit()
        return row[0] if row else None
    except Exception as e:
        try: conn.rollback()
        except: pass
        return None

# ============================================================
# REDDIT DEEP COLLECTOR
# Flow: Search keywords -> Get posts -> For each post get comments
# ============================================================
def collect_reddit_deep(conn):
    log.info('=== Reddit Deep Collection ===')
    queries = build_search_queries('reddit')
    total_posts, total_stored, total_comments, total_leads = 0, 0, 0, 0
    
    # Step 1: Search each subreddit with each keyword
    for sub in REDDIT_TARGETS['subreddits'] + REDDIT_TARGETS['search_subs']:
        for q in queries[:15]:  # Top 15 keywords per sub
            try:
                term = q['term']
                url = f'https://www.reddit.com/r/{sub}/search.json?q={quote_plus(term)}&sort=new&t=week&limit=25'
                r = safe_request(url)
                if not r: continue
                data = r.json()
                posts = data.get('data', {}).get('children', [])
                
                for post in posts:
                    d = post.get('data', {})
                    title = d.get('title', '')
                    body = d.get('selftext', '')
                    author = d.get('author', '')
                    if author in ['[deleted]', 'AutoModerator', '']: continue
                    
                    permalink = d.get('permalink', '')
                    post_url = f'https://reddit.com{permalink}'
                    subreddit = d.get('subreddit', '')
                    created = d.get('created_utc', 0)
                    post_time = datetime.utcfromtimestamp(created) if created else None
                    
                    total_posts += 1
                    
                    # Store the post with DEEP data
                    post_id = store_post(conn, {
                        'platform': 'reddit',
                        'post_url': post_url,
                        'post_title': title,
                        'post_body': body,
                        'author': author,
                        'author_profile': f'https://reddit.com/u/{author}',
                        'group_name': f'r/{subreddit}',
                        'group_url': f'https://reddit.com/r/{subreddit}',
                        'upvotes': int(d.get('ups', 0)),
                        'comment_count': int(d.get('num_comments', 0)),
                        'likes': int(d.get('ups', 0)),
                        'shares': int(d.get('crossposts', []).__len__() if isinstance(d.get('crossposts'), list) else 0),
                        'post_time': post_time,
                        'search_keyword': term,
                        'keyword_group': q['group'],
                        'keyword_weight': q['weight'],
                        'hashtags': f'r/{subreddit}',
                        'media_urls': d.get('url', '') if d.get('is_video') or d.get('post_hint') == 'image' else ''
                    })
                    
                    if post_id:
                        total_stored += 1
                        
                        # Step 2: Fetch comments for this post
                        try:
                            comment_url = f'https://www.reddit.com{permalink}.json?limit=50'
                            cr = safe_request(comment_url)
                            if cr:
                                cdata = cr.json()
                                if len(cdata) > 1:
                                    comments = cdata[1].get('data', {}).get('children', [])
                                    for c in comments[:30]:
                                        cd = c.get('data', {})
                                        ct = cd.get('body', '')
                                        ca = cd.get('author', '')
                                        if not ct or ca in ['[deleted]', 'AutoModerator']: continue
                                        cc_time = cd.get('created_utc', 0)
                                        stored = store_comment(conn, post_id, {
                                            'text': ct,
                                            'author': ca,
                                            'likes': int(cd.get('ups', 0)),
                                            'time': datetime.utcfromtimestamp(cc_time) if cc_time else None
                                        })
                                        if stored: total_comments += 1
                            time.sleep(1)  # Rate limit
                        except Exception as e:
                            log.warning(f'Reddit comments error: {e}')
                        
                        # Step 3: Generate lead if high relevance
                        full_text = f'{title} {body}'
                        intent, _ = detect_intent(full_text)
                        rel, _ = score_relevance(full_text, q['weight'])
                        if rel >= 60 and author not in ['[deleted]', '']:
                            lid = store_lead(conn, post_id, {
                                'username': author,
                                'platform': 'reddit',
                                'profile_url': f'https://reddit.com/u/{author}',
                                'lead_score': rel,
                                'category': auto_categorize(full_text),
                                'intent': intent,
                                'post_url': post_url
                            })
                            if lid: total_leads += 1
                
                time.sleep(2)  # Rate limit between searches
            except Exception as e:
                log.error(f'Reddit r/{sub} "{q["term"]}" error: {e}')
                try: conn.rollback()
                except: pass
    
    log.info(f'Reddit: {total_posts} found, {total_stored} stored, {total_comments} comments, {total_leads} leads')
    return total_posts, total_stored, total_comments, total_leads

# ============================================================
# GOOGLE NEWS DEEP COLLECTOR
# ============================================================
def collect_news_deep(conn):
    log.info('=== Google News Deep Collection ===')
    total_posts, total_stored = 0, 0
    queries = build_search_queries('news')
    for q in queries[:20]:
        try:
            term = q['term']
            url = f'https://news.google.com/rss/search?q={quote_plus(term)}&hl=en-IN&gl=IN&ceid=IN:en'
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                link = entry.get('link', '')
                pub_date = entry.get('published_parsed')
                post_time = datetime(*pub_date[:6]) if pub_date else None
                source = entry.get('source', {}).get('title', 'Google News')
                total_posts += 1
                pid = store_post(conn, {
                    'platform': 'google_news',
                    'post_url': link,
                    'post_title': title,
                    'post_body': summary,
                    'author': source,
                    'group_name': source,
                    'post_time': post_time,
                    'search_keyword': term,
                    'keyword_group': q['group'],
                    'keyword_weight': q['weight']
                })
                if pid: total_stored += 1
            time.sleep(1)
        except Exception as e:
            log.warning(f'News "{q["term"]}" error: {e}')
            try: conn.rollback()
            except: pass
    log.info(f'News: {total_posts} found, {total_stored} stored')
    return total_posts, total_stored, 0, 0

# ============================================================
# WEATHER COLLECTOR
# ============================================================
def collect_weather(conn):
    log.info('=== Weather Collection ===')
    try:
        url = 'https://api.open-meteo.com/v1/forecast?latitude=19.9975&longitude=73.7898&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code&timezone=Asia/Kolkata&forecast_days=7'
        r = safe_request(url)
        if not r: return 0, 0, 0, 0
        data = r.json()
        current = data.get('current', {})
        daily = data.get('daily', {})
        temp = current.get('temperature_2m', 0)
        humidity = current.get('relative_humidity_2m', 0)
        wc = daily.get('weather_code', [])
        clear_weekend = all(c < 3 for c in wc[5:7]) if len(wc) >= 7 else False
        txt = f'Nashik: {temp}C, humidity {humidity}%, weekend clear: {clear_weekend}'
        pid = store_post(conn, {
            'platform': 'weather',
            'post_url': f'https://open-meteo.com/nashik/{datetime.now().date()}',
            'post_title': f'Nashik Weather {datetime.now().date()}',
            'post_body': txt,
            'author': 'open-meteo',
            'group_name': 'nashik_weather',
            'post_time': datetime.now(),
            'search_keyword': 'nashik weather',
            'keyword_group': 'weather',
            'keyword_weight': 40
        })
        log.info(f'Weather: {txt}')
        return 1, 1 if pid else 0, 0, 0
    except Exception as e:
        log.warning(f'Weather error: {e}')
        return 0, 0, 0, 0

# ============================================================
# YOUTUBE DEEP COLLECTOR
# ============================================================
def collect_youtube_deep(conn):
    log.info('=== YouTube Deep Collection ===')
    total_posts, total_stored = 0, 0
    queries = [q for q in build_search_queries('youtube') if q['weight'] >= 50][:10]
    for q in queries:
        try:
            term = q['term']
            url = f'https://www.youtube.com/results?search_query={quote_plus(term)}'
            r = safe_request(url)
            if not r: continue
            video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', r.text)[:5]
            titles = re.findall(r'"title":\{"runs":\[\{"text":"([^"]+)"', r.text)[:5]
            view_counts = re.findall(r'"viewCountText":\{"simpleText":"([^"]+)"', r.text)[:5]
            for i, vid in enumerate(video_ids):
                vurl = f'https://www.youtube.com/watch?v={vid}'
                vtitle = titles[i] if i < len(titles) else f'YouTube: {term}'
                views_str = view_counts[i] if i < len(view_counts) else '0'
                views = int(re.sub(r'[^0-9]', '', views_str) or 0)
                total_posts += 1
                pid = store_post(conn, {
                    'platform': 'youtube',
                    'post_url': vurl,
                    'post_title': vtitle,
                    'post_body': '',
                    'author': '',
                    'group_name': 'youtube',
                    'views': views,
                    'post_time': None,
                    'search_keyword': term,
                    'keyword_group': q['group'],
                    'keyword_weight': q['weight']
                })
                if pid: total_stored += 1
            time.sleep(2)
        except Exception as e:
            log.warning(f'YouTube "{q["term"]}" error: {e}')
            try: conn.rollback()
            except: pass
    log.info(f'YouTube: {total_posts} found, {total_stored} stored')
    return total_posts, total_stored, 0, 0

# ============================================================
# GOOGLE SEARCH COLLECTOR (TripAdvisor, Quora, Blogs, etc.)
# Same deep flow: search -> collect post data -> store
# ============================================================
def collect_via_google(conn, site_name, site_domain, queries_limit=8):
    log.info(f'=== {site_name} Collection via Google ===')
    total_posts, total_stored = 0, 0
    queries = [q for q in build_search_queries(site_name) if q['weight'] >= 40][:queries_limit]
    for q in queries:
        try:
            term = q['term']
            url = f'https://www.google.com/search?q=site:{site_domain}+{quote_plus(term)}&num=10'
            r = safe_request(url)
            if not r: continue
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                if site_domain in href:
                    txt = a.get_text(strip=True)
                    if len(txt) < 20: continue
                    total_posts += 1
                    pid = store_post(conn, {
                        'platform': site_name,
                        'post_url': href[:500],
                        'post_title': txt[:300],
                        'post_body': '',
                        'author': '',
                        'group_name': site_name,
                        'search_keyword': term,
                        'keyword_group': q['group'],
                        'keyword_weight': q['weight']
                    })
                    if pid: total_stored += 1
            time.sleep(3)
        except Exception as e:
            log.warning(f'{site_name} error: {e}')
            try: conn.rollback()
            except: pass
    log.info(f'{site_name}: {total_posts} found, {total_stored} stored')
    return total_posts, total_stored, 0, 0

# ============================================================
# BLOG/MEDIUM RSS COLLECTOR
# ============================================================
def collect_blogs_deep(conn):
    log.info('=== Blog Collection ===')
    total_posts, total_stored = 0, 0
    feeds = [
        'https://medium.com/feed/tag/nashik',
        'https://medium.com/feed/tag/wine-tourism',
        'https://medium.com/feed/tag/indian-wine',
    ]
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                title = entry.get('title', '')
                link = entry.get('link', '')
                summary = entry.get('summary', '')[:500]
                author = entry.get('author', '')
                pub = entry.get('published_parsed')
                post_time = datetime(*pub[:6]) if pub else None
                if len(title) < 10: continue
                total_posts += 1
                pid = store_post(conn, {
                    'platform': 'blog',
                    'post_url': link,
                    'post_title': title,
                    'post_body': summary,
                    'author': author,
                    'group_name': 'medium',
                    'post_time': post_time,
                    'search_keyword': 'blog rss',
                    'keyword_group': 'blogs',
                    'keyword_weight': 40
                })
                if pid: total_stored += 1
        except Exception as e:
            log.warning(f'Blog RSS error: {e}')
            try: conn.rollback()
            except: pass
    log.info(f'Blogs: {total_posts} found, {total_stored} stored')
    return total_posts, total_stored, 0, 0

# ============================================================
# MAIN CYCLE
# ============================================================
def run_cycle(conn):
    log.info('========== COLLECTION CYCLE START ==========')
    run_start = datetime.now()
    results = {}
    
    collectors = [
        ('reddit', collect_reddit_deep),
        ('google_news', collect_news_deep),
        ('weather', collect_weather),
        ('youtube', collect_youtube_deep),
        ('tripadvisor', lambda c: collect_via_google(c, 'tripadvisor', 'tripadvisor.com', 5)),
        ('quora', lambda c: collect_via_google(c, 'quora', 'quora.com', 5)),
        ('blogs', collect_blogs_deep),
        ('makemytrip', lambda c: collect_via_google(c, 'makemytrip', 'makemytrip.com', 3)),
        ('booking', lambda c: collect_via_google(c, 'booking', 'booking.com', 3)),
    ]
    
    for name, func in collectors:
        try:
            posts, stored, comments, leads = func(conn)
            results[name] = {'posts': posts, 'stored': stored, 'comments': comments, 'leads': leads}
        except Exception as e:
            log.error(f'{name} collector FAILED: {e}')
            results[name] = {'error': str(e)}
            try: conn.rollback()
            except: pass
    
    # Log the run
    try:
        cur = conn.cursor()
        total_p = sum(r.get('posts',0) for r in results.values() if isinstance(r.get('posts'), int))
        total_s = sum(r.get('stored',0) for r in results.values() if isinstance(r.get('stored'), int))
        total_c = sum(r.get('comments',0) for r in results.values() if isinstance(r.get('comments'), int))
        total_l = sum(r.get('leads',0) for r in results.values() if isinstance(r.get('leads'), int))
        cur.execute('INSERT INTO collection_runs (run_start, run_end, platform, keyword, posts_found, posts_stored, comments_stored, leads_generated) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
            (run_start, datetime.now(), 'all', 'full_cycle', total_p, total_s, total_c, total_l))
        conn.commit()
    except: pass
    
    log.info(f'========== CYCLE COMPLETE: {json.dumps({k: v for k,v in results.items()}, default=str)} ==========')
    return results

# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == '__main__':
    log.info('VayaVia Demand Engine v5.0 - Deep Collection starting...')
    conn = get_db()
    ensure_tables(conn)
    
    while True:
        try:
            run_cycle(conn)
            log.info(f'Sleeping {CYCLE_INTERVAL}s until next cycle...')
            time.sleep(CYCLE_INTERVAL)
        except KeyboardInterrupt:
            log.info('Shutting down...')
            break
        except Exception as e:
            log.error(f'Cycle error: {e}')
            try: conn.rollback()
            except: pass
            log.info('Retrying in 5 minutes...')
            time.sleep(300)
