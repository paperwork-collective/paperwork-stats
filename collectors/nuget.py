#!/usr/bin/env python3
"""
Daily NuGet download snapshot for the Paperwork and Scryber packages.

NuGet only publishes running totals (per package and per version), so the
downloads for a day are the difference between two snapshots. This keeps:

  data/nuget/history.json  every snapshot taken - one per date (a re-run on the
                           same date replaces that day's snapshot)
  data/nuget/latest.json   the latest snapshot worked out for a report - totals,
                           increases (since the previous snapshot, 7 and 30 days),
                           downloads per day and the version breakdown, as arrays
                           so a template can loop over them

Standard library only. Run from the repo root: python3 collectors/nuget.py
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

PACKAGES = [
    {"id": "Scryber.Core", "family": "Scryber", "description": "The open-source generation engine"},
    {"id": "Scryber.Core.Mvc", "family": "Scryber", "description": "ASP.NET MVC integration for Scryber.Core"},
    {"id": "Paperwork.Core", "family": "Paperwork", "description": "Generate PDFs from Paperwork templates"},
    {"id": "Paperwork.Core.Extensions", "family": "Paperwork", "description": "Configuration, assets, maps and auth for Paperwork.Core apps"},
    {"id": "Paperwork.CLI", "family": "Paperwork", "description": "The paperwork command line tool"},
]

SEARCH = "https://azuresearch-usnc.nuget.org/query"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "nuget")
HISTORY = os.path.join(DATA, "history.json")
LATEST = os.path.join(DATA, "latest.json")

DAILY_DAYS = 30      # days of downloads-per-day in latest.json
TOP_VERSIONS = 10    # versions listed per package in latest.json


def fetch(package_id):
    """The running totals for one package: overall and per (listed) version."""
    query = urllib.parse.urlencode({
        "q": "packageid:" + package_id,
        "prerelease": "true",
        "semVerLevel": "2.0.0",
    })
    req = urllib.request.Request(SEARCH + "?" + query, headers={"User-Agent": "paperwork-stats"})
    with urllib.request.urlopen(req, timeout=30) as res:
        body = json.load(res)

    match = [d for d in body.get("data", []) if d.get("id", "").lower() == package_id.lower()]
    if not match:
        raise RuntimeError("NuGet did not return the package " + package_id)
    found = match[0]
    return {
        "total": int(found.get("totalDownloads", 0)),
        "latestVersion": found.get("version", ""),
        "versions": {v["version"]: int(v.get("downloads", 0)) for v in found.get("versions", [])},
    }


def load(path, empty):
    if not os.path.exists(path):
        return empty
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
        f.write("\n")


def snapshot_on_or_before(snapshots, day):
    """The latest snapshot taken on or before a date, or None."""
    best = None
    for s in snapshots:
        if s["date"] <= day.isoformat():
            best = s
    return best


def increase(now, then, package_id):
    if then is None or package_id not in then["packages"]:
        return None
    return now["packages"][package_id]["total"] - then["packages"][package_id]["total"]


def build_latest(snapshots, taken_at):
    """Works the snapshots out into the shape the report template reads."""
    current = snapshots[-1]
    previous = snapshots[-2] if len(snapshots) > 1 else None
    today = date.fromisoformat(current["date"])
    week = snapshot_on_or_before(snapshots, today - timedelta(days=7))
    month = snapshot_on_or_before(snapshots, today - timedelta(days=30))
    first = snapshots[0]

    packages = []
    for p in PACKAGES:
        pid = p["id"]
        now = current["packages"].get(pid)
        if now is None:
            continue

        # Downloads per day: each snapshot's difference from the one before it,
        # put against the later date. A missed day shows as one larger step.
        daily = []
        window = [s for s in snapshots if s["date"] > (today - timedelta(days=DAILY_DAYS)).isoformat()]
        for s in window:
            i = snapshots.index(s)
            before = snapshots[i - 1] if i > 0 else None
            if before and pid in before["packages"] and pid in s["packages"]:
                daily.append({"date": s["date"], "downloads": s["packages"][pid]["total"] - before["packages"][pid]["total"]})

        before_versions = previous["packages"][pid]["versions"] if previous and pid in previous["packages"] else {}
        versions = [
            {
                "version": v,
                "downloads": n,
                "increase": (n - before_versions[v]) if v in before_versions else None,
                "share": round(100.0 * n / now["total"], 1) if now["total"] else 0,
                "isLatest": v == now["latestVersion"],
            }
            for v, n in now["versions"].items()
        ]
        versions.sort(key=lambda v: (-(v["increase"] or 0), -v["downloads"]))
        top = versions[:TOP_VERSIONS]
        if not any(v["isLatest"] for v in top):
            top += [v for v in versions if v["isLatest"]]

        packages.append({
            "id": pid,
            "family": p["family"],
            "description": p["description"],
            "nugetUrl": "https://www.nuget.org/packages/" + pid,
            "latestVersion": now["latestVersion"],
            "latestVersionDownloads": now["versions"].get(now["latestVersion"], 0),
            "versionCount": len(now["versions"]),
            "total": now["total"],
            "sincePrevious": increase(current, previous, pid),
            "last7Days": increase(current, week, pid),
            "last30Days": increase(current, month, pid),
            "sinceTrackingStarted": increase(current, first, pid),
            "daily": daily,
            "versions": top,
        })

    def add(field):
        values = [p[field] for p in packages if p[field] is not None]
        return sum(values) if values else None

    return {
        "date": current["date"],
        "takenAt": taken_at,
        "previousDate": previous["date"] if previous else None,
        "trackingStarted": first["date"],
        "snapshotCount": len(snapshots),
        "totals": {
            "downloads": add("total"),
            "sincePrevious": add("sincePrevious"),
            "last7Days": add("last7Days"),
            "last30Days": add("last30Days"),
            "sinceTrackingStarted": add("sinceTrackingStarted"),
        },
        "families": [
            {
                "name": fam,
                "downloads": sum(p["total"] for p in packages if p["family"] == fam),
                "sincePrevious": sum((p["sincePrevious"] or 0) for p in packages if p["family"] == fam),
            }
            for fam in ["Scryber", "Paperwork"]
        ],
        "packages": packages,
    }


def main():
    now = datetime.now(timezone.utc)
    taken_at = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    snapshot = {"date": now.date().isoformat(), "takenAt": taken_at, "packages": {}}

    for p in PACKAGES:
        snapshot["packages"][p["id"]] = fetch(p["id"])
        print(f"{p['id']}: {snapshot['packages'][p['id']]['total']:,}")

    history = load(HISTORY, {"source": "NuGet search API running totals", "snapshots": []})
    history["snapshots"] = [s for s in history["snapshots"] if s["date"] != snapshot["date"]]
    history["snapshots"].append(snapshot)
    history["snapshots"].sort(key=lambda s: s["date"])

    save(HISTORY, history)
    save(LATEST, build_latest(history["snapshots"], taken_at))
    print(f"Saved the snapshot for {snapshot['date']} ({len(history['snapshots'])} in all).")


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:  # a failed run must fail the workflow, not commit half a snapshot
        print("Error: " + str(ex), file=sys.stderr)
        sys.exit(1)
