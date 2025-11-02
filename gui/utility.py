# gui/utility.py

import streamlit as st
import time


@st.dialog("Message")
def success_popup(message: str):
    st.success(message)

    if st.button("Okay"):
        st.rerun()

    time.sleep(1.5)
    st.rerun()


@st.dialog("Message")
def error_popup(message: str):
    st.error(message)

    if st.button("Okay"):
        st.rerun()

    time.sleep(1.5)
    st.rerun()


@st.dialog("Message")
def warning_popup(message: str):
    st.warning(message)

    if st.button("Okay"):
        st.rerun()

    time.sleep(1.5)
    st.rerun()
