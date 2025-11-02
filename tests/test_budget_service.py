from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.database.models import Budget, BudgetPeriod, TransactionType
from app.exception import AlreadyExistsError, InvalidInputError, NotFoundError
from app.services.budget_service import BudgetService


# ---- Fixtures ----


@pytest.fixture
def mock_db_session():
    return MagicMock()


@pytest.fixture
def mock_category_service():
    return MagicMock()


@pytest.fixture
def budget_service(mock_db_session, mock_category_service):
    return BudgetService(mock_db_session, mock_category_service)


# ---- get_budget ----


class TestGetBudget:

    def test_get_budget_exists(self, budget_service, mock_db_session):
        budget = Budget(
            id=1,
            category_id=1,
            limit_amount=Decimal("100"),
            period=BudgetPeriod.MONTHLY,
        )
        mock_db_session.query().filter_by().first.return_value = budget
        assert budget_service.get_budget(1) == budget

    def test_get_budget_not_exists(self, budget_service, mock_db_session):
        mock_db_session.query().filter_by().first.return_value = None
        assert budget_service.get_budget(999) is None


# ---- get_category_budget ----


class TestGetCategoryBudget:

    def test_returns_budget_for_valid_category(
        self, budget_service, mock_db_session, mock_category_service
    ):
        category = MagicMock(id=1)
        mock_category_service.get_category_by_name_and_type.return_value = category
        budget = Budget(
            category_id=1, limit_amount=Decimal("100"), period=BudgetPeriod.MONTHLY
        )
        mock_db_session.query().filter_by().first.return_value = budget
        assert budget_service.get_category_budget("Food", "expense") == budget

    def test_category_not_found_raises(self, budget_service, mock_category_service):
        mock_category_service.get_category_by_name_and_type.return_value = None
        with pytest.raises(NotFoundError):
            budget_service.get_category_budget("Unknown", "expense")

    def test_non_expense_type_raises(self, budget_service):
        with pytest.raises(InvalidInputError):
            budget_service.get_category_budget("Food", "income")

    def test_category_exists_but_no_budget_returns_none(
        self, budget_service, mock_db_session, mock_category_service
    ):
        category = MagicMock(id=1)
        mock_category_service.get_category_by_name_and_type.return_value = category
        mock_db_session.query().filter_by().first.return_value = None
        assert budget_service.get_category_budget("Food", "expense") is None


# ---- get_all_budgets ----


class TestGetAllBudgets:

    def test_returns_all_budgets(self, budget_service, mock_db_session):
        budgets = [
            Budget(
                id=1,
                category_id=1,
                limit_amount=Decimal("100"),
                period=BudgetPeriod.MONTHLY,
            ),
            Budget(
                id=2,
                category_id=2,
                limit_amount=Decimal("200"),
                period=BudgetPeriod.WEEKLY,
            ),
        ]
        mock_db_session.query().all.return_value = budgets
        assert budget_service.get_all_budgets() == budgets

    def test_returns_empty_list_if_no_budgets(self, budget_service, mock_db_session):
        mock_db_session.query().all.return_value = []
        assert budget_service.get_all_budgets() == []


# ---- add_budget ----


class TestAddBudget:

    def test_add_budget_success_sets_defaults(
        self, budget_service, mock_db_session, mock_category_service
    ):
        category = MagicMock(id=1)
        mock_category_service.get_category_by_name_and_type.return_value = category
        # Ensure no existing budget
        budget_service.get_category_budget = MagicMock(return_value=None)

        fixed_now = datetime(2024, 6, 10, 8, 0, 0)
        with patch(
            "app.services.budget_service.get_current_time", return_value=fixed_now
        ):
            budget = budget_service.add_budget(
                category_name="Food",
                transaction_type_input="expense",
                limit_amount="100",
                period="monthly",
            )

        assert budget.limit_amount == Decimal("100")
        assert budget.period == BudgetPeriod.MONTHLY
        assert budget.start_date == fixed_now
        mock_db_session.add.assert_called_once_with(budget)
        mock_db_session.commit.assert_called_once()

    def test_add_budget_with_future_start_date(
        self, budget_service, mock_db_session, mock_category_service
    ):
        category = MagicMock(id=1)
        mock_category_service.get_category_by_name_and_type.return_value = category
        budget_service.get_category_budget = MagicMock(return_value=None)

        future_date = datetime(2025, 1, 1, 0, 0, 0)
        result = budget_service.add_budget(
            category_name="Food",
            transaction_type_input="expense",
            limit_amount="100",
            period="monthly",
            start_date=future_date,
        )
        assert result.start_date == future_date
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    def test_add_budget_invalid_category_raises(
        self, budget_service, mock_category_service
    ):
        mock_category_service.get_category_by_name_and_type.return_value = None
        with pytest.raises(NotFoundError):
            budget_service.add_budget("Unknown", "expense", "100", "monthly")

    def test_add_budget_non_expense_type_raises(self, budget_service):
        with pytest.raises(InvalidInputError):
            budget_service.add_budget("Food", "income", "100", "monthly")

    def test_add_budget_negative_limit_raises(
        self, budget_service, mock_category_service
    ):
        mock_category_service.get_category_by_name_and_type.return_value = MagicMock(
            id=1
        )
        with pytest.raises(InvalidInputError):
            budget_service.add_budget("Food", "expense", "-100", "monthly")

    def test_add_budget_invalid_period_raises(
        self, budget_service, mock_category_service
    ):
        mock_category_service.get_category_by_name_and_type.return_value = MagicMock(
            id=1
        )
        with pytest.raises(InvalidInputError):
            budget_service.add_budget("Food", "expense", "100", "invalid_period")

    def test_add_budget_duplicate_budget_raises(
        self, budget_service, mock_category_service
    ):
        mock_category_service.get_category_by_name_and_type.return_value = MagicMock(
            id=1
        )
        budget_service.get_category_budget = MagicMock(return_value=MagicMock())
        with pytest.raises(AlreadyExistsError):
            budget_service.add_budget("Food", "expense", "100", "monthly")


