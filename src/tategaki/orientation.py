# Copyright (c) 2026 magichan (https://github.com/magichan-lab)

"""フォントや描画器に依存しない Unicode の縦書き方向分類を提供する。"""

from bisect import bisect_right

import regex

from ._vertical_orientation import RANGES

_STARTS = tuple(start for start, _, _ in RANGES)


def vertical_orientation(char: str) -> str:
    """単一の文字に対する Unicode 17.0.0 の U/R/Tu/Tr 分類を返す。"""
    cp = ord(char)
    index = bisect_right(_STARTS, cp) - 1
    if index >= 0 and cp <= RANGES[index][1]:
        return RANGES[index][2]
    return "R"


def cluster_orientation(cluster: str) -> str:
    """UAX #50 §3.2.1 に従い、書記素クラスタの縦書き方向を返す。

    基本的には先頭文字の分類を使い、囲み記号を含む場合は U を返す。
    """
    if regex.search(r"\p{Me}", cluster):
        return "U"
    return vertical_orientation(cluster[0])
