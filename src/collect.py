from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from config import COUNTRY, LIMIT, CHART, CATEGORIES

BASE_URL = "https://rss.marketingtools.apple.com/api/v2"
KST = ZoneInfo("Asia/Seoul")
DATA_ROOT = Path(__file__).resolve().parents[1] / "data"

HEADERS = {
    "User-Agent": "appstore-rank-collector/1.0 (+GitHub Actions)"
}


def fetch_category(category_name: str, genre_id: int) -> dict:
    url = f"{BASE_URL}/{COUNTRY}/apps/{CHART}/{LIMIT}/apps.json"
    response = requests.get(
        url,
        params={"genre": genre_id},
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    payload = response.json()
    feed = payload.get("feed", {})
    results = feed.get("results", [])

    apps = []
    for rank, item in enumerate(results, start=1):
        genres = item.get("genres") or []
        apps.append(
            {
                "rank": rank,
                "id": item.get("id"),
                "name": item.get("name"),
                "developer": item.get("artistName"),
                "url": item.get("url"),
                "icon": item.get("artworkUrl100"),
                "release_date": item.get("releaseDate"),
                "genres": [
                    {
                        "id": genre.get("genreId"),
                        "name": genre.get("name"),
                        "url": genre.get("url"),
                    }
                    for genre in genres
                ],
            }
        )

    now = datetime.now(KST)
    return {
        "collected_at": now.isoformat(),
        "date": now.date().isoformat(),
        "country": COUNTRY,
        "chart": CHART,
        "category": category_name,
        "genre_id": genre_id,
        "feed_updated": feed.get("updated"),
        "count": len(apps),
        "apps": apps,
    }


def main() -> None:
    today = datetime.now(KST).date().isoformat()
    output_dir = DATA_ROOT / today
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "date": today,
        "country": COUNTRY,
        "chart": CHART,
        "categories": {},
    }

    for index, (category_name, genre_id) in enumerate(CATEGORIES.items()):
        print(f"[{index + 1}/{len(CATEGORIES)}] collecting {category_name}...")
        try:
            data = fetch_category(category_name, genre_id)
            output_file = output_dir / f"{category_name}.json"
            output_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            summary["categories"][category_name] = {
                "genre_id": genre_id,
                "count": data["count"],
                "file": str(output_file.relative_to(DATA_ROOT.parent)),
            }
            print(f"  saved {data['count']} apps")
        except Exception as exc:
            summary["categories"][category_name] = {
                "genre_id": genre_id,
                "error": str(exc),
            }
            print(f"  ERROR: {exc}")

        # Be polite to the public feed.
        time.sleep(0.5)

    (output_dir / "_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"done: {output_dir}")


if __name__ == "__main__":
    main()
