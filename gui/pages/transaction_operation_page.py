from datetime import datetime
from decimal import Decimal

import pandas as pd
import streamlit as st

import gui.utility as utility
from app.currency import get_currency_list, get_currency_symbol
from app.database.base import SessionLocal
from app.database.models import TransactionType
from app.exception import InvalidInputError, NotFoundError
from app.services.account_service import AccountService
from app.services.budget_service import BudgetService
from app.services.category_service import CategoryService
from app.services.currency_service import CurrencyService
from app.services.transaction_service import TransactionService
from app.utility import format_amount


def show_transaction_operation_page():
    """Display the transaction operations page"""

    # Create database session and services
    db_session = SessionLocal()
    currency_service = CurrencyService(db_session)
    account_service = AccountService(db_session, currency_service)
    category_service = CategoryService(db_session)
    budget_service = BudgetService(db_session, category_service)
    transaction_service = TransactionService(
        db_session, account_service, category_service, currency_service
    )

    st.title("Transaction Operations")

    # Create tabs for different operations
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "Add Transaction",
            "View Transactions",
            "Edit Transaction",
            "Delete Transaction",
        ]
    )

    try:
        with tab1:
            add_transaction_view(
                transaction_service,
                account_service,
                category_service,
                budget_service,
                currency_service,
            )

        with tab2:
            view_transactions_view(
                transaction_service, account_service, category_service, currency_service
            )

        with tab3:
            edit_transaction_view(
                transaction_service, account_service, category_service
            )

        with tab4:
            delete_transaction_view(transaction_service)

    finally:
        db_session.close()


def add_transaction_view(
    transaction_service: TransactionService,
    account_service: AccountService,
    category_service: CategoryService,
    budget_service: BudgetService,
    currency_service: CurrencyService,
):
    """Tab for adding a new transaction."""

    st.header("Add New Transaction")

    # Transaction type selection (reactive to changes)
    transaction_type = st.selectbox("Transaction Type", ["Expense", "Income"])

    # Get categories based on transaction type (updates immediately when type changes)
    if transaction_type == "Expense":
        categories = category_service.get_categories(TransactionType.EXPENSE)
    else:
        categories = category_service.get_categories(TransactionType.INCOME)

    category_names = [cat.name for cat in categories] if categories else []

    # All inputs OUTSIDE form for immediate reactivity
    col1, col2 = st.columns(2)

    with col1:
        # Category selector
        category = st.selectbox(
            "Category",
            category_names if category_names else ["No categories available"],
        )

    with col2:
        # Get all accounts
        accounts = account_service.get_all_accounts()
        if accounts:
            account_names = [acc.account_name for acc in accounts]
            account_name = st.selectbox("Account", account_names)
        else:
            st.warning("No accounts available. Please create an account first!")
            account_name = None

    # Amount and Currency inputs
    col_amount, col_currency = st.columns([3, 1])
    with col_amount:
        amount = st.number_input(
            "Amount",
            min_value=0.00,
            step=0.01,
            format="%.2f",
            key="add_transaction_amount",
        )
    with col_currency:
        currency = st.selectbox(
            "Currency",
            options=get_currency_list(),
            index=0,  # Default to MYR
            help="Select the currency for this transaction",
            key="add_transaction_currency",
        )

    # Add date and time inputs
    col_date, col_time = st.columns(2)
    with col_date:
        transaction_date = st.date_input("Transaction Date", value=datetime.now())
    with col_time:
        transaction_time = st.time_input(
            "Transaction Time", value=datetime.now().time()
        )

    description = st.text_area("Description (Optional)", key="add_transaction_desc")

    # Budget warning check (BEFORE form submission - shows live as user types)
    if transaction_type == "Expense" and category and amount > 0 and currency:
        # Convert amount to MYR for budget check
        amount_in_myr = format_amount(amount)
        if currency != "MYR":
            try:
                exchange_rate = currency_service.get_exchange_rate(currency)
                amount_in_myr = format_amount(amount) * exchange_rate
            except Exception:
                pass  # If conversion fails, use original amount

        # Check budget warning
        budget_check = budget_service.check_budget_warning(
            category, transaction_type, amount_in_myr
        )

        if budget_check["has_budget"]:
            # Display budget warning with color coding
            if budget_check["warning_level"] == "exceeded":
                st.error(budget_check["message"])
                st.progress(
                    1.0,
                    text=f"Budget: RM {budget_check['limit']:,.2f} | New Total: RM {budget_check['new_spent']:,.2f}",
                )
            elif budget_check["warning_level"] == "warning":
                st.warning(budget_check["message"])
                st.progress(
                    min(budget_check["new_percentage"] / 100, 1.0),
                    text=f"Budget: RM {budget_check['limit']:,.2f} | New Total: RM {budget_check['new_spent']:,.2f}",
                )
            elif budget_check["warning_level"] == "caution":
                st.info(budget_check["message"])
                st.progress(
                    budget_check["new_percentage"] / 100,
                    text=f"Budget: RM {budget_check['limit']:,.2f} | New Total: RM {budget_check['new_spent']:,.2f}",
                )
            else:
                st.success(budget_check["message"])
                st.progress(
                    budget_check["new_percentage"] / 100,
                    text=f"Budget: RM {budget_check['limit']:,.2f} | New Total: RM {budget_check['new_spent']:,.2f}",
                )

    # Form with just the submit button
    with st.form("add_transaction_form"):
        submitted = st.form_submit_button("Add Transaction")

        if submitted:
            if not accounts:
                utility.error_popup(
                    "Cannot add transaction without an account. Please create an account first."
                )
            elif not categories:
                st.error(
                    f"Cannot add transaction without categories. Please create a {transaction_type.lower()} category first."
                )
            elif account_name is None:
                utility.error_popup("No account selected.")
            elif transaction_date is None:
                utility.error_popup("Please select a valid transaction date.")
            elif transaction_time is None:
                utility.error_popup("Please select a valid transaction time.")

            else:

                try:
                    # Combine date and time into datetime object
                    custom_datetime = datetime.combine(
                        transaction_date, transaction_time
                    )

                    transaction_service.add_transaction(
                        transaction_type_input=transaction_type,
                        category_name=category,
                        account_name=account_name,
                        amount=str(amount),
                        currency=currency,
                        description=description if description else "",
                        custom_datetime=custom_datetime,
                    )
                    utility.success_popup("Transaction added successfully!")

                except (InvalidInputError, NotFoundError) as e:
                    utility.error_popup(f"Error: {e}")


