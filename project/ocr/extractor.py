from pathlib import Path
import re

try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover - optional runtime dependency
    cv2 = None
    np = None

import pytesseract
from pytesseract import Output
from pdf2image import convert_from_path
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from pypdf import PdfReader


def _clean_multiline_text(text):
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _compact_text(text):
    return re.sub(r"\s+", "", text or "")


def _normalize_ocr_line(line):
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

    line = _clean_multiline_text(line)
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
    return _clean_multiline_text(normalized)


def _dedupe_lines(lines):
    unique_lines = []
    seen = set()
    for line in lines:
        cleaned = _normalize_ocr_line(line)
        if not cleaned:
            continue
        key = _compact_text(cleaned.lower())
        if key in seen:
            continue
        seen.add(key)
        unique_lines.append(cleaned)
    return unique_lines


class OCRService:
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
    ROTATION_CANDIDATES = (0, 180)

    FULL_PAGE_CONFIG = "--oem 3 --psm 6 -c preserve_interword_spaces=1"
    SPARSE_CONFIG = "--oem 3 --psm 11 -c preserve_interword_spaces=1"
    REGION_CONFIG = "--oem 3 --psm 6 -c preserve_interword_spaces=1"
    DENSE_REGION_CONFIG = "--oem 3 --psm 4 -c preserve_interword_spaces=1"

    CORE_KEYWORDS = [
        "결제내역",
        "고객명",
        "전화번호",
        "청구금액",
        "결제금액",
        "청구일자",
        "결제일시",
        "진료상담비",
        "초음파",
        "내복약",
        "병원",
        "의료센터",
        "센터",
    ]
    ORGANIZATION_HINTS = [
        "동물의료센터",
        "의료센터",
        "대학병원",
        "병원",
        "의원",
        "한의원",
        "클리닉",
        "센터",
    ]
    REGION_LAYOUT = [
        {
            "name": "organization",
            "bbox": (0.0, 0.0, 1.0, 0.15),
            "variants": ("enhanced", "threshold"),
            "configs": ("--oem 3 --psm 6 -c preserve_interword_spaces=1",),
        },
        {
            "name": "identity",
            "bbox": (0.0, 0.18, 1.0, 0.33),
            "variants": ("threshold", "line_removed", "enhanced"),
            "configs": (
                "--oem 3 --psm 6 -c preserve_interword_spaces=1",
                "--oem 3 --psm 11 -c preserve_interword_spaces=1",
            ),
        },
        {
            "name": "datetime",
            "bbox": (0.0, 0.30, 0.78, 0.45),
            "variants": ("threshold", "line_removed", "enhanced"),
            "configs": (
                "--oem 3 --psm 6 -c preserve_interword_spaces=1",
                "--oem 3 --psm 11 -c preserve_interword_spaces=1",
            ),
        },
        {
            "name": "summary",
            "bbox": (0.0, 0.42, 1.0, 0.61),
            "variants": ("line_removed", "threshold"),
            "configs": (
                "--oem 3 --psm 6 -c preserve_interword_spaces=1",
                "--oem 3 --psm 4 -c preserve_interword_spaces=1",
            ),
        },
        {
            "name": "table",
            "bbox": (0.0, 0.58, 1.0, 0.78),
            "variants": ("line_removed", "threshold"),
            "configs": (
                "--oem 3 --psm 6 -c preserve_interword_spaces=1",
                "--oem 3 --psm 11 -c preserve_interword_spaces=1",
            ),
        },
    ]
    REGION_KEYWORDS = {
        "organization": ["병원", "센터", "의료센터", "전화", "주소"],
        "identity": ["고객명", "환자명", "전화번호", "주소", "고객번호"],
        "datetime": ["결제일시", "청구일자", "오전", "오후", "진료일", "내원일"],
        "summary": ["청구금액", "결제금액", "공급가액", "부가세", "결제"],
        "table": ["청구일자", "진료상담비", "검사", "초음파", "내복약"],
        "page": ["결제내역", "고객명", "청구금액", "결제금액", "전화번호"],
        "document": ["결제내역", "고객명", "청구금액", "결제금액", "병원", "센터"],
    }
    REGION_WEIGHTS = {
        "organization": 2.2,
        "identity": 2.0,
        "datetime": 2.3,
        "summary": 1.6,
        "table": 0.7,
    }
    DATE_PATTERN = re.compile(
        r"\d{4}[./-]\d{1,2}[./-]\d{1,2}|\d{2}[./-]\d{1,2}[./-]\d{1,2}|\d{4}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일"
    )
    AMOUNT_PATTERN = re.compile(r"\d{1,3}(?:,\d{3})+|\d{4,}")

    def __init__(self, language="kor+eng", max_pages=3):
        self.language = language
        self.max_pages = max_pages

    def extract_text(self, file_path):
        path = Path(file_path)
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return self._extract_from_pdf(path)
        if suffix in self.IMAGE_EXTENSIONS:
            return self._extract_from_image(path)
        raise ValueError("OCR이 지원하지 않는 파일 형식입니다.")

    def _extract_from_image(self, file_path):
        with Image.open(file_path) as image:
            return self._extract_from_pil_image(image)

    def _extract_from_pdf(self, file_path):
        page_texts = []

        try:
            images = convert_from_path(
                file_path,
                first_page=1,
                last_page=self.max_pages,
            )
            for image in images:
                page_texts.append(self._extract_from_pil_image(image))
        except Exception:
            page_texts = []

        combined_ocr = "\n".join(text for text in page_texts if text)
        if combined_ocr:
            return _clean_multiline_text(combined_ocr)

        try:
            reader = PdfReader(str(file_path))
            extracted = []
            for page in reader.pages[: self.max_pages]:
                extracted.append(page.extract_text() or "")
            return _clean_multiline_text("\n".join(extracted))
        except Exception as exc:
            raise RuntimeError(
                "PDF OCR 처리에 실패했습니다. Tesseract와 Poppler 설치를 확인해 주세요."
            ) from exc

    def _extract_from_pil_image(self, image):
        base_image = ImageOps.exif_transpose(image).convert("RGB")
        orientation_candidates = []

        for angle in self.ROTATION_CANDIDATES:
            oriented = base_image if angle == 0 else base_image.rotate(angle, expand=True)
            variants = self._build_variants(oriented)
            full_page_candidate = self._select_best_full_page_candidate(variants, angle)
            region_candidates = self._select_priority_region_candidates(variants, angle)
            assembled_text = self._assemble_document_text(full_page_candidate, region_candidates)
            assembled_score = self._score_text(
                assembled_text,
                full_page_candidate["avg_conf"],
                region_name="document",
            )
            total_score = full_page_candidate["score"] + assembled_score
            for region_name, candidate in region_candidates.items():
                total_score += candidate["score"] * self.REGION_WEIGHTS.get(region_name, 1.0)

            orientation_candidates.append(
                {
                    "angle": angle,
                    "text": assembled_text,
                    "score": total_score,
                }
            )

        best_candidate = self._pick_best_candidate(orientation_candidates)
        if best_candidate and best_candidate.get("text"):
            return best_candidate["text"]

        fallback = self._build_variants(base_image)
        return self._build_candidate(
            fallback["enhanced"],
            self.FULL_PAGE_CONFIG,
            region_name="page",
            source="fallback",
        )["text"]

    def _select_best_full_page_candidate(self, variants, angle):
        candidates = [
            self._build_candidate(
                variants["enhanced"],
                self.FULL_PAGE_CONFIG,
                region_name="page",
                source=f"page-enhanced@{angle}",
            ),
            self._build_candidate(
                variants["threshold"],
                self.FULL_PAGE_CONFIG,
                region_name="page",
                source=f"page-threshold@{angle}",
            ),
            self._build_candidate(
                variants["threshold"],
                self.SPARSE_CONFIG,
                region_name="page",
                source=f"page-sparse@{angle}",
            ),
        ]
        if variants.get("line_removed") is not None:
            candidates.append(
                self._build_candidate(
                    variants["line_removed"],
                    self.DENSE_REGION_CONFIG,
                    region_name="page",
                    source=f"page-line-removed@{angle}",
                )
            )
        return self._pick_best_candidate(candidates)

    def _select_priority_region_candidates(self, variants, angle):
        selected = {}

        for spec in self.REGION_LAYOUT:
            candidates = []
            for variant_name in spec["variants"]:
                variant_image = variants.get(variant_name)
                if variant_image is None:
                    continue

                region_image = self._crop_region(variant_image, spec["bbox"])
                for config in spec["configs"]:
                    candidates.append(
                        self._build_candidate(
                            region_image,
                            config,
                            region_name=spec["name"],
                            source=f"{spec['name']}:{variant_name}@{angle}",
                        )
                    )

            best_candidate = self._pick_best_candidate(candidates)
            if best_candidate and best_candidate.get("text"):
                selected[spec["name"]] = best_candidate

        return selected

    def _build_variants(self, image):
        prepared = self._upscale_image(image)
        enhanced = self._enhance_with_pil(prepared)

        if cv2 is None or np is None:
            threshold = enhanced.point(lambda pixel: 255 if pixel > 170 else 0).convert("L")
            return {
                "enhanced": enhanced,
                "threshold": threshold,
                "line_removed": threshold,
            }

        cv_image = cv2.cvtColor(np.array(prepared), cv2.COLOR_RGB2BGR)
        grayscale = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        grayscale = cv2.fastNlMeansDenoising(grayscale, None, 10, 7, 21)
        grayscale = self._deskew(grayscale)
        normalized = cv2.normalize(grayscale, None, 0, 255, cv2.NORM_MINMAX)

        threshold = cv2.adaptiveThreshold(
            normalized,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            15,
        )
        threshold = cv2.medianBlur(threshold, 3)
        line_removed = self._remove_table_lines(threshold)

        return {
            "enhanced": Image.fromarray(normalized),
            "threshold": Image.fromarray(threshold),
            "line_removed": Image.fromarray(line_removed),
        }

    def _enhance_with_pil(self, image):
        grayscale = ImageOps.grayscale(image)
        grayscale = ImageOps.autocontrast(grayscale)
        grayscale = ImageEnhance.Contrast(grayscale).enhance(1.9)
        grayscale = grayscale.filter(ImageFilter.SHARPEN)
        return grayscale

    def _upscale_image(self, image):
        width, height = image.size
        if width >= 1800:
            return image

        ratio = 1800 / max(width, 1)
        return image.resize(
            (int(width * ratio), int(height * ratio)),
            Image.Resampling.LANCZOS,
        )

    def _deskew(self, grayscale_image):
        if cv2 is None or np is None:
            return grayscale_image

        coordinates = np.column_stack(np.where(grayscale_image < 220))
        if len(coordinates) < 1000:
            return grayscale_image

        angle = cv2.minAreaRect(coordinates)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        if abs(angle) < 0.2 or abs(angle) > 12:
            return grayscale_image

        height, width = grayscale_image.shape[:2]
        matrix = cv2.getRotationMatrix2D((width // 2, height // 2), angle, 1.0)
        return cv2.warpAffine(
            grayscale_image,
            matrix,
            (width, height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=255,
        )

    def _remove_table_lines(self, binary_image):
        if cv2 is None:
            return binary_image

        inverted = 255 - binary_image
        height, width = binary_image.shape[:2]
        horizontal_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (max(30, width // 24), 1),
        )
        vertical_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (1, max(30, height // 24)),
        )

        horizontal_lines = cv2.morphologyEx(inverted, cv2.MORPH_OPEN, horizontal_kernel)
        vertical_lines = cv2.morphologyEx(inverted, cv2.MORPH_OPEN, vertical_kernel)
        table_lines = cv2.add(horizontal_lines, vertical_lines)
        cleaned = cv2.subtract(inverted, table_lines)
        return 255 - cleaned

    def _crop_region(self, image, bbox):
        width, height = image.size
        left_ratio, top_ratio, right_ratio, bottom_ratio = bbox
        return image.crop(
            (
                int(width * left_ratio),
                int(height * top_ratio),
                int(width * right_ratio),
                int(height * bottom_ratio),
            )
        )

    def _build_candidate(self, image, config, region_name, source):
        line_data = self._ocr_image_to_line_data(image, config)
        filtered_lines = self._filter_noise_lines(line_data, region_name)
        text = "\n".join(item["text"] for item in filtered_lines)
        average_confidence = 0.0
        if filtered_lines:
            average_confidence = sum(item["confidence"] for item in filtered_lines) / len(filtered_lines)

        score = self._score_text(text, average_confidence, region_name)
        return {
            "text": text,
            "score": score,
            "avg_conf": round(average_confidence, 2),
            "source": source,
            "region": region_name,
        }

    def _ocr_image_to_line_data(self, image, config):
        try:
            data = pytesseract.image_to_data(
                image,
                lang=self.language,
                config=config,
                output_type=Output.DICT,
            )
        except pytesseract.TesseractNotFoundError as exc:
            raise RuntimeError(
                "Tesseract OCR이 설치되어 있지 않습니다. tesseract-ocr와 한국어 데이터 파일을 설치해 주세요."
            ) from exc

        buckets = {}
        total_tokens = len(data.get("text", []))
        for index in range(total_tokens):
            token = (data["text"][index] or "").strip()
            if not token:
                continue

            line_key = (
                data["block_num"][index],
                data["par_num"][index],
                data["line_num"][index],
            )
            bucket = buckets.setdefault(line_key, {"words": [], "confs": []})
            bucket["words"].append(token)

            confidence = self._parse_confidence(data["conf"][index])
            if confidence >= 0:
                bucket["confs"].append(confidence)

        line_data = []
        for line_key in sorted(buckets):
            words = buckets[line_key]["words"]
            if not words:
                continue
            confidence_values = buckets[line_key]["confs"]
            average_confidence = (
                sum(confidence_values) / len(confidence_values)
                if confidence_values
                else 0.0
            )
            line_data.append(
                {
                    "text": _clean_multiline_text(" ".join(words)),
                    "confidence": average_confidence,
                }
            )

        return line_data

    def _filter_noise_lines(self, line_data, region_name):
        region_keywords = self.REGION_KEYWORDS.get(region_name, [])
        filtered = []
        seen = set()

        for line in line_data:
            text = _normalize_ocr_line(line["text"])
            compact = _compact_text(text.lower())
            if not text or compact in seen:
                continue

            if not self._should_keep_line(text, line["confidence"], region_name, region_keywords):
                continue

            seen.add(compact)
            filtered.append(
                {
                    "text": text,
                    "confidence": line["confidence"],
                }
            )

        return filtered

    def _should_keep_line(self, text, confidence, region_name, region_keywords):
        compact = _compact_text(text.lower())
        hangul_count = len(re.findall(r"[가-힣]", text))
        digit_count = len(re.findall(r"\d", text))
        latin_count = len(re.findall(r"[A-Za-z]", text))
        weird_count = len(re.findall(r"[`'\"~_=|<>^]", text))
        keyword_hit = self._contains_any(compact, region_keywords) or self._contains_any(
            compact,
            self.CORE_KEYWORDS,
        )
        meaningful_chars = hangul_count + digit_count + latin_count

        if meaningful_chars == 0:
            return False
        if len(compact) < 2:
            return False
        if confidence < 8 and not keyword_hit and digit_count < 2:
            return False
        if region_name != "table" and confidence < 14 and not keyword_hit and not self.DATE_PATTERN.search(text):
            return False
        if latin_count > meaningful_chars * 0.65 and hangul_count == 0 and digit_count < 3 and not keyword_hit:
            return False
        if weird_count > max(2, meaningful_chars * 0.4) and not keyword_hit:
            return False
        if region_name == "organization":
            return self._contains_any(compact, self.ORGANIZATION_HINTS) or keyword_hit
        if region_name == "identity":
            return keyword_hit or self._contains_any(compact, ["고객명", "환자명", "전화번호", "주소"])
        if region_name == "datetime":
            return keyword_hit or bool(self.DATE_PATTERN.search(text)) or digit_count >= 8
        if region_name == "summary":
            return keyword_hit or bool(self.AMOUNT_PATTERN.search(text))
        if region_name == "table":
            return keyword_hit or (digit_count >= 6 and hangul_count >= 2)
        return True

    def _score_text(self, text, average_confidence, region_name):
        if not text:
            return -1000.0

        compact = _compact_text(text.lower())
        lines = text.splitlines()
        keyword_hits = self._count_keyword_hits(compact, self.CORE_KEYWORDS)
        region_hits = self._count_keyword_hits(
            compact,
            self.REGION_KEYWORDS.get(region_name, []),
        )

        field_hits = 0
        if self.DATE_PATTERN.search(text):
            field_hits += 1
        if self.AMOUNT_PATTERN.search(text):
            field_hits += 1
        if self._contains_any(compact, self.ORGANIZATION_HINTS):
            field_hits += 1
        if self._contains_any(compact, ["고객명", "환자명", "전화번호", "주소"]):
            field_hits += 1

        hangul_count = len(re.findall(r"[가-힣]", text))
        digit_count = len(re.findall(r"\d", text))
        latin_count = len(re.findall(r"[A-Za-z]", text))
        weird_count = len(re.findall(r"[`'\"~_=|<>^]", text))

        score = average_confidence / 12.0
        score += keyword_hits * 3.8
        score += region_hits * 3.0
        score += field_hits * 2.5
        score += min(len(lines), 6) * 0.8
        score += min(hangul_count, 80) / 18.0
        score += min(digit_count, 40) / 25.0

        if region_name == "organization":
            score += 4.5 if self._contains_any(compact, self.ORGANIZATION_HINTS) else -2.0
            score -= digit_count * 0.03
        elif region_name == "identity":
            score += 3.0 if self._contains_any(compact, ["고객명", "환자명", "전화번호", "주소"]) else -1.0
        elif region_name == "datetime":
            score += 4.0 if self.DATE_PATTERN.search(text) else -3.0
            if self._contains_any(compact, ["결제일시", "청구일자", "진료일", "내원일", "오전", "오후"]):
                score += 2.0
        elif region_name == "summary":
            score += 3.0 if self._contains_any(compact, ["청구금액", "결제금액", "공급가액", "부가세"]) else -1.0
        elif region_name == "table":
            score += 2.0 if self._contains_any(compact, ["청구일자", "진료상담비", "검사", "초음파", "내복약"]) else 0.0
        elif region_name in {"page", "document"}:
            if self._contains_any(compact, ["결제내역", "고객명", "청구금액", "결제금액"]):
                score += 2.5

        if latin_count > hangul_count + digit_count and keyword_hits == 0 and region_hits == 0:
            score -= 8.0
        score -= weird_count * 0.8
        score -= self._count_low_quality_lines(lines) * 1.3

        return score

    def _assemble_document_text(self, full_page_candidate, region_candidates):
        ordered_lines = []

        for region_name in ["organization", "identity", "datetime", "summary", "table"]:
            candidate = region_candidates.get(region_name)
            if candidate and candidate.get("text"):
                ordered_lines.extend(candidate["text"].splitlines())

        if full_page_candidate and full_page_candidate.get("text"):
            ordered_lines.extend(full_page_candidate["text"].splitlines())

        filtered_lines = []
        for line in _dedupe_lines(ordered_lines):
            if self._should_keep_document_line(line):
                filtered_lines.append(line)

        return "\n".join(filtered_lines[:40])

    def _should_keep_document_line(self, line):
        compact = _compact_text(line.lower())
        hangul_count = len(re.findall(r"[가-힣]", line))
        digit_count = len(re.findall(r"\d", line))
        latin_count = len(re.findall(r"[A-Za-z]", line))
        weird_count = len(re.findall(r"[`'\"~_=|<>^]", line))

        if not compact:
            return False
        if self._contains_any(compact, self.CORE_KEYWORDS) or self._contains_any(
            compact,
            self.ORGANIZATION_HINTS,
        ):
            return True
        if self.DATE_PATTERN.search(line) or self.AMOUNT_PATTERN.search(line):
            return True
        if self._contains_any(compact, ["고객명", "환자명", "전화번호", "주소"]):
            return True
        if weird_count > max(2, (hangul_count + digit_count + latin_count) * 0.5):
            return False
        if latin_count > hangul_count + digit_count and digit_count < 3:
            return False
        return hangul_count >= 2 or digit_count >= 6

    def _pick_best_candidate(self, candidates):
        valid_candidates = [candidate for candidate in candidates if candidate is not None]
        if not valid_candidates:
            return None
        return max(valid_candidates, key=lambda candidate: candidate.get("score", -1000.0))

    def _contains_any(self, compact_text, keywords):
        return any(_compact_text(keyword.lower()) in compact_text for keyword in keywords)

    def _count_keyword_hits(self, compact_text, keywords):
        return sum(1 for keyword in keywords if _compact_text(keyword.lower()) in compact_text)

    def _count_low_quality_lines(self, lines):
        penalty = 0
        for line in lines:
            compact = _compact_text(line)
            hangul_count = len(re.findall(r"[가-힣]", line))
            digit_count = len(re.findall(r"\d", line))
            latin_count = len(re.findall(r"[A-Za-z]", line))
            weird_count = len(re.findall(r"[`'\"~_=|<>^]", line))

            if len(compact) < 3:
                penalty += 1
            elif weird_count > max(2, (hangul_count + digit_count + latin_count) * 0.5):
                penalty += 1
            elif latin_count > hangul_count + digit_count and digit_count < 3:
                penalty += 1
        return penalty

    def _parse_confidence(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return -1.0
