
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

def register_current_user(username="anonymous"):
    db_url = get_db_url()
    print(f"Registering user '{username}' in database: {db_url}")
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        # Check if user exists
        result = conn.execute(text("SELECT 1 FROM registered_users WHERE username = :username"), {"username": username})
        if not result.fetchone():
            conn.execute(text("INSERT INTO registered_users (username) VALUES (:username)"), {"username": username})
            conn.commit()
            print(f"Successfully registered user: {username}")
        else:
            print(f"User {username} already registered.")

        # Verify
        result = conn.execute(text("SELECT * FROM registered_users"))
        users = result.fetchall()
        print(f"All registered users: {users}")

if __name__ == "__main__":
    register_current_user()
