# app/services/category_service.py

import logging
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import Category, Transaction, TransactionType
from app.exception import AlreadyExistsError, CategoryInUseError, NotFoundError
from app.utility import validate_non_empty_string, validate_transaction_type

logger = logging.getLogger(__name__)


class CategoryService:
    """
    Service class to operations related to categor
    """

    def __init__(self, db_session: Session) -> None:
        """
        Initialize CategoryService.

        Args:
            db_session (Session): database session.
        """
        self.db_session = db_session

    def get_all_categories(self) -> list[Category]:
        """
        Retrieve all categories.

        Returns:
            list[Category]: List of all categories.
        """
        categories = self.db_session.query(Category).all()
        logger.info(f"Retrieved {len(categories)} categories")
        return categories

    def get_categories(self, transaction_type: TransactionType) -> list[Category]:
        """
        Get categories by transaction type.

        Args:
            transaction_type (TransactionType): Type of transaction.

        Returns:
            list[Category]: List of categories matching the type.
        """
        categories = (
            self.db_session.query(Category).filter_by(type=transaction_type).all()
        )
        logger.info(f"Retrieved {len(categories)} {transaction_type.value} categories")
        return categories

    def get_category(self, category_name) -> Category | None:
        """
        Retrieve a category by its name.

        Args:
            category_name (str): Category name.

        Returns:
            Category | None: Category object if found, else None.
        """
        category = self.db_session.query(Category).filter_by(name=category_name).first()
        if category:
            logger.info(f"Category found: {category_name}")
        else:
            logger.info(f"Category not found: {category_name}")
        return category

    def get_category_by_name_and_type(
        self, category_name: str, transaction_type: TransactionType
    ) -> Category | None:
        """
        Get category by name and type.

        Args:
            category_name (str): Category name.
            transaction_type (TransactionType): Transaction type.

        Returns:
            Category | None: Category if found, else None.
        """

        return (
            self.db_session.query(Category)
            .filter_by(name=category_name, type=transaction_type)
            .first()
        )

    def is_valid_category(
        self, category_name: str, transaction_type: TransactionType
    ) -> bool:
        """
        Check if a category exists for a transaction type.

        Args:
            category_name (str): Category name.
            transaction_type (TransactionType): Transaction type.

        Returns:
            bool: True if exists, else False.
        """
        return (
            self.get_category_by_name_and_type(category_name, transaction_type)
            is not None
        )

    def add_category(self, category: str, transaction_type_input: str) -> Category:
        """
        Add a new category.

        Args:
            category (str): Category name.
            transaction_type_input (str): Transaction type.

        Returns:
            Category: Newly created category.

        Raises:
            AlreadyExistsError: If category already exists.
        """
        logger.info(f"Adding new category: {category} ({transaction_type_input})")

        # Convert string input to TransactionType enum
        transaction_type = validate_transaction_type(transaction_type_input)

        # Validate category name
        category = validate_non_empty_string(category, "Category name")

        # Check if the category already exist
        existing = self.get_category_by_name_and_type(category, transaction_type)
        if existing:
            logger.warning(f"Category creation failed: '{category}' already exists")
            raise AlreadyExistsError(f"A category named '{category}' already exists.")

        # Create new category
        new_category = Category(name=category, type=transaction_type)
        self.db_session.add(new_category)

        try:
            self.db_session.commit()
            logger.info(f"Category created successfully: {category}")
        except IntegrityError as e:
            self.db_session.rollback()
            logger.error(f"Failed to create category {category}: {e}")
            raise AlreadyExistsError(f"A category named '{category}' already exists.")

        return new_category

    def edit_category(
        self,
        old_category_input: str,
        new_category_input: str,
        transaction_type_input: str,
    ):
        """
        Edit a category's name.

        Args:
            old_category_input (str): Current category name.
            new_category_input (str): New category name.
            transaction_type_input (str): Transaction type.

        Returns:
            Category: Updated category object.

        Raises:
            NotFoundError: If old category not found.
            AlreadyExistsError: If new name already exists.
        """
        logger.info(
            f"Editing category '{old_category_input}' to '{new_category_input}' ({transaction_type_input})"
        )

        # Convert string input to TransactionType enum
        transaction_type = validate_transaction_type(transaction_type_input)

        # Validate new category name
        old_category_input = validate_non_empty_string(
            old_category_input, "Old category name"
        )
        new_category_input = validate_non_empty_string(
            new_category_input, "New category name"
        )

        # Check if old category exist
        old_category = self.get_category_by_name_and_type(
            old_category_input, transaction_type
        )
        if not old_category:
            logger.warning(
                f"Category edit failed: '{old_category_input}' not found in {transaction_type.value} categories"
            )
            raise NotFoundError(
                f"Category '{old_category_input}' not found in {transaction_type.value} categories."
            )

        # Check if new category name already exist
        new_category = self.get_category_by_name_and_type(
            new_category_input, transaction_type
        )
        if new_category and new_category.id != old_category.id:  # type: ignore
            logger.warning(
                f"Category edit failed: '{new_category_input}' already exists"
            )
            raise AlreadyExistsError(
                f"Category '{new_category_input}' already exists. Choose a different name."
            )

        # Update the category name
        old_category.name = new_category_input

        # Save the changes
        self.db_session.commit()
        logger.info(
            f"Category renamed successfully from '{old_category_input}' to '{new_category_input}'"
        )

        return old_category

    def delete_category(self, category_name: str, transaction_type_input: str) -> bool:
        """
        Delete a category with given name and category type

        Args:
            category_name (str): Category name.
            transaction_type_input (str): Transaction type.

        Returns:
            bool: True if deleted successfully.

        Raises:
            NotFoundError: If category does not exist.
            CategoryInUseError: If category is linked to transactions.
        """
        logger.info(f"Deleting category '{category_name}' ({transaction_type_input})")

        # Convert string input to TransactionType enum
        transaction_type = validate_transaction_type(transaction_type_input)

        # Validate category name
        category_name = validate_non_empty_string(category_name, "Category name")

        # Check if category exists
        category = self.get_category_by_name_and_type(category_name, transaction_type)
        if not category:
            logger.warning(
                f"Category deletion failed: '{category_name}' does not exist"
            )
            raise NotFoundError(f"Category '{category_name}' does not exist.")

        # Check if any transactions use this category
        used = (
            self.db_session.query(Transaction)
            .filter_by(category_id=category.id, transaction_type=transaction_type)
            .first()
        )
        if used:
            logger.warning(
                f"Category deletion failed: '{category_name}' is in use by transactions"
            )
            raise CategoryInUseError(
                f"Category '{category_name}' is used by transactions and cannot be deleted."
            )

        # Remove category and save changes
        self.db_session.delete(category)
        self.db_session.commit()
        logger.info(f"Category '{category_name}' deleted successfully")

        return True
