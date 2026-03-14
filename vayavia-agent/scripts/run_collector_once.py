import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import collector_service
from agent.utils.logging_utils import setup_logger

logger = setup_logger("test_collector")

if __name__ == "__main__":
    logger.info("Running manual collector cycle...")
    collector_service.run_collector_cycle()
    logger.info("Manual cycle finished.")
