"""Tests for the dictation history store."""

from __future__ import annotations

import os
import tempfile
import threading

import pytest

from src.history import HistoryStore


@pytest.fixture()
def store(tmp_path):
    """Yield a HistoryStore backed by a temporary database."""
    db = str(tmp_path / "test_history.db")
    return HistoryStore(db_path=db)


# ---- add / get_last --------------------------------------------------


def test_add_returns_id(store: HistoryStore):
    entry_id = store.add("hello world", "Hello world.")
    assert isinstance(entry_id, int)
    assert entry_id >= 1


def test_add_auto_calculates_word_count(store: HistoryStore):
    store.add("one two three", "One two three.")
    last = store.get_last()
    assert last is not None
    assert last["word_count"] == 3


def test_add_empty_cleaned_text_word_count(store: HistoryStore):
    store.add("   ", "   ")
    last = store.get_last()
    assert last is not None
    assert last["word_count"] == 0


def test_get_last_empty(store: HistoryStore):
    assert store.get_last() is None


def test_get_last_returns_newest(store: HistoryStore):
    store.add("first", "First")
    store.add("second", "Second")
    last = store.get_last()
    assert last is not None
    assert last["cleaned_text"] == "Second"


# ---- dict keys -------------------------------------------------------


def test_result_dict_keys(store: HistoryStore):
    store.add("raw", "clean", language="fr", duration=1.5, profile="work")
    last = store.get_last()
    expected_keys = {
        "id", "timestamp", "raw_text", "cleaned_text",
        "language", "duration_s", "word_count", "profile",
    }
    assert set(last.keys()) == expected_keys
    assert last["language"] == "fr"
    assert last["duration_s"] == 1.5
    assert last["profile"] == "work"


# ---- get_recent ------------------------------------------------------


def test_get_recent_order(store: HistoryStore):
    for i in range(5):
        store.add(f"raw {i}", f"Clean {i}")
    recent = store.get_recent(limit=3)
    assert len(recent) == 3
    # newest first
    assert recent[0]["cleaned_text"] == "Clean 4"
    assert recent[2]["cleaned_text"] == "Clean 2"


def test_get_recent_limit(store: HistoryStore):
    for i in range(10):
        store.add(f"r{i}", f"c{i}")
    assert len(store.get_recent(limit=5)) == 5


# ---- search ----------------------------------------------------------


def test_search_finds_in_raw(store: HistoryStore):
    store.add("the quick fox", "The quick fox.")
    store.add("lazy dog", "Lazy dog.")
    results = store.search("quick")
    assert len(results) == 1
    assert results[0]["raw_text"] == "the quick fox"


def test_search_finds_in_cleaned(store: HistoryStore):
    store.add("abc", "Hello World")
    results = store.search("World")
    assert len(results) == 1


def test_search_no_results(store: HistoryStore):
    store.add("abc", "def")
    assert store.search("zzz") == []


def test_search_limit(store: HistoryStore):
    for i in range(10):
        store.add(f"word {i}", f"word {i}")
    results = store.search("word", limit=3)
    assert len(results) == 3


# ---- delete ----------------------------------------------------------


def test_delete(store: HistoryStore):
    id1 = store.add("a", "A")
    id2 = store.add("b", "B")
    store.delete(id1)
    assert store.count() == 1
    assert store.get_last()["id"] == id2


def test_delete_nonexistent_is_noop(store: HistoryStore):
    store.add("a", "A")
    store.delete(9999)
    assert store.count() == 1


# ---- clear_all -------------------------------------------------------


def test_clear_all(store: HistoryStore):
    for i in range(5):
        store.add(f"r{i}", f"c{i}")
    assert store.count() == 5
    store.clear_all()
    assert store.count() == 0
    assert store.get_last() is None


# ---- count -----------------------------------------------------------


def test_count_empty(store: HistoryStore):
    assert store.count() == 0


def test_count_after_adds(store: HistoryStore):
    store.add("a", "A")
    store.add("b", "B")
    assert store.count() == 2


# ---- thread safety ---------------------------------------------------


def test_concurrent_adds(tmp_path):
    db = str(tmp_path / "thread_test.db")
    store = HistoryStore(db_path=db)
    errors: list[Exception] = []

    def writer(n: int):
        try:
            for i in range(20):
                store.add(f"thread-{n}-{i}", f"Thread {n} item {i}")
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(t,)) for t in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert store.count() == 80
