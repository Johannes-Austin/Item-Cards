import csv
import os
import requests
import re
from bs4 import BeautifulSoup

# --- Configuration ---
URL_TO_SCRAPE = "http://dnd5e.wikidot.com/wondrous-items"
BASE_URL = "http://dnd5e.wikidot.com"
MASTER_CSV = "itemNames.csv"
NEW_ITEMS_CSV = "newItemNames.csv"

def load_existing_urls(filename):
    """Reads the existing CSV and returns a set of known URLs."""
    existing_urls = set()
    if os.path.exists(filename):
        with open(filename, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                if row:  # Skip empty lines
                    # URL is the first item in the row based on your format
                    existing_urls.add(row[0]) 
    return existing_urls

def scrape_wondrous_items():
    """Scrapes the wikidot page and returns a filtered list of actual (URL, Name) tuples."""
    response = requests.get(URL_TO_SCRAPE)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    scraped_items = []
    
    ignored_categories = {
        'armor', 'potion', 'ring', 'rod', 'scroll', 
        'staff', 'wand', 'weapon', 'wondrous-items', 'homebrew'
    }
    
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        
        if href.startswith('/wondrous-items:'):
            slug = href.split(':', 1)[1].lower()
            
            # 1. Skip multi-colon filtering (e.g., bg:da)
            if ':' in slug:
                continue
                
            # 2. Skip explicitly ignored category words
            if slug in ignored_categories:
                continue
                
            # 3. NEW FILTER: Skip short book codes (e.g., 'dmg', 'cos', 'ai', 'xge')
            # If it has no hyphens and is short, it's a book source abbreviation.
            if '-' not in slug and len(slug) <= 5:
                continue
                
            full_url = BASE_URL + href
            name = a_tag.get_text(strip=True)
            
            if name: 
                scraped_items.append((full_url, name))
                
    return scraped_items
def main():
    print(f"Loading existing database from {MASTER_CSV}...")
    existing_urls = load_existing_urls(MASTER_CSV)
    
    print("Scraping Wikidot for current Wondrous Items...")
    try:
        current_items = scrape_wondrous_items()
    except Exception as e:
        print(f"Failed to scrape webpage: {e}")
        return

    # Filter out items we already know about
    new_items = []
    for url, name in current_items:
        if url not in existing_urls:
            # We also check if the URL is already in new_items to avoid 
            # duplicates if the webpage lists the same item twice
            if url not in [item[0] for item in new_items]:
                new_items.append((url, name))

    if not new_items:
        print("No new items found. Your master list is up to date.")
        return

    print(f"Found {len(new_items)} new items! Updating files...")

    # Append the new discoveries to the master list
    with open(MASTER_CSV, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerows(new_items)

    # Append the new discoveries to the new items list
    with open(NEW_ITEMS_CSV, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerows(new_items)

    print("Update complete.")

if __name__ == "__main__":
    main()