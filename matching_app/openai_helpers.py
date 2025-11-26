import base64
import json
import mimetypes
import os
import re
from io import BytesIO
from typing import Dict, Iterable, Tuple

from PIL import Image, UnidentifiedImageError

import openai
from django.conf import settings
from rest_framework.exceptions import APIException

from .models import UserProfile

DEFAULT_MODEL = 'gpt-4o-mini'
VISION_MODEL = 'gpt-4.1-mini'
TEMPERATURE = 0.75
MAX_TOKENS = 220


def _get_openai_api_key() -> str:
    return os.getenv('OPENAI_API_KEY') or getattr(settings, 'OPENAI_API_KEY', None)


def _profile_detail_lines(profile: UserProfile) -> Iterable[str]:
    detail_map: Dict[str, str] = {
        'Candidate name': profile.candidate_name,
        'Profile for': profile.profile_for,
        'Gender': profile.gender,
        'Marital status': profile.marital_status,
        'Country': profile.country,
        'City': profile.city,
        'Religion': profile.religion,
        'Sect': profile.sect,
        'Caste': profile.caste,
        'Height': f"{profile.height_cm} cm" if profile.height_cm else None,
        'Weight': f"{profile.weight_kg} kg" if profile.weight_kg else None,
        'Education': profile.education_level,
        'Employment': profile.employment_status,
        'Profession': profile.profession,
        'Father status': profile.father_status,
        'Father employment': profile.father_employment_status,
        'Mother status': profile.mother_status,
        'Mother employment': profile.mother_employment_status,
        'Siblings (brothers)': (
            str(profile.total_brothers) if profile.total_brothers else None
        ),
        'Siblings (sisters)': (
            str(profile.total_sisters) if profile.total_sisters else None
        ),
    }
    for label, value in detail_map.items():
        if value:
            yield f"{label}: {value}"


def _build_openai_messages(profile: UserProfile) -> list[dict[str, str]]:
    user_reference = profile.candidate_name or profile.user.first_name or profile.user.username or f"user-{profile.id}"
    detail_lines = list(_profile_detail_lines(profile))

    detail_text = (
        '\n'.join(detail_lines)
        if detail_lines
        else 'No additional profile details were provided.'
    )

    system_content = (
        "You are a creative writer crafting short (3-4 line) dating profile descriptions "
        "for a modern matchmaking app. Keep the tone warm, confident, and respectful. "
        "Avoid clichés, avoid mentioning AI, and do not hallucinate personal details."
    )
    user_content = (
        f"Write a unique and friendly dating description for {user_reference}. "
        "Use the profile facts below to ground your reply. "
        "Deliver the response as plain text only, with 3 to 4 sentences.\n\n"
        f"Profile facts (keep the tone natural):\n{detail_text}"
    )

    return [
        {'role': 'system', 'content': system_content},
        {'role': 'user', 'content': user_content},
    ]


def generate_profile_description(profile: UserProfile) -> str:
    api_key = _get_openai_api_key()
    if not api_key:
        raise APIException(
            'OpenAI API key is not configured. '
            'Set the OPENAI_API_KEY env variable to enable AI-generated descriptions.'
        )

    client = openai.OpenAI(api_key=api_key)

    try:
        completion = client.chat.completions.create(
            model=DEFAULT_MODEL,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            messages=_build_openai_messages(profile),
        )
    except Exception as exc:
        raise APIException(f'Failed to generate AI description: {exc}')

    try:
        choice = completion.choices[0]
        message = choice.message
        generated = getattr(message, 'content', None)
        if isinstance(generated, list):
            generated = '\n'.join(generated)
        if generated:
            generated = generated.strip()
        else:
            raise AttributeError('No content returned.')
    except (IndexError, AttributeError) as exc:
        raise APIException('OpenAI returned an unexpected response structure.') from exc

    if not generated:
        raise APIException('OpenAI returned an empty description.')

    return generated


