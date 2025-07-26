import streamlit as st
from auth0_component import login_button

from agentic_scraper.backend.core.settings import Settings

# Retrieve Auth0 credentials from Settings
settings = Settings()
client_id = settings.auth0_client_id
domain = settings.auth0_domain

def login_with_auth0():
    """Handles login via Auth0 and stores user info in session state."""
    user_info = login_button(client_id=client_id, domain=domain)

    # When the user logs in, store their JWT and other info
    if user_info:
        st.session_state.logged_in = True
        st.session_state.user_info = user_info  # Contains JWT token and user info
        st.experimental_rerun()  # Re-run to reflect login state
    else:
        st.session_state.logged_in = False

def display_user_info():
    """Displays the logged-in user's information."""
    if st.session_state.get("logged_in"):
        st.write(f"Welcome {st.session_state.user_info['name']}")
        st.write(f"Email: {st.session_state.user_info['email']}")
    else:
        st.write("Please log in.")

def logout():
    """Logs out the user and clears session data."""
    if st.button("Logout"):
        st.session_state.clear()  # Clear session state to log out
        st.experimental_rerun()  # Re-run to refresh the app state

# Call login function at the start of the app
login_with_auth0()

# Display user information after login
display_user_info()

# Provide an optional logout button
logout()
