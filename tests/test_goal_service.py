# tests/test_goal_service.py

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.database.models import Goal, Transaction, TransactionType
from app.exception import AlreadyExistsError, InvalidInputError, NotFoundError
from app.services.goal_service import GoalService


@pytest.fixture
def mock_db_session():
    return MagicMock()


@pytest.fixture
def mock_account_service():
    return MagicMock()


@pytest.fixture
def goal_service(mock_db_session, mock_account_service):
    return GoalService(mock_db_session, mock_account_service)


class TestAddGoal:

    def test_add_goal_with_linked_account_success(
        self, goal_service, mock_db_session, mock_account_service
    ):
        # No duplicate name
        mock_db_session.query().filter_by().first.return_value = None

        # Found linked account with current balance
        account = MagicMock(id=1, balance=Decimal("1000.00"))
        mock_account_service.get_account.return_value = account

        future_deadline = date.today() + timedelta(days=30)
        g = goal_service.add_goal(
            name="new goal",
            target_amount="500",
            deadline=future_deadline,
            account_name="Main",
            description="  save more  ",
        )

        assert isinstance(g, Goal)
        assert g.name == "New goal"  # capitalized by validator
        assert g.target_amount == Decimal("500.00")
        assert g.initial_balance == Decimal(
            "0"
        )  # Always starts at 0 with net income tracking
        assert g.account_id == 1
        assert g.is_completed == 0
        assert g.description == "save more"
        mock_db_session.add.assert_called_once_with(g)
        mock_db_session.commit.assert_called_once()

    def test_add_goal_without_account_uses_zero_initial_balance(
        self, goal_service, mock_db_session, mock_account_service
    ):
        # No duplicate
        mock_db_session.query().filter_by().first.return_value = None

        # Two accounts with balances (not used for initial_balance anymore)
        acc1 = MagicMock(balance=Decimal("100.00"))
        acc2 = MagicMock(balance=Decimal("250.50"))
        mock_account_service.get_all_accounts.return_value = [acc1, acc2]

        future_deadline = date.today() + timedelta(days=10)
        g = goal_service.add_goal(
            name="Emergency",
            target_amount="200",
            deadline=future_deadline,
        )

        assert g.initial_balance == Decimal(
            "0"
        )  # Always starts at 0 with net income tracking
        assert g.account_id is None

    def test_add_goal_duplicate_name_raises(self, goal_service, mock_db_session):
        mock_db_session.query().filter_by().first.return_value = MagicMock()
        with pytest.raises(AlreadyExistsError):
            goal_service.add_goal("Test", "100", date.today() + timedelta(days=1))

    def test_add_goal_invalid_amount_raises(self, goal_service, mock_db_session):
        mock_db_session.query().filter_by().first.return_value = None
        with pytest.raises(InvalidInputError):
            goal_service.add_goal("Test", "-1", date.today() + timedelta(days=1))

    def test_add_goal_deadline_today_raises(self, goal_service, mock_db_session):
        mock_db_session.query().filter_by().first.return_value = None
        with pytest.raises(InvalidInputError):
            goal_service.add_goal("Test", "100", date.today())

    def test_add_goal_linked_account_not_found_raises(
        self, goal_service, mock_db_session, mock_account_service
    ):
        mock_db_session.query().filter_by().first.return_value = None
        mock_account_service.get_account.return_value = None
        with pytest.raises(NotFoundError):
            goal_service.add_goal(
                "Test", "100", date.today() + timedelta(days=1), account_name="X"
            )


class TestGetGoals:

    def test_get_goal_by_id(self, goal_service, mock_db_session):
        goal = Goal(
            id=1,
            name="A",
            target_amount=Decimal("10"),
            initial_balance=Decimal("0"),
            deadline=datetime.now(),
            created_at=datetime.now(),
        )
        mock_db_session.query().filter_by().first.return_value = goal
        assert goal_service.get_goal(1) == goal

    def test_get_goal_by_id_not_found(self, goal_service, mock_db_session):
        mock_db_session.query().filter_by().first.return_value = None
        assert goal_service.get_goal(999) is None

    def test_get_all_goals_order(self, goal_service, mock_db_session):
        g1 = Goal(
            id=1,
            name="A",
            target_amount=Decimal("10"),
            initial_balance=Decimal("0"),
            deadline=datetime.now(),
            created_at=datetime.now(),
            is_completed=0,
        )
        g2 = Goal(
            id=2,
            name="B",
            target_amount=Decimal("20"),
            initial_balance=Decimal("0"),
            deadline=datetime.now(),
            created_at=datetime.now(),
            is_completed=1,
        )
        mock_db_session.query().order_by().all.return_value = [g1, g2]
        assert goal_service.get_all_goals() == [g1, g2]

    def test_get_active_goals(self, goal_service, mock_db_session):
        g1 = Goal(
            id=1,
            name="A",
            target_amount=Decimal("10"),
            initial_balance=Decimal("0"),
            deadline=datetime.now(),
            created_at=datetime.now(),
            is_completed=0,
        )
        mock_db_session.query().filter().order_by().all.return_value = [g1]
        assert goal_service.get_active_goals() == [g1]


