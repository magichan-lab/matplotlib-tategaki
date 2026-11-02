# Copyright (c) 2026 magichan (https://github.com/magichan-lab)

"""Matplotlib の目盛りを使い、数値位置に固定したカテゴリラベルを設定する。"""

from __future__ import annotations

from math import isfinite
from numbers import Real

from matplotlib.axes import Axes
from matplotlib.font_manager import FontProperties
from matplotlib.text import Text
from matplotlib.ticker import NullFormatter
from matplotlib.transforms import ScaledTranslation

from .stacking import stack_label


def set_xticklabels(
    ax: Axes,
    positions,
    labels,
    *,
    fontproperties: FontProperties | None = None,
    fontsize: float | None = None,
    linespacing: float = 1.0,
    pad: float = 4.0,
    orientation: str = "upright",
    engine: str = "stacked",
    font=None,
    color="black",
) -> list[Text] | VerticalTickHandle:
    """x 軸下側の固定ラベルを縦積みまたは OpenType の輪郭で設定する。

    主目盛りの Locator と Formatter を固定カテゴリ用に置き換える。
    位置は重複しない有限の実数とし、ラベル文字列の重複は許す。
    ``stacked`` の ``pad`` は目盛り線の長さも考慮する。
    ``opentype`` の ``pad`` は Axes 下端からのポイント数を表す。
    ``linespacing`` は Matplotlib の行間であり、フォントの送り量ではない。
    軸タイトルとの間隔は必要に応じて ``labelpad`` で指定する。

    Args:
        ax: 対象の座標軸。
        positions: ラベルを置く X 座標の列。
        labels: 各位置のラベル文字列の列。
        fontproperties: ``stacked`` で用いる Matplotlib フォント設定。
        fontsize: 文字サイズ（ポイント）。
        linespacing: ``stacked`` で用いる Matplotlib の行間倍率。
        pad: ラベルとの間隔（ポイント）。基準位置は描画方式により異なる。
        orientation: ``"upright"`` または、OpenType 用の ``"mixed"``。
        engine: 改行による ``"stacked"`` または輪郭を描く ``"opentype"``。
        font: OpenType 用のフォントファイル。省略時は rcParams から選ぶ。
        color: OpenType 用ラベルの色。

    Returns:
        ``stacked`` では Matplotlib の ``Text`` のリスト、
        ``opentype`` では取り外し用の ``VerticalTickHandle``。

    Raises:
        TypeError: ラベル列として単一の文字列を渡した場合。
        ValueError: 位置、ラベル、表示設定が不正な場合。
    """
    if engine not in {"stacked", "opentype"}:
        raise ValueError("engine must be stacked or opentype")
    if orientation not in {"upright", "mixed"} or (
        engine == "stacked" and orientation != "upright"
    ):
        raise ValueError("mixed orientation requires engine='opentype'; otherwise use upright")
    if isinstance(labels, str):
        raise TypeError("labels must be an iterable of strings, not a single str")
    positions, labels = list(positions), list(labels)
    if len(positions) != len(labels):
        raise ValueError("positions and labels must have the same length")
    if any(isinstance(p, bool) or not isinstance(p, Real) or not isfinite(p) for p in positions):
        raise ValueError("positions must be finite real numbers")
    if len(set(positions)) != len(positions):
        raise ValueError("positions must be distinct")
    for name, value, positive in (
        ("linespacing", linespacing, True),
        ("pad", pad, False),
        ("fontsize", fontsize, True),
    ):
        if value is None and name == "fontsize":
            continue
        if (
            not isinstance(value, Real)
            or not isfinite(value)
            or (value <= 0 if positive else value < 0)
        ):
            raise ValueError(f"invalid {name}")
    displayed = [stack_label(label) for label in labels]
    if engine == "opentype":
        if fontproperties is not None:
            raise ValueError("use font, not fontproperties, with opentype")
        if linespacing != 1.0:
            raise ValueError("opentype uses font advances; linespacing must be 1")
        return _set_opentype(ax, positions, labels, font, fontsize, pad, color, orientation)
    if font is not None:
        raise ValueError("font is only used with opentype; use fontproperties")
    previous = getattr(ax, "_tategaki_handle", None)
    if previous is not None:
        previous.remove()
    kwargs = dict(
        rotation=0,
        ha="center",
        va="top",
        multialignment="center",
        linespacing=linespacing,
        parse_math=False,
        usetex=False,
    )
    if fontproperties is not None:
        kwargs["fontproperties"] = fontproperties
    if fontsize is not None:
        kwargs["fontsize"] = fontsize
    ax.set_xticks(positions, displayed, **kwargs)
    ax.tick_params(
        axis="x", which="major", bottom=True, labelbottom=True, top=False, labeltop=False, pad=pad
    )
    return ax.get_xticklabels()


