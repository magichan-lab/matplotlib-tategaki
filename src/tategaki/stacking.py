# Copyright (c) 2026 magichan (https://github.com/magichan-lab)

"""Matplotlib の描画に依存しない文字列変換を提供する。"""

import unicodedata

import regex

_GRAPHEME = regex.compile(r"\X")


def stack_label(label: str) -> str:
    """拡張書記素の間に改行を挿入し、入力の改行には空行を加える。

    LF 以外の Cc 制御文字と、行・段落区切り文字は受け付けない。
    ZWJ と異体字セレクタは許可する。書記素を保持しても、使用するフォントや
    描画器がその書記素を表示できるとは限らない。
    """
    _validate_label(label, allow_newline=True)
    return "\n\n".join("\n".join(_GRAPHEME.findall(line)) for line in label.split("\n"))


def _validate_label(label: str, *, allow_newline: bool) -> None:
    """入力文字列と、描画方式で許可される制御文字を検証する。"""
    if not isinstance(label, str):
        raise TypeError("label must be a str")
    for char in label:
        if (char != "\n" or not allow_newline) and unicodedata.category(char) in {"Cc", "Zl", "Zp"}:
            raise ValueError(f"label contains unsupported control/separator U+{ord(char):04X}")