class TestCalculateGoalProgress:

    def test_progress_for_all_accounts_on_track(
        self, goal_service, mock_db_session, mock_account_service
    ):
        # Goal without specific account - uses net income tracking
        today = date.today()
        goal = Goal(
            id=3,
            name="Save",
            target_amount=Decimal("500"),
            initial_balance=Decimal("0"),  # Always 0 with net income tracking
            deadline=datetime.combine(today + timedelta(days=20), datetime.min.time()),
            created_at=datetime.combine(
                today - timedelta(days=10), datetime.min.time()
            ),
        )

        # Mock transactions: Income = 400, Expenses = 100, Net = 300
        income_txn = MagicMock(amount_in_myr=Decimal("400"))
        expense_txn = MagicMock(amount_in_myr=Decimal("100"))

        # Mock query chain for transactions
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        # First call returns income transactions, second call returns expense transactions
        mock_query.all.side_effect = [[income_txn], [expense_txn]]

        result = goal_service.calculate_goal_progress(goal)

        assert result["progress_amount"] == pytest.approx(300.0)  # 400 - 100
        assert result["progress_pct"] == pytest.approx(60.0)
        assert result["days_total"] == 30
        assert result["days_passed"] == 10
        assert result["days_remaining"] == 20
        assert result["daily_needed"] == pytest.approx(10.0)
        assert result["weekly_needed"] == pytest.approx(70.0)
        assert result["monthly_needed"] == pytest.approx(300.0)
        assert result["on_track"] is True
        assert result["status"] == "on_track"
        assert result["account_name"] == "All Accounts"

    def test_progress_for_linked_account_achieved(
        self, goal_service, mock_db_session, mock_account_service
    ):
        today = date.today()
        goal = Goal(
            id=4,
            name="Phone",
            target_amount=Decimal("200"),
            initial_balance=Decimal("0"),  # Always 0 with net income tracking
            deadline=datetime.combine(today + timedelta(days=5), datetime.min.time()),
            created_at=datetime.combine(today - timedelta(days=5), datetime.min.time()),
            account_id=1,
        )

        # Mock account
        acc = MagicMock(id=1, name="Savings", balance=Decimal("250"))
        mock_account_service.get_account.return_value = acc

        # Mock transactions: Income = 300, Expenses = 50, Net = 250 (125% of 200 target)
        income_txn = MagicMock(amount_in_myr=Decimal("300"))
        expense_txn = MagicMock(amount_in_myr=Decimal("50"))

        # Mock query chain for transactions
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        # First call returns income transactions, second call returns expense transactions
        mock_query.all.side_effect = [[income_txn], [expense_txn]]

        result = goal_service.calculate_goal_progress(goal)
        assert result["progress_amount"] == pytest.approx(250.0)  # 300 - 50
        assert result["progress_pct"] == pytest.approx(125.0)
        assert result["status"] in {"on_track", "achieved"}


