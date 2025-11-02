from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.database.models import Account, Category, Transaction, TransactionType
from app.exception import InvalidInputError, NotFoundError
from app.services.transaction_service import TransactionService


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
    service = MagicMock()
    service.convert_to_myr.side_effect = lambda amount, currency: amount
    service.get_exchange_rate.return_value = Decimal("1.0")  # Default to 1.0 for MYR
    return service


@pytest.fixture
def transaction_service(
    mock_db_session, mock_account_service, mock_category_service, mock_currency_service
):
    return TransactionService(
        mock_db_session,
        mock_account_service,
        mock_category_service,
        mock_currency_service,
    )


class TestAddTransaction:

    @pytest.mark.parametrize(
        "trans_type,cat_name,cat_type,acc_name,initial_bal,amount,desc,currency,myr_equiv,expected_bal",
        [
            (
                "income",
                "Salary",
                TransactionType.INCOME,
                "Main",
                "100",
                "50.25",
                " October salary ",
                None,
                "50.25",
                "150.25",
            ),
            (
                "expense",
                "Groceries",
                TransactionType.EXPENSE,
                "Wallet",
                "200",
                "30.50",
                "",
                None,
                "30.50",
                "169.50",
            ),
        ],
    )
    def test_add_transaction_success(
        self,
        transaction_service,
        mock_db_session,
        mock_account_service,
        mock_category_service,
        trans_type,
        cat_name,
        cat_type,
        acc_name,
        initial_bal,
        amount,
        desc,
        currency,
        myr_equiv,
        expected_bal,
    ):
        account = Account(account_name=acc_name, balance=Decimal(initial_bal))
        account.id = 1
        category = Category(name=cat_name, type=cat_type)
        category.id = 1
        mock_account_service.get_account.return_value = account
        mock_category_service.get_category_by_name_and_type.return_value = category

        # Only pass currency if it's not None
        if currency:
            transaction = transaction_service.add_transaction(
                trans_type, cat_name, acc_name, amount, desc, currency=currency
            )
        else:
            transaction = transaction_service.add_transaction(
                trans_type, cat_name, acc_name, amount, desc
            )

        assert transaction.amount == Decimal(amount)
        assert transaction.transaction_type == cat_type
        assert transaction.description == desc.strip()
        assert account.balance == Decimal(expected_bal)
        mock_db_session.add.assert_called_once_with(transaction)
        mock_db_session.commit.assert_called_once()

    def test_add_transaction_with_foreign_currency(
        self,
        transaction_service,
        mock_db_session,
        mock_account_service,
        mock_category_service,
        mock_currency_service,
    ):
        """Test adding transaction in foreign currency (USD) converts to MYR for balance."""
        account = Account(account_name="Main", balance=Decimal("1000"))
        account.id = 1
        category = Category(name="Shopping", type=TransactionType.EXPENSE)
        category.id = 1

        mock_account_service.get_account.return_value = account
        mock_category_service.get_category_by_name_and_type.return_value = category

        # Mock USD to MYR exchange rate: 1 USD = 4.50 MYR
        mock_currency_service.get_exchange_rate.return_value = Decimal("4.50")

        transaction = transaction_service.add_transaction(
            transaction_type_input="expense",
            category_name="Shopping",
            account_name="Main",
            amount="100.00",
            description="Purchase in USD",
            currency="USD",
        )

        assert transaction.amount == Decimal("100.00")
        assert transaction.currency == "USD"
        assert transaction.transaction_type == TransactionType.EXPENSE
        assert transaction.exchange_rate == Decimal("4.50")
        assert transaction.amount_in_myr == Decimal("450.00")

        # Balance should decrease by MYR equivalent (RM 450)
        assert account.balance == Decimal("550.00")  # 1000 - 450

        # Verify get_exchange_rate was called (not convert_to_myr)
        mock_currency_service.get_exchange_rate.assert_called_once_with("USD")
        mock_db_session.add.assert_called_once_with(transaction)
        mock_db_session.commit.assert_called_once()

    def test_add_transaction_category_not_exist_raises(
        self, transaction_service, mock_account_service, mock_category_service
    ):
        mock_account_service.get_account.return_value = Account(
            account_name="Main", balance=Decimal("100")
        )
        mock_category_service.get_category_by_name_and_type.return_value = None
        with pytest.raises(NotFoundError):
            transaction_service.add_transaction(
                "income", "Nonexistent", "Main", "50", "Desc"
            )

    def test_add_transaction_account_not_exist_raises(
        self, transaction_service, mock_account_service, mock_category_service
    ):
        mock_category_service.get_category_by_name_and_type.return_value = Category(
            name="Salary", type=TransactionType.INCOME
        )
        mock_account_service.get_account.return_value = None
        with pytest.raises(NotFoundError):
            transaction_service.add_transaction(
                "income", "Salary", "Missing", "50", "Desc"
            )

    @pytest.mark.parametrize(
        "trans_type,category,account,amount,currency,error_match,error_type",
        [
            ("invalid", "Food", "Main", "50", None, None, InvalidInputError),
            ("expense", "Food", "Main", "-50", None, None, InvalidInputError),
            ("expense", "", "Main", "50", None, "Category name", InvalidInputError),
            ("expense", "Food", "", "50", None, "Account name", InvalidInputError),
            (
                "expense",
                "Food",
                "Main",
                "50",
                "INVALID",
                "Unsupported currency",
                InvalidInputError,
            ),
        ],
    )
    def test_add_transaction_validation_errors(
        self,
        transaction_service,
        mock_account_service,
        mock_category_service,
        trans_type,
        category,
        account,
        amount,
        currency,
        error_match,
        error_type,
    ):
        if account:
            mock_account_service.get_account.return_value = Account(
                account_name="Main", balance=Decimal("100")
            )
        if category:
            mock_category_service.get_category_by_name_and_type.return_value = Category(
                name="Food", type=TransactionType.EXPENSE
            )

        with pytest.raises(error_type, match=error_match):
            if currency:
                transaction_service.add_transaction(
                    trans_type, category, account, amount, "Test", currency=currency
                )
            else:
                transaction_service.add_transaction(
                    trans_type, category, account, amount, "Test"
                )


