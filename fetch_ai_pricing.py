import time
import gspread
from google.oauth2.service_account import Credentials
import getLLMPrice  # Your AI pricing API client

def enrich_google_sheet_with_ai(sheet_url, creds_path):
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_url(sheet_url).sheet1

    data = sheet.get_all_values()
    headers = data[0]
    print(repr(headers))

    rows = data[1:]
    # Find column indexes
    idx_image = headers.index("Image")
    idx_descr = headers.index("Description")
    idx_aiPrice = headers.index("AI Price")
    idx_aiDescription = headers.index("AI Description")
    # Update rows missing AI Price
    for i, row in enumerate(rows, start=2):
        if not row[idx_aiPrice] or not row[idx_aiDescription]:
            try:
                result = getLLMPrice.get_llm_price(
                    image_urls=[row[idx_image]],
                    description=row[idx_descr],
                    latitude=42.01984729301244,
                    longitude=-93.66806296271663
                )
                if result and "listing" in result and "llmPrice" in result["listing"]:
                    ai_price = result["listing"]["llmPrice"]
                    ai_description = result["listing"]["priceExplanation"]
                    sheet.update_cell(i, idx_aiPrice+1, ai_price)
                    sheet.update_cell(i, idx_aiDescription+1, ai_description)
                    print(f"Updated row {i} with AI price {ai_price} and AI description")
                else:
                    print(f"Row {i}: No AI price found (API error or incomplete response).")
            except Exception as e:
                print(f"Row {i}: Error fetching LLM price: {e}")


if __name__ == "__main__":
    start_time = time.perf_counter()
    sheet_url = "https://docs.google.com/spreadsheets/d/1PCJE3OE5VuTaCFxbg41Yz5H4NgLJwBWzPHvaJddLyH0/edit#gid=0"
    creds_path = "evaluation-dataset-67b8dd770c30.json"
    enrich_google_sheet_with_ai(sheet_url, creds_path)
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    print(f"Program execution time: {elapsed_time:.4f} seconds")
