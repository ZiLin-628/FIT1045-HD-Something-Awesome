from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.database.models import Account, Category, Transaction, TransactionType
from app.exception import InvalidInputError, NotFoundError
from app.services.filter_service import FilterService


@pytest.fixture
def mock_db_session():
    return MagicMock()


@pytest.fixture
def mock_account_service():
    return MagicMock()


@pytest.fixture
def mock_category_service():
    return MagicMock()


@pytest.fixture
def filter_service(mock_db_session, mock_account_service, mock_category_service):
    return FilterService(mock_db_session, mock_account_service, mock_category_service)


# ---------------------------
# Helper to create mock transactions
# ---------------------------
def create_transaction(
    id=1,
    account_id=1,
    category_id=1,
    t_type=TransactionType.EXPENSE,
    amount=Decimal("10.00"),
):
    transaction = Transaction(
        id=id,
        account_id=account_id,
        category_id=category_id,
        transaction_type=t_type,
        amount=amount,
        currency="MYR",
        amount_in_myr=amount,  # For tests, use same amount
        datetime=datetime.now(),
        description="Test transaction",
    )
    return transaction


# ===========================
# Tests for filter by category
# ===========================
class TestFilterByCategory:

    def test_existing_category_returns_transactions(
        self, filter_service, mock_category_service, mock_db_session
    ):
        category = Category(id=1, name="Food", type=TransactionType.EXPENSE)
        mock_category_service.get_category.return_value = category
        transactions = [
            create_transaction(id=1, category_id=1),
            create_transaction(id=2, category_id=1),
        ]
        mock_db_session.query.return_value.filter_by.return_value.all.return_value = (
            transactions
        )

        result = filter_service.filter_transaction_by_category("Food")
        assert result == transactions

    def test_category_with_no_transactions_returns_empty_list(
        self, filter_service, mock_category_service, mock_db_session
    ):
        category = Category(id=1, name="Empty", type=TransactionType.EXPENSE)
        mock_category_service.get_category.return_value = category
        mock_db_session.query.return_value.filter_by.return_value.all.return_value = []

        result = filter_service.filter_transaction_by_category("Empty")
        assert result == []

    def test_category_name_trim_and_case_insensitive(
        self, filter_service, mock_category_service, mock_db_session
    ):
        category = Category(id=1, name="Food", type=TransactionType.EXPENSE)
        mock_category_service.get_category.return_value = category
        transaction = create_transaction(category_id=1)
        mock_db_session.query.return_value.filter_by.return_value.all.return_value = [
            transaction
        ]

        result = filter_service.filter_transaction_by_category("  food  ")
        assert result == [transaction]

    def test_empty_category_name_raises_error(self, filter_service):
        with pytest.raises(InvalidInputError):
            filter_service.filter_transaction_by_category("  ")

    def test_nonexistent_category_raises_error(
        self, filter_service, mock_category_service
    ):
        mock_category_service.get_category.return_value = None
        with pytest.raises(NotFoundError):
            filter_service.filter_transaction_by_category("Unknown")


# ===========================
# Tests for filter by account
# ===========================
class TestFilterByAccount:

    def test_existing_account_returns_transactions(
        self, filter_service, mock_account_service, mock_db_session
    ):
        account = Account(id=1, account_name="Wallet", balance=Decimal("100.00"))
        mock_account_service.get_account.return_value = account
        transactions = [
            create_transaction(id=1, account_id=1),
            create_transaction(id=2, account_id=1),
        ]
        mock_db_session.query.return_value.filter_by.return_value.all.return_value = (
            transactions
        )

        result = filter_service.filter_transaction_by_account("Wallet")
        assert result == transactions

    def test_account_with_no_transactions_returns_empty_list(
        self, filter_service, mock_account_service, mock_db_session
    ):
        account = Account(id=1, account_name="Empty", balance=Decimal("0.00"))
        mock_account_service.get_account.return_value = account
        mock_db_session.query.return_value.filter_by.return_value.all.return_value = []

        result = filter_service.filter_transaction_by_account("Empty")
        assert result == []

    def test_account_name_trim_and_case_insensitive(
        self, filter_service, mock_account_service, mock_db_session
    ):
        account = Account(id=1, account_name="Wallet", balance=Decimal("100.00"))
        mock_account_service.get_account.return_value = account
        transaction = create_transaction(account_id=1)
        mock_db_session.query.return_value.filter_by.return_value.all.return_value = [
            transaction
        ]

        result = filter_service.filter_transaction_by_account("  wallet  ")
        assert result == [transaction]

    def test_empty_account_name_raises_error(self, filter_service):
        with pytest.raises(InvalidInputError):
            filter_service.filter_transaction_by_account("  ")

    def test_nonexistent_account_raises_error(
        self, filter_service, mock_account_service
    ):
        mock_account_service.get_account.return_value = None
        with pytest.raises(NotFoundError):
            filter_service.filter_transaction_by_account("Unknown")


