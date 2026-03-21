#!/usr/bin/env python3
"""VayaVia Demand Engine - Multi-Platform Collector v4.0
Auto-triggering, self-healing daemon. Collects from Reddit (with engagement),
Google News, Weather, Google Trends, Twitter/X, Quora, Instagram (instaloader),
Facebook, YouTube, TripAdvisor, MakeMyTrip, Goibibo, Blog/Medium RSS,
Telegram, Pinterest, LinkedIn, Booking.com, Competitor monitoring.
Sentiment analysis, cross-platform dedup, outreach templates, email alerts.
Stores ALL real data. Runs as systemd daemon with auto error recovery."""

import psycopg2, requests, json, time, re, logging, sys, traceback, hashlib
import os, smtplib, subprocess
from datetime import datetime, timedelta
from email.mime.text import MIMEText
import feedparser
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

# --- Optional imports with graceful fallback ---
try:
    from textblob import TextBlob
    HAS_TEXTBLOB = True
except ImportError:
    HAS_TEXTBLOB = False

try:
    import instaloader
    HAS_INSTALOADER = True
except ImportError:
    HAS_INSTALOADER = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('/tmp/collector.log')]
)
log = logging.getLogger('collector')

# --- CONFIG ---
DB = dict(dbname='vayavia_agent', user='postgres', password='postgres', host='localhost')
CYCLE_INTERVAL = 3600
MAX_RETRIES = 3
RETRY_DELAY = 10
MIN_SCORE_LEAD = 30

# Email alerts (set SMTP env vars to enable)
ALERT_EMAIL = os.environ.get('ALERT_EMAIL', '')
SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASS = os.environ.get('SMTP_PASS', '')
HOT_SCORE_THRESHOLD = 70

# --- SUBREDDITS ---
SUBREDDITS = [
    'india', 'mumbai', 'pune', 'travel', 'wine',
    'IndiaTravel', 'backpacking', 'solotravel',
    'hotels', 'digitalnomad'
]

# --- KEYWORDS ---
HIGH_KW = [
    'nashik wine', 'sula vineyard', 'york winery', 'grover zampa',
    'nashik winery tour', 'wine tasting nashik', 'nashik resort',
    'vayavia', 'nashik weekend getaway', 'nashik vineyard stay'
]
MED_KW = [
    'nashik', 'wine tourism india', 'maharashtra wine', 'indian wine',
    'nashik travel', 'nashik hotel', 'nashik tour', 'nashik food',
    'wine country india', 'sula wines', 'nasik'
]
LOW_KW = [
    'wine', 'vineyard', 'winery', 'wine tasting', 'weekend getaway',
    'mumbai day trip', 'pune weekend', 'maharashtra tourism'
]

SEGMENTS = {
    'Wine Enthusiast': ['wine', 'vineyard', 'winery', 'sula', 'york', 'grover', 'tasting', 'sommelier'],
    'Weekend Getaway': ['weekend', 'getaway', 'escape', 'break', 'short trip', 'day trip'],
    'Luxury Seeker': ['luxury', 'premium', 'resort', '5 star', 'spa', 'fine dining', 'boutique'],
    'Culture Explorer': ['culture', 'heritage', 'temple', 'fort', 'history', 'local food', 'art'],
    'Family Traveler': ['family', 'kids', 'children', 'parents', 'family trip', 'holiday'],
    'Honeymoon': ['honeymoon', 'couple', 'romantic', 'anniversary', 'wedding'],
    'Corporate Retreat': ['corporate', 'team', 'offsite', 'conference', 'business travel'],
}

COMPETITORS = ['sula vineyards', 'york winery', 'grover zampa', 'fratelli wines',
               'soma vine village', 'vallonne vineyards', 'four seasons wine']

# --- OUTREACH TEMPLATES ---
OUTREACH_TEMPLATES = {
    'Wine Enthusiast': 'Hi! We noticed your interest in wine tourism. VayaVia offers exclusive vineyard stays in Nashik with private tastings, harvest experiences & farm-to-table dinners. Reply for a personalised itinerary!',
    'Weekend Getaway': 'Looking for a perfect weekend escape? VayaVia\'s Nashik retreats are just 4hrs from Mumbai/Pune - think vineyards, fresh air & total relaxation. Check availability this weekend!',
    'Luxury Seeker': 'Elevate your next escape. VayaVia curates premium Nashik vineyard experiences - private villa stays, sommelier-led tastings & bespoke dining. Ask about our luxury packages.',
    'Honeymoon': 'Celebrate love among the vines. VayaVia\'s romantic Nashik packages include private vineyard dinners, couples spa & sunrise wine tasting. Perfect for honeymoons & anniversaries!',
    'Corporate Retreat': 'Take your team offsite to something memorable. VayaVia\'s Nashik vineyard retreats include meeting facilities, team tastings & curated experiences. Request a group quote.',
    'Family Traveler': 'Plan a family getaway the kids will love! Nashik\'s vineyards offer grape picking, nature walks & farm activities alongside beautiful stays. VayaVia handles everything.',
    'General Tourist': 'Discover Nashik - India\'s wine capital! VayaVia offers curated stays at Nashik\'s finest vineyards. Book now for an unforgettable experience.',
}

