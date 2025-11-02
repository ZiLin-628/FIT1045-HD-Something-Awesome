# tests/test_account_service.py

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.database.models import Account
from app.exception import AlreadyExistsError, InvalidInputError, NotFoundError
from app.services.account_service import AccountService


@pytest.fixture
def mock_db_session():
    return MagicMock()


@pytest.fixture
def mock_currency_service():
    """Mock currency service for testing."""
    mock = MagicMock()
    # Default: 1:1 conversion (no conversion needed)
    mock.convert_to_myr = MagicMock(side_effect=lambda amount, currency: amount)
    return mock


@pytest.fixture
def account_service(mock_db_session, mock_currency_service):
    return AccountService(mock_db_session, mock_currency_service)


class TestAddAccount:

    @pytest.mark.parametrize(
        "name,balance,expected_name,expected_balance",
        [
            ("Savings", "100.00", "Savings", Decimal("100.00")),  # Normal case
            ("Zero Balance", "0", "Zero balance", Decimal("0.00")),  # Zero balance
            (
                "Test Account",
                "100.1234   ",
                "Test account",
                Decimal("100.12"),
            ),  # Rounded to 2 decimals and can trip space
            (
                "  mixed case  ",
                "10",
                "Mixed case",
                Decimal("10.00"),
            ),  # Trim and capitalize
            (
                "Big Balance",
                "999999999999.99",
                "Big balance",
                Decimal("999999999999.99"),
            ),  # Big number
        ],
    )
    def test_add_account_success(
        self,
        account_service,
        mock_db_session,
        name,
        balance,
        expected_name,
        expected_balance,
    ):
        # No existing account
        mock_db_session.query().filter_by().first.return_value = None
        mock_db_session.add.return_value = None
        mock_db_session.commit.return_value = None

        account = account_service.add_account(name, balance)

        assert account.account_name == expected_name
        assert account.balance == expected_balance
        mock_db_session.add.assert_called_once_with(account)
        mock_db_session.commit.assert_called_once()

    @pytest.mark.parametrize(
        "name,balance,expected_exception",
        [
            ("", "10", InvalidInputError),  # Empty name
            ("   ", "10", InvalidInputError),  # Name contain spaces only
            ("Test", "-5", InvalidInputError),  # Negative balance
        ],
    )
    def test_add_account_invalid_input_raises(
        self, account_service, name, balance, expected_exception
    ):
        with pytest.raises(expected_exception):
            account_service.add_account(name, balance)

    def test_add_account_non_numeric_balance_raises(self, account_service):
        with patch(
            "app.services.account_service.validate_non_negative_amount",
            side_effect=InvalidInputError,
        ):
            with pytest.raises(InvalidInputError):
                account_service.add_account("Test", "abc")

    def test_add_account_duplicate_name_raises(self, account_service, mock_db_session):
        existing_account = Account(account_name="Test account", balance=Decimal("0.00"))
        mock_db_session.query().filter_by().first.return_value = existing_account

        with pytest.raises(AlreadyExistsError):
            account_service.add_account("Test account", "10")

    def test_add_account_with_foreign_currency(
        self, account_service, mock_db_session, mock_currency_service
    ):
        """Test adding account with foreign currency converts to MYR."""
        # No existing account
        mock_db_session.query().filter_by().first.return_value = None

        # Mock USD to MYR conversion: $1000 USD = RM 4500
        mock_currency_service.convert_to_myr = MagicMock(
            return_value=Decimal("4500.00")
        )

        account = account_service.add_account("USD Wallet", "1000.00", currency="USD")

        assert account.account_name == "Usd wallet"
        assert account.balance == Decimal("4500.00")  # Converted to MYR

        # Verify conversion was called
        mock_currency_service.convert_to_myr.assert_called_once_with(
            Decimal("1000.00"), "USD"
        )
        mock_db_session.add.assert_called_once_with(account)
        mock_db_session.commit.assert_called_once()

    def test_add_account_with_myr_currency_no_conversion(
        self, account_service, mock_db_session, mock_currency_service
    ):
        """Test adding account with MYR doesn't trigger conversion."""
        # No existing account
        mock_db_session.query().filter_by().first.return_value = None

        account = account_service.add_account("MYR Account", "1000.00", currency="MYR")

        assert account.account_name == "Myr account"
        assert account.balance == Decimal("1000.00")

        # Verify conversion was NOT called (MYR to MYR)
        mock_currency_service.convert_to_myr.assert_not_called()
        mock_db_session.add.assert_called_once_with(account)
        mock_db_session.commit.assert_called_once()


