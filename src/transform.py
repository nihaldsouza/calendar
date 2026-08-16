import calendar
import urllib.request
from datetime import date, timedelta

# Matches the region already configured on the community "Simple Calendar"
# plugin this replaces, so behavior stays consistent.
REGION = "CA-BC"

# Text size in the item list is fixed (no shrink-to-fit), so instead the
# item count is capped to what actually fits in the list area. Despite the
# different layouts (stacked under the grid in full/half_vertical, beside
# it in half_horizontal), the available list height works out the same —
# half_horizontal's box is only half the device height, offsetting its
# side-by-side layout advantage. Tuned by rendering dense fixture data
# locally via trmnlp and counting rows before overflow.
MAX_ITEMS = 6


# 2026 F1 qualifying + race sessions only (no practice, no sprint sessions).
# Times converted from UTC to fixed Pacific Standard Time (UTC-8, no DST
# adjustment) at conversion time — source: f1calendar.com/timezone/Etc-UTC.
F1_2026_EVENTS = [
    ("2026-03-06", "9:00pm Australian Qualifying"),
    ("2026-03-07", "8:00pm Australian Grand Prix"),
    ("2026-03-13", "11:00pm Chinese Qualifying"),
    ("2026-03-14", "11:00pm Chinese Grand Prix"),
    ("2026-03-27", "10:00pm Japanese Qualifying"),
    ("2026-03-28", "10:00pm Japanese Grand Prix"),
    ("2026-05-02", "1:00pm Miami Qualifying"),
    ("2026-05-03", "10:00am Miami Grand Prix"),
    ("2026-05-23", "1:00pm Canadian Qualifying"),
    ("2026-05-24", "1:00pm Canadian Grand Prix"),
    ("2026-06-06", "7:00am Monaco Qualifying"),
    ("2026-06-07", "6:00am Monaco Grand Prix"),
    ("2026-06-13", "7:00am Barcelona Qualifying"),
    ("2026-06-14", "6:00am Barcelona Grand Prix"),
    ("2026-06-27", "7:00am Austrian Qualifying"),
    ("2026-06-28", "6:00am Austrian Grand Prix"),
    ("2026-07-04", "8:00am British Qualifying"),
    ("2026-07-05", "7:00am British Grand Prix"),
    ("2026-07-18", "7:00am Belgian Qualifying"),
    ("2026-07-19", "6:00am Belgian Grand Prix"),
    ("2026-07-25", "7:00am Hungarian Qualifying"),
    ("2026-07-26", "6:00am Hungarian Grand Prix"),
    ("2026-08-22", "7:00am Dutch Qualifying"),
    ("2026-08-23", "6:00am Dutch Grand Prix"),
    ("2026-09-05", "7:00am Italian Qualifying"),
    ("2026-09-06", "6:00am Italian Grand Prix"),
    ("2026-09-12", "7:00am Spanish Qualifying"),
    ("2026-09-13", "6:00am Spanish Grand Prix"),
    ("2026-09-25", "5:00am Azerbaijan Qualifying"),
    ("2026-09-26", "4:00am Azerbaijan Grand Prix"),
    ("2026-10-03", "2:00am Bahrain Qualifying"),
    ("2026-10-04", "12:00am Bahrain Grand Prix"),
    ("2026-10-10", "6:00am Singapore Qualifying"),
    ("2026-10-11", "5:00am Singapore Grand Prix"),
    ("2026-10-24", "2:00pm United States Qualifying"),
    ("2026-10-25", "12:00pm United States Grand Prix"),
    ("2026-10-31", "1:00pm Mexico City Qualifying"),
    ("2026-11-01", "12:00pm Mexico City Grand Prix"),
    ("2026-11-07", "10:00am Brazilian Qualifying"),
    ("2026-11-08", "9:00am Brazilian Grand Prix"),
    ("2026-11-20", "8:00pm Las Vegas Qualifying"),
    ("2026-11-21", "8:00pm Las Vegas Grand Prix"),
    ("2026-11-28", "10:00am Qatar Qualifying"),
    ("2026-11-29", "8:00am Qatar Grand Prix"),
    ("2026-12-05", "6:00am Abu Dhabi Qualifying"),
    ("2026-12-06", "5:00am Abu Dhabi Grand Prix"),
]


