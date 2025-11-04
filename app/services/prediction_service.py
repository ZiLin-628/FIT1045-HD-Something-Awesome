# app/services/prediction_service.py

import calendar
import logging
import warnings
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session
from statsmodels.tsa.holtwinters import SimpleExpSmoothing

from app.database.models import (
    Budget,
    BudgetPeriod,
    Category,
    Transaction,
    TransactionType,
)
from app.services.budget_service import BudgetService
from app.services.category_service import CategoryService

logger = logging.getLogger(__name__)

# Suppress statsmodels warnings
warnings.filterwarnings("ignore", category=UserWarning, module="statsmodels")
warnings.filterwarnings(
    "ignore", category=RuntimeWarning, message="divide by zero encountered in log"
)


class PredictionService:
    """Service for spending predictions"""

    def __init__(self, db_session: Session):
        """
        Initialize prediction service.

        Args:
            db_session: database session
        """

        self.db_session = db_session
        category_service = CategoryService(db_session)
        self.budget_service = BudgetService(db_session, category_service)

    def predict_category_monthly_spending(
        self,
        category_name: str,
        year: int,
        month: int,
        lookback_months: int = 6,
    ) -> dict:
        """Predict monthly spending for a category.

        Uses a mix of current spending progress and historical data to estimate
        total spending for the current or upcoming period.

        Args:
            category_name (str): Category name.
            year (int): Year for prediction.
            month (int): Month for prediction
            lookback_months (int, optional): Number of months of history to use. Defaults to 6.

        Returns:
            dict: Spending prediction and related data.
        """
        logger.info(
            f"Predicting monthly spending for category '{category_name}' for {year}-{month:02d}"
        )

        # Determine whether to use budget period or calendar month
        period_data = self.get_period_data(category_name, year, month)

        # Get historical spending patterns
        historical_totals = self.get_historical_monthly_spending(
            category_name, year, month, lookback_months
        )

        # Calculate current and historical daily spending rates
        current_daily_rate = self.calculate_daily_rate(
            period_data["current_spending"], period_data["days_passed"]
        )

        historical_daily_rate, method = self.calculate_historical_rate(
            historical_totals, period_data["days_in_period"]
        )
        
        # Now have 

        # Blend current and historical trends
        blended_daily_rate = self.mix_daily_rates(
            current_daily_rate,
            historical_daily_rate,
            period_data["days_passed"],
            period_data["days_in_period"],
        )

        # Predict remaining spending for the rest of the period
        predicted_total = period_data["current_spending"] + (
            blended_daily_rate * Decimal(period_data["days_remaining"])
        )

        return {
            "predicted_total": predicted_total,
            "current_spending": period_data["current_spending"],
            "daily_rate_current": current_daily_rate,
            "daily_rate_predicted": blended_daily_rate,
            "days_passed": period_data["days_passed"],
            "days_remaining": period_data["days_remaining"],
            "confidence": self.calculate_confidence(
                period_data["days_passed"], len(historical_totals)
            ),
            "historical_average": (
                Decimal(str(historical_totals[-1]))
                if historical_totals
                else Decimal("0")
            ),
            "method": method,
            "budget_limit": period_data["budget_limit"],
            "will_exceed": (
                predicted_total > period_data["budget_limit"]
                if period_data["budget_limit"]
                else False
            ),
            "period_start": period_data["period_start"],
            "period_end": period_data["period_end"],
        }

    def get_period_data(self, category_name: str, year: int, month: int) -> dict:
        """
        Get the date range and spending info for a period.

        Args:
            category_name (str): Category name.
            year (int): Year.
            month (int): Month.

        Returns:
            dict: Information about the period, including dates, spending, and budget.
        """

        # Get budget period info
        budget_info = self.get_budget_period_info(category_name, year, month)
        today = datetime.now()

        if budget_info:
            # Use budget period
            period_start = budget_info["period_start"]
            period_end = budget_info["period_end"]
            days_in_period = budget_info["days_in_period"]
            budget_limit = budget_info["budget_limit"]

            # Compute days passed and current spending in budget period
            days_passed = self.calculate_days_passed(
                today, period_start, period_end, days_in_period
            )
            current_spending = self.get_spending_in_period(
                category_name, period_start, period_end
            )
            
        else:
            # Use calendar month
            days_in_period = calendar.monthrange(year, month)[1]
            period_start = datetime(year, month, 1)
            period_end = (
                datetime(year + 1, 1, 1)
                if month == 12
                else datetime(year, month + 1, 1)
            )
            budget_limit = None

            # Determine days passed based on current month
            if year == today.year and month == today.month:
                days_passed = today.day
            elif year < today.year or (year == today.year and month < today.month):
                days_passed = days_in_period
            else:
                days_passed = 0

            # Calculate current spending for the calendar month
            current_spending = self.get_category_spending(category_name, year, month)

        return {
            "period_start": period_start,
            "period_end": period_end,
            "days_in_period": days_in_period,
            "days_passed": days_passed,
            "days_remaining": max(0, days_in_period - days_passed),
            "current_spending": current_spending,
            "budget_limit": budget_limit,
        }

    def calculate_days_passed(
        self,
        today: datetime,
        period_start: datetime,
        period_end: datetime,
        days_in_period: int,
    ) -> int:
        """
        Calculate how many days have passed in the current period.

        Args:
            today (datetime): Current date.
            period_start (datetime): Period start date.
            period_end (datetime): Period end date.
            days_in_period (int): Total days in the period.

        Returns:
            int: Number of days passed.
        """

        # Period not started
        if today < period_start:
            return 0

        # Period finished
        elif today >= period_end:
            return days_in_period

        # Day passed
        else:
            return (today - period_start).days + 1

    def calculate_daily_rate(self, amount: Decimal, days: int) -> Decimal:
        """
        Get daily average spending.

        Args:
            amount (Decimal): Total amount spent.
            days (int): Number of days passed.

        Returns:
            Decimal: Average daily spending.
        """
        return amount / Decimal(days) if days > 0 else Decimal("0")

    def calculate_historical_rate(
        self, historical_totals: list, days_in_period: int
    ) -> tuple[Decimal, str]:
        """
        Calculate the average daily rate from historical data using exponential smoothing.

        Args:
            historical_totals (list): List of previous monthly totals (always 6 months).
            days_in_period (int): Days in the current period.

        Returns:
            tuple[Decimal, str]: (historical daily rate, method name)
        """

        # Always use exponential smoothing (lookback_months is fixed at 6)
        historical_avg = self.predict_with_exponential_smoothing(historical_totals)
        method = "Exponential Smoothing"

        # Convert to daily rate
        historical_daily_rate = Decimal(str(historical_avg)) / Decimal(
            str(days_in_period)
        )
        return historical_daily_rate, method

    def mix_daily_rates(
        self,
        current_rate: Decimal,
        historical_rate: Decimal,
        days_passed: int,
        days_in_period: int,
    ) -> Decimal:
        """
        Blend current and historical daily rates based on progress.

        Args:
            current_rate (Decimal): Current daily rate.
            historical_rate (Decimal): Historical daily rate.
            days_passed (int): Number of days passed.
            days_in_period (int): Total days in the period.

        Returns:
            Decimal: Blended daily rate.
        """
        if days_in_period > 0 and days_passed > 0:
            # Weight current rate
            progress_weight = Decimal(days_passed) / Decimal(days_in_period)

            return (
                progress_weight * current_rate
                + (Decimal("1") - progress_weight) * historical_rate
            )
        return historical_rate

    def predict_with_exponential_smoothing(self, historical_values: list) -> float:
        """
        Predict next month's spending using Exponential Smoothing.

        Args:
            historical_values (list): Monthly totals from oldest to newest.

        Returns:
            float: Predicted value for the next month.
        """
        try:
            if len(historical_values) < 2:
                return historical_values[0] if historical_values else 0

            # Check if all values are the same (causes zero variance issues)
            if len(set(historical_values)) == 1:
                return historical_values[0]

            # Suppress numpy/statsmodels warnings during model fitting
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore")

                # Create and fit model
                model = SimpleExpSmoothing(historical_values)
                fitted_model = model.fit(optimized=True)

                # Forecast next period
                prediction = fitted_model.forecast(1)[0]

            return float(prediction)

        except Exception:
            # Fallback to simple average
            return (
                sum(historical_values) / len(historical_values)
                if historical_values
                else 0
            )

    def get_budget_predictions(self, year: int, month: int) -> list:
        """
        Get predictions for all categories with budgets.

        Returns list of all categories with budgets, showing their predicted usage.

        Args:
            year: Year to predict for
            month: Month to predict for

        Returns:
            List of predictions for all budgeted categories, sorted by usage percentage (highest first)
        """
        logger.info(
            f"Getting budget predictions for all categories for {year}-{month:02d}"
        )

        # Get all expense categories
        categories = (
            self.db_session.query(Category)
            .filter(Category.type == TransactionType.EXPENSE)
            .all()
        )

        budgeted = []
        for category in categories:
            try:
                prediction = self.predict_category_monthly_spending(
                    category.name, year, month
                )
                prediction["category_name"] = category.name

                # Only include categories with budgets
                if prediction["budget_limit"] is not None:
                    prediction["predicted_usage_pct"] = float(
                        (prediction["predicted_total"] / prediction["budget_limit"])
                        * 100
                    )
                    budgeted.append(prediction)
            except Exception as e:
                logger.warning(f"Failed to predict for category {category.name}: {e}")
                continue

        # Sort by usage percentage descending
        budgeted.sort(key=lambda x: x.get("predicted_usage_pct", 0), reverse=True)
        logger.info(f"Generated predictions for {len(budgeted)} budgeted categories")

        return budgeted

    def get_spending_recommendation(
        self, category_name: str, year: int, month: int
    ) -> dict:
        """Give daily spending advice to stay within budget.

        Args:
            category_name (str): Category name.
            year (int): Year.
            month (int): Month

        Returns:
            dict: Recommendation and current spending details.
        """

        prediction = self.predict_category_monthly_spending(category_name, year, month)

        if prediction["budget_limit"] is None:
            return {
                "has_budget": False,
                "recommended_daily_rate": None,
                "current_daily_rate": prediction["daily_rate_current"],
                "adjustment_needed": None,
                "message": "No budget set for this category.",
            }

        # Calculate recommended daily rate
        days_remaining = prediction["days_remaining"]
        current_spending = prediction["current_spending"]
        budget_limit = prediction["budget_limit"]

        if days_remaining > 0:
            remaining_budget = budget_limit - current_spending
            recommended_daily_rate = remaining_budget / Decimal(days_remaining)
        else:
            recommended_daily_rate = Decimal("0")

        adjustment_needed = prediction["daily_rate_current"] - recommended_daily_rate

        # Generate message
        if prediction["will_exceed"]:
            if adjustment_needed > 0:
                message = (
                    f"Reduce spending to RM {recommended_daily_rate:.2f}/day "
                    f"(currently RM {prediction['daily_rate_current']:.2f}/day) "
                    f"to stay within budget."
                )
            else:
                message = "You may exceed budget. Monitor spending carefully."
        else:
            message = f"On track! Keep spending at or below RM {recommended_daily_rate:.2f}/day."

        return {
            "has_budget": True,
            "recommended_daily_rate": recommended_daily_rate,
            "current_daily_rate": prediction["daily_rate_current"],
            "adjustment_needed": adjustment_needed,
            "message": message,
        }

    def get_category_spending(
        self, category_name: str, year: int, month: int
    ) -> Decimal:
        """Get total spending for a category in a given month.

        Args:
            category_name (str): Category name.
            year (int): Year.
            month (int): Month

        Returns:
            Decimal: Total amount spent in MYR.
        """

        start_date = datetime(year, month, 1)

        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)

        transactions = (
            self.db_session.query(Transaction)
            .filter(
                Transaction.datetime >= start_date,
                Transaction.datetime < end_date,
                Transaction.category.has(name=category_name),
                Transaction.transaction_type == TransactionType.EXPENSE,
            )
            .all()
        )

        total = sum(t.amount_in_myr for t in transactions)
        
        # Rertun 0.00 if not= transaction found
        return Decimal(str(total))

    def get_historical_monthly_spending(
        self,
        category_name: str,
        current_year: int,
        current_month: int,
        lookback_months: int,
    ) -> list:
        """
        Get historical monthly spending totals in chronological order.

        Args:
            category_name: Name of the category
            current_year: Current year
            current_month: Current month
            lookback_months: Number of months to look back

        Returns:
            List [oldest, ..., most_recent] of monthly spending totals
        """
        historical = []

        year = current_year
        month = current_month

        # Collect historical data
        for _ in range(lookback_months):
            month -= 1
            if month < 1:
                month = 12
                year -= 1

            spending = self.get_category_spending(category_name, year, month)
            historical.append(float(spending))

        # Reverse to chronological order
        historical.reverse()

        return historical

    def calculate_confidence(self, days_passed: int, historical_count: int) -> str:
        """Estimate confidence level of the prediction.

        Args:
            days_passed (int): Days passed in the current period.
            historical_count (int): Number of months of historical data.

        Returns:
            str: 'low', 'medium', or 'high' confidence.
        """

        # Score based on current month progress
        day_score = min(days_passed / 7, 1.0)

        # Score based on historical data
        history_score = min(historical_count / 6, 1.0)

        # Combined score
        total_score = (day_score + history_score) / 2

        if total_score >= 0.7:
            return "high"
        elif total_score >= 0.4:
            return "medium"
        else:
            return "low"

    def get_budget_period_info(
        self, category_name: str, year: int, month: int
    ) -> dict | None:
        """
        Get budget details and current period for a category.

        Args:
            category_name (str): Category name.
            year (int): Year.
            month (int): Month

        Returns:
            dict | None: Budget period data, or None if not found.
        """
        try:
            # Get category and budget
            category = (
                self.db_session.query(Category)
                .filter(
                    Category.name == category_name,
                    Category.type == TransactionType.EXPENSE,
                )
                .first()
            )

            if not category:
                return None

            # Get MONTHLY budgets only
            budget = (
                self.db_session.query(Budget)
                .filter_by(category_id=category.id, period=BudgetPeriod.MONTHLY)
                .first()
            )

            if not budget:
                return None

            # Calculate current period
            period_start, period_end = self.budget_service._get_current_period(budget)
            days_in_period = (period_end - period_start).days

            return {
                "period_start": period_start,
                "period_end": period_end,
                "budget_limit": budget.limit_amount,
                "days_in_period": days_in_period,
            }

        except Exception:
            return None

    def get_spending_in_period(
        self, category_name: str, start_date: datetime, end_date: datetime
    ) -> Decimal:
        """
        Get total spending for a category within a custom date range.

        Args:
            category_name (str): Category name.
            start_date (datetime): Start of the period.
            end_date (datetime): End of the period.

        Returns:
            Decimal: Total amount spent in MYR.
        """

        transactions = (
            self.db_session.query(Transaction)
            .filter(
                Transaction.datetime >= start_date,
                Transaction.datetime < end_date,
                Transaction.category.has(name=category_name),
                Transaction.transaction_type == TransactionType.EXPENSE,
            )
            .all()
        )

        total = sum(t.amount_in_myr for t in transactions)
        return Decimal(str(total))