# ---- edit_budget ----


class TestEditBudget:

    def test_edit_budget_success_updates_fields(
        self, budget_service, mock_db_session, mock_category_service
    ):
        category = MagicMock(id=1)
        mock_category_service.get_category_by_name_and_type.return_value = category
        budget = Budget(
            category_id=1, limit_amount=Decimal("100"), period=BudgetPeriod.MONTHLY
        )
        mock_db_session.query().filter_by().first.return_value = budget

        updated = budget_service.edit_budget(
            "Food", "expense", new_limit_amount="150", new_period="yearly"
        )
        assert updated.limit_amount == Decimal("150")
        assert updated.period == BudgetPeriod.YEARLY
        mock_db_session.commit.assert_called_once()

    def test_edit_budget_updates_start_date_future_ok(
        self, budget_service, mock_db_session, mock_category_service
    ):
        category = MagicMock(id=1)
        mock_category_service.get_category_by_name_and_type.return_value = category
        budget = Budget(
            category_id=1,
            limit_amount=Decimal("100"),
            period=BudgetPeriod.MONTHLY,
            start_date=datetime(2024, 6, 1),
        )
        mock_db_session.query().filter_by().first.return_value = budget

        future_date = datetime(2024, 7, 1)
        result = budget_service.edit_budget(
            "Food", "expense", new_start_date=future_date
        )
        assert result.start_date == future_date
        mock_db_session.commit.assert_called_once()

    def test_edit_budget_invalid_limit_raises(
        self, budget_service, mock_db_session, mock_category_service
    ):
        category = MagicMock(id=1)
        mock_category_service.get_category_by_name_and_type.return_value = category
        budget = Budget(
            category_id=1, limit_amount=Decimal("100"), period=BudgetPeriod.MONTHLY
        )
        mock_db_session.query().filter_by().first.return_value = budget
        with pytest.raises(InvalidInputError):
            budget_service.edit_budget("Food", "expense", new_limit_amount="-5")

    def test_edit_budget_invalid_period_raises(
        self, budget_service, mock_db_session, mock_category_service
    ):
        category = MagicMock(id=1)
        mock_category_service.get_category_by_name_and_type.return_value = category
        budget = Budget(
            category_id=1, limit_amount=Decimal("100"), period=BudgetPeriod.MONTHLY
        )
        mock_db_session.query().filter_by().first.return_value = budget
        with pytest.raises(InvalidInputError):
            budget_service.edit_budget("Food", "expense", new_period="invalid_period")

    def test_edit_budget_category_not_found_raises(
        self, budget_service, mock_category_service
    ):
        mock_category_service.get_category_by_name_and_type.return_value = None
        with pytest.raises(NotFoundError):
            budget_service.edit_budget("Food", "expense", new_limit_amount="50")

    def test_edit_budget_budget_not_found_raises(
        self, budget_service, mock_db_session, mock_category_service
    ):
        category = MagicMock(id=1)
        mock_category_service.get_category_by_name_and_type.return_value = category
        mock_db_session.query().filter_by().first.return_value = None
        with pytest.raises(NotFoundError):
            budget_service.edit_budget("Food", "expense", new_limit_amount="50")

    def test_edit_budget_non_expense_raises(self, budget_service):
        with pytest.raises(InvalidInputError):
            budget_service.edit_budget("Food", "income", new_limit_amount="50")


# ---- delete_budget ----


