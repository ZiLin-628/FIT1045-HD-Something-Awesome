"""Service for managing category budgets."""

import calendar
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database.models import Budget, BudgetPeriod, Transaction, TransactionType
from app.exception import AlreadyExistsError, InvalidInputError, NotFoundError
from app.utility import (
    validate_non_empty_string,
    validate_non_negative_amount,
    validate_transaction_type,
    validate_budget_period,
    get_current_time,
)

logger = logging.getLogger(__name__)


class BudgetService:
    """Service class for handling budget management."""

    def __init__(self, db_session: Session, category_service) -> None:
        """
        Initialize the BudgetService.

        Args:
            db_session (Session): session instance.
            category_service (CategoryService): Service to handle category-related operations.
        """
        self.db_session = db_session
        self.category_service = category_service

    def get_budget(self, budget_id: int) -> Budget | None:
        """
        Get budget by ID.

        Args:
            budget_id (int): Id of th budget

        Returns:
            Budget | None: The budget object
        """
        budget = self.db_session.query(Budget).filter_by(id=budget_id).first()
        if budget:
            logger.info(f"Budget found with ID: {budget_id}")
        else:
            logger.info(f"Budget not found with ID: {budget_id}")
        return budget

    def get_category_budget(
        self, category_name: str, transaction_type_input: str
    ) -> Budget | None:
        """
        Get active budget for an expense category. Returns None if not found.

        Args:
            category_name (str): Name of the category.
            transaction_type_input (str): Transaction type.

        Returns:
            Budget | None: Budget object if found, else None.

        Raises:
            InvalidInputError: If transaction_type is not 'expense'.
            NotFoundError: If category does not exist.
        """
        logger.info(
            f"Getting budget for category: {category_name}, type: {transaction_type_input}"
        )

        # Validate transaction type
        transaction_type = validate_transaction_type(transaction_type_input)

        # Only allow expense category
        if transaction_type != TransactionType.EXPENSE:
            logger.warning(
                f"Budget requested for non-expense type: {transaction_type.value}"
            )
            raise InvalidInputError(
                "Budgets are only available for expense categories."
            )

        # Validate if category exist
        category = self.category_service.get_category_by_name_and_type(
            category_name, transaction_type
        )

        if not category:
            logger.warning(
                f"Category not found: {category_name} ({transaction_type.value})"
            )
            raise NotFoundError(
                f"Category '{category_name}' not found in {transaction_type.value} categories."
            )

        # Get the budget based on the category
        budget = (
            self.db_session.query(Budget).filter_by(category_id=category.id).first()
        )
        if budget:
            logger.info(
                f"Budget found for category '{category_name}': limit={budget.limit_amount}, period={budget.period}"
            )
        else:
            logger.info(f"No budget found for category: {category_name}")
        return budget

    def get_all_budgets(self) -> list[Budget]:
        """
        Retrieve all budgets.

        Returns:
            list[Budget]: List of all Budget objects.
        """
        budgets = self.db_session.query(Budget).all()
        logger.info(f"Retrieved {len(budgets)} budgets")
        return budgets

    def add_budget(
        self,
        category_name: str,
        transaction_type_input: str,
        limit_amount: str,
        period: str,
        start_date: datetime = None,
    ) -> Budget:
        """
        Create a new budget for a category.

        Args:
            category_name (str): Name of the category.
            transaction_type_input (str): transaction type.
            limit_amount (str): Budget limit (in MYR).
            period (str): Budget period enum.
            start_date (datetime, optional): Start date of the budget. Defaults to current time.

        Returns:
            Budget: Newly created Budget object.

        Raises:
            InvalidInputError: If transaction_type or period is invalid.
            NotFoundError: If the category does not exist.
            AlreadyExistsError: If a budget for the category already exists.
        """
        logger.info(
            f"Adding budget for category '{category_name}': {limit_amount} MYR ({period})"
        )

        # Validate inputs
        category_name = validate_non_empty_string(category_name, "Category name")
        transaction_type = validate_transaction_type(transaction_type_input)

        # Only allow expense category
        if transaction_type != TransactionType.EXPENSE:
            logger.warning(
                f"Budget creation failed: Cannot create budget for {transaction_type.value} category"
            )
            raise InvalidInputError(
                "Budgets are only available for expense categories."
            )

        # Convert limit amount to decimal
        limit_decimal = validate_non_negative_amount(
            limit_amount, "Budget limit", allow_zero=False
        )

        # Validate period
        budget_period = validate_budget_period(period)

        # Check if category exists
        category = self.category_service.get_category_by_name_and_type(
            category_name, transaction_type
        )
        if not category:
            logger.warning(
                f"Budget creation failed: Category '{category_name}' not found"
            )
            raise NotFoundError(
                f"Category '{category_name}' not found for {transaction_type.value}."
            )

        # Check if budget already exists for this category
        existing = self.get_category_budget(category_name, transaction_type.value)
        if existing:
            logger.warning(
                f"Budget creation failed: Budget already exists for '{category_name}'"
            )
            raise AlreadyExistsError(
                f"Budget already exists for category '{category_name}'. "
                f"Edit or delete it first."
            )

        # Validate and set start date
        if start_date is None:
            start_date = get_current_time()

        # Create budget
        new_budget = Budget(
            category_id=category.id,
            limit_amount=limit_decimal,
            period=budget_period,
            start_date=start_date,
        )

        # Add to database and save
        self.db_session.add(new_budget)

        try:
            self.db_session.commit()
            logger.info(f"Budget created successfully for category '{category_name}'")
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to create budget for '{category_name}': {e}")
            raise

        return new_budget

    def edit_budget(
        self,
        category_name: str,
        transaction_type_input: str,
        new_limit_amount: str = None,
        new_period: str = None,
        new_start_date: datetime = None,
    ) -> Budget:
        """
        Edit an existing budget.

        Args:
            category_name (str): Name of the category.
            transaction_type_input (str): Transaction type'.
            new_limit_amount (str, optional): New budget limit.
            new_period (str, optional): Budget period enum.
            new_start_date (datetime, optional): New start date.

        Returns:
            Budget: Updated Budget object.

        Raises:
            InvalidInputError: If transaction_type or period is invalid.
            NotFoundError: If category or budget does not exist.
        """
        logger.info(f"Editing budget for category '{category_name}'")

        # Validate inputs
        category_name = validate_non_empty_string(category_name, "Category name")
        transaction_type = validate_transaction_type(transaction_type_input)

        # Enforce expense-only budgets
        if transaction_type != TransactionType.EXPENSE:
            logger.warning(
                f"Budget edit failed: Cannot edit budget for {transaction_type.value} category"
            )
            raise InvalidInputError(
                "Budgets are only available for expense categories."
            )

        # Get category
        category = self.category_service.get_category_by_name_and_type(
            category_name, transaction_type
        )
        if not category:
            logger.warning(f"Budget edit failed: Category '{category_name}' not found")
            raise NotFoundError(
                f"Category '{category_name}' not found for {transaction_type.value}."
            )

        # Get budget
        budget = self.get_category_budget(category_name, transaction_type.value)
        if not budget:
            logger.warning(f"Budget edit failed: No budget found for '{category_name}'")
            raise NotFoundError(f"No budget found for category '{category_name}'.")

        # Update fields
        if new_limit_amount is not None and new_limit_amount.strip():
            budget.limit_amount = validate_non_negative_amount(
                new_limit_amount, "Budget limit", allow_zero=False
            )

        if new_period is not None and new_period.strip():
            budget.period = validate_budget_period(new_period)

        if new_start_date is not None:
            # Future start dates are now allowed for planning purposes
            budget.start_date = new_start_date

        try:
            self.db_session.commit()
            logger.info(f"Budget for category '{category_name}' edited successfully")
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to edit budget for '{category_name}': {e}")
            raise

        return budget

    def delete_budget(self, category_name: str, transaction_type_input: str) -> bool:
        """
        Delete a budget.

        Args:
            category_name (str): Name of the category.
            transaction_type_input (str): transaction type.

        Returns:
            bool: True if deletion succeeds.

        Raises:
            InvalidInputError: If transaction_type is invalid.
            NotFoundError: If category or budget does not exist.
        """
        logger.info(f"Deleting budget for category '{category_name}'")

        # Validate inputs
        category_name = validate_non_empty_string(category_name, "Category name")
        transaction_type = validate_transaction_type(transaction_type_input)

        # Enforce expense-only budgets
        if transaction_type != TransactionType.EXPENSE:
            logger.warning(
                f"Budget deletion failed: Cannot delete budget for {transaction_type.value} category"
            )
            raise InvalidInputError(
                "Budgets are only available for expense categories."
            )

        # Get category
        category = self.category_service.get_category_by_name_and_type(
            category_name, transaction_type
        )
        if not category:
            logger.warning(
                f"Budget deletion failed: Category '{category_name}' not found"
            )
            raise NotFoundError(
                f"Category '{category_name}' not found for {transaction_type.value}."
            )

        # Get budget
        budget = self.get_category_budget(category_name, transaction_type.value)
        if not budget:
            logger.warning(
                f"Budget deletion failed: No budget found for '{category_name}'"
            )
            raise NotFoundError(f"No budget found for category '{category_name}'.")

        self.db_session.delete(budget)

        try:
            self.db_session.commit()
            logger.info(f"Budget for category '{category_name}' deleted successfully")
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to delete budget for '{category_name}': {e}")
            raise

        return True

    def get_budget_status(
        self, category_name: str, transaction_type_input: str
    ) -> dict:
        """
        Get budget status including spent amount, remaining, and period information.

        Args:
            category_name (str): Name of the category.
            transaction_type_input (str): transaction type.

        Returns:
            dict[str, object]: Dictionary with keys:
                - "budget" (Budget): Budget object
                - "limit" (Decimal): Budget limit
                - "spent" (Decimal): Amount spent in current period
                - "remaining" (Decimal): Remaining budget
                - "percentage" (float): Percentage of budget used
                - "period_start" (datetime): Start of current period
                - "period_end" (datetime): End of current period
                - "is_exceeded" (bool): True if spent > limit

        Raises:
            InvalidInputError: If transaction_type is not "expense".
            NotFoundError: If category or budget is not found.
        """
        logger.info(f"Getting budget status for category: {category_name}")

        # Validate transaction type
        transaction_type = validate_transaction_type(transaction_type_input)

        # only allow expense category
        if transaction_type != TransactionType.EXPENSE:
            raise InvalidInputError(
                "Budgets are only available for expense categories."
            )

        # Get category
        category = self.category_service.get_category_by_name_and_type(
            category_name, transaction_type
        )
        if not category:
            raise NotFoundError(
                f"Category '{category_name}' not found for {transaction_type.value}."
            )

        # Get budget
        budget = self.get_category_budget(category_name, transaction_type.value)
        if not budget:
            raise NotFoundError(f"No budget found for category '{category_name}'.")

        # Calculate current period
        period_start, period_end = self._get_current_period(budget)

        # Calculate spent amount (sum of transactions in current period)
        spent = self._calculate_spent(category.id, period_start, period_end)

        # Calculate remaining
        remaining = budget.limit_amount - spent

        # Calculate percentage
        percentage = (
            float((spent / budget.limit_amount) * 100) if budget.limit_amount > 0 else 0
        )

        result = {
            "budget": budget,
            "limit": budget.limit_amount,
            "spent": spent,
            "remaining": remaining,
            "percentage": percentage,
            "period_start": period_start,
            "period_end": period_end,
            "is_exceeded": spent > budget.limit_amount,
        }
        logger.info(
            f"Budget status for '{category_name}': {percentage:.1f}% used ({spent}/{budget.limit_amount})"
        )
        return result

    def _get_current_period(self, budget: Budget) -> tuple[datetime, datetime]:
        """
        Calculate the current budget period's start and end dates.

        Args:
            budget (Budget): Budget object.

        Returns:
            tuple[datetime, datetime]: Tuple containing (period_start, period_end).
        """

        now = get_current_time()
        start = budget.start_date

        # If budget hasn't started yet, return the first period
        if now < start:

            if budget.period == BudgetPeriod.WEEKLY:
                return start, start + timedelta(weeks=1)

            elif budget.period == BudgetPeriod.MONTHLY:
                # Calculate next month
                if start.month == 12:
                    next_year, next_month = start.year + 1, 1
                else:
                    next_year, next_month = start.year, start.month + 1

                max_day_in_next = calendar.monthrange(next_year, next_month)[1]
                safe_day_next = min(start.day, max_day_in_next)
                period_end = start.replace(
                    year=next_year, month=next_month, day=safe_day_next
                )

                return start, period_end

            elif budget.period == BudgetPeriod.YEARLY:
                end_year = start.year + 1

                if (
                    start.month == 2
                    and start.day == 29
                    and not calendar.isleap(end_year)
                ):
                    period_end = start.replace(year=end_year, day=28)

                else:
                    period_end = start.replace(year=end_year)

                return start, period_end

        # Find the current period
        if budget.period == BudgetPeriod.WEEKLY:
            days_diff = (now - start).days
            periods_passed = days_diff // 7
            period_start = start + timedelta(weeks=periods_passed)
            period_end = period_start + timedelta(weeks=1)

        elif budget.period == BudgetPeriod.MONTHLY:
            # Calculate months difference
            months_diff = (now.year - start.year) * 12 + (now.month - start.month)

            # If we haven't reached the day of the month yet, we're still in the previous period
            if now.day < start.day:
                months_diff -= 1

            # Calculate period start
            year = start.year + (start.month + months_diff - 1) // 12
            month = (start.month + months_diff - 1) % 12 + 1

            # Handle months with fewer days (e.g., Jan 31 -> Feb 28)
            max_day_in_month = calendar.monthrange(year, month)[1]
            safe_day = min(start.day, max_day_in_month)
            period_start = start.replace(year=year, month=month, day=safe_day)

            # Calculate period end (next month)
            if month == 12:
                next_year, next_month = year + 1, 1
            else:
                next_year, next_month = year, month + 1

            # Handle period end date overflow
            max_day_in_next = calendar.monthrange(next_year, next_month)[1]
            safe_day_next = min(start.day, max_day_in_next)
            period_end = start.replace(
                year=next_year, month=next_month, day=safe_day_next
            )

        elif budget.period == BudgetPeriod.YEARLY:
            years_diff = now.year - start.year
            target_year = start.year + years_diff

            # Handle Feb 29 in leap year -> non-leap year transition
            if start.month == 2 and start.day == 29:
                if not calendar.isleap(target_year):
                    period_start = start.replace(year=target_year, day=28)
                else:
                    period_start = start.replace(year=target_year)
            else:
                period_start = start.replace(year=target_year)

            # Calculate period end with same leap year handling
            end_year = period_start.year + 1
            if start.month == 2 and start.day == 29:
                if not calendar.isleap(end_year):
                    period_end = start.replace(year=end_year, day=28)
                else:
                    period_end = start.replace(year=end_year)
            else:
                period_end = period_start.replace(year=end_year)

        return period_start, period_end

    def _calculate_spent(
        self, category_id: int, period_start: datetime, period_end: datetime
    ) -> Decimal:
        """Calculate total spent in MYR for category in given period."""

        transactions = (
            self.db_session.query(Transaction)
            .filter(
                Transaction.category_id == category_id,
                Transaction.datetime >= period_start,
                Transaction.datetime < period_end,
            )
            .all()
        )

        total = Decimal("0.00")
        for t in transactions:
            total += t.amount_in_myr

        return total

    def get_all_budget_statuses(self) -> list[dict]:
        """
        Get status for all budgets (expense categories only).

        Note: Only returns expense category budgets since income budgets are not supported.
        """
        logger.info("Getting status for all budgets")
        budgets = self.get_all_budgets()
        statuses = []

        for budget in budgets:
            category = budget.category
            # Skip non-expense budgets (if any exist in database)
            if category.type != TransactionType.EXPENSE:
                continue

            try:
                status = self.get_budget_status(category.name, category.type.value)
                statuses.append(status)
            except Exception:
                # Skip if error
                continue

        logger.info(f"Retrieved {len(statuses)} budget statuses")
        return statuses

    def check_budget_warning(
        self,
        category_name: str,
        transaction_type_input: str,
        additional_amount: Decimal,
    ) -> dict:
        """
        Check if adding a transaction would trigger budget warnings.

        Args:
            category_name: Name of the category
            transaction_type_input: "expense"
            additional_amount: Amount to be added (in MYR)

        Returns:
            {
                "has_budget": bool,
                "warning_level": str ("none", "caution", "warning", "exceeded"),
                "current_percentage": float,
                "new_percentage": float,
                "message": str,
                "limit": Decimal,
                "current_spent": Decimal,
                "new_spent": Decimal,
                "remaining_after": Decimal
            }
        """
        logger.info(
            f"Checking budget warning for category '{category_name}', amount: {additional_amount}"
        )
        try:
            # Try to get budget status
            status = self.get_budget_status(category_name, transaction_type_input)

            current_spent = status["spent"]
            limit = status["limit"]
            current_percentage = status["percentage"]

            # Calculate new values
            new_spent = current_spent + additional_amount
            new_percentage = float((new_spent / limit) * 100) if limit > 0 else 0
            remaining_after = limit - new_spent

            # Determine warning level
            if new_percentage >= 100:
                warning_level = "exceeded"
                message = f"⛔ BUDGET EXCEEDED! This transaction will put you at {new_percentage:.1f}% of your budget (over by RM {abs(remaining_after):.2f})"
            elif new_percentage >= 90:
                warning_level = "warning"
                message = f"⚠️ HIGH ALERT! This will use {new_percentage:.1f}% of your budget. Only RM {remaining_after:.2f} remaining."
            elif new_percentage >= 80:
                warning_level = "caution"
                message = f"⚡ CAUTION: This will use {new_percentage:.1f}% of your budget. RM {remaining_after:.2f} remaining."
            else:
                warning_level = "none"
                message = f"✅ Within budget ({new_percentage:.1f}% used). RM {remaining_after:.2f} remaining."

            result = {
                "has_budget": True,
                "warning_level": warning_level,
                "current_percentage": current_percentage,
                "new_percentage": new_percentage,
                "message": message,
                "limit": limit,
                "current_spent": current_spent,
                "new_spent": new_spent,
                "remaining_after": remaining_after,
            }
            logger.info(
                f"Budget warning for '{category_name}': {warning_level} (new: {new_percentage:.1f}%)"
            )
            return result

        except (NotFoundError, InvalidInputError):
            # No budget for this category
            logger.info(f"No budget found for category '{category_name}'")
            return {
                "has_budget": False,
                "warning_level": "none",
                "current_percentage": 0,
                "new_percentage": 0,
                "message": "",
                "limit": Decimal("0"),
                "current_spent": Decimal("0"),
                "new_spent": Decimal("0"),
                "remaining_after": Decimal("0"),
            }

    def get_budgets_at_risk(self, threshold: float = 80.0) -> list[dict]:
        """
        Get all budgets that are at or above a certain threshold.

        Args:
            threshold: Percentage threshold (default 80%)

        Returns:
            List of budget statuses that are at or above threshold
        """
        logger.info(f"Getting budgets at risk (threshold: {threshold}%)")
        all_statuses = self.get_all_budget_statuses()
        at_risk = []

        for status in all_statuses:
            if status["percentage"] >= threshold:
                at_risk.append(status)

        # Sort by percentage (highest first)
        at_risk.sort(key=lambda x: x["percentage"], reverse=True)

        logger.info(f"Found {len(at_risk)} budgets at or above {threshold}% threshold")
        return at_risk
