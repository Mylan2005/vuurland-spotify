"""Only owner-confirmed release substitutions, never a generic remix fallback."""


def owner_approved_album_version(artist, title):
    """Use the ordinary album recording for the unavailable Ambient Mix."""
    if (str(artist or "").strip().casefold() == "the cure"
            and str(title or "").strip().casefold()
            == "this is a lie (ambient mix)"):
        return "This Is a Lie"
    return title
