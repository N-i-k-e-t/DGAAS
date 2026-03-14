import sys
import os
# Add parent directory to path to import agent
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import db
from agent.utils.logging_utils import setup_logger

logger = setup_logger("init_db")

def init():
    logger.info("Initializing database...")
    schema_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent", "models.sql")
    
    with open(schema_path, "r") as f:
        sql = f.read()
        
    conn = db.get_conn()
    cur = conn.cursor()
    try:
        cur.execute(sql)
        conn.commit()
        logger.info("Schema applied successfully.")
    except Exception as e:
        logger.error(f"Error applying schema: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    init()
