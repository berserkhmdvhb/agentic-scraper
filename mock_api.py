import random
import asyncio
import logging
import argparse
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
import uvicorn

# ─── CLI Args ─────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(description="Mock API Server")
parser.add_argument("--fail-rate", type=float, default=0.05, help="Simulated failure rate (0.0–1.0)")
parser.add_argument("--port", type=int, default=8000, help="Port to run the server on")
parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind the server to")

args, _ = parser.parse_known_args()
FAIL_RATE = args.fail_rate

# ─── App Initialization ───────────────────────────────────────────────────────

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Logger Setup ─────────────────────────────────────────────────────────────

logger = logging.getLogger("mock_api")
logging.basicConfig(level=logging.INFO)

# ─── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/posts/{post_id}")
async def get_post(post_id: int):
    logger.info(f"Serving /posts/{post_id}")

    await asyncio.sleep(random.uniform(0.1, 0.5))

    if random.random() < FAIL_RATE:
        logger.warning(f"Simulated failure on /posts/{post_id}")
        raise HTTPException(status_code=500, detail="Simulated internal error")

    # Simulated LLM-style JSON as a string (to be parsed by extract_structured_data)
    content = f'''
    {{
        "title": "Post {post_id}",
        "summary": "This is a mock summary.",
        "tags": ["mock", "post", "{post_id}"]
    }}
    '''
    return HTMLResponse(content.strip(), media_type="text/plain")


@app.get("/page/{page_id}")
async def get_page(page_id: int):
    logger.info(f"Serving /page/{page_id}")

    await asyncio.sleep(random.uniform(0.05, 0.2))

    html = f"""
    <html>
        <head><title>Page {page_id}</title></head>
        <body>
            <h1>Mock Page {page_id}</h1>
            <p>{"Content " * random.randint(5, 50)}</p>
        </body>
    </html>
    """
    return HTMLResponse(html)

@app.get("/")
async def root():
    return HTMLResponse("<h1>This is a mock domain server.</h1>")



# ─── Entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("mock_api:app", host=args.host, port=args.port, reload=True)