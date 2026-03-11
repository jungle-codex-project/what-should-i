from pathlib import Path

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


def _dedupe_lines(lines):
    unique_lines = []
    seen = set()
    for line in lines:
        cleaned = " ".join(line.split())
        if not cleaned:
            continue
        key = "".join(cleaned.lower().split())
        if key in seen:
            continue
        seen.add(key)
        unique_lines.append(cleaned)
    return unique_lines


class OCRService:
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
    FULL_PAGE_CONFIG = "--oem 3 --psm 6 -c preserve_interword_spaces=1"
    SPARSE_CONFIG = "--oem 3 --psm 11 -c preserve_interword_spaces=1"
    REGION_CONFIG = "--oem 3 --psm 6 -c preserve_interword_spaces=1"

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
        ocr_texts = []

        try:
            images = convert_from_path(
                file_path,
                first_page=1,
                last_page=self.max_pages,
            )
            for image in images:
                ocr_texts.append(self._extract_from_pil_image(image))
        except Exception:
            ocr_texts = []

        combined_ocr = self._merge_texts(ocr_texts)
        if combined_ocr:
            return combined_ocr

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
        variants = self._build_variants(base_image)

        ocr_texts = [
            self._ocr_image_to_string(variants["enhanced"], self.FULL_PAGE_CONFIG),
            self._ocr_image_to_string(variants["threshold"], self.SPARSE_CONFIG),
            self._ocr_image_to_lines(variants["threshold"], self.FULL_PAGE_CONFIG),
        ]

        if variants.get("line_removed") is not None:
            ocr_texts.append(
                self._ocr_image_to_lines(variants["line_removed"], self.REGION_CONFIG)
            )

        for cropped_image in self._build_region_crops(variants["threshold"]):
            ocr_texts.append(self._ocr_image_to_lines(cropped_image, self.REGION_CONFIG))

        merged = self._merge_texts(ocr_texts)
        if merged:
            return merged

        return _clean_multiline_text(
            self._ocr_image_to_string(ImageOps.grayscale(base_image), self.FULL_PAGE_CONFIG)
        )

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
        grayscale = ImageEnhance.Contrast(grayscale).enhance(1.8)
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

    def _build_region_crops(self, image):
        width, height = image.size
        regions = [
            (0.0, 0.0, 1.0, 0.18),
            (0.0, 0.16, 1.0, 0.34),
            (0.0, 0.28, 1.0, 0.58),
            (0.0, 0.54, 1.0, 0.82),
            (0.0, 0.78, 0.62, 1.0),
            (0.48, 0.78, 1.0, 1.0),
        ]
        cropped_images = []
        for left_ratio, top_ratio, right_ratio, bottom_ratio in regions:
            cropped_images.append(
                image.crop(
                    (
                        int(width * left_ratio),
                        int(height * top_ratio),
                        int(width * right_ratio),
                        int(height * bottom_ratio),
                    )
                )
            )
        return cropped_images

    def _ocr_image_to_string(self, image, config):
        try:
            text = pytesseract.image_to_string(
                image,
                lang=self.language,
                config=config,
            )
        except pytesseract.TesseractNotFoundError as exc:
            raise RuntimeError(
                "Tesseract OCR이 설치되어 있지 않습니다. tesseract-ocr와 한국어 데이터 파일을 설치해 주세요."
            ) from exc
        return _clean_multiline_text(text)

    def _ocr_image_to_lines(self, image, config):
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

        lines = []
        current_key = None
        current_words = []

        for index, token in enumerate(data.get("text", [])):
            token = token.strip()
            if not token:
                continue

            confidence = self._parse_confidence(data.get("conf", ["-1"])[index])
            if confidence != -1 and confidence < 18 and not any(char.isdigit() for char in token):
                continue

            line_key = (
                data.get("block_num", [0])[index],
                data.get("par_num", [0])[index],
                data.get("line_num", [0])[index],
            )

            if current_key is None:
                current_key = line_key

            if line_key != current_key:
                lines.append(" ".join(current_words))
                current_key = line_key
                current_words = [token]
            else:
                current_words.append(token)

        if current_words:
            lines.append(" ".join(current_words))

        return _clean_multiline_text("\n".join(lines))

    def _parse_confidence(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return -1

    def _merge_texts(self, texts):
        lines = []
        for text in texts:
            if not text:
                continue
            lines.extend(_clean_multiline_text(text).splitlines())
        return "\n".join(_dedupe_lines(lines))