class TestGetTransaction:

    def test_get_existing_transaction(self, transaction_service, mock_db_session):
        transaction = Transaction()
        mock_db_session.query().filter_by().first.return_value = transaction
        result = transaction_service.get_transaction(1)
        assert result == transaction

    def test_get_non_existing_transaction_returns_none(
        self, transaction_service, mock_db_session
    ):
        mock_db_session.query().filter_by().first.return_value = None
        result = transaction_service.get_transaction(999)
        assert result is None


class TestGetAllTransactions:

    def test_get_all_transactions_descending(
        self, transaction_service, mock_db_session
    ):
        t1 = Transaction()
        t2 = Transaction()
        mock_db_session.query().order_by().all.return_value = [t2, t1]
        result = transaction_service.get_all_transactions()
        assert result == [t2, t1]

    def test_get_all_transactions_ascending(self, transaction_service, mock_db_session):
        t1 = Transaction()
        t2 = Transaction()
        mock_db_session.query().order_by().all.return_value = [t1, t2]
        result = transaction_service.get_all_transactions(reverse_chronological=False)
        assert result == [t1, t2]

    def test_get_all_transactions_empty(self, transaction_service, mock_db_session):
        mock_db_session.query().order_by().all.return_value = []
        result = transaction_service.get_all_transactions()
        assert result == []


