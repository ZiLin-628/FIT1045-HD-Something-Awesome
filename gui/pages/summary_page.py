# gui/pages/summary_page.py

from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from app.database.base import SessionLocal
from app.services.account_service import AccountService
from app.services.category_service import CategoryService
from app.services.currency_service import CurrencyService
from app.services.summary_service import SummaryService


def show_summary_page():
    """Display the summary page"""

    # Create database session and services
    db_session = SessionLocal()
    currency_service = CurrencyService(db_session)
    account_service = AccountService(db_session, currency_service)
    category_service = CategoryService(db_session)
    summary_service = SummaryService(
        db_session, account_service, category_service, currency_service
    )

    st.title("Financial Summary")

    # Create tabs for different summary types
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "Daily Summary",
            "Weekly Summary",
            "Monthly Summary",
            "Expenses by Category",
            "Income by Category",
        ]
    )

    try:
        with tab1:
            daily_summary_view(summary_service)

        with tab2:
            weekly_summary_view(summary_service)

        with tab3:
            monthly_summary_view(summary_service)

        with tab4:
            expenses_by_category_view(summary_service)

        with tab5:
            income_by_category_view(summary_service)

    finally:
        db_session.close()


def daily_summary_view(summary_service: SummaryService):
    """Tab for daily financial summary."""

    st.header("Daily Summary")

    # Date picker
    selected_date = st.date_input(
        "Select Date",
        value=datetime.now(),
        help="Choose a date to view the financial summary",
    )

    if selected_date:
        # Convert date to datetime
        date_obj = datetime.combine(selected_date, datetime.min.time())

        # Get summary
        summary = summary_service.get_daily_summary(date_obj)

        # Display summary

        st.markdown("<br>", unsafe_allow_html=True)

        st.subheader(f"Summary for {summary['date']}")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Income", f"RM {summary['total_income']:,.2f}")
        with col2:
            st.metric("Total Expenses", f"RM {summary['total_expense']:,.2f}")
        with col3:
            net_value = summary["net"]
            st.metric("Net Balance", f"RM {net_value:,.2f}")
        with col4:
            st.metric("Transactions", summary["transaction_count"])

        # Visual representation
        if summary["transaction_count"] > 0:
            st.divider()

            st.subheader("Visual Breakdown")

            # Create pie chart
            chart_data = pd.DataFrame(
                {
                    "Category": ["Income", "Expenses"],
                    "Amount": [
                        float(summary["total_income"]),
                        float(summary["total_expense"]),
                    ],
                }
            )

            if chart_data["Amount"].sum() > 0:
                fig = px.pie(
                    chart_data,
                    values="Amount",
                    names="Category",
                    title="Income vs Expenses",
                    color_discrete_sequence=["#00CC96", "#EF553B"],
                )
                fig.update_traces(
                    hovertemplate="%{label}<br>RM %{value:.2f}<br>%{percent}<extra></extra>"
                )
                st.plotly_chart(fig, use_container_width=True, key="daily_pie_chart")
        else:
            st.info("No transactions found for this date.")


def weekly_summary_view(summary_service: SummaryService):
    """Tab for weekly financial summary."""

    st.header("Weekly Summary")

    # Date picker for any day in the week
    selected_date = st.date_input(
        "Select any date in the week",
        value=datetime.now(),
        help="Choose a date, and the summary will show the entire week containing that date",
    )

    if selected_date:
        # Convert date to datetime
        date_obj = datetime.combine(selected_date, datetime.min.time())

        # Get summary
        summary = summary_service.get_weekly_summary(date_obj)

        # Display summary
        st.markdown("<br>", unsafe_allow_html=True)

        st.subheader(f"Week: {summary['week_start']} to {summary['week_end']}")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Income", f"RM {summary['total_income']:,.2f}")
        with col2:
            st.metric("Total Expenses", f"RM {summary['total_expense']:,.2f}")
        with col3:
            net_value = summary["net"]
            st.metric("Net Balance", f"RM {net_value:,.2f}")
        with col4:
            st.metric("Transactions", summary["transaction_count"])

        # Visual representation
        if summary["transaction_count"] > 0:
            st.divider()
            st.subheader("Visual Breakdown")

            # Create pie chart
            chart_data = pd.DataFrame(
                {
                    "Category": ["Income", "Expenses"],
                    "Amount": [
                        float(summary["total_income"]),
                        float(summary["total_expense"]),
                    ],
                }
            )

            if chart_data["Amount"].sum() > 0:
                fig = px.pie(
                    chart_data,
                    values="Amount",
                    names="Category",
                    title="Income vs Expenses",
                    color_discrete_sequence=["#00CC96", "#EF553B"],
                )
                fig.update_traces(
                    hovertemplate="%{label}<br>RM %{value:.2f}<br>%{percent}<extra></extra>"
                )
                st.plotly_chart(fig, use_container_width=True, key="weekly_pie_chart")
        else:
            st.info("No transactions found for this week.")


def monthly_summary_view(summary_service: SummaryService):
    """Tab for monthly financial summary."""

    st.header("Monthly Summary")

    # Month and year pickers
    col1, col2 = st.columns(2)
    with col1:
        selected_month = st.selectbox(
            "Select Month",
            options=list(range(1, 13)),
            format_func=lambda x: datetime(2000, x, 1).strftime("%B"),
            index=datetime.now().month - 1,
        )
    with col2:
        current_year = datetime.now().year
        selected_year = st.number_input(
            "Select Year",
            min_value=2000,
            max_value=2100,
            value=current_year,
            step=1,
        )

    # Get summary
    summary = summary_service.get_monthly_summary(selected_year, selected_month)

    if summary:
        # Display summary
        st.markdown("<br>", unsafe_allow_html=True)

        st.subheader(f"{summary['month']} {summary['year']}")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Income", f"RM {summary['total_income']:,.2f}")
        with col2:
            st.metric("Total Expenses", f"RM {summary['total_expense']:,.2f}")
        with col3:
            net_value = summary["net"]
            st.metric("Net Balance", f"RM {net_value:,.2f}")
        with col4:
            st.metric("Transactions", summary["transaction_count"])

        # Visual representation
        if summary["transaction_count"] > 0:
            st.divider()
            st.subheader("Visual Breakdown")

            # Create comparison chart
            chart_data = pd.DataFrame(
                {
                    "Category": ["Income", "Expenses"],
                    "Amount": [
                        float(summary["total_income"]),
                        float(summary["total_expense"]),
                    ],
                }
            )

            # Pie chart
            if chart_data["Amount"].sum() > 0:
                fig = px.pie(
                    chart_data,
                    values="Amount",
                    names="Category",
                    title="Income vs Expenses",
                    color_discrete_sequence=["#00CC96", "#EF553B"],
                )
                fig.update_traces(
                    hovertemplate="%{label}<br>RM %{value:.2f}<br>%{percent}<extra></extra>"
                )
                st.plotly_chart(fig, use_container_width=True, key="monthly_pie_chart")
        else:
            st.info(f"No transactions found for {summary['month']} {summary['year']}.")
    else:
        st.error("Invalid month or year selected.")


