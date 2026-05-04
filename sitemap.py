import requests
import re
import random
import time
import xml.etree.ElementTree as ET

# The sitemap url was obtained by accessing the robots.txt file under the main domain of the site
INDEX_URL = "https://www.trollandtoad.com/sitemap.xml"
NAMESPACE = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

def get_multi_sitemap_ygo_links(target_count=1000):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    # Regex filter to select yugioh products urls
    ygo_regex = re.compile(r'products/[a-z0-9\-]+-([a-z]{3,4}-en[0-9]{3,5})-(common|.*?rare)', re.IGNORECASE)
    
    try:
        print(f"Fetching Sitemap Index: {INDEX_URL}")
        index_res = requests.get(INDEX_URL, headers=headers, timeout=15)
        root = ET.fromstring(index_res.content)
        
        # 1. Identify all product sitemaps
        all_sub_maps = []
        for sitemap in root.findall('ns:sitemap', NAMESPACE):
            loc = sitemap.find('ns:loc', NAMESPACE).text
            if "sitemap_products_" in loc:
                all_sub_maps.append(loc)
        
        # Shuffle the maps to randomly select urls
        random.shuffle(all_sub_maps)
        print(f"Found {len(all_sub_maps)} product sitemaps. Starting the search...")

        final_ygo_links = []

        # 2. Loop through each sub sitemap until reaching the target count
        for sub_map_url in all_sub_maps:
            if len(final_ygo_links) >= target_count:
                break
                
            print(f"  Scanning: {sub_map_url.split('/')[-1]} (Current count: {len(final_ygo_links)})")
            
            # Use streaming for the sub sitemap to prevent memory crashes
            with requests.get(sub_map_url, headers=headers, stream=True, timeout=30) as r:
                for line in r.iter_lines():
                    if line:
                        line_text = line.decode('utf-8')
                        
                        # Apply the "Precision" filter we built
                        if ygo_regex.search(line_text):
                            match = re.search(r'<loc>(.*?)</loc>', line_text)
                            if match:
                                final_ygo_links.append(match.group(1))
                    
                    # Periodic check to stop streaming if this one file gave us enough
                    if len(final_ygo_links) >= target_count * 2: 
                        break
            
            # wait time between each download
            time.sleep(1)

        # 3. Finalize the list
        if not final_ygo_links:
            print("No links found matching the YGO pattern in any sitemap.")
            return

        selected_links = random.sample(final_ygo_links, min(len(final_ygo_links), target_count))
        
        with open("links.txt", "w") as f:
            for link in selected_links:
                f.write(link + "\n")
        
        print(f"\nSuccess! Total YGO-style links discovered: {len(final_ygo_links)}")
        print(f"Saved {len(selected_links)} unique links to links.txt")

    except Exception as e:
        print(f"Critical Error: {e}")

if __name__ == "__main__":
    get_multi_sitemap_ygo_links(1000)
    