# tests/test_category_service.py

from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.database.models import Category, Transaction, TransactionType
from app.exception import (
    AlreadyExistsError,
    CategoryInUseError,
    InvalidInputError,
    NotFoundError,
)
from app.services.category_service import CategoryService


@pytest.fixture
def mock_db_session():
    return MagicMock()


@pytest.fixture
def category_service(mock_db_session):
    return CategoryService(mock_db_session)


class TestGetCategories:

    @pytest.mark.parametrize(
        "transaction_type,category_name,expected_count",
        [
            (TransactionType.INCOME, "Salary", 1),
            (TransactionType.EXPENSE, "Groceries", 1),
            (TransactionType.EXPENSE, "Empty", 0),
        ],
    )
    def test_get_categories(
        self,
        category_service,
        mock_db_session,
        transaction_type,
        category_name,
        expected_count,
    ):
        if expected_count > 0:
            category = Category(name=category_name, type=transaction_type)
            mock_db_session.query().filter_by().all.return_value = [category]
            result = category_service.get_categories(transaction_type)
            assert result == [category]
        else:
            mock_db_session.query().filter_by().all.return_value = []
            result = category_service.get_categories(transaction_type)
            assert result == []


class TestGetAllCategories:

    @pytest.mark.parametrize(
        "categories,expected_count",
        [
            (
                [
                    Category(name="Salary", type=TransactionType.INCOME),
                    Category(name="Groceries", type=TransactionType.EXPENSE),
                ],
                2,
            ),
            ([], 0),
        ],
    )
    def test_get_all_categories(
        self, category_service, mock_db_session, categories, expected_count
    ):
        mock_db_session.query().all.return_value = categories
        result = category_service.get_all_categories()
        assert result == categories
        assert len(result) == expected_count


class TestGetCategory:

    def test_get_existing_category(self, category_service, mock_db_session):
        cat = Category(name="Salary", type=TransactionType.INCOME)
        mock_db_session.query().filter_by().first.return_value = cat
        result = category_service.get_category("Salary")
        assert result == cat

    def test_get_non_existing_category_returns_none(
        self, category_service, mock_db_session
    ):
        mock_db_session.query().filter_by().first.return_value = None
        result = category_service.get_category("Nonexistent")
        assert result is None


class TestGetCategoryByNameAndType:

    def test_get_existing_category_by_name_and_type(
        self, category_service, mock_db_session
    ):
        cat = Category(name="Salary", type=TransactionType.INCOME)
        mock_db_session.query().filter_by().first.return_value = cat
        result = category_service.get_category_by_name_and_type(
            "Salary", TransactionType.INCOME
        )
        assert result == cat

    def test_category_does_not_exist_for_type(self, category_service, mock_db_session):
        mock_db_session.query().filter_by().first.return_value = None
        result = category_service.get_category_by_name_and_type(
            "Salary", TransactionType.EXPENSE
        )
        assert result is None


class TestIsValidCategory:

    def test_category_exists_returns_true(self, category_service, mock_db_session):
        cat = Category(name="Salary", type=TransactionType.INCOME)
        category_service.get_category_by_name_and_type = MagicMock(return_value=cat)
        assert (
            category_service.is_valid_category("Salary", TransactionType.INCOME) is True
        )

    def test_category_not_exists_returns_false(self, category_service, mock_db_session):
        category_service.get_category_by_name_and_type = MagicMock(return_value=None)
        assert (
            category_service.is_valid_category("Unknown", TransactionType.EXPENSE)
            is False
        )


