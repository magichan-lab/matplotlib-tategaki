# Copyright (c) 2026 magichan (https://github.com/magichan-lab)

"""固定カテゴリ目盛りの設定と入力検証を確認する。"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest
from matplotlib.ticker import FixedLocator

from tategaki import set_xticklabels


def test_fixed_categories_and_reapplication():
    """固定位置の縦積み目盛りを再設定しても軸上の要素が増えないことを確認する。"""
    with plt.rc_context({"text.usetex": True, "text.parse_math": True}):
        fig, ax = plt.subplots()
        bars = ax.bar([0, 2, 5, 7], [10, 24, 36, 18])
        texts = set_xticklabels(ax, [0, 2, 5, 7], ["AAA", "AAA", "$x$", "DDD"])
        assert isinstance(ax.xaxis.get_major_locator(), FixedLocator)
        assert [t.get_text() for t in texts] == ["A\nA\nA", "A\nA\nA", "$\nx\n$", "D\nD\nD"]
        assert [b.get_x() + b.get_width() / 2 for b in bars] == [0, 2, 5, 7]
        for t in texts:
            assert t.get_rotation() == 0
            assert t.get_ha() == "center" and t.get_va() == "top"
            assert not t.get_parse_math() and not t.get_usetex()
        count = len(ax.get_children())
        set_xticklabels(ax, [0, 2, 5, 7], ["BBB"] * 4)
        assert len(ax.get_children()) == count
        plt.close(fig)


@pytest.mark.parametrize(
    "positions,labels,kwargs,error",
    [
        ([0], [], {}, ValueError),
        ([0, 0], ["A", "B"], {}, ValueError),
        ([float("nan")], ["A"], {}, ValueError),
        (["a"], ["A"], {}, ValueError),
        ([0], ["A\n"], {}, ValueError),
        ([0], [None], {}, TypeError),
        ([0], "A", {}, TypeError),
        ([0], ["A"], {"orientation": "mixed"}, ValueError),
        ([0], ["A"], {"pad": -1}, ValueError),
        ([0], ["A"], {"linespacing": 0}, ValueError),
        ([0], ["A"], {"engine": "unknown"}, ValueError),
        ([0], ["A"], {"font": "unused.ttf"}, ValueError),
    ],
)
def test_invalid_does_not_mutate_axis(positions, labels, kwargs, error):
    """不正な目盛り設定が例外を出し、既存の軸設定を変更しないことを確認する。"""
    fig, ax = plt.subplots()
    locator = ax.xaxis.get_major_locator()
    with pytest.raises(error):
        set_xticklabels(ax, positions, labels, **kwargs)
    assert ax.xaxis.get_major_locator() is locator
    plt.close(fig)


def test_empty():
    """空の位置とラベルを指定した場合に空の結果を返すことを確認する。"""
    fig, ax = plt.subplots()
    assert set_xticklabels(ax, [], []) == []
    plt.close(fig)
