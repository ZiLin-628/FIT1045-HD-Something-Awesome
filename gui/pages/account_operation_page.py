import pandas as pd
import streamlit as st

import gui.utility as utility
from app.currency import get_currency_list, get_currency_symbol
from app.database.base import SessionLocal
from app.exception import AlreadyExistsError, InvalidInputError, NotFoundError
from app.services.account_service import AccountService
from app.services.currency_service import CurrencyService


def show_account_operation_page():
    """Display the account operations page"""

    # Create database session
    db_session = SessionLocal()
    currency_service = CurrencyService(db_session)
    account_service = AccountService(db_session, currency_service)

    st.title("Account Management")

    # Create tabs for different operations
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "View All Accounts",
            "Add Account",
            "Edit Account Name",
            "Delete Account",
        ]
    )

    try:
        with tab1:
            show_all_accounts(account_service)

        with tab2:
            add_account_view(account_service)

        with tab3:
            edit_account_view(account_service)

        with tab4:
            delete_account_view(account_service)

    finally:
        db_session.close()


def show_all_accounts(account_service: AccountService):
    """Display all accounts in a table."""

    st.subheader("All Accounts")

    try:
        accounts = account_service.get_all_accounts()

        if not accounts:
            st.info(
                "No accounts found. Add your first account using the 'Add Account' tab!"
            )
            return

        # Convert accounts to dataframe for better display
        data = []
        for account in accounts:
            data.append(
                {
                    "Account Name": account.account_name,
                    "Balance (MYR)": f"RM {account.balance:,.2f}",
                }
            )

        df = pd.DataFrame(data)

        # Display without index column
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Show summary statistics
        st.markdown("<br>", unsafe_allow_html=True)

        total_balance = sum(account.balance for account in accounts)

        col1, col2 = st.columns(2)

        with col1:
            st.metric("Total Accounts", len(accounts))
        with col2:
            st.metric("Total Balance", f"RM {total_balance:,.2f}")

    except Exception as e:
        st.error(f"Error loading accounts: {e}")


def add_account_view(account_service: AccountService):
    """Form to add a new account."""

    st.subheader("Add New Account")

    with st.form("add_account_form", clear_on_submit=True):

        # Input fields
        account_name = st.text_input(
            "Account Name",
            help="Enter a unique name for this account",
        )

        # Currency and initial balance in columns
        col1, col2 = st.columns([1, 2])

        with col1:
            currency = st.selectbox(
                "Currency",
                options=get_currency_list(),
                index=0,  # Default to MYR
                help="Select the currency for the initial balance",
            )

        with col2:
            currency_symbol = get_currency_symbol(currency)
            initial_balance = st.number_input(
                f"Initial Balance ({currency_symbol})",
                min_value=0.0,
                step=0.01,
                format="%.2f",
                help="Enter the starting balance (will be converted to MYR)",
            )

        # Submit button
        submitted = st.form_submit_button("Add Account")

        if submitted:
            try:
                # Add the account with currency conversion
                new_account = account_service.add_account(
                    account_name=account_name,
                    initial_balance=str(initial_balance),
                    currency=currency,
                )

                # Show success message with conversion info
                success_msg = f"Account '{new_account.account_name}' created successfully with balance RM {new_account.balance:,.2f}!"

                utility.success_popup(success_msg)
                st.balloons()

            except InvalidInputError as e:
                utility.error_popup(f"Invalid input: {e}")
            except AlreadyExistsError as e:
                utility.error_popup(f"{e}")
            except Exception as e:
                utility.error_popup(f"Unexpected error: {e}")


def edit_account_view(account_service: AccountService):
    """Form to edit an account name."""

    st.subheader("Edit Account Name")

    # Get all accounts for selection
    accounts = account_service.get_all_accounts()

    if not accounts:
        st.info("No accounts available to edit. Add an account first!")
        return

    # Create a mapping of display names to account names
    account_names = [acc.account_name for acc in accounts]

    with st.form("edit_account_form"):

        # Select account to edit
        old_name = st.selectbox(
            "Select Account to Rename",
            options=account_names,
            help="Choose the account you want to rename",
        )

        # New name input
        new_name = st.text_input(
            "New Account Name",
            placeholder="Enter new name",
            help="Enter the new name for this account",
        )

        # Submit button
        submitted = st.form_submit_button("Rename Account")

        if submitted:
            try:
                # Edit the account name
                updated_account = account_service.edit_account_name(
                    old_name=old_name, new_name=new_name
                )

                utility.success_popup(
                    f"Account renamed from '{old_name}' to '{updated_account.account_name}' successfully!"
                )

            except InvalidInputError as e:
                utility.error_popup(f"❌ Invalid input: {e}")
            except NotFoundError as e:
                utility.error_popup(f"❌ {e}")
            except AlreadyExistsError as e:
                utility.error_popup(f"❌ {e}")
            except Exception as e:
                utility.error_popup(f"❌ Unexpected error: {e}")


def delete_account_view(account_service: AccountService):
    """Form to delete an account."""

    st.subheader("Delete Account")

    # Get all accounts for selection
    accounts = account_service.get_all_accounts()

    if not accounts:
        st.info("No accounts available to delete.")
        return

    # Create account selection with balance info
    account_options = {
        f"{acc.account_name} (RM {acc.balance:,.2f})": acc.account_name
        for acc in accounts
    }

    with st.form("delete_account_form"):
        # Select account to delete
        selected_display = st.selectbox(
            "Select Account to Delete",
            options=list(account_options.keys()),
            help="Warning: This will permanently delete the account and all associated transactions!",
        )

        # Confirmation checkbox
        confirm = st.checkbox(
            "I understand this action cannot be undone",
            help="Please confirm you want to delete this account",
        )

        # Submit button
        submitted = st.form_submit_button("Delete Account")

        if submitted:
            if not confirm:
                utility.warning_popup(
                    "Please confirm deletion by checking the checkbox above."
                )
                return

            try:
                # Get the actual account name from the display string
                account_name = account_options[selected_display]

                # Delete the account
                account_service.delete_account(account_name)

                utility.success_popup(
                    f"Account '{account_name}' and all associated transactions deleted successfully!"
                )

            except InvalidInputError as e:
                utility.error_popup(f"❌ Invalid input: {e}")
            except NotFoundError as e:
                utility.error_popup(f"❌ {e}")
            except Exception as e:
                utility.error_popup(f"❌ Unexpected error: {e}")
