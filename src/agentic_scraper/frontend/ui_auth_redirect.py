import streamlit as st
import streamlit.components.v1 as components

from agentic_scraper.backend.core.settings import get_settings


def render_auth_redirect_handler() -> None:
    """
    Render a dynamic redirect handler page that extracts the token from
    the fragment (#access_token=...) and redirects the user to the main app
    with it passed as a query string (?access_token=...), which Streamlit can read.
    """
    settings = get_settings()
    domain = settings.frontend_domain.strip().rstrip("/")

    # Ensure domain has a scheme
    if not domain.startswith("http://") and not domain.startswith("https://"):
        domain = "https://" + domain

    # Template with JS that pulls the access token and redirects to Streamlit with it
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <title>Redirecting...</title>
      <script>
        window.onload = function () {{
          const hash = window.location.hash.substring(1);
          const params = new URLSearchParams(hash);
          const token = params.get("access_token");

          if (token) {{
            const redirectUrl = "{domain}/?access_token=" + token;
            window.location.replace(redirectUrl);
          }} else {{
            document.body.innerHTML = "<h3>Login failed: Token not found in redirect.</h3>";
          }}
        }};
      </script>
    </head>
    <body>
      <h3>Redirecting...</h3>
    </body>
    </html>
    """

    # Replace double braces for valid JS in f-string
    html = html_template.replace("{{", "{").replace("}}", "}")
    # Do NOT use unsafe_allow_html here — it's not valid for components.html
    components.html(html, height=300)
