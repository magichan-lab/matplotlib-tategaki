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
        ("AB\nCD", "A\nB\n\nC\nD"),
        ("\nA\n", "\n\nA\n\n"),
    ],
)
def test_clusters(label, expected):
    """書記素クラスタを保ちながら文字列を縦積みに変換することを確認する。"""
    result = stack_label(label)
    assert result == expected
    assert result.replace("\n", "") == label.replace("\n", "")


@pytest.mark.parametrize("control", ["\r", "\t", "\0", "\x7f", "\x85", "\u2028", "\u2029"])
def test_controls(control):
    """制御文字を含むラベルが拒否されることを確認する。"""
    with pytest.raises(ValueError):
        stack_label("A" + control)


@pytest.mark.parametrize("label", [None, 1, b"A", ["A"]])
def test_types(label):
    """文字列以外のラベルが拒否されることを確認する。"""
    with pytest.raises(TypeError):
        stack_label(label)
