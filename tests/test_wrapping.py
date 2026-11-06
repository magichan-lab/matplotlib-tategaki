# Copyright (c) 2026 magichan (https://github.com/magichan-lab)

"""任意に有効化する Matplotlib メソッドとその状態遷移を検証する。"""

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotlib.axes import Axes
from matplotlib.font_manager import FontProperties, findfont, fontManager
from matplotlib.text import Text
from test_vertical import font_file as font_file

import tategaki
from tategaki.wrapping import WrappedVerticalText


@pytest.fixture(autouse=True)
def wrapping():
    """各テストの前後で Matplotlib の縦書き拡張を有効化・解除する。"""
    tategaki.enable()
    yield
    tategaki.disable()
    plt.close("all")


def test_text_alignment_updates_and_exports(font_file):
    """縦書きテキストの位置揃え、属性変更、各形式への保存を確認する。"""
    fig, ax = plt.subplots()
    artist = ax.text(
        0.5,
        0.5,
        "東京AB",
        writing_mode="vertical-rl",
        font=font_file,
        ha="center",
        va="center",
        transform=ax.transAxes,
        color="blue",
    )
    assert isinstance(artist, Text)
    bounds = artist.get_window_extent()
    np.testing.assert_allclose(
        [(bounds.x0 + bounds.x1) / 2, (bounds.y0 + bounds.y1) / 2],
        ax.transAxes.transform((0.5, 0.5)),
    )
    artist.set_text("東京")
    artist.set_fontsize(24)
    artist.set_color("red")
    for fmt in ("png", "svg", "pdf"):
        output = io.BytesIO()
        fig.savefig(output, format=fmt, bbox_inches="tight")
        assert len(output.getvalue()) > 500
    artist.remove()
    assert artist not in ax.texts


def test_multicolumn_text_alignment(font_file):
    """複数列の縦書きでも Text の中央揃えと描画範囲が一致する。"""
    fig, ax = plt.subplots()
    artist = ax.text(
        0.5,
        0.5,
        "東京\nAB",
        writing_mode="vertical-rl",
        font=font_file,
        ha="center",
        va="center",
        transform=ax.transAxes,
    )
    bounds = artist.get_window_extent()
    np.testing.assert_allclose(
        [(bounds.x0 + bounds.x1) / 2, (bounds.y0 + bounds.y1) / 2],
        ax.transAxes.transform((0.5, 0.5)),
    )
    fig.canvas.draw()


def test_axis_labels_position_resize_and_switch(font_file):
    """縦書き軸タイトルの位置、DPI 変更、横書きへの切り替えを確認する。"""
    fig, ax = plt.subplots(layout="constrained")
    for method in (ax.set_xlabel, ax.set_ylabel):
        label = method("東京", writing_mode="vertical-rl", font=font_file, fontsize=16, labelpad=14)
        assert isinstance(label, WrappedVerticalText)
    for dpi in (100, 150):
        fig.set_dpi(dpi)
        fig.canvas.draw()
        xb = ax.xaxis.label.get_window_extent()
        yb = ax.yaxis.label.get_window_extent()
        assert xb.y1 < ax.bbox.y0
        assert yb.x1 < ax.bbox.x0
    previous = ax.yaxis.label
    with pytest.raises(ValueError):
        ax.set_ylabel("東京", writing_mode="vertical-rl", font=font_file, rotation=90)
    assert ax.yaxis.label is previous
    normal = ax.set_ylabel("Normal")
    assert type(normal) is Text
    assert normal.get_rotation() == 90
    fig.canvas.draw()


def test_ticks_replace_and_restore(font_file):
    """縦書き目盛りの差し替えと通常の目盛りへの復帰を確認する。"""
    fig, ax = plt.subplots()
    handle = ax.set_xticks(
        ticks=[0, 1],
        labels=["東京", "AB"],
        writing_mode="vertical-rl",
        font=font_file,
        orientation="mixed",
    )
    assert isinstance(handle, tategaki.VerticalTickHandle)
    fig.canvas.draw()
    replacement = ax.set_xticklabels(
        labels=["AB", "東京"], writing_mode="vertical-rl", font=font_file
    )
    assert all(a.axes is None for a in handle.artists)
    assert len(replacement.artists) == 2
    ax.set_xticks([2, 3], ["two", "three"])
    assert all(a.axes is None for a in replacement.artists)
    assert [t.get_text() for t in ax.get_xticklabels()] == ["two", "three"]


