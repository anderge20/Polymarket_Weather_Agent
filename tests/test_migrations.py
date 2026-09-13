"""Migrations: gaps are applied, published bodies are frozen, versions are 1..N (B-139)."""
from __future__ import annotations

import duckdb

from weather_agent import database as db

#: The checksum of every PUBLISHED migration. A mismatch means the body of a migration
#: that databases may already have applied was edited, which changes nothing on those
#: databases and leaves no trace (migration 9 exists because of exactly that). Add a
#: NEW migration instead, and pin it here.
PINNED_CHECKSUMS = {1: 'ea58ae99b5b853a76aca7cd016abd0234853fabdcc9e4cf3283db7c6b23018f3', 2: '2c919eef2acd928370410619fe0c1bcc9894a08a22c85562bae8d6026292e478', 3: 'b0451408565f17f419c91741498fa6c796d778c3edc7ad2dc9678cf88080b05d', 4: '86ad41c182931361fc5d1d5be302fe05a464c084d630e2cc09912614322606db', 5: '50667b932b8403c3b8604d2af69c7e3657e83ac62466a514ebc8bbc74a5996fe', 6: '274b4935b654af754db3d6c42ebc285365ec466ac68ae63077177b742810a907', 7: '79489e3cb7205771809dbf51db772903d52ce1cb429c5848af1c8129a2fe38e6', 8: 'fec6b2497bf86aefda9ae090f26aa79cd58a4abdc688fb4463b3fd99ae09ab37', 9: '517000119f0978dd1a8100fb8262b6a0a2c7e4e3d14fbeb125379c07ab30ca89'}


def test_migration_versions_are_1_to_N_in_order():
    """Migration 5 was introduced below an already-applied 6. The numbering rule is the
    next integer, in order, and nothing else."""
    versions = [m["version"] for m in db.MIGRATIONS]
    assert versions == list(range(1, len(versions) + 1)), versions
    assert db.SCHEMA_VERSION == versions[-1]


def test_the_body_of_a_published_migration_is_never_edited():
    current = {m["version"]: db.migration_checksum(m) for m in db.MIGRATIONS}
    edited = sorted(v for v in PINNED_CHECKSUMS if current.get(v) != PINNED_CHECKSUMS[v])
    assert not edited, (
        f"migrations {edited} changed after being published. Their databases will never "
        "see the change: add a NEW migration instead of editing this one.")
    unpinned = sorted(set(current) - set(PINNED_CHECKSUMS))
    assert not unpinned, f"new migrations {unpinned}: pin their checksum here"


def test_a_fresh_database_records_the_checksum_of_what_it_applied(con):
    rows = dict(con.execute("SELECT version, checksum FROM schema_version").fetchall())
    assert rows == {m["version"]: db.migration_checksum(m) for m in db.MIGRATIONS}


def _database_with_the_historical_gap(path):
    """A REAL file database in the state session A's `pmw.duckdb` is in: migrations
    1-4, 6, 7 and 8 applied and recorded, never 5, and migration 2 applied WITHOUT
    the `contract_source` line, which was added to it three days after it had run.
    Built statement by statement, the way the old `init_db` built it, not simulated."""
    con = duckdb.connect(str(path))
    db._ensure_schema_version_table(con)
    for mig in db.MIGRATIONS:
        if mig["version"] in (5, 9):
            continue
        for st in mig["statements"]:
            if mig["version"] == 2 and "contract_source" in st:
                continue
            con.execute(st)
        con.execute("INSERT INTO schema_version (version, name, applied_at) VALUES (?, ?, now())",
                    [mig["version"], mig["name"]])
    con.execute("INSERT INTO markets (market_id, question, source, ingestion_timestamp, "
                "dataset_version, record_version) VALUES ('m1', 'q', 's', now(), 'ds', 1)")
    cols = {c for (c,) in con.execute("SELECT column_name FROM information_schema.columns "
                                     "WHERE table_name = 'markets'").fetchall()}
    assert "measurement_rule_code" not in cols and "contract_source" not in cols
    con.close()


def test_init_db_applies_a_migration_numbered_BELOW_the_highest_recorded(tmp_path):
    """The old rule skipped every version at or below the highest recorded, so the gap
    was permanent and the suite never saw it: it always builds a new database."""
    path = tmp_path / "gap.duckdb"
    _database_with_the_historical_gap(path)

    con = db.init_db(db_path=str(path))
    try:
        recorded = sorted(v for (v,) in con.execute("SELECT version FROM schema_version").fetchall())
        assert recorded == list(range(1, db.SCHEMA_VERSION + 1)), recorded
        cols = set(db.column_names(con, "markets"))
        assert "measurement_rule_code" in cols, "migration 5, below the recorded 6, was not applied"
        assert "contract_source" in cols, "the line added to migration 2 after it ran was not re-declared"
        assert con.execute("SELECT count(*) FROM markets").fetchone()[0] == 1, "existing rows must survive"
        db.init_db(con)
        assert sorted(v for (v,) in con.execute("SELECT version FROM schema_version").fetchall()) == recorded
    finally:
        con.close()
