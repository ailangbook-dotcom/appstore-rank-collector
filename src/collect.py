from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

# Windows 기본 콘솔 인코딩(cp949)에서는 체크·엑스 기호를 못 찍어
# 에러 분기의 print 한 줄에서 프로세스 전체가 죽는다.
# 출력 스트림을 utf-8로 고정하고, 그래도 안 되면 대체 문자로 흘린다.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

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


def fetch_category(
    country: str,
    category_name: str,
    genre_id: int,
) -> dict:
    """
    Apple App Store 공개 RSS Feed에서
    특정 국가 / 카테고리의 무료 앱 Top N을 가져온다.
    """

    # rss.marketingtools.apple.com(v2)은 genre 파라미터를 무시하므로
    # 카테고리 필터가 동작하는 iTunes RSS 피드를 사용한다.
    url = (
        f"{BASE_URL}/"
        f"{country}/rss/{CHART_FEEDS[CHART]}/limit={LIMIT}/genre={genre_id}/json"
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
