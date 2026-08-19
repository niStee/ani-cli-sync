from __future__ import annotations

import unittest
from ani_cli_sync.cli import find_in_watching_list


class TestAniCliSync(unittest.TestCase):
    def setUp(self):
        self.sample_entries = [
            {
                "id": 1,
                "mediaId": 182255,
                "progress": 4,
                "media": {
                    "id": 182255,
                    "title": {
                        "english": "Frieren: Beyond Journey’s End Season 2",
                        "romaji": "Sousou no Frieren 2nd Season",
                    },
                    "episodes": 10,
                },
            },
            {
                "id": 2,
                "mediaId": 120377,
                "progress": 3,
                "media": {
                    "id": 120377,
                    "title": {
                        "english": "Cyberpunk: Edgerunners",
                        "romaji": "Cyberpunk: Edgerunners",
                    },
                    "episodes": 10,
                },
            },
        ]

        self.multi_season_entries = [
            {
                "id": 1,
                "mediaId": 154587,
                "progress": 28,
                "media": {
                    "id": 154587,
                    "title": {
                        "english": "Frieren: Beyond Journey’s End",
                        "romaji": "Sousou no Frieren",
                    },
                    "episodes": 28,
                },
            },
            {
                "id": 2,
                "mediaId": 182255,
                "progress": 4,
                "media": {
                    "id": 182255,
                    "title": {
                        "english": "Frieren: Beyond Journey’s End Season 2",
                        "romaji": "Sousou no Frieren 2nd Season",
                    },
                    "episodes": 10,
                },
            },
        ]

    def test_find_by_substring(self):
        res = find_in_watching_list(self.sample_entries, "frieren")
        self.assertIsNotNone(res)
        self.assertEqual(res["id"], 182255)

    def test_find_by_romaji(self):
        res = find_in_watching_list(self.sample_entries, "sousou")
        self.assertIsNotNone(res)
        self.assertEqual(res["id"], 182255)

    def test_find_exact_season1(self):
        res = find_in_watching_list(self.multi_season_entries, "Sousou no Frieren")
        self.assertIsNotNone(res)
        self.assertEqual(res["id"], 154587)

    def test_find_exact_season2(self):
        res = find_in_watching_list(self.multi_season_entries, "Sousou no Frieren 2nd Season")
        self.assertIsNotNone(res)
        self.assertEqual(res["id"], 182255)

    def test_find_substring_season2(self):
        res = find_in_watching_list(self.multi_season_entries, "Season 2")
        self.assertIsNotNone(res)
        self.assertEqual(res["id"], 182255)

    def test_nonexistent(self):
        res = find_in_watching_list(self.sample_entries, "NonexistentAnime")
        self.assertIsNone(res)

    def test_empty_query(self):
        res = find_in_watching_list(self.sample_entries, "")
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
