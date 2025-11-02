import pandas as pd
import streamlit as st

import gui.utility as utility
from app.database.base import SessionLocal
from app.database.models import TransactionType
from app.exception import (
    AlreadyExistsError,
    CategoryInUseError,
    InvalidInputError,
    NotFoundError,
)
from app.services.category_service import CategoryService


def show_category_operation_page():
    """Display the category operations page"""

    # Create database session
    db_session = SessionLocal()
    category_service = CategoryService(db_session)

    st.title("Category Management")

    # Create tabs for different operations
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "View All Categories",
            "Add Category",
            "Edit Category",
            "Delete Category",
        ]
    )

    try:
        with tab1:
            show_all_categories(category_service)

        with tab2:
            add_category_view(category_service)

        with tab3:
            edit_category_view(category_service)

        with tab4:
            delete_category_view(category_service)

    finally:
        db_session.close()


def show_all_categories(category_service: CategoryService):
    """Display all categories grouped by type."""

    st.subheader("All Categories")

    try:
        # Get categories by type
        income_categories = category_service.get_categories(TransactionType.INCOME)
        expense_categories = category_service.get_categories(TransactionType.EXPENSE)

        # Create two columns for income and expense
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### Income Categories")
            if not income_categories:
                st.info("No income categories found.")

            else:
                income_data = [{"Category": cat.name} for cat in income_categories]
                df_income = pd.DataFrame(income_data)
                st.dataframe(df_income, use_container_width=True, hide_index=True)

        with col2:
            st.markdown("### Expense Categories")
            if not expense_categories:
                st.info("No expense categories found.")

            else:
                expense_data = [{"Category": cat.name} for cat in expense_categories]
                df_expense = pd.DataFrame(expense_data)
                st.dataframe(df_expense, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Error loading categories: {e}")


def add_category_view(category_service: CategoryService):
    """Form to add a new category."""

    st.subheader("Add New Category")

    with st.form("add_category_form", clear_on_submit=True):

        # Transaction type selection
        transaction_type = st.selectbox(
            "Category Type",
            options=["Income", "Expense"],
            help="Select whether this is an income or expense category",
        )

        # Category name input
        category_name = st.text_input(
            "Category Name",
            help="Enter a unique name for this category",
        )

        # Submit button
        submitted = st.form_submit_button("Add Category")

        if submitted:
            try:

                # Add the category
                new_category = category_service.add_category(
                    category=category_name, transaction_type_input=transaction_type
                )

                utility.success_popup(
                    f"{transaction_type} category '{new_category.name}' created successfully!"
                )
                st.balloons()

            except InvalidInputError as e:
                utility.error_popup(f"Invalid input: {e}")
            except AlreadyExistsError as e:
                utility.error_popup(f"{e}")
            except Exception as e:
                utility.error_popup(f"Unexpected error: {e}")


def edit_category_view(category_service: CategoryService):
    """Form to edit a category name."""

    st.subheader("Edit Category Name")

    # Transaction type selection (outside form for dynamic filtering)
    transaction_type = st.selectbox(
        "Select Category Type to Edit",
        options=["Income", "Expense"],
        help="Choose the type of category you want to edit",
    )

    # Get categories for selected type
    type_enum = (
        TransactionType.INCOME
        if transaction_type == "Income"
        else TransactionType.EXPENSE
    )
    categories = category_service.get_categories(type_enum)

    if not categories:
        st.info(
            f"No {transaction_type.lower()} categories available to edit. Add one first!"
        )
        return

    # Create a list of category names
    category_names = [cat.name for cat in categories]

    with st.form("edit_category_form"):

        # Select category to edit
        old_name = st.selectbox(
            f"Select {transaction_type} Category to Rename",
            options=category_names,
            help="Choose the category you want to rename",
        )

        # New name input
        new_name = st.text_input(
            "New Category Name",
            help="Enter the new name for this category",
        )

        # Submit button
        submitted = st.form_submit_button("Rename Category")

        if submitted:
            try:

                # Edit the category name
                updated_category = category_service.edit_category(
                    old_category_input=old_name,
                    new_category_input=new_name,
                    transaction_type_input=transaction_type,
                )

                utility.success_popup(
                    f"Category renamed from '{old_name}' to '{updated_category.name}' successfully!"
                )

            except InvalidInputError as e:
                utility.error_popup(f"Invalid input: {e}")
            except NotFoundError as e:
                utility.error_popup(f"{e}")
            except AlreadyExistsError as e:
                utility.error_popup(f"{e}")
            except Exception as e:
                utility.error_popup(f"Unexpected error: {e}")


def delete_category_view(category_service: CategoryService):
    """Form to delete a category."""

    st.subheader("Delete Category")

    # Transaction type selection (outside form for dynamic filtering)
    transaction_type = st.selectbox(
        "Select Category Type to Delete",
        options=["Income", "Expense"],
        help="Choose the type of category you want to delete",
    )

    # Get categories for selected type
    type_enum = (
        TransactionType.INCOME
        if transaction_type == "Income"
        else TransactionType.EXPENSE
    )
    categories = category_service.get_categories(type_enum)

    if not categories:
        st.info(f"No {transaction_type.lower()} categories available to delete.")
        return

    # Create a list of category names
    category_names = [cat.name for cat in categories]

    with st.form("delete_category_form"):

        # Select category to delete
        category_name = st.selectbox(
            f"Select {transaction_type} Category to Delete",
            options=category_names,
            help="Warning: Category can only be deleted if not used in any transactions!",
        )

        # Confirmation checkbox
        confirm = st.checkbox(
            "I understand this action cannot be undone",
            help="Please confirm you want to delete this category",
        )

        # Warning message
        st.warning("**Warning:** Categories in use by transactions cannot be deleted.")

        # Submit button
        submitted = st.form_submit_button("Delete Category")

        if submitted:
            if not confirm:
                
                utility.warning_popup("Please confirm deletion by checking the checkbox above.")
                

            try:
                # Delete the category
                category_service.delete_category(
                    category_name=category_name, transaction_type_input=transaction_type
                )

                utility.success_popup(
                    f"{transaction_type} category '{category_name}' deleted successfully!"
                )

                # Rerun to refresh the view
                st.rerun()

            except InvalidInputError as e:
                utility.error_popup(f"Invalid input: {e}")
            except NotFoundError as e:
                utility.error_popup(f"{e}")
            except CategoryInUseError as e:
                utility.error_popup(f"{e}")
            except Exception as e:
                utility.error_popup(f"Unexpected error: {e}")
