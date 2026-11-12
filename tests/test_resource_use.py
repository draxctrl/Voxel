"""What Voxel is costing the machine, read without a new dependency."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from src import resource_use


class TestReadingTheNumbers:
    def test_memory_is_a_real_figure_for_this_process(self):
        mb = resource_use.memory_mb()
        assert mb is not None
        assert 5 < mb < 20_000, "%r is not a plausible memory figure" % mb

    def test_cpu_needs_two_readings_before_it_means_anything(self):
        """A percentage is a rate, so the first call has nothing to compare
        against and must say so rather than invent a zero."""
        meter = resource_use.CpuMeter()
        assert meter.percent() is None
        value = meter.percent()
        assert value is None or value >= 0.0

    def test_cpu_is_never_a_nonsense_percentage(self):
        meter = resource_use.CpuMeter()
        meter.percent()
        for _ in range(3):
            value = meter.percent()
            if value is not None:
                assert 0.0 <= value <= 100.0, "%r is not a percentage" % value


class TestItNeverTakesTheAppDown:
    def test_a_failing_call_reads_as_unknown_not_as_a_crash(self, monkeypatch):
        def boom(*_args, **_kwargs):
            raise OSError("no such process")

        monkeypatch.setattr(resource_use, "_memory_bytes", boom)
        assert resource_use.memory_mb() is None

    def test_the_summary_is_a_sentence_even_with_nothing_to_report(self, monkeypatch):
        monkeypatch.setattr(resource_use, "memory_mb", lambda: None)
        meter = resource_use.CpuMeter()
        text = resource_use.summary(meter)
        assert isinstance(text, str) and text.strip() != ""

    def test_the_summary_names_the_memory_when_it_has_it(self, monkeypatch):
        monkeypatch.setattr(resource_use, "memory_mb", lambda: 412.0)
        meter = resource_use.CpuMeter()
        text = resource_use.summary(meter)
        assert "412" in text and "MB" in text


class TestWhatItSaysIsPlainEnoughToRead:
    def test_it_does_not_talk_about_processes_or_working_sets(self, monkeypatch):
        monkeypatch.setattr(resource_use, "memory_mb", lambda: 412.0)
        text = resource_use.summary(resource_use.CpuMeter()).lower()
        for jargon in ("working set", "process", "rss", "pid"):
            assert jargon not in text, "%r is jargon" % jargon
