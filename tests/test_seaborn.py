"""Seaborn が作成した軸への縦書き適用を確認する。"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest
from test_vertical import font_file as font_file

import tategaki

sns = pytest.importorskip("seaborn")


@pytest.fixture(autouse=True)
def wrapping():
    tategaki.enable()
    yield
    tategaki.disable()
    plt.close("all")


def _make_vertical(ax, font_file):
    positions = ax.get_xticks()
    labels = [label.get_text() for label in ax.get_xticklabels()]
    return ax.set_xticks(positions, labels, writing_mode="vertical-rl", font=font_file)


def test_barplot_vertical_category_ticks(font_file):
    ax = sns.barplot(x=["東京", "ケーキ", "AB"], y=[12, 20, 15], errorbar=None)
    handle = _make_vertical(ax, font_file)
    assert isinstance(handle, tategaki.VerticalTickHandle)
    assert [artist.get_text() for artist in handle.artists] == ["東京", "ケーキ", "AB"]
    ax.figure.canvas.draw()


def test_catplot_facets_with_independent_x_axes(font_file):
    grid = sns.catplot(
        x=["東京", "ケーキ", "東京", "ケーキ"],
        y=[12, 20, 15, 18],
        col=["A", "A", "B", "B"],
        kind="bar",
        errorbar=None,
        sharex=False,
    )
    handles = [_make_vertical(ax, font_file) for ax in grid.axes.flat]
    assert len(handles) == 2
    assert all(len(handle.artists) == 2 for handle in handles)
    grid.figure.canvas.draw()
