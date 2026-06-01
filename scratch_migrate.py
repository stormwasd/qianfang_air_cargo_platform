import asyncio
from sqlalchemy import text
from app.database import SessionLocal

def run_migration():
    db = SessionLocal()
    try:
        with open("sql/migration_add_customer_new_fields.sql", "r", encoding="utf-8") as f:
            sql_statements = f.read().split(";")
            for statement in sql_statements:
                if statement.strip():
                    db.execute(text(statement))
        db.commit()
        print("Migration applied successfully.")
    except Exception as e:
        db.rollback()
        print(f"Migration failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_migration()
