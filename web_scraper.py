import json
import os
import requests
from bs4 import BeautifulSoup
import cloudscraper
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path


# -----------------------------
# Sazen Tea stock check
# -----------------------------
def check_sazen_stock(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    text = soup.get_text(separator=" ", strip=True).lower()

    if "this product is unavailable" in text:
        return "Out of stock"
    else:
        return "In stock"


# -----------------------------
# Marukyu Koyamaen stock check
# -----------------------------
def check_mk_stock(url):
    scraper = cloudscraper.create_scraper()
    response = scraper.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    products = {}

    for li in soup.find_all("li", class_="product"):
        name_tag = li.find("h2", class_="woocommerce-loop-product__title") or li.find("a")
        name = name_tag.get_text(strip=True) if name_tag else "Unknown"

        # clean up the name
        if "¥" in name:
            name = name.split("¥")[0].strip()

        link_tag = li.find("a", href=True)
        link = link_tag["href"] if link_tag else "No link"

        classes = li.get("class", [])
        if "instock" in classes:
            stock_status = "In stock"
        elif "outofstock" in classes:
            stock_status = "Out of stock"
        else:
            stock_status = "Unknown"

        products[link] = stock_status

    return products


# -----------------------------
# Combined scrape
# -----------------------------
def scrape_products():
    results = {}

    sazen_urls = [
        "https://www.sazentea.com/en/products/p825-matcha-samidori.html",
        "https://www.sazentea.com/en/products/p823-matcha-ogurayama.html",
        "https://www.sazentea.com/en/products/p826-matcha-matsukaze.html"
    ]

    for url in sazen_urls:
        results[url] = check_sazen_stock(url)

    mk_urls = [
        "https://www.marukyu-koyamaen.co.jp/english/shop/products/catalog/matcha/tea-schools",
        "https://www.marukyu-koyamaen.co.jp/english/shop/products/catalog/matcha/principal",
        "https://www.marukyu-koyamaen.co.jp/english/shop/products/catalog/matcha/kancho",
        "https://www.marukyu-koyamaen.co.jp/english/shop/products/catalog/matcha/gentei"
    ]

    for url in mk_urls:
        results.update(check_mk_stock(url))

    return results


# -----------------------------
# Email configuration
# -----------------------------

# Load config from environment variables
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
TO_EMAIL = os.getenv("TO_EMAIL")


def send_email(subject, body):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = TO_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

    print("📧 Email sent successfully!")


# -----------------------------
# Compare stock + send updates
# -----------------------------
def check_stock_changes():
    data_file = Path("last_stock.json")

    # Load old data
    if data_file.exists():
        with open(data_file, "r") as f:
            old_data = json.load(f)
    else:
        old_data = {}

    # Scrape new data
    new_data = scrape_products()

    # Compare
    changes = []
    items_stocked = False
    for product, status in new_data.items():
        if status == "In stock":
            items_stocked = True
        old_status = old_data.get(product)
        if old_status != status and status == "In stock":
            changes.append(f"{product}\n{old_status or 'Unknown'} → {status}\n")

    # Send email if any changes
    if changes and items_stocked:
        message = "\n".join(changes)
        print("Stock changes detected:\n", message)
        send_email("Matcha Stock Update", message)

        # Update file
        with open(data_file, "w") as f:
            json.dump(new_data, f, indent=2)
    else:
        print("No changes since last check.")


if __name__ == "__main__":
    check_stock_changes()
