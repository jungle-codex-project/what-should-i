import json
import re

import requests

from app.utils import (
    clean_multiline_text,
    compact_text,
    extract_date_candidates,
    normalize_whitespace,
    strip_code_fence,
)


class DocumentParser:
    DOCUMENT_TYPE_KEYWORDS = {
        "medical_receipt": [
            "결제내역",
            "진료비",
            "수납",
            "영수증",
            "청구금액",
            "결제금액",
            "진료상담비",
            "내복약",
            "검사",
            "병원비",
            "medical receipt",
        ],
        "medical_certificate": ["진단서", "진료확인서", "의사소견서", "medical certificate"],
        "funeral_certificate": ["장례", "부고", "사망", "funeral"],
        "competition_participation": ["대회", "참가확인", "competition", "contest", "참가증"],
        "counseling_confirmation": ["상담", "심리", "counseling", "상담확인서"],
    }
    ORGANIZATION_SUFFIXES = [
        "동물의료센터",
        "의료센터",
        "대학병원",
        "병원",
        "의원",
        "한의원",
        "치과",
        "클리닉",
        "센터",
        "대학교",
        "학교",
        "협회",
        "학회",
        "재단",
        "hospital",
        "clinic",
        "center",
    ]

    def __init__(self, api_key="", model="gpt-4.1-mini", api_url=""):
        self.api_key = api_key
        self.model = model
        self.api_url = api_url

    def parse(self, text):
        cleaned_text = clean_multiline_text(text)
        if not cleaned_text:
            return self._finalize(
                {
                    "name": "",
                    "document_type": "unknown",
                    "organization": "",
                    "issue_date": "",
                    "valid_period": "",
                },
                source="empty",
            )

        if self.api_key:
            parsed = self._parse_with_llm(cleaned_text)
            if parsed:
                return self._finalize(parsed, source="llm")

        return self._finalize(self._parse_with_heuristics(cleaned_text), source="heuristic")

    def _parse_with_llm(self, text):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "당신은 학사 결석 증빙 문서를 구조화하는 파서입니다. "
                        "문서 유형은 medical_certificate, medical_receipt, "
                        "funeral_certificate, competition_participation, "
                        "counseling_confirmation, unknown 중 하나를 사용하세요. "
                        "반드시 JSON 객체만 반환하세요. 키는 name, document_type, "
                        "organization, issue_date, valid_period 입니다."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "다음 OCR 텍스트를 읽고 구조화된 JSON을 반환하세요.\n\n"
                        f"{text[:5000]}"
                    ),
                },
            ],
        }

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=45,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(strip_code_fence(content))
            return {
                "name": parsed.get("name", ""),
                "document_type": parsed.get("document_type", "unknown"),
                "organization": parsed.get("organization", ""),
                "issue_date": parsed.get("issue_date", ""),
                "valid_period": parsed.get("valid_period", ""),
            }
        except Exception:
            return None

    def _parse_with_heuristics(self, text):
        normalized = normalize_whitespace(text)
        document_type = self._infer_document_type(normalized)
        issue_date = self._extract_issue_date(text)
        valid_period = self._extract_valid_period(text, issue_date, document_type)
        return {
            "name": self._extract_name(text),
            "document_type": document_type,
            "organization": self._extract_organization(text),
            "issue_date": issue_date,
            "valid_period": valid_period,
        }

    def _extract_name(self, text):
        patterns = [
            r"(?:고객명|고객\s*명|환자명|보호자명|성명|이름|학생명|name)\s*[:：]?\s*([A-Za-z가-힣 ]{2,30}?)(?=\s*(?:전화번호|주소|고객번호|생년월일|주민번호|$|\n))",
            r"(?:본인|대상자)\s*[:：]?\s*([A-Za-z가-힣 ]{2,30})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return normalize_whitespace(match.group(1))
        return ""

    def _extract_organization(self, text):
        patterns = [
            r"(?:발급기관|병원명|기관명|주최기관|상담기관|organization)\s*[:：]?\s*([^\n]{2,80})",
            r"([^\n]{1,80}(?:동물의료센터|의료센터|대학병원|병원|의원|한의원|치과|클리닉|센터))",
            r"([^\n]{1,80}(?:hospital|clinic|center|university|association|foundation))",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return normalize_whitespace(match.group(1))

        for line in text.splitlines()[:12]:
            compact_line = normalize_whitespace(line)
            if any(suffix.lower() in compact_line.lower() for suffix in self.ORGANIZATION_SUFFIXES):
                return compact_line[:80]
        return ""

    def _extract_issue_date(self, text):
        labeled_patterns = [
            r"(?:발급일|발행일|작성일|결제일시|결제일|진료일|진료일자|청구일자|방문일|내원일|issue date)\s*[:：]?\s*([^\n]+)",
        ]
        for pattern in labeled_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_candidate = self._first_date_candidate(match.group(1))
                if date_candidate:
                    return date_candidate

        datetime_match = re.search(
            r"(\d{4}[./-]\d{1,2}[./-]\d{1,2}\s*(?:오전|오후|AM|PM|am|pm)?\s*\d{1,2}:\d{2}(?::\d{2})?)",
            text,
        )
        if datetime_match:
            date_candidate = self._first_date_candidate(datetime_match.group(1))
            if date_candidate:
                return date_candidate

        candidates = extract_date_candidates(text)
        return self._first_date_candidate("\n".join(candidates))

    def _extract_valid_period(self, text, issue_date, document_type):
        patterns = [
            r"(?:유효기간|진료기간|참가일시|참가기간|기간)\s*[:：]?\s*([^\n]+)",
            r"((?:\d{4}[./-]\d{1,2}[./-]\d{1,2}|\d{4}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일).{0,10}[~-].{0,10}(?:\d{4}[./-]\d{1,2}[./-]\d{1,2}|\d{4}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일))",
            r"(?:청구일자|진료일|내원일)\s*[:：]?\s*([^\n]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                if document_type == "medical_receipt":
                    receipt_date = self._first_date_candidate(candidate)
                    if receipt_date:
                        return receipt_date
                    continue
                return candidate

        if document_type == "medical_receipt" and issue_date:
            return issue_date
        return ""

    def _infer_document_type(self, text):
        lowered = text.lower()
        compact_lowered = compact_text(lowered)

        medical_receipt_signals = [
            "결제내역",
            "청구금액",
            "결제금액",
            "진료상담비",
            "영수증",
        ]
        if any(compact_text(signal.lower()) in compact_lowered for signal in medical_receipt_signals):
            if any(suffix.lower() in compact_lowered for suffix in self.ORGANIZATION_SUFFIXES):
                return "medical_receipt"

        for document_type, keywords in self.DOCUMENT_TYPE_KEYWORDS.items():
            for keyword in keywords:
                if compact_text(keyword.lower()) in compact_lowered:
                    return document_type
        return "unknown"

    def _first_date_candidate(self, text):
        if not text:
            return ""

        for candidate in extract_date_candidates(text):
            date_match = re.search(
                r"\d{4}[./-]\d{1,2}[./-]\d{1,2}|\d{4}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일|\d{2}[./-]\d{1,2}[./-]\d{1,2}",
                candidate,
            )
            if date_match:
                return normalize_whitespace(date_match.group(0))
        return ""

    def _finalize(self, parsed, source):
        normalized = {
            "name": str(parsed.get("name", "")).strip(),
            "document_type": str(parsed.get("document_type", "unknown")).strip() or "unknown",
            "organization": str(parsed.get("organization", "")).strip(),
            "issue_date": str(parsed.get("issue_date", "")).strip(),
            "valid_period": str(parsed.get("valid_period", "")).strip(),
            "parser_source": source,
        }

        if (
            normalized["document_type"] == "medical_receipt"
            and not normalized["valid_period"]
            and normalized["issue_date"]
        ):
            normalized["valid_period"] = normalized["issue_date"]

        filled_fields = 0
        for field in ["name", "organization", "issue_date", "valid_period"]:
            filled_fields += 1 if normalized.get(field) else 0
        if normalized.get("document_type") and normalized["document_type"] != "unknown":
            filled_fields += 1

        base_score = 0.75 if source == "llm" else 0.5
        if source == "empty":
            base_score = 0.1
        normalized["parser_confidence"] = round(
            min(0.99, base_score + (filled_fields * 0.05)),
            2,
        )
        return normalized