def test_validation_does_not_attach_artists(font_file):
    """無効な縦書き設定が軸に Artist を追加しないことを確認する。"""
    fig, ax = plt.subplots()
    for options in (
        {"writing_mode": "invalid"},
        {"writing_mode": "vertical-rl", "font": font_file, "rotation": 90},
        {"writing_mode": "vertical-rl", "font": font_file, "bbox": {}},
    ):
        with pytest.raises(ValueError):
            ax.text(0, 0, "東京", **options)
    assert not ax.texts
    with pytest.raises(ValueError, match="set_xticks"):
        ax.set_xticklabels(["東京"], writing_mode="vertical-rl", font=font_file)
    with pytest.raises(ValueError, match="explicit labels"):
        ax.set_xticks([0], writing_mode="vertical-rl", font=font_file)


def test_enable_disable_and_pyplot(font_file):
    """拡張の重複有効化・解除と pyplot 経由の呼び出しを確認する。"""
    method = Axes.text
    tategaki.enable()
    assert Axes.text is method
    fig, ax = plt.subplots()
    ax.set_xlabel(xlabel="Horizontal")
    ax.set_ylabel(ylabel="東京", writing_mode="vertical-rl", font=font_file)
    normal = ax.text(0, 0, "plain")
    assert type(normal) is Text
    artist = plt.text(0.5, 0.5, "東京", writing_mode="vertical-rl", font=font_file)
    _, handle = plt.xticks([0, 1], ["東京", "AB"], writing_mode="vertical-rl", font=font_file)
    assert isinstance(handle, tategaki.VerticalTickHandle)
    tategaki.disable()
    tategaki.disable()
    assert Axes.text is not method
    fig.canvas.draw()
    assert artist in ax.texts
    with pytest.raises(AttributeError):
        ax.text(0, 0, "東京", writing_mode="vertical-rl")


def test_rcparams_font_used_when_omitted(font_file):
    """フォント未指定時に rcParams のフォントが使われることを確認する。"""
    fontManager.addfont(str(font_file))
    with plt.rc_context({"font.family": "Test Vertical"}):
        selected = findfont(FontProperties(), fallback_to_default=False)
        fig, ax = plt.subplots()
        ax.set_yticks([])
        text = ax.text(0.5, 0.5, "東京", writing_mode="vertical-rl")
        xlabel = ax.set_xlabel("東京", writing_mode="vertical-rl")
        ylabel = ax.set_ylabel("東京", writing_mode="vertical-rl")
        handle = ax.set_xticks([0], ["東京"], writing_mode="vertical-rl")
        assert isinstance(handle, tategaki.VerticalTickHandle)
        for artist in (text, xlabel, ylabel, *handle.artists):
            vertical = artist._vertical if isinstance(artist, WrappedVerticalText) else artist
            assert vertical._font.filename == selected
        fig.canvas.draw()
        replacement = ax.set_xticklabels(["東京"], writing_mode="vertical-rl")
        assert replacement.artists[0]._font.filename == selected
        direct = tategaki.VerticalText(0, 0, "東京")
        assert direct._font.filename == selected
        fig.canvas.draw()


def test_explicit_font_overrides_rcparams(font_file):
    """明示したフォントが rcParams の設定より優先されることを確認する。"""
    with plt.rc_context({"font.family": "DejaVu Sans"}):
        fig, ax = plt.subplots()
        artist = ax.text(0, 0, "東京", writing_mode="vertical-rl", font=font_file)
        assert artist._vertical._font.filename == str(font_file.resolve())
        fig.canvas.draw()
