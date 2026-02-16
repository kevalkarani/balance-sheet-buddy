"""
Simple authentication for Balance Sheet Buddy.
"""

import streamlit as st
import hashlib


def check_password():
    """
    Returns True if user has entered correct password.
    Uses session state to persist login across app reruns.
    """

    # Initialize session state
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    # If already authenticated, return True
    if st.session_state.password_correct:
        return True

    # Show login form
    st.markdown("""
    <div style='text-align: center; padding: 50px;'>
        <h1>🔐 Balance Sheet Buddy</h1>
        <h3>AI-Powered Balance Sheet Reconciliation</h3>
        <p style='color: #666;'>Please enter the password to access the application</p>
    </div>
    """, unsafe_allow_html=True)

    # Password input
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        password = st.text_input(
            "Password",
            type="password",
            key="password_input",
            placeholder="Enter password"
        )

        login_button = st.button("🔓 Login", use_container_width=True, type="primary")

        if login_button:
            # Get the correct password hash from secrets
            try:
                correct_password = st.secrets["APP_PASSWORD"]

                # Check password
                if password == correct_password:
                    st.session_state.password_correct = True
                    st.success("✅ Login successful!")
                    st.rerun()
                else:
                    st.error("❌ Incorrect password")
            except KeyError:
                st.error("⚠️ APP_PASSWORD not configured in secrets")

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; font-size: 0.9em;'>
        <p>Powered by Claude AI (Sonnet 4.5)</p>
    </div>
    """, unsafe_allow_html=True)

    return False


def show_logout_button():
    """Display logout button in sidebar."""
    with st.sidebar:
        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.password_correct = False
            st.rerun()
