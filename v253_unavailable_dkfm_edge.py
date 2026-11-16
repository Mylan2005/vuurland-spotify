"""Owner-confirmed non-Spotify recording, scoped strictly to DKFM Edge."""


def skip_unavailable_dkfm_edge_recording(source, artist, title):
    return (
        str(source or "").strip().casefold() == "dkfm_edge"
        and str(artist or "").strip().casefold() == "the veldt"
        and " ".join(str(title or "").strip().casefold().split()) == "angel heart"
    )
