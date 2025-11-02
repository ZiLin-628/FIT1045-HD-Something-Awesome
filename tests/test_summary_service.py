# tests/test_summary_service.py

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.database.models import Account, Category, Transaction, TransactionType
from app.services.summary_service import SummaryService


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
def mock_currency_service():
    """Mock currency service for testing."""
    mock = MagicMock()
    # Default: 1:1 conversion (all amounts treated as MYR)
    mock.convert_to_myr = MagicMock(side_effect=lambda amount, currency: amount)
    return mock


@pytest.fixture
def summary_service(
    mock_db_session, mock_account_service, mock_category_service, mock_currency_service
):
    return SummaryService(
        mock_db_session,
        mock_account_service,
        mock_category_service,
        mock_currency_service,
    )


def create_transaction(amount, trans_type, category_name, date_time, currency="MYR"):
    """Helper function to create a transaction."""
    account = Account(account_name="Test", balance=Decimal("0"))
    category = Category(name=category_name, type=trans_type)
    amount_decimal = Decimal(str(amount))
    return Transaction(
        datetime=date_time,
        transaction_type=trans_type,
        amount=amount_decimal,
        currency=currency,
        amount_in_myr=amount_decimal,  # For tests, use same amount as MYR equivalent
        account=account,
        category=category,
        description="",
    )


class TestGetTransactionsInRange:

    def test_get_transactions_success(self, summary_service, mock_db_session):
        start = datetime(2025, 1, 1)
        end = datetime(2025, 1, 31)
        t1 = create_transaction(
            100, TransactionType.INCOME, "Salary", datetime(2025, 1, 15)
        )

        mock_query = MagicMock()
        mock_query.filter().all.return_value = [t1]
        mock_db_session.query.return_value = mock_query

        result = summary_service._get_transactions_in_range(start, end)
        assert len(result) == 1

    def test_get_transactions_with_type_filter(self, summary_service, mock_db_session):
        start = datetime(2025, 1, 1)
        end = datetime(2025, 1, 31)
        t1 = create_transaction(
            100, TransactionType.INCOME, "Salary", datetime(2025, 1, 15)
        )

        mock_query = MagicMock()
        mock_query.filter().filter().all.return_value = [t1]
        mock_db_session.query.return_value = mock_query

        result = summary_service._get_transactions_in_range(
            start, end, TransactionType.INCOME
        )
        assert len(result) == 1

    def test_get_transactions_empty(self, summary_service, mock_db_session):
        mock_query = MagicMock()
        mock_query.filter().all.return_value = []
        mock_db_session.query.return_value = mock_query

        result = summary_service._get_transactions_in_range(
            datetime(2025, 1, 1), datetime(2025, 1, 31)
        )
        assert result == []


class TestGetDailySummary:

    def test_daily_summary_mixed_transactions(self, summary_service, mock_db_session):
        date = datetime(2025, 1, 15)
        t1 = create_transaction(100, TransactionType.INCOME, "Salary", date)
        t2 = create_transaction(30, TransactionType.EXPENSE, "Food", date)

        mock_query = MagicMock()
        mock_query.filter().all.return_value = [t1, t2]
        mock_db_session.query.return_value = mock_query

        result = summary_service.get_daily_summary(date)

        assert result["date"] == "15-01-2025"
        assert result["total_income"] == Decimal("100")
        assert result["total_expense"] == Decimal("30")
        assert result["net"] == Decimal("70")
        assert result["transaction_count"] == 2

    def test_daily_summary_only_income(self, summary_service, mock_db_session):
        date = datetime(2025, 1, 15)
        t1 = create_transaction(100, TransactionType.INCOME, "Salary", date)

        mock_query = MagicMock()
        mock_query.filter().all.return_value = [t1]
        mock_db_session.query.return_value = mock_query

        result = summary_service.get_daily_summary(date)
        assert result["total_income"] == Decimal("100")
        assert result["total_expense"] == Decimal("0")

    def test_daily_summary_no_transactions(self, summary_service, mock_db_session):
        mock_query = MagicMock()
        mock_query.filter().all.return_value = []
        mock_db_session.query.return_value = mock_query

        result = summary_service.get_daily_summary(datetime(2025, 1, 15))

        assert result["total_income"] == Decimal("0")
        assert result["total_expense"] == Decimal("0")
        assert result["net"] == Decimal("0")
        assert result["transaction_count"] == 0


class TestGetWeeklySummary:

    def test_weekly_summary_success(self, summary_service, mock_db_session):
        date = datetime(2025, 1, 15)
        t1 = create_transaction(
            100, TransactionType.INCOME, "Salary", datetime(2025, 1, 13)
        )
        t2 = create_transaction(
            30, TransactionType.EXPENSE, "Food", datetime(2025, 1, 15)
        )

        mock_query = MagicMock()
        mock_query.filter().all.return_value = [t1, t2]
        mock_db_session.query.return_value = mock_query

        result = summary_service.get_weekly_summary(date)

        assert result["total_income"] == Decimal("100")
        assert result["total_expense"] == Decimal("30")
        assert result["net"] == Decimal("70")
        assert result["transaction_count"] == 2

    def test_weekly_summary_no_transactions(self, summary_service, mock_db_session):
        mock_query = MagicMock()
        mock_query.filter().all.return_value = []
        mock_db_session.query.return_value = mock_query

        result = summary_service.get_weekly_summary(datetime(2025, 1, 15))
        assert result["transaction_count"] == 0