class VerticalTickHandle:
    """固定した下側ラベルを保持し、軸の元の状態を復元する。

    再設定時は以前のハンドルを置き換える。イベントコールバックは使わない。
    設定後に呼び出し側が変更した軸範囲は保持する。共有 x 軸には対応しない。
    """

    def __init__(self, ax, artists):
        """軸、ラベル Artist と復元に必要な元の状態を記録する。"""
        self.ax = ax
        self.artists = tuple(artists)
        axis = ax.xaxis
        self._locator = axis.get_major_locator()
        self._formatter = axis.get_major_formatter()
        self._defaults = (axis.isDefault_majloc, axis.isDefault_majfmt)
        self._limits = ax.get_xlim()
        self._autoscale = ax.get_autoscalex_on()
        self._installed_limits = None
        self._removed = False

    def remove(self):
        """ラベル Artist を除去し、軸の主目盛り設定を一度だけ復元する。"""
        if self._removed:
            return
        self._removed = True
        for artist in self.artists:
            if artist.axes is not None:
                artist.remove()
        axis = self.ax.xaxis
        axis.set_major_locator(self._locator)
        axis.set_major_formatter(self._formatter)
        axis.isDefault_majloc, axis.isDefault_majfmt = self._defaults
        if self.ax.get_xlim() == self._installed_limits:
            self.ax.set_xlim(self._limits, auto=self._autoscale)
        if getattr(self.ax, "_tategaki_handle", None) is self:
            del self.ax._tategaki_handle
        self.ax.stale = True


def _set_opentype(ax, positions, labels, font, fontsize, pad, color, orientation):
    """OpenType の縦書きラベルを検証して軸へ取り付ける。"""
    from .artist import VerticalText

    if ax.name != "rectilinear":
        raise ValueError("opentype fixed categories require rectilinear axes")
    if len(ax.get_shared_x_axes().get_siblings(ax)) != 1:
        raise ValueError("opentype fixed categories do not support shared x axes")
    # 軸や以前のハンドルを変更する前に、すべてのラベルを検証して整形する。
    artists = [
        VerticalText(
            p,
            0,
            text,
            font=font,
            fontsize=12 if fontsize is None else fontsize,
            color=color,
            orientation=orientation,
        )
        for p, text in zip(positions, labels, strict=True)
    ]
    if not artists:
        # ラベルが空でもフォントと設定を検証する。
        VerticalText(0, 0, "", font=font, color=color, orientation=orientation).get_layout()
    for artist in artists:
        artist.get_layout()
    previous = getattr(ax, "_tategaki_handle", None)
    if previous is not None:
        previous.remove()
    handle = VerticalTickHandle(ax, artists)
    # 合成変換による基点は軸範囲と反転に追従する。ずれと字形の寸法には
    # データ座標の倍率や出力 DPI に依存しない物理的なポイントを使う。
    transform = ax.get_xaxis_transform() + ScaledTranslation(
        0, -pad / 72, ax.get_figure(root=True).dpi_scale_trans
    )
    ax.set_xticks(positions)
    ax.xaxis.set_major_formatter(NullFormatter())
    for artist in artists:
        artist.set_transform(transform)
        artist.set_in_layout(True)
        ax.add_artist(artist)
    handle._installed_limits = ax.get_xlim()
    ax._tategaki_handle = handle
    return handle