def is_relevant(holiday):
    if holiday.get("global"):
        return True
    counties = holiday.get("counties") or []
    return REGION in counties


# Grid cells are ~60px wide — a full name like "National Day for Truth and
# Reconciliation" wraps across several lines and blows out that week's row
# height. Curated short forms read better than a blind word-truncation
# (e.g. "BC Day" instead of just "British").
HOLIDAY_ABBREVIATIONS = {
    "New Year's Day": "New Year's",
    "Family Day": "Family",
    "Good Friday": "Good Fri.",
    "Victoria Day": "Victoria",
    "Canada Day": "Canada",
    "British Columbia Day": "BC Day",
    "Labour Day": "Labour",
    "National Day for Truth and Reconciliation": "Reconcil.",
    "Thanksgiving": "Thanksgiv.",
    "Remembrance Day": "Remembr.",
    "Christmas Day": "Christmas",
    "Boxing Day": "Boxing",
    "Easter Monday": "Easter",
}


def short_holiday_label(name, max_len=9):
    if name in HOLIDAY_ABBREVIATIONS:
        return HOLIDAY_ABBREVIATIONS[name]
    first_word = name.split(" ", 1)[0]
    if len(first_word) <= max_len:
        return first_word
    return first_word[: max_len - 1] + "…"


def build_weeks(year, month, items_by_date):
    cal = calendar.Calendar(firstweekday=0)  # Monday-first, matches the old view
    today = date.today()
    weeks = []
    for week in cal.monthdatescalendar(year, month):
        row = []
        for d in week:
            iso = d.strftime("%Y-%m-%d")
            names = items_by_date.get(iso, [])
            is_holiday = bool(names)
            row.append(
                {
                    "day": d.day,
                    "in_month": d.month == month,
                    "is_today": d == today,
                    "is_holiday": is_holiday,
                    "holiday_short": short_holiday_label(names[0]) if is_holiday else None,
                    # Sunday is the configured weekly rest day (matches the
                    # old plugin's "weekly holiday day" setting) — Saturday
                    # renders as a normal day, only Sunday + holidays dim.
                    "is_dim": d.weekday() == 6 or is_holiday,
                }
            )
        weeks.append(row)
    return weeks


def unfold_ics_lines(text):
    # RFC 5545: a line starting with a space or tab is a continuation of the
    # previous line and must be joined without the leading whitespace.
    lines = text.replace("\r\n", "\n").split("\n")
    unfolded = []
    for line in lines:
        if line[:1] in (" ", "\t") and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def unescape_ics_text(value):
    return (
        value.replace("\\n", " ")
        .replace("\\N", " ")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def parse_ics_date(value):
    # DTSTART values look like "20260802" (all-day) or "20260802T130000Z"
    # (timed) — we only care about the calendar date for a monthly grid.
    return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))


def expand_rrule(start, freq, interval, window_end):
    # Handles the recurrence patterns realistic for a personal/family
    # calendar (yearly birthdays, weekly standing plans). COUNT/UNTIL/BYDAY
    # aren't parsed — recurrences just run to the window edge.
    occurrences = []
    current = start
    guard = 0
    while current <= window_end and guard < 800:
        guard += 1
        if current >= start:
            occurrences.append(current)
        if freq == "YEARLY":
            try:
                current = current.replace(year=current.year + interval)
            except ValueError:  # Feb 29 in a non-leap year
                current = current.replace(year=current.year + interval, day=28)
        elif freq == "MONTHLY":
            month_index = current.month - 1 + interval
            year = current.year + month_index // 12
            month = month_index % 12 + 1
            day = min(current.day, calendar.monthrange(year, month)[1])
            current = date(year, month, day)
        elif freq == "WEEKLY":
            current = current + timedelta(weeks=interval)
        elif freq == "DAILY":
            current = current + timedelta(days=interval)
        else:
            break
    return occurrences