# ========================================
# Tests for filter by transaction type
# ========================================
class TestFilterByTransactionType:

    def test_filter_income_transactions(self, filter_service, mock_db_session):
        transaction = create_transaction(id=1, t_type=TransactionType.INCOME)
        mock_db_session.query.return_value.filter_by.return_value.all.return_value = [
            transaction
        ]

        result = filter_service.filter_transaction_by_transaction_type("income")
        assert result == [transaction]

    def test_filter_expense_transactions(self, filter_service, mock_db_session):
        transaction = create_transaction(id=1, t_type=TransactionType.EXPENSE)
        mock_db_session.query.return_value.filter_by.return_value.all.return_value = [
            transaction
        ]

        result = filter_service.filter_transaction_by_transaction_type("expense")
        assert result == [transaction]

    def test_transaction_type_trim_and_case_insensitive(
        self, filter_service, mock_db_session
    ):
        transaction = create_transaction(id=1, t_type=TransactionType.EXPENSE)
        mock_db_session.query.return_value.filter_by.return_value.all.return_value = [
            transaction
        ]

        result = filter_service.filter_transaction_by_transaction_type("  ExPeNse ")
        assert result == [transaction]

    def test_invalid_transaction_type_raises_error(self, filter_service):
        with pytest.raises(InvalidInputError):
            filter_service.filter_transaction_by_transaction_type("invalid")

    def test_empty_transaction_type_raises_error(self, filter_service):
        with pytest.raises(InvalidInputError):
            filter_service.filter_transaction_by_transaction_type("")


# ===========================
# Integration / Combined Filters
# ===========================
class TestCombinedFilters:

    def test_filter_by_category_then_account(
        self,
        filter_service,
        mock_category_service,
        mock_account_service,
        mock_db_session,
    ):
        category = Category(id=1, name="Food", type=TransactionType.EXPENSE)
        account = Account(id=1, account_name="Wallet", balance=Decimal("100.00"))
        mock_category_service.get_category.return_value = category
        mock_account_service.get_account.return_value = account

        transaction = create_transaction(account_id=1, category_id=1)
        mock_db_session.query.return_value.filter_by.return_value.all.return_value = [
            transaction
        ]

        category_filtered = filter_service.filter_transaction_by_category("Food")
        account_filtered = filter_service.filter_transaction_by_account("Wallet")

        # Simulate intersection of results for combined filtering
        result = [t for t in category_filtered if t in account_filtered]
        assert result == [transaction]

    def test_add_edit_delete_transaction_reflects_in_filter(
        self,
        filter_service,
        mock_category_service,
        mock_account_service,
        mock_db_session,
    ):
        # Initial transaction
        category = Category(id=1, name="Food", type=TransactionType.EXPENSE)
        account = Account(id=1, account_name="Wallet", balance=Decimal("100.00"))
        transaction = create_transaction(account_id=1, category_id=1)
        mock_category_service.get_category.return_value = category
        mock_account_service.get_account.return_value = account
        mock_db_session.query.return_value.filter_by.return_value.all.return_value = [
            transaction
        ]

        # Add a new transaction
        new_transaction = create_transaction(id=2, account_id=1, category_id=1)
        transactions = [transaction, new_transaction]
        mock_db_session.query.return_value.filter_by.return_value.all.return_value = (
            transactions
        )

        result = filter_service.filter_transaction_by_category("Food")
        assert new_transaction in result
        assert transaction in result

        # Delete transaction
        transactions.remove(transaction)
        mock_db_session.query.return_value.filter_by.return_value.all.return_value = (
            transactions
        )
        result_after_delete = filter_service.filter_transaction_by_category("Food")
        assert transaction not in result_after_delete
        assert new_transaction in result_after_delete

    def test_deleting_category_or_account_used_by_transactions_raises_error(
        self, filter_service, mock_category_service, mock_account_service
    ):
        # Category deleted while transactions exist
        mock_category_service.get_category.return_value = None
        with pytest.raises(NotFoundError):
            filter_service.filter_transaction_by_category("Food")

        # Account deleted while transactions exist
        mock_account_service.get_account.return_value = None
        with pytest.raises(NotFoundError):
            filter_service.filter_transaction_by_account("Wallet")


# ===========================
# Validation / Normalization
# ===========================
class TestNormalizationValidation:

    def test_category_account_trimmed(
        self,
        filter_service,
        mock_category_service,
        mock_account_service,
        mock_db_session,
    ):
        category = Category(id=1, name="Food", type=TransactionType.EXPENSE)
        account = Account(id=1, account_name="Wallet", balance=Decimal("100.00"))
        transaction = create_transaction(account_id=1, category_id=1)
        mock_category_service.get_category.return_value = category
        mock_account_service.get_account.return_value = account
        mock_db_session.query.return_value.filter_by.return_value.all.return_value = [
            transaction
        ]

        result_category = filter_service.filter_transaction_by_category("  food  ")
        result_account = filter_service.filter_transaction_by_account("  wallet  ")
        assert result_category == [transaction]
        assert result_account == [transaction]

    def test_transaction_type_case_insensitive(self, filter_service, mock_db_session):
        transaction = create_transaction(id=1, t_type=TransactionType.INCOME)
        mock_db_session.query.return_value.filter_by.return_value.all.return_value = [
            transaction
        ]

        result = filter_service.filter_transaction_by_transaction_type("InCoMe")
        assert result == [transaction]

    def test_empty_dataset_returns_empty_list(
        self,
        filter_service,
        mock_category_service,
        mock_account_service,
        mock_db_session,
    ):
        mock_category_service.get_category.return_value = Category(
            id=1, name="Food", type=TransactionType.EXPENSE
        )
        mock_account_service.get_account.return_value = Account(
            id=1, account_name="Wallet", balance=Decimal("0.00")
        )
        mock_db_session.query.return_value.filter_by.return_value.all.return_value = []

        assert filter_service.filter_transaction_by_category("Food") == []
        assert filter_service.filter_transaction_by_account("Wallet") == []
        assert filter_service.filter_transaction_by_transaction_type("expense") == []
