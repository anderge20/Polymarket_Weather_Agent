"""
stations.py — canonical station coordinates  (decision D1)
==========================================================

Until Phase 2E the project had **no** station coordinate table: `req_lat`/`req_lon`
came from a research artifact whose provenance was not reproducible from the code.
Since the grid cell — and therefore the forecast — depends on the coordinate, that
was an unfixed, unpreregistered degree of freedom. This module closes it.

RULE (D1, `~/pmw-e2/DECISIONS.md`)
-----------------------------------
`station_lat/lon` is the **observing station** of NOAA AviationWeather's METAR
station registry (`siteType ⊇ {METAR}`), frozen in a dated snapshot shipped with
the code. The ICAO is resolved from the market's own `icao2`, never from the city
name — aerodromes change (Paris LFPG→LFPB on 2026-04-19, Taipei RCTP→RCSS on
2026-04-05). OurAirports is a control only; IEM and WMO OSCAR are forbidden as a
position: both point at the WMO synoptic *city* station in 7 of the 55 stations
(ZSQD is 39.5 km off).

SCOPE OF THE VERIFICATION (D6 — adversarial refutation)
--------------------------------------------------------
The premise "the NOAA coordinate is the sensor location" is **observed** for
11 of 55 stations: 10 US ASOS verified against NCEI HOMR (`source: 'ASOS CM'`,
mean 8.8 m, max 71 m) and WSSS verified against the Singapore AIP, WMO OSCAR and
NEA (40-46 m). The 10 US stations share one network and one configuration
database, so they are one line of evidence, not ten. For the remaining 43
stations — all outside the US, 10 of them in China — the rule rests on registry
lineage and the absence of counterexamples, **not** on individual verification.
Any report using these coordinates must say so.

KNOWN OPEN CASE: OPKC (Karachi). The NOAA point is 2.51 km from the ARP, which
changes the ECMWF cell with a 2.8 °C temperature difference over 1 551 markets.
It is used under the general rule and flagged. KBKF is canonical but *not*
verifiable against HOMR (its record has no `ASOS CM` entry and DDMM precision,
±0.93 km, cannot separate sensor from ARP).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SNAPSHOT_PATH = Path(__file__).with_name("data") / "station_coords_v1.json"

#: sha256 of the snapshot this code was written against. A mismatch means the
#: table moved under the code: forecasts extracted before and after are not
#: comparable, so we refuse rather than silently mix conventions.
SNAPSHOT_SHA256 = "071b142c7ba37e36ba95be8a1d12c81db1db53e69caa8dd41d00306cd50d74b1"

#: Stations whose coordinate is canonical but whose sensor identity is unresolved.
OPEN_EXCEPTIONS = frozenset({"OPKC"})


class UnknownStation(KeyError):
    """No canonical coordinate for this ICAO."""


class SnapshotMismatch(RuntimeError):
    """The coordinate snapshot on disk is not the one this code was frozen against."""


@dataclass(frozen=True)
class Station:
    icao: str
    city: str
    lat: float
    lon: float
    country: str | None = None
    site: str | None = None
    status: str | None = None

    @property
    def coords(self) -> tuple[float, float]:
        return (self.lat, self.lon)

    @property
    def verified_sensor(self) -> bool:
        """True only for the 11 stations verified individually (D6)."""
        return self.icao in VERIFIED_SENSOR


#: The 11 stations whose sensor identity was verified against primary sources (D6).
VERIFIED_SENSOR = frozenset(
    {"KATL", "KAUS", "KDAL", "KHOU", "KLAX", "KLGA", "KMIA", "KORD", "KSEA", "KSFO", "WSSS"}
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def load(verify: bool = True) -> dict[str, Station]:
    """The frozen snapshot, keyed by ICAO. Verifies its hash by default."""
    if verify:
        got = _sha256(SNAPSHOT_PATH)
        if got != SNAPSHOT_SHA256:
            raise SnapshotMismatch(
                f"station snapshot sha256 {got} != frozen {SNAPSHOT_SHA256}; "
                "forecasts extracted under different coordinate conventions are not comparable"
            )
    raw = json.loads(SNAPSHOT_PATH.read_text())
    return {
        s["icao"]: Station(
            icao=s["icao"],
            city=s.get("city"),
            lat=float(s["lat"]),
            lon=float(s["lon"]),
            country=s.get("country"),
            site=s.get("site"),
            status=s.get("status"),
        )
        for s in raw["stations"]
    }


def get(icao: str) -> Station:
    """The canonical station for `icao`. Raises rather than guessing."""
    try:
        return load()[icao.upper()]
    except KeyError as e:
        raise UnknownStation(
            f"{icao!r} has no canonical coordinate; resolve its ICAO from the market's "
            "icao2 and extend the snapshot deliberately — never fall back to a city lookup"
        ) from e


def coords(icao: str) -> tuple[float, float]:
    return get(icao).coords


def all_icaos() -> list[str]:
    return sorted(load())


#: Timezone per ICAO. The daily high is a LOCAL-day quantity, so a station
#: without a known timezone is a refusal, never a guess of UTC.
TZ_BY_ICAO = {
    "KLGA": "America/New_York", "KATL": "America/New_York", "KMIA": "America/New_York",
    "KORD": "America/Chicago", "KDAL": "America/Chicago", "KHOU": "America/Chicago",
    "KAUS": "America/Chicago", "KDEN": "America/Denver", "KBKF": "America/Denver",
    "KLAX": "America/Los_Angeles", "KSFO": "America/Los_Angeles",
    "KSEA": "America/Los_Angeles", "KPHX": "America/Phoenix",
    "EGLC": "Europe/London", "LFPG": "Europe/Paris", "LFPB": "Europe/Paris",
    "EDDM": "Europe/Berlin", "EHAM": "Europe/Amsterdam", "LEMD": "Europe/Madrid",
    "LIMC": "Europe/Rome", "EPWA": "Europe/Warsaw", "EFHK": "Europe/Helsinki",
    "UUWW": "Europe/Moscow", "LTFM": "Europe/Istanbul", "LTAC": "Europe/Istanbul",
    "LLBG": "Asia/Jerusalem", "OEJN": "Asia/Riyadh", "OPKC": "Asia/Karachi",
    "VILK": "Asia/Kolkata", "VHHH": "Asia/Hong_Kong", "RCTP": "Asia/Taipei",
    "RCSS": "Asia/Taipei", "RJTT": "Asia/Tokyo", "RKSI": "Asia/Seoul",
    "RKPK": "Asia/Seoul", "ZBAA": "Asia/Shanghai", "ZSPD": "Asia/Shanghai",
    "ZSQD": "Asia/Shanghai", "ZSJN": "Asia/Shanghai", "ZGGG": "Asia/Shanghai",
    "ZGSZ": "Asia/Shanghai", "ZHHH": "Asia/Shanghai", "ZHCC": "Asia/Shanghai",
    "ZUUU": "Asia/Shanghai", "ZUCK": "Asia/Shanghai",
    "WSSS": "Asia/Singapore", "WMKK": "Asia/Kuala_Lumpur", "WIHH": "Asia/Jakarta",
    "RPLL": "Asia/Manila", "VTBS": "Asia/Bangkok",
    "SBGR": "America/Sao_Paulo", "SAEZ": "America/Argentina/Buenos_Aires",
    "MMMX": "America/Mexico_City", "MPMG": "America/Panama",
    "CYYZ": "America/Toronto", "NZWN": "Pacific/Auckland",
    "FACT": "Africa/Johannesburg", "DNMM": "Africa/Lagos",
}


def timezone_of(icao: str) -> str:
    """The station's timezone. Raises rather than defaulting to UTC."""
    try:
        return TZ_BY_ICAO[icao.upper()]
    except KeyError as e:
        raise UnknownStation(
            f"no timezone for {icao!r}; the daily high is a local-day quantity "
            "and assuming UTC would silently shift the window"
        ) from e
