
import sqlalchemy
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_url():
    """Get database URL based on environment."""
    if os.getenv("GAE_ENV", "").startswith("standard"):
        # Production Cloud SQL
        db_user = os.getenv("DB_USER")
        db_pass = os.getenv("DB_PASS")
        db_name = os.getenv("DB_NAME")
        cloud_sql_connection = os.getenv("CLOUD_SQL_CONNECTION_NAME")
        socket_path = f"/cloudsql/{cloud_sql_connection}"
        return f"postgresql+pg8000://{db_user}:{db_pass}@/{db_name}?unix_sock={socket_path}/.s.PGSQL.5432"
    else:
        # Local development - use SQLite
        return "sqlite:///./spartan_phalanx.db"

def init_db():
    db_url = get_db_url()
    print(f"Initializing database: {db_url}")
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        # Create registered_users table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS registered_users (
                username TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Create sessions table (if not exists, though ADK handles this usually)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                app_name TEXT,
                state TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        conn.commit()
        print("Database initialized successfully.")

if __name__ == "__main__":
    init_db()