class TestEditTransaction:

    def test_edit_transaction_update_all_fields(
        self,
        transaction_service,
        mock_db_session,
        mock_account_service,
        mock_category_service,
        mock_currency_service,
    ):
        old_account = Account(account_name="Wallet", balance=Decimal("200"))
        new_account = Account(account_name="Bank", balance=Decimal("500"))
        old_account.id = new_account.id = 1
        old_cat = Category(name="Groceries", type=TransactionType.EXPENSE)
        new_cat = Category(name="Bills", type=TransactionType.EXPENSE)
        transaction = Transaction(
            datetime=datetime.now(),
            transaction_type=TransactionType.EXPENSE,
            amount=Decimal("50"),
            currency="MYR",
            amount_in_myr=Decimal("50"),
            exchange_rate=Decimal("1.0"),
            account=old_account,
            category=old_cat,
            description="Old",
        )
        transaction.id = 1

        transaction_service.get_transaction = MagicMock(return_value=transaction)
        mock_account_service.get_account.return_value = new_account
        mock_category_service.get_category_by_name_and_type.return_value = new_cat
        mock_currency_service.convert_to_myr.side_effect = (
            lambda amount, currency: amount
        )

        updated = transaction_service.edit_transaction(
            1, "expense", "Bills", "Bank", "30", "Updated"
        )

        assert updated.amount == Decimal("30")
        assert updated.description == "Updated"
        assert updated.account == new_account
        assert updated.category == new_cat
        assert old_account.balance == Decimal("250")
        assert new_account.balance == Decimal("470")
        mock_db_session.commit.assert_called_once()

    @pytest.mark.parametrize(
        "error_type,trans_id,type_input,cat,acc,amt,match",
        [
            (NotFoundError, 999, "", "", "", "100", "Transaction ID 999 not found"),
            (NotFoundError, 1, "expense", "Bad", "", "", "Category 'Bad' not found"),
            (NotFoundError, 1, "", "", "Bad", "", "Account 'Bad' not found"),
            (InvalidInputError, 1, "bad_type", "", "", "", None),
            (InvalidInputError, 1, "", "", "", "-100", None),
        ],
    )
    def test_edit_transaction_errors(
        self,
        transaction_service,
        mock_account_service,
        mock_category_service,
        error_type,
        trans_id,
        type_input,
        cat,
        acc,
        amt,
        match,
    ):
        if trans_id == 1:
            trans = Transaction(
                datetime=datetime.now(),
                transaction_type=TransactionType.EXPENSE,
                amount=Decimal("50"),
                currency="MYR",
                amount_in_myr=Decimal("50"),
                exchange_rate=Decimal("1.0"),
                account=Account(account_name="Main", balance=Decimal("100")),
                category=Category(name="Food", type=TransactionType.EXPENSE),
                description="Test",
            )
            trans.id = 1
            transaction_service.get_transaction = MagicMock(return_value=trans)
        else:
            transaction_service.get_transaction = MagicMock(return_value=None)

        if cat == "Bad":
            mock_category_service.get_category_by_name_and_type.return_value = None
        if acc == "Bad":
            mock_account_service.get_account.return_value = None

        with pytest.raises(error_type, match=match):
            transaction_service.edit_transaction(
                trans_id, type_input, cat, acc, amt, ""
            )


class TestDeleteTransaction:

    @pytest.mark.parametrize(
        "trans_type,amount,currency,amount_myr,initial_balance,expected_balance,should_convert",
        [
            (TransactionType.INCOME, "50", "MYR", "50", "100", "50", False),
            (TransactionType.EXPENSE, "30", "MYR", "30", "100", "130", False),
            (TransactionType.EXPENSE, "100", "USD", "450", "1000", "1450", False),
        ],
    )
    def test_delete_transaction(
        self,
        transaction_service,
        mock_db_session,
        mock_currency_service,
        trans_type,
        amount,
        currency,
        amount_myr,
        initial_balance,
        expected_balance,
        should_convert,
    ):
        account = Account(account_name="Main", balance=Decimal(initial_balance))
        transaction = Transaction(
            transaction_type=trans_type,
            amount=Decimal(amount),
            currency=currency,
            amount_in_myr=Decimal(amount_myr),
            exchange_rate=Decimal(amount_myr) / Decimal(amount),
            account=account,
        )
        transaction.id = 1
        transaction_service.get_transaction = MagicMock(return_value=transaction)
        if should_convert:
            mock_currency_service.convert_to_myr.return_value = Decimal(amount_myr)

        result = transaction_service.delete_transaction(1)
        assert result is True
        assert account.balance == Decimal(expected_balance)
        if not should_convert:
            mock_currency_service.convert_to_myr.assert_not_called()
        mock_db_session.delete.assert_called_once_with(transaction)
        mock_db_session.commit.assert_called_once()

    def test_delete_non_existing_transaction_raises(self, transaction_service):
        transaction_service.get_transaction = MagicMock(return_value=None)
        with pytest.raises(NotFoundError):
            transaction_service.delete_transaction(999)
