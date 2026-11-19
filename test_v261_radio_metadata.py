"""Regression tests for conservative, reusable radio metadata cleanups."""
import unittest

from v233_general_radio_metadata import normalize_radio_metadata
from v255_catalog_rescue import catalog_metadata


class RadioMetadataRegressionTests(unittest.TestCase):
    def test_export_filename_has_full_song_title(self):
        self.assertEqual(
            normalize_radio_metadata("DARKSIDE", "05 Im The Echo 16bit 1.11.21"),
            ("DARKSIDE", "I'm The Echo"),
        )

    def test_thousands_separator_is_not_a_different_song(self):
        self.assertEqual(
            normalize_radio_metadata("Tahiti 80", "1.000 Times"),
            ("Tahiti 80", "1000 Times"),
        )
        self.assertEqual(
            normalize_radio_metadata("Example", "Song 1.2"),
            ("Example", "Song 1.2"),
        )

    def test_trailing_guest_becomes_required_credit(self):
        self.assertEqual(
            normalize_radio_metadata("Stereo MCs", "Boy Feat. Jamie Cullum (Album)"),
            ("Stereo MCs feat. Jamie Cullum", "Boy"),
        )
        self.assertEqual(
            normalize_radio_metadata("Kleintierschaukel", "Nous ft. Juliette C Mayr"),
            ("Kleintierschaukel feat. Juliette C Mayr", "Nous"),
        )

    def test_remix_is_preserved(self):
        self.assertEqual(
            normalize_radio_metadata(
                "Just Emma", "Sunshine ft. Matthias Wittmann (Thomas Atzmann Remix)"
            ),
            ("Just Emma feat. Matthias Wittmann", "Sunshine (Thomas Atzmann Remix)"),
        )

    def test_verified_catalog_corrections_are_narrow(self):
        self.assertEqual(catalog_metadata("Cocteau Twins", "Pearly-Dewdrops"),
                         ("Cocteau Twins", "Pearly-Dewdrops' Drops"))
        self.assertEqual(catalog_metadata("AIR", "Radio No.1"),
                         ("AIR", "Radio Number 1"))
        self.assertEqual(catalog_metadata("Beatsteakes", "Let Me In"),
                         ("Beatsteaks", "Let Me In"))
        self.assertEqual(catalog_metadata("Jon Batiste feat. Zazie Smith", "SHOW ME THE WAY"),
                         ("Jon Batiste feat. Zadie Smith", "SHOW ME THE WAY"))
        self.assertEqual(catalog_metadata("Koffee", "Pull Up"),
                         ("Original Koffee", "Pull Up"))
        self.assertEqual(catalog_metadata("Koffee", "Some Other Song"),
                         ("Koffee", "Some Other Song"))

    def test_london_grammar_exact_radio_typo(self):
        self.assertEqual(
            catalog_metadata("London Grammer", "Dancing By The Night"),
            ("London Grammar", "Dancing By Night"),
        )
        for artist, title in (
            ("London Grammer", "Dancing By Night (Live)"),
            ("London Grammer", "Dancing By The Night (Remix)"),
            ("London Grammar", "Dancing By The Night (Extended Mix)"),
            ("Other Artist", "Dancing By The Night"),
        ):
            self.assertEqual(catalog_metadata(artist, title), (artist, title))

    def test_justice_truncated_multi_guest_not_dropped(self):
        self.assertEqual(
            normalize_radio_metadata(
                "Justice", "Flower in a Hurricane (f Tame Impala, SZA, King Gizzard...)"
            ),
            ("Justice feat. Tame Impala, SZA, King Gizzard...", "Flower in a Hurricane"),
        )

    def test_short_radio_parenthesized_feature(self):
        self.assertEqual(
            normalize_radio_metadata("beabadoobee", "All I Did Was Dream of You (f The Marías)"),
            ("beabadoobee feat. The Marías", "All I Did Was Dream of You"),
        )
        self.assertEqual(
            normalize_radio_metadata("The Chemical Brothers", "Go (f Q-Tip)"),
            ("The Chemical Brothers feat. Q-Tip", "Go"),
        )
        self.assertEqual(
            normalize_radio_metadata("Charli xcx", "The girl, so confusing (f Lorde)"),
            ("Charli xcx feat. Lorde", "The girl, so confusing"),
        )

    def test_broadcast_country_context_only(self):
        self.assertEqual(
            normalize_radio_metadata("Fink (UK)", "Berlin Sunrise"),
            ("Fink", "Berlin Sunrise"),
        )
        self.assertEqual(
            normalize_radio_metadata("Claire Holley (USA)", "Go Away Now"),
            ("Claire Holley", "Go Away Now"),
        )
        self.assertEqual(
            normalize_radio_metadata("Boards of Canada (Live)", "Test"),
            ("Boards of Canada (Live)", "Test"),
        )

    def test_never_invent_song_or_strip_edition(self):
        self.assertEqual(
            normalize_radio_metadata("Hatchie", "August"),
            ("Hatchie", "August"),
        )
        self.assertEqual(
            normalize_radio_metadata("Birdy", "1901 (Phoenix Cover)"),
            ("Birdy", "1901 (Phoenix Cover)"),
        )
        self.assertEqual(
            normalize_radio_metadata("Swirlies", "Cousteau"),
            ("Swirlies", "Cousteau"),
        )
        self.assertEqual(
            normalize_radio_metadata("A.R. Kane", "Crack Up (Album Version)"),
            ("A.R. Kane", "Crack Up (Album Version)"),
        )
        self.assertEqual(
            normalize_radio_metadata("Dead Can Dance", "Tristan / Sanvean"),
            ("Dead Can Dance", "Tristan / Sanvean"),
        )

    def test_cannot_invent_missing_word_or_merge_two_tracks(self):
        self.assertEqual(
            normalize_radio_metadata("Cosmic Cowboys", "If You Leave Tonigh ft. Lazarusman"),
            ("Cosmic Cowboys feat. Lazarusman", "If You Leave Tonigh"),
        )
        self.assertEqual(
            normalize_radio_metadata(
                "Dead Can Dance", "The Carnival Is Over / Ariadne (Remastered)"
            ),
            ("Dead Can Dance", "The Carnival Is Over / Ariadne (Remastered)"),
        )

    def test_existing_safe_labels_are_unchanged(self):
        self.assertEqual(
            normalize_radio_metadata("Donavon Frankenreiter & Jack Johnson", "Free"),
            ("Donavon Frankenreiter & Jack Johnson", "Free"),
        )
        self.assertEqual(
            normalize_radio_metadata("Example", "Some Song (Live)"),
            ("Example", "Some Song (Live)"),
        )


if __name__ == "__main__":
    unittest.main()
