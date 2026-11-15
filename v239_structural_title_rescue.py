"""v239: reusable, conservative RadioBox title-spelling rescue.

Only search hints and narrowly provable *structural* equivalences.
Never approve a Spotify URI, change artist credits, change requested versions,
or make extra HTTP requests. The regular matcher enforces all other gates.
"""
import re
import unicodedata

_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def _fold(value):
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", text)


def _number_annotation(title):
    match = re.fullmatch(r"\s*(\d{1,2})\s*\(\s*([A-Za-z]+)\s*\)\s*", str(title or ""))
    if match and _NUMBERS.get(match.group(2).lower()) == int(match.group(1)):
        return match.group(1)
    return None


def _extended_theme_parts(title):
    # "Stranger Things Theme (Extended)" vs "Stranger Things - Extended":
    # require TWO meaningful words preceding Theme; not "Theme (Extended)".
    match = re.fullmatch(
        r"\s*(.*?)\s+Theme\s*(?:\(\s*Extended\s*\)|[-–—]\s*Extended)\s*",
        str(title or ""), re.I,
    )
    if not match:
        return None
    words = re.findall(r"[\w]+", match.group(1), flags=re.UNICODE)
    if len(words) < 2 or len(_fold(match.group(1))) < 8:
        return None
    return match.group(1).strip()


def _extended_plain_parts(title):
    match = re.fullmatch(
        r"\s*(.*?)\s*(?:\(\s*Extended\s*\)|[-–—]\s*Extended)\s*",
        str(title or ""), re.I,
    )
    if not match:
        return None
    return match.group(1).strip()


def safe_search_title(artist, title, variant):
    """Alternative title only on an existing retry search, not an extra call."""
    if int(variant or 0) == 0:
        return None
    text = str(title or "").strip()
    if not text:
        return None
    theme = _extended_theme_parts(text)
    if theme:
        return theme + " Extended"
    annotation = _number_annotation(text)
    if annotation:
        return annotation
    # RadioBox sometimes translates a possessive apostrophe into -s-.
    # This is a QUERY hint only, never proof of identical recordings.
    if re.search(r"(?i)[a-z]-s-[a-z]", text):
        return re.sub(r"(?i)([A-Za-z])-s-(?=[A-Za-z])", r"\1's ", text)
    # The original/extended qualifiers remain mandatory for acceptance.
    if re.search(r"(?i)\(\s*original\s*\)\s*$", text):
        return re.sub(r"(?i)\s*\(\s*original\s*\)\s*$", "", text).strip()
    return None


def structural_recording_equivalent(requested, candidate, *, primary_artist_exact,
                                    requested_version, candidate_version):
    """Only two high-proof title-structure cases, with strict version identity."""
    if not primary_artist_exact or requested_version != candidate_version:
        return False
    left, right = str(requested or "").strip(), str(candidate or "").strip()
    if not left or not right:
        return False
    annotation = _number_annotation(left)
    if annotation is not None:
        return _fold(right) == _fold(annotation)
    annotation = _number_annotation(right)
    if annotation is not None:
        return _fold(left) == _fold(annotation)
    if requested_version != "extended":
        return False
    left_theme, right_theme = _extended_theme_parts(left), _extended_theme_parts(right)
    left_plain, right_plain = _extended_plain_parts(left), _extended_plain_parts(right)
    return bool(
        (left_theme and right_plain and _fold(left_theme) == _fold(right_plain))
        or (right_theme and left_plain and _fold(right_theme) == _fold(left_plain))
    )
