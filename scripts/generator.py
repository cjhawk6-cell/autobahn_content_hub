"""
generator.py — Autobahn Content Hub
Reads data/articles.json and uses the Anthropic API to generate
LinkedIn posts, blog hooks, and email newsletter intros for each chapter.
Saves output to data/drafts_YYYY-MM-DD.json and data/drafts_latest.json.
"""

import json
import os
import anthropic
from datetime import datetime, timezone

# ── Prompt template ────────────────────────────────────────────────────────────

LINKEDIN_PROMPT = """You are a content strategist for Autobahn Consultants, a business consulting firm that helps companies scale from $50M to $500M and beyond. You are writing for the @AutobahnConsultants LinkedIn company page.

Book context: "Rock Your Business: Navigating the Road from $50 Million to $500 Million and Beyond" by Jonathan Slain and Katherine Slain is releasing soon. This is Autobahn's second book, following "Rock the Recession."

Chapter: {chapter_num} — {chapter_title}
Topic area: {chapter_sub}
Chapter authors: {chapter_authors}

Articles found today:
{articles_block}

Write THREE LinkedIn post drafts. Each must be distinct in format:

POST 1 — THOUGHT LEADERSHIP (no direct book mention):
- 150–200 words
- Open with a bold, counterintuitive statement about {chapter_sub}
- Reference one of the articles above as supporting evidence (paraphrase — do not quote)
- Share 2–3 specific insights a $50M+ business leader would find valuable
- End with a thought-provoking question
- Tone: confident, direct, zero buzzwords, no em dashes
- 3 relevant hashtags at the very end only

POST 2 — ARTICLE REACTION (ties to a specific scraped article):
- 100–150 words
- Name the article and source naturally ("A recent piece in [source]...")
- Add Autobahn's unique angle on why this matters for scaling companies
- End with a call-to-action and the article URL
- Tone: authoritative but conversational, no em dashes

POST 3 — BOOK TIE-IN (direct book mention):
- 100–150 words
- Tie the article topic to Chapter {chapter_num} of "Rock Your Business"
- Name the chapter title and at least one author
- Tease one insight without giving the full framework away
- End with: "Rock Your Business — available [soon]. Follow us for updates."
- Tone: proud but not salesy, no em dashes

Return ONLY valid JSON, no markdown fences, no preamble:
{{
  "post1": {{
    "type": "thought_leadership",
    "text": "...",
    "hashtags": ["...", "...", "..."]
  }},
  "post2": {{
    "type": "article_reaction",
    "text": "...",
    "source_url": "..."
  }},
  "post3": {{
    "type": "book_tie_in",
    "text": "..."
  }},
  "blog_hook": "A 60-word hook paragraph for a blog post or email newsletter on this topic. Sharp, no filler.",
  "email_subject": "A compelling email subject line (under 50 chars) for a newsletter issue on this topic."
}}"""


def format_articles_block(articles: list[dict]) -> str:
    """Format articles into a readable block for the prompt."""
    if not articles:
        return "No articles found for this chapter today."
    lines = []
    for i, a in enumerate(articles, 1):
        lines.append(f"{i}. \"{a['title']}\" — {a.get('source', 'Unknown source')}")
        lines.append(f"   URL: {a['url']}")
        if a.get("snippet"):
            lines.append(f"   Summary: {a['snippet'][:150]}")
        lines.append("")
    return "\n".join(lines).strip()


def generate_posts_for_chapter(client: anthropic.Anthropic, chapter: dict) -> dict:
    """Call Claude API to generate posts for a single chapter."""
    articles_block = format_articles_block(chapter.get("articles", []))

    prompt = LINKEDIN_PROMPT.format(
        chapter_num=chapter["chapter"],
        chapter_title=chapter["title"],
        chapter_sub=chapter["sub"],
        chapter_authors=chapter["authors"],
        articles_block=articles_block,
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Graceful fallback — store raw text so nothing is lost
        parsed = {"_parse_error": True, "_raw": raw}

    return parsed


def run_generator() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY not set. Add it to your .env file or GitHub Secrets."
        )

    client = anthropic.Anthropic(api_key=api_key)

    # Load scraped articles
    articles_path = "data/articles.json"
    if not os.path.exists(articles_path):
        raise FileNotFoundError(
            f"{articles_path} not found. Run scripts/scraper.py first."
        )

    with open(articles_path) as f:
        articles_data = json.load(f)

    chapters = articles_data.get("chapters", [])
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": run_date,
        "chapters": [],
    }

    print(f"\n=== Autobahn Content Hub — Generator ===")
    print(f"Run date: {run_date}")
    print(f"Chapters to process: {len(chapters)}\n")

    for chapter in chapters:
        print(f"Generating posts: Chapter {chapter['chapter']} — {chapter['sub']}...")
        try:
            posts = generate_posts_for_chapter(client, chapter)
            output["chapters"].append(
                {
                    "chapter": chapter["chapter"],
                    "title": chapter["title"],
                    "sub": chapter["sub"],
                    "authors": chapter["authors"],
                    "articles": chapter.get("articles", []),
                    "posts": posts,
                    "scraped_at": chapter.get("scraped_at", run_date),
                }
            )
            print(f"  Done.\n")
        except Exception as e:
            print(f"  [ERROR] Chapter {chapter['chapter']}: {e}\n")
            output["chapters"].append(
                {
                    "chapter": chapter["chapter"],
                    "title": chapter["title"],
                    "sub": chapter["sub"],
                    "authors": chapter["authors"],
                    "articles": chapter.get("articles", []),
                    "posts": {"_error": str(e)},
                }
            )

    # Save dated output
    os.makedirs("data", exist_ok=True)
    dated_path = f"data/drafts_{run_date}.json"
    latest_path = "data/drafts_latest.json"

    with open(dated_path, "w") as f:
        json.dump(output, f, indent=2)
    with open(latest_path, "w") as f:
        json.dump(output, f, indent=2)

    total_posts = sum(
        3 for c in output["chapters"] if not c["posts"].get("_error")
    )
    print(f"Saved {total_posts} post sets to {dated_path}")
    print(f"Latest snapshot updated at {latest_path}")


if __name__ == "__main__":
    # Load .env if running locally
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    run_generator()
