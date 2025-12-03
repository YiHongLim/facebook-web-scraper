from google.oauth2.service_account import Credentials
import gspread
from playwright.async_api import async_playwright
import json
import asyncio
from bs4 import BeautifulSoup
import requests
import os

HEADERS = ['Id', 'Category', 'Rank', 'Title', 'Condition', 'Description',
           'Image', 'Price', 'AI Price', 'AI Description', 'url']

def get_existing_urls(sheet, url_column_name="url"):
    records = sheet.get_all_records()
    # Use .strip().lower() for robust comparison
    return {str(record[url_column_name]).strip().lower() for record in records if url_column_name in record}

def download_image(image_url, path):
    """Download image from URL and save to local path"""
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

def save_to_google_sheet(items, sheet_url, creds_path):
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_url(sheet_url).sheet1

    existing_urls = get_existing_urls(sheet, url_column_name="url")
    next_id = len(sheet.get_all_values())

    for item in items:
        url_key = str(item.get("url", "")).strip().lower()
        if url_key in existing_urls:
            print(f"Already present, skipping: {item['url']}")
            continue
        existing_urls.add(url_key)
        
        # Use local filename if image was downloaded, otherwise use URL
        image_value = item.get("image_filename", item.get("image_url", ""))
        
        row = [
            next_id,
            item.get("category", ""),
            item.get("rank", ""), # Or idx+1, or manual rank
            item.get("title", ""),
            item.get("condition", ""),
            item.get("description", ""),
            image_value,
            item.get("price", ""),
            "",
            item.get("url", "")
        ]
        sheet.append_row(row)
        next_id += 1
    print("All items saved to Google Sheet (without AI Price).")

async def scrape_marketplace_items(url, category, download_images=True):
    items = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        try:
            with open("fb_cookies.json", "r") as f:
                cookies = json.load(f)
                await context.add_cookies(cookies)
        except FileNotFoundError:
            print("No cookies found - log in manually in this run")
        page = await context.new_page()
        print(f"Navigating to {url}")
        await page.goto(url)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(5)
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("h1", attrs={"aria-hidden": "false"})
        title = title_tag.get_text(strip=True) if title_tag else "N/A"
        price_tag = soup.find("span", string=lambda x: x and "$" in x)
        price = price_tag.get_text(strip = True).replace("$", "") if price_tag else "N/A"

        # Find the container with both "Condition" and its value as children
        condition = "N/A"
        ul = soup.find('ul')
        if ul:
            first_li = ul.find('li')
            if first_li:
                flex_div = first_li.find('div')
                spans = flex_div.find_all('span', recursive=False)
                if len(spans) >= 2:
                    value_span = spans[1]
                    # Traverse into divs/spans to find the actual value span
                    deep_span = value_span.find_all('span')
                    if deep_span:
                        # Get the last span (most nested)
                        condition = deep_span[-1].get_text(strip=True)

        # Find the <ul> containing item properties
        ul = soup.find('ul')
        description = "N/A"
        if ul:
            # Get the next div after the <ul>
            desc_div = ul.find_next_sibling('div')
            if desc_div:
                # Find the span inside that div
                desc_span = desc_div.find('span')
                if desc_span:
                    desc_text = desc_span.get_text(strip=True)
                    if len(desc_text) > 10:
                        description = desc_text

        # Extract image URL from Facebook Marketplace
        image_url = "N/A"
        # Try multiple strategies to find the product image
        # Strategy 1: Look for img tag with alt containing "Product photo" or "Image"
        img_tag = soup.find('img', alt=lambda v: v and ("Product photo" in v or "Image" in v or "product" in v.lower()))
        if img_tag:
            image_url = img_tag.get('src') or img_tag.get('data-src') or "N/A"
        
        # Strategy 2: If not found, look for images in common Facebook Marketplace containers
        if image_url == "N/A":
            # Look for images in divs with role="img" or aria-label
            img_div = soup.find('div', role='img')
            if img_div:
                img_inside = img_div.find('img')
                if img_inside:
                    image_url = img_inside.get('src') or img_inside.get('data-src') or "N/A"
        
        # Strategy 3: Look for the first large image (likely the product image)
        if image_url == "N/A":
            all_imgs = soup.find_all('img')
            for img in all_imgs:
                src = img.get('src') or img.get('data-src')
                if src and ('scontent' in src or 'fbcdn' in src or 'marketplace' in src.lower()):
                    # Check if it's a reasonable size (not an icon)
                    width = img.get('width')
                    height = img.get('height')
                    if (width and int(width) > 200) or (height and int(height) > 200):
                        image_url = src
                        break
        
        # Strategy 4: Use Playwright to get image from page directly
        if image_url == "N/A":
            try:
                # Try to find image using Playwright selectors
                img_element = await page.query_selector('img[alt*="Product"], img[alt*="product"], img[alt*="Image"]')
                if img_element:
                    image_url = await img_element.get_attribute('src') or "N/A"
                else:
                    # Try to find the main image in the carousel or gallery
                    img_element = await page.query_selector('div[role="img"] img, img[src*="scontent"], img[src*="fbcdn"]')
                    if img_element:
                        image_url = await img_element.get_attribute('src') or "N/A"
            except Exception as e:
                print(f"Error extracting image with Playwright: {e}")

        # Download image if URL was found and download_images is True
        image_filename = ""
        if image_url != "N/A" and download_images:
            # Generate filename based on URL or use a timestamp
            import re
            # Extract item ID from URL if possible
            item_id_match = re.search(r'/item/(\d+)/', url)
            item_id = item_id_match.group(1) if item_id_match else str(len(items) + 1)
            filename = f"images/item_{item_id}.jpg"
            
            print(f"Downloading image from {image_url[:100]}...")
            if download_image(image_url, filename):
                image_filename = filename
                print(f"Successfully downloaded image to {filename}")
            else:
                print(f"Failed to download image, using URL instead")
                image_filename = image_url
        else:
            image_filename = image_url

        item = {
            "category": category,
            "title": title,
            "rank": "", 
            "condition": condition,
            "description": description,
            "image_url": image_url,
            "image_filename": image_filename,
            "price": price,
            "url": url
        }
        items.append(item)
        await page.close()
        await browser.close()
    return items

if __name__ == "__main__":
    sheet_url = "https://docs.google.com/spreadsheets/d/1PCJE3OE5VuTaCFxbg41Yz5H4NgLJwBWzPHvaJddLyH0/edit#gid=0"
    creds_path = "evaluation-dataset-67b8dd770c30.json"
    
    # Prompt for URL and category
    url = input("Enter Facebook Marketplace URL: ").strip()
    if not url:
        print("Error: URL is required")
        exit(1)
    
    category = input("Enter category (e.g., 'Bed frame'): ").strip()
    if not category:
        category = "Uncategorized"
        print(f"Using default category: {category}")
    
    print(f"\nScraping URL: {url}")
    print(f"Category: {category}\n")
    
    items = asyncio.run(scrape_marketplace_items(url, category, download_images=True))
    save_to_google_sheet(items, sheet_url, creds_path)