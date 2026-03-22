#!/usr/bin/env python3
"""VayaVia Browser Collector v1.0 - Parallel Browser-Based Deep Collection

Runs ALONGSIDE the existing collector.py (API-based).
Uses Playwright headless Chromium to scrape platforms that block API access.
Stores into the SAME posts/post_comments/leads tables.

Platforms handled by this browser collector:
- YouTube (full video + comments)
- TripAdvisor (reviews + ratings)
- Quora (answers + discussions)
- Google Search (organic results for travel queries)
- Instagram (public profiles/hashtags)
- MakeMyTrip / Booking.com (listings + prices)
- Google Trends (trending topics)

The existing collector.py handles: Reddit, Google News RSS, Weather, Blogs
"""

import psycopg2, psycopg2.extras
import json, time, re, logging, hashlib, random
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger('browser_collector')

# ── Config ──
DB_CONFIG = dict(host='localhost', port=5432, dbname='vayavia_agent', user='postgres', password='postgres')
CYCLE_INTERVAL = 1800  # 30 min
SLOW_MO = 200  # ms between actions (anti-detection)
PAGE_TIMEOUT = 30000  # 30s page load timeout

# ── Keyword Strategy (same as collector.py) ──
KEYWORD_STRATEGY = {
    'direct_brand': {'weight': 100, 'terms': ['vayavia nashik', 'sula vineyards', 'york winery nashik', 'grover zampa nashik', 'soma vine village']},
    'nashik_wine': {'weight': 80, 'terms': ['nashik wine tasting', 'nashik vineyard tour', 'nashik winery visit', 'nashik grape stomping', 'nashik wine trail']},
    'nashik_travel': {'weight': 70, 'terms': ['nashik weekend trip', 'nashik tourism', 'things to do nashik', 'nashik hotel resort', 'nashik travel guide']},
    'wine_tourism': {'weight': 60, 'terms': ['wine tourism india', 'best wineries india', 'indian wine tasting', 'vineyard stay india']},
    'weekend_getaway': {'weight': 50, 'terms': ['weekend getaway pune', 'weekend trip mumbai', 'romantic getaway maharashtra', 'couple trip near pune']},
    'hooks': {'weight': 40, 'terms': ['best wine experience india', 'where to go wine tasting', 'vineyard resort recommend', 'wine trip planning india']}
}

# ── Intent Detection ──
INTENT_PATTERNS = {
    'planning': r'plan|itinerary|schedule|going to|want to visit|thinking of|looking for|suggest',
    'asking': r'how to|where can|what is|anyone know|recommend|best place|tips for',
    'booking': r'book|reserv|avail|price|cost|rate|package|deal|offer|discount',
    'complaining': r'bad|worst|terrible|disappoint|avoid|overpriced|waste|scam|don.t go',
    'recommending': r'must visit|highly recommend|amazing|love|best|wonderful|fantastic|perfect',
    'sharing': r'just visited|went to|stayed at|had a great|experience at|trip to|photos from'
}

SEGMENTS = {
    'Wine Enthusiast': r'wine|vineyard|winery|tasting|sommelier|grape|vintage|cellar',
    'Weekend Tripper': r'weekend|getaway|short trip|quick trip|day trip|2 day',
    'Luxury Seeker': r'luxury|premium|5 star|suite|spa|resort|exclusive|boutique',
    'Honeymoon/Couple': r'honeymoon|couple|romantic|anniversary|partner|spouse',
    'Family Traveler': r'family|kids|children|child.friendly|family trip',
    'Culture Explorer': r'culture|heritage|history|temple|festival|tradition|local',
    'Corporate/Group': r'corporate|team|group|retreat|conference|offsite|event',
    'Budget Traveler': r'budget|cheap|affordable|backpack|hostel|save money',
    'Food & Drink': r'food|restaurant|cuisine|dining|eat|taste|culinary|chef'
}

def detect_intent(text):
    if not text: return 'general', 0.3
    text_lower = text.lower()
    for intent, pattern in INTENT_PATTERNS.items():
        if re.search(pattern, text_lower):
            return intent, 0.8
    return 'general', 0.3

def auto_categorize(text):
    if not text: return 'General Tourist'
    text_lower = text.lower()
    for seg, pattern in SEGMENTS.items():
        if re.search(pattern, text_lower):
            return seg
    return 'General Tourist'

