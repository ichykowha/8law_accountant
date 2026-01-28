# backend/database/init_db.py


def main():
    from backend.database.models import Base
    from backend.database.connection import engine
    Base.metadata.create_all(bind=engine)
    print("Database tables created.")

if __name__ == "__main__":
    main()

