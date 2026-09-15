from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from config import COUNTRIES, LIMIT, CHART, CATEGORIES


BASE_URL = "https://rss.marketingtools.apple.com/api/v2"

KST = ZoneInfo("Asia/Seoul")

DATA_ROOT = Path(__file__).resolve().parents[1] / "data"

HEADERS = {
    "User-Agent": "appstore-rank-collector/1.0 (+GitHub Actions)"
}


def fetch_category(
    country: str,
    category_name: str,
    genre_id: int,
) -> dict:
    """
    Apple App Store 공개 RSS Feed에서
    특정 국가 / 카테고리의 무료 앱 Top N을 가져온다.
    """

    url = (
        f"{BASE_URL}/"
        f"{country}/apps/{CHART}/{LIMIT}/apps.json"
    )

    response = requests.get(
        url,
        params={
            "genre": genre_id,
        },
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
        "country": country,
        "chart": CHART,
        "category": category_name,
        "genre_id": genre_id,
        "count": len(apps),
        "apps": apps,
    }


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    now = datetime.now(KST)
    today = now.date().isoformat()

    output_dir = DATA_ROOT / today

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary = {
        "date": today,
        "collected_at": now.isoformat(),
        "chart": CHART,
        "limit": LIMIT,
        "countries": {},
    }

    total_jobs = len(COUNTRIES) * len(CATEGORIES)
    current_job = 0

    for country in COUNTRIES:
        print()
        print("=" * 60)
        print(f"Country: {country}")
        print("=" * 60)

        country_dir = output_dir / country

        country_summary = {
            "categories": {},
        }

        for category_name, genre_id in CATEGORIES.items():
            current_job += 1

            print(
                f"[{current_job}/{total_jobs}] "
                f"{country} / {category_name}"
            )

            try:
                data = fetch_category(
                    country=country,
                    category_name=category_name,
                    genre_id=genre_id,
                )

                output_file = (
                    country_dir
                    / f"{category_name}.json"
                )

                save_json(
                    output_file,
                    data,
                )

                country_summary["categories"][category_name] = {
                    "genre_id": genre_id,
                    "count": data["count"],
                    "status": "success",
                    "file": str(
                        output_file.relative_to(
                            DATA_ROOT.parent
                        )
                    ),
                }

                print(
                    f"  ✓ saved {data['count']} apps"
                )

            except requests.Timeout:
                error_message = "request timeout"

                country_summary["categories"][category_name] = {
                    "genre_id": genre_id,
                    "status": "error",
                    "error": error_message,
                }

                print(
                    f"  ✗ {error_message}"
                )

            except requests.HTTPError as exc:
                status_code = None

                if exc.response is not None:
                    status_code = exc.response.status_code

                error_message = (
                    f"HTTP {status_code}: {exc}"
                )

                country_summary["categories"][category_name] = {
                    "genre_id": genre_id,
                    "status": "error",
                    "error": error_message,
                }

                print(
                    f"  ✗ {error_message}"
                )

            except Exception as exc:
                error_message = str(exc)

                country_summary["categories"][category_name] = {
                    "genre_id": genre_id,
                    "status": "error",
                    "error": error_message,
                }

                print(
                    f"  ✗ {error_message}"
                )

            # Apple 공개 Feed에 너무 빠르게 요청하지 않도록
            # 요청 사이에 약간의 간격을 둔다.
            time.sleep(0.5)

        summary["countries"][country] = country_summary

    summary_file = output_dir / "_summary.json"

    save_json(
        summary_file,
        summary,
    )

    print()
    print("=" * 60)
    print("Collection complete")
    print(f"Output: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
