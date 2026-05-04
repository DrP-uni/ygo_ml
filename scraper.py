import requests
from bs4 import BeautifulSoup
import json
import re
import csv
import os
from datetime import datetime
import time

# Configuration
INPUT_FILE = "links.txt"
OUTPUT_FILE = "card_data_final.csv"
PROJECT_DATE = datetime(2026, 4, 29) 
BASE_URL = "https://www.db.yugioh-card.com"

def get_neuron_details(card_name):
    """
    Fixes the 'Empty List' issue by sending a POST request 
    directly to the database search engine.
    """
    search_url = f"{BASE_URL}/yugiohdb/card_search.action"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.db.yugioh-card.com/yugiohdb/card_search.action"
    }

    # logic params for the database card search 
    params = {
        "ope": "1",
        "sess": "1",
        "keyword": card_name,
        "stype": "1",
        "ctype": "", # ctype is card type, blank to ignore the card type filter (can be removed). potentially useful
        "othercon": "2",
        "rp": "50", # how many cards are shown per page, 50 is necessary as sometimes there are multiple related cards
        "request_locale": "en"
    }

    try:
        # Step 1: Get the search results
        response = requests.get(search_url, params=params, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        results = soup.find_all("div", id="card_list") # card_list contains all returned card from the query
        target_path = None
        for res in results:
            # Strict name matching check (in case the query returns multiple cards)
            card_list = res.find_all("div", class_="t_row")
            for card in card_list:
                name_span = card.find("span", class_="card_name")
                if name_span:
                    found_name = name_span.get_text(strip=True)
                    if found_name.lower() == card_name.lower():
                        link_tag = card.find("input", class_="link_value")
                        if link_tag:
                            target_path = link_tag['value'].replace('&amp;', '&')
                            print(f"    [DEBUG] Verified Match: {found_name}")
                            break
            
        if not target_path:

            return "N/A"

        # Step 2: Follow the link to the card detail page
        time.sleep(1)
        detail_res = requests.get(f"{BASE_URL}{target_path}", headers=headers, timeout=10)
        detail_soup = BeautifulSoup(detail_res.text, 'html.parser')
        
        # Step 3: Get the last reprint date
        rows = detail_soup.find_all("div", id="update_list")
        dates = []
        for row in rows:
            time_cell = row.find("div", class_="time")
            if time_cell:
                try:
                    d_obj = datetime.strptime(time_cell.get_text(strip=True), "%Y-%m-%d")
                    dates.append(d_obj)
                except: continue

        if dates:
            orig_date = min(dates)
            days_old = (PROJECT_DATE - orig_date).days
            return days_old

    except Exception as e:
        print(f"    [DEBUG] Scraper Error: {e}")
    
    return "N/A"

def run_scraper():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    with open(INPUT_FILE, "r") as f:
        urls = [line.strip() for line in f if line.strip()]

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    fieldnames = ["Card Name", "Card Code", "Days Since Print", "Rarity", "Price", "Availability"]
    all_results = []

    for url in urls:
        try:
            print(f"\n--- Processing: {url} ---")
            res = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')

            # selecting the unique h1 tag as it contains the product name (card name + code + rarity)
            h1_tag = soup.find("h1")
            full_title = h1_tag.get_text(strip=True) if h1_tag else ""
            
            if not full_title or "Troll and Toad" in full_title:
                # Fallback to meta if H1 is weird
                title_tag = soup.find("meta", property="og:title")
                full_title = title_tag["content"] if title_tag else ""

            rarity_list = [
                "Quarter Century Secret Rare", 
                "Prismatic Secret Rare",
                "Starlight Rare", 
                "Collector's Rare",
                "Ultimate Rare", 
                "Secret Rare", 
                "Ghost Rare", 
                "Ultra Rare", 
                "Super Rare", 
                "Gold Rare", 
                "Platinum Rare",
                "Rare",
                "Common"
            ]
            found_rarity = "N/A"
            # matching the rarity from full_title to check for rarity
            for r in rarity_list:
                if re.search(rf"\b{re.escape(r)}\b", full_title, re.IGNORECASE):
                    found_rarity = r
                    break

            # Remove product codes (e.g., LOB-001) and anything after a hyphen or parenthesis
            # Prone to error on card names with hyphen
            # 1. Identify card set code
            code_match = re.search(r'([A-Z0-9]+-[A-Z0-9]+)', full_title)
            product_code = code_match.group(1) if code_match else ""
            
            # 2. Extract the card name
            if product_code:
                clean_name = full_title.split(product_code)[0].strip().rstrip('(').strip()
            else:
                # Split at common separators if no code found
                clean_name = re.split(r' - | \(', full_title)[0].strip()

            
            if found_rarity != "N/A":
                #Removing the rarity from the name 
                clean_name = re.sub(rf"(?i)\b{re.escape(found_rarity)}\b", '', clean_name).strip().rstrip('()').strip()
            print(f"DEBUG: Rarity: {found_rarity} | Name for DB: {clean_name}")
            
            days_old = get_neuron_details(clean_name)

            # Finding pricing data
            # There are some bug regarding the availability, which may be due to Troll and Toad backend
            script = soup.find("script", string=re.compile(r'window\.ShopifyAnalytics\.meta'))
            if script:
                json_match = re.search(r'meta = (\{.*?\});', script.string, re.DOTALL)
                if json_match:
                    json_data = json.loads(json_match.group(1))
                    variants = json_data.get("product", {}).get("variants", [])
                    
                    for v in variants:
                        v_title = v.get("title", "")
                        # Priority for near mint (almost perfect) or the only available variant
                        if "Near Mint" in v_title or len(variants) == 1:
                            price = f"{float(v.get('price', 0))/100:.2f}"
                            stock = "In Stock" if v.get("available") else "Out of Stock"
                            
                            all_results.append({
                                "Card Name": clean_name,
                                "Card Code": product_code,
                                "Days Since Print": days_old,
                                "Rarity": found_rarity,
                                "Price": price,
                                "Availability": stock
                            })
                            break
        except Exception as e:
            print(f"Error: {e}")

    # Export
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_results)
    print(f"\nSaved {len(all_results)} rows to {OUTPUT_FILE}")

if __name__ == "__main__":
    run_scraper()