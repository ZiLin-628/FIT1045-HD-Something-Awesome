# gui/pages/goals_page.py

"""Financial Goals page for tracking savings goals."""

from datetime import datetime, date

import streamlit as st

import gui.utility as utility
from app.database.base import SessionLocal
from app.database.models import Goal
from app.exception import InvalidInputError, NotFoundError
from app.services.account_service import AccountService
from app.services.currency_service import CurrencyService
from app.services.goal_service import GoalService


def show_goals_page():
    """Display the financial goals page."""

    st.title("Goals")

    # Create database session and services
    db_session = SessionLocal()
    currency_service = CurrencyService(db_session)
    account_service = AccountService(db_session, currency_service)
    goal_service = GoalService(db_session, account_service)

    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs(
        ["Add Goal", "View Goals", "Edit Goal", "Delete Goal"]
    )

    try:
        with tab1:
            add_goal_view(goal_service, account_service)

        with tab2:
            view_goals_view(goal_service)

        with tab3:
            edit_goal_view(goal_service)

        with tab4:
            delete_goal_view(goal_service)

    finally:
        db_session.close()


def add_goal_view(goal_service: GoalService, account_service: AccountService):
    """Tab for adding a new goal."""

    st.header("Create New Goal")

    # Goal name
    name = st.text_input(
        "Goal Name",
        help="Give your goal a descriptive name",
    )

    # Target amount
    col1, col2 = st.columns([2, 1])
    with col1:
        target_amount = st.number_input(
            "Target Amount (RM)",
            min_value=0.01,
            step=100.0,
            format="%.2f",
            help="How much do you want to save?",
        )

    with col2:
        # Display in nice format
        if target_amount > 0:
            st.metric("Target", f"RM {target_amount:,.2f}")

    # Deadline
    deadline = st.date_input(
        "Deadline",
        min_value=date.today(),
        value=date.today(),
        help="When do you want to achieve this goal?",
    )

    # Optional: Link to account
    accounts = account_service.get_all_accounts()
    account_options = ["All Accounts (Track Total Balance)"] + [
        acc.account_name for acc in accounts
    ]
    account_selection = st.selectbox(
        "Track Progress From",
        account_options,
        help="Link to a specific account, or track total balance",
    )

    # Description
    description = st.text_area(
        "Description (Optional)",
        placeholder="Add notes about this goal...",
        height=100,
    )

    # Submit button
    if st.button("Create Goal"):
        if not name or not name.strip():
            utility.error_popup("Please enter a goal name")

        elif target_amount <= 0:
            utility.error_popup("Target amount must be greater than 0")

        elif deadline <= date.today():
            utility.error_popup("Deadline must be in the future")

        else:
            try:
                # Determine account name
                account_name = None
                if account_selection != "All Accounts (Track Total Balance)":
                    account_name = account_selection

                # Create goal
                goal_service.add_goal(
                    name=name,
                    target_amount=str(target_amount),
                    deadline=deadline,
                    account_name=account_name,
                    description=description,
                )

                utility.success_popup(f"Goal '{name}' created successfully!")

            except (InvalidInputError, NotFoundError) as e:
                utility.error_popup(f"Error: {e}")


def view_goals_view(goal_service: GoalService):
    """Tab for viewing all goals with progress."""

    st.header("Your Goals")

    goals = goal_service.get_all_goals()

    if not goals:
        st.info("No goals yet. Create your first goal to start tracking progress!")
        return

    # Separate active and completed
    active_goals = [g for g in goals if not g.is_completed]
    completed_goals = [g for g in goals if g.is_completed]

    # Show summary stats
    if active_goals:
        summary = goal_service.get_goals_summary()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Active Goals", summary["active_goals"])
        with col2:
            st.metric("Total Target", f"RM {summary['total_target']:,.2f}")
        with col3:
            st.metric("Total Progress", f"RM {summary['total_progress']:,.2f}")
        with col4:
            st.metric("Avg Progress", f"{summary['average_progress_pct']:.1f}%")

        st.divider()

    # Display active goals
    if active_goals:
        st.subheader("Active Goals")

        for goal in active_goals:
            display_goal_card(goal, goal_service)

    # Display completed goals
    if completed_goals:
        st.divider()
        st.subheader("Completed Goals")

        for goal in completed_goals:
            display_goal_card(goal, goal_service, is_completed=True)


