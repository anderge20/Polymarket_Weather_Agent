"""The chain from a REAL IEM response to a settlement refusal, run end to end.

WHY THIS FILE EXISTS. `fetch_metar` is the single entry point for every
observation that will ever settle a position, and it had **no test anywhere in
the repository** — not one. Every observation test entered below it, and every
settle test monkeypatched `ingest_daily_high`. So the chain

    IEM payload -> fetch_metar -> daily_high -> to_row -> weather_observations
                -> stage_settle

had never been executed against anything but rows made by hand. `paper_cycle`
already said so about itself — *"Settlement had therefore never been exercised
against a row any ingester produced, and R24's P4 was closed against that
fixture"* — and nobody went to close it. That is worse than a missing test: the
gap was written down and left.

WHAT THE FIXTURE IS. `tests/fixtures/iem_kbkf_20260909.csv` is the verbatim body
of one real request to IEM's public ASOS archive for KBKF, 2026-09-09 to
2026-09-11, fetched 2026-09-11. It is committed so these tests are offline and
so the parser is pinned against output the SERVER produced rather than output we
imagined. Regenerate with the query in `observations.fetch_metar`; do not edit it
by hand — a fixture someone tidied is no longer evidence of anything.
"""
from __future__ import annotations

import io
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

import pytest

from weather_agent import observations as obs

PAYLOAD = (Path(__file__).parent / "fixtures" / "iem_kbkf_20260909.csv").read_text()


