from sqlalchemy import create_engine, Column, Integer, DateTime
from sqlalchemy.sql import text
from src.database.database_handler import Base, DATABASE_URL

def upgrade():
    engine = create_engine(DATABASE_URL)
    
    # Add new columns one at a time
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE goals ADD COLUMN target_minutes INTEGER"))
        conn.execute(text("ALTER TABLE goals ADD COLUMN time_spent_minutes INTEGER DEFAULT 0"))
        conn.execute(text("ALTER TABLE goals ADD COLUMN last_tracked_at TIMESTAMP"))
        conn.commit()

def downgrade():
    engine = create_engine(DATABASE_URL)
    
    # Remove columns one at a time
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE goals DROP COLUMN target_minutes"))
        conn.execute(text("ALTER TABLE goals DROP COLUMN time_spent_minutes"))
        conn.execute(text("ALTER TABLE goals DROP COLUMN last_tracked_at"))
        conn.commit()

if __name__ == "__main__":
    upgrade() 