from datetime import datetime

import pandas as pd
import streamlit as st

from app.database.base import SessionLocal
from app.database.models import TransactionType
from app.exception import AlreadyExistsError, InvalidInputError, NotFoundError
from app.services.budget_service import BudgetService
from app.services.category_service import CategoryService
import gui.utility as utility


def show_budget_operation_page():
    """Display the budget operations page with tabs for different operations."""

    # Create database session
    db_session = SessionLocal()
    category_service = CategoryService(db_session)
    budget_service = BudgetService(db_session, category_service)

    st.title("Budget Management")

    # Create tabs for different operations
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "Budget Overview",
            "View All Budgets",
            "Add Budget",
            "Edit Budget",
            "Delete Budget",
        ]
    )

    try:
        with tab1:
            show_budget_overview_view(budget_service)

        with tab2:
            show_all_budgets_view(budget_service)

        with tab3:
            add_budget_view(budget_service, category_service)

        with tab4:
            edit_budget_view(budget_service, category_service)

        with tab5:
            delete_budget_view(budget_service, category_service)

    finally:
        db_session.close()


def show_budget_overview_view(budget_service: BudgetService):
    """Display budget overview with status for all budgets."""

    st.subheader("Expense Budget Status Overview")

    try:
        # Get all budget statuses
        statuses = budget_service.get_all_budget_statuses()

        # Filter to only expense budgets
        expense_statuses = [
            s for s in statuses if s["budget"].category.type == TransactionType.EXPENSE
        ]

        if not expense_statuses:
            st.info("No expense budgets configured yet. Add a budget to get started!")
            return

        # Separate by exceeded status
        exceeded_budgets = [s for s in expense_statuses if s["is_exceeded"]]
        on_track_budgets = [s for s in expense_statuses if not s["is_exceeded"]]

        # Show alerts for exceeded budgets
        if exceeded_budgets:
            st.error(f"**{len(exceeded_budgets)} budget(s) exceeded!**")
            for status in exceeded_budgets:
                with st.expander(
                    f"🔴 {status['budget'].category.name}",
                    expanded=True,
                ):
                    _display_budget_status(status)

        # Show on-track budgets
        if on_track_budgets:
            st.success(f"**{len(on_track_budgets)} budget(s) on track**")
            for status in on_track_budgets:
                with st.expander(f"🟢 {status['budget'].category.name}"):
                    _display_budget_status(status)

        # Summary metrics
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Budgets", len(statuses))
        with col2:
            st.metric(
                "On Track", len(on_track_budgets), delta="Good", delta_color="normal"
            )
        with col3:
            st.metric(
                "Exceeded",
                len(exceeded_budgets),
                delta="Alert" if exceeded_budgets else "None",
                delta_color="inverse",
            )

    except Exception as e:
        st.error(f"Error loading budget overview: {e}")


def _display_budget_status(status: dict):
    """Display a single budget's status with progress bar and details."""

    budget = status["budget"]

    # Budget details
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Category:** {budget.category.name}")
        st.markdown(f"**Period:** {budget.period.value.title()}")
    with col2:
        st.markdown(f"**Limit:** RM {status['limit']:,.2f}")
        st.markdown(f"**Spent:** RM {status['spent']:,.2f}")
        st.markdown(f"**Remaining:** RM {status['remaining']:,.2f}")

    # Progress bar
    percentage = min(status["percentage"], 100)  # Cap at 100 for display
    if status["is_exceeded"]:
        st.progress(1.0, text=f"⚠️ {status['percentage']:.1f}% used (EXCEEDED)")
    else:
        st.progress(percentage / 100, text=f"{status['percentage']:.1f}% used")

    # Period info
    st.caption(
        f"Period: {status['period_start'].strftime('%Y-%m-%d')} to {status['period_end'].strftime('%Y-%m-%d')}"
    )


