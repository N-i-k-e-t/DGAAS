import psycopg2, requests, json, time, re, logging
from datetime import datetime
import feedparser
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('collector')
DB = dict(dbname='vayavia_agent', user='postgres', password='postgres', host='localhost')
WEATHER_KEY = '2dce6b15be076925e81c0765e9a3a7e4'
SUBREDDITS = ['india', 'travel', 'wine', 'IndiaTravelAdvice', 'solotravel', 'digitalnomad']
RSS_FEEDS = [
    'https://news.google.com/rss/search?q=nashik+wine+tourism&hl=en-IN&gl=IN',
    'https://news.google.com/rss/search?q=nashik+vineyard+stay&hl=en-IN&gl=IN',
    'https://news.google.com/rss/search?q=maharashtra+wine+resort&hl=en-IN&gl=IN',
]

SEGMENT_KEYWORDS = {
    'Wine Enthusiast': ['wine tasting', 'winery', 'sula', 'vineyard tour', 'sommelier', 'grapes'],
    'Weekend Getaway': ['weekend', 'getaway', 'short trip', 'day trip', '2 days'],
    'Luxury Seeker': ['luxury', 'premium', 'spa', 'resort', '5 star', 'boutique'],
    'Couples/Romance': ['couple', 'romantic', 'honeymoon', 'anniversary', 'date'],
    'Family Vacation': ['family', 'kids', 'children', 'group trip'],
    'Corporate Group': ['corporate', 'team', 'offsite', 'conference', 'retreat'],
    'Budget Traveler': ['budget', 'cheap', 'affordable', 'backpack', 'hostel'],
    'Seasonal Traveler': ['festival', 'season', 'harvest', 'grape stomping', 'winter'],
}

def get_conn():
    return psycopg2.connect(**DB)

def insert_raw(cur, src, url, txt):
    cur.execute('SELECT id FROM raw_signals WHERE url=%s', (url,))
    if cur.fetchone():
        return None
    cur.execute(
        'INSERT INTO raw_signals (source_site, url, text_snippet) VALUES (%s,%s,%s) RETURNING id',
        (src, url, txt[:500])
    )
    return cur.fetchone()[0]

def keyword_score(text):
    t = text.lower()
    high = ['book', 'stay', 'visit', 'plan', 'recommend', 'looking for', 'want to go', 'trip to nashik']
    med = ['nashik', 'wine', 'vineyard', 'winery', 'sula', 'tourism', 'maharashtra']
    score = 30
    for k in high:
        if k in t:
            score += 15
    for k in med:
        if k in t:
            score += 5
    score = min(100, score)
    seg = 'Unknown'
    best = 0
    for s, kws in SEGMENT_KEYWORDS.items():
        c = sum(1 for k in kws if k in t)
        if c > best:
            best = c
            seg = s
    if seg == 'Unknown':
        seg = 'Wine Enthusiast'
    if score >= 70:
        urg = 'high'
    elif score >= 50:
        urg = 'medium'
    else:
        urg = 'low'
    return {'segment': seg, 'score': score, 'urgency': urg, 'reasoning': f'Keyword match score {score}'}

def collect_reddit():
    signals = []
    hdrs = {'User-Agent': 'VayaVia-DemandBot/1.0'}
    for sub in SUBREDDITS:
        for kw in ['nashik', 'wine+tourism+india', 'vineyard+stay', 'maharashtra+weekend']:
            try:
                url = f'https://www.reddit.com/r/{sub}/search.json?q={kw}&sort=new&t=week&limit=10'
                r = requests.get(url, headers=hdrs, timeout=15)
                if r.status_code == 200:
                    for p in r.json().get('data', {}).get('children', []):
                        d = p.get('data', {})
                        t = d.get('title', '') + ' ' + d.get('selftext', '')[:200]
                        link = 'https://reddit.com' + d.get('permalink', '')
                        if any(k in t.lower() for k in ['nashik', 'wine', 'vineyard', 'sula', 'maharashtra', 'winery']):
                            signals.append(('reddit', link, t[:500]))
                time.sleep(2)
            except Exception:
                pass
    log.info(f'Reddit: {len(signals)} signals')
    return signals

