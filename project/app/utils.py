import re
from datetime import datetime


def allowed_file(filename, allowed_extensions):
    if not filename or "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in allowed_extensions


def clean_multiline_text(text):
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def normalize_whitespace(text):
    return re.sub(r"\s+", " ", text).strip()


def compact_text(text):
    return re.sub(r"\s+", "", text or "")


def strip_code_fence(text):
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9_-]*", "", stripped).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    return stripped


def extract_date_candidates(text):
    patterns = [
        r"\d{4}[./-]\d{1,2}[./-]\d{1,2}\s*(?:오전|오후|AM|PM|am|pm)?\s*\d{1,2}:\d{2}(?::\d{2})?",
        r"\d{4}[./-]\d{1,2}[./-]\d{1,2}",
        r"\d{4}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일",
        r"\d{2}[./-]\d{1,2}[./-]\d{1,2}",
        r"\d{1,2}[./-]\d{1,2}[./-]\d{4}",
    ]
    matches = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text))

    deduped = []
    for item in matches:
        if item not in deduped:
            deduped.append(item)
    return deduped


def parse_date_string(value):
    if not value:
        return None

    raw = value.strip()
    candidates = [raw] + extract_date_candidates(raw)
    for candidate in candidates:
        cleaned = candidate.strip()
        cleaned = re.sub(
            r"(오전|오후|AM|PM|am|pm)\s*\d{1,2}:\d{2}(?::\d{2})?",
            "",
            cleaned,
        )
        cleaned = re.sub(r"\d{1,2}:\d{2}(?::\d{2})?", "", cleaned)
        cleaned = cleaned.replace("년", "-").replace("월", "-").replace("일", "")
        cleaned = cleaned.replace(".", "-").replace("/", "-")
        cleaned = re.sub(r"\s+", "", cleaned)
        cleaned = re.sub(r"-+", "-", cleaned).strip("-")

        for fmt in ("%Y-%m-%d", "%m-%d-%Y", "%d-%m-%Y", "%y-%m-%d"):
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                continue
    return None


def parse_period_bounds(value):
    if not value:
        return None, None

    candidates = extract_date_candidates(value)
    parsed_dates = [parse_date_string(item) for item in candidates]
    parsed_dates = [item for item in parsed_dates if item]
    if not parsed_dates:
        single_date = parse_date_string(value)
        return single_date, None
    if len(parsed_dates) == 1:
        return parsed_dates[0], None
    return parsed_dates[0], parsed_dates[1]


def dedupe_lines(lines):
    unique_lines = []
    seen = set()
    for line in lines:
        cleaned = normalize_whitespace(line)
        if not cleaned:
            continue
        key = compact_text(cleaned.lower())
        if key in seen:
            continue
        seen.add(key)
        unique_lines.append(cleaned)
    return unique_lines
