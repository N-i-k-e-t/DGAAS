import time
import random
from playwright.sync_api import sync_playwright
from . import config, db
from .utils.logging_utils import setup_logger

logger = setup_logger("collector_service")

SOURCES = [
    {
        "name": "Reddit",
        "url_template": "https://old.reddit.com/search/?q={query}&sort=new",
        "platform": "reddit",
        "post_selector": ".search-result-link",
        "queries": ["nashik resort", "nashik wine", "visit nashik", "nashik stay"]
    },
    {
        "name": "Twitter_Mock", # Direct scraping X is hard, so we assume a search page or specific URL
        "url_template": "https://nitter.net/search?f=tweets&q={query}",
        "platform": "twitter",
        "post_selector": ".timeline-item",
        "queries": ["nashik weekend", "sula trip", "nashik roadtrip"]
    }
]

def run_collector_cycle():
    logger.info("Starting collector cycle...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Block images/CSS for speed
        context.route("**/*.{png,jpg,jpeg,svg,css}", lambda route: route.abort())
        
        page = context.new_page()
        
        for source in SOURCES:
            for query in source["queries"]:
                url = source["url_template"].format(query=query.replace(" ", "+"))
                logger.info(f"Scraping {source['name']} for query: {query}")
                
                try:
                    page.goto(url, wait_until="networkidle")
                    time.sleep(random.uniform(2, 5))
                    
                    posts = page.query_selector_all(source["post_selector"])[:config.ITEMS_PER_KEYWORD]
                    logger.info(f"Found {len(posts)} potential signals.")
                    
                    for post in posts:
                        try:
                            # Extract link and text
                            link_elem = post.query_selector("a.search-title") or post.query_selector("a")
                            text_elem = post.query_selector(".search-result-text") or post.query_selector(".tweet-content") or post
                            
                            if link_elem and text_elem:
                                post_url = link_elem.get_attribute("href")
                                if post_url and post_url.startswith("/"):
                                    if source["platform"] == "reddit":
                                        post_url = "https://old.reddit.com" + post_url
                                
                                snippet = text_elem.inner_text().strip()
                                
                                if post_url and snippet:
                                    db.insert_raw_signal(source["platform"], post_url, snippet)
                        except Exception as post_err:
                            logger.error(f"Error extracting post: {post_err}")
                            
                except Exception as e:
                    logger.error(f"Error scraping {url}: {e}")
                
                # Random delay between queries
                time.sleep(random.uniform(config.SCRAPER_DELAY_MIN, config.SCRAPER_DELAY_MAX))
        
        browser.close()
    
    logger.info("Collector cycle complete.")

if __name__ == "__main__":
    while True:
        try:
            run_collector_cycle()
            db.write_health(True, None, True, 0, "Collector cycle success")
        except Exception as e:
            logger.error(f"Collector loop crash: {e}")
            db.write_health(False, None, True, 1, str(e))
        
        # Run every hour
        logger.info("Sleeping for 1 hour...")
        time.sleep(3600)
