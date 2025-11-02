"""Service for managing financial goals."""

import logging
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database.models import Goal
from app.exception import InvalidInputError, NotFoundError, AlreadyExistsError
from app.utility import validate_non_empty_string, validate_non_negative_amount

logger = logging.getLogger(__name__)


class GoalService:
    """Service class for handling goal operations."""

    def __init__(self, db_session: Session, account_service):
        """
        Initialize goal service.

        Args:
            db_session: SQLAlchemy database session
            account_service: AccountService instance
        """
        self.db_session = db_session
        self.account_service = account_service

    def add_goal(
        self,
        name: str,
        target_amount: str,
        deadline: date,
        account_name: str = None,
        description: str = "",
    ) -> Goal:
        """
        Create a new financial goal.

        Args:
            name: Goal name
            target_amount: Target amount in MYR
            deadline: Target date to achieve goal
            account_name: Optional account to link goal to
            description: Optional goal description

        Returns:
            Created Goal object

        Raises:
            InvalidInputError: If inputs are invalid
            NotFoundError: If account not found
            AlreadyExistsError: If goal with same name already exists
        """
        logger.info(
            f"Adding new goal: {name}, target: {target_amount} MYR, deadline: {deadline}"
        )

        # Validate name (strips, capitalizes, checks if empty)
        name = validate_non_empty_string(name, "Goal name")

        # Check for duplicate goal name
        existing_goal = self.db_session.query(Goal).filter_by(name=name).first()
        if existing_goal:
            logger.warning(f"Goal creation failed: '{name}' already exists")
            raise AlreadyExistsError(f"A goal named '{name}' already exists")

        # Validate and convert amount (must be positive, zero not allowed)
        target = validate_non_negative_amount(
            target_amount, "Target amount", allow_zero=False
        )

        # Validate deadline
        if isinstance(deadline, datetime):
            deadline_date = deadline.date()
        else:
            deadline_date = deadline

        if deadline_date <= date.today():
            logger.warning(
                f"Goal creation failed: Deadline {deadline_date} is not in the future"
            )
            raise InvalidInputError("Deadline must be in the future")

        # Get account if specified
        account_id = None
        initial_balance = Decimal("0")

        if account_name and account_name.strip():
            account = self.account_service.get_account(account_name.strip())
            if not account:
                logger.warning(
                    f"Goal creation failed: Account '{account_name}' not found"
                )
                raise NotFoundError(f"Account '{account_name}' not found")
            account_id = account.id
            initial_balance = account.balance
            logger.info(
                f"Goal linked to account '{account_name}' with balance {initial_balance}"
            )
        else:
            # No specific account - use total balance across all accounts
            accounts = self.account_service.get_all_accounts()
            initial_balance = sum(acc.balance for acc in accounts)
            logger.info(
                f"Goal using total balance across all accounts: {initial_balance}"
            )

        # Create goal
        goal = Goal(
            name=name,
            target_amount=target,
            initial_balance=initial_balance,
            deadline=datetime.combine(deadline_date, datetime.min.time()),
            account_id=account_id,
            description=description.strip() if description else "",
            is_completed=0,
            created_at=datetime.now(),
        )

        self.db_session.add(goal)
        self.db_session.commit()
        logger.info(f"Goal '{name}' created successfully with target {target} MYR")

        return goal

    def get_goal(self, goal_id: int) -> Goal | None:
        """
        Get a goal by ID.

        Args:
            goal_id: Goal ID

        Returns:
            Goal object or None if not found
        """
        goal = self.db_session.query(Goal).filter_by(id=goal_id).first()
        if goal:
            logger.info(f"Goal found with ID: {goal_id}")
        else:
            logger.info(f"Goal not found with ID: {goal_id}")
        return goal

    def get_all_goals(self) -> list[Goal]:
        """
        Get all goals, ordered by completion status and deadline.

        Returns:
            List of Goal objects
        """
        goals = (
            self.db_session.query(Goal).order_by(Goal.is_completed, Goal.deadline).all()
        )
        logger.info(f"Retrieved {len(goals)} goals")
        return goals

    def get_active_goals(self) -> list[Goal]:
        """
        Get only active (not completed) goals.

        Returns:
            List of active Goal objects
        """
        goals = (
            self.db_session.query(Goal)
            .filter(Goal.is_completed == 0)
            .order_by(Goal.deadline)
            .all()
        )
        logger.info(f"Retrieved {len(goals)} active goals")
        return goals

    def calculate_goal_progress(self, goal: Goal) -> dict:
        """
        Calculate detailed progress for a goal.

        Args:
            goal: Goal object

        Returns:
            Dictionary with progress details
        """
        logger.info(f"Calculating progress for goal: {goal.name} (ID: {goal.id})")
        # Get current amount
        if goal.account_id:
            # Linked to specific account
            accounts = self.account_service.get_all_accounts()
            account = next((a for a in accounts if a.id == goal.account_id), None)
            current_amount = account.balance if account else Decimal("0")
        else:
            # Track total balance across all accounts
            accounts = self.account_service.get_all_accounts()
            current_amount = sum(acc.balance for acc in accounts)

        # Calculate progress using initial balance from when goal was created
        initial_amount = goal.initial_balance
        progress_amount = current_amount - initial_amount
        progress_pct = (
            (progress_amount / goal.target_amount * 100)
            if goal.target_amount > 0
            else 0
        )
        remaining_amount = goal.target_amount - progress_amount

        # Time calculations
        today = date.today()
        deadline_date = (
            goal.deadline.date()
            if isinstance(goal.deadline, datetime)
            else goal.deadline
        )
        created_date = (
            goal.created_at.date()
            if isinstance(goal.created_at, datetime)
            else goal.created_at
        )

        days_total = (deadline_date - created_date).days
        days_passed = (today - created_date).days
        days_remaining = (deadline_date - today).days

        # Calculate what's needed
        if days_remaining > 0 and remaining_amount > 0:
            daily_needed = remaining_amount / days_remaining
            weekly_needed = daily_needed * 7
            monthly_needed = daily_needed * 30
        else:
            daily_needed = weekly_needed = monthly_needed = Decimal("0")

        # Calculate expected progress (linear projection)
        if days_total > 0:
            expected_progress_pct = (days_passed / days_total) * 100
            expected_amount = (goal.target_amount * days_passed) / days_total
        else:
            expected_progress_pct = 0
            expected_amount = Decimal("0")

        # On track status
        on_track = progress_amount >= expected_amount

        # Determine status
        if goal.is_completed:
            status = "completed"
        elif days_remaining < 0:
            status = "overdue"
        elif progress_pct >= 100:
            status = "achieved"
        elif on_track:
            status = "on_track"
        else:
            status = "behind"

        result = {
            # Current state
            "initial_balance": float(initial_amount),
            "current_amount": float(current_amount),
            "target_amount": float(goal.target_amount),
            "progress_amount": float(progress_amount),
            "remaining_amount": float(remaining_amount),
            "progress_pct": float(progress_pct),
            # Time tracking
            "days_total": days_total,
            "days_passed": days_passed,
            "days_remaining": days_remaining,
            # Recommendations
            "daily_needed": float(daily_needed),
            "weekly_needed": float(weekly_needed),
            "monthly_needed": float(monthly_needed),
            # Status
            "on_track": on_track,
            "status": status,
            "expected_progress_pct": float(expected_progress_pct),
            # Goal details
            "goal_name": goal.name,
            "goal_id": goal.id,
            "deadline": deadline_date.strftime("%Y-%m-%d"),
            "account_name": (
                goal.account.account_name if goal.account else "All Accounts"
            ),
            "description": goal.description or "",
        }
        logger.info(
            f"Goal '{goal.name}' progress: {float(progress_pct):.1f}%, status: {status}"
        )
        return result

    def edit_goal(
        self,
        goal_id: int,
        name: str = None,
        target_amount: str = None,
        deadline: date = None,
        description: str = None,
    ) -> Goal:
        """
        Update goal details.

        Args:
            goal_id: Goal ID
            name: New goal name
            target_amount: New target amount
            deadline: New deadline
            description: New description

        Returns:
            Updated Goal object

        Raises:
            NotFoundError: If goal not found
            InvalidInputError: If inputs are invalid
            AlreadyExistsError: If new name conflicts with existing goal
        """
        logger.info(f"Editing goal ID {goal_id}")

        goal = self.get_goal(goal_id)
        if not goal:
            logger.warning(f"Goal edit failed: ID {goal_id} not found")
            raise NotFoundError(f"Goal with ID {goal_id} not found")

        # Update fields if provided
        if name is not None:
            # Validate name (strips, capitalizes, checks if empty)
            name = validate_non_empty_string(name, "Goal name")

            # Check for duplicate (but allow keeping the same name)
            if name != goal.name:
                existing_goal = self.db_session.query(Goal).filter_by(name=name).first()
                if existing_goal:
                    logger.warning(f"Goal edit failed: Name '{name}' already exists")
                    raise AlreadyExistsError(f"A goal named '{name}' already exists")

            goal.name = name

        if target_amount is not None:
            # Validate and convert amount (must be positive, zero not allowed)
            target = validate_non_negative_amount(
                target_amount, "Target amount", allow_zero=False
            )
            goal.target_amount = target

        if deadline is not None:
            deadline_date = (
                deadline.date() if isinstance(deadline, datetime) else deadline
            )
            if deadline_date <= date.today():
                logger.warning(
                    f"Goal edit failed: Deadline {deadline_date} is not in the future"
                )
                raise InvalidInputError("Deadline must be in the future")
            goal.deadline = datetime.combine(deadline_date, datetime.min.time())

        if description is not None:
            goal.description = description.strip()

        self.db_session.commit()
        logger.info(f"Goal ID {goal_id} edited successfully")
        return goal

    def mark_goal_completed(self, goal_id: int) -> Goal:
        """
        Mark a goal as completed.

        Args:
            goal_id: Goal ID

        Returns:
            Updated Goal object

        Raises:
            NotFoundError: If goal not found
        """
        logger.info(f"Marking goal ID {goal_id} as completed")

        goal = self.get_goal(goal_id)
        if not goal:
            logger.warning(f"Goal completion failed: ID {goal_id} not found")
            raise NotFoundError(f"Goal with ID {goal_id} not found")

        goal.is_completed = 1
        self.db_session.commit()
        logger.info(f"Goal ID {goal_id} marked as completed")

        return goal

    def delete_goal(self, goal_id: int) -> bool:
        """
        Delete a goal.

        Args:
            goal_id: Goal ID

        Returns:
            True if deleted

        Raises:
            NotFoundError: If goal not found
        """
        logger.info(f"Deleting goal ID {goal_id}")

        goal = self.get_goal(goal_id)
        if not goal:
            logger.warning(f"Goal deletion failed: ID {goal_id} not found")
            raise NotFoundError(f"Goal with ID {goal_id} not found")

        self.db_session.delete(goal)
        self.db_session.commit()
        logger.info(f"Goal ID {goal_id} deleted successfully")

        return True

    def get_goals_summary(self) -> dict:
        """
        Get summary of all goals for dashboard.

        Returns:
            Dictionary with goals summary
        """
        logger.info("Getting goals summary")
        all_goals = self.get_all_goals()
        active_goals = [g for g in all_goals if not g.is_completed]

        if not active_goals:
            logger.info("No active goals found")
            return {
                "total_goals": len(all_goals),
                "active_goals": 0,
                "completed_goals": len(all_goals),
                "total_target": 0,
                "total_progress": 0,
                "average_progress_pct": 0,
                "top_goals": [],
            }

        # Calculate totals
        total_target = sum(g.target_amount for g in active_goals)

        # Get progress for all active goals
        goals_with_progress = []
        total_progress_amount = Decimal("0")

        for goal in active_goals:
            progress = self.calculate_goal_progress(goal)
            goals_with_progress.append(progress)
            total_progress_amount += Decimal(str(progress["progress_amount"]))

        # Calculate average progress
        avg_progress_pct = (
            sum(g["progress_pct"] for g in goals_with_progress)
            / len(goals_with_progress)
            if goals_with_progress
            else 0
        )

        # Get top 3 goals (closest to deadline)
        top_goals = sorted(goals_with_progress, key=lambda x: x["days_remaining"])[:3]

        result = {
            "total_goals": len(all_goals),
            "active_goals": len(active_goals),
            "completed_goals": len(all_goals) - len(active_goals),
            "total_target": float(total_target),
            "total_progress": float(total_progress_amount),
            "average_progress_pct": float(avg_progress_pct),
            "top_goals": top_goals,
        }
        logger.info(
            f"Goals summary: {len(active_goals)} active, avg progress: {avg_progress_pct:.1f}%"
        )
        return result
