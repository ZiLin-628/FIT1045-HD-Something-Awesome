# app/utility.py

import logging
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
import sqlite3
from pathlib import Path

from app.database.models import TransactionType, BudgetPeriod
from app.exception import InvalidInputError

logger = logging.getLogger(__name__)


def format_amount(amount: str | float | Decimal) -> Decimal:
    """
    Convert input to Decimal and round to 2 decimal places.

    Args:
        amount: A string, float, or Decimal representing an amount.

    Returns:
        Decimal: Rounded amount to 2 decimal places.

    Raises:
        InvalidInputError: If the input cannot be converted to Decimal.
    """
    try:
        return Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception as e:
        logger.error(f"Failed to format amount '{amount}': {e}")
        raise InvalidInputError(f"Invalid amount format: {amount}")


def get_current_time() -> datetime:
    """
    Return current datetime.

    Returns:
        datetime: Current datetime
    """
    return datetime.now()


def validate_non_empty_string(value: str, field_name: str = "Value") -> str:
    """
    Validation for string, ensure input string is not empty

    Args:
        value: String to validate.
        field_name: Name of the field (for error message).

    Returns:
        str: Capitalized, stripped string.

    Raises:
        InvalidInputError: If the input is empty or only whitespace.
    """

    stripped_value = value.strip().capitalize()
    if not stripped_value:
        logger.warning(f"Validation failed: {field_name} is empty")
        raise InvalidInputError(f"{field_name} cannot be empty.")
    return stripped_value


def validate_transaction_type(transaction_type_input: str) -> TransactionType:
    """
    Convert string to TransactionType enum.

    Args:
        transaction_type_input: Input string representing transaction type.

    Returns:
        TransactionType: Corresponding TransactionType enum.

    Raises:
        InvalidInputError: If the type is not valid.
    """
    try:
        return TransactionType(transaction_type_input.strip().lower())
    except ValueError:
        logger.error(f"Invalid transaction type: {transaction_type_input}")
        raise InvalidInputError(
            f"'{transaction_type_input}' is not a valid transaction type."
        )


def validate_non_negative_amount(
    amount: str | float | Decimal, field_name: str = "Amount", allow_zero: bool = True
) -> Decimal:
    """
    Validate that amount is non-negative or non-zero.

    Args:
        amount: Input amount.
        field_name: Field label for error messages.
        allow_zero: Whether zero is allowed.

    Returns:
        Decimal: Validated rounded amount.

    Raises:
        InvalidInputError: If the amount is negative or zero (when allow_zero = False).
    """
    decimal_amount = format_amount(amount)

    if not allow_zero and decimal_amount == Decimal("0.00"):
        logger.warning(f"{field_name} validation failed: amount is zero")
        raise InvalidInputError(f"{field_name} must be greater than zero.")

    if decimal_amount < Decimal("0.00"):
        logger.warning(
            f"{field_name} validation failed: amount is negative ({decimal_amount})"
        )
        raise InvalidInputError(f"{field_name} cannot be negative.")

    return decimal_amount


def validate_budget_period(budget_period_onput: str) -> BudgetPeriod:
    """
    Convert string to BudgetPeriod enum.

    Args:
        budget_period_onput: Input string representing budget period.

    Returns:
        BudgetPeriod: Corresponding BudgetPeriod enum.

    Raises:
        InvalidInputError: If the type is not valid.
    """
    try:
        return BudgetPeriod(budget_period_onput.strip().lower())
    except ValueError:
        logger.error(f"Invalid budget period: {budget_period_onput}")
        raise InvalidInputError(
            f"Invalid period '{budget_period_onput}'. Must be 'weekly', 'monthly', or 'yearly'."
        )


def create_backup() -> None:
    """
    Create a backup of the database file
    """
    logger.info("Creating database backup")

    # Database file location
    db_path = Path("data/money_tracker.db")

    # Create timestamped backup filename
    timestamp = datetime.now().strftime("%d-%m-%Y %H-%M-%S")
    backup_path = Path("backups") / f"money_tracker-{timestamp}.db"

    try:
        # Use SQLite's backup API for safe backup while database is open
        source = sqlite3.connect(str(db_path))
        backup = sqlite3.connect(str(backup_path))

        with backup:
            source.backup(backup)

        backup.close()
        source.close()
        logger.info(f"Database backup created successfully: {backup_path}")
    except Exception as e:
        logger.error(f"Failed to create database backup: {e}")
        raise
