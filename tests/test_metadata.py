from __future__ import annotations

import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from ani_cli_sync.metadata import (
    CharacterProfile,
    SeriesMetadata,
    extract_active_characters,
    resolve_series_metadata,
)
from ani_cli_sync.subtitles import VTTCue

SAMPLE_ANILIST_RESPONSE = {
    "data": {
        "Media": {
            "id": 16498,
            "title": {
                "romaji": "Shingeki no Kyojin",
                "english": "Attack on Titan",
                "native": "進撃の巨人",
            },
            "description": "Centuries ago, mankind was slaughtered to near extinction...",
            "characters": {
                "edges": [
                    {
                        "role": "MAIN",
                        "node": {
                            "name": {
                                "userPreferred": "Eren Yeager",
                                "alternative": ["Eren Jäger"],
                            },
                            "gender": "Male",
                        },
                    },
                    {
                        "role": "MAIN",
                        "node": {
                            "name": {
                                "userPreferred": "Armin Arlert",
                                "alternative": [],
                            },
                            "gender": "Male",
                        },
                    },
                    {
                        "role": "MAIN",
                        "node": {
                            "name": {
                                "userPreferred": "Mikasa Ackerman",
                                "alternative": [],
                            },
                            "gender": "Female",
                        },
                    },
                    {
                        "role": "SUPPORTING",
                        "node": {
                            "name": {
                                "userPreferred": "Hange Zoë",
                                "alternative": ["Hans"],
                            },
                            "gender": "Non-binary",
                        },
                    },
                ]
            },
        }
    }
}


class TestCharacterProfile(unittest.TestCase):
    def test_format_card(self):
        char = CharacterProfile(
            name="Armin Arlert",
            gender="male",
            role="MAIN",
            aliases=("Armin", "Arlert"),
        )
        self.assertEqual(char.format_card(), "Armin Arlert (male)")

    def test_format_card_unspecified_gender(self):
        char = CharacterProfile(
            name="Mystery Character",
            gender=None,
            role="SUPPORTING",
        )
        self.assertEqual(char.format_card(), "Mystery Character (unspecified)")


class TestSeriesMetadata(unittest.TestCase):
    def test_serialization_roundtrip(self):
        char = CharacterProfile(
            name="Eren Yeager",
            gender="male",
            role="MAIN",
            aliases=("Eren", "Yeager"),
        )
        meta = SeriesMetadata(
            media_id=16498,
            title_romaji="Shingeki no Kyojin",
            title_english="Attack on Titan",
            synopsis="Titans attack humans.",
            characters=[char],
        )
        meta_dict = meta.to_dict()
        restored = SeriesMetadata.from_dict(meta_dict)
        self.assertEqual(restored.media_id, 16498)
        self.assertEqual(restored.title_english, "Attack on Titan")
        self.assertEqual(restored.canonical_title, "Attack on Titan")
        self.assertEqual(len(restored.characters), 1)
        self.assertEqual(restored.characters[0].name, "Eren Yeager")
        self.assertEqual(restored.characters[0].gender, "male")
        self.assertEqual(restored.characters[0].aliases, ("Eren", "Yeager"))


class TestExtractActiveCharacters(unittest.TestCase):
    def setUp(self):
        self.eren = CharacterProfile("Eren Yeager", "male", "MAIN", ("Eren", "Yeager"))
        self.armin = CharacterProfile(
            "Armin Arlert", "male", "MAIN", ("Armin", "Arlert")
        )
        self.mikasa = CharacterProfile(
            "Mikasa Ackerman", "female", "MAIN", ("Mikasa", "Ackerman")
        )
        self.characters = [self.eren, self.armin, self.mikasa]

    def test_extract_active_matches_alias(self):
        cues = [
            VTTCue("1", "00:00:01.000 --> 00:00:03.000", ["Armin, behind you!"]),
            VTTCue("2", "00:00:04.000 --> 00:00:06.000", ["I'm on it!"]),
        ]
        active = extract_active_characters(cues, self.characters)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].name, "Armin Arlert")

    def test_extract_active_multiple_characters(self):
        cues = [
            VTTCue(
                "1", "00:00:01.000 --> 00:00:03.000", ["Mikasa and Eren, let's go!"]
            ),
        ]
        active = extract_active_characters(cues, self.characters)
        self.assertEqual(len(active), 2)
        names = [c.name for c in active]
        self.assertIn("Eren Yeager", names)
        self.assertIn("Mikasa Ackerman", names)
        self.assertNotIn("Armin Arlert", names)

    def test_extract_active_no_false_positive_on_short_substring(self):
        # A 2-letter token or substring should not trigger false positives
        char_al = CharacterProfile("Al Phone", "male", "SUPPORTING", ("Al",))
        cues = [VTTCue("1", "00:00:01.000 --> 00:00:03.000", ["All of us are ready."])]
        active = extract_active_characters(cues, [char_al])
        self.assertEqual(active, [])

    def test_extract_empty_when_no_match(self):
        cues = [
            VTTCue("1", "00:00:01.000 --> 00:00:03.000", ["The weather is nice today."])
        ]
        active = extract_active_characters(cues, self.characters)
        self.assertEqual(active, [])


class TestResolveSeriesMetadata(unittest.TestCase):
    def test_resolve_series_metadata_fetches_and_caches(self):
        with (
            tempfile.TemporaryDirectory() as td,
            patch.dict(os.environ, {"XDG_CACHE_HOME": td}),
            patch("ani_cli_sync.metadata._execute_graphql") as mock_gql,
        ):
            mock_gql.return_value = SAMPLE_ANILIST_RESPONSE

            # 1. First call: Cache miss -> GraphQL fetch -> Cache write
            meta = resolve_series_metadata(title="Attack on Titan")
            self.assertIsNotNone(meta)
            self.assertEqual(meta.media_id, 16498)
            self.assertEqual(meta.canonical_title, "Attack on Titan")
            self.assertEqual(len(meta.characters), 4)

            armin = next(c for c in meta.characters if "Armin" in c.name)
            self.assertEqual(armin.gender, "male")
            self.assertIn("Armin", armin.aliases)

            hange = next(c for c in meta.characters if "Hange" in c.name)
            self.assertEqual(hange.gender, "non-binary")

            # Verify file was written to cache
            cache_file = Path(td) / "ani-cli" / "metadata" / "16498.json"
            self.assertTrue(cache_file.exists())

            # 2. Second call: Cache hit -> No GraphQL call
            mock_gql.reset_mock()
            cached_meta = resolve_series_metadata(media_id=16498)
            self.assertIsNotNone(cached_meta)
            self.assertEqual(cached_meta.media_id, 16498)
            mock_gql.assert_not_called()

    def test_resolve_series_metadata_network_error_graceful_fallback(self):
        with (
            tempfile.TemporaryDirectory() as td,
            patch.dict(os.environ, {"XDG_CACHE_HOME": td}),
            patch("ani_cli_sync.metadata._execute_graphql") as mock_gql,
        ):
            mock_gql.side_effect = urllib.error.URLError("Offline")
            meta = resolve_series_metadata(title="Attack on Titan")
            self.assertIsNone(meta)


if __name__ == "__main__":
    unittest.main()
