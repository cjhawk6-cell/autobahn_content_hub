"""
scraper.py — Autobahn Content Hub
Pulls Google News RSS articles for each Rock Your Business chapter topic.
Saves results to data/articles.json.
"""

import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import os

CHAPTER_QUERIES = [
    {
        "chapter": 1,
        "title": "Lead Like Lives Depend On It",
        "sub": "Leadership & Scaling",
        "authors": "Katherine Slain",
        "queries": [
            "executive leadership scaling company",
            "CEO delegation time management growth",
            "leadership skills C-suite scaling",
        ],
    },
    {
        "chapter": 2,
        "title": "Maximize Your Multiple to Achieve Your Exit",
        "sub": "M&A & Business Valuation",
        "authors": "Paul Belair & George Hohman",
        "queries": [
            "business exit strategy entrepreneur",
            "company valuation multiple M&A",
            "founder exit private equity acquisition",
        ],
    },
    {
        "chapter": 3,
        "title": "What We Learned Selling Fish Food and Nike Shoes",
        "sub": "Strategic Planning & Execution",
        "authors": "Rafa Loyo & Jim Randall",
        "queries": [
            "strategic plan execution business",
            "OKR Rockefeller Habits scaling company",
            "strategy execution mid-market growth",
        ],
    },
    {
        "chapter": 4,
        "title": "Every Day Without a Real Sales Strategy is a Donation",
        "sub": "Sales Strategy",
        "authors": "Deb & Brandon",
        "queries": [
            "B2B sales strategy revenue growth",
            "sales structure coaching mid-market",
            "enterprise sales process optimization",
        ],
    },
    {
        "chapter": 5,
        "title": "What Does Your Marketing Smell Like?",
        "sub": "Branding & Marketing",
        "authors": "Kayli Simpson & Yasmin West",
        "queries": [
            "brand building company culture marketing",
            "marketing automation brand humanity",
            "brand differentiation growth company",
        ],
    },
    {
        "chapter": 6,
        "title": "The Talent Engine",
        "sub": "Talent & People Strategy",
        "authors": "Caleb Hawkins, Darla Klein & Yasmin West",
        "queries": [
            "talent acquisition strategy scaling company",
            "behavioral profiles hiring DISC leadership",
            "people strategy culture high-growth business",
        ],
    },
    {
        "chapter": 7,
        "title": "Death by KPIs",
        "sub": "Metrics & Performance",
        "authors": "Héctor Arias, Matt Radicelli & Jim Randall",
        "queries": [
            "KPI strategy business performance",
            "metrics data-driven leadership company",
            "performance measurement scaling organization",
        ],
    },
    {
        "chapter": 8,
        "title": "The Third Monitor Theory",
        "sub": "AI in Business",
        "authors": "Hudson Shank & Jonathan Slain",
        "queries": [
            "AI business productivity executives",
            "artificial intelligence company operations strategy",
            "AI tools CEO leadership productivity",
        ],
    },
    {
        "chapter": 9,
        "title": "How Could You Be Successful and Not Have It?",
        "sub": "Imposter Syndrome & Leadership Psychology",
        "authors": "Samantha Frost, Caleb Hawkins & Rafa Loyo",
        "queries": [
            "imposter syndrome executive leadership",
            "leadership confidence CEO psychology",
            "high-performance team psychology business",
        ],
    },
    {
        "chapter": 10,
        "title": "Coming Up for Air",
        "sub": "Life Planning & Work-Life Design",
        "authors": "Samantha Frost, Jonathan & Katherine Slain",
        "queries": [
            "life planning entrepreneur founder",
            "work-life design executive burnout prevention",
            "founder wellbeing business success",
        ],
    },
]

MAX_ARTICLES_PER_CHAPTER = 3  # How many articles to keep per chapter


def fetch_google_news_rss(query: str, max_results: int = 5) -> list[dict]:
    """Fetch articles from Google News RSS for a given query."""
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"

    articles = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_data = resp.read()

        root = ET.fromstring(xml_data)
        channel = root.find("channel")
        if channel is None:
            return articles

        items = channel.findall("item")
        for item in items[:max_results]:
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            pub_el = item.find("pubDate")
            source_el = item.find("source")

            title = title_el.text if title_el is not None else ""
            link = link_el.text if link_el is not None else ""
            description = desc_el.text if desc_el is not None else ""
            pub_date = pub_el.text if pub_el is not None else ""
            source = source_el.text if source_el is not None else ""

            # Strip HTML tags from description
            import re
            description = re.sub(r"<[^>]+>", "", description).strip()

            if title and link:
                articles.append(
                    {
                        "title": title,
                        "url": link,
                        "source": source,
                        "snippet": description[:200] if description else "",
                        "pub_date": pub_date,
                    }
                )
    except Exception as e:
        print(f"  [WARN] Could not fetch RSS for query '{query}': {e}")

    return articles


def deduplicate(articles: list[dict]) -> list[dict]:
    """Remove duplicate articles by URL."""
    seen = set()
    unique = []
    for a in articles:
        if a["url"] not in seen:
            seen.add(a["url"])
            unique.append(a)
    return unique


def scrape_all_chapters() -> list[dict]:
    """Run the full scrape across all chapters and queries."""
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    all_chapter_results = []

    print(f"\n=== Autobahn Content Hub — Scraper ===")
    print(f"Run date: {run_date}")
    print(f"Chapters to scrape: {len(CHAPTER_QUERIES)}\n")

    for chapter in CHAPTER_QUERIES:
        print(f"Chapter {chapter['chapter']}: {chapter['sub']}")
        all_articles = []

        for query in chapter["queries"]:
            print(f"  Querying: {query}")
            results = fetch_google_news_rss(query, max_results=4)
            all_articles.extend(results)

        unique_articles = deduplicate(all_articles)[:MAX_ARTICLES_PER_CHAPTER]
        print(f"  Found {len(unique_articles)} unique articles\n")

        all_chapter_results.append(
            {
                "chapter": chapter["chapter"],
                "title": chapter["title"],
                "sub": chapter["sub"],
                "authors": chapter["authors"],
                "articles": unique_articles,
                "scraped_at": run_date,
            }
        )

    return all_chapter_results


def save_results(data: list[dict]) -> None:
    """Save results to data/articles.json."""
    os.makedirs("data", exist_ok=True)
    output_path = "data/articles.json"
    with open(output_path, "w") as f:
        json.dump(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "chapters": data,
            },
            f,
            indent=2,
        )
    print(f"Saved {sum(len(c['articles']) for c in data)} total articles to {output_path}")


if __name__ == "__main__":
    results = scrape_all_chapters()
    save_results(results)
