from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parents[1] / "data"


def load_apps(day: str, category: str) -> list[dict]:
    path = DATA_ROOT / day / f"{category}.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))["apps"]


def compare(previous_day: str, current_day: str, category: str) -> dict:
    previous = load_apps(previous_day, category)
    current = load_apps(current_day, category)

    old_rank = {app["id"]: app["rank"] for app in previous}
    current_ids = {app["id"] for app in current}

    changes = []
    for app in current:
        app_id = app["id"]
        before = old_rank.get(app_id)

        if before is None:
            status = "new"
            change = None
        else:
            # Positive means ranking improved: 80 -> 20 = +60
            change = before - app["rank"]
            status = "up" if change > 0 else "down" if change < 0 else "same"

        changes.append(
            {
                "id": app_id,
                "name": app["name"],
                "developer": app.get("developer"),
                "previous_rank": before,
                "current_rank": app["rank"],
                "change": change,
                "status": status,
                "url": app.get("url"),
            }
        )

    dropped = [
        {
            "id": app["id"],
            "name": app["name"],
            "previous_rank": app["rank"],
        }
        for app in previous
        if app["id"] not in current_ids
    ]

    rising = sorted(
        [x for x in changes if x["change"] is not None and x["change"] > 0],
        key=lambda x: x["change"],
        reverse=True,
    )

    falling = sorted(
        [x for x in changes if x["change"] is not None and x["change"] < 0],
        key=lambda x: x["change"],
    )

    new_entries = [x for x in changes if x["status"] == "new"]

    return {
        "category": category,
        "previous_date": previous_day,
        "current_date": current_day,
        "rising": rising,
        "falling": falling,
        "new_entries": new_entries,
        "dropped": dropped,
    }


def main() -> None:
    if len(sys.argv) >= 4:
        previous_day, current_day, category = sys.argv[1:4]
    else:
        today = date.today()
        current_day = today.isoformat()
        previous_day = (today - timedelta(days=1)).isoformat()
        category = "productivity"

    result = compare(previous_day, current_day, category)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
