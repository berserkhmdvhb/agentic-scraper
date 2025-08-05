import streamlit as st


def render_login_highlight() -> None:
    """
    Render a dim overlay and animated arrow that shifts position depending on sidebar state.
    """
    st.markdown(
        """
        <style>
        /* Overlay to dim entire screen */
        .login-overlay {
            position: fixed;
            top: 0; left: 0;
            width: 100vw; height: 100vh;
            background: rgba(0, 0, 0, 0.4);
            z-index: 9998;
        }

        /* Highlight login button */
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

        /* Arrow that adjusts position via custom property */
        .login-arrow {
            position: fixed;
            top: 180px;
            left: var(--arrow-left, 10px);
            z-index: 2147483647;
            font-size: 2rem;
            animation: bounce 1s infinite;
            color: #EF476F;
            transition: left 0.4s ease;
        }

        @keyframes bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-8px); }
        }
        </style>

        <script>
        // Use ResizeObserver to detect sidebar visibility
        setTimeout(() => {
            const arrow = document.querySelector('.login-arrow');
            const sidebar = document.querySelector('[data-testid="stSidebar"]');
            if (arrow && sidebar) {
                const observer = new ResizeObserver(() => {
                    const isVisible = window.getComputedStyle(sidebar).width !== '0px';
                    arrow.style.setProperty('--arrow-left', isVisible ? '260px' : '10px');
                });
                observer.observe(sidebar);
            }
        }, 500);
        </script>

        <div class="login-overlay"></div>
        <div class="login-arrow">⬅️</div>
        """,
        unsafe_allow_html=True,
    )