def collect_news():
    signals = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                t = entry.get('title', '') + ' ' + entry.get('summary', '')[:200]
                if any(k in t.lower() for k in ['nashik', 'wine', 'vineyard', 'winery', 'tourism']):
                    signals.append(('google_news', entry.get('link', ''), t[:500]))
        except Exception:
            pass
    log.info(f'News: {len(signals)} signals')
    return signals

def collect_weather():
    signals = []
    try:
        r = requests.get(
            f'https://api.openweathermap.org/data/2.5/weather?q=Nashik,IN&appid={WEATHER_KEY}&units=metric',
            timeout=10
        )
        w = r.json()
        temp = w['main']['temp']
        desc = w['weather'][0]['description']
        if 20 <= temp <= 32 and 'rain' not in desc.lower():
            signals.append((
                'weather',
                'https://openweathermap.org/city/1261529',
                f'Nashik weather ideal for tourism: {temp}C, {desc}. Perfect for vineyard visits.'
            ))
    except Exception:
        pass
    for city, cid in [('Mumbai', '1275339'), ('Pune', '1259229'), ('Delhi', '1273294')]:
        try:
            r = requests.get(
                f'https://api.openweathermap.org/data/2.5/weather?q={city},IN&appid={WEATHER_KEY}&units=metric',
                timeout=10
            )
            w = r.json()
            temp = w['main']['temp']
            desc = w['weather'][0]['description']
            if temp > 35 or 'haze' in desc.lower() or 'smoke' in desc.lower():
                signals.append((
                    'weather',
                    f'https://openweathermap.org/city/{cid}',
                    f'{city} {desc} at {temp}C - escape demand to Nashik vineyards.'
                ))
        except Exception:
            pass
    log.info(f'Weather: {len(signals)} signals')
    return signals

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
                    signals.append((
                        'google_trends',
                        f'https://trends.google.com/trends/explore?q={kw.replace(" ", "+")}&geo=IN',
                        f'Google Trends spike: "{kw}" at {v}/100 interest in India.'
                    ))
    except Exception as e:
        log.warning(f'Trends error: {e}')
    log.info(f'Trends: {len(signals)} signals')
    return signals

def run_cycle():
    log.info('=' * 60)
    log.info(f'COLLECTION CYCLE at {datetime.now()}')
    log.info('=' * 60)
    sigs = collect_reddit() + collect_news() + collect_weather() + collect_trends()
    log.info(f'Total raw signals: {len(sigs)}')
    if not sigs:
        log.info('No new signals this cycle.')
        return 0
    conn = get_conn()
    cur = conn.cursor()
    ns = nl = 0
    for src, url, txt in sigs:
        rid = insert_raw(cur, src, url, txt)
        if not rid:
            continue
        ns += 1
        ai = keyword_score(txt)
        seg = ai.get('segment', 'Unknown')
        sc = min(100, max(1, int(ai.get('score', 40))))
        urg = ai.get('urgency', 'low')
        reason = ai.get('reasoning', '')
        cur.execute(
            'INSERT INTO signals (raw_signal_id, segment, score, urgency) VALUES (%s,%s,%s,%s) RETURNING id',
            (rid, seg, sc, urg)
        )
        sid = cur.fetchone()[0]
        if sc >= 50:
            h = url.split('/comments/')[0].split('/')[-1] if '/comments/' in url else src
            cur.execute(
                'INSERT INTO leads (signal_id, segment, score, urgency, platform, handle, ai_message, original_url, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (sid, seg, sc, urg, src, h, reason[:300], url, 'new' if sc >= 70 else 'nurturing')
            )
            nl += 1
    conn.commit()
    cur.close()
    conn.close()
    log.info(f'Cycle done: {ns} new signals, {nl} new leads')
    return ns

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        run_cycle()
    else:
        log.info('Starting hourly collection daemon...')
        run_cycle()
        import schedule
        schedule.every(1).hours.do(run_cycle)
        while True:
            schedule.run_pending()
            time.sleep(60)
