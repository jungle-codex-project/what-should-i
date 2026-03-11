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


def normalize_ocr_line(line):
    replacements = {
        "고객 명": "고객명",
        "고객 번호": "고객번호",
        "전화 번호": "전화번호",
        "청구 금액": "청구금액",
        "결제 금액": "결제금액",
        "청구 일자": "청구일자",
        "결제 일시": "결제일시",
        "진료 상담비": "진료상담비",
        "신 체 검사": "신체검사",
        "초 음 파": "초음파",
        "내 복 약": "내복약",
        "동 물": "동물",
        "의 료": "의료",
        "의료 센터": "의료센터",
        "대표 원장": "대표원장",
        "방 문": "방문",
        "처 방": "처방",
    }

    line = normalize_whitespace(line)
    if not line:
        return ""

    tokens = line.split()
    merged_tokens = []
    index = 0
    while index < len(tokens):
        if re.fullmatch(r"[가-힣]", tokens[index]):
            run = [tokens[index]]
            next_index = index + 1
            while next_index < len(tokens) and re.fullmatch(r"[가-힣]", tokens[next_index]):
                run.append(tokens[next_index])
                next_index += 1

            if len(run) >= 2:
                merged_tokens.append("".join(run))
            else:
                merged_tokens.append(run[0])
            index = next_index
            continue

        merged_tokens.append(tokens[index])
        index += 1

    normalized = " ".join(merged_tokens)
    for before, after in replacements.items():
        normalized = normalized.replace(before, after)

    normalized = re.sub(r"(\d{2,4})\s*-\s*(\d{1,2})\s*-\s*(\d{1,2})", r"\1-\2-\3", normalized)
    normalized = re.sub(r"([가-힣])\s*:\s*", r"\1: ", normalized)
    return normalize_whitespace(normalized)


def normalize_ocr_text(text):
    lines = [normalize_ocr_line(line) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


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
