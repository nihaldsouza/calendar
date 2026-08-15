# Calendar

A TRMNL plugin showing a month calendar with Canadian public holidays — polls the free [Nager.Date](https://date.nager.at) API. No API key needed. Refreshes every 12 hours.

## How it works

**Settings** (`src/settings.yml`): Polls `PublicHolidays/{year}/CA` (the full-year endpoint, so already-passed holidays earlier in the month still show up). The year is currently hardcoded and needs a manual bump each January.

**Transform** (`src/transform.py`): Filters holidays down to nationwide ones plus British Columbia regional ones (`REGION = "CA-BC"`), builds a Monday-first month grid (`weeks`) with today/holiday/weekend flags, and groups the current month's holidays by date (`month_holidays`) — a date can hold more than one holiday name. Long holiday names get a curated short form (`HOLIDAY_ABBREVIATIONS`) for grid-cell display. `holiday_text_class` auto-shrinks the holiday list's font size when a month has enough holidays that the full size would overflow.

**Templates**: `half_vertical` is the actively maintained layout — top half is the month grid, bottom half lists that month's holidays grouped by date with a highlighted date badge. `full`, `half_horizontal`, and `quadrant` still work (same data model, no broken references) but haven't been given the same visual pass yet.

## Local Development

**Lint and preview:**
```bash
./bin/trmnlp lint
./bin/trmnlp serve
```

Open `http://localhost:4567` to cycle through all four layouts. Select the "TRMNL X" device in the preview UI to match the target hardware.

*Note: The `serve` command uses Docker under the hood. If running non-interactively (e.g. in CI), omit the `-it` flag from your docker invocation — the container will still start.*

## Deployment

CI lints every PR. On merge to `main`, the `push` job automatically deploys **all four layouts** to your TRMNL account using the `TRMNL_API_KEY` repo secret.

A separate `preview` job captures and commits an updated demo GIF on every push to `main`.
