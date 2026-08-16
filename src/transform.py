import calendar
from datetime import date

# Matches the region already configured on the community "Simple Calendar"
# plugin this replaces, so behavior stays consistent.
REGION = "CA-BC"


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


def build_weeks(year, month, holidays_by_date):
    cal = calendar.Calendar(firstweekday=0)  # Monday-first, matches the old view
    today = date.today()
    weeks = []
    for week in cal.monthdatescalendar(year, month):
        row = []
        for d in week:
            iso = d.strftime("%Y-%m-%d")
            names = holidays_by_date.get(iso, [])
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


def run(input):
    today = date.today()
    # trmnlp's local dev server wraps an array-root polling response as
    # {"data": [...]}; some production responses pass the raw array directly.
    raw_holidays = input["data"] if isinstance(input, dict) else input
    holidays = [h for h in raw_holidays if is_relevant(h)]
    # A date can carry more than one relevant holiday (e.g. a national and a
    # regional one falling on the same day), so each date maps to a list.
    holidays_by_date = {}
    for h in holidays:
        holidays_by_date.setdefault(h["date"], []).append(h["localName"])

    weeks = build_weeks(today.year, today.month, holidays_by_date)

    month_holidays = sorted(
        (
            {"date": d, "names": names}
            for d, names in holidays_by_date.items()
            if d[:7] == today.isoformat()[:7]
        ),
        key=lambda h: h["date"],
    )
    for h in month_holidays:
        h_date = date.fromisoformat(h["date"])
        h["short_date"] = h_date.strftime("%b %-d")
        h["is_past"] = h_date < today

    upcoming = sorted(
        (
            {"date": d, "name": ", ".join(names)}
            for d, names in holidays_by_date.items()
            if d >= today.isoformat()
        ),
        key=lambda h: h["date"],
    )
    for h in upcoming:
        h["short_date"] = date.fromisoformat(h["date"]).strftime("%b %-d")

    # Each date contributes one badge line plus one line per holiday name.
    # Past ~6 lines, text--large starts clipping the bottom half on half_vertical,
    # so drop to text--small to fit a busier month instead of cutting entries off.
    holiday_lines = len(month_holidays) + sum(len(h["names"]) for h in month_holidays)
    holiday_text_class = "text--large" if holiday_lines <= 6 else "text--small"

    return {
        "month_label": today.strftime("%B").upper(),
        "month_short": today.strftime("%b").upper(),
        "year": today.year,
        "weekday_labels": ["M", "T", "W", "T", "F", "S", "S"],
        "weeks": weeks,
        "upcoming": upcoming[:3],
        "month_holidays": month_holidays,
        "holiday_text_class": holiday_text_class,
    }
