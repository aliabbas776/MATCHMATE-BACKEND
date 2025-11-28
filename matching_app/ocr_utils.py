import re
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import Optional

from PIL import Image, ImageFilter, ImageStat
from .openai_helpers import extract_cnic_details_from_images

CNIC_REGEX = re.compile(r'\b\d{5}-\d{7}-\d\b')
DATE_PATTERNS = [
    '%d-%m-%Y',
    '%d/%m/%Y',
    '%Y-%m-%d',
]

@dataclass
class CNICExtractionResult:
    full_name: Optional[str]
    cnic_number: Optional[str]
    date_of_birth: Optional[datetime]
    gender: Optional[str]
    blur_score: float
    tampering_detected: bool
    raw_front_text: str
    raw_back_text: str


def _load_image_from_bytes(image_bytes: bytes) -> Image.Image:
    image = Image.open(BytesIO(image_bytes))
    if image.mode not in ('L', 'RGB'):
        image = image.convert('RGB')
    return image


def _estimate_blur(image: Image.Image) -> float:
    # Use variance of Laplacian approximation via FIND_EDGES filter
    edges = image.convert('L').filter(ImageFilter.FIND_EDGES)
    variance = ImageStat.Stat(edges).var[0]
    return variance


def _extract_cnic_number(text: str) -> Optional[str]:
    match = CNIC_REGEX.search(text.replace(' ', ''))
    if match:
        raw = match.group(0)
        return f'{raw[:5]}-{raw[5:12]}-{raw[-1]}'
    return None


def _normalize_cnic_number(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digits = re.sub(r'\D', '', value)
    if len(digits) == 13:
        return f'{digits[:5]}-{digits[5:12]}-{digits[-1]}'
    return _extract_cnic_number(value)


def _extract_dob(text: str) -> Optional[datetime]:
    cleaned = text.replace(' ', '')
    for delimiter in ('-', '/'):
        pattern = re.compile(r'\d{2}%s\d{2}%s\d{4}' % (re.escape(delimiter), re.escape(delimiter)))
        match = pattern.search(cleaned)
        if match:
            value = match.group(0)
            for fmt in DATE_PATTERNS:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
    return None


def _extract_gender(text: str) -> Optional[str]:
    lowered = text.lower()
    if 'female' in lowered:
        return 'female'
    if 'male' in lowered:
        return 'male'
    if 'm' in lowered and 'f' not in lowered:
        return 'male'
    if 'f' in lowered and 'm' not in lowered:
        return 'female'
    return None


def _extract_full_name(text: str) -> Optional[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidates = [line for line in lines if any(char.isalpha() for char in line)]
    for line in candidates:
        tokens = re.sub(r'[^A-Za-z\s]', '', line).strip()
        token_count = len(tokens.split())
        if token_count >= 2 and tokens.isascii():
            return tokens.title()
    return candidates[0].title() if candidates else None


def _parse_iso_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def analyze_cnic_images(front_bytes: bytes, back_bytes: bytes) -> CNICExtractionResult:
    front_image = _load_image_from_bytes(front_bytes)
    back_image = _load_image_from_bytes(back_bytes)

    ai_payload = extract_cnic_details_from_images(front_bytes, back_bytes)
    front_text = ai_payload.get('raw_front_text', '')
    back_text = ai_payload.get('raw_back_text', '')

    blur_score_front = _estimate_blur(front_image)
    blur_score_back = _estimate_blur(back_image)
    blur_score = min(blur_score_front, blur_score_back)
    tampering = blur_score < 5 or front_image.width < 600 or back_image.width < 600

    combined_text = f'{front_text}\n{back_text}'

    full_name = ai_payload.get('full_name') or _extract_full_name(front_text)
    cnic_number = _normalize_cnic_number(ai_payload.get('cnic_number')) or _extract_cnic_number(combined_text)
    dob = _parse_iso_date(ai_payload.get('date_of_birth')) or _extract_dob(combined_text)
    gender = ai_payload.get('gender') or _extract_gender(combined_text)

    result = CNICExtractionResult(
        full_name=full_name,
        cnic_number=cnic_number,
        date_of_birth=dob,
        gender=gender,
        blur_score=blur_score,
        tampering_detected=tampering,
        raw_front_text=front_text,
        raw_back_text=back_text,
    )
    return result

