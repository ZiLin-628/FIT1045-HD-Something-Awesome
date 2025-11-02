# app/services/summary_service.py

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database.models import Transaction, TransactionType

logger = logging.getLogger(__name__)


class SummaryService:
    """
    Service class for generating summaries.
    """

    def __init__(
        self, db_session: Session, account_service, category_service, currency_service
    ) -> None:
        """
        Initialize SummaryService.

        Args:
            db_session (Session): database session.
            account_service: Service managing accounts.
            category_service: Service managing categories.
            currency_service: Service managing currency conversions.
        """

        self.db_session = db_session
        self.account_service = account_service
        self.category_service = category_service
        self.currency_service = currency_service

    def _get_transactions_in_range(
        self,
        start: datetime,
        end: datetime,
        transaction_type: TransactionType | None = None,
    ):
        """
        Fetch transactions within a datetime range.

        Args:
            start (datetime): Start datetime.
            end (datetime): End datetime.
            transaction_type (TransactionType | None): Optional filter by type.

        Returns:
            list[Transaction]: Transactions matching the criteria.
        """

        query = self.db_session.query(Transaction).filter(
            Transaction.datetime >= start, Transaction.datetime <= end
        )
        if transaction_type:
            query = query.filter(Transaction.transaction_type == transaction_type)
        return query.all()

    def get_daily_summary(self, date: datetime):
        """
        Generate a summary for a specific day.

        Args:
            date (datetime): The date for which to generate the summary.

        Returns:
            dict: Summary containing total income, expenses, net balance, and count of transactions.
        """
        logger.info(f"Generating daily summary for {date.strftime('%d-%m-%Y')}")

        # Set the day start and end boundaries
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)

        # Filter transactions happen on this day
        transactions = self._get_transactions_in_range(start_of_day, end_of_day)

        # Use stored MYR amounts for consistency
        total_income = sum(
            t.amount_in_myr
            for t in transactions
            if t.transaction_type == TransactionType.INCOME
        )
        total_expense = sum(
            t.amount_in_myr
            for t in transactions
            if t.transaction_type == TransactionType.EXPENSE
        )
        net = total_income - total_expense

        logger.info(
            f"Daily summary: {len(transactions)} transactions, Income: {total_income}, Expense: {total_expense}, Net: {net}"
        )

        return {
            "date": date.strftime("%d-%m-%Y"),
            "total_income": total_income,
            "total_expense": total_expense,
            "net": net,
            "transaction_count": len(transactions),
        }

    def get_weekly_summary(self, date: datetime):
        """
        Generate a summary for the week containing the given date.

        Args:
            date (datetime): Any date within the desired week.

        Returns:
            dict: Summary with totals for income, expenses, net balance, and transaction count.
        """
        logger.info(
            f"Generating weekly summary for week containing {date.strftime('%d-%m-%Y')}"
        )

        # Get the ISO calendar (year, week_number, weekday)
        # weekday: 1=Monday, 7=Sunday
        iso_year, iso_week, iso_weekday = date.isocalendar()

        # Calculate Monday of this week (start of week)
        week_start = date - timedelta(days=iso_weekday - 1)
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

        # Calculate Sunday of this week (end of week)
        week_end = week_start + timedelta(days=6)
        week_end = week_end.replace(hour=23, minute=59, second=59, microsecond=999999)

        # Filter transactions for this week
        transactions = self._get_transactions_in_range(week_start, week_end)

        # Use stored MYR amounts for consistency
        total_income = sum(
            t.amount_in_myr
            for t in transactions
            if t.transaction_type == TransactionType.INCOME
        )
        total_expense = sum(
            t.amount_in_myr
            for t in transactions
            if t.transaction_type == TransactionType.EXPENSE
        )
        net = total_income - total_expense

        return {
            "week_start": week_start.strftime("%d-%m-%Y"),
            "week_end": week_end.strftime("%d-%m-%Y"),
            "total_income": total_income,
            "total_expense": total_expense,
            "net": net,
            "transaction_count": len(transactions),
        }

    def get_monthly_summary(self, year: int, month: int) -> dict:
        """
        Generate a summary for a specific month.

        Args:
            year (int): Year of the summary.
            month (int): Month number (1-12).

        Returns:
            dict: Summary with totals for income, expenses, net balance, and transaction count.
                  Returns an empty dict if year/month are invalid.
        """
        logger.info(f"Generating monthly summary for {month}/{year}")

        # Validate month and year
        if month < 1 or month > 12 or year <= 0:
            logger.warning(f"Invalid month/year: {month}/{year}")
            return {}

        month_start = datetime(year, month, 1, 0, 0, 0)

        if month == 12:
            next_month = datetime(year + 1, 1, 1)
        else:
            next_month = datetime(year, month + 1, 1)

        month_end = next_month - timedelta(days=1)
        month_end = month_end.replace(hour=23, minute=59, second=59, microsecond=999999)

        transactions = self._get_transactions_in_range(month_start, month_end)

        # Use stored MYR amounts for consistency
        total_income = sum(
            t.amount_in_myr
            for t in transactions
            if t.transaction_type == TransactionType.INCOME
        )
        total_expense = sum(
            t.amount_in_myr
            for t in transactions
            if t.transaction_type == TransactionType.EXPENSE
        )
        net = total_income - total_expense

        month_name = month_start.strftime("%B")
        return {
            "month": month_name,
            "year": year,
            "total_income": total_income,
            "total_expense": total_expense,
            "net": net,
            "transaction_count": len(transactions),
        }

    def get_expenses_by_category(
        self, start_date: datetime, end_date: datetime
    ) -> dict:
        """
        Summarize expenses by category for a date range.

        Args:
            start_date (datetime): Start date.
            end_date (datetime): End date.

        Returns:
            dict: Mapping of category name to total expense (MYR).
        """
        logger.info(
            f"Getting expenses by category from {start_date.date()} to {end_date.date()}"
        )

        # Validate dates
        if start_date > end_date:
            logger.warning("Invalid date range: start_date > end_date")
            return {}

        # Set time boundaries
        start_of_day = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        # Filter expense transactions for this date range
        transactions = self._get_transactions_in_range(
            start_of_day, end_of_day, transaction_type=TransactionType.EXPENSE
        )

        expenses_by_category = {}
        for t in transactions:
            cat_name = t.category.name
            # Use stored MYR amount for consistency
            expenses_by_category[cat_name] = (
                expenses_by_category.get(cat_name, Decimal("0.00")) + t.amount_in_myr
            )

        logger.info(f"Expenses by category: {len(expenses_by_category)} categories")
        return expenses_by_category

    def get_income_by_category(self, start_date: datetime, end_date: datetime) -> dict:
        """
        Summarize income by category for a date range.

        Args:
            start_date (datetime): Start date.
            end_date (datetime): End date.

        Returns:
            dict: Mapping of category name to total income (MYR).
        """
        logger.info(
            f"Getting income by category from {start_date.date()} to {end_date.date()}"
        )

        # Validate dates
        if start_date > end_date:
            logger.warning("Invalid date range: start_date > end_date")
            return {}

        # Set time boundaries
        start_of_day = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        # Filter income transactions for this date range
        transactions = self._get_transactions_in_range(
            start_of_day, end_of_day, transaction_type=TransactionType.INCOME
        )

        income_by_category = {}
        for t in transactions:
            cat_name = t.category.name
            # Use stored MYR amount for consistency
            income_by_category[cat_name] = (
                income_by_category.get(cat_name, Decimal("0.00")) + t.amount_in_myr
            )

        logger.info(f"Income by category: {len(income_by_category)} categories")
        return income_by_category
