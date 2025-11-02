# gui/pages/dashboard_page.py

import calendar
from datetime import datetime

import streamlit as st

from app.database.base import SessionLocal
from app.services.account_service import AccountService
from app.services.budget_service import BudgetService
from app.services.category_service import CategoryService
from app.services.currency_service import CurrencyService
from app.services.prediction_service import PredictionService
from app.services.summary_service import SummaryService


def show_dashboard_page():
    """Display the main dashboard with financial overview."""

    st.title("Dashboard")

    # Create database session and services
    db_session = SessionLocal()
    currency_service = CurrencyService(db_session)
    account_service = AccountService(db_session, currency_service)
    category_service = CategoryService(db_session)
    budget_service = BudgetService(db_session, category_service)
    prediction_service = PredictionService(db_session)
    summary_service = SummaryService(
        db_session, account_service, category_service, currency_service
    )

    try:
        # Get current date for summaries
        today = datetime.now()
        current_year = today.year
        current_month = today.month

        # Get monthly summary
        monthly_summary = summary_service.get_monthly_summary(
            current_year, current_month
        )

        # Get all accounts
        accounts = account_service.get_all_accounts()

        # Calculate total balance across all accounts
        total_balance = sum(account.balance for account in accounts)

        #  Financial Overview
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                label="Total Balance",
                value=f"RM {total_balance:,.2f}",
            )

        with col2:
            st.metric(
                label="This Month's Expenses",
                value=f"RM {monthly_summary['total_expense']:,.2f}",
            )

        with col3:
            net = monthly_summary["net"]
            delta_color = "normal" if net >= 0 else "inverse"
            st.metric(
                label="Net This Month",
                value=f"RM {net:,.2f}",
                delta_color=delta_color,
            )

        st.divider()

        # Budget Alerts
        _show_budget_summary_widget(budget_service)

        st.divider()

        # Smart Predictions
        _show_spending_prediction_widget(
            prediction_service, current_year, current_month
        )

    except Exception as e:
        st.error(f"❌ Error loading dashboard: {str(e)}")
    finally:
        db_session.close()


def _show_budget_summary_widget(budget_service: BudgetService):
    """Display budget summary widget showing budgets at risk."""

    st.subheader("Budget Overview (Current Usage)")

    try:
        # Get budgets at risk (80% or higher)
        budgets_at_risk = budget_service.get_budgets_at_risk(threshold=80.0)

        if not budgets_at_risk:
            st.success("All budgets are healthy! No categories at risk.")
            return

        st.info("This shows your **actual spending so far** this period.")

        # Count by severity
        exceeded = [b for b in budgets_at_risk if b["percentage"] >= 100]
        high_alert = [b for b in budgets_at_risk if 90 <= b["percentage"] < 100]
        caution = [b for b in budgets_at_risk if 80 <= b["percentage"] < 90]

        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "🔴 Exceeded",
                len(exceeded),
                delta=f"{len(exceeded)} over budget" if exceeded else "None",
                delta_color="inverse",
            )
        with col2:
            st.metric(
                "🟠 High Alert",
                len(high_alert),
                delta="90-100%" if high_alert else "None",
                delta_color="off",
            )
        with col3:
            st.metric(
                "🟡 Caution",
                len(caution),
                delta="80-90%" if caution else "None",
                delta_color="off",
            )

        # Display budgets at risk
        for budget_status in budgets_at_risk[:5]:  # Show top 5 at risk
            category_name = budget_status["budget"].category.name
            percentage = budget_status["percentage"]
            spent = budget_status["spent"]
            limit = budget_status["limit"]
            remaining = budget_status["remaining"]
            period_start = budget_status["period_start"]
            period_end = budget_status["period_end"]

            # Determine color based on percentage
            if percentage >= 100:
                color = "🔴"
            elif percentage >= 90:
                color = "🟠"
            else:
                color = "🟡"

            # Create expandable section for each budget
            with st.expander(
                f"{color} **{category_name}** - {percentage:.1f}% used",
                expanded=percentage >= 100,
            ):
                col_a, col_b = st.columns(2)
                with col_a:
                    st.write(f"**Spent:** RM {spent:,.2f}")
                    st.write(f"**Limit:** RM {limit:,.2f}")
                with col_b:
                    st.write(f"**Remaining:** RM {remaining:,.2f}")
                    st.write(
                        f"**Period:** {period_start.strftime('%b %d')} - {period_end.strftime('%b %d, %Y')}"
                    )

                # Progress bar
                progress_value = min(percentage / 100, 1.0)
                st.progress(progress_value, text=f"{percentage:.1f}% of budget used")

                if percentage >= 100:
                    over_amount = abs(remaining)
                    st.error(f"Over budget by RM {over_amount:,.2f}!")
                elif percentage >= 90:
                    st.warning(f"Only RM {remaining:,.2f} remaining!")

        # Link to budget page
        st.caption("Manage your budgets in the **Budgets** page")

    except Exception as e:
        st.error(f"Error loading budget alerts: {str(e)}")


