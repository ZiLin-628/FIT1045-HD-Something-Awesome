"""Initialize or reset the database."""

from app.database.base import Base, SessionLocal, engine
from app.database.init_data import initialize_default_categories
from app.setup import setup_directories


def setup_database():
    """Create all tables and initialize default data."""

    # Ensure all required directories exist
    setup_directories()

    # Create database
    Base.metadata.create_all(bind=engine)

    # Initialize default category
    db_session = SessionLocal()
    try:
        initialize_default_categories(db_session)
    finally:
        db_session.close()


if __name__ == "__main__":
    setup_database()
