# Copyright (c) 2026 magichan (https://github.com/magichan-lab)

"""書記素単位の縦積みと入力検証を確認する。"""

import pytest

from tategaki import stack_label


@pytest.mark.parametrize(
    "label,expected",
    [
        ("AAA", "A\nA\nA"),
        ("ＡＢＣ", "Ａ\nＢ\nＣ"),
        ("", ""),
        (" A　", " \nA\n　"),
        ("が", "が"),
        ("か\u3099A", "か\u3099\nA"),
        ("葛\U000e0100A", "葛\U000e0100\nA"),
        ("✈\ufe0fA", "✈\ufe0f\nA"),
        ("👩\u200d💻A", "👩\u200d💻\nA"),
        ("🇯🇵A", "🇯🇵\nA"),
        ("$x$", "$\nx\n$"),
    ],
)
def test_clusters(label, expected):
    """各種書記素を分割せず、書記素間だけ改行することを確認する。"""
    result = stack_label(label)
    assert result == expected
    assert result.replace("\n", "") == label


@pytest.mark.parametrize("control", ["\n", "\r", "\t", "\0", "\x7f", "\x85", "\u2028", "\u2029"])
def test_controls(control):
    """制御文字と区切り文字を拒否することを確認する。"""
    with pytest.raises(ValueError):
        stack_label("A" + control)


@pytest.mark.parametrize("label", [None, 1, b"A", ["A"]])
def test_types(label):
    """文字列以外の入力を拒否することを確認する。"""
    with pytest.raises(TypeError):
        stack_label(label)
