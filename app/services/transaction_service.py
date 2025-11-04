# app/services/transaction_service.py

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.currency import validate_currency
from app.database.models import Transaction, TransactionType
from app.exception import InvalidInputError, NotFoundError
from app.utility import (
    format_amount,
    get_current_time,
    validate_non_empty_string,
    validate_non_negative_amount,
    validate_transaction_type,
)

logger = logging.getLogger(__name__)


class TransactionService:
    """Service class which handle all operations related to transactions."""

    def __init__(
        self, db_session: Session, account_service, category_service, currency_service
    ) -> None:
        """
        Initialize TransactionService.

        Args:
            db_session (Session): database session.
            account_service (AccountService): Service for managing accounts.
            category_service (CategoryService): Service for managing categories.
            currency_service (CurrencyService): Service for managing currency conversions.
        """

        self.db_session = db_session
        self.account_service = account_service
        self.category_service = category_service
        self.currency_service = currency_service

    def get_transaction(self, transaction_id: int):
        """
        Retrieve a transaction by ID.

        Args:
            transaction_id (int): Transaction ID.

        Returns:
            Transaction | None: Transaction object if found, else None.
        """
        transaction = (
            self.db_session.query(Transaction).filter_by(id=transaction_id).first()
        )
        if transaction:
            logger.info(f"Transaction found: ID {transaction_id}")
        else:
            logger.info(f"Transaction not found: ID {transaction_id}")
        return transaction

    def get_all_transactions(self, reverse_chronological: bool = True):
        """
        Retrieve all transactions, optionally sorted by datetime.

        Args:
            reverse_chronological (bool): True to sort descending, False ascending.

        Returns:
            list[Transaction]: List of transaction objects.
        """

        query = self.db_session.query(Transaction)

        if reverse_chronological:
            query = query.order_by(Transaction.datetime.desc())
        else:
            query = query.order_by(Transaction.datetime.asc())

        transactions = query.all()
        logger.info(f"Retrieved {len(transactions)} transactions")
        return transactions

    def add_transaction(
        self,
        transaction_type_input: str,
        category_name: str,
        account_name: str,
        amount: str,
        description: str,
        custom_datetime: datetime = None,
        currency: str = "MYR",
    ) -> Transaction:
        """
        Add a new transaction.

        Args:
            transaction_type_input (str): Transaction type.
            category_name (str): Category name.
            account_name (str): Account name.
            amount (str | float | Decimal): Transaction amount.
            description (str): Transaction description.
            custom_datetime (datetime, optional): Transaction date/time.
            currency (str, optional): Currency code (default: 'MYR').

        Returns:
            Transaction: Newly created transaction.

        Raises:
            InvalidInputError: If input values are invalid.
            NotFoundError: If account or category does not exist.
        """
        logger.info(
            f"Adding {transaction_type_input} transaction: {amount} {currency} to account '{account_name}'"
        )

        # Convert the transaction type string to an Enum
        transaction_type = validate_transaction_type(transaction_type_input)

        # Validate field name
        category_name = validate_non_empty_string(category_name, "Category name")
        account_name = validate_non_empty_string(account_name, "Account name")
        amount_decimal = validate_non_negative_amount(amount, "Transaction amount")
        description = description.strip()

        # Validate currency
        currency = currency.strip().upper()
        if not currency:
            logger.error("Transaction creation failed: Currency is empty")
            raise InvalidInputError("Currency cannot be empty.")
        if not validate_currency(currency):
            logger.error(
                f"Transaction creation failed: Unsupported currency {currency}"
            )
            raise InvalidInputError(f"Unsupported currency: {currency}")

        # Use custom datetime if provided, otherwise use current time
        timestamp = custom_datetime if custom_datetime else get_current_time()

        # Verify category and account exist
        category = self.category_service.get_category_by_name_and_type(
            category_name, transaction_type
        )
        if not category:
            logger.warning(
                f"Transaction creation failed: Category '{category_name}' not found for {transaction_type.value}"
            )
            raise NotFoundError(
                f"Category '{category_name}' not found for {transaction_type.value} transactions."
            )

        # Validate if account exist
        account = self.account_service.get_account(account_name)
        if not account:
            logger.warning(
                f"Transaction creation failed: Account '{account_name}' not found"
            )
            raise NotFoundError(f"Account '{account_name}' not found.")

        # Calculate exchange rate and MYR amount
        if currency == "MYR":
            exchange_rate = 1.0
            amount_in_myr = amount_decimal

        else:
            # Get the current exchange rate from currency service
            logger.info(f"Converting {amount_decimal} {currency} to MYR")
            exchange_rate = self.currency_service.get_exchange_rate(currency)
            # Convert using the same rate and format to 2 decimal places
            amount_in_myr = format_amount(amount_decimal * exchange_rate)

        # Create transaction
        transaction = Transaction(
            datetime=timestamp,
            transaction_type=transaction_type,
            category=category,
            account=account,
            amount=amount_decimal,
            currency=currency,
            amount_in_myr=amount_in_myr,
            exchange_rate=exchange_rate,
            description=description,
        )

        # Update account balance
        if transaction_type == TransactionType.INCOME:
            account.balance += amount_in_myr
        else:
            account.balance -= amount_in_myr

        # Add to collections
        self.db_session.add(transaction)

        # Save changes
        try:
            self.db_session.commit()
            logger.info(
                f"Transaction created successfully: {transaction_type.value} of {amount_in_myr} MYR in account '{account_name}'"
            )
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to create transaction: {e}")
            raise

        return transaction

    def edit_transaction(
        self,
        transaction_id: int,
        transaction_type_input: str,
        category_name: str,
        account_name: str,
        amount: str,
        description: str,
        custom_datetime: datetime = None,
    ) -> Transaction:
        """
        Edit an existing transaction.

        Args:
            transaction_id (int): ID of the transaction to edit.
            transaction_type_input (str): Transaction type.
            category_name (str): Updated category name.
            account_name (str): Updated account name.
            amount (str | float | Decimal): Updated transaction amount.
            description (str): Updated description.
            custom_datetime (datetime, optional): Updated datetime.

        Returns:
            Transaction: Updated transaction object.

        Raises:
            NotFoundError: If transaction, account, or category does not exist.
        """
        logger.info(f"Editing transaction ID {transaction_id}")

        # Check if transaction exist
        transaction = self.get_transaction(transaction_id)
        if not transaction:
            logger.warning(f"Transaction edit failed: ID {transaction_id} not found")
            raise NotFoundError(f"Transaction ID {transaction_id} not found.")

        old_type = transaction.transaction_type
        old_category = transaction.category
        old_account = transaction.account

        # Update transaction type
        new_type = old_type
        if transaction_type_input.strip():
            new_type = validate_transaction_type(transaction_type_input)

        # Update category
        new_category = old_category
        if category_name.strip():
            category_name = validate_non_empty_string(category_name, "Category name")
            category = self.category_service.get_category_by_name_and_type(
                category_name, new_type
            )
            if not category:
                raise NotFoundError(
                    f"Category '{category_name}' not found for {new_type.value} transactions."
                )
            new_category = category

        # Account
        new_account = old_account
        if account_name.strip():
            account_name = validate_non_empty_string(account_name, "Account name")
            account = self.account_service.get_account(account_name)
            if not account:
                raise NotFoundError(f"Account '{account_name}' not found.")
            new_account = account

        # Amount - only allow editing amount in the same currency
        new_amount = transaction.amount
        if amount.strip():
            new_amount = validate_non_negative_amount(amount, "Transaction amount")

        # Description
        new_description = description.strip()

        # Update datetime
        if custom_datetime:
            transaction.datetime = (
                custom_datetime if custom_datetime else get_current_time()
            )

        # Reverse old transaction using stored MYR amount
        old_amount_in_myr = transaction.amount_in_myr
        if old_type == TransactionType.INCOME:
            old_account.balance -= old_amount_in_myr
        else:
            old_account.balance += old_amount_in_myr

        # Calculate new MYR amount using stored exchange rate
        new_amount_in_myr = format_amount(new_amount * transaction.exchange_rate)

        # Update transaction fields
        transaction.transaction_type = new_type
        transaction.category = new_category
        transaction.account = new_account
        transaction.amount = new_amount
        transaction.amount_in_myr = new_amount_in_myr
        transaction.description = new_description

        # Apply new transaction effect using new MYR amount
        if new_type == TransactionType.INCOME:
            new_account.balance += new_amount_in_myr
        else:
            new_account.balance -= new_amount_in_myr

        # Save changes
        try:
            self.db_session.commit()
            logger.info(f"Transaction ID {transaction_id} edited successfully")
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to edit transaction ID {transaction_id}: {e}")
            raise

        return transaction

    def delete_transaction(self, transaction_id: int) -> bool:
        """
        Delete a transaction and reverse its effect on the account.

        Args:
            transaction_id (int): ID of the transaction to delete.

        Returns:
            bool: True if deletion succeeded.

        Raises:
            NotFoundError: If transaction does not exist.
        """
        logger.info(f"Deleting transaction ID {transaction_id}")

        # Check if transaction exist
        transaction = self.get_transaction(transaction_id)
        if not transaction:
            logger.warning(
                f"Transaction deletion failed: ID {transaction_id} not found"
            )
            raise NotFoundError(f"Transaction ID '{transaction_id}' not found.")

        account = transaction.account

        # Use stored MYR amount for balance reversal
        amount_in_myr = transaction.amount_in_myr

        # Reverse the impact on the account balance
        if transaction.transaction_type == TransactionType.INCOME:
            account.balance -= amount_in_myr
        else:
            account.balance += amount_in_myr

        # Remove transaction
        self.db_session.delete(transaction)

        try:
            self.db_session.commit()
            logger.info(f"Transaction ID {transaction_id} deleted successfully")
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to delete transaction ID {transaction_id}: {e}")
            raise

        return True
