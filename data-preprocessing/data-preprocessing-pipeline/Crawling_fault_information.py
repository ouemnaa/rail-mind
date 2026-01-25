from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import csv
import json
import re
from datetime import datetime, timedelta
import time

start_date = datetime(2024, 10, 1)
end_date = datetime(2024, 10, 15)

csv_file = "Train_fault_information_description.csv"
with open(csv_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["date", "source", "title", "description"])

options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--log-level=3")
driver = webdriver.Chrome(options=options)

total_records = 0
current_date = start_date

while current_date <= end_date:
    date_str = current_date.strftime("%d_%m_%Y")
    url = f"https://trainstats.altervista.org/avvisi.php?data={date_str}"
    print(f"📡 Fetching {date_str} ...", end=" ")

    try:
        driver.get(url)
        time.sleep(3)  # Wait for JavaScript to load

        # Get page source and parse
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")

        # Extract JSON data from JavaScript variables
        avvisi = []
        
        # Find all script tags
        scripts = soup.find_all("script")
        for script in scripts:
            script_text = script.string if script.string else ""
            
            # Extract datarfi (RFI announcements)
            rfi_match = re.search(r'var datarfi = JSON\.parse\("(.+?)"\);', script_text)
            if rfi_match:
                json_str = rfi_match.group(1)
                if json_str != "null":
                    try:
                        # Unescape the JSON string
                        json_str = json_str.replace('\\"', '"').replace('\\\\', '\\')
                        data = json.loads(json_str)
                        for item in data:
                            title = item.get('titolo', '').strip()
                            body = item.get('corpo', '').strip()
                            if title or body:
                                avvisi.append(('RFI', title, body))
                    except json.JSONDecodeError:
                        pass
            
            # Extract datati (Trenitalia announcements)
            ti_match = re.search(r'var datati = JSON\.parse\("(.+?)"\);', script_text)
            if ti_match:
                json_str = ti_match.group(1)
                if json_str != "null":
                    try:
                        json_str = json_str.replace('\\"', '"').replace('\\\\', '\\')
                        data = json.loads(json_str)
                        for item in data:
                            title = item.get('titolo', '').strip()
                            body = item.get('corpo', '').strip()
                            if title or body:
                                avvisi.append(('Trenitalia', title, body))
                    except json.JSONDecodeError:
                        pass

        if avvisi:
            with open(csv_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                for source, title, body in avvisi:
                    # Clean up text
                    body = body.replace('\n', ' ').replace('\r', ' ').strip()
                    writer.writerow([current_date.strftime("%Y-%m-%d"), source, title, body])
            total_records += len(avvisi)
            print(f"✅ {len(avvisi)} announcements")
        else:
            print("⚠️ No announcements found")

    except Exception as e:
        print(f"❌ Error: {e}")

    current_date += timedelta(days=1)

driver.quit()
print(f"\n✅ Completed! Total: {total_records} announcements saved to {csv_file}")
