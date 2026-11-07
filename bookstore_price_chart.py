"""
Scrape every book from books.toscrape.com (all 50 pages) politely,
save them to a CSV, and chart price vs. star rating with matplotlib.

Usage:
    python bookstore_price_chart.py            # scrape, then chart
    python bookstore_price_chart.py --cached   # skip scraping, reuse books.csv
"""

import argparse
import csv
import random
import re
import time
from pathlib import Path
from statistics import mean
from urllib.parse import urljoin

import matplotlib.pyplot as plt
import requests
from bs4 import BeautifulSoup

# ---------- Settings ----------
START_URL = "https://books.toscrape.com/catalogue/page-1.html"
MAX_PAGES = 50            # safety cap so a bug can never loop forever
PAUSE_SECONDS = 1.5       # polite delay between page requests
TIMEOUT_SECONDS = 10      # never wait forever on a slow server
CSV_FILE = Path("books.csv")
CHART_FILE = Path("price_vs_rating.png")
HEADERS = {
    # Tell the site who you are. Customize this!
    "User-Agent": "BookPriceChartLearner/1.0 (educational scraping project)"
}

# The site stores ratings as words in a CSS class, e.g. "star-rating Three"
RATING_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def parse_page(html):
    """Pull (title, price, rating) from every book on one page,
    and return them along with the relative URL of the 'next' page (or None)."""
    soup = BeautifulSoup(html, "html.parser")
    books = []

    for card in soup.select("article.product_pod"):
        title = card.h3.a["title"]

        # Price looks like "£51.77" -> keep only digits and the dot
        price_text = card.select_one("p.price_color").get_text()
        price = float(re.sub(r"[^\d.]", "", price_text))

        # Rating lives in the class list: ["star-rating", "Three"]
        classes = card.select_one("p.star-rating")["class"]
        rating = next(RATING_WORDS[c] for c in classes if c in RATING_WORDS)

        books.append({"title": title, "price": price, "rating": rating})

    next_link = soup.select_one("li.next a")
    next_href = next_link["href"] if next_link else None
    return books, next_href


def scrape_all_books():
    """Walk through the catalogue by following each page's 'next' button."""
    all_books = []
    url = START_URL
    page_number = 0

    with requests.Session() as session:      # reuses the connection = lighter load
        session.headers.update(HEADERS)

        while url and page_number < MAX_PAGES:
            page_number += 1
            print(f"Fetching page {page_number}: {url}")

            response = session.get(url, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()      # stop loudly on 404/500 errors
            response.encoding = "utf-8"      # avoids "Â£" garbage in prices

            books, next_href = parse_page(response.text)
            all_books.extend(books)

            # Build the absolute URL of the next page (or None at the end)
            url = urljoin(url, next_href) if next_href else None

            if url:
                time.sleep(PAUSE_SECONDS)    # be polite: pause between requests

    print(f"Done. Collected {len(all_books)} books from {page_number} pages.")
    return all_books


def save_csv(books):
    with CSV_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "price", "rating"])
        writer.writeheader()
        writer.writerows(books)
    print(f"Saved {CSV_FILE}")


def load_csv():
    with CSV_FILE.open(newline="", encoding="utf-8") as f:
        return [
            {"title": r["title"], "price": float(r["price"]), "rating": int(r["rating"])}
            for r in csv.DictReader(f)
        ]


def make_chart(books):
    """Scatter of price vs. rating, with a jitter and an average line."""
    random.seed(42)  # same jitter every run
    # Ratings are whole numbers, so dots would stack in 5 vertical lines.
    # A tiny random sideways nudge ("jitter") lets you see every dot.
    xs = [b["rating"] + random.uniform(-0.18, 0.18) for b in books]
    ys = [b["price"] for b in books]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(xs, ys, alpha=0.45, s=18, label="Individual books")

    ratings = sorted({b["rating"] for b in books})
    averages = [mean(b["price"] for b in books if b["rating"] == r) for r in ratings]
    ax.plot(ratings, averages, color="crimson", marker="o", linewidth=2,
            label="Average price")
    for r, avg in zip(ratings, averages):
        ax.annotate(f"£{avg:.2f}", (r, avg), textcoords="offset points",
                    xytext=(0, 10), ha="center", color="crimson", fontsize=9)

    ax.set_title(f"Book Price vs. Star Rating ({len(books)} books)")
    ax.set_xlabel("Star rating")
    ax.set_ylabel("Price (£)")
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()

    fig.savefig(CHART_FILE, dpi=150)
    print(f"Saved {CHART_FILE}")
    plt.show()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cached", action="store_true",
                        help="reuse books.csv instead of scraping again")
    args = parser.parse_args()

    if args.cached and CSV_FILE.exists():
        books = load_csv()
        print(f"Loaded {len(books)} books from {CSV_FILE}")
    else:
        books = scrape_all_books()
        save_csv(books)

    make_chart(books)


if __name__ == "__main__":
    main()
