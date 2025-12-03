import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import json

async def scrape_marketplace_item(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # False shows browser
        context = await browser.new_context()

        # Optional: load cookies for logged-in access
        try:
            with open("fb_cookies.json", "r") as f:
                cookies = json.load(f)
                await context.add_cookies(cookies)
        except FileNotFoundError:
            print("Cookies not found, continuing without login")

        page = await context.new_page()
        await page.goto(url)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(5)

        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")

        # --- Extract item fields ---
        title_tag = soup.find("h1", attrs={"aria-hidden": "false"})
        title = title_tag.get_text(strip=True) if title_tag else "N/A"

        price_tag = soup.find("span", string=lambda x: x and "$" in x)
        price = price_tag.get_text(strip=True) if price_tag else "N/A"

        possible_conditions = ["Used", "New", "Fair", "Like New", "Good", "Excellent"]
        condition = "N/A"
        for cond in possible_conditions:
            if soup.find("span", string=lambda x: x and cond in x):
                condition = cond
                break

        spans = soup.find_all("span")
        texts = [s.get_text(strip=True) for s in spans if len(s.get_text(strip=True)) > 30]
        description = next((t for t in texts if "$" not in t and t != title), "N/A")

        img_tag = soup.find("img", alt=lambda v: v and ("Product photo" in v or "Image" in v))
        image_url = img_tag["src"] if img_tag else "N/A"

        await browser.close()

        return {
            "title": title,
            "price": price,
            "condition": condition,
            "description": description,
            "image_url": image_url,
            "url": url
        }

# Quick test run
async def main():
    url = "https://www.facebook.com/marketplace/item/1311813240949671"
    data = await scrape_marketplace_item(url)
    print(json.dumps(data, indent=4))

asyncio.run(main())