def view_transactions_view(
    transaction_service: TransactionService,
    account_service: AccountService,
    category_service: CategoryService,
    currency_service: CurrencyService,
):
    """Tab for viewing all transactions with filters."""

    st.header("All Transactions")

    transactions = transaction_service.get_all_transactions()

    if transactions:
        # Add filter options
        col1, col2, col3 = st.columns(3)

        with col1:
            filter_type = st.selectbox("Filter by Type", ["All", "Expense", "Income"])

        with col2:
            accounts = account_service.get_all_accounts()
            account_names = ["All"] + [acc.account_name for acc in accounts]
            filter_account = st.selectbox("Filter by Account", account_names)

        with col3:
            all_categories = category_service.get_all_categories()
            category_options = ["All"] + [cat.name for cat in all_categories]
            filter_category = st.selectbox("Filter by Category", category_options)

        # Apply filters
        filtered_transactions = transactions

        if filter_type != "All":
            filter_type_enum = (
                TransactionType.EXPENSE
                if filter_type == "Expense"
                else TransactionType.INCOME
            )
            filtered_transactions = [
                t
                for t in filtered_transactions
                if t.transaction_type == filter_type_enum
            ]

        if filter_account != "All":
            filtered_transactions = [
                t
                for t in filtered_transactions
                if t.account.account_name == filter_account
            ]

        if filter_category != "All":
            filtered_transactions = [
                t for t in filtered_transactions if t.category.name == filter_category
            ]

        if filtered_transactions:

            # Convert to DataFrame

            transactions_data = []
            for trans in filtered_transactions:
                # Format amount with currency
                currency_symbol = get_currency_symbol(trans.currency)
                if trans.currency != "MYR":
                    # Show original currency + locked MYR equivalent
                    amount_display = f"{currency_symbol}{trans.amount:,.2f} ({trans.currency}) = RM {trans.amount_in_myr:,.2f}"
                else:
                    amount_display = f"{currency_symbol} {trans.amount:,.2f}"

                transactions_data.append(
                    {
                        "ID": trans.id,
                        "Date": trans.datetime.strftime("%Y-%m-%d %H:%M"),
                        "Type": trans.transaction_type.value.capitalize(),
                        "Category": trans.category.name,
                        "Account": trans.account.account_name,
                        "Amount": amount_display,
                        "Description": (
                            trans.description[:30] + "..."
                            if len(trans.description) > 30
                            else trans.description
                        ),
                    }
                )

            df = pd.DataFrame(transactions_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Export button
            csv = df.to_csv(index=False).encode("utf-8")

            # Generate filename with current filters
            filter_parts = []
            if filter_type != "All":
                filter_parts.append(filter_type)
            if filter_account != "All":
                filter_parts.append(filter_account.replace(" ", "_"))
            if filter_category != "All":
                filter_parts.append(filter_category.replace(" ", "_"))

            filter_suffix = "_" + "_".join(filter_parts) if filter_parts else ""
            filename = f"transactions{filter_suffix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            st.download_button(
                label="Export to CSV",
                data=csv,
                file_name=filename,
                mime="text/csv",
                help="Download filtered transactions as CSV file",
            )

            # Show summary
            st.markdown("<br>", unsafe_allow_html=True)

            col_a, col_b, col_c = st.columns(3)

            total_transactions = len(filtered_transactions)

            # Use stored MYR amounts for accurate totals
            total_expense = Decimal("0")
            total_income = Decimal("0")

            for t in filtered_transactions:
                if t.transaction_type == TransactionType.EXPENSE:
                    total_expense += t.amount_in_myr
                else:
                    total_income += t.amount_in_myr

            col_a.metric("Total Transactions", total_transactions)
            col_b.metric("Total Expenses (MYR)", f"RM {total_expense:,.2f}")
            col_c.metric("Total Income (MYR)", f"RM {total_income:,.2f}")
        else:
            st.info("No transactions match the selected filters.")
    else:
        st.info(
            "No transactions found. Add your first transaction in the 'Add Transaction' tab!"
        )