def _show_spending_prediction_widget(
    prediction_service: PredictionService, year: int, month: int
):
    """Display spending prediction widget using EWMA."""

    st.subheader("Smart Spending Forecast (Predicted End-of-Period)")

    try:
        # Get predictions for all categories with budgets
        budget_predictions = prediction_service.get_budget_predictions(year, month)

        if not budget_predictions:
            st.info("No budgets set yet. Create budgets to see spending predictions!")
            return

        st.info(
            "This predicts **how much you'll spend by the end** of each budget period."
        )

        # Get current month info
        today = datetime.now()
        if year == today.year and month == today.month:
            current_day = today.day
            month_name = today.strftime("%B %Y")
        else:
            current_day = calendar.monthrange(year, month)[1]
            month_name = f"{calendar.month_name[month]} {year}"

        days_in_month = calendar.monthrange(year, month)[1]

        # Overall summary
        st.write(f"**{month_name}** - Day {current_day}/{days_in_month}")

        # Count predictions by severity
        exceeded = [p for p in budget_predictions if p["will_exceed"]]
        high_usage = [
            p
            for p in budget_predictions
            if not p["will_exceed"] and p["predicted_usage_pct"] >= 90
        ]
        caution = [
            p
            for p in budget_predictions
            if not p["will_exceed"] and 80 <= p["predicted_usage_pct"] < 90
        ]
        on_track = [
            p
            for p in budget_predictions
            if not p["will_exceed"] and p["predicted_usage_pct"] < 80
        ]

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "🔴 Will Exceed",
                len(exceeded),
                delta="Predicted over budget" if exceeded else "None",
                delta_color="inverse",
            )
        with col2:
            st.metric(
                "🟠 High Usage",
                len(high_usage),
                delta="90%+ predicted" if high_usage else "None",
                delta_color="off",
            )
        with col3:
            st.metric(
                "🟡 Caution",
                len(caution),
                delta="80-90% predicted" if caution else "None",
                delta_color="off",
            )
        with col4:
            st.metric(
                "🟢 On Track",
                len(on_track),
                delta="Under 80%" if on_track else "None",
                delta_color="normal",
            )

        st.write("---")

        # Show all budget predictions
        for prediction in budget_predictions:  # Show all
            category_name = prediction["category_name"]
            predicted_total = prediction["predicted_total"]
            current_spending = prediction["current_spending"]
            budget_limit = prediction["budget_limit"]
            predicted_usage_pct = prediction["predicted_usage_pct"]
            confidence = prediction["confidence"]
            method = prediction["method"]
            period_start = prediction.get("period_start")
            period_end = prediction.get("period_end")
            days_passed = prediction.get("days_passed", 0)
            days_remaining = prediction.get("days_remaining", 0)

            # Ensure days_remaining is not negative
            days_remaining = max(0, days_remaining)

            # Determine color and icon based on predicted usage
            if prediction["will_exceed"]:
                icon = "🔴"
            elif predicted_usage_pct >= 90:
                icon = "🟠"
            elif predicted_usage_pct >= 80:
                icon = "🟡"
            else:
                icon = "🟢"

            # Create expandable section
            with st.expander(
                f"{icon} **{category_name}** - {predicted_usage_pct:.0f}% predicted",
                expanded=prediction["will_exceed"],  # Only auto-expand if exceeding
            ):
                # Show budget period if available
                if period_start and period_end:
                    today = datetime.now()
                    if today < period_start:
                        # Budget hasn't started yet
                        days_until_start = (period_start - today).days
                        st.caption(
                            f"Budget Period: {period_start.strftime('%b %d')} - {period_end.strftime('%b %d')} "
                            f"(Starts in {days_until_start} day{'s' if days_until_start != 1 else ''})"
                        )
                    elif days_remaining > 0:
                        # Budget period is active
                        st.caption(
                            f"Budget Period: {period_start.strftime('%b %d')} - {period_end.strftime('%b %d')} "
                            f"({days_passed} of {days_passed + days_remaining} days elapsed, {days_remaining} day{'s' if days_remaining != 1 else ''} left)"
                        )
                    else:
                        # Budget period has ended
                        st.caption(
                            f"Budget Period: {period_start.strftime('%b %d')} - {period_end.strftime('%b %d')} "
                            f"(Period ended - {days_passed} days total)"
                        )

                col_a, col_b = st.columns(2)

                with col_a:
                    st.write(f"**Current Spending:** RM {current_spending:,.2f}")
                    st.write(f"**Predicted Total:** RM {predicted_total:,.2f}")
                    st.write(f"**Budget Limit:** RM {budget_limit:,.2f}")

                with col_b:
                    overage = predicted_total - budget_limit
                    if overage > 0:
                        st.write(f"**Predicted Overage:** RM {overage:,.2f}")
                    else:
                        st.write(f"**Remaining:** RM {abs(overage):,.2f}")

                    st.write(f"**Confidence:** {confidence.upper()}")
                    st.write(f"**Method:** {method}")

                # Recommendation
                recommendation = prediction_service.get_spending_recommendation(
                    category_name, year, month
                )
                if recommendation["has_budget"]:
                    st.info(recommendation["message"])

                # Status message based on predicted usage
                if prediction["will_exceed"]:
                    st.error(
                        f"Predicted to exceed budget by RM {overage:,.2f} at current pace!"
                    )
                elif predicted_usage_pct >= 90:
                    st.warning("High spending predicted - monitor carefully!")
                elif predicted_usage_pct >= 80:
                    st.warning("Approaching budget limit - be cautious!")
                else:
                    st.success("On track to stay within budget!")

    except Exception as e:
        st.error(f"Error loading predictions: {str(e)}")