class _FakeResponse(io.BytesIO):
    """Just enough of urlopen's context-manager response to drive the parser."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *a):
        return PAYLOAD.encode()


@pytest.fixture
def served():
    """Serve the recorded payload to whatever window the code asks for.

    Patching at `urlopen` and not at `fetch_metar` is the point: the query
    building, the CSV reading, the timestamp format and the unit conversion are
    all inside the function under test."""
    with mock.patch("urllib.request.urlopen", lambda *a, **k: _FakeResponse()):
        yield


def test_fetch_metar_parses_a_real_iem_response(served):
    rows = obs.fetch_metar("KBKF",
                           datetime(2026, 9, 9, tzinfo=timezone.utc),
                           datetime(2026, 9, 10, 23, 59, tzinfo=timezone.utc))

    assert len(rows) == 47, "one routine METAR per hour over the two days served"

    # The timestamp format. `strptime(..., "%Y-%m-%d %H:%M")` is the whole
    # contract with IEM, and a malformed row is SKIPPED, never guessed at — so a
    # server that started emitting seconds would not raise here. It would return
    # an empty list, and `daily_high` would report "no observations at all": the
    # right refusal with the wrong cause. This pins the format that is actually
    # served.
    first, last = rows[0], rows[-1]
    assert first[0] == datetime(2026, 9, 9, 0, 58, tzinfo=timezone.utc)
    assert last[0] == datetime(2026, 9, 10, 23, 58, tzinfo=timezone.utc)
    assert all(t.tzinfo is timezone.utc for t, _ in rows)
    assert rows == sorted(rows, key=lambda r: r[0])

    # Fahrenheit in, Celsius out, converted exactly once. 72.30 F is the first
    # row of the fixture.
    assert first[1] == pytest.approx(obs.f_to_c(72.30))
    assert first[1] == pytest.approx(22.3889, abs=1e-4)


def test_the_station_column_is_not_the_icao(served):
    """IEM answers for KBKF with the string `BKF`, and that is not a typo.

    Recorded because the parser does NOT read this column — it takes the ICAO
    from its own argument — and the day someone decides to cross-check the
    response against the station they asked for, this is what they will hit. A
    check written on the assumption that the column echoes the ICAO would reject
    every US row, silently, since a row that fails is skipped rather than
    raised."""
    assert "\nBKF,2026-09-09 00:58,72.30" in PAYLOAD
    assert "KBKF," not in PAYLOAD

    rows = obs.fetch_metar("KBKF",
                           datetime(2026, 9, 9, tzinfo=timezone.utc),
                           datetime(2026, 9, 9, 23, 59, tzinfo=timezone.utc))
    assert rows, "the parser must not depend on the station column at all"


def test_a_changed_timestamp_format_yields_SILENCE_not_an_error():
    """The failure mode the fixture above exists to make visible.

    Not a defect being asserted as correct — a documented consequence. Every row
    is skipped on `ValueError`, so a format change makes `fetch_metar` return an
    EMPTY LIST with no exception, and the caller reports "no observations at
    all". True in its refusal, wrong in its cause, and it would send whoever
    debugs it to the station instead of the parser."""
    mangled = PAYLOAD.replace(" 00:58", " 00:58:00").replace(" 01:58", " 01:58:00")
    # Counted, not assumed: the fixture covers two days, so each substitution
    # hits both. The first draft of this test hard-coded "two rows" and failed
    # on its own arithmetic — which is the same shape as every other number in
    # this project that turned out to be an assertion about something nobody
    # had counted.
    n_mangled = PAYLOAD.count(" 00:58") + PAYLOAD.count(" 01:58")
    assert n_mangled == 4

    class _Mangled(_FakeResponse):
        def read(self, *a):
            return mangled.encode()

    with mock.patch("urllib.request.urlopen", lambda *a, **k: _Mangled()):
        rows = obs.fetch_metar("KBKF",
                               datetime(2026, 9, 9, tzinfo=timezone.utc),
                               datetime(2026, 9, 9, 23, 59, tzinfo=timezone.utc))

    served_instants = {r[0].strftime("%H:%M") for r in rows}
    assert "00:58" not in served_instants and "01:58" not in served_instants
    assert len(rows) == 47 - n_mangled, (
        "the mangled rows vanished without a word — that is the point")


def test_the_real_payload_produces_the_real_series_and_grid(served):
    """`daily_high` and `to_row` over the actual response, not a hand-made row.

    This is the first time in this project that the value reaching
    `weather_observations` was produced from a server payload rather than typed
    into a fixture, and it confirms two things that had only been argued:
    KBKF reports on a TENTHS-of-Fahrenheit grid, and the daily high of that day
    still lands on a whole degree. Both true at once, which is the pair
    `paper_cycle.SERIES_CORRESPONDENCE` warns nobody should collapse."""
    dh = obs.daily_high("KBKF", date(2026, 9, 9), "America/Denver")

    assert dh.n_obs == 24, "a full station-local day, not a partial one"
    assert dh.when_utc == datetime(2026, 9, 9, 22, 58, tzinfo=timezone.utc)
    assert dh.tmax_f == 82.0

    row = obs.to_row(dh, "ds_test")
    assert row["station"] == "KBKF"          # the argument, not the CSV column
    assert row["observed_unit"] == "F"
    assert row["observed_value"] == 82.0
    assert row["series"] == "IEM_ASOS_TMPF_0.1F"


def test_a_real_ingested_row_is_refused_by_settlement_and_says_why(served):
    """THE END OF THE CHAIN, and the assertion this whole file was written for.

    A row produced by the ingester from a real payload is handed to the frozen
    core, and the expected outcome is a REFUSAL — `IEM_ASOS_TMPF_0.1F` is left
    undeclared on purpose, because KBKF's stratum already fails closed upstream.

    So this does not prove settlement works. It proves something that had never
    been checked at all: that the series a real ingester actually emits is the
    one the boundary expects to refuse, by name. If `observations` ever renamed
    that series, or `SERIES_CORRESPONDENCE` grew an entry for it without the
    stratum question being reopened, this is where it shows up."""
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(
        "paper_cycle", Path(__file__).resolve().parents[1] / "scripts" / "paper_cycle.py")
    paper_cycle = importlib.util.module_from_spec(spec)
    sys.modules["paper_cycle"] = paper_cycle
    spec.loader.exec_module(paper_cycle)

    row = obs.to_row(obs.daily_high("KBKF", date(2026, 9, 9), "America/Denver"),
                     "ds_test")

    assert paper_cycle.to_core_series(row["series"]) is None, (
        "a real KBKF row must stay undeclared: mapping it would settle a tenths "
        "grid against a whole-degree operator")

    # And the declared ones are not accidentally None either — otherwise the
    # assertion above would pass for the wrong reason.
    for ingested, core in paper_cycle.SERIES_CORRESPONDENCE.items():
        assert paper_cycle.to_core_series(ingested) == core