def edit_transaction_view(
    transaction_service: TransactionService,
    account_service: AccountService,
    category_service: CategoryService,
):
    """Tab for editing an existing transaction."""

    st.header("Edit Transaction")

    transactions = transaction_service.get_all_transactions()

    if transactions:
        # Let user select transaction to edit
        transaction_options = [
            f"ID {t.id} - {t.datetime.strftime('%Y-%m-%d')} - {t.category.name} - {get_currency_symbol(t.currency)}{t.amount:,.2f}"
            for t in transactions
        ]

        selected_index = st.selectbox(
            "Select Transaction to Edit",
            options=range(len(transactions)),
            format_func=lambda i: transaction_options[i],
        )

        selected_transaction = transactions[selected_index]

        st.subheader("Current Transaction Details")

        col1, col2, col3 = st.columns(3)

        col1.write(
            f"**Type:** {selected_transaction.transaction_type.value.capitalize()}"
        )
        col2.write(f"**Category:** {selected_transaction.category.name}")
        col3.write(f"**Account:** {selected_transaction.account.account_name}")

        # Display amount with currency
        currency_symbol = get_currency_symbol(selected_transaction.currency)
        col1.write(
            f"**Amount:** {currency_symbol}{selected_transaction.amount:,.2f} ({selected_transaction.currency})"
        )

        col2.write(
            f"**Date:** {selected_transaction.datetime.strftime('%Y-%m-%d %H:%M')}"
        )
        col3.write(f"**Description:** {selected_transaction.description}")

        st.markdown("<br>", unsafe_allow_html=True)

        st.subheader("Edit Transaction")
        st.info("Leave fields empty to keep current values")

        with st.form("edit_transaction_form"):
            col1, col2 = st.columns(2)

            with col1:
                new_type = st.selectbox(
                    "New Transaction Type (optional)", options=["", "Expense", "Income"]
                )

                # Get categories based on new type if selected, otherwise current type
                type_for_categories = (
                    new_type
                    if new_type
                    else selected_transaction.transaction_type.value.capitalize()
                )
                if type_for_categories == "Expense":
                    categories = category_service.get_categories(
                        TransactionType.EXPENSE
                    )
                else:
                    categories = category_service.get_categories(TransactionType.INCOME)

                category_names = [""] + [cat.name for cat in categories]
                new_category = st.selectbox(
                    "New Category (optional)", options=category_names
                )

            with col2:
                accounts = account_service.get_all_accounts()
                account_options = [""] + [acc.account_name for acc in accounts]
                new_account = st.selectbox(
                    "New Account (optional)", options=account_options
                )

            # Amount and Currency
            col_cur, col_amt = st.columns([1, 3])

            with col_cur:
                # Display current currency (cannot be changed)
                st.text_input(
                    "Currency",
                    value=selected_transaction.currency,
                    disabled=True,
                    help="Currency cannot be changed after transaction is created",
                )

            with col_amt:
                new_amount = st.text_input(
                    "New Amount (optional)",
                    placeholder=f"Current: {selected_transaction.amount}",
                )

            new_description = st.text_area(
                "New Description",
                placeholder="Leave empty to keep current description",
            )

            col_date1, col_date2 = st.columns(2)
            with col_date1:
                new_date = st.date_input(
                    "Transaction Date",
                    value=selected_transaction.datetime.date(),
                    help="Update the date for this transaction",
                )

            with col_date2:
                new_time = st.time_input(
                    "Transaction Time",
                    value=selected_transaction.datetime.time(),
                    help="Update the time for this transaction",
                )

            submitted = st.form_submit_button("Update Transaction")

            if submitted:
                try:
                    # Combine date and time into a datetime object
                    custom_datetime = datetime.combine(new_date, new_time)

                    updated_transaction = transaction_service.edit_transaction(
                        transaction_id=selected_transaction.id,
                        transaction_type_input=new_type,
                        category_name=new_category,
                        account_name=new_account,
                        amount=new_amount,
                        description=new_description,
                        custom_datetime=custom_datetime,
                    )
                    utility.success_popup(
                        f"Transaction ID {updated_transaction.id} updated successfully!"
                    )

                except (InvalidInputError, NotFoundError, ValueError) as e:
                    utility.error_popup(f"Error: {e}")
    else:
        st.info("No transactions available to edit.")