def show_all_budgets_view(budget_service: BudgetService):
    """Display all budgets in a table."""

    st.subheader("All Expense Budgets")

    try:
        budgets = budget_service.get_all_budgets()

        # Filter to only expense budgets
        expense_budgets = [
            b for b in budgets if b.category.type == TransactionType.EXPENSE
        ]

        if not expense_budgets:
            st.info("No expense budgets found. Add one to get started!")
            return

        # Prepare data for table
        budget_data = []
        for budget in expense_budgets:
            budget_data.append(
                {
                    "Category": budget.category.name,
                    "Limit (RM)": f"{budget.limit_amount:,.2f}",
                    "Period": budget.period.value.title(),
                    "Start Date": budget.start_date.strftime("%Y-%m-%d"),
                }
            )

        df = pd.DataFrame(budget_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Error loading budgets: {e}")


def add_budget_view(budget_service: BudgetService, category_service: CategoryService):
    """Form to add a new budget."""

    st.subheader("Add New Budget")
    st.info(
        "Budgets are only available for expense categories to help you track and limit spending."
    )

    # Get expense categories only
    expense_categories = category_service.get_categories(TransactionType.EXPENSE)

    if not expense_categories:
        st.warning(
            "No expense categories available. Please create expense categories first!"
        )
        return

    with st.form("add_budget_form", clear_on_submit=True):
        # Fixed to Expense only
        transaction_type = "Expense"

        category_names = [cat.name for cat in expense_categories]

        # Category selection
        category_name = st.selectbox(
            "Select Expense Category",
            options=category_names,
            help="Choose the expense category for this budget",
        )

        # Budget limit input
        limit_amount = st.number_input(
            "Budget Limit (RM)",
            min_value=0.0,
            value=500.0,
            step=50.0,
            format="%.2f",
            help="Enter the budget limit in MYR",
        )

        # Period selection
        period = st.selectbox(
            "Budget Period",
            options=["Weekly", "Monthly", "Yearly"],
            index=1,  # Default to Monthly
            help="Select how often this budget resets",
        )

        # Start date selection
        start_date = st.date_input(
            "Start Date",
            value=datetime.now().date(),
            help="Select when this budget period starts",
        )

        # Submit button
        submitted = st.form_submit_button("Add Budget")

        if submitted:
            try:
                # Convert start_date to datetime
                start_datetime = datetime.combine(start_date, datetime.min.time())

                # Add the budget
                budget_service.add_budget(
                    category_name=category_name,
                    transaction_type_input=transaction_type,
                    limit_amount=str(limit_amount),
                    period=period.lower(),
                    start_date=start_datetime,
                )

                utility.success_popup(
                    f"{period} budget of RM {limit_amount:,.2f} created for "
                    f"'{category_name}' successfully!"
                )

            except InvalidInputError as e:
                utility.error_popup(f"Invalid input: {e}")
            except AlreadyExistsError as e:
                utility.error_popup(f"{e}")
            except NotFoundError as e:
                utility.error_popup(f"{e}")
            except Exception as e:
                utility.error_popup(f"Unexpected error: {e}")


def edit_budget_view(budget_service: BudgetService, category_service: CategoryService):
    """Form to edit a budget."""

    st.subheader("Edit Budget")

    # Fixed to Expense only
    transaction_type = "Expense"

    # Get expense categories with budgets
    categories = category_service.get_categories(TransactionType.EXPENSE)

    # Filter to only categories with budgets
    categories_with_budgets = []
    for cat in categories:
        budget = budget_service.get_category_budget(cat.name, transaction_type)
        if budget:
            categories_with_budgets.append(cat)

    if not categories_with_budgets:
        st.info("No expense budgets available to edit. Add one first!")
        return

    category_names = [cat.name for cat in categories_with_budgets]

    # Select category (outside form to load current values)
    selected_category = st.selectbox(
        "Select Expense Category",
        options=category_names,
        help="Choose the expense category budget to edit",
    )

    # Get current budget
    current_budget = budget_service.get_category_budget(
        selected_category, transaction_type
    )

    # Show current values prominently before the form in 3 columns
    st.markdown(f"**Current Budget for '{selected_category}':**")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.write(f"**Limit:** RM {current_budget.limit_amount:,.2f}")
    with col2:
        st.write(f"**Period:** {current_budget.period.value.title()}")
    with col3:
        st.write(f"**Start Date:** {current_budget.start_date.strftime('%Y-%m-%d')}")

    with st.form("edit_budget_form"):

        # New limit input
        new_limit = st.number_input(
            "New Budget Limit (RM)",
            min_value=0.0,
            value=float(current_budget.limit_amount),
            step=50.0,
            format="%.2f",
            help="Enter the new budget limit in MYR",
        )

        # New period selection
        current_period_index = ["weekly", "monthly", "yearly"].index(
            current_budget.period.value
        )
        new_period = st.selectbox(
            "New Budget Period",
            options=["Weekly", "Monthly", "Yearly"],
            index=current_period_index,
            help="Select how often this budget resets",
        )

        # New start date selection
        new_start_date = st.date_input(
            "New Start Date",
            value=current_budget.start_date.date(),
            help="Select when this budget period starts",
        )

        # Submit button
        submitted = st.form_submit_button("Update Budget")

        if submitted:
            try:
                # Convert start_date to datetime
                start_datetime = datetime.combine(new_start_date, datetime.min.time())

                # Edit the budget
                budget_service.edit_budget(
                    category_name=selected_category,
                    transaction_type_input=transaction_type,
                    new_limit_amount=str(new_limit),
                    new_period=new_period.lower(),
                    new_start_date=start_datetime,
                )

                utility.success_popup(
                    f"Budget for '{selected_category}' updated successfully!"
                )

            except InvalidInputError as e:
                utility.error_popup(f"Invalid input: {e}")
            except NotFoundError as e:
                utility.error_popup(f"{e}")
            except Exception as e:
                utility.error_popup(f"Unexpected error: {e}")


def delete_budget_view(
    budget_service: BudgetService, category_service: CategoryService
):
    """Form to delete a budget."""

    st.subheader("Delete Budget")

    # Fixed to Expense only
    transaction_type = "Expense"

    # Get expense categories with budgets
    categories = category_service.get_categories(TransactionType.EXPENSE)

    # Filter to only categories with budgets
    categories_with_budgets = []
    for cat in categories:
        budget = budget_service.get_category_budget(cat.name, transaction_type)
        if budget:
            categories_with_budgets.append(cat)

    if not categories_with_budgets:
        st.info("No expense budgets available to delete.")
        return

    # Create options with budget details
    budget_options = {}
    for cat in categories_with_budgets:
        budget = budget_service.get_category_budget(cat.name, transaction_type)
        if budget:
            display_text = f"{cat.name} (RM {budget.limit_amount:,.2f} / {budget.period.value.title()})"
            budget_options[display_text] = cat.name

    with st.form("delete_budget_form"):
        # Select budget to delete
        selected_display = st.selectbox(
            "Select Expense Category Budget to Delete",
            options=list(budget_options.keys()),
            help="Warning: This will permanently delete the budget!",
        )

        # Get the actual category name from the display string
        category_name = budget_options[selected_display]

        # Confirmation checkbox
        confirm = st.checkbox(
            "I understand this action cannot be undone",
            help="Please confirm you want to delete this budget",
        )

        # Submit button
        submitted = st.form_submit_button("Delete Budget")

        if submitted:
            if not confirm:
                utility.warning_popup(
                    "Please confirm deletion by checking the checkbox above."
                )
                return

            try:
                # Delete the budget
                budget_service.delete_budget(
                    category_name=category_name, transaction_type_input=transaction_type
                )

                utility.success_popup(
                    f"Budget for '{category_name}' deleted successfully!"
                )

            except NotFoundError as e:
                utility.error_popup(f"{e}")
            except Exception as e:
                utility.error_popup(f"Unexpected error: {e}")
