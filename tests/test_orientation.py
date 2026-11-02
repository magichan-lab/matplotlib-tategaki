# Copyright (c) 2026 magichan (https://github.com/magichan-lab)

"""同梱した Unicode 原本の全コードポイントと生成表を照合する。"""

import hashlib
from pathlib import Path

import regex

from tategaki._vertical_orientation import SOURCE_SHA256
from tategaki.orientation import cluster_orientation, vertical_orientation
from tategaki.shaping import split_runs


def test_complete_unicode_source_and_default_ranges():
    """生成済み縦書き方向表が同梱の Unicode 原本と全符号位置で一致することを確認する。"""
    source = Path(__file__).parent / "data" / "VerticalOrientation-17.0.0.txt"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == SOURCE_SHA256
    expected = ["R"] * 0x110000
    for line in source.read_text(encoding="utf-8").splitlines():
        data = line.split("#", 1)[0].strip()
        if data:
            span, value = map(str.strip, data.split(";"))
            ends = span.split("..")
            start, end = int(ends[0], 16), int(ends[-1], 16)
            expected[start : end + 1] = [value] * (end - start + 1)
    assert all(vertical_orientation(chr(cp)) == value for cp, value in enumerate(expected))


def test_grapheme_orientation_and_run_boundaries():
    """書記素の縦書き方向と混在文字列の区間境界を確認する。"""
    assert [vertical_orientation(c) for c in "A1Ａ東、ー"] == ["R", "R", "U", "U", "Tu", "Tr"]
    assert cluster_orientation("A\u0301") == "R"
    assert cluster_orientation("A\u20dd") == "U"
    text = "東京A\u0301B 12$Ｃ「ケーキ、。」"
    runs, spans = split_runs(text, "mixed")
    assert "".join(r.text for r in runs) == text
    assert spans == tuple(m.span() for m in regex.finditer(r"\X", text))
    assert all(text[r.start : r.end] == r.text for r in runs)
    assert [(r.text, r.rotation) for r in runs if r.rotation] == [("A\u0301B 12$", 90)]
    assert next(r for r in runs if r.text == "Ｃ").rotation == 0
    enclosed, _ = split_runs("A\u20ddB", "mixed")
    assert [r.rotation for r in enclosed] == [0, 90]