def expenses_by_category_view(summary_service: SummaryService):
    """Tab for expenses breakdown by category."""

    st.header("Expenses by Category")

    # Date range picker
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=datetime.now() - timedelta(days=30),
            help="Start of the date range",
        )
    with col2:
        end_date = st.date_input(
            "End Date",
            value=datetime.now(),
            help="End of the date range",
        )

    if start_date and end_date:
        if start_date > end_date:
            st.error("Start date must be before or equal to end date.")
        else:
            # Convert dates to datetime
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.min.time())

            # Get expenses by category
            expenses = summary_service.get_expenses_by_category(
                start_datetime, end_datetime
            )

            if expenses:
                st.markdown("<br>", unsafe_allow_html=True)

                st.subheader(
                    f"Expenses from {start_date.strftime('%d-%m-%Y')} to {end_date.strftime('%d-%m-%Y')}"
                )

                # Calculate total
                total_expenses = sum(expenses.values())

                # Display total
                st.metric("Total Expenses", f"RM {total_expenses:,.2f}")

                st.divider()

                # Create DataFrame
                expense_data = pd.DataFrame(
                    [
                        {
                            "Category": cat,
                            "Amount": float(amount),
                            "Percentage": f"{(float(amount)/float(total_expenses)*100):.1f}%",
                        }
                        for cat, amount in sorted(
                            expenses.items(), key=lambda x: x[1], reverse=True
                        )
                    ]
                )

                # Display table
                st.dataframe(expense_data, use_container_width=True, hide_index=True)

                # Visual representation
                st.divider()
                st.subheader("Visual Breakdown")

                # Pie chart
                chart_data = pd.DataFrame(
                    [
                        {"Category": cat, "Amount": float(amount)}
                        for cat, amount in expenses.items()
                    ]
                )
                fig = px.pie(
                    chart_data,
                    values="Amount",
                    names="Category",
                    title="Expenses Distribution",
                )
                fig.update_traces(
                    hovertemplate="%{label}<br>RM %{value:.2f}<br>%{percent}<extra></extra>"
                )
                st.plotly_chart(fig, use_container_width=True, key="expenses_pie_chart")
            else:
                st.info(
                    f"No expenses found between {start_date.strftime('%d-%m-%Y')} and {end_date.strftime('%d-%m-%Y')}."
                )


def income_by_category_view(summary_service: SummaryService):
    """Tab for income breakdown by category."""

    st.header("Income by Category")

    # Date range picker
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=datetime.now() - timedelta(days=30),
            help="Start of the date range",
            key="income_start",
        )
    with col2:
        end_date = st.date_input(
            "End Date",
            value=datetime.now(),
            help="End of the date range",
            key="income_end",
        )

    if start_date and end_date:
        if start_date > end_date:
            st.error("Start date must be before or equal to end date.")
        else:
            # Convert dates to datetime
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.min.time())

            # Get income by category
            income = summary_service.get_income_by_category(
                start_datetime, end_datetime
            )

            if income:
                st.markdown("<br>", unsafe_allow_html=True)

                st.subheader(
                    f"Income from {start_date.strftime('%d-%m-%Y')} to {end_date.strftime('%d-%m-%Y')}"
                )

                # Calculate total
                total_income = sum(income.values())

                # Display total
                st.metric("Total Income", f"RM {total_income:,.2f}")

                st.divider()

                # Create DataFrame
                income_data = pd.DataFrame(
                    [
                        {
                            "Category": cat,
                            "Amount": float(amount),
                            "Percentage": f"{(float(amount)/float(total_income)*100):.1f}%",
                        }
                        for cat, amount in sorted(
                            income.items(), key=lambda x: x[1], reverse=True
                        )
                    ]
                )

                # Display table
                st.dataframe(income_data, use_container_width=True, hide_index=True)

                # Visual representation
                st.divider()
                st.subheader("Visual Breakdown")

                # Pie chart
                chart_data = pd.DataFrame(
                    [
                        {"Category": cat, "Amount": float(amount)}
                        for cat, amount in income.items()
                    ]
                )
                fig = px.pie(
                    chart_data,
                    values="Amount",
                    names="Category",
                    title="Income Distribution",
                )
                fig.update_traces(
                    hovertemplate="%{label}<br>RM %{value:.2f}<br>%{percent}<extra></extra>"
                )
                st.plotly_chart(fig, use_container_width=True, key="income_pie_chart")
            else:
                st.info(
                    f"No income found between {start_date.strftime('%d-%m-%Y')} and {end_date.strftime('%d-%m-%Y')}."
                )
