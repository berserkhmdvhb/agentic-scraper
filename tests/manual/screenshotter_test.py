from agentic_scraper.backend.scraper.screenshotter import capture_screenshot
import asyncio

async def test():
    path = await capture_screenshot("https://example.com", "screenshots")
    print("Screenshot saved to:", path)

asyncio.run(test())
