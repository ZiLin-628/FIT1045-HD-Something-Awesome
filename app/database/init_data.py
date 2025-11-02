# init_data.py

import logging
from sqlalchemy.orm import Session

from app.database.models import Category, TransactionType

logger = logging.getLogger(__name__)


def initialize_default_categories(db_session: Session) -> None:
    """
    Initialize default categories if they don't already exist.
    This function is idempotent - it can be called multiple times safely.
    """
    logger.info("Initializing default categories")

    # Define default expense categories
    default_expense_categories = [
        "Food",
        "Transportation",
        "Shopping",
        "Entertainment",
        "Bills",
        "Healthcare",
        "Education",
        "Other expenses",
    ]

    # Define default income categories
    default_income_categories = [
        "Salary",
        "Investment",
        "Gift",
        "Other income",
    ]

    # Check if any categories exist
    existing_categories = db_session.query(Category).first()

    # Only initialize if no categories exist
    if existing_categories is None:
        logger.info("No existing categories found, creating default categories")
        # Add expense categories
        for category_name in default_expense_categories:
            category = Category(name=category_name, type=TransactionType.EXPENSE)
            db_session.add(category)
            logger.debug(f"Added expense category: {category_name}")

        # Add income categories
        for category_name in default_income_categories:
            category = Category(name=category_name, type=TransactionType.INCOME)
            db_session.add(category)
            logger.debug(f"Added income category: {category_name}")

        # Commit all categories at once
        db_session.commit()
        logger.info("Default categories initialized successfully")
    else:
        logger.info("Categories already exist, skipping initialization")

