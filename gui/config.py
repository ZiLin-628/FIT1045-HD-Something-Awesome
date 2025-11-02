# gui/config.py

from enum import Enum

from gui.pages.account_operation_page import show_account_operation_page
from gui.pages.budget_operation_page import show_budget_operation_page
from gui.pages.category_operation import show_category_operation_page
from gui.pages.dashboard_page import show_dashboard_page
from gui.pages.goals_page import show_goals_page
from gui.pages.invalid_page import show_invalid_page
from gui.pages.summary_page import show_summary_page
from gui.pages.transaction_operation_page import show_transaction_operation_page


class Page(Enum):
    """Enum of all page available for CareLog system"""

    DASHBOARD = "Dashboard"
    ACCOUNT_OPERATION_PAGE = "Accounts"
    CATEGORY_OPERATION_PAGE = "Categories"
    BUDGET_OPERATION_PAGE = "Budgets"
    GOALS_PAGE = "Goals"
    TRANSACTION_OPERATION_PAGE = "Transactions"
    SUMMARY_PAGE = "Summary"
    # INVALID_PAGE = "Invalid Page"


PAGE_ROUTER: dict = {
    Page.DASHBOARD: show_dashboard_page,
    Page.ACCOUNT_OPERATION_PAGE: show_account_operation_page,
    Page.CATEGORY_OPERATION_PAGE: show_category_operation_page,
    Page.BUDGET_OPERATION_PAGE: show_budget_operation_page,
    Page.GOALS_PAGE: show_goals_page,
    Page.TRANSACTION_OPERATION_PAGE: show_transaction_operation_page,
    Page.SUMMARY_PAGE: show_summary_page,
}


def run_page(page: Page):
    """
    Render the page based on the page selected. Obtain the render function from PAGE_ROUTER and render it

    Args:
        page (Page): The page selected
        hospital_manager (HospitalManager): A manager object which stores all the information of the hospital
    """
    func = PAGE_ROUTER.get(page, show_invalid_page)
    func()
