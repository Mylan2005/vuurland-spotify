"""v260 offline regression: named-remix search rescue, no unsafe approvals."""
from pathlib import Path
import unittest
from v260_named_remix_search import original_search_hint as hint
from v243_remix_fallback import safe_remix_original_fallback as allowed


class RemixRescueTests(unittest.TestCase):
    def test_requested_mr_little_jeans(self):
        self.assertEqual(
            hint("Mr. Little Jeans", "Oh Sailor (Strange Talk Remix)", "Mr Little Jeans"),
            'Mr Little Jeans "Oh Sailor"',
        )
        self.assertEqual(
            hint("Sunday Girl", "Love U More (RAC Mix)", "Sunday Girl"),
            'Sunday Girl "Love U More"',
        )

    def test_no_broad_remix_or_unrelated_version_rescues(self):
        for title in (
            "Oh Sailor", "Oh Sailor (Remix)", "Oh Sailor (Live)",
            "Oh Sailor (Acoustic)", "Oh Sailor (Studio Version)",
            "Oh Sailor (Album Mix)", "Oh Sailor (Original Mix)",
            "Oh Sailor (Radio Mix)", "Oh Sailor (Club Mix)",
            "Oh Sailor (Extended Mix)", "Oh Sailor (Strange Talk Remix) Extra",
            "A (RAC Remix)",
        ):
            self.assertIsNone(hint("Mr Little Jeans", title, "Mr Little Jeans"), title)

    def test_still_forbidden_on_first_search_and_wrong_version(self):
        args = dict(requested_version="remix", candidate_version=None,
                    primary_artist_exact=True, all_credits_present=True,
                    requested_base="oh sailor", candidate_base="Oh Sailor")
        self.assertFalse(allowed(**args, search_variant=0))
        self.assertTrue(allowed(**args, search_variant=1))
        self.assertFalse(allowed(**{**args, "candidate_version":"live"}, search_variant=1))
        self.assertFalse(allowed(**{**args, "candidate_base":"Another song"}, search_variant=1))
        self.assertFalse(allowed(**{**args, "primary_artist_exact":False}, search_variant=1))

    def test_source_wiring_without_more_searches(self):
        source=Path("vuurland_sync.py").read_text(encoding="utf-8")
        self.assertIn("from v260_named_remix_search import original_search_hint", source)
        self.assertIn("_v260_hint = original_search_hint(artist, title, spotify_search_artist)", source)
        self.assertIn("if search_variant >= 1:", source)
        self.assertIn("SPOTIFY_SEARCH_HTTP_LIMIT = 1", source)
        self.assertIn("safe_remix_original_fallback(", source)
        self.assertIn("max_additions_per_round = 1", source)


if __name__=="__main__":
    unittest.main()
