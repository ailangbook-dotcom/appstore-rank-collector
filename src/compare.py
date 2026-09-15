from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path


DATA_ROOT = Path(__file__).resolve().parents[1] / "data"


def load_apps(
    day: str,
    country: str,
    category: str,
) -> list[dict]:
    """
    data/YYYY-MM-DD/{country}/{category}.json 파일에서
    앱 목록을 읽는다.
    """

    path = (
        DATA_ROOT
        / day
        / country
        / f"{category}.json"
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Data file not found: {path}"
        )

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    return data.get("apps", [])


def compare(
    previous_day: str,
    current_day: str,
    country: str,
    category: str,
) -> dict:
    previous = load_apps(
        previous_day,
        country,
        category,
    )

    current = load_apps(
        current_day,
        country,
        category,
    )

    previous_by_id = {
        app["id"]: app
        for app in previous
    }

    current_by_id = {
        app["id"]: app
        for app in current
    }

    changes = []

    for app in current:
        app_id = app["id"]
        previous_app = previous_by_id.get(app_id)

        if previous_app is None:
            previous_rank = None
            change = None
            status = "new"

        else:
            previous_rank = previous_app["rank"]

            # 예:
            # 80위 -> 20위
            # 80 - 20 = +60
            # 양수일수록 순위 상승
            change = (
                previous_rank
                - app["rank"]
            )

            if change > 0:
                status = "up"

            elif change < 0:
                status = "down"

            else:
                status = "same"

        changes.append(
            {
                "id": app_id,
                "name": app.get("name"),
                "developer": app.get("developer"),
                "previous_rank": previous_rank,
                "current_rank": app.get("rank"),
                "change": change,
                "status": status,
                "url": app.get("url"),
                "icon": app.get("icon"),
            }
        )

    dropped = []

    for app in previous:
        app_id = app["id"]

        if app_id not in current_by_id:
            dropped.append(
                {
                    "id": app_id,
                    "name": app.get("name"),
                    "developer": app.get("developer"),
                    "previous_rank": app.get("rank"),
                    "url": app.get("url"),
                    "icon": app.get("icon"),
                }
            )

    rising = sorted(
        [
            item
            for item in changes
            if item["change"] is not None
            and item["change"] > 0
        ],
        key=lambda item: item["change"],
        reverse=True,
    )

    falling = sorted(
        [
            item
            for item in changes
            if item["change"] is not None
            and item["change"] < 0
        ],
        key=lambda item: item["change"],
    )

    new_entries = [
        item
        for item in changes
        if item["status"] == "new"
    ]

    same = [
        item
        for item in changes
        if item["status"] == "same"
    ]

    return {
        "country": country,
        "category": category,
        "previous_date": previous_day,
        "current_date": current_day,
        "summary": {
            "previous_count": len(previous),
            "current_count": len(current),
            "rising_count": len(rising),
            "falling_count": len(falling),
            "new_count": len(new_entries),
            "dropped_count": len(dropped),
            "same_count": len(same),
        },
        "rising": rising,
        "falling": falling,
        "new_entries": new_entries,
        "dropped": dropped,
        "same": same,
    }


def main() -> None:
    """
    사용법:

    python src/compare.py \
        2026-09-14 \
        2026-09-15 \
        us \
        productivity

    인자를 안 넣으면:
    어제 vs 오늘 / kr / productivity
    """

    if len(sys.argv) >= 5:
        previous_day = sys.argv[1]
        current_day = sys.argv[2]
        country = sys.argv[3]
        category = sys.argv[4]

    else:
        today = date.today()

        current_day = today.isoformat()
        previous_day = (
            today - timedelta(days=1)
        ).isoformat()

        country = "kr"
        category = "productivity"

    result = compare(
        previous_day=previous_day,
        current_day=current_day,
        country=country,
        category=category,
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