class TestGetAccount:

    @pytest.mark.parametrize(
        "input_name",
        [
            "Test account",  # Exact match
            "  Test account  ",  # With spaces
            "tEsT aCcOuNt",  # Different case
        ],
    )
    def test_get_existing_account(self, account_service, mock_db_session, input_name):
        existing = Account(account_name="Test account", balance=Decimal("50"))
        mock_db_session.query().filter_by().first.return_value = existing
        account = account_service.get_account(input_name)
        assert account == existing

    def test_get_non_existing_account_returns_none(
        self, account_service, mock_db_session
    ):
        mock_db_session.query().filter_by().first.return_value = None
        account = account_service.get_account("Nonexistent")
        assert account is None

    def test_get_account_empty_name_raises(self, account_service):
        with pytest.raises(InvalidInputError):
            account_service.get_account("")

        with pytest.raises(InvalidInputError):
            account_service.get_account("   ")


class TestGetAllAccounts:

    def test_get_all_accounts(self, account_service, mock_db_session):
        accounts = [
            Account(account_name="A", balance=Decimal("1")),
            Account(account_name="B", balance=Decimal("2")),
        ]
        mock_db_session.query().all.return_value = accounts
        result = account_service.get_all_accounts()
        assert result == accounts

    def test_get_all_accounts_empty(self, account_service, mock_db_session):
        mock_db_session.query().all.return_value = []
        result = account_service.get_all_accounts()
        assert result == []


class TestEditAccountName:

    @pytest.mark.parametrize(
        "old_name,new_name,expected_name",
        [
            ("Old Name", "New Name", "New name"),  # Rename success
            ("Same Name", "Same name", "Same name"),  # Same name no error
        ],
    )
    def test_rename_account_success(
        self, account_service, mock_db_session, old_name, new_name, expected_name
    ):
        account = Account(account_name=old_name, balance=Decimal("10"))
        # old exists, new either doesn't exist or is the same account
        mock_db_session.query().filter_by().first.side_effect = [
            account,
            None if old_name != new_name else account,
        ]
        updated = account_service.edit_account_name(old_name, new_name)
        assert updated.account_name == expected_name

    @pytest.mark.parametrize(
        "old_name,new_name,expected_exception",
        [
            ("", "New", InvalidInputError),  # Empty old name
            ("Old", "", InvalidInputError),  # Empty new name
        ],
    )
    def test_rename_invalid_input_raises(
        self, account_service, old_name, new_name, expected_exception
    ):
        with pytest.raises(expected_exception):
            account_service.edit_account_name(old_name, new_name)

    def test_rename_non_existing_old_account_raises(
        self, account_service, mock_db_session
    ):
        mock_db_session.query().filter_by().first.return_value = None
        with pytest.raises(NotFoundError):
            account_service.edit_account_name("DoesNotExist", "NewName")

    def test_rename_to_existing_name_raises(self, account_service, mock_db_session):
        old_account = Account(account_name="Old", balance=Decimal("10"))
        old_account.id = 1
        new_account = Account(account_name="New", balance=Decimal("20"))
        new_account.id = 2
        mock_db_session.query().filter_by().first.side_effect = [
            old_account,
            new_account,
        ]

        with pytest.raises(AlreadyExistsError):
            account_service.edit_account_name("Old", "New")


class TestDeleteAccount:

    @pytest.mark.parametrize(
        "input_name,stored_name",
        [
            ("ToDelete", "ToDelete"),  # Exact match
            ("  DeleteMe  ", "DeleteMe"),  # With spaces
        ],
    )
    def test_delete_existing_account(
        self, account_service, mock_db_session, input_name, stored_name
    ):
        account = Account(account_name=stored_name, balance=Decimal("10"))
        mock_db_session.query().filter_by().first.return_value = account
        result = account_service.delete_account(input_name)
        assert result is True
        mock_db_session.delete.assert_called_once_with(account)
        mock_db_session.commit.assert_called_once()

    def test_delete_non_existing_account_raises(self, account_service, mock_db_session):
        mock_db_session.query().filter_by().first.return_value = None
        with pytest.raises(NotFoundError):
            account_service.delete_account("Nonexistent")

    def test_delete_empty_name_raises(self, account_service):
        with pytest.raises(InvalidInputError):
            account_service.delete_account("")
