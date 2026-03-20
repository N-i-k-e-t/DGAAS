#!/usr/bin/env python3
"""VayaVia Demand Engine - Multi-Platform Collector v3.0
Auto-triggering, self-healing, collects from Reddit, X/Twitter,
Instagram, Facebook, Quora, Google News, Weather, Trends.
Each platform stored SEPARATELY with platform-specific fields.
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
WEATHER_KEY = '2dce6b15be076925e81c0765e9a3a7e4'
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
    cur.execute('''
        CREATE TABLE IF NOT EXISTS raw_signals (
            id SERIAL PRIMARY KEY,
            source_site TEXT, url TEXT UNIQUE, text_snippet TEXT,
            platform TEXT, author TEXT DEFAULT '',
            author_followers INT DEFAULT 0,
            engagement_likes INT DEFAULT 0,
            engagement_comments INT DEFAULT 0,
            engagement_shares INT DEFAULT 0,
            hashtags TEXT DEFAULT '',
            location TEXT DEFAULT '',
            collected_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id SERIAL PRIMARY KEY,
            raw_signal_id INT REFERENCES raw_signals(id),
            segment TEXT, score INT, urgency TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id SERIAL PRIMARY KEY,
            signal_id INT REFERENCES signals(id),
            segment TEXT, score INT, urgency TEXT,
            platform TEXT, handle TEXT,
            likes INT DEFAULT 0, comments INT DEFAULT 0,
            shares INT DEFAULT 0, hashtags TEXT DEFAULT '',
            followers INT DEFAULT 0, location TEXT DEFAULT '',
            ai_message TEXT, original_url TEXT,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
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
        if k in t:
            score += 20
    for k in MED_KW:
        if k in t:
            score += 10
    for k in LOW_KW:
        if k in t:
            score += 5
    score = min(100, max(1, score))
    seg = 'General Tourist'
    best = 0
    for s, kws in SEGMENTS.items():
        c = sum(1 for k in kws if k in t)
        if c > best:
            best = c
            seg = s
    urg = 'high' if score >= 70 else ('medium' if score >= 40 else 'low')
    return {'segment': seg, 'score': score, 'urgency': urg, 'reasoning': f'Keyword match score {score}'}

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
        log.warning(f'Insert error for {url[:60]}: {e}')
        return None

# ============ PLATFORM COLLECTORS ============

def collect_reddit():
    """Collect from Reddit using public JSON API - each subreddit separately."""
    signals = []
    for sub in SUBREDDITS:
        for kw in SEARCH_KEYWORDS[:5]:
            url = f'https://www.reddit.com/r/{sub}/search.json?q={quote_plus(kw)}&sort=new&limit=25&restrict_sr=on&t=week'
            r = safe_request(url)
            if not r:
                continue
            try:
                data = r.json()
                for post in data.get('data', {}).get('children', []):
                    d = post.get('data', {})
                    title = d.get('title', '')
                    body = d.get('selftext', '')
                    text = f"{title} {body}".strip()
                    if not text:
                        continue
                    signals.append({
                        'source': f'r/{sub}',
                        'url': f"https://reddit.com{d.get('permalink', '')}",
                        'text': text,
                        'platform': 'reddit',
                        'author': d.get('author', ''),
                        'followers': 0,
                        'likes': d.get('ups', 0),
                        'comments': d.get('num_comments', 0),
                        'shares': 0,
                        'hashtags': '',
                        'location': '',
                    })
            except Exception as e:
                log.warning(f'Reddit parse error r/{sub}: {e}')
            time.sleep(2)
    log.info(f'Reddit: {len(signals)} signals')
    return signals

def collect_twitter():
    """Collect from X/Twitter using syndication API and public search."""
    signals = []
    # Method 1: Twitter syndication API (public, no auth needed)
    for kw in SEARCH_KEYWORDS[:6]:
        url = f'https://syndication.twitter.com/srv/timeline-profile/screen-name/search?q={quote_plus(kw)}'
        r = safe_request(url, retries=2, timeout=15)
        if r and r.status_code == 200:
            try:
                tweets = re.findall(r'"full_text":"([^"]+)"', r.text)
                names = re.findall(r'"screen_name":"([^"]+)"', r.text)
                for i, tweet in enumerate(tweets[:20]):
                    author = names[i] if i < len(names) else ''
                    signals.append({
                        'source': 'twitter_syndication',
                        'url': f'https://twitter.com/search?q={quote_plus(kw)}&t={content_hash(tweet)}',
                        'text': tweet,
                        'platform': 'twitter',
                        'author': author,
                        'followers': 0,
                        'likes': 0, 'comments': 0, 'shares': 0,
                        'hashtags': ' '.join(re.findall(r'#\w+', tweet)),
                        'location': '',
                    })
            except Exception as e:
                log.warning(f'Twitter syndication parse: {e}')
        time.sleep(3)

    # Method 2: Nitter mirrors (fallback)
    nitter_mirrors = [
        'https://nitter.privacydev.net', 'https://nitter.poast.org',
        'https://nitter.cz', 'https://nitter.net',
    ]
    for kw in SEARCH_KEYWORDS[:4]:
        for mirror in nitter_mirrors:
            url = f'{mirror}/search?q={quote_plus(kw)}&f=tweets'
            r = safe_request(url, retries=1, timeout=10)
            if not r or r.status_code != 200:
                continue
            try:
                texts = re.findall(r'class="tweet-content[^>]*>([^<]+)<', r.text)
                authors = re.findall(r'class="username[^>]*>@([^<]+)<', r.text)
                links = re.findall(r'href="(/[^/]+/status/\d+)"', r.text)
                for i, text in enumerate(texts[:15]):
                    author = authors[i] if i < len(authors) else ''
                    link = links[i] if i < len(links) else ''
                    signals.append({
                        'source': mirror.split('//')[1],
                        'url': f'https://twitter.com{link}' if link else f'{mirror}/search?q={quote_plus(kw)}&h={content_hash(text)}',
                        'text': text.strip(),
                        'platform': 'twitter',
                        'author': author,
                        'followers': 0,
                        'likes': 0, 'comments': 0, 'shares': 0,
                        'hashtags': ' '.join(re.findall(r'#\w+', text)),
                        'location': '',
                    })
                break
            except Exception as e:
                log.warning(f'Nitter parse error: {e}')
        time.sleep(2)
    log.info(f'Twitter: {len(signals)} signals')
    return signals

def collect_instagram():
    """Collect from Instagram using public web endpoints and hashtag pages."""
    signals = []
    ig_tags = ['nashikwine', 'nashikvineyards', 'sulavineyards', 'nashiktourism',
               'winetasting', 'indianwine', 'yorkwinery', 'nashikdiaries',
               'maharashtratourism', 'winelover']
    for tag in ig_tags:
        # Method 1: Instagram public hashtag page
        url = f'https://www.instagram.com/explore/tags/{tag}/?__a=1&__d=dis'
        r = safe_request(url, retries=2, timeout=15)
        if r and r.status_code == 200:
            try:
                data = r.json()
                edges = data.get('graphql', {}).get('hashtag', {}).get('edge_hashtag_to_media', {}).get('edges', [])
                for edge in edges[:10]:
                    node = edge.get('node', {})
                    text = node.get('edge_media_to_caption', {}).get('edges', [{}])[0].get('node', {}).get('text', '')
                    if not text:
                        continue
                    signals.append({
                        'source': f'instagram_tag_{tag}',
                        'url': f"https://instagram.com/p/{node.get('shortcode', '')}",
                        'text': text,
                        'platform': 'instagram',
                        'author': node.get('owner', {}).get('username', ''),
                        'followers': 0,
                        'likes': node.get('edge_liked_by', {}).get('count', 0),
                        'comments': node.get('edge_media_to_comment', {}).get('count', 0),
                        'shares': 0,
                        'hashtags': ' '.join(re.findall(r'#\w+', text)),
                        'location': node.get('location', {}).get('name', '') if node.get('location') else '',
                    })
            except Exception as e:
                log.warning(f'Instagram API parse {tag}: {e}')

        # Method 2: Google search for Instagram posts
        gurl = f'https://www.google.com/search?q=site:instagram.com+{quote_plus(tag)}&tbs=qdr:w&num=10'
        r = safe_request(gurl, retries=1, timeout=15)
        if r and r.status_code == 200:
            try:
                titles = re.findall(r'<h3[^>]*>([^<]+)</h3>', r.text)
                links = re.findall(r'href="(https://www\.instagram\.com/p/[^"&]+)', r.text)
                for i, title in enumerate(titles[:8]):
                    link = links[i] if i < len(links) else f'https://instagram.com/explore/tags/{tag}'
                    signals.append({
                        'source': f'google_ig_{tag}',
                        'url': link,
                        'text': title,
                        'platform': 'instagram',
                        'author': '', 'followers': 0,
                        'likes': 0, 'comments': 0, 'shares': 0,
                        'hashtags': f'#{tag}',
                        'location': '',
                    })
            except Exception as e:
                log.warning(f'Google IG search error: {e}')
        time.sleep(5)
    log.info(f'Instagram: {len(signals)} signals')
    return signals

def collect_facebook():
    """Collect from Facebook using public page/group RSS feeds and Google search."""
    signals = []
    fb_pages = [
        'SulaVineyards', 'YorkWinery', 'NashikTourism',
        'MaharashtraTourism', 'WineTourismIndia',
    ]
    # Method 1: Facebook public page feeds via RSS bridge
    for page in fb_pages:
        url = f'https://www.facebook.com/{page}/posts/'
        r = safe_request(url, retries=1, timeout=15)
        if r and r.status_code == 200:
            try:
                texts = re.findall(r'"message":{"text":"([^"]+)"', r.text)
                for text in texts[:10]:
                    signals.append({
                        'source': f'fb_{page}',
                        'url': f'https://facebook.com/{page}',
                        'text': text,
                        'platform': 'facebook',
                        'author': page,
                        'followers': 0,
                        'likes': 0, 'comments': 0, 'shares': 0,
                        'hashtags': ' '.join(re.findall(r'#\w+', text)),
                        'location': '',
                    })
            except Exception as e:
                log.warning(f'FB page parse {page}: {e}')
        time.sleep(3)

    # Method 2: Google search for Facebook posts
    for kw in SEARCH_KEYWORDS[:5]:
        gurl = f'https://www.google.com/search?q=site:facebook.com+{quote_plus(kw)}&tbs=qdr:w&num=10'
        r = safe_request(gurl, retries=1, timeout=15)
        if r and r.status_code == 200:
            try:
                titles = re.findall(r'<h3[^>]*>([^<]+)</h3>', r.text)
                links = re.findall(r'href="(https://www\.facebook\.com/[^"&]+)"', r.text)
                for i, title in enumerate(titles[:8]):
                    link = links[i] if i < len(links) else f'https://facebook.com/search?q={quote_plus(kw)}'
                    signals.append({
                        'source': 'google_fb',
                        'url': link,
                        'text': title,
                        'platform': 'facebook',
                        'author': '', 'followers': 0,
                        'likes': 0, 'comments': 0, 'shares': 0,
                        'hashtags': '',
                        'location': '',
                    })
            except Exception as e:
                log.warning(f'Google FB search error: {e}')
        time.sleep(5)
    log.info(f'Facebook: {len(signals)} signals')
    return signals

def collect_quora():
    """Collect from Quora using RSS feeds and Google search."""
    signals = []
    quora_topics = [
        'Nashik-Wine', 'Indian-Wine', 'Wine-Tourism', 'Nashik-Tourism',
        'Sula-Vineyards', 'Maharashtra-Tourism', 'Wine-Tasting',
    ]
    # Method 1: Quora topic RSS feeds
    for topic in quora_topics:
        url = f'https://www.quora.com/topic/{topic}/rss'
        r = safe_request(url, retries=1, timeout=15)
        if r and r.status_code == 200:
            try:
                feed = feedparser.parse(r.content)
                for entry in feed.entries[:10]:
                    title = entry.get('title', '')
                    summary = re.sub(r'<[^>]+>', '', entry.get('summary', ''))[:300]
                    text = f"{title} {summary}".strip()
                    if not text:
                        continue
                    signals.append({
                        'source': f'quora_{topic}',
                        'url': entry.get('link', ''),
                        'text': text,
                        'platform': 'quora',
                        'author': entry.get('author', ''),
                        'followers': 0,
                        'likes': 0, 'comments': 0, 'shares': 0,
                        'hashtags': '',
                        'location': '',
                    })
            except Exception as e:
                log.warning(f'Quora RSS parse {topic}: {e}')
        time.sleep(3)

    # Method 2: Google search for Quora answers
    for kw in SEARCH_KEYWORDS[:4]:
        gurl = f'https://www.google.com/search?q=site:quora.com+{quote_plus(kw)}&tbs=qdr:m&num=10'
        r = safe_request(gurl, retries=1, timeout=15)
        if r and r.status_code == 200:
            try:
                titles = re.findall(r'<h3[^>]*>([^<]+)</h3>', r.text)
                links = re.findall(r'href="(https://www\.quora\.com/[^"&]+)"', r.text)
                for i, title in enumerate(titles[:8]):
                    link = links[i] if i < len(links) else f'https://quora.com/search?q={quote_plus(kw)}'
                    signals.append({
                        'source': 'google_quora',
                        'url': link,
                        'text': title,
                        'platform': 'quora',
                        'author': '', 'followers': 0,
                        'likes': 0, 'comments': 0, 'shares': 0,
                        'hashtags': '',
                        'location': '',
                    })
            except Exception as e:
                log.warning(f'Google Quora search error: {e}')
        time.sleep(5)
    log.info(f'Quora: {len(signals)} signals')
    return signals

def collect_news():
    """Collect from Google News RSS feeds."""
    signals = []
    for feed_url in RSS_FEEDS:
        r = safe_request(feed_url, retries=2, timeout=15)
        if not r:
            continue
        try:
            feed = feedparser.parse(r.content)
            for entry in feed.entries[:15]:
                title = entry.get('title', '')
                summary = re.sub(r'<[^>]+>', '', entry.get('summary', ''))[:200]
                text = f"{title} {summary}".strip()
                signals.append({
                    'source': entry.get('source', {}).get('title', 'google_news'),
                    'url': entry.get('link', ''),
                    'text': text,
                    'platform': 'google_news',
                    'author': entry.get('source', {}).get('title', ''),
                    'followers': 0,
                    'likes': 0, 'comments': 0, 'shares': 0,
                    'hashtags': '',
                    'location': '',
                })
        except Exception as e:
            log.warning(f'News RSS parse error: {e}')
        time.sleep(2)
    log.info(f'News: {len(signals)} signals')
    return signals

def collect_weather():
    """Collect weather data for Nashik."""
    signals = []
    url = f'https://api.openweathermap.org/data/2.5/forecast?q=Nashik,IN&appid={WEATHER_KEY}&units=metric'
    r = safe_request(url, retries=2)
    if r and r.status_code == 200:
        try:
            data = r.json()
            for item in data.get('list', [])[:8]:
                temp = item['main']['temp']
                desc = item['weather'][0]['description']
                dt = item['dt_txt']
                text = f"Nashik weather {dt}: {temp}C, {desc}"
                signals.append({
                    'source': 'openweathermap',
                    'url': f'https://openweathermap.org/city/1261529?dt={item["dt"]}',
                    'text': text,
                    'platform': 'weather',
                    'author': 'OpenWeatherMap',
                    'followers': 0,
                    'likes': 0, 'comments': 0, 'shares': 0,
                    'hashtags': '#weather #nashik',
                    'location': 'Nashik, Maharashtra',
                })
        except Exception as e:
            log.warning(f'Weather parse error: {e}')
    log.info(f'Weather: {len(signals)} signals')
    return signals

def collect_trends():
    """Collect Google Trends data via RSS."""
    signals = []
    trends_url = 'https://trends.google.com/trends/trendingsearches/daily/rss?geo=IN'
    r = safe_request(trends_url, retries=2)
    if r and r.status_code == 200:
        try:
            feed = feedparser.parse(r.content)
            for entry in feed.entries[:30]:
                title = entry.get('title', '').lower()
                if any(k in title for k in ['wine', 'nashik', 'tourism', 'travel', 'maharashtra', 'vineyard', 'winery']):
                    text = f"Trending: {entry.get('title', '')} - {entry.get('summary', '')[:150]}"
                    signals.append({
                        'source': 'google_trends',
                        'url': entry.get('link', ''),
                        'text': text,
                        'platform': 'google_trends',
                        'author': 'Google Trends',
                        'followers': 0,
                        'likes': 0, 'comments': 0, 'shares': 0,
                        'hashtags': f'#trending #{entry.get("title", "").replace(" ", "")}',
                        'location': 'India',
                    })
        except Exception as e:
            log.warning(f'Trends parse error: {e}')
    log.info(f'Trends: {len(signals)} signals')
    return signals

# ============ PROCESSING & STORAGE ============

COLLECTORS = {
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
                author=sig.get('author', ''), followers=sig.get('followers', 0),
                likes=sig.get('likes', 0), comments=sig.get('comments', 0),
                shares=sig.get('shares', 0), hashtags=sig.get('hashtags', ''),
                location=sig.get('location', '')
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
            if sc >= MIN_SCORE_LEAD:
                handle = sig.get('author', '') or sig['source']
                cur.execute(
                    '''INSERT INTO leads (signal_id, segment, score, urgency, platform, handle,
                        likes, comments, shares, hashtags, followers, location,
                        ai_message, original_url, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (sid, seg, sc, urg, sig['platform'], handle[:100],
                     sig.get('likes', 0), sig.get('comments', 0), sig.get('shares', 0),
                     sig.get('hashtags', '')[:300], sig.get('followers', 0),
                     sig.get('location', '')[:100],
                     reason[:300], sig['url'], 'new' if sc >= 70 else 'nurturing')
                )
                nl += 1
        except Exception as e:
            log.error(f'Store error for {sig.get("url", "?")}: {e}')
            try:
                conn.rollback()
            except Exception:
                pass
    try:
        conn.commit()
    except Exception as e:
        log.error(f'Commit error: {e}')
    conn.close()
    return ns, nl

# ============ MAIN DAEMON ============

def run_cycle():
    """Run one complete collection cycle across all platforms."""
    start = time.time()
    total_raw = total_stored = total_leads = 0
    platform_stats = {}

    for name, collector_fn in COLLECTORS.items():
        log.info(f'--- Collecting: {name} ---')
        try:
            signals = collector_fn()
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
    for name, stats in platform_stats.items():
        err = f" ERROR: {stats['error']}" if 'error' in stats else ''
        log.info(f'  {name}: {stats["raw"]} raw, {stats["stored"]} stored, {stats["leads"]} leads{err}')
    return total_stored, total_leads

def main():
    log.info('='*60)
    log.info('VayaVia Demand Engine v3.0 starting')
    log.info(f'Platforms: {", ".join(COLLECTORS.keys())}')
    log.info(f'Cycle interval: {CYCLE_INTERVAL}s')
    log.info('='*60)

    # Ensure DB tables exist
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