class TestDeleteBudget:

    def test_delete_budget_success(
        self, budget_service, mock_db_session, mock_category_service
    ):
        category = MagicMock(id=1)
        mock_category_service.get_category_by_name_and_type.return_value = category
        budget = MagicMock()
        mock_db_session.query().filter_by().first.return_value = budget
        assert budget_service.delete_budget("Food", "expense") is True
        mock_db_session.delete.assert_called_once_with(budget)
        mock_db_session.commit.assert_called_once()

    def test_delete_budget_not_found_raises(
        self, budget_service, mock_db_session, mock_category_service
    ):
        category = MagicMock(id=1)
        mock_category_service.get_category_by_name_and_type.return_value = category
        mock_db_session.query().filter_by().first.return_value = None
        with pytest.raises(NotFoundError):
            budget_service.delete_budget("Food", "expense")

    def test_delete_budget_non_expense_type_raises(self, budget_service):
        with pytest.raises(InvalidInputError):
            budget_service.delete_budget("Food", "income")

    def test_delete_budget_category_not_found_raises(
        self, budget_service, mock_category_service
    ):
        mock_category_service.get_category_by_name_and_type.return_value = None
        with pytest.raises(NotFoundError):
            budget_service.delete_budget("Food", "expense")


# ---- get_budget_status (and period logic) ----


class TestGetBudgetStatus:

    def test_weekly_status_calculation(
        self, budget_service, mock_db_session, mock_category_service
    ):
        category = MagicMock(id=1, type=TransactionType.EXPENSE, name="Food")
        mock_category_service.get_category_by_name_and_type.return_value = category
        budget = Budget(
            category_id=1,
            limit_amount=Decimal("100"),
            period=BudgetPeriod.WEEKLY,
            start_date=datetime.now() - timedelta(days=3),
        )
        mock_db_session.query().filter_by().first.return_value = budget

        t1 = MagicMock(
            amount_in_myr=Decimal("40"), datetime=datetime.now() - timedelta(days=2)
        )
        t2 = MagicMock(
            amount_in_myr=Decimal("30"), datetime=datetime.now() - timedelta(days=1)
        )
        mock_db_session.query().filter().all.return_value = [t1, t2]

        status = budget_service.get_budget_status("Food", "expense")
        assert status["spent"] == Decimal("70")
        assert status["remaining"] == Decimal("30")
        assert status["percentage"] == 70.0
        assert status["is_exceeded"] is False

    def test_monthly_previous_period_until_day_reached(
        self, budget_service, mock_db_session, mock_category_service
    ):
        category = MagicMock(id=1, type=TransactionType.EXPENSE, name="Food")
        mock_category_service.get_category_by_name_and_type.return_value = category
        start_date = datetime(2023, 1, 31, 10, 0, 0)
        budget = Budget(
            category_id=1,
            limit_amount=Decimal("100"),
            period=BudgetPeriod.MONTHLY,
            start_date=start_date,
        )
        mock_db_session.query().filter_by().first.return_value = budget
        mock_db_session.query().filter().all.return_value = []

        fixed_now = datetime(2023, 2, 15, 12, 0, 0)
        with patch(
            "app.services.budget_service.get_current_time", return_value=fixed_now
        ):
            status = budget_service.get_budget_status("Food", "expense")

        assert status["period_start"].date() == datetime(2023, 1, 31).date()
        assert status["period_end"].date() == datetime(2023, 2, 28).date()

    def test_yearly_leap_day_transition(
        self, budget_service, mock_db_session, mock_category_service
    ):
        category = MagicMock(id=1, type=TransactionType.EXPENSE, name="Bills")
        mock_category_service.get_category_by_name_and_type.return_value = category
        start_date = datetime(2024, 2, 29, 9, 0, 0)
        budget = Budget(
            category_id=1,
            limit_amount=Decimal("500"),
            period=BudgetPeriod.YEARLY,
            start_date=start_date,
        )
        mock_db_session.query().filter_by().first.return_value = budget
        mock_db_session.query().filter().all.return_value = []

        fixed_now = datetime(2025, 3, 1, 8, 0, 0)
        with patch(
            "app.services.budget_service.get_current_time", return_value=fixed_now
        ):
            status = budget_service.get_budget_status("Bills", "expense")

        assert status["period_start"].date() == datetime(2025, 2, 28).date()
        assert status["period_end"].date() == datetime(2026, 2, 28).date()

    def test_future_start_date_returns_first_period(
        self, budget_service, mock_db_session, mock_category_service
    ):
        category = MagicMock(id=1, type=TransactionType.EXPENSE, name="Gym")
        mock_category_service.get_category_by_name_and_type.return_value = category
        start_date = datetime(2025, 12, 1, 0, 0, 0)
        budget = Budget(
            category_id=1,
            limit_amount=Decimal("300"),
            period=BudgetPeriod.WEEKLY,
            start_date=start_date,
        )
        mock_db_session.query().filter_by().first.return_value = budget
        mock_db_session.query().filter().all.return_value = []

        fixed_now = datetime(2025, 11, 1, 0, 0, 0)
        with patch(
            "app.services.budget_service.get_current_time", return_value=fixed_now
        ):
            status = budget_service.get_budget_status("Gym", "expense")

        assert status["period_start"] == start_date
        assert status["period_end"] == start_date + timedelta(weeks=1)


