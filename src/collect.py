from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from config import COUNTRIES, LIMIT, CHART, CATEGORIES

BASE_URL = "https://itunes.apple.com"

CHART_FEEDS = {
    "top-free": "topfreeapplications",
    "top-paid": "toppaidapplications",
    "top-grossing": "topgrossingapplications",
}

KST = ZoneInfo("Asia/Seoul")
DATA_ROOT = Path(__file__).resolve().parents[1] / "data"

HEADERS = {
    "User-Agent": "appstore-rank-collector/1.0 (+GitHub Actions)"
}


def fetch_category(country: str, category_name: str, genre_id: int) -> dict:
    """
    특정 국가 / 카테고리의 무료 앱 Top N을 가져온다.
    """

    # rss.marketingtools.apple.com(v2)은 genre 파라미터를 무시하므로
    # 카테고리 필터가 동작하는 iTunes RSS 피드를 사용한다.
    url = (
        f"{BASE_URL}/{country}/rss/{CHART_FEEDS[CHART]}/"
        f"limit={LIMIT}/genre={genre_id}/json"
    )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    payload = response.json()

    entries = payload.get("feed", {}).get("entry", [])

    if isinstance(entries, dict):
        entries = [entries]

    apps = []

    for rank, item in enumerate(entries, start=1):
        category = item.get("category", {}).get("attributes", {})
        images = item.get("im:image") or [{}]

        apps.append(
            {
                "rank": rank,
                "id": item.get("id", {}).get("attributes", {}).get("im:id"),
                "name": item.get("im:name", {}).get("label"),
                "developer": item.get("im:artist", {}).get("label"),
                "url": item.get("id", {}).get("label"),
                "icon": images[-1].get("label"),
                "release_date": item.get("im:releaseDate", {}).get("label", "")[:10],
                "genres": [
                    {
                        "id": category.get("im:id"),
                        "name": category.get("label"),
                        "url": category.get("scheme"),
                    }
                ],
            }
        )

    now = datetime.now(KST)
    return {
        "collected_at": now.isoformat(),
        "date": now.date().isoformat(),
        "country": country,
        "chart": CHART,
        "category": category_name,
        "genre_id": genre_id,
        "count": len(apps),
        "apps": apps,
    }


def main() -> None:
    today = datetime.now(KST).date().isoformat()

    for country in COUNTRIES:
        output_dir = DATA_ROOT / today / country
        output_dir.mkdir(parents=True, exist_ok=True)

        summary = {
            "date": today,
            "country": country,
            "chart": CHART,
            "categories": {},
        }

        for index, (category_name, genre_id) in enumerate(CATEGORIES.items()):
            print(f"[{country}] [{index + 1}/{len(CATEGORIES)}] collecting {category_name}...")
            try:
                data = fetch_category(country, category_name, genre_id)
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
