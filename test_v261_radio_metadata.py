"""Regression tests for conservative, reusable radio metadata cleanups."""
import unittest

from v233_general_radio_metadata import normalize_radio_metadata


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
