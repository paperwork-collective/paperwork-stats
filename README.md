# Paperwork stats

Usage numbers for the Paperwork family, collected daily into JSON so a Paperwork template can turn them into a report.

## NuGet downloads

A GitHub Action ([`nuget.yml`](.github/workflows/nuget.yml)) runs every day at 06:17 UTC, and can be run by hand from the Actions tab. It reads the download totals for:

| Package | Family |
|---|---|
| [Scryber.Core](https://www.nuget.org/packages/Scryber.Core) | Scryber |
| [Scryber.Core.Mvc](https://www.nuget.org/packages/Scryber.Core.Mvc) | Scryber |
| [Paperwork.Core](https://www.nuget.org/packages/Paperwork.Core) | Paperwork |
| [Paperwork.Core.Extensions](https://www.nuget.org/packages/Paperwork.Core.Extensions) | Paperwork |
| [Paperwork.CLI](https://www.nuget.org/packages/Paperwork.CLI) | Paperwork |

NuGet only publishes running totals, and updates them about once a day, so downloads for a day are the difference between two snapshots. Tracking started on 2026-11-04; nothing before that can be recovered.

### The data

- [`data/nuget/history.json`](data/nuget/history.json) - every snapshot: the total and per-version totals for each package, one snapshot per date.
- [`data/nuget/latest.json`](data/nuget/latest.json) - the latest snapshot, already worked out for a report. For a template, load it from
  `https://raw.githubusercontent.com/paperwork-collective/paperwork-stats/main/data/nuget/latest.json`

`latest.json` has:

| Field | What it is |
|---|---|
| `date`, `previousDate`, `trackingStarted`, `snapshotCount` | When this snapshot and the one before were taken, and how much history there is |
| `totals` | All packages together: `downloads`, `sincePrevious`, `last7Days`, `last30Days`, `sinceTrackingStarted` |
| `families` | Scryber and Paperwork: `downloads` and `sincePrevious` |
| `packages[]` | Per package: `id`, `family`, `description`, `nugetUrl`, `latestVersion`, `latestVersionDownloads`, `versionCount`, `total` and the same increases as `totals` |
| `packages[].daily[]` | `date` and `downloads` for each of the last 30 days - the difference from the snapshot before |
| `packages[].versions[]` | The busiest versions (by increase, then downloads) plus the latest: `version`, `downloads`, `increase`, `share` (% of the package's total), `isLatest` |

An increase is `null` until there is an earlier snapshot to compare with - `last7Days` needs a week of history, `last30Days` a month. A missed day appears as one larger step on the next day.

### Run it locally

```bash
python3 collectors/nuget.py
```

Standard library only. A second run on the same date replaces that day's snapshot.

## Still to come

- The Paperwork template for the daily report, reading `latest.json`.
- Site visits for paperwork.help, paperwork.design and paperwork.vu.