def delete_transaction_view(transaction_service: TransactionService):
    """Tab for deleting a transaction."""

    st.header("Delete Transaction")

    transactions = transaction_service.get_all_transactions()

    if transactions:

        # Let user select transaction to delete
        transaction_options = [
            f"ID {t.id} - {t.datetime.strftime('%Y-%m-%d')} - {t.category.name} - {get_currency_symbol(t.currency)}{t.amount:,.2f}"
            for t in transactions
        ]
        selected_index = st.selectbox(
            "Select Transaction to Delete",
            range(len(transactions)),
            format_func=lambda i: transaction_options[i],
            key="delete_select",
        )

        selected_transaction = transactions[selected_index]

        st.divider()

        st.subheader("Transaction Details")

        col1, col2, col3 = st.columns(3)

        col1.write(f"**ID:** {selected_transaction.id}")
        col2.write(
            f"**Date:** {selected_transaction.datetime.strftime('%Y-%m-%d %H:%M')}"
        )
        col3.write(
            f"**Type:** {selected_transaction.transaction_type.value.capitalize()}"
        )

        col1.write(f"**Category:** {selected_transaction.category.name}")
        col2.write(f"**Account:** {selected_transaction.account.account_name}")

        # Display amount with currency
        currency_symbol = get_currency_symbol(selected_transaction.currency)
        col3.write(
            f"**Amount:** {currency_symbol}{selected_transaction.amount:,.2f} ({selected_transaction.currency})"
        )

        if selected_transaction.description:
            st.write(f"**Description:** {selected_transaction.description}")

        with st.form("delete_transaction_form"):
            confirm = st.checkbox("I confirm that I want to delete this transaction")
            submitted = st.form_submit_button("Delete Transaction")

            if submitted:
                if not confirm:
                    utility.error_popup(
                        "Please confirm the deletion by checking the box."
                    )
                else:
                    try:
                        transaction_service.delete_transaction(selected_transaction.id)
                        utility.success_popup(
                            f"Transaction ID {selected_transaction.id} deleted successfully!"
                        )
                        st.rerun()
                    except NotFoundError as e:
                        utility.error_popup(f"Error: {e}")
    else:
        st.info("No transactions available to delete.")
