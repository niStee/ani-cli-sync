from __future__ import annotations

import copy
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from ani_cli_sync import cli


def media(
    media_id: int,
    title: str,
    *,
    episodes: int | None = 12,
    media_format: str = "TV",
    synonyms: list[str] | None = None,
) -> dict:
    return {
        "id": media_id,
        "title": {"english": title, "romaji": title, "native": title},
        "synonyms": synonyms or [],
        "episodes": episodes,
        "format": media_format,
    }


class FakeAniList:
    """Strict synthetic GraphQL boundary; no transport or real account state."""

    def __init__(
        self,
        *,
        candidates: dict[str, object] | None = None,
        entries: dict[int, object] | None = None,
    ) -> None:
        self.candidates = candidates or {}
        self.entries = entries or {}
        self.entry_reads: dict[int, list[object]] = {}
        self.mutation_responses: dict[int, object] = {}
        self.calls: list[tuple[str, dict, str | None]] = []
        self.mutations: list[dict] = []

    def __call__(
        self,
        query: str,
        variables: dict | None = None,
        token: str | None = None,
        retries: int = 3,
    ) -> dict:
        del retries
        variables = copy.deepcopy(variables or {})
        self.calls.append((query, variables, token))

        if "SaveMediaListEntry" in query:
            self.mutations.append(copy.deepcopy(variables))
            media_id = variables["mediaId"]
            if media_id in self.mutation_responses:
                response = self.mutation_responses[media_id]
                if isinstance(response, BaseException):
                    raise response
                return copy.deepcopy(response)  # type: ignore[arg-type]
            entry = {
                "id": 9000 + media_id,
                "mediaId": media_id,
                "progress": variables["progress"],
                "status": variables["status"],
            }
            self.entries[media_id] = {
                "progress": variables["progress"],
                "status": variables["status"],
            }
            return {"data": {"SaveMediaListEntry": entry}}

        if "Viewer" in query:
            return {"data": {"Viewer": {"id": 42, "name": "SyntheticViewer"}}}

        if "Page" in query and "media" in query:
            release = variables.get("search")
            if not isinstance(release, str):
                raise AssertionError(f"candidate query has no search variable: {variables}")
            response = self.candidates.get(release, [])
            if isinstance(response, BaseException):
                raise response
            if isinstance(response, dict):
                return copy.deepcopy(response)
            return {"data": {"Page": {"media": copy.deepcopy(response)}}}

        if "MediaList" in query:
            media_id = variables.get("mid", variables.get("mediaId"))
            if not isinstance(media_id, int):
                raise AssertionError(f"state query has no media id: {variables}")
            queued = self.entry_reads.get(media_id, [])
            response = queued.pop(0) if queued else self.entries.get(media_id)
            if isinstance(response, BaseException):
                raise response
            if isinstance(response, dict) and ("data" in response or "errors" in response):
                return copy.deepcopy(response)
            if response is None:
                return {"data": {"MediaList": None}}
            return {"data": {"MediaList": copy.deepcopy(response)}}

        # The pinned implementation's singular query is answered safely, which
        # keeps red tests hermetic without giving that legacy path a match.
        if "Media" in query:
            return {"data": {"Media": None}}
        raise AssertionError(f"unexpected GraphQL operation: {query}")

    @property
    def searches(self) -> list[tuple[str, dict, str | None]]:
        return [call for call in self.calls if "Page" in call[0] and "media" in call[0]]

    def state_reads(self, media_id: int) -> int:
        count = 0
        for query, variables, _ in self.calls:
            if "SaveMediaListEntry" in query or "MediaList" not in query:
                continue
            if variables.get("mid", variables.get("mediaId")) == media_id:
                count += 1
        return count


class NetflixImportTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary_directory.cleanup)
        self.csv_path = Path(self._temporary_directory.name) / "synthetic-history.csv"

    def write_csv(self, content: str | bytes) -> Path:
        data = content.encode("utf-8") if isinstance(content, str) else content
        self.csv_path.write_bytes(data)
        return self.csv_path

    def invoke(
        self,
        content: str | bytes | None = None,
        *,
        fake: FakeAniList | None = None,
        apply: bool = False,
        via_cli: bool = False,
        path: Path | None = None,
    ) -> tuple[object, str, str, FakeAniList]:
        if content is not None:
            self.write_csv(content)
        fake = fake or FakeAniList()
        csv_path = path or self.csv_path
        stdout = io.StringIO()
        stderr = io.StringIO()
        direct_kwargs = {"apply": True} if apply else {}
        argv = ["ani-cli-sync", "import-netflix"]
        if apply:
            argv.append("--apply")
        argv.append(str(csv_path))

        with (
            mock.patch.object(cli, "get_token", return_value="tok"),
            mock.patch.object(cli, "gql_query", side_effect=fake),
            mock.patch.object(cli.time, "sleep", return_value=None),
            mock.patch.object(
                cli.urllib.request,
                "urlopen",
                side_effect=AssertionError("unexpected live HTTP transport"),
            ),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            try:
                if via_cli:
                    with mock.patch.object(sys, "argv", argv):
                        cli.main()
                else:
                    cli.cmd_import_netflix(str(csv_path), **direct_kwargs)
            except SystemExit as exc:
                code = 0 if exc.code is None else exc.code
            else:
                code = 0
        return code, stdout.getvalue(), stderr.getvalue(), fake

    def assert_no_mutations(self, fake: FakeAniList) -> None:
        self.assertEqual([], fake.mutations)

    def assert_summary_reconciles(self, output: str, rows: int) -> None:
        pattern = rf"(?i)(?:input|rows?|events?).{{0,40}}\b{rows}\b|\b{rows}\b.{{0,40}}(?:input|rows?|events?)"
        self.assertRegex(output, pattern)

    def assert_no_verified_playback_claim(self, output: str) -> None:
        lowered = output.lower()
        self.assertNotIn("verified playback completion", lowered)
        self.assertNotIn("playback verified", lowered)


class TestNetflixCsvInput(NetflixImportTestCase):
    def test_f01_f02_bom_crlf_quoted_unicode_and_opaque_dates(self) -> None:
        release = 'Chrono Academy: Eclipse, "Äther"'
        content = (
            '\ufeffTitle,Date\r\n"Chrono Academy: Eclipse, ""Äther"": Episode 1","31/12/2024"\r\n'
            '"Chrono Academy: Eclipse, ""Äther"": Episode 2","not a calendar date"\r\n'
        )
        fake = FakeAniList(candidates={release: [media(101, release, episodes=2)]})
        code, out, err, fake = self.invoke(content, fake=fake, via_cli=True)
        output = out + err

        self.assertEqual(0, code, output)
        self.assertIn("preview", output.lower())
        self.assertIn("31/12/2024", output)
        self.assertIn("not a calendar date", output)
        self.assertIn(release, output)
        self.assertIn("inferred", output.lower())
        self.assert_no_verified_playback_claim(output)
        self.assert_no_mutations(fake)
        self.assertEqual(1, len(fake.searches))
        self.assertEqual(release, fake.searches[0][1]["search"])
        self.assert_summary_reconciles(output, 2)

    def test_f03_lf_and_header_only_inputs_are_valid(self) -> None:
        release = "Chrono Academy"
        fake = FakeAniList(candidates={release: [media(101, release)]})
        code, out, err, fake = self.invoke(
            f"Title,Date\n{release}: Episode 1,opaque\n",
            fake=fake,
        )
        self.assertEqual(0, code, out + err)
        self.assertIn("inferred", (out + err).lower())
        self.assert_no_mutations(fake)

        empty_fake = FakeAniList()
        code, out, err, empty_fake = self.invoke("Title,Date\n", fake=empty_fake)
        output = out + err
        self.assertEqual(0, code, output)
        self.assertRegex(output.lower(), r"zero|0")
        self.assertIn("event", output.lower())
        self.assertEqual([], empty_fake.calls)
        self.assert_no_mutations(empty_fake)

    def test_f04_missing_unreadable_and_non_utf8_files_exit_2_without_api(self) -> None:
        missing = Path(self._temporary_directory.name) / "absent.csv"
        code, out, err, fake = self.invoke(path=missing)
        self.assertEqual(2, code, out + err)
        self.assertEqual([], fake.calls)

        directory = Path(self._temporary_directory.name) / "directory.csv"
        directory.mkdir()
        code, out, err, fake = self.invoke(path=directory)
        self.assertEqual(2, code, out + err)
        self.assertEqual([], fake.calls)

        code, out, err, fake = self.invoke(b"\xff\xfeTitle,Date\n")
        self.assertEqual(2, code, out + err)
        self.assertEqual([], fake.calls)

    def test_f04_malformed_csv_matrix_exits_2_without_api(self) -> None:
        cases = {
            "wrong_header": "Name,Date\nChrono Academy: Episode 1,x\n",
            "case_sensitive_header": "title,Date\nChrono Academy: Episode 1,x\n",
            "extra_header_field": "Title,Date,Extra\nChrono Academy: Episode 1,x,y\n",
            "short_row": "Title,Date\nChrono Academy: Episode 1\n",
            "long_row": "Title,Date\nChrono Academy: Episode 1,x,extra\n",
            "missing_header": "Chrono Academy: Episode 1,x\n",
            "missing_date_header": "Title\nChrono Academy: Episode 1\n",
            "malformed_quote": 'Title,Date\n"Chrono Academy: Episode 1,x\n',
            "blank_title": "Title,Date\n   ,x\n",
            "blank_date": "Title,Date\nChrono Academy: Episode 1,   \n",
        }
        for name, content in cases.items():
            with self.subTest(name=name):
                code, out, err, fake = self.invoke(content)
                self.assertEqual(2, code, out + err)
                self.assertEqual([], fake.calls)
                self.assert_no_mutations(fake)

    def test_f04_later_invalid_row_invalidates_whole_file_before_api(self) -> None:
        content = "Title,Date\nChrono Academy: Episode 1,opaque\nChrono Academy: Episode 2,\n"
        code, out, err, fake = self.invoke(content)
        self.assertEqual(2, code, out + err)
        self.assertEqual([], fake.calls)
        self.assert_no_mutations(fake)


class TestNetflixIdentityAndResolution(NetflixImportTestCase):
    def test_f07_right_anchored_episode_grammar_preserves_colon_and_season(self) -> None:
        release = "Chrono Academy: Eclipse: Season 2"
        rows = "".join(f'"{release}: Episode {number}",opaque\n' for number in (1, 2, 3))
        fake = FakeAniList(candidates={release: [media(102, release, episodes=3)]})
        code, out, err, fake = self.invoke(f"Title,Date\n{rows}", fake=fake)
        output = out + err

        self.assertEqual(0, code, output)
        self.assertEqual(1, len(fake.searches))
        self.assertEqual(release, fake.searches[0][1]["search"])
        self.assertIn("Season 2", output)
        self.assertIn("inferred", output.lower())
        self.assertRegex(output, r"(?i)progress\D{0,20}3")
        self.assert_summary_reconciles(output, 3)
        self.assert_no_mutations(fake)

    def test_f07_surrounding_title_whitespace_is_trimmed_before_grammar_match(self) -> None:
        release = "Chrono Academy: Eclipse"
        fake = FakeAniList(candidates={release: [media(102, release)]})
        code, out, err, fake = self.invoke(
            f'Title,Date\n"  {release}: Episode 1  ",opaque\n',
            fake=fake,
        )
        output = out + err
        self.assertEqual(0, code, output)
        self.assertEqual(1, len(fake.searches))
        self.assertEqual(release, fake.searches[0][1]["search"])
        self.assertIn("inferred", output.lower())
        self.assertNotIn("unresolved", output.lower())
        self.assert_no_mutations(fake)

        titles = [
            "Chrono Academy",
            "Chrono Academy: The Name",
            "Chrono Academy: Episode 3: The Name",
            "Chrono Academy: episode 1",
            "Chrono Academy: Episode 01",
            "Chrono Academy: Episode 0",
            "Chrono Academy: Episode -1",
            "Chrono Academy: Episode 1 extra",
            "Chrono Academy: Episode +1",
            "Chrono Academy: Episode 1.0",
            "Chrono Academy: Episode  1",
            "Chrono Academy: Special 1",
        ]
        for title in titles:
            with self.subTest(title=title):
                code, out, err, fake = self.invoke(f'Title,Date\n"{title}",opaque\n')
                output = out + err
                self.assertEqual(0, code, output)
                self.assertIn(title, output)
                self.assertIn("unresolved", output.lower())
                self.assertIn("unsupported", output.lower())
                self.assertNotIn("inferred progress", output.lower())
                self.assertEqual([], fake.searches)
                self.assert_no_mutations(fake)
                self.assert_summary_reconciles(output, 1)

    def test_f05_duplicate_views_dedupe_identity_and_reconcile_every_row(self) -> None:
        release = "Chrono Academy"
        content = (
            "Title,Date\n"
            f"{release}: Episode 1,first opaque date\n"
            f"{release}: Episode 1,second opaque date\n"
            f"{release}: Episode 2,earlier opaque date\n"
        )
        fake = FakeAniList(candidates={release: [media(101, release, episodes=3)]})
        code, out, err, fake = self.invoke(content, fake=fake)
        output = out + err

        self.assertEqual(0, code, output)
        self.assertIn("first opaque date", output)
        self.assertIn("second opaque date", output)
        self.assertIn("earlier opaque date", output)
        self.assertIn("dedup", output.lower())
        self.assertRegex(output, r"(?i)inferred.{0,80}progress\D{0,20}2|progress\D{0,20}2.{0,80}inferred")
        self.assertNotRegex(output, r"(?i)progress\D{0,20}3")
        self.assertEqual(1, len(fake.searches))
        self.assert_summary_reconciles(output, 3)
        self.assert_no_mutations(fake)

    def test_f06_season_and_part_contexts_remain_distinct_targets(self) -> None:
        releases = {
            "Chrono Academy: Season 2": media(102, "Chrono Academy: Season 2"),
            "Chrono Academy: Part 2": media(103, "Chrono Academy: Part 2"),
        }
        rows = "".join(f'"{release}: Episode 1",opaque\n' for release in releases)
        fake = FakeAniList(candidates={key: [value] for key, value in releases.items()})
        code, out, err, fake = self.invoke(f"Title,Date\n{rows}", fake=fake, apply=True)
        output = out + err

        self.assertEqual(0, code, output)
        self.assertEqual({102, 103}, {call["mediaId"] for call in fake.mutations})
        self.assertEqual(2, len(fake.mutations))
        for mutation in fake.mutations:
            self.assertEqual(1, mutation["progress"])
            self.assertEqual("CURRENT", mutation["status"])
        self.assertIn("Chrono Academy: Season 2", output)
        self.assertIn("Chrono Academy: Part 2", output)

    def test_f09_exact_match_and_no_match_are_both_completed_processing(self) -> None:
        matched = "Chrono Academy"
        unmatched = "Unknown Academy"
        fake = FakeAniList(candidates={matched: [media(101, matched)], unmatched: []})
        content = f"Title,Date\n{matched}: Episode 1,one\n{unmatched}: Episode 1,two\n"
        code, out, err, fake = self.invoke(content, fake=fake)
        output = out + err

        self.assertEqual(0, code, output)
        self.assertIn(matched, output)
        self.assertIn(unmatched, output)
        self.assertIn("unmatched", output.lower())
        self.assertNotRegex(output.lower(), r"lookup.{0,30}fail|search.{0,30}fail|no match.{0,30}fail")
        self.assertIn("inferred", output.lower())
        self.assertNotIn("successfully imported", output.lower())
        self.assert_summary_reconciles(output, 2)
        self.assert_no_mutations(fake)

    def test_f10_multiple_exact_candidates_are_ambiguous_not_first_hit(self) -> None:
        release = "Chrono Academy"
        candidates = [media(101, release), media(202, release)]
        fake = FakeAniList(candidates={release: candidates})
        code, out, err, fake = self.invoke(
            f"Title,Date\n{release}: Episode 1,opaque\n",
            fake=fake,
            apply=True,
        )
        output = out + err

        self.assertEqual(0, code, output)
        self.assertIn("ambiguous", output.lower())
        self.assertIn("101", output)
        self.assertIn("202", output)
        self.assertNotIn("inferred progress", output.lower())
        self.assert_no_mutations(fake)

    def test_f10_remake_and_film_conflict_is_not_resolved_by_order_or_format(self) -> None:
        release = "Chrono Academy"
        fake = FakeAniList(
            candidates={release: [media(101, release), media(202, release, media_format="MOVIE")]}
        )
        code, out, err, fake = self.invoke(f"Title,Date\n{release}: Episode 1,opaque\n", fake=fake)
        output = out + err
        self.assertEqual(0, code, output)
        self.assertIn("ambiguous", output.lower())
        self.assertNotIn("inferred progress", output.lower())
        self.assert_no_mutations(fake)

    def test_f10_missing_source_season_never_matches_extra_candidate_season(self) -> None:
        source = "Chrono Academy"
        for field, title in (
            ("english", "Chrono Academy: Season 1"),
            ("romaji", "Chrono Academy: Season 1"),
            ("synonyms", "Chrono Academy: Part 1"),
        ):
            with self.subTest(field=field):
                candidate = media(101, "Unrelated Romaji")
                if field == "synonyms":
                    candidate["synonyms"] = [title]
                else:
                    candidate["title"][field] = title
                fake = FakeAniList(candidates={source: [candidate]})
                code, out, err, fake = self.invoke(
                    f"Title,Date\n{source}: Episode 1,opaque\n",
                    fake=fake,
                    apply=True,
                )
                output = out + err
                self.assertEqual(0, code, output)
                self.assertNotIn("inferred progress", output.lower())
                self.assertRegex(output.lower(), r"unmatched|unresolved")
                self.assert_no_mutations(fake)

    def test_f10_full_candidate_page_with_one_match_reports_incomplete_lookup(self) -> None:
        release = "Chrono Academy"
        candidates = [media(101, release)] + [
            media(1000 + index, f"Unrelated Academy {index}") for index in range(9)
        ]
        fake = FakeAniList(candidates={release: candidates})
        code, out, err, fake = self.invoke(
            f"Title,Date\n{release}: Episode 1,opaque\n",
            fake=fake,
            apply=True,
        )
        output = out + err
        self.assertEqual(0, code, output)
        self.assertIn("ambiguous", output.lower())
        self.assertRegex(output.lower(), r"incomplete|full page|bounded")
        self.assertNotIn("inferred progress", output.lower())
        self.assert_no_mutations(fake)

    def test_f10_malformed_and_missing_candidate_fields_fail_closed(self) -> None:
        release = "Chrono Academy"
        cases = {
            "missing_id": {"title": {"english": release}, "episodes": 12},
            "string_id": {**media(101, release), "id": "101"},
            "null_titles": {**media(101, release), "title": None, "synonyms": None},
            "malformed_titles": {**media(101, release), "title": {"english": 101}},
        }
        for name, candidate in cases.items():
            with self.subTest(name=name):
                fake = FakeAniList(candidates={release: [candidate]})
                code, out, err, fake = self.invoke(
                    f"Title,Date\n{release}: Episode 1,opaque\n",
                    fake=fake,
                    apply=True,
                )
                output = out + err
                self.assertIn(code, (0, 1), output)
                self.assertNotIn("inferred progress", output.lower())
                self.assert_no_mutations(fake)
                if code == 0:
                    self.assertRegex(output.lower(), r"unresolved|unmatched|invalid|malformed")

        release = "Chrono Academy"
        fake = FakeAniList(candidates={release: [media(101, release)]})
        content = (
            f"Title,Date\n{release}: Episode 1,one\n{release}: Episode 2,two\n"
        )
        code, out, err, fake = self.invoke(content, fake=fake)
        self.assertEqual(0, code, out + err)
        self.assertEqual(1, len(fake.searches))
        variables = fake.searches[0][1]
        if "perPage" in variables:
            self.assertLessEqual(variables["perPage"], 10)


class TestNetflixProgressAndStatus(NetflixImportTestCase):
    def test_f12_exact_contiguous_set_proposes_inferred_progress(self) -> None:
        release = "Chrono Academy"
        rows = "".join(f"{release}: Episode {number},opaque\n" for number in (3, 1, 2))
        fake = FakeAniList(candidates={release: [media(101, release, episodes=3)]})
        code, out, err, fake = self.invoke(f"Title,Date\n{rows}", fake=fake)
        output = out + err
        self.assertEqual(0, code, output)
        self.assertRegex(output, r"(?i)inferred.{0,100}progress\D{0,20}3|progress\D{0,20}3.{0,100}inferred")
        self.assertIn("recorded", output.lower())
        self.assert_no_verified_playback_claim(output)

    def test_f12_late_only_and_sparse_sets_block_the_whole_group(self) -> None:
        for name, episodes, forbidden in (
            ("late_only", (8,), (1, 8)),
            ("sparse", (1, 2, 4), (2, 3, 4)),
        ):
            with self.subTest(name=name):
                release = "Chrono Academy"
                rows = "".join(f"{release}: Episode {number},opaque\n" for number in episodes)
                fake = FakeAniList(candidates={release: [media(101, release, episodes=12)]})
                code, out, err, fake = self.invoke(f"Title,Date\n{rows}", fake=fake, apply=True)
                output = out + err
                self.assertEqual(0, code, output)
                self.assertRegex(output.lower(), r"insufficient|sparse|coverage|contiguous")
                self.assertNotIn("inferred", output.lower())
                self.assertNotIn("COMPLETED", output)
                for number in forbidden:
                    self.assertNotRegex(output, rf"(?i)progress\D{{0,20}}{number}\b")
                self.assert_no_mutations(fake)

    def test_f13_absent_full_coverage_creates_current_never_completed(self) -> None:
        release = "Chrono Academy"
        fake = FakeAniList(
            candidates={release: [media(101, release, episodes=2)]},
            entries={101: None},
        )
        content = f"Title,Date\n{release}: Episode 1,one\n{release}: Episode 2,two\n"
        code, out, err, fake = self.invoke(content, fake=fake, apply=True)
        output = out + err
        self.assertEqual(0, code, output)
        self.assertEqual(1, len(fake.mutations))
        self.assertEqual(
            {"mediaId": 101, "progress": 2, "status": "CURRENT"},
            fake.mutations[0],
        )
        self.assertIn("inferred", output.lower())
        self.assert_no_verified_playback_claim(output)

    def test_f13_current_full_coverage_can_complete_only_with_apply(self) -> None:
        release = "Chrono Academy"
        content = f"Title,Date\n{release}: Episode 1,one\n{release}: Episode 2,two\n"
        candidates = {release: [media(101, release, episodes=2)]}
        preview_fake = FakeAniList(
            candidates=candidates,
            entries={101: {"status": "CURRENT", "progress": 1}},
        )
        code, preview_out, preview_err, preview_fake = self.invoke(content, fake=preview_fake)
        preview = preview_out + preview_err
        self.assertEqual(0, code, preview)
        self.assertIn("preview", preview.lower())
        self.assertIn("inferred", preview.lower())
        self.assertIn("COMPLETED", preview)
        self.assert_no_mutations(preview_fake)

        apply_fake = FakeAniList(
            candidates=candidates,
            entries={101: {"status": "CURRENT", "progress": 1}},
        )
        code, out, err, apply_fake = self.invoke(content, fake=apply_fake, apply=True, via_cli=True)
        output = out + err
        self.assertEqual(0, code, output)
        self.assertEqual(
            [{"mediaId": 101, "progress": 2, "status": "COMPLETED"}],
            apply_fake.mutations,
        )
        self.assertIn("inferred", output.lower())
        self.assertIn("recorded", output.lower())
        self.assert_no_verified_playback_claim(output)

    def test_f13_status_only_completion_is_allowed_for_current_at_total(self) -> None:
        release = "Chrono Academy"
        fake = FakeAniList(
            candidates={release: [media(101, release, episodes=2)]},
            entries={101: {"status": "CURRENT", "progress": 2}},
        )
        content = f"Title,Date\n{release}: Episode 1,one\n{release}: Episode 2,two\n"
        code, out, err, fake = self.invoke(content, fake=fake, apply=True)
        self.assertEqual(0, code, out + err)
        self.assertEqual(
            [{"mediaId": 101, "progress": 2, "status": "COMPLETED"}],
            fake.mutations,
        )

    def test_f14_unknown_zero_and_negative_totals_do_not_complete(self) -> None:
        for total in (None, 0, -1):
            with self.subTest(total=total):
                release = "Chrono Academy"
                fake = FakeAniList(
                    candidates={release: [media(101, release, episodes=total)]},
                    entries={101: {"status": "CURRENT", "progress": 0}},
                )
                content = f"Title,Date\n{release}: Episode 1,one\n{release}: Episode 2,two\n"
                code, out, err, fake = self.invoke(content, fake=fake, apply=True)
                output = out + err
                self.assertEqual(0, code, output)
                self.assertEqual(
                    [{"mediaId": 101, "progress": 2, "status": "CURRENT"}],
                    fake.mutations,
                )
                self.assertNotIn("inferred COMPLETED", output)
                self.assertNotIn("inferred completed", output.lower())

    def test_f15_current_equal_or_higher_progress_is_not_regressed(self) -> None:
        for current in (2, 5):
            with self.subTest(current=current):
                release = "Chrono Academy"
                fake = FakeAniList(
                    candidates={release: [media(101, release, episodes=12)]},
                    entries={101: {"status": "CURRENT", "progress": current}},
                )
                content = f"Title,Date\n{release}: Episode 1,one\n{release}: Episode 2,two\n"
                code, out, err, fake = self.invoke(content, fake=fake, apply=True)
                output = out + err
                self.assertEqual(0, code, output)
                self.assertRegex(output.lower(), r"unchanged|stale|current")
                self.assert_no_mutations(fake)

    def test_f15_current_above_known_total_is_blocked_not_lowered(self) -> None:
        release = "Chrono Academy"
        fake = FakeAniList(
            candidates={release: [media(101, release, episodes=2)]},
            entries={101: {"status": "CURRENT", "progress": 3}},
        )
        content = f"Title,Date\n{release}: Episode 1,one\n{release}: Episode 2,two\n"
        code, out, err, fake = self.invoke(content, fake=fake, apply=True)
        self.assertEqual(0, code, out + err)
        self.assert_no_mutations(fake)

    def test_f15_every_non_current_status_is_preserved(self) -> None:
        for status in ("PLANNING", "PAUSED", "DROPPED", "REPEATING", "COMPLETED"):
            with self.subTest(status=status):
                release = "Chrono Academy"
                fake = FakeAniList(
                    candidates={release: [media(101, release, episodes=2)]},
                    entries={101: {"status": status, "progress": 0}},
                )
                content = f"Title,Date\n{release}: Episode 1,one\n{release}: Episode 2,two\n"
                code, out, err, fake = self.invoke(content, fake=fake, apply=True)
                output = out + err
                self.assertEqual(0, code, output)
                self.assertIn(status, output)
                self.assertRegex(output.lower(), r"unchanged|status.policy|policy.skip")
                self.assert_no_mutations(fake)


class TestNetflixApiFailuresAndApply(NetflixImportTestCase):
    def test_f11_transport_graphql_and_malformed_search_failures_are_not_no_match(self) -> None:
        release = "Chrono Academy"
        responses = (
            RuntimeError("synthetic transport failure"),
            {"errors": [{"message": "synthetic GraphQL failure"}], "data": {"Page": {"media": []}}},
            {"data": {}},
            {"data": {"Page": {}}},
        )
        for response in responses:
            with self.subTest(response=response):
                fake = FakeAniList(candidates={release: response})
                code, out, err, fake = self.invoke(
                    f"Title,Date\n{release}: Episode 1,opaque\n",
                    fake=fake,
                )
                output = out + err
                self.assertEqual(1, code, output)
                self.assertRegex(output.lower(), r"fail|error|malformed|invalid")
                self.assertNotIn("unmatched", output.lower())
                self.assert_no_mutations(fake)

    def test_f17_failed_initial_state_read_is_not_absence(self) -> None:
        release = "Chrono Academy"
        fake = FakeAniList(
            candidates={release: [media(101, release)]},
            entries={101: RuntimeError("synthetic state read failure")},
        )
        code, out, err, fake = self.invoke(
            f"Title,Date\n{release}: Episode 1,opaque\n",
            fake=fake,
            apply=True,
        )
        output = out + err
        self.assertEqual(1, code, output)
        self.assertIn("fail", output.lower())
        self.assertNotRegex(output.lower(), r"absent.{0,40}(?:create|new)|(?:create|new).{0,40}absent")
        self.assert_no_mutations(fake)

    def test_f17_fresh_read_failure_blocks_only_that_mutation(self) -> None:
        release = "Chrono Academy"
        fake = FakeAniList(
            candidates={release: [media(101, release)]},
            entries={101: {"status": "CURRENT", "progress": 0}},
        )
        fake.entry_reads[101] = [
            {"status": "CURRENT", "progress": 0},
            RuntimeError("synthetic fresh read failure"),
        ]
        code, out, err, fake = self.invoke(
            f"Title,Date\n{release}: Episode 1,opaque\n",
            fake=fake,
            apply=True,
        )
        output = out + err
        self.assertEqual(1, code, output)
        self.assertIn("fail", output.lower())
        self.assertEqual(2, fake.state_reads(101))
        self.assert_no_mutations(fake)

    def test_f18_fresh_higher_progress_skips_stale_mutation(self) -> None:
        release = "Chrono Academy"
        fake = FakeAniList(
            candidates={release: [media(101, release, episodes=3)]},
        )
        fake.entry_reads[101] = [
            {"status": "CURRENT", "progress": 0},
            {"status": "CURRENT", "progress": 3},
        ]
        content = f"Title,Date\n{release}: Episode 1,one\n{release}: Episode 2,two\n"
        code, out, err, fake = self.invoke(content, fake=fake, apply=True)
        output = out + err
        self.assertEqual(0, code, output)
        self.assertRegex(output.lower(), r"stale|unchanged|fresh")
        self.assertEqual(2, fake.state_reads(101))
        self.assert_no_mutations(fake)

    def test_f18_fresh_disallowed_status_blocks_stale_mutation(self) -> None:
        release = "Chrono Academy"
        fake = FakeAniList(candidates={release: [media(101, release)]})
        fake.entry_reads[101] = [
            {"status": "CURRENT", "progress": 0},
            {"status": "PAUSED", "progress": 0},
        ]
        code, out, err, fake = self.invoke(
            f"Title,Date\n{release}: Episode 1,opaque\n",
            fake=fake,
            apply=True,
        )
        output = out + err
        self.assertEqual(0, code, output)
        self.assertRegex(output.lower(), r"stale|unchanged|status.policy")
        self.assert_no_mutations(fake)

    def test_f19_mutation_response_must_match_every_requested_field(self) -> None:
        release = "Chrono Academy"
        valid = {"id": 9101, "mediaId": 101, "progress": 1, "status": "CURRENT"}
        responses = {
            "empty": {"data": {}},
            "null": {"data": {"SaveMediaListEntry": None}},
            "wrong_media": {"data": {"SaveMediaListEntry": {**valid, "mediaId": 999}}},
            "wrong_progress": {"data": {"SaveMediaListEntry": {**valid, "progress": 2}}},
            "wrong_status": {"data": {"SaveMediaListEntry": {**valid, "status": "COMPLETED"}}},
            "graphql_errors": {"errors": [{"message": "synthetic failure"}], "data": {"SaveMediaListEntry": valid}},
            "transport": RuntimeError("synthetic mutation transport failure"),
        }
        for name, response in responses.items():
            with self.subTest(name=name):
                fake = FakeAniList(
                    candidates={release: [media(101, release)]},
                    entries={101: {"status": "CURRENT", "progress": 0}},
                )
                fake.mutation_responses[101] = response
                code, out, err, fake = self.invoke(
                    f"Title,Date\n{release}: Episode 1,opaque\n",
                    fake=fake,
                    apply=True,
                )
                output = out + err
                self.assertEqual(1, code, output)
                self.assertRegex(output.lower(), r"unverified|fail|error|mismatch")
                self.assertNotIn("successfully imported", output.lower())
                self.assertEqual(1, len(fake.mutations))

    def test_f19_exact_mutation_response_is_verified(self) -> None:
        release = "Chrono Academy"
        fake = FakeAniList(
            candidates={release: [media(101, release)]},
            entries={101: {"status": "CURRENT", "progress": 0}},
        )
        code, out, err, fake = self.invoke(
            f"Title,Date\n{release}: Episode 1,opaque\n",
            fake=fake,
            apply=True,
        )
        output = out + err
        self.assertEqual(0, code, output)
        self.assertEqual(1, len(fake.mutations))
        self.assertIn("verified", output.lower())
        self.assertNotIn("unverified", output.lower())

    def test_f20_partial_apply_preserves_verified_and_failed_results(self) -> None:
        first = "Alpha Academy"
        second = "Beta Academy"
        fake = FakeAniList(
            candidates={first: [media(101, first)], second: [media(202, second)]},
            entries={
                101: {"status": "CURRENT", "progress": 0},
                202: {"status": "CURRENT", "progress": 0},
            },
        )
        fake.mutation_responses[202] = {
            "data": {
                "SaveMediaListEntry": {
                    "id": 9202,
                    "mediaId": 202,
                    "progress": 0,
                    "status": "CURRENT",
                }
            }
        }
        content = f"Title,Date\n{first}: Episode 1,one\n{second}: Episode 1,two\n"
        code, out, err, fake = self.invoke(content, fake=fake, apply=True)
        output = out + err

        self.assertEqual(1, code, output)
        first_lines = [line for line in output.splitlines() if first in line]
        second_lines = [line for line in output.splitlines() if second in line]
        self.assertTrue(
            any("verified" in line.lower() and "unverified" not in line.lower() for line in first_lines),
            output,
        )
        self.assertTrue(
            any("unverified" in line.lower() or "fail" in line.lower() for line in second_lines),
            output,
        )
        self.assertNotIn("successfully imported", output.lower())
        self.assertEqual(2, len(fake.mutations))
        self.assertGreaterEqual(fake.state_reads(101), 2)
        self.assertGreaterEqual(fake.state_reads(202), 2)

    def test_f20_rerun_with_already_current_state_is_idempotent(self) -> None:
        release = "Chrono Academy"
        fake = FakeAniList(
            candidates={release: [media(101, release, episodes=3)]},
            entries={101: {"status": "CURRENT", "progress": 0}},
        )
        content = f"Title,Date\n{release}: Episode 1,one\n{release}: Episode 2,two\n"
        code, out, err, fake = self.invoke(content, fake=fake, apply=True)
        self.assertEqual(0, code, out + err)
        self.assertEqual(1, len(fake.mutations))

        code, out, err, fake = self.invoke(content, fake=fake, apply=True)
        output = out + err
        self.assertEqual(0, code, output)
        self.assertEqual(1, len(fake.mutations))
        self.assertRegex(output.lower(), r"unchanged|already.current")
        self.assertNotIn("successfully imported", output.lower())

    def test_f21_safe_unresolved_ambiguous_and_sparse_rows_remain_visible(self) -> None:
        safe = "Alpha Academy"
        unmatched = "Unknown Academy"
        ambiguous = "Remake Academy"
        sparse = "Sparse Academy"
        fake = FakeAniList(
            candidates={
                safe: [media(101, safe)],
                unmatched: [],
                ambiguous: [media(201, ambiguous), media(202, ambiguous)],
                sparse: [media(303, sparse)],
            }
        )
        content = (
            "Title,Date\n"
            f"{safe}: Episode 1,one\n"
            f"{unmatched}: Episode 1,two\n"
            f"{ambiguous}: Episode 1,three\n"
            f"{sparse}: Episode 4,four\n"
        )
        code, out, err, fake = self.invoke(content, fake=fake)
        output = out + err

        self.assertEqual(0, code, output)
        for title in (safe, unmatched, ambiguous, sparse):
            self.assertIn(title, output)
        self.assertIn("unmatched", output.lower())
        self.assertIn("ambiguous", output.lower())
        self.assertRegex(output.lower(), r"insufficient|sparse|coverage|contiguous")
        self.assertIn("inferred", output.lower())
        self.assertNotIn("successfully imported", output.lower())
        self.assert_summary_reconciles(output, 4)
        self.assert_no_mutations(fake)


if __name__ == "__main__":
    unittest.main()
