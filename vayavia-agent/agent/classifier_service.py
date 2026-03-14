import time
from . import db
from .utils.ollama_client import classify_signal
from .utils.text_fallbacks import keyword_classifier
from .utils.logging_utils import setup_logger

logger = setup_logger("classifier_service")

def process_unclassified_signals():
    raw_signals = db.fetch_unclassified_signals(limit=10)
    if not raw_signals:
        return 0
        
    logger.info(f"Processing {len(raw_signals)} unclassified signals...")
    count = 0
    
    for rs in raw_signals:
        text = rs["text_snippet"]
        
        # Try Ollama classification
        classification = classify_signal(text)
        
        # Fallback to keywords if LLM fails
        if not classification:
            logger.info("Ollama failed, using keyword fallback...")
            classification = keyword_classifier(text)
            
        try:
            db.insert_signal_and_lead(
                raw_signal_id=rs["id"],
                segment=classification.get("segment", "Irrelevant"),
                score=classification.get("score", 0),
                urgency=classification.get("urgency", "low"),
                text_snippet=text,
                source_url=rs["url"],
                platform=rs["source_site"]
            )
            db.mark_raw_signal_classified(rs["id"])
            count += 1
        except Exception as e:
            logger.error(f"Error saving classified signal {rs['id']}: {e}")
            
    logger.info(f"Classified {count} signals in this batch.")
    return count

if __name__ == "__main__":
    logger.info("Starting classifier service...")
    while True:
        try:
            processed = process_unclassified_signals()
            db.write_health(None, True, True, 0, f"Classified batch: {processed}")
            
            # Sleep if no work, else process next batch immediately
            if processed == 0:
                time.sleep(30)
            else:
                time.sleep(2)
                
        except Exception as e:
            logger.error(f"Classifier loop crash: {e}")
            db.write_health(None, False, True, 1, str(e))
            time.sleep(60)
