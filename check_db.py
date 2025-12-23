
import sqlalchemy
from sqlalchemy import text
import os
import json

db_url = "postgresql+pg8000://spartanapp:SpartanWarrior2025!@/spartancoach?unix_sock=/cloudsql/basic-buttress-170121:us-central1:spartan-coach-db/.s.PGSQL.5432"

def check_sessions():
    engine = sqlalchemy.create_engine(db_url)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT user_id, state FROM sessions"))
        for row in result.fetchall():
            uid, state_json = row
            state = json.loads(state_json)
            notif_settings = state.get("notification_settings", {})
            print(f"User: {uid}")
            print(f"WhatsApp Number: {notif_settings.get('whatsapp_number')}")
            print("-" * 20)

if __name__ == "__main__":
    check_sessions()