def score_relevance(text, keyword_weight=50):
    if not text: return keyword_weight
    score = keyword_weight
    text_lower = text.lower()
    nashik_terms = ['nashik', 'nasik', 'sula', 'york winery', 'vayavia', 'grover zampa', 'soma vine']
    for t in nashik_terms:
        if t in text_lower: score += 15
    if any(w in text_lower for w in ['wine', 'vineyard', 'winery', 'tasting']): score += 10
    return min(score, 100)

def make_hash(text):
    return hashlib.md5((text or '').encode()).hexdigest()[:12]

# ── Database ──
def get_db():
    return psycopg2.connect(**DB_CONFIG)

def store_post(conn, data):
    """Store a post, dedup by post_url. Returns post_id or None."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM posts WHERE post_url=%s", (data.get('post_url',''),))
        if cur.fetchone():
            cur.close()
            return None
        full_text = f"{data.get('post_title','')} {data.get('post_body','')}"
        intent, intent_score = detect_intent(full_text)
        category = auto_categorize(full_text)
        relevance = score_relevance(full_text, data.get('keyword_weight', 50))
        urgency = 'high' if relevance >= 75 else 'medium' if relevance >= 50 else 'low'
        cur.execute("""INSERT INTO posts (platform, post_url, post_title, post_body, post_full_text,
            author_username, author_profile_url, author_followers,
            group_name, group_url, likes, upvotes, shares, comment_count, views,
            hashtags, mentions, media_urls, post_time,
            search_keyword, keyword_group, keyword_weight,
            intent, intent_score, category, relevance_score, urgency, sentiment,
            is_competitor, is_lead_candidate, source_collector)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id""",
            (data.get('platform'), data.get('post_url'), data.get('post_title'), data.get('post_body'), full_text,
             data.get('author_username'), data.get('author_profile_url'), data.get('author_followers', 0),
             data.get('group_name'), data.get('group_url'), data.get('likes', 0), data.get('upvotes', 0),
             data.get('shares', 0), data.get('comment_count', 0), data.get('views', 0),
             data.get('hashtags'), data.get('mentions'), data.get('media_urls'),
             data.get('post_time'), data.get('search_keyword'), data.get('keyword_group'),
             data.get('keyword_weight', 50), intent, intent_score, category, relevance, urgency,
             data.get('sentiment', 'neutral'), data.get('is_competitor', False),
             relevance >= 60, 'browser_collector'))
        post_id = cur.fetchone()[0]
        conn.commit()
        return post_id
    except Exception as e:
        conn.rollback()
        log.warning(f"Store post error: {e}")
        return None
    finally:
        cur.close()

def store_comment(conn, post_id, data):
    cur = conn.cursor()
    try:
        cur.execute("""INSERT INTO post_comments (post_id, comment_text, comment_author, comment_likes, comment_time, intent, sentiment)
            VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (post_id, data.get('text','')[:2000], data.get('author',''), data.get('likes',0),
             data.get('time'), detect_intent(data.get('text',''))[0], 'neutral'))
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        cur.close()

