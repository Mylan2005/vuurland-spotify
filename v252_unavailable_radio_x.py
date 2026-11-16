"""User-confirmed unavailable Radio X Chilled recording.

Keep this an exact-source/exact-song exclusion, not a global artist ban.
RadioBox can truncate the final closing parenthesis.
"""
import re


def skip_unavailable_radio_x_recording(source, artist, title):
    if str(source or "").strip().casefold() != "radio_x_chilled":
        return False
    if str(artist or "").strip().casefold() != "brooke combe":
        return False
    value = " ".join(str(title or "").strip().casefold().split())
    return bool(re.fullmatch(
        r"broken stones\s*\(live at on the beach\)?",
        value,
    ))
