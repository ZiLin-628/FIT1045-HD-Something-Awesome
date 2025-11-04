# app/services/filter_service.py

import logging
from sqlalchemy.orm import Session

from app.database.models import Transaction
from app.exception import NotFoundError
from app.utility import validate_non_empty_string, validate_transaction_type

logger = logging.getLogger(__name__)


class FilterService:
    """
    Service class for handling filter transaction
    """

    def __init__(self, db_session: Session, account_service, category_service) -> None:
        """
        Initialize FilterService.

        Args:
            db_session (Session): database session.
            account_service: Service for managing accounts.
            category_service: Service for managing categories.
        """

        self.db_session = db_session
        self.account_service = account_service
        self.category_service = category_service

    def filter_transaction_by_category(self, category_name: str):
        """
        Filter transactions by category.

        Args:
            category_name (str): Name of the category.

        Returns:
            list[Transaction]: Transactions associated with the category.

        Raises:
            InvalidInputError: If category_name is empty.
            NotFoundError: If the category does not exist.
        """
        logger.info(f"Filtering transactions by category: {category_name}")

        # Validate category name
        category_name = validate_non_empty_string(category_name, "Category name")

        # Check if category exist
        category = self.category_service.get_category(category_name)
        if not category:
            logger.warning(f"Filter failed: Category '{category_name}' does not exist")
            raise NotFoundError(f"Category '{category_name}' does not exist.")

        # Filter transactions which having this category
        transactions = (
            self.db_session.query(Transaction).filter_by(category_id=category.id).all()
        )
        logger.info(
            f"Found {len(transactions)} transactions for category '{category_name}'"
        )
        return transactions

    def filter_transaction_by_account(self, account_name: str):
        """
        Filter transactions by account.

        Args:
            account_name (str): Name of the account.

        Returns:
            list[Transaction]: Transactions associated with the account.

        Raises:
            InvalidInputError: If account_name is empty.
            NotFoundError: If the account does not exist.
        """
        logger.info(f"Filtering transactions by account: {account_name}")

        # Validate account name
        account_name = validate_non_empty_string(account_name, "Account name")

        # Validate if account exist
        account = self.account_service.get_account(account_name)
        if not account:
            logger.warning(f"Filter failed: Account '{account_name}' does not exist")
            raise NotFoundError(f"Account '{account_name}' does not exist.")

        # Filter transactions by account
        transactions = (
            self.db_session.query(Transaction).filter_by(account_id=account.id).all()
        )
        logger.info(
            f"Found {len(transactions)} transactions for account '{account_name}'"
        )
        return transactions

    def filter_transaction_by_transaction_type(self, transaction_type_input: str):
        """
        Filter transactions by transaction type

        Args:
            transaction_type_input (str): Transaction type as string.

        Returns:
            list[Transaction]: Transactions matching the type.

        Raises:
            InvalidInputError: If transaction type is invalid.
        """
        logger.info(
            f"Filtering transactions by transaction type: {transaction_type_input}"
        )

        # Validate transaction type
        transaction_type = validate_transaction_type(transaction_type_input)

        # Filter all transactions mathced with the specified transacion type
        transactions = (
            self.db_session.query(Transaction)
            .filter_by(transaction_type=transaction_type)
            .all()
        )
        logger.info(
            f"Found {len(transactions)} transactions of type '{transaction_type.value}'"
        )
        return transactions
