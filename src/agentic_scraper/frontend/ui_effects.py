import streamlit as st


def render_login_highlight() -> None:
    """
    Render CSS overlay and arrow to highlight login button if required.
    """
    st.markdown(
        """
        <style>
        /* Dim background */
        .block-container:before {
            content: "";
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: rgba(0, 0, 0, 0.4);
            z-index: 9998;
        }

        /* Glow animation on login button */
        .auth-highlight button {
            animation: pulse 1.5s infinite;
            border: 2px solid #EF476F !important;
            box-shadow: 0 0 10px #EF476F !important;
            z-index: 9999;
            position: relative;
        }

        @keyframes pulse {
            0% { box-shadow: 0 0 10px #EF476F; }
            50% { box-shadow: 0 0 20px #FF6B81; }
            100% { box-shadow: 0 0 10px #EF476F; }
        }

        /* Bouncing arrow */
        .login-arrow {
            position: fixed;
            top: 180px;  /* Adjust if needed */
            left: 10px;
            z-index: 10000;
            font-size: 2rem;
            animation: bounce 1s infinite;
            color: #EF476F;
        }

        @keyframes bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-8px); }
        }
        </style>

        <div class="login-arrow">⬅️</div>
        """,
        unsafe_allow_html=True,
    )