class TestAddCategory:

    @pytest.mark.parametrize(
        "category_name, transaction_type",
        [
            ("Salary", "income"),
            ("   salary   ", "income"),
        ],
    )
    def test_add_income_category_success(
        self, category_service, mock_db_session, category_name, transaction_type
    ):
        # Mock the method to return None (category doesn't exist)
        category_service.get_category_by_name_and_type = MagicMock(return_value=None)
        cat = category_service.add_category(category_name, transaction_type)

        assert cat.name == category_name.strip().capitalize()
        assert cat.type == TransactionType.INCOME
        mock_db_session.add.assert_called_once_with(cat)
        mock_db_session.commit.assert_called_once()

    def test_add_expense_category_success(self, category_service, mock_db_session):
        # Mock the method to return None (category doesn't exist)
        category_service.get_category_by_name_and_type = MagicMock(return_value=None)
        cat = category_service.add_category("Groceries", "expense")
        assert cat.name == "Groceries"
        assert cat.type == TransactionType.EXPENSE

    @pytest.mark.parametrize(
        "category_name,category_type,exception",
        [
            ("", "income", InvalidInputError),
            ("Misc", "invalid", InvalidInputError),
        ],
    )
    def test_add_category_invalid_input_raises(
        self, category_service, category_name, category_type, exception
    ):
        """Test that invalid inputs raise appropriate exceptions."""
        with pytest.raises(exception):
            category_service.add_category(category_name, category_type)

    def test_add_duplicate_category_raises(self, category_service):
        category_service.is_valid_category = MagicMock(return_value=True)
        with pytest.raises(AlreadyExistsError):
            category_service.add_category("Salary", "income")

    def test_add_category_commit_integrity_error_raises(
        self, category_service, mock_db_session
    ):
        category_service.is_valid_category = MagicMock(return_value=False)
        mock_db_session.commit.side_effect = IntegrityError("", "", "")
        with pytest.raises(AlreadyExistsError):
            category_service.add_category("Salary", "income")


class TestEditCategory:

    def test_edit_category_success(self, category_service, mock_db_session):
        old_cat = Category(name="Old", type=TransactionType.INCOME)
        old_cat.id = 1
        category_service.get_category_by_name_and_type = MagicMock(
            side_effect=[old_cat, None]
        )
        updated = category_service.edit_category("Old", "New", "income")
        assert updated.name == "New"
        mock_db_session.commit.assert_called_once()

    def test_edit_category_same_name_no_error(self, category_service, mock_db_session):
        cat = Category(name="Same", type=TransactionType.INCOME)
        cat.id = 1
        category_service.get_category_by_name_and_type = MagicMock(
            side_effect=[cat, cat]
        )
        updated = category_service.edit_category("Same", "Same", "income")
        assert updated.name == "Same"

    def test_edit_category_old_not_exist_raises(self, category_service):
        category_service.get_category_by_name_and_type = MagicMock(return_value=None)
        with pytest.raises(NotFoundError):
            category_service.edit_category("Nonexistent", "New", "income")

    def test_edit_category_new_name_exists_raises(self, category_service):
        old_cat = Category(name="Old", type=TransactionType.INCOME)
        old_cat.id = 1
        new_cat = Category(name="New", type=TransactionType.INCOME)
        new_cat.id = 2
        category_service.get_category_by_name_and_type = MagicMock(
            side_effect=[old_cat, new_cat]
        )
        with pytest.raises(AlreadyExistsError):
            category_service.edit_category("Old", "New", "income")

    def test_edit_category_empty_old_name_raises(self, category_service):
        with pytest.raises(InvalidInputError):
            category_service.edit_category("", "New", "income")

    def test_edit_category_empty_new_name_raises(self, category_service):
        with pytest.raises(InvalidInputError):
            category_service.edit_category("Old", "", "income")


class TestDeleteCategory:

    def test_delete_existing_category_success(self, category_service, mock_db_session):
        cat = Category(name="Salary", type=TransactionType.INCOME)
        cat.id = 1

        category_service.get_category_by_name_and_type = MagicMock(return_value=cat)
        mock_db_session.query().filter_by().first.return_value = None  # No transactions

        result = category_service.delete_category("Salary", "income")

        assert result is True
        mock_db_session.delete.assert_called_once_with(cat)
        mock_db_session.commit.assert_called_once()

    def test_delete_category_used_in_transaction_raises(
        self, category_service, mock_db_session
    ):
        cat = Category(name="Salary", type=TransactionType.INCOME)
        cat.id = 1
        category_service.get_category_by_name_and_type = MagicMock(return_value=cat)
        trans = Transaction()
        mock_db_session.query().filter_by().first.return_value = trans
        with pytest.raises(CategoryInUseError):
            category_service.delete_category("Salary", "income")

    def test_delete_non_existing_category_raises(
        self, category_service, mock_db_session
    ):
        category_service.get_category_by_name_and_type = MagicMock(return_value=None)
        with pytest.raises(NotFoundError):
            category_service.delete_category("Nonexistent", "income")

    def test_delete_category_empty_name_raises(self, category_service):
        with pytest.raises(InvalidInputError):
            category_service.delete_category("", "income")

    def test_delete_category_invalid_type_raises(self, category_service):
        with pytest.raises(InvalidInputError):
            category_service.delete_category("Salary", "invalid")
