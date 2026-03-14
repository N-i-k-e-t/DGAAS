import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import classifier_service
from agent.utils.logging_utils import setup_logger

logger = setup_logger("test_classifier")

if __name__ == "__main__":
    logger.info("Running manual classifier iteration...")
    processed = classifier_service.process_unclassified_signals()
    logger.info(f"Manual iteration finished. Processed {processed} signals.")
