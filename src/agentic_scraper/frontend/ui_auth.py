import httpx
import streamlit as st
from auth0_component import get_jwt_token, login_button, logout_button
from fastapi import status
from jose.exceptions import JWTError  # Importing JWTError for specific exception handling

from agentic_scraper.backend.api.auth.auth0_helpers import verify_jwt  # Backend JWT verification
from agentic_scraper.backend.scraper.models import OpenAIConfig  # Ensure OpenAIConfig is imported


def authenticate_user() -> None:
    """Authenticate user using Auth0 and store JWT token in session_state."""
    jwt_token = get_jwt_token()
    if jwt_token:
        try:
            # Verify the JWT token's signature and validity using backend logic
            decoded_token = verify_jwt(jwt_token)  # Verifying the JWT
            st.session_state["jwt_token"] = jwt_token
            st.session_state["user_info"] = decoded_token  # Store user info

            # Now fetch OpenAI credentials
            fetch_openai_credentials()  # We will create this function to fetch credentials

            st.success("Logged in successfully!")
        except JWTError as e:
            # Specifically catching JWTError during JWT validation
            st.error(f"JWT verification failed: {e!s}")
        except ValueError as e:
            # Catch ValueError exceptions if they occur (e.g., incorrect values in the JWT)
            st.error(f"A value error occurred: {e!s}")
        except RuntimeError as e:
            # Catch any runtime errors
            st.error(f"A runtime error occurred: {e!s}")
        except Exception as e:
            # Catch any other general exceptions
            st.error(f"An unexpected error occurred: {e!s}")
            raise  # Re-raise the error to avoid silent failure
    else:
        st.error("Login failed!")


def logout_user() -> None:
    """Log the user out and clear the session."""
    logout_button()
    if "jwt_token" in st.session_state:
        del st.session_state["jwt_token"]
    if "user_info" in st.session_state:
        del st.session_state["user_info"]
    if "openai_credentials" in st.session_state:
        del st.session_state["openai_credentials"]  # Clear OpenAI credentials on logout
    st.success("Logged out successfully!")
    # Refresh the page to clear state
    st.experimental_rerun()  # type: ignore[attr-defined]


def fetch_openai_credentials() -> None:
    """Fetch OpenAI credentials from the backend and store them in session_state."""
    if "jwt_token" not in st.session_state:
        st.error("User is not authenticated!")
        return

    headers = {"Authorization": f"Bearer {st.session_state['jwt_token']}"}

    try:
        # Make the API request to get OpenAI credentials (blocking request using httpx.Client)
        with httpx.Client() as client:
            # Backend endpoint to fetch OpenAI credentials
            response = client.get(
                # Replace with actual backend URL
                "https://bb348695cff1.ngrok-free.app/api/v1/user/openai-credentials",  
                headers=headers,
            )

            if response.status_code == status.HTTP_200_OK:
                openai_credentials = response.json()

                # Create an OpenAIConfig instance and store in session_state
                openai_config = OpenAIConfig(
                    api_key=openai_credentials.get("api_key"),
                    project_id=openai_credentials.get("project_id"),
                )
                st.session_state["openai_credentials"] = (
                    openai_config  # Store OpenAI credentials as OpenAIConfig in session state
                )

                st.success("OpenAI credentials retrieved successfully!")
            else:
                st.error(f"Failed to fetch OpenAI credentials: {response.text}")

    except httpx.HTTPStatusError as e:
        st.error(f"HTTP error occurred: {e!s}")
    except httpx.RequestError as e:
        st.error(f"Request error occurred: {e!s}")
    except ValueError as e:
        st.error(f"Value error occurred while parsing response: {e!s}")
    except RuntimeError as e:
        st.error(f"Runtime error occurred: {e!s}")
    except KeyError as e:
        st.error(f"Missing expected key in the response: {e!s}")
    except TypeError as e:
        st.error(f"Type error occurred: {e!s}")


def login_ui() -> None:
    """Displays login or logout button based on authentication state."""
    if "jwt_token" not in st.session_state:
        login_button()  # Will redirect the user to Auth0's login page
    else:
        # Display user information from the JWT token
        user_info = st.session_state["user_info"]
        st.write(f"Welcome, {user_info['name']}")
        st.write(f"Email: {user_info['email']}")
        logout_button()  # Logs out the user