class TestGetMonthlySummary:

    def test_monthly_summary_success(self, summary_service, mock_db_session):
        t1 = create_transaction(
            1000, TransactionType.INCOME, "Salary", datetime(2025, 1, 5)
        )
        t2 = create_transaction(
            200, TransactionType.EXPENSE, "Food", datetime(2025, 1, 15)
        )

        mock_query = MagicMock()
        mock_query.filter().all.return_value = [t1, t2]
        mock_db_session.query.return_value = mock_query

        result = summary_service.get_monthly_summary(2025, 1)

        assert result["month"] == "January"
        assert result["year"] == 2025
        assert result["total_income"] == Decimal("1000")
        assert result["total_expense"] == Decimal("200")
        assert result["net"] == Decimal("800")
        assert result["transaction_count"] == 2

    def test_monthly_summary_invalid_month(self, summary_service):
        assert summary_service.get_monthly_summary(2025, 0) == {}
        assert summary_service.get_monthly_summary(2025, 13) == {}

    def test_monthly_summary_invalid_year(self, summary_service):
        assert summary_service.get_monthly_summary(0, 1) == {}
        assert summary_service.get_monthly_summary(-1, 1) == {}

    def test_monthly_summary_december(self, summary_service, mock_db_session):
        t1 = create_transaction(
            1000, TransactionType.INCOME, "Salary", datetime(2025, 12, 15)
        )

        mock_query = MagicMock()
        mock_query.filter().all.return_value = [t1]
        mock_db_session.query.return_value = mock_query

        result = summary_service.get_monthly_summary(2025, 12)
        assert result["month"] == "December"

    def test_monthly_summary_no_transactions(self, summary_service, mock_db_session):
        mock_query = MagicMock()
        mock_query.filter().all.return_value = []
        mock_db_session.query.return_value = mock_query

        result = summary_service.get_monthly_summary(2025, 1)
        assert result["transaction_count"] == 0


class TestGetExpensesByCategory:

    def test_expenses_by_category_success(self, summary_service, mock_db_session):
        start_date = datetime(2025, 1, 1)
        end_date = datetime(2025, 1, 31)

        t1 = create_transaction(
            50, TransactionType.EXPENSE, "Food", datetime(2025, 1, 5)
        )
        t2 = create_transaction(
            30, TransactionType.EXPENSE, "Food", datetime(2025, 1, 15)
        )
        t3 = create_transaction(
            20, TransactionType.EXPENSE, "Transport", datetime(2025, 1, 10)
        )

        mock_query = MagicMock()
        mock_query.filter().filter().all.return_value = [t1, t2, t3]
        mock_db_session.query.return_value = mock_query

        result = summary_service.get_expenses_by_category(start_date, end_date)

        assert result["Food"] == Decimal("80")
        assert result["Transport"] == Decimal("20")

    def test_expenses_by_category_no_transactions(
        self, summary_service, mock_db_session
    ):
        mock_query = MagicMock()
        mock_query.filter().filter().all.return_value = []
        mock_db_session.query.return_value = mock_query

        result = summary_service.get_expenses_by_category(
            datetime(2025, 1, 1), datetime(2025, 1, 31)
        )
        assert result == {}

    def test_expenses_by_category_start_after_end(self, summary_service):
        result = summary_service.get_expenses_by_category(
            datetime(2025, 1, 31), datetime(2025, 1, 1)
        )
        assert result == {}


class TestGetIncomeByCategory:

    def test_income_by_category_success(self, summary_service, mock_db_session):
        start_date = datetime(2025, 1, 1)
        end_date = datetime(2025, 1, 31)

        t1 = create_transaction(
            1000, TransactionType.INCOME, "Salary", datetime(2025, 1, 5)
        )
        t2 = create_transaction(
            500, TransactionType.INCOME, "Salary", datetime(2025, 1, 15)
        )
        t3 = create_transaction(
            200, TransactionType.INCOME, "Freelance", datetime(2025, 1, 10)
        )

        mock_query = MagicMock()
        mock_query.filter().filter().all.return_value = [t1, t2, t3]
        mock_db_session.query.return_value = mock_query

        result = summary_service.get_income_by_category(start_date, end_date)

        assert result["Salary"] == Decimal("1500")
        assert result["Freelance"] == Decimal("200")

    def test_income_by_category_no_transactions(self, summary_service, mock_db_session):
        mock_query = MagicMock()
        mock_query.filter().filter().all.return_value = []
        mock_db_session.query.return_value = mock_query

        result = summary_service.get_income_by_category(
            datetime(2025, 1, 1), datetime(2025, 1, 31)
        )
        assert result == {}

    def test_income_by_category_start_after_end(self, summary_service):
        result = summary_service.get_income_by_category(
            datetime(2025, 1, 31), datetime(2025, 1, 1)
        )
        assert result == {}