class TestEditGoal:

    def test_edit_goal_success(self, goal_service, mock_db_session):
        existing = Goal(
            id=10,
            name="Old",
            target_amount=Decimal("100"),
            initial_balance=Decimal("0"),
            deadline=datetime.now() + timedelta(days=10),
            created_at=datetime.now(),
            description="desc",
        )
        # get_goal -> returns existing
        goal_service.get_goal = MagicMock(return_value=existing)
        # duplicate name check -> none
        mock_db_session.query().filter_by().first.return_value = None

        new_deadline = date.today() + timedelta(days=30)
        updated = goal_service.edit_goal(
            goal_id=10,
            name="new name",
            target_amount="150.50",
            deadline=new_deadline,
            description="  updated  ",
        )

        assert updated.name == "New name"
        assert updated.target_amount == Decimal("150.50")
        assert updated.deadline.date() == new_deadline
        assert updated.description == "updated"
        mock_db_session.commit.assert_called_once()

    def test_edit_goal_duplicate_new_name_raises(self, goal_service, mock_db_session):
        existing = Goal(
            id=11,
            name="Keep",
            target_amount=Decimal("50"),
            initial_balance=Decimal("0"),
            deadline=datetime.now(),
            created_at=datetime.now(),
        )
        goal_service.get_goal = MagicMock(return_value=existing)
        # Duplicate exists
        mock_db_session.query().filter_by().first.return_value = MagicMock()
        with pytest.raises(AlreadyExistsError):
            goal_service.edit_goal(11, name="Other")

    def test_edit_goal_invalid_deadline_raises(self, goal_service):
        existing = Goal(
            id=12,
            name="X",
            target_amount=Decimal("50"),
            initial_balance=Decimal("0"),
            deadline=datetime.now(),
            created_at=datetime.now(),
        )
        goal_service.get_goal = MagicMock(return_value=existing)
        with pytest.raises(InvalidInputError):
            goal_service.edit_goal(12, deadline=date.today())

    def test_edit_goal_not_found_raises(self, goal_service):
        goal_service.get_goal = MagicMock(return_value=None)
        with pytest.raises(NotFoundError):
            goal_service.edit_goal(999, name="any")


class TestMarkDeleteGoal:

    def test_mark_goal_completed(self, goal_service, mock_db_session):
        existing = Goal(
            id=20,
            name="G",
            target_amount=Decimal("10"),
            initial_balance=Decimal("0"),
            deadline=datetime.now(),
            created_at=datetime.now(),
            is_completed=0,
        )
        goal_service.get_goal = MagicMock(return_value=existing)
        result = goal_service.mark_goal_completed(20)
        assert result.is_completed == 1
        mock_db_session.commit.assert_called_once()

    def test_mark_goal_completed_not_found(self, goal_service):
        goal_service.get_goal = MagicMock(return_value=None)
        with pytest.raises(NotFoundError):
            goal_service.mark_goal_completed(1)

    def test_delete_goal_success(self, goal_service, mock_db_session):
        existing = Goal(
            id=21,
            name="G",
            target_amount=Decimal("10"),
            initial_balance=Decimal("0"),
            deadline=datetime.now(),
            created_at=datetime.now(),
        )
        goal_service.get_goal = MagicMock(return_value=existing)
        assert goal_service.delete_goal(21) is True
        mock_db_session.delete.assert_called_once_with(existing)
        mock_db_session.commit.assert_called_once()

    def test_delete_goal_not_found(self, goal_service):
        goal_service.get_goal = MagicMock(return_value=None)
        with pytest.raises(NotFoundError):
            goal_service.delete_goal(999)


class TestGoalsSummary:

    def test_summary_no_active_goals(self, goal_service):
        g1 = Goal(
            id=1,
            name="A",
            target_amount=Decimal("100"),
            initial_balance=Decimal("0"),
            deadline=datetime.now(),
            created_at=datetime.now(),
            is_completed=1,
        )
        goal_service.get_all_goals = MagicMock(return_value=[g1])
        s = goal_service.get_goals_summary()
        assert s["total_goals"] == 1
        assert s["active_goals"] == 0
        assert s["completed_goals"] == 1
        assert s["total_target"] == 0
        assert s["top_goals"] == []

    def test_summary_with_active_goals(self, goal_service):
        g1 = Goal(
            id=1,
            name="A",
            target_amount=Decimal("100"),
            initial_balance=Decimal("0"),
            deadline=datetime.now(),
            created_at=datetime.now(),
            is_completed=0,
        )
        g2 = Goal(
            id=2,
            name="B",
            target_amount=Decimal("200"),
            initial_balance=Decimal("0"),
            deadline=datetime.now(),
            created_at=datetime.now(),
            is_completed=0,
        )
        goal_service.get_all_goals = MagicMock(return_value=[g1, g2])

        # Mock progress results
        p1 = {"progress_amount": 30.0, "progress_pct": 30.0, "days_remaining": 10}
        p2 = {"progress_amount": 60.0, "progress_pct": 60.0, "days_remaining": 5}
        goal_service.calculate_goal_progress = MagicMock(side_effect=[p1, p2])

        s = goal_service.get_goals_summary()
        assert s["total_goals"] == 2
        assert s["active_goals"] == 2
        assert s["completed_goals"] == 0
        assert s["total_target"] == 300.0
        assert s["total_progress"] == 90.0
        assert s["average_progress_pct"] == pytest.approx(45.0)
        assert s["top_goals"][0]["days_remaining"] == 5