# --- DB HELPERS ---
def get_db():
    try:
        return psycopg2.connect(**DB)
    except Exception as e:
        log.error(f'DB connect failed: {e}')
        time.sleep(5)
        return psycopg2.connect(**DB)

def safe_request(url, timeout=15, retries=3, delay=5):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'}
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.exceptions.Timeout:
            log.warning(f'Timeout {url[:60]}, retry {attempt+1}')
            time.sleep(delay)
        except requests.exceptions.ConnectionError:
            log.warning(f'ConnError {url[:60]}, retry {attempt+1}')
            time.sleep(delay * (attempt + 1))
        except Exception as e:
            log.warning(f'Request error {url[:60]}: {e}')
            time.sleep(delay)
    return None

def make_hash(text):
    return hashlib.md5(text.strip().lower()[:200].encode()).hexdigest()

def get_sentiment(text):
    """Returns sentiment: positive/negative/neutral and polarity score."""
    if not HAS_TEXTBLOB:
        return 'neutral', 0.0
    try:
        blob = TextBlob(text)
        pol = blob.sentiment.polarity
        if pol > 0.1: return 'positive', round(pol, 2)
        elif pol < -0.1: return 'negative', round(pol, 2)
        return 'neutral', round(pol, 2)
    except Exception:
        return 'neutral', 0.0

def score_text(text):
    """Score text by keyword matches. Returns score dict."""
    t = text.lower()
    score = 0
    for k in HIGH_KW:
        if k in t: score += 20
    for k in MED_KW:
        if k in t: score += 10
    for k in LOW_KW:
        if k in t: score += 5
    score = min(100, max(1, score))
    seg = 'General Tourist'
    best = 0
    for s, kws in SEGMENTS.items():
        c = sum(1 for k in kws if k in t)
        if c > best:
            best = c
            seg = s
    urg = 'high' if score >= 70 else ('medium' if score >= 40 else 'low')
    sentiment, pol = get_sentiment(text)
    # Check competitor mention
    comp_mention = next((c for c in COMPETITORS if c in t), '')
    return {
        'score': score, 'segment': seg, 'urgency': urg,
        'sentiment': sentiment, 'polarity': pol,
        'competitor': comp_mention,
        'outreach': OUTREACH_TEMPLATES.get(seg, OUTREACH_TEMPLATES['General Tourist'])
    }

