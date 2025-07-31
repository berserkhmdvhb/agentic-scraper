from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from agentic_scraper.backend.core.settings import get_settings

router = APIRouter(include_in_schema=False)
settings = get_settings()


@router.get("/auth/redirect", response_class=HTMLResponse)
async def oauth_redirect():
    """
    Serve a dynamic HTML+JS page that extracts the access_token from the URL fragment
    and redirects to the Streamlit frontend with the token in query params.
    """
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <title>Redirecting...</title>
      <script>
        const hash = window.location.hash.substring(1);
        const params = new URLSearchParams(hash);
        const token = params.get("access_token");

        if (token) {{
          const redirectUrl = "https://{settings.frontend_domain}/?access_token=" + token;
          window.location.href = redirectUrl;
        }} else {{
          document.body.innerHTML = "<h3>Login failed: Token not found in redirect.</h3>";
        }}
      </script>
    </head>
    <body>
      <h3>Redirecting...</h3>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