def parse_ics_events(ics_text, window_start, window_end):
    events = []
    lines = unfold_ics_lines(ics_text)
    in_event = False
    dtstart = None
    summary = None
    rrule = None
    for line in lines:
        if line.startswith("BEGIN:VEVENT"):
            in_event, dtstart, summary, rrule = True, None, None, None
            continue
        if line.startswith("END:VEVENT"):
            if dtstart:
                title = unescape_ics_text(summary) if summary else "(untitled)"
                if rrule:
                    freq = rrule.get("FREQ", "")
                    interval = int(rrule.get("INTERVAL", "1"))
                    for occ in expand_rrule(dtstart, freq, interval, window_end):
                        if window_start <= occ <= window_end:
                            events.append({"date": occ.isoformat(), "name": title})
                elif window_start <= dtstart <= window_end:
                    events.append({"date": dtstart.isoformat(), "name": title})
            in_event = False
            continue
        if not in_event or ":" not in line:
            continue
        key, _, value = line.partition(":")
        prop = key.split(";", 1)[0]
        if prop == "DTSTART":
            dtstart = parse_ics_date(value)
        elif prop == "SUMMARY":
            summary = value
        elif prop == "RRULE":
            rrule = dict(part.split("=", 1) for part in value.split(";") if "=" in part)
    return events


def fetch_ics_events(ics_url, window_start, window_end):
    if not ics_url:
        return []
    try:
        body = urllib.request.urlopen(ics_url, timeout=10).read().decode("utf-8", errors="replace")
        return parse_ics_events(body, window_start, window_end)
    except Exception:
        # A transient fetch/parse failure shouldn't take down the holiday
        # calendar — just show holidays until the next successful refresh.
        return []


def run(input):
    today = date.today()
    # trmnlp's local dev server wraps an array-root polling response as
    # {"data": [...]}; some production responses pass the raw array directly.
    raw_holidays = input["data"] if isinstance(input, dict) else input
    holidays = [h for h in raw_holidays if is_relevant(h)]
    # A date can carry more than one relevant holiday (e.g. a national and a
    # regional one falling on the same day), so each date maps to a list.
    items_by_date = {}
    for h in holidays:
        items_by_date.setdefault(h["date"], []).append(h["localName"])

    custom_fields = (
        input.get("trmnl", {}).get("plugin_settings", {}).get("custom_fields_values", {})
        if isinstance(input, dict)
        else {}
    )
    ics_url = custom_fields.get("gcal_ics_url")
    window_start = date(today.year, 1, 1)
    window_end = date(today.year + 1, 12, 31)
    for ev in fetch_ics_events(ics_url, window_start, window_end):
        items_by_date.setdefault(ev["date"], []).append(ev["name"])

    for f1_date, f1_label in F1_2026_EVENTS:
        items_by_date.setdefault(f1_date, []).append(f1_label)

    weeks = build_weeks(today.year, today.month, items_by_date)

    # Chronological, future-only (today included), spanning any month —
    # each date contributes one badge line plus one line per item name, at
    # a fixed text size, so the count that fits is capped per layout rather
    # than shrinking the font to squeeze more in.
    upcoming_items = sorted(
        (
            {"date": d, "names": names}
            for d, names in items_by_date.items()
            if d >= today.isoformat()
        ),
        key=lambda h: h["date"],
    )
    for h in upcoming_items:
        h["short_date"] = date.fromisoformat(h["date"]).strftime("%b %-d (%A)")

    return {
        "month_label": today.strftime("%B").upper(),
        "month_short": today.strftime("%b").upper(),
        "year": today.year,
        "weekday_labels": ["M", "T", "W", "T", "F", "S", "S"],
        "weeks": weeks,
        "upcoming_items": upcoming_items[:MAX_ITEMS],
    }
