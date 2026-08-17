"""Tests for syncing a release back into the catalog.

The catalog is where operators look when something is wrong at 3am, so a sync
that silently loses a field, or that doubles a record on retry, is worse than
one that fails loudly.
"""

from omnigent.tools.pipely.sync_catalog import sync

FACTS = {
    "version": "v1.4.2",
    "record_count": 10_000,
    "quality": "passed",
    "lineage": ["raw_orders", "staging_orders", "published_orders"],
    "run_state": "succeeded",
}


class _Catalog:
    """A catalog double with genuine upsert semantics: one record per key.

    Keyed rather than appending, because that is what the real ``upsert`` does.
    Idempotence therefore rests on the *key the tool supplies* being stable,
    which is the tool's own behavior and what these tests exercise.
    """

    def __init__(self) -> None:
        self.records: dict[str, dict[str, object]] = {}

    def upsert(self, key: str, facts: dict[str, object]) -> None:
        """Record *facts* under *key*, replacing any previous record."""
        self.records[key] = dict(facts)


def test_every_fact_reaches_the_catalog_unchanged() -> None:
    """A sync that drops a field leaves the operator reading a half-truth."""
    catalog = _Catalog()

    sync(catalog=catalog, pipeline="orders_daily", facts=FACTS)

    (written,) = catalog.records.values()
    assert written == FACTS


def test_a_catalog_outage_is_reported_apart_from_a_scheduler_outage() -> None:
    """They ship together, which is exactly why one must not be read as the other.

    "The platform is down" sends the operator to the wrong dashboard; the
    catalog can be unreachable while jobs keep running, and the reverse.
    """

    class _DownCatalog:
        def upsert(self, key: str, facts: dict[str, object]) -> None:
            raise ConnectionError("catalog refused the connection")

    result = sync(catalog=_DownCatalog(), pipeline="orders_daily", facts=FACTS)

    assert result["synced"] is False
    assert result["unreachable"] == "catalog"


def test_syncing_the_same_release_twice_leaves_one_record() -> None:
    """Retries are normal, so the second sync must land on the first record.

    A retried sync that appends leaves the operator with two versions of the
    truth and no way to tell which is current.
    """
    catalog = _Catalog()

    sync(catalog=catalog, pipeline="orders_daily", facts=FACTS)
    sync(catalog=catalog, pipeline="orders_daily", facts=FACTS)

    assert len(catalog.records) == 1