def store_lead(conn, post_id, data):
    cur = conn.cursor()
    try:
        cur.execute("""INSERT INTO leads (post_id, username, platform, profile_url, lead_score, category, intent, post_url, outreach_template)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (post_id, data.get('username'), data.get('platform'), data.get('profile_url',''),
             data.get('lead_score',50), data.get('category','General Tourist'),
             data.get('intent','general'), data.get('post_url',''),
             f"Hi {data.get('username','')}, noticed your interest in {data.get('category','')}. VayaVia offers..."))
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        cur.close()

# ── Browser Setup ──
def create_browser(pw):
    """Launch headless Chromium with anti-detection settings."""
    browser = pw.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage',
              '--disable-blink-features=AutomationControlled']
    )
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        locale='en-US',
        timezone_id='Asia/Kolkata'
    )
    context.set_default_timeout(PAGE_TIMEOUT)
    return browser, context

def safe_goto(page, url, wait_until='domcontentloaded'):
    try:
        page.goto(url, wait_until=wait_until, timeout=PAGE_TIMEOUT)
        time.sleep(random.uniform(1, 3))
        return True
    except Exception as e:
        log.warning(f"Navigation failed: {url} - {e}")
        return False

def random_delay(min_s=1, max_s=4):
    time.sleep(random.uniform(min_s, max_s))

# ============================================================
# PLATFORM COLLECTORS (Browser-based)
# ============================================================

def collect_youtube_browser(context, conn):
    """Scrape YouTube search results + video details + comments via browser."""
    log.info("=== YouTube Browser Collection ===")
    page = context.new_page()
    stats = {'posts': 0, 'stored': 0, 'comments': 0, 'leads': 0}
    
    for group, info in KEYWORD_STRATEGY.items():
        for term in info['terms']:
            query = term.replace(' ', '+')
            url = f"https://www.youtube.com/results?search_query={query}"
            if not safe_goto(page, url): continue
            random_delay(2, 5)
            
            # Scroll to load more results
            for _ in range(3):
                page.evaluate('window.scrollBy(0, 800)')
                random_delay(0.5, 1.5)
            
            # Extract video links
            videos = page.evaluate("""() => {
                const results = [];
                document.querySelectorAll('ytd-video-renderer, ytd-rich-item-renderer').forEach(el => {
                    const titleEl = el.querySelector('#video-title');
                    const channelEl = el.querySelector('#channel-name a, .ytd-channel-name a, #text.ytd-channel-name');
                    const viewsEl = el.querySelector('#metadata-line span');
                    if (titleEl) {
                        results.push({
                            title: titleEl.textContent.trim(),
                            url: titleEl.href || '',
                            channel: channelEl ? channelEl.textContent.trim() : '',
                            channel_url: channelEl && channelEl.href ? channelEl.href : '',
                            views_text: viewsEl ? viewsEl.textContent.trim() : ''
                        });
                    }
                });
                return results.slice(0, 10);
            }""")
            
            stats['posts'] += len(videos)
            log.info(f"  YouTube '{term}': {len(videos)} videos found")
            
            for vid in videos:
                if not vid.get('url'): continue
                # Parse views
                views = 0
                vm = re.search(r'([\d,.]+)\s*(K|M|B)?\s*view', vid.get('views_text',''), re.I)
                if vm:
                    v = float(vm.group(1).replace(',',''))
                    mult = {'K':1000,'M':1000000,'B':1000000000}.get(vm.group(2) or '',1)
                    views = int(v * mult)
                
                post_id = store_post(conn, {
                    'platform': 'youtube',
                    'post_url': vid['url'],
                    'post_title': vid['title'],
                    'post_body': vid['title'],
                    'author_username': vid['channel'],
                    'author_profile_url': vid.get('channel_url',''),
                    'group_name': 'YouTube Search',
                    'views': views,
                    'search_keyword': term,
                    'keyword_group': group,
                    'keyword_weight': info['weight']
                })
                
                if post_id:
                    stats['stored'] += 1
                    # Navigate to video to get comments
                    try:
                        video_page = context.new_page()
                        if safe_goto(video_page, vid['url']):
                            random_delay(2, 4)
                            # Scroll to load comments
                            for _ in range(5):
                                video_page.evaluate('window.scrollBy(0, 500)')
                                random_delay(0.8, 1.5)
                            
                            comments = video_page.evaluate("""() => {
                                const cmts = [];
                                document.querySelectorAll('ytd-comment-thread-renderer').forEach(el => {
                                    const author = el.querySelector('#author-text');
                                    const content = el.querySelector('#content-text');
                                    const likes = el.querySelector('#vote-count-middle');
                                    if (content) {
                                        cmts.push({
                                            author: author ? author.textContent.trim() : '',
                                            text: content.textContent.trim(),
                                            likes: likes ? likes.textContent.trim() : '0'
                                        });
                                    }
                                });
                                return cmts.slice(0, 20);
                            }""")
                            
                            for cmt in comments:
                                store_comment(conn, post_id, cmt)
                                stats['comments'] += 1
                            
                            # Lead gen
                            full = vid['title']
                            rel = score_relevance(full, info['weight'])
                            if rel >= 60 and vid['channel']:
                                store_lead(conn, post_id, {
                                    'username': vid['channel'], 'platform': 'youtube',
                                    'profile_url': vid.get('channel_url',''),
                                    'lead_score': rel, 'category': auto_categorize(full),
                                    'intent': detect_intent(full)[0], 'post_url': vid['url']
                                })
                                stats['leads'] += 1
                        video_page.close()
                    except Exception as e:
                        log.warning(f"  YouTube comment fetch error: {e}")
            random_delay(3, 7)  # Between search queries
    
    page.close()
    log.info(f"YouTube Browser: {stats}")
    return stats

def collect_tripadvisor_browser(context, conn):
    """Scrape TripAdvisor Nashik reviews + attractions via browser."""
    log.info("=== TripAdvisor Browser Collection ===")
    page = context.new_page()
    stats = {'posts': 0, 'stored': 0, 'comments': 0, 'leads': 0}
    
    ta_urls = [
        ('https://www.tripadvisor.in/Attractions-g297614-Activities-Nashik_Nashik_District_Maharashtra.html', 'Nashik Attractions'),
        ('https://www.tripadvisor.in/Restaurants-g297614-Nashik_Nashik_District_Maharashtra.html', 'Nashik Restaurants'),
    ]
    search_terms = ['sula vineyards nashik', 'york winery nashik', 'nashik wine tour', 'nashik resort']
    for term in search_terms:
        ta_urls.append((f'https://www.tripadvisor.in/Search?q={term.replace(" ", "+")}', f'Search: {term}'))
    
    for url, label in ta_urls:
        if not safe_goto(page, url): continue
        random_delay(2, 5)
        
        items = page.evaluate("""() => {
            const results = [];
            // Search results or listing cards
            document.querySelectorAll('[data-automation="searchResult"], .listing_title a, .result-title, [data-test-target="top-result"]').forEach(el => {
                const link = el.href || (el.querySelector('a') ? el.querySelector('a').href : '');
                const title = el.textContent.trim();
                if (title && title.length > 5) results.push({title, url: link});
            });
            // Also try card format
            document.querySelectorAll('.prw_rup, .location-meta-block, .search-result').forEach(el => {
                const a = el.querySelector('a');
                const title = el.querySelector('.result-title, .listing_title, h3');
                if (a && title) results.push({title: title.textContent.trim(), url: a.href || ''});
            });
            return results.slice(0, 15);
        }""")
        
        stats['posts'] += len(items)
        log.info(f"  TripAdvisor '{label}': {len(items)} items")
        
        for item in items:
            full_url = item.get('url', '')
            if not full_url or not full_url.startswith('http'):
                full_url = f"https://www.tripadvisor.in{full_url}" if full_url.startswith('/') else ''
            if not full_url: continue
            
            post_id = store_post(conn, {
                'platform': 'tripadvisor', 'post_url': full_url,
                'post_title': item['title'], 'post_body': item['title'],
                'group_name': label, 'group_url': url,
                'search_keyword': label, 'keyword_group': 'nashik_travel', 'keyword_weight': 70
            })
            if post_id:
                stats['stored'] += 1
                # Try to get reviews from detail page
                try:
                    detail = context.new_page()
                    if safe_goto(detail, full_url):
                        random_delay(2, 4)
                        reviews = detail.evaluate("""() => {
                            const revs = [];
                            document.querySelectorAll('[data-automation="reviewCard"], .review-container, .partial_entry, .prw_reviews_text_summary_hsx').forEach(el => {
                                const text = el.querySelector('.partial_entry, [data-automation="reviewText"], .entry');
                                const author = el.querySelector('.info_text, .member_info .username, [data-automation="reviewer"]');
                                const rating = el.querySelector('.ui_bubble_rating, [data-automation="bubbleRating"]');
                                if (text) revs.push({
                                    text: text.textContent.trim().slice(0, 1000),
                                    author: author ? author.textContent.trim() : '',
                                    rating: rating ? rating.className : ''
                                });
                            });
                            return revs.slice(0, 10);
                        }""")
                        for rev in reviews:
                            store_comment(conn, post_id, {'text': rev['text'], 'author': rev['author']})
                            stats['comments'] += 1
                    detail.close()
                except: pass
        random_delay(5, 10)
    
    page.close()
    log.info(f"TripAdvisor Browser: {stats}")
    return stats


def collect_google_search_browser(context, conn):
    """Google Search for travel queries — extract organic results."""
    log.info("=== Google Search Browser Collection ===")
    page = context.new_page()
    stats = {'posts': 0, 'stored': 0, 'comments': 0, 'leads': 0}
    
    queries = [
        'nashik wine tourism review', 'sula vineyard experience',
        'best winery nashik 2024 2025', 'nashik weekend getaway blog',
        'york winery nashik review', 'wine tasting nashik recommendations',
        'soma vine village review', 'nashik vineyard resort booking',
        'couple trip nashik winery', 'nashik travel itinerary wine'
    ]
    
    for query in queries:
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}&hl=en"
        if not safe_goto(page, url): continue
        random_delay(3, 6)
        
        results = page.evaluate("""() => {
            const items = [];
            document.querySelectorAll('#search .g, div[data-sokoban-container]').forEach(el => {
                const a = el.querySelector('a[href]');
                const h3 = el.querySelector('h3');
                const snippet = el.querySelector('.VwiC3b, [data-sncf], .st');
                if (a && h3) {
                    items.push({
                        title: h3.textContent.trim(),
                        url: a.href,
                        snippet: snippet ? snippet.textContent.trim() : ''
                    });
                }
            });
            return items.slice(0, 10);
        }""")
        
        stats['posts'] += len(results)
        log.info(f"  Google '{query}': {len(results)} results")
        
        for r in results:
            if not r.get('url') or 'google.com' in r['url']: continue
            post_id = store_post(conn, {
                'platform': 'google_search', 'post_url': r['url'],
                'post_title': r['title'], 'post_body': r.get('snippet',''),
                'group_name': 'Google Organic', 'search_keyword': query,
                'keyword_group': 'nashik_wine', 'keyword_weight': 70
            })
            if post_id: stats['stored'] += 1
        random_delay(8, 15)  # Longer delay for Google
    
    page.close()
    log.info(f"Google Search Browser: {stats}")
    return stats


def collect_quora_browser(context, conn):
    """Scrape Quora questions and answers about Nashik wine tourism."""
    log.info("=== Quora Browser Collection ===")
    page = context.new_page()
    stats = {'posts': 0, 'stored': 0, 'comments': 0, 'leads': 0}
    
    quora_queries = [
        'nashik wine tasting', 'sula vineyards review', 'best winery nashik',
        'nashik weekend trip', 'wine tourism india', 'york winery review'
    ]
    
    for query in quora_queries:
        url = f"https://www.quora.com/search?q={query.replace(' ', '+')}"
        if not safe_goto(page, url): continue
        random_delay(3, 6)
        
        # Scroll to load content
        for _ in range(3):
            page.evaluate('window.scrollBy(0, 600)')
            random_delay(1, 2)
        
        questions = page.evaluate("""() => {
            const qs = [];
            document.querySelectorAll('[class*="question"], .q-box a[href*="/"]').forEach(el => {
                const text = el.textContent.trim();
                const href = el.href || '';
                if (text.length > 20 && text.length < 300 && href.includes('quora.com')) {
                    qs.push({title: text, url: href});
                }
            });
            // Deduplicate
            const seen = new Set();
            return qs.filter(q => { if (seen.has(q.url)) return false; seen.add(q.url); return true; }).slice(0, 10);
        }""")
        
        stats['posts'] += len(questions)
        log.info(f"  Quora '{query}': {len(questions)} questions")
        
        for q in questions:
            post_id = store_post(conn, {
                'platform': 'quora', 'post_url': q['url'],
                'post_title': q['title'], 'post_body': q['title'],
                'group_name': 'Quora', 'search_keyword': query,
                'keyword_group': 'nashik_wine', 'keyword_weight': 60
            })
            if post_id:
                stats['stored'] += 1
                # Try to get answers
                try:
                    qpage = context.new_page()
                    if safe_goto(qpage, q['url']):
                        random_delay(2, 4)
                        for _ in range(3):
                            qpage.evaluate('window.scrollBy(0, 500)')
                            random_delay(0.5, 1)
                        answers = qpage.evaluate("""() => {
                            const ans = [];
                            document.querySelectorAll('[class*="Answer"], .qu-truncation--3').forEach(el => {
                                const text = el.textContent.trim();
                                if (text.length > 30) ans.push({text: text.slice(0, 1000), author: ''});
                            });
                            return ans.slice(0, 5);
                        }""")
                        for a in answers:
                            store_comment(conn, post_id, a)
                            stats['comments'] += 1
                    qpage.close()
                except: pass
        random_delay(5, 10)
    
    page.close()
    log.info(f"Quora Browser: {stats}")
    return stats


def collect_instagram_browser(context, conn):
    """Scrape public Instagram hashtag pages for travel content."""
    log.info("=== Instagram Browser Collection ===")
    page = context.new_page()
    stats = {'posts': 0, 'stored': 0, 'comments': 0, 'leads': 0}
    
    hashtags = ['nashikwine', 'sulavineyards', 'nashikwinery', 'winetourism',
                'nashiktravel', 'yorkwinery', 'winetasting', 'nashikdiaries']
    
    for tag in hashtags:
        url = f"https://www.instagram.com/explore/tags/{tag}/"
        if not safe_goto(page, url): continue
        random_delay(3, 6)
        
        # Instagram may require login, try to extract what we can
        posts = page.evaluate("""() => {
            const items = [];
            document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]').forEach(a => {
                const img = a.querySelector('img');
                items.push({
                    url: a.href,
                    alt: img ? img.alt || '' : '',
                });
            });
            return items.slice(0, 12);
        }""")
        
        stats['posts'] += len(posts)
        log.info(f"  Instagram #{tag}: {len(posts)} posts found")
        
        for p in posts:
            if not p.get('url'): continue
            post_id = store_post(conn, {
                'platform': 'instagram', 'post_url': p['url'],
                'post_title': p.get('alt', f'#{tag} post')[:200],
                'post_body': p.get('alt', ''),
                'hashtags': f'#{tag}', 'group_name': f'#{tag}',
                'search_keyword': tag, 'keyword_group': 'nashik_wine', 'keyword_weight': 70
            })
            if post_id: stats['stored'] += 1
        random_delay(5, 10)
    
    page.close()
    log.info(f"Instagram Browser: {stats}")
    return stats


def collect_travel_platforms_browser(context, conn):
    """Scrape MakeMyTrip and Booking.com for Nashik listings."""
    log.info("=== Travel Platforms Browser Collection ===")
    page = context.new_page()
    stats = {'posts': 0, 'stored': 0, 'comments': 0, 'leads': 0}
    
    platforms = [
        ('makemytrip', 'https://www.makemytrip.com/hotels/nashik-hotels.html', 'MMT Nashik Hotels'),
        ('booking', 'https://www.booking.com/searchresults.html?ss=Nashik&nflt=ht_id%3D204', 'Booking Nashik'),
    ]
    
    for plat, url, label in platforms:
        if not safe_goto(page, url): continue
        random_delay(3, 6)
        
        # Scroll to load listings
        for _ in range(3):
            page.evaluate('window.scrollBy(0, 600)')
            random_delay(1, 2)
        
        listings = page.evaluate("""() => {
            const items = [];
            // Generic selectors that work across platforms
            document.querySelectorAll('[data-testid="property-card"], .listingCard, .hotel-card, .sr_property_block, [data-hotelid]').forEach(el => {
                const title = el.querySelector('[data-testid="title"], .persuasion__title, .hotel-name, .sr-hotel__name, h3, .fnt22');
                const price = el.querySelector('[data-testid="price-and-discounted-price"], .price, .bui-price-display, .fnt18');
                const rating = el.querySelector('[data-testid="review-score"], .rating, .review-score, .bui-review-score');
                const link = el.querySelector('a[href]');
                if (title) {
                    items.push({
                        title: title.textContent.trim(),
                        price: price ? price.textContent.trim() : '',
                        rating: rating ? rating.textContent.trim() : '',
                        url: link ? link.href : ''
                    });
                }
            });
            return items.slice(0, 15);
        }""")
        
        stats['posts'] += len(listings)
        log.info(f"  {label}: {len(listings)} listings")
        
        for item in listings:
            full_url = item.get('url', url)
            body = f"{item['title']} | Price: {item.get('price','')} | Rating: {item.get('rating','')}"
            post_id = store_post(conn, {
                'platform': plat, 'post_url': full_url,
                'post_title': item['title'], 'post_body': body,
                'group_name': label, 'group_url': url,
                'search_keyword': 'nashik hotels', 'keyword_group': 'nashik_travel', 'keyword_weight': 70
            })
            if post_id: stats['stored'] += 1
        random_delay(5, 10)
    
    page.close()
    log.info(f"Travel Platforms Browser: {stats}")
    return stats


def collect_google_trends_browser(context, conn):
    """Scrape Google Trends for trending wine/travel topics."""
    log.info("=== Google Trends Browser Collection ===")
    page = context.new_page()
    stats = {'posts': 0, 'stored': 0, 'comments': 0, 'leads': 0}
    
    trends_queries = [
        'nashik wine', 'sula vineyards', 'wine tourism india', 'nashik tourism',
        'york winery', 'nashik weekend'
    ]
    
    for query in trends_queries:
        url = f"https://trends.google.com/trends/explore?q={query.replace(' ', '+')}&geo=IN"
        if not safe_goto(page, url, wait_until='networkidle'): continue
        random_delay(3, 6)
        
        # Extract related queries
        related = page.evaluate("""() => {
            const items = [];
            document.querySelectorAll('[class*="related"] a, .fe-related-queries a, .widget-actions-item a').forEach(el => {
                const text = el.textContent.trim();
                if (text.length > 2 && text.length < 100) items.push({title: text, url: el.href || ''});
            });
            return items.slice(0, 10);
        }""")
        
        stats['posts'] += len(related)
        log.info(f"  Trends '{query}': {len(related)} related queries")
        
        for r in related:
            post_id = store_post(conn, {
                'platform': 'google_trends', 'post_url': r.get('url', url),
                'post_title': r['title'], 'post_body': f"Trending: {r['title']} (related to {query})",
                'group_name': 'Google Trends', 'search_keyword': query,
                'keyword_group': 'nashik_wine', 'keyword_weight': 50
            })
            if post_id: stats['stored'] += 1
        random_delay(5, 8)
    
    page.close()
    log.info(f"Google Trends Browser: {stats}")
    return stats


# ============================================================
# CYCLE ORCHESTRATOR
# ============================================================

def run_browser_cycle(conn):
    """Run one complete browser collection cycle."""
    log.info("="*50)
    log.info("BROWSER COLLECTION CYCLE START")
    log.info("="*50)
    
    cycle_start = datetime.now(timezone.utc)
    results = {}
    
    with sync_playwright() as pw:
        browser, context = create_browser(pw)
        
        collectors = [
            ('youtube', collect_youtube_browser),
            ('tripadvisor', collect_tripadvisor_browser),
            ('google_search', collect_google_search_browser),
            ('quora', collect_quora_browser),
            ('instagram', collect_instagram_browser),
            ('travel_platforms', collect_travel_platforms_browser),
            ('google_trends', collect_google_trends_browser),
        ]
        
        for name, func in collectors:
            try:
                log.info(f"\n--- Starting {name} browser collector ---")
                stats = func(context, conn)
                results[name] = stats
                log.info(f"--- {name} done: {stats} ---")
            except Exception as e:
                log.error(f"Browser collector {name} failed: {e}")
                results[name] = {'posts': 0, 'stored': 0, 'comments': 0, 'leads': 0, 'error': str(e)}
        
        browser.close()
    
    # Store cycle summary
    cycle_end = datetime.now(timezone.utc)
    total_posts = sum(r.get('stored', 0) for r in results.values())
    total_comments = sum(r.get('comments', 0) for r in results.values())
    total_leads = sum(r.get('leads', 0) for r in results.values())
    
    try:
        cur = conn.cursor()
        cur.execute("""INSERT INTO collection_runs (run_start, run_end, platform, keyword, posts_found, posts_stored, comments_collected, leads_generated)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (cycle_start, cycle_end, 'browser_all', 'browser_cycle',
             sum(r.get('posts', 0) for r in results.values()), total_posts, total_comments, total_leads))
        conn.commit()
        cur.close()
    except Exception as e:
        conn.rollback()
        log.warning(f"Failed to store cycle run: {e}")
    
    log.info("="*50)
    log.info(f"BROWSER CYCLE COMPLETE: {json.dumps(results, default=str)}")
    log.info(f"Totals: {total_posts} posts, {total_comments} comments, {total_leads} leads")
    log.info("="*50)
    return results


# ============================================================
# MAIN ENTRY POINT
# ============================================================

if __name__ == '__main__':
    log.info("VayaVia Browser Collector v1.0 starting...")
    log.info("This runs PARALLEL to collector.py (API-based)")
    log.info(f"Cycle interval: {CYCLE_INTERVAL}s ({CYCLE_INTERVAL//60} min)")
    
    # Add source_collector column if not exists
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS source_collector TEXT DEFAULT 'api_collector'")
        conn.commit()
        cur.close()
        conn.close()
        log.info("Database schema updated (source_collector column)")
    except Exception as e:
        log.warning(f"Schema update note: {e}")
    
    while True:
        try:
            conn = get_db()
            run_browser_cycle(conn)
            conn.close()
        except Exception as e:
            log.error(f"Cycle error: {e}")
            try: conn.close()
            except: pass
        
        log.info(f"Sleeping {CYCLE_INTERVAL}s until next browser cycle...")
        time.sleep(CYCLE_INTERVAL)
