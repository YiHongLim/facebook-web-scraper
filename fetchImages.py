import os
import asyncio
import requests
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials
import gspread
from playwright.async_api import async_playwright


# Helper function to download and save images

def download_image(image_url, path):
    try:
        response = requests.get(image_url, stream=True)
        if response.status_code == 200:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return True
    except Exception as e:
        print(f"Failed to download {image_url}: {e}")
    return False


async def scrape_image_url(page_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(page_url)
        await page.wait_for_load_state("networkidle")
        html = await page.content()
        await browser.close()

    soup = BeautifulSoup(html, 'html.parser')
    img_tag = soup.find('img', alt=lambda v: v and ("Product photo" in v or "Image" in v))
    if img_tag and img_tag.get('src'):
        return img_tag['src']
    return None


async def fetch_and_download_images(sheet_url, creds_path):
    # Setup client
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_url(sheet_url).sheet1

    # Get headers and data
    headers = sheet.row_values(1)
    url_col = headers.index('url') + 1
    image_col = headers.index('Image') + 1
    all_rows = sheet.get_all_values()[1:]  # Exclude header

    for i, row in enumerate(all_rows, start=2):  # row numbers start at 1, plus header
        image_cell_value = row[image_col - 1]
        fb_url = row[url_col - 1]
        print(f"Row {i}: FB URL: {fb_url}")
        if not fb_url:
            print(f"Row {i}: No URL, skipping")
            continue
        if image_cell_value.strip():
            print(f"Row {i}: Image already present, skipping")
            continue

        print(f"Row {i}: Scraping image for {fb_url}")
        image_url = await scrape_image_url(fb_url)
        if not image_url:
            print(f"Row {i}: No image URL found")
            continue

        # Download image
        filename = f"images/item_{i}.jpg"
        success = download_image(image_url, filename)

        if success:
            # Update Google Sheet cell
            sheet.update_cell(i, image_col, filename)
            print(f"Row {i}: Downloaded and updated image")
        else:
            print(f"Row {i}: Failed to download image")

sheet_url = "https://docs.google.com/spreadsheets/d/1PCJE3OE5VuTaCFxbg41Yz5H4NgLJwBWzPHvaJddLyH0/edit#gid=0"
creds_path = "evaluation-dataset-67b8dd770c30.json"

# Example usage:
asyncio.run(fetch_and_download_images(sheet_url, creds_path))
