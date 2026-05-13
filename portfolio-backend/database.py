import os
from supabase import create_client, Client
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

_supabase_client: Client = None

def get_supabase() -> Client:
    global _supabase_client
    if _supabase_client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set")
        _supabase_client = create_client(url, key)
    return _supabase_client

async def init_db():
    """Initialize database tables if they don't exist"""
    logger.info("Database connection initialized (tables managed via Supabase dashboard)")
    # Tables are created via SQL in Supabase dashboard
    # See supabase_schema.sql for the schema
    try:
        db = get_supabase()
        # Quick connectivity test
        db.table("portfolio_holdings").select("id").limit(1).execute()
        logger.info("Supabase connection successful")
    except Exception as e:
        logger.warning(f"Supabase connectivity check: {e}")
