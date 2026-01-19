import os
import re
import json
import time
import requests
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.canada.ca"
LIST_URL = "https://www.canada.ca/en/revenue-agency/services/forms-publications/forms.html"
OUTPUT_DIR = "CRA_Forms"
INDEX_PATH = os.path.join(OUTPUT_DIR, "cra_forms_index.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

PREFIX_CATEGORY_MAP = {
    "T1": "Personal",
    "T2": "Business",
    "T3": "Trusts",
    "T4": "Personal",
    "T4A": "Personal",
    "T5": "Personal",
    "RC": "Business",
    "GST": "Business",
    "NR": "NonResident",
    "UHT": "Property",
    "DST": "Digital",
}

def guess_category_and_prefix(form_number: str):
    if not form_number:
        return "Other", "Other"
    num = form_number.strip().upper()
    prefixes = sorted(PREFIX_CATEGORY_MAP.keys(), key=len, reverse=True)
    for p in prefixes:
        if num.startswith(p):
            return PREFIX_CATEGORY_MAP[p], p
    if num[0].isalpha():
        return "Other", num[0]
    return "Other", "Other"

def get_soup(url):
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")

def scrape_master_list():
    print("Loading CRA forms list page...")
    soup = get_soup(LIST_URL)

    table = soup.find("table")
    if not table:
        print("No table found on the page. Structure may have changed.")
        return []

    forms = []
    tbody = table.find("tbody") or table
    rows = tbody.find_all("tr")
    print(f"Found {len(rows)} rows in the table (page 1).")

    # If CRA adds pagination with links, we could extend here.
    # For now, assume full list is on this page (as in your run: 1240 rows).

    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        number = cols[0].get_text(strip=True)
        title_cell = cols[1]
        last_update = cols[2].get_text(strip=True)

        html_link_tag = title_cell.find("a")
        html_url = urljoin(BASE_URL, html_link_tag["href"]) if html_link_tag and html_link_tag.has_attr("href") else None
        title = html_link_tag.get_text(strip=True) if html_link_tag else title_cell.get_text(strip=True)

        category, prefix = guess_category_and_prefix(number)

        forms.append({
            "number": number,
            "title": title,
            "last_update": last_update,
            "html_url": html_url,
            "category": category,
            "prefix": prefix,
            "pdfs": []  # will fill with Playwright
        })

    return forms

def ensure_folder_for_form(category, prefix):
    cat_dir = os.path.join(OUTPUT_DIR, category)
    pre_dir = os.path.join(cat_dir, prefix)
    os.makedirs(pre_dir, exist_ok=True)
    return pre_dir

def extract_year(last_update: str):
    if not last_update:
        return "unknown"
    m = re.search(r"(19|20)\d{2}", last_update)
    if m:
        return m.group(0)
    return "unknown"

def classify_pdf_kind(href: str, link_text: str):
    href = href.lower()
    text = (link_text or "").lower()
    if "-fill" in href or "fillable" in text:
        return "fillable"
    return "print"

def build_structured_filename(form_number: str, kind: str, year: str):
    num = form_number.replace(" ", "").upper()
    return f"{num}_{kind}_{year}.pdf"

def scrape_pdfs_with_playwright(forms):
    print("\nStarting Playwright to fetch PDFs from each form page...\n")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=HEADERS["User-Agent"])
        page = context.new_page()

        for i, form in enumerate(forms, start=1):
            number = form["number"]
            title = form["title"]
            html_url = form["html_url"]

            print(f"[{i}/{len(forms)}] {number} - {title}")
            if not html_url:
                print("  [SKIP] No HTML URL")
                continue

            try:
                page.goto(html_url, wait_until="load", timeout=60000)
                # Give JS time to render the "Ways to get the form" section
                page.wait_for_timeout(2000)

                # Grab all links that look like PDFs
                pdf_links = page.locator("a[href*='.pdf']")
                count = pdf_links.count()

                if count == 0:
                    print("  [SKIP] No PDF links found in rendered page.")
                    continue

                year = extract_year(form["last_update"])
                folder = ensure_folder_for_form(form["category"], form["prefix"])

                for idx in range(count):
                    href = pdf_links.nth(idx).get_attribute("href")
                    text = pdf_links.nth(idx).inner_text().strip()
                    if not href or ".pdf" not in href.lower():
                        continue

                    pdf_url = urljoin(BASE_URL, href)
                    kind = classify_pdf_kind(href, text)
                    filename = build_structured_filename(number, kind, year)
                    path = os.path.join(folder, filename)

                    # Avoid duplicates
                    if os.path.exists(path):
                        print(f"  [EXISTS] {path}")
                    else:
                        print(f"  [DL] {kind.upper()} → {path}")
                        try:
                            with requests.get(pdf_url, headers=HEADERS, stream=True) as r:
                                r.raise_for_status()
                                with open(path, "wb") as f:
                                    for chunk in r.iter_content(chunk_size=8192):
                                        if chunk:
                                            f.write(chunk)
                            time.sleep(0.2)
                        except Exception as e:
                            print(f"    [FAIL] Download error: {e}")
                            continue

                    form["pdfs"].append({
                        "kind": kind,
                        "year": year,
                        "url": pdf_url,
                        "local_path": path
                    })

            except Exception as e:
                print(f"  [WARN] Failed to process form page: {e}")

        browser.close()

def main():
    forms = scrape_master_list()
    print(f"\nTotal forms discovered: {len(forms)}")

    scrape_pdfs_with_playwright(forms)

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(forms, f, ensure_ascii=False, indent=2)

    print(f"\nIndex written to: {INDEX_PATH}")
    print("Done.")

if __name__ == "__main__":
    main()
