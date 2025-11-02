# gui/start.py

import streamlit as st

from gui.config import Page, run_page
from app.utility import create_backup


def launch():
    """
    Set up the main streamlit application window and page router
    """

    # Streamlit webpage basic configuration
    st.set_page_config(
        page_title="Money Tracker", layout="wide", initial_sidebar_state="expanded"
    )

    # Initialize all session states that will be used
    init_session_state()

    # Create list of page options from the Page enum
    page_options = [page.value for page in Page]

    st.session_state.page_showing = st.sidebar.selectbox("Navigation", page_options)

    # Add backup button to sidebar
    if st.sidebar.button("Create Backup"):
        try:
            create_backup()
            st.sidebar.success("Backup created successfully!")
        except Exception as e:
            st.sidebar.error(f"Backup failed: {str(e)}")

    # Find the Page enum that matches the selected string
    page = Page(st.session_state.page_showing)

    run_page(page)


def init_session_state():
    if "page_showing" not in st.session_state:
        st.session_state.page_showing = None