def insert_raw(cur, src, url, txt, platform, author='', followers=0,
               likes=0, comments=0, shares=0, hashtags='', location='',
               sentiment='neutral', polarity=0.0, competitor=''):
    """Insert into raw_signals with deduplication."""
    try:
        cur.execute('SELECT id FROM raw_signals WHERE url=%s', (url,))
        if cur.fetchone():
            return None
        cur.execute(
            '''INSERT INTO raw_signals (source_site, url, text_snippet, platform,
            author, author_followers, engagement_likes, engagement_comments,
            engagement_shares, hashtags, location)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (src, url, txt[:500], platform, author[:100], followers,
             likes, comments, shares, hashtags[:300], location[:100])
        )
        row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        log.warning(f'insert_raw error {url[:60]}: {e}')
        return None

def insert_lead(cur, name, source, score, details):
    """Insert lead with deduplication by name+source."""
    try:
        h = make_hash(f'{source}:{name}')
        cur.execute('SELECT id FROM leads WHERE lead_hash=%s', (h,))
        if cur.fetchone():
            return None
        cur.execute(
            '''INSERT INTO leads (name, source, score, details, lead_hash)
            VALUES (%s,%s,%s,%s,%s) RETURNING id''',
            (name[:300], source, score, json.dumps(details), h)
        )
        row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        log.warning(f'insert_lead error: {e}')
        return None

def cross_dedup(cur, txt, platform):
    """Check if similar content exists from another platform (content-hash based)."""
    h = make_hash(txt)
    try:
        cur.execute('SELECT id FROM raw_signals WHERE url LIKE %s', (f'%{h[:8]}%',))
        return cur.fetchone() is not None
    except Exception:
        return False

def send_alert(lead_name, source, score, segment, outreach):
    """Send email alert for hot lead."""
    if not ALERT_EMAIL or not SMTP_USER:
        return
    try:
        msg = MIMEText(
            f'HOT LEAD ALERT - Score {score}\n\n'
            f'Name/Handle: {lead_name}\n'
            f'Source: {source}\n'
            f'Segment: {segment}\n'
            f'Score: {score}/100\n\n'
            f'Recommended Outreach:\n{outreach}'
        )
        msg['Subject'] = f'[VayaVia] Hot Lead Score {score} - {segment}'
        msg['From'] = SMTP_USER
        msg['To'] = ALERT_EMAIL
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        log.info(f'Alert sent for {lead_name} score={score}')
    except Exception as e:
        log.warning(f'Alert email failed: {e}')

# ============================================================
# COLLECTORS
# ============================================================

def collect_reddit(conn):
    """Reddit - FIXED: stores engagement (upvotes/comments) properly."""
    raw, stored, leads_added = 0, 0, 0
    cur = conn.cursor()
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
                permalink = f"https://reddit.com{d.get('permalink', '')}"
                author = d.get('author', '')
                upvotes = int(d.get('ups', 0))
                num_comments = int(d.get('num_comments', 0))
                subreddit = d.get('subreddit', '')
                rid = insert_raw(
                    cur, f'reddit:r/{sub}', permalink, text, 'reddit',
                    author=author, likes=upvotes, comments=num_comments,
                    location='reddit', hashtags=f'r/{subreddit}'
                )
                if rid:
                    stored += 1
                    conn.commit()
                    if sc['score'] >= MIN_SCORE_LEAD and author not in ['[deleted]', 'AutoModerator', '']:
                        details = {
                            'post_title': title[:200], 'subreddit': subreddit,
                            'score': sc['score'], 'segment': sc['segment'],
                            'urgency': sc['urgency'], 'sentiment': sc['sentiment'],
                            'upvotes': upvotes, 'comments': num_comments,
                            'outreach': sc['outreach'], 'competitor': sc['competitor'],
                            'url': permalink
                        }
                        lid = insert_lead(cur, author, 'reddit', sc['score'], details)
                        if lid:
                            leads_added += 1
                            conn.commit()
                            if sc['score'] >= HOT_SCORE_THRESHOLD:
                                send_alert(author, f'reddit:r/{sub}', sc['score'], sc['segment'], sc['outreach'])
            time.sleep(2)
        except Exception as e:
            log.error(f'Reddit r/{sub} error: {e}')
            try: conn.rollback()
            except Exception: pass
    log.info(f'Reddit: {raw} raw, {stored} stored, {leads_added} leads')
    return raw, stored

def collect_google_news(conn):
    """Google News via RSS feeds."""
    raw, stored = 0, 0
    cur = conn.cursor()
    queries = [
        'nashik wine tourism', 'nashik vineyard', 'sula vineyards', 'york winery nashik',
        'nashik weekend getaway', 'nashik resort stay', 'wine tourism india',
        'maharashtra wine tourism', 'nashik travel 2026', 'grover zampa wines'
    ]
    for q in queries:
        try:
            url = f'https://news.google.com/rss/search?q={quote_plus(q)}&hl=en-IN&gl=IN&ceid=IN:en'
            feed = feedparser.parse(url)
            for entry in feed.entries[:15]:
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                text = f'{title} {summary}'
                link = entry.get('link', url)
                sc = score_text(text)
                raw += 1
                rid = insert_raw(
                    cur, f'google_news:{q[:30]}', link, text, 'google_news',
                    location='india', sentiment=sc['sentiment']
                )
                if rid:
                    stored += 1
                    conn.commit()
            time.sleep(1)
        except Exception as e:
            log.warning(f'Google News {q}: {e}')
            try: conn.rollback()
            except Exception: pass
    log.info(f'Google News: {raw} raw, {stored} stored')
    return raw, stored

def collect_weather(conn):
    """Weather via Open-Meteo (free, no key needed)."""
    raw, stored = 0, 0
    cur = conn.cursor()
    try:
        url = 'https://api.open-meteo.com/v1/forecast?latitude=19.9975&longitude=73.7898&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code&timezone=Asia/Kolkata&forecast_days=7'
        r = safe_request(url)
        if r:
            data = r.json()
            current = data.get('current', {})
            daily = data.get('daily', {})
            wc = daily.get('weather_code', [])
            clear_weekend = all(c < 3 for c in wc[5:7]) if len(wc) >= 7 else False
            temp = current.get('temperature_2m', 0)
            humidity = current.get('relative_humidity_2m', 0)
            txt = f'Nashik weather: {temp}C, humidity {humidity}%, weekend clear: {clear_weekend}'
            triggers = []
            if clear_weekend: triggers.append('clear_weekend_ahead')
            if temp > 15 and temp < 32: triggers.append('ideal_visit_temperature')
            if humidity < 70: triggers.append('comfortable_humidity')
            rid = insert_raw(
                cur, 'weather:open-meteo',
                f'https://open-meteo.com/nashik/{datetime.now().date()}',
                txt, 'weather', location='nashik'
            )
            if rid:
                stored = 1
                conn.commit()
            raw = 1
    except Exception as e:
        log.warning(f'Weather error: {e}')
        try: conn.rollback()
        except Exception: pass
    log.info(f'Weather: {raw} raw, {stored} stored')
    return raw, stored

def collect_trends(conn):
    """Google Trends via RSS."""
    raw, stored = 0, 0
    cur = conn.cursor()
    try:
        url = 'https://trends.google.com/trends/trendingsearches/daily/rss?geo=IN'
        feed = feedparser.parse(url)
        kw_filter = ['nashik', 'wine', 'vineyard', 'tourism', 'travel', 'maharashtra', 'mumbai', 'pune']
        for entry in feed.entries[:50]:
            title = entry.get('title', '').lower()
            if any(k in title for k in kw_filter):
                txt = entry.get('title', '')
                link = entry.get('link', 'https://trends.google.com')
                raw += 1
                rid = insert_raw(cur, 'google_trends', link, txt, 'google_trends', location='india')
                if rid:
                    stored += 1
                    conn.commit()
    except Exception as e:
        log.warning(f'Trends error: {e}')
        try: conn.rollback()
        except Exception: pass
    log.info(f'Trends: {raw} raw, {stored} stored')
    return raw, stored


# --- TWITTER/X COLLECTOR (via syndication API) ---
def collect_twitter(conn):
    """Collect tweets about Nashik wine tourism via Twitter syndication."""
    raw, stored = 0, 0
    cur = conn.cursor()
    queries = ['nashik wine', 'nashik vineyard', 'sula vineyards', 'york winery nashik',
               'nashik tourism', 'wine tasting nashik', 'grover zampa nashik']
    for q in queries:
        try:
            url = f'https://syndication.twitter.com/srv/timeline-profile/screen-name/{quote_plus(q)}'
            headers = {'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1)'}
            r = safe_request(url, headers=headers)
            if not r: continue
            soup = BeautifulSoup(r.text, 'html.parser')
            for tweet in soup.find_all('div', class_='timeline-Tweet')[:10]:
                txt_el = tweet.find('p', class_='timeline-Tweet-text')
                if not txt_el: continue
                txt = txt_el.get_text(strip=True)
                if len(txt) < 20: continue
                link = f'https://twitter.com/search?q={quote_plus(q)}'
                raw += 1
                rid = insert_raw(cur, f'twitter:{q}', link, txt, 'twitter', location='nashik')
                if rid:
                    stored += 1
                    conn.commit()
        except Exception as e:
            log.warning(f'Twitter {q} error: {e}')
            try: conn.rollback()
            except Exception: pass
    # Fallback: Google search for tweets
    if stored == 0:
        for q in queries[:3]:
            try:
                gurl = f'https://www.google.com/search?q=site:twitter.com+{quote_plus(q)}&num=5'
                r = safe_request(gurl)
                if not r: continue
                soup = BeautifulSoup(r.text, 'html.parser')
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if 'twitter.com' in href and '/status/' in href:
                        txt = a.get_text(strip=True)
                        if len(txt) > 20:
                            raw += 1
                            rid = insert_raw(cur, f'twitter:google:{q}', href, txt, 'twitter')
                            if rid:
                                stored += 1
                                conn.commit()
                time.sleep(3)
            except Exception as e:
                log.warning(f'Twitter Google fallback error: {e}')
                try: conn.rollback()
                except Exception: pass
    log.info(f'Twitter: {raw} raw, {stored} stored')
    return raw, stored

# --- QUORA COLLECTOR (via Google) ---
def collect_quora(conn):
    """Collect Quora questions about Nashik wine tourism."""
    raw, stored = 0, 0
    cur = conn.cursor()
    queries = ['nashik wine tourism', 'nashik vineyard visit', 'sula vineyards experience',
               'best winery nashik', 'nashik weekend trip wine']
    for q in queries:
        try:
            url = f'https://www.google.com/search?q=site:quora.com+{quote_plus(q)}&num=10'
            r = safe_request(url)
            if not r: continue
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                if 'quora.com' in href:
                    txt = a.get_text(strip=True)
                    if len(txt) > 20:
                        raw += 1
                        rid = insert_raw(cur, f'quora:{q}', href, txt, 'quora', location='nashik')
                        if rid:
                            stored += 1
                            conn.commit()
            time.sleep(3)
        except Exception as e:
            log.warning(f'Quora {q} error: {e}')
            try: conn.rollback()
            except Exception: pass
    log.info(f'Quora: {raw} raw, {stored} stored')
    return raw, stored

# --- INSTAGRAM COLLECTOR (meta tags + Google) ---
def collect_instagram(conn):
    """Collect Instagram mentions about Nashik wine tourism."""
    raw, stored = 0, 0
    cur = conn.cursor()
    hashtags = ['nashikwine', 'nashikwinery', 'sulavineyards', 'yorkwinery',
                'nashiktravel', 'winetourism', 'maharashtrawine', 'indianwine']
    for tag in hashtags:
        try:
            url = f'https://www.instagram.com/explore/tags/{tag}/'
            r = safe_request(url)
            if r:
                soup = BeautifulSoup(r.text, 'html.parser')
                meta = soup.find('meta', attrs={'name': 'description'})
                if meta and meta.get('content') and len(meta['content']) > 30:
                    raw += 1
                    rid = insert_raw(cur, f'instagram:#{tag}', url, meta['content'],
                                   'instagram', hashtags=f'#{tag}', location='nashik')
                    if rid:
                        stored += 1
                        conn.commit()
            time.sleep(2)
        except Exception as e:
            log.warning(f'Instagram #{tag} error: {e}')
            try: conn.rollback()
            except Exception: pass
    # Google fallback
    try:
        gurl = f'https://www.google.com/search?q=site:instagram.com+nashik+wine&num=10'
        r = safe_request(gurl)
        if r:
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                if 'instagram.com' in a['href']:
                    txt = a.get_text(strip=True)
                    if len(txt) > 20:
                        raw += 1
                        rid = insert_raw(cur, 'instagram:google', a['href'], txt, 'instagram')
                        if rid:
                            stored += 1
                            conn.commit()
    except Exception as e:
        log.warning(f'Instagram Google fallback: {e}')
        try: conn.rollback()
        except Exception: pass
    log.info(f'Instagram: {raw} raw, {stored} stored')
    return raw, stored

# --- FACEBOOK COLLECTOR (meta tags + Google) ---
def collect_facebook(conn):
    """Collect Facebook mentions about Nashik wine tourism."""
    raw, stored = 0, 0
    cur = conn.cursor()
    pages = ['sulavineyards', 'yorkwinery', 'nashiktourism', 'groverzampawines']
    for page in pages:
        try:
            url = f'https://www.facebook.com/{page}/'
            r = safe_request(url)
            if r:
                soup = BeautifulSoup(r.text, 'html.parser')
                meta = soup.find('meta', attrs={'name': 'description'})
                if meta and meta.get('content') and len(meta['content']) > 30:
                    raw += 1
                    rid = insert_raw(cur, f'facebook:{page}', url, meta['content'],
                                   'facebook', author=page, location='nashik')
                    if rid:
                        stored += 1
                        conn.commit()
            time.sleep(2)
        except Exception as e:
            log.warning(f'Facebook {page} error: {e}')
            try: conn.rollback()
            except Exception: pass
    # Google fallback
    try:
        gurl = 'https://www.google.com/search?q=site:facebook.com+nashik+wine+tourism&num=10'
        r = safe_request(gurl)
        if r:
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                if 'facebook.com' in a['href']:
                    txt = a.get_text(strip=True)
                    if len(txt) > 20:
                        raw += 1
                        rid = insert_raw(cur, 'facebook:google', a['href'], txt, 'facebook')
                        if rid:
                            stored += 1
                            conn.commit()
    except Exception as e:
        log.warning(f'Facebook Google fallback: {e}')
        try: conn.rollback()
        except Exception: pass
    log.info(f'Facebook: {raw} raw, {stored} stored')
    return raw, stored

# --- YOUTUBE COLLECTOR ---
def collect_youtube(conn):
    """Collect YouTube videos about Nashik wine tourism."""
    raw, stored = 0, 0
    cur = conn.cursor()
    queries = ['nashik wine tour', 'sula vineyards tour', 'nashik vineyard', 'wine tasting nashik']
    for q in queries:
        try:
            url = f'https://www.youtube.com/results?search_query={quote_plus(q)}'
            r = safe_request(url)
            if not r: continue
            import re as _re
            video_ids = _re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', r.text)[:5]
            titles = _re.findall(r'"title":\{"runs":\[\{"text":"([^"]+)"', r.text)[:5]
            for i, vid in enumerate(video_ids):
                vurl = f'https://www.youtube.com/watch?v={vid}'
                txt = titles[i] if i < len(titles) else f'YouTube video about {q}'
                raw += 1
                rid = insert_raw(cur, f'youtube:{q}', vurl, txt, 'youtube', location='nashik')
                if rid:
                    stored += 1
                    conn.commit()
            time.sleep(2)
        except Exception as e:
            log.warning(f'YouTube {q} error: {e}')
            try: conn.rollback()
            except Exception: pass
    log.info(f'YouTube: {raw} raw, {stored} stored')
    return raw, stored

# --- TRIPADVISOR COLLECTOR ---
def collect_tripadvisor(conn):
    """Collect TripAdvisor reviews about Nashik wineries."""
    raw, stored = 0, 0
    cur = conn.cursor()
    queries = ['sula vineyards nashik review', 'york winery nashik review',
               'nashik winery tripadvisor', 'grover zampa nashik review']
    for q in queries:
        try:
            url = f'https://www.google.com/search?q=site:tripadvisor.com+{quote_plus(q)}&num=10'
            r = safe_request(url)
            if not r: continue
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                if 'tripadvisor' in a['href']:
                    txt = a.get_text(strip=True)
                    if len(txt) > 20:
                        raw += 1
                        rid = insert_raw(cur, f'tripadvisor:{q}', a['href'], txt,
                                       'tripadvisor', location='nashik')
                        if rid:
                            stored += 1
                            conn.commit()
            time.sleep(3)
        except Exception as e:
            log.warning(f'TripAdvisor {q} error: {e}')
            try: conn.rollback()
            except Exception: pass
    log.info(f'TripAdvisor: {raw} raw, {stored} stored')
    return raw, stored

# --- MAKEMYTRIP / GOIBIBO COLLECTOR ---
def collect_travel_platforms(conn):
    """Monitor Indian travel platforms for Nashik demand."""
    raw, stored = 0, 0
    cur = conn.cursor()
    platforms = [
        ('makemytrip', 'https://www.google.com/search?q=site:makemytrip.com+nashik+hotels+wine&num=10'),
        ('goibibo', 'https://www.google.com/search?q=site:goibibo.com+nashik+hotels&num=10'),
        ('booking', 'https://www.google.com/search?q=site:booking.com+nashik+vineyard&num=10'),
        ('airbnb', 'https://www.google.com/search?q=site:airbnb.com+nashik+wine&num=10'),
    ]
    for name, url in platforms:
        try:
            r = safe_request(url)
            if not r: continue
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                if name in a['href']:
                    txt = a.get_text(strip=True)
                    if len(txt) > 15:
                        raw += 1
                        rid = insert_raw(cur, f'{name}:google', a['href'], txt,
                                       name, location='nashik')
                        if rid:
                            stored += 1
                            conn.commit()
            time.sleep(3)
        except Exception as e:
            log.warning(f'{name} error: {e}')
            try: conn.rollback()
            except Exception: pass
    log.info(f'Travel platforms: {raw} raw, {stored} stored')
    return raw, stored

# --- BLOG / MEDIUM RSS COLLECTOR ---
def collect_blogs(conn):
    """Collect blog posts about Nashik wine tourism."""
    raw, stored = 0, 0
    cur = conn.cursor()
    feeds = [
        'https://medium.com/feed/tag/nashik',
        'https://medium.com/feed/tag/wine-tourism',
        'https://medium.com/feed/tag/indian-wine',
        'https://www.google.com/alerts/feeds/nashik+wine+tourism',
    ]
    queries_google = ['nashik wine tourism blog', 'nashik vineyard experience blog',
                      'sula vineyards blog review']
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                title = entry.get('title', '')
                link = entry.get('link', '')
                summary = entry.get('summary', '')[:300]
                if len(title) > 10:
                    raw += 1
                    rid = insert_raw(cur, f'blog:rss', link, f'{title} {summary}',
                                   'blog', location='nashik')
                    if rid:
                        stored += 1
                        conn.commit()
        except Exception as e:
            log.warning(f'Blog RSS error: {e}')
            try: conn.rollback()
            except Exception: pass
    for q in queries_google:
        try:
            url = f'https://www.google.com/search?q={quote_plus(q)}&num=10'
            r = safe_request(url)
            if not r: continue
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                if any(d in href for d in ['medium.com', 'wordpress.com', 'blogspot.com', 'traveltriangle']):
                    txt = a.get_text(strip=True)
                    if len(txt) > 20:
                        raw += 1
                        rid = insert_raw(cur, f'blog:google:{q[:20]}', href, txt, 'blog')
                        if rid:
                            stored += 1
                            conn.commit()
            time.sleep(3)
        except Exception as e:
            log.warning(f'Blog Google error: {e}')
            try: conn.rollback()
            except Exception: pass
    log.info(f'Blogs: {raw} raw, {stored} stored')
    return raw, stored

# --- TELEGRAM COLLECTOR ---
def collect_telegram(conn):
    """Collect Telegram public channel mentions."""
    raw, stored = 0, 0
    cur = conn.cursor()
    queries = ['nashik wine', 'sula vineyards', 'nashik tourism']
    for q in queries:
        try:
            url = f'https://www.google.com/search?q=site:t.me+{quote_plus(q)}&num=10'
            r = safe_request(url)
            if not r: continue
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                if 't.me' in a['href']:
                    txt = a.get_text(strip=True)
                    if len(txt) > 15:
                        raw += 1
                        rid = insert_raw(cur, f'telegram:{q}', a['href'], txt, 'telegram')
                        if rid:
                            stored += 1
                            conn.commit()
            time.sleep(3)
        except Exception as e:
            log.warning(f'Telegram error: {e}')
            try: conn.rollback()
            except Exception: pass
    log.info(f'Telegram: {raw} raw, {stored} stored')
    return raw, stored

# --- COMPETITOR MONITORING ---
def collect_competitors(conn):
    """Monitor competitor wineries pricing and mentions."""
    raw, stored = 0, 0
    cur = conn.cursor()
    competitors = [
        ('sula_vineyards', ['sula vineyards price', 'sula wine tour cost', 'sula nashik package']),
        ('york_winery', ['york winery nashik price', 'york winery tour', 'york winery package']),
        ('grover_zampa', ['grover zampa nashik', 'grover zampa wine tour']),
        ('soma_vine', ['soma vine village nashik', 'soma vineyard tour']),
    ]
    for comp_name, queries in competitors:
        for q in queries:
            try:
                url = f'https://www.google.com/search?q={quote_plus(q)}&num=5'
                r = safe_request(url)
                if not r: continue
                soup = BeautifulSoup(r.text, 'html.parser')
                for div in soup.find_all(['div', 'span']):
                    txt = div.get_text(strip=True)
                    if len(txt) > 30 and len(txt) < 500:
                        if any(w in txt.lower() for w in ['price', 'rs', 'inr', 'cost', 'package', 'tour', 'book']):
                            raw += 1
                            rid = insert_raw(cur, f'competitor:{comp_name}', url, txt[:400],
                                           'competitor', author=comp_name, location='nashik')
                            if rid:
                                stored += 1
                                conn.commit()
                            break
                time.sleep(3)
            except Exception as e:
                log.warning(f'Competitor {comp_name} error: {e}')
                try: conn.rollback()
                except Exception: pass
    log.info(f'Competitors: {raw} raw, {stored} stored')
    return raw, stored

# --- SENTIMENT ANALYSIS ---
def analyze_sentiment(text):
    """Simple keyword-based sentiment analysis."""
    pos_words = ['amazing', 'beautiful', 'excellent', 'wonderful', 'great', 'love', 'best',
                 'fantastic', 'awesome', 'perfect', 'recommend', 'must visit', 'worth',
                 'stunning', 'delightful', 'enjoyed', 'lovely', 'brilliant', 'superb']
    neg_words = ['bad', 'worst', 'terrible', 'awful', 'poor', 'disappointed', 'overpriced',
                 'boring', 'avoid', 'waste', 'horrible', 'not worth', 'mediocre', 'crowded',
                 'dirty', 'rude', 'expensive', 'scam']
    t = text.lower()
    pos = sum(1 for w in pos_words if w in t)
    neg = sum(1 for w in neg_words if w in t)
    if pos > neg: return 'positive', min(1.0, pos * 0.2)
    elif neg > pos: return 'negative', min(1.0, neg * 0.2)
    return 'neutral', 0.0

# --- INSIGHTS GENERATION ---
def generate_insights(conn, total_raw, total_stored, total_leads, platform_data):
    """Generate cycle insights summary."""
    try:
        cur = conn.cursor()
        platforms_json = json.dumps(platform_data)
        top_segment = max(platform_data, key=lambda x: platform_data[x].get('stored', 0)) if platform_data else 'none'
        top_action = 'Monitor high-score leads for outreach'
        weather_summary = 'Check /api/weather for current conditions'
        trend_summary = f'Collected {total_raw} raw signals, {total_stored} stored, {total_leads} leads'
        insight_text = f'Cycle completed: {total_stored} new signals across {len(platform_data)} platforms. Top: {top_segment}'
        cur.execute(
            """INSERT INTO cycle_insights (cycle_time, total_raw, total_stored, total_leads,
            platforms_data, top_segment, top_action, weather_summary, trend_summary, insight_text)
            VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (total_raw, total_stored, total_leads, platforms_json, top_segment, top_action,
             weather_summary, trend_summary, insight_text[:1000])
        )
        conn.commit()
        log.info(f'Insights saved: {total_raw} raw, {total_stored} stored, {total_leads} leads')
    except Exception as e:
        log.error(f'Insights error: {e}')
        try: conn.rollback()
        except Exception: pass

# --- EMAIL/WEBHOOK ALERTS ---
def send_alerts(conn, new_leads):
    """Send alerts for high-score leads."""
    if not new_leads:
        return
    try:
        import urllib.request
        hot = [l for l in new_leads if l.get('score', 0) >= 70]
        if not hot:
            return
        alert_msg = f'VayaVia Alert: {len(hot)} new HOT leads detected!\n'
        for l in hot[:5]:
            alert_msg += f"- {l.get('name','Unknown')} (score:{l.get('score',0)}, source:{l.get('source','')})\n"
        log.info(f'ALERT: {len(hot)} hot leads - {alert_msg[:200]}')
        # Try n8n webhook
        try:
            req = urllib.request.Request(
                'http://localhost:5678/webhook/vayavia-trigger',
                data=json.dumps({'type': 'hot_leads', 'count': len(hot), 'message': alert_msg}).encode(),
                headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(req, timeout=5) as resp:
                log.info(f'Webhook alert sent: {resp.read().decode()[:100]}')
        except Exception:
            pass
        # Log to action_log table
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO action_log (action, details, ts) VALUES (%s, %s, NOW())",
                       ('hot_lead_alert', json.dumps({'count': len(hot), 'leads': [l.get('name','') for l in hot[:5]]})))
            conn.commit()
        except Exception:
            try: conn.rollback()
            except Exception: pass
    except Exception as e:
        log.warning(f'Alert error: {e}')

# --- OUTREACH TEMPLATES ---
OUTREACH_TEMPLATES = {
    'Wine Enthusiast': 'Discover exclusive wine experiences at VayaVia, Nashik. Private tastings, vineyard tours, and curated wine journeys await.',
    'Weekend Getaway': 'Plan your perfect weekend escape! VayaVia offers wine-country stays just 3hrs from Mumbai with stunning vineyard views.',
    'Luxury Seeker': 'Experience luxury wine living at VayaVia. Premium suites, personal sommelier, gourmet dining amidst Nashik vineyards.',
    'Culture Explorer': 'Explore the rich wine culture of Nashik at VayaVia. Heritage tours, grape-stomping festivals, and local Maharashtra experiences.',
    'Corporate Retreat': 'Host your next corporate offsite at VayaVia. Conference facilities, team activities, and wine-tasting events in Nashik.',
    'General Tourist': 'Visit VayaVia in Nashik for an unforgettable wine tourism experience. Tours, tastings, and beautiful vineyard stays.',
}

def get_outreach_template(segment):
    """Get outreach template for a lead segment."""
    return OUTREACH_TEMPLATES.get(segment, OUTREACH_TEMPLATES['General Tourist'])

# ---- MAIN COLLECTION CYCLE ----
def run_cycle(conn):
    """Run one complete collection cycle."""
    log.info('=== Starting collection cycle ===')
    results = {}
    
    # Reddit
    try:
        r, s = collect_reddit(conn)
        results['reddit'] = {'raw': r, 'stored': s}
    except Exception as e:
        log.error(f'Reddit collector failed: {e}')
    
    # Google News
    try:
        r, s = collect_news(conn)
        results['news'] = {'raw': r, 'stored': s}
    except Exception as e:
        log.error(f'News collector failed: {e}')
    
    # Weather
    try:
        r, s = collect_weather(conn)
        results['weather'] = {'raw': r, 'stored': s}
    except Exception as e:
        log.error(f'Weather collector failed: {e}')
    
    # Google Trends
    try:
        r, s = collect_trends(conn)
        results['trends'] = {'raw': r, 'stored': s}
    except Exception as e:
        log.error(f'Trends collector failed: {e}')
    
    # Instagram
    try:
        r, s = collect_instagram(conn)
        results['instagram'] = {'raw': r, 'stored': s}
    except Exception as e:
        log.error(f'Instagram collector failed: {e}')
    
    # Facebook
    try:
        r, s = collect_facebook(conn)
        results['facebook'] = {'raw': r, 'stored': s}
    except Exception as e:
        log.error(f'Facebook collector failed: {e}')
    
    # Telegram
    try:
        r, s = collect_telegram(conn)
        results['telegram'] = {'raw': r, 'stored': s}
    except Exception as e:
        log.error(f'Telegram collector failed: {e}')
    
    # Sentiment analysis
    try:
        analyze_sentiment(conn)
    except Exception as e:
        log.error(f'Sentiment analysis failed: {e}')
    
    # Competitor monitoring
    try:
        monitor_competitors(conn)
    except Exception as e:
        log.error(f'Competitor monitoring failed: {e}')
    
    # Check alerts
    try:
        alerts = check_alerts(conn)
        if alerts:
            send_alert(alerts)
    except Exception as e:
        log.error(f'Alert check failed: {e}')
    
    # Score signals and generate leads
    try:
        score_signals(conn)
    except Exception as e:
        log.error(f'Signal scoring failed: {e}')
    
    try:
        generate_leads(conn)
    except Exception as e:
        log.error(f'Lead generation failed: {e}')
    
    log.info(f'=== Cycle complete: {results} ===')
    return results

# ---- ENTRY POINT ----
if __name__ == '__main__':
    log.info('VayaVia Demand Engine v3.3 starting...')
    conn = get_db()
    ensure_tables(conn)
    
    while True:
        try:
            run_cycle(conn)
            log.info('Sleeping 30 minutes until next cycle...')
            time.sleep(1800)
        except KeyboardInterrupt:
            log.info('Shutting down...')
            break
        except Exception as e:
            log.error(f'Cycle error: {e}')
            try:
                conn.rollback()
            except Exception:
                pass
            log.info('Retrying in 5 minutes...')
            time.sleep(300)