# ---- get_all_budget_statuses ----


class TestAllBudgetStatuses:

    def test_skips_income_and_collects_expense(self, budget_service):
        expense_category = MagicMock()
        expense_category.type = TransactionType.EXPENSE
        expense_category.name = "Food"
        income_category = MagicMock()
        income_category.type = TransactionType.INCOME
        income_category.name = "Salary"

        b_expense = MagicMock(category=expense_category)
        b_income = MagicMock(category=income_category)
        budget_service.get_all_budgets = MagicMock(return_value=[b_expense, b_income])

        ok_status = {"percentage": 42, "budget": b_expense}
        budget_service.get_budget_status = MagicMock(return_value=ok_status)

        statuses = budget_service.get_all_budget_statuses()
        assert statuses == [ok_status]
        budget_service.get_budget_status.assert_called_once_with("Food", "expense")

    def test_errors_do_not_break_collection(self, budget_service):
        expense_category = MagicMock()
        expense_category.type = TransactionType.EXPENSE
        expense_category.name = "A"
        expense_category2 = MagicMock()
        expense_category2.type = TransactionType.EXPENSE
        expense_category2.name = "B"
        b1 = MagicMock(category=expense_category)
        b2 = MagicMock(category=expense_category2)
        budget_service.get_all_budgets = MagicMock(return_value=[b1, b2])

        def side_effect(name, ttype):
            if name == "A":
                raise NotFoundError()
            return {"percentage": 10, "budget": b2}

        budget_service.get_budget_status = MagicMock(side_effect=side_effect)
        statuses = budget_service.get_all_budget_statuses()
        assert len(statuses) == 1
        assert statuses[0]["budget"] == b2


# ---- check_budget_warning ----


class TestCheckBudgetWarning:

    def test_no_budget_returns_defaults(self, budget_service):
        budget_service.get_budget_status = MagicMock(side_effect=NotFoundError)
        result = budget_service.check_budget_warning("Any", "expense", Decimal("10"))
        assert result["has_budget"] is False
        assert result["warning_level"] == "none"

    def test_warning_levels_none_caution_warning_exceeded(self, budget_service):
        # Base status: limit 100, current 0
        base = {"limit": Decimal("100"), "spent": Decimal("0"), "percentage": 0.0}
        budget_service.get_budget_status = MagicMock(return_value=base)

        r1 = budget_service.check_budget_warning("Food", "expense", Decimal("10"))
        assert r1["warning_level"] == "none"

        budget_service.get_budget_status.return_value = {
            "limit": Decimal("100"),
            "spent": Decimal("79.9"),
            "percentage": 79.9,
        }
        r2 = budget_service.check_budget_warning("Food", "expense", Decimal("0.2"))
        assert r2["warning_level"] == "caution"

        budget_service.get_budget_status.return_value = {
            "limit": Decimal("100"),
            "spent": Decimal("89.9"),
            "percentage": 89.9,
        }
        r3 = budget_service.check_budget_warning("Food", "expense", Decimal("0.2"))
        assert r3["warning_level"] == "warning"

        budget_service.get_budget_status.return_value = {
            "limit": Decimal("100"),
            "spent": Decimal("100"),
            "percentage": 100.0,
        }
        r4 = budget_service.check_budget_warning("Food", "expense", Decimal("1"))
        assert r4["warning_level"] == "exceeded"
        assert "BUDGET EXCEEDED" in r4["message"].upper()


# ---- get_budgets_at_risk ----


class TestGetBudgetsAtRisk:

    def test_default_threshold_returns_above_80_sorted(self, budget_service):
        status1 = {"percentage": 85, "budget": MagicMock()}
        status2 = {"percentage": 50, "budget": MagicMock()}
        status3 = {"percentage": 95, "budget": MagicMock()}
        budget_service.get_all_budget_statuses = MagicMock(
            return_value=[status1, status2, status3]
        )
        at_risk = budget_service.get_budgets_at_risk()
        assert [s["percentage"] for s in at_risk] == [95, 85]

    def test_custom_threshold(self, budget_service):
        status1 = {"percentage": 70}
        status2 = {"percentage": 60}
        budget_service.get_all_budget_statuses = MagicMock(
            return_value=[status1, status2]
        )
        assert budget_service.get_budgets_at_risk(threshold=65.0) == [status1]
