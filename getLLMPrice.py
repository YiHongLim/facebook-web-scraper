import requests

def get_llm_price(
    image_urls,
    description,
    latitude,
    longitude,
    username="user_jt7bdy",
    model="claude-haiku-4-5-20251001",
    radius_in_km=1000,
    search_database=False
):
    url = "https://estimatelistingprice-cwjz6kyz6q-uc.a.run.app"
    headers = {
    "Origin": "https://throwly.co/",
    "Referer": "https://throwly.co/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Content-Type": "application/json"
}

    payload = {
        "imageUrls": image_urls,
        "description": description,
        "latitude": latitude,
        "longitude": longitude,
        "radiusInKm": radius_in_km,
        "username": username,          # required for Firestore username gate
        "searchDatabase": search_database,  # optional, default True
        "model": model                 # e.g., "claude-3-haiku-20240307"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)

        # Raise an error if status code is not 200 OK
        response.raise_for_status()

        # Parse JSON response
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"Error fetching LLM price: {e}")
        return None