def display_goal_card(goal: Goal, goal_service: GoalService, is_completed=False):
    """Display a single goal card with progress."""

    progress = goal_service.calculate_goal_progress(goal)

    with st.container(border=True):
        # Header
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"### {goal.name}")
        with col2:
            if not is_completed and progress["status"] != "completed":
                if st.button("✓ Complete", key=f"complete_{goal.id}", type="secondary"):
                    try:
                        goal_service.mark_goal_completed(goal.id)
                        utility.success_popup(
                            f"Goal '{goal.name}' marked as completed!"
                        )
                    except Exception as e:
                        utility.error_popup(f"Error: {e}")

        # Progress bar
        progress_val = max(0.0, min(progress["progress_pct"] / 100, 1.0))
        st.progress(
            progress_val,
            text=f"{progress['progress_pct']:.1f}% Complete",
        )

        # Stats
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "Current (Net)",
                f"RM {progress['progress_amount']:,.2f}",
            )
        with col2:
            st.metric(
                "Target",
                f"RM {progress['target_amount']:,.2f}",
            )
        with col3:
            st.metric(
                "Remaining",
                f"RM {progress['remaining_amount']:,.2f}",
            )
        with col4:
            st.metric(
                "Income",
                f"RM {progress.get('total_income', 0):,.2f}",
                delta=f"-RM {progress.get('total_expenses', 0):,.2f}",
                delta_color="inverse",
            )

        # Timeline
        col1, col2, col3 = st.columns(3)
        with col1:
            st.caption(f"**Deadline:** {progress['deadline']}")
        with col2:
            st.caption(f"**Days Remaining:** {progress['days_remaining']}")
        with col3:
            st.caption(f"**Track From:** {progress['account_name']}")

        # Recommendations (if not completed)
        if not is_completed and progress["status"] not in ["completed", "achieved"]:

            # Status message
            if progress["status"] == "on_track":
                st.success("**Status:** On track! Keep up the great work!")
            elif progress["status"] == "behind":
                st.warning(
                    f"**Status:** Behind schedule You're {progress['expected_progress_pct'] - progress['progress_pct']:.1f}% below expected progress"
                )
            elif progress["status"] == "overdue":
                st.error("**Status:** Deadline passed Consider extending the deadline")

            # Savings recommendations
            if progress["days_remaining"] > 0:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.info(f"**Save Daily**\n\nRM {progress['daily_needed']:.2f}/day")
                with col2:
                    st.info(
                        f"**Save Weekly**\n\nRM {progress['weekly_needed']:.2f}/week"
                    )
                with col3:
                    st.info(
                        f"**Save Monthly**\n\nRM {progress['monthly_needed']:.2f}/month"
                    )

        # Description
        if goal.description:
            with st.expander("Description"):
                st.write(goal.description)


def edit_goal_view(goal_service: GoalService):
    """Tab for editing an existing goal."""

    st.header("Edit Goal")

    goals = goal_service.get_active_goals()

    if not goals:
        st.info("No active goals to edit")
        return

    # Select goal
    goal_names = [f"{g.name} (Target: RM {g.target_amount:,.2f})" for g in goals]
    selected_index = st.selectbox(
        "Select Goal to Edit",
        range(len(goal_names)),
        format_func=lambda x: goal_names[x],
    )

    if selected_index is not None:
        goal = goals[selected_index]

        # Edit form
        name = st.text_input("Goal Name", value=goal.name)

        target_amount = st.number_input(
            "Target Amount (RM)",
            min_value=0.01,
            value=float(goal.target_amount),
            step=100.0,
            format="%.2f",
        )

        current_deadline = (
            goal.deadline.date()
            if isinstance(goal.deadline, datetime)
            else goal.deadline
        )
        deadline = st.date_input(
            "Deadline",
            min_value=date.today(),
            value=current_deadline,
        )

        description = st.text_area(
            "Description (Optional)",
            value=goal.description or "",
            height=100,
        )

        # Submit button
        if st.button("Save Changes"):
            try:
                goal_service.edit_goal(
                    goal_id=goal.id,
                    name=name,
                    target_amount=str(target_amount),
                    deadline=deadline,
                    description=description,
                )

                utility.success_popup("Goal updated successfully!")


            except (InvalidInputError, NotFoundError) as e:
                utility.error_popup(f"Error: {e}")


def delete_goal_view(goal_service: GoalService):
    """Tab for deleting a goal."""

    st.header("Delete Goal")

    goals = goal_service.get_all_goals()

    if not goals:
        st.info("No goals to delete")
        return

    # Select goal
    goal_names = [
        f"{g.name} (Target: RM {g.target_amount:,.2f}, Status: {'Completed' if g.is_completed else 'Active'})"
        for g in goals
    ]
    selected_index = st.selectbox(
        "Select Goal to Delete",
        range(len(goal_names)),
        format_func=lambda x: goal_names[x],
    )

    if selected_index is not None:
        goal = goals[selected_index]

        st.error(
            "**Warning:** This action cannot be undone. The goal and its progress history will be permanently deleted."
        )

        # Confirmation checkbox
        confirm = st.checkbox(
            "I understand this action cannot be undone",
            help="Please confirm you want to delete this goal",
        )

        # Delete button
        if st.button("Delete Goal"):
            if not confirm:
                utility.warning_popup(
                    "Please confirm deletion by checking the checkbox above."
                )
                return

            try:
                goal_service.delete_goal(goal.id)
                utility.success_popup(f"Goal '{goal.name}' deleted successfully")


            except NotFoundError as e:
                utility.error_popup(f"Error: {e}")