def _serialize_image_to_data_uri(image_bytes: bytes, filename: str | None = None) -> str:
    """
    Convert binary image data into a data URI so it can be passed directly to OpenAI Vision.
    """
    if not image_bytes:
        raise APIException('No image data was provided for validation.')

    # Try to infer the mime type from the filename first, then from the raw byte stream.
    mime_type, _ = mimetypes.guess_type(filename or '') if filename else (None, None)
    if not mime_type:
        try:
            with Image.open(BytesIO(image_bytes)) as img:
                image_format = img.format
        except UnidentifiedImageError as exc:
            raise APIException('The uploaded file is not a valid image.') from exc
        mime_type = Image.MIME.get(image_format, 'image/jpeg')

    encoded = base64.b64encode(image_bytes).decode('ascii')
    return f'data:{mime_type};base64,{encoded}'


def _vision_prompt_instructions() -> str:
    return (
        "You are an automated trust & safety reviewer for dating profile photos. "
        "Strictly allow an image only if it shows exactly one real human face without any "
        "filters, ai-generation artifacts, cartoons, drawings, pets, animals, scenery, memes, "
        "screenshots, objects, or explicit/NSFW content. Reject anything suspicious, including "
        "deepfakes, heavily edited selfies, or content that could belong to more than one person."
    )


def _vision_user_request() -> str:
    return (
        "Analyze the attached profile picture candidate. Determine whether it shows exactly one "
        "real human face and complies with the safety policy. Reasons to reject include: no person, "
        "multiple people, minors, pets, animals, objects, scenery, memes, screenshots, AI/digital art, "
        "cartoons/anime, filters, deepfakes, NSFW/explicit nudity, or anything unsafe. "
        "Respond using ONLY strict JSON in the following shape:\n"
        '{"allowed": true|false, "reason": "short explanation"}'
    )


def _extract_text_from_response(response) -> str:
    """
    Pull the first text segment out of the Responses API payload.
    """
    data = response.model_dump()
    for block in data.get('output', []):
        for content in block.get('content', []):
            if content.get('type') == 'output_text':
                text = content.get('text', '')
                if isinstance(text, list):
                    return ''.join(segment.get('text', '') for segment in text)
                return text
    # Fall back to legacy structures if present.
    output_text = data.get('output_text')
    if isinstance(output_text, list) and output_text:
        return ''.join(output_text)
    if isinstance(output_text, str):
        return output_text
    raise APIException('OpenAI Vision response did not include any text output.')


def _parse_validation_result(raw_text: str) -> Tuple[bool, str]:
    """
    Parse the JSON payload returned by the model and normalize the response.
    """
    if not raw_text:
        raise APIException('OpenAI Vision returned an empty response.')
    match = re.search(r'\{.*\}', raw_text, re.DOTALL)
    candidate = match.group(0) if match else raw_text
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise APIException(f'OpenAI Vision returned non-JSON output: {raw_text}') from exc

    allowed = bool(parsed.get('allowed'))
    reason = str(parsed.get('reason') or '').strip() or (
        'Model rejected the image without providing a reason.'
    )
    return allowed, reason


def validate_profile_photo(image_bytes: bytes, filename: str | None = None) -> Tuple[bool, str]:
    """
    Run the uploaded photo through OpenAI Vision and return (allowed, reason).
    """
    api_key = _get_openai_api_key()
    if not api_key:
        raise APIException(
            'OpenAI API key is not configured. '
            'Set the OPENAI_API_KEY env variable to enable photo validation.'
        )

    client = openai.OpenAI(api_key=api_key)
    data_uri = _serialize_image_to_data_uri(image_bytes, filename)

    try:
        response = client.responses.create(
            model=VISION_MODEL,
            input=[
                {
                    'role': 'system',
                    'content': [
                        {'type': 'input_text', 'text': _vision_prompt_instructions()},
                    ],
                },
                {
                    'role': 'user',
                    'content': [
                        {'type': 'input_text', 'text': _vision_user_request()},
                        {'type': 'input_image', 'image_url': data_uri},
                    ],
                },
            ],
        )
    except Exception as exc:
        raise APIException(f'Failed to validate profile photo: {exc}')

    raw_text = _extract_text_from_response(response)
    return _parse_validation_result(raw_text)

