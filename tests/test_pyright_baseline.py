"""Tests for tools.pyright_baseline: only errors beyond the baseline fail."""
from __future__ import annotations

import json
from collections import Counter

from tools import pyright_baseline as pb


def _diag(file: str, line: int, rule: str, message: str, severity: str = "error") -> dict:
    return {
        "file": str(pb.ROOT / file),
        "severity": severity,
        "rule": rule,
        "message": message,
        "range": {"start": {"line": line, "character": 0}, "end": {"line": line, "character": 1}},
    }


def _report(*diags: dict) -> dict:
    return {"version": "1.1.999", "generalDiagnostics": list(diags)}


def test_keys_ignore_line_numbers_warnings_and_environment_rules():
    counts = pb.count_errors(_report(
        _diag("graphify/a.py", 10, "reportArgumentType", 'Argument of type "x"\n  detail'),
        _diag("graphify/a.py", 99, "reportArgumentType", 'Argument of type "x"\n  other detail'),
        _diag("graphify/a.py", 5, "reportMissingImports", 'Import "y" could not be resolved'),
        _diag("graphify/a.py", 6, "reportArgumentType", "a warning", severity="warning"),
    ))
    assert counts == Counter({("graphify/a.py", 'reportArgumentType: Argument of type "x"'): 2})


def test_moved_errors_pass_and_extra_occurrences_fail():
    baseline = pb.count_errors(_report(_diag("graphify/a.py", 10, "r", "m")))
    moved = pb.count_errors(_report(_diag("graphify/a.py", 50, "r", "m")))
    assert pb.compare(moved, baseline) == (Counter(), 0)

    doubled = pb.count_errors(_report(
        _diag("graphify/a.py", 10, "r", "m"), _diag("graphify/a.py", 20, "r", "m")))
    new, fixed = pb.compare(doubled, baseline)
    assert new == Counter({("graphify/a.py", "r: m"): 1}) and fixed == 0


def test_fixed_errors_are_counted_not_failed():
    baseline = pb.count_errors(_report(
        _diag("graphify/a.py", 1, "r", "m"), _diag("graphify/b.py", 1, "r", "m")))
    current = pb.count_errors(_report(_diag("graphify/a.py", 1, "r", "m")))
    assert pb.compare(current, baseline) == (Counter(), 1)


def test_baseline_round_trips(tmp_path):
    counts = pb.count_errors(_report(
        _diag("graphify/a.py", 1, "r", "m"), _diag("graphify/a.py", 2, "r", "m"),
        _diag("tests/t.py", 3, "q", "n")))
    path = tmp_path / "baseline.json"
    pb.dump_baseline(counts, "1.1.999", path)
    assert pb.load_baseline(path) == (counts, "1.1.999")


def test_main_fails_only_on_new_errors(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(pb, "BASELINE", tmp_path / "baseline.json")
    pb.dump_baseline(pb.count_errors(_report(_diag("graphify/a.py", 1, "r", "m"))), "1.1.999")

    same = tmp_path / "same.json"
    same.write_text(json.dumps(_report(_diag("graphify/a.py", 7, "r", "m"))))
    assert pb.main(["--report", str(same)]) == 0

    worse = tmp_path / "worse.json"
    worse.write_text(json.dumps(_report(
        _diag("graphify/a.py", 7, "r", "m"), _diag("graphify/c.py", 3, "r", "new one"))))
    assert pb.main(["--report", str(worse)]) == 1
    out = capsys.readouterr().out
    assert "1 new pyright error(s)" in out and "graphify/c.py:4:1" in out
