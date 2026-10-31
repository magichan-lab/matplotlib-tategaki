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

    主目盛りの Locator と Formatter を固定カテゴリ用に置き換える。位置には
    重複のない有限な実数を指定する。ラベル名の重複は許可する。``pad`` は
    Axes 下端からのポイント単位の距離で、目盛り線の長さを考慮する。
    ``linespacing`` は Matplotlib の行間であり、フォントの送り量ではない。
    ``stacked`` は通常の Text のリストを返す。``opentype`` は ``font`` が
    必須で、VerticalTickHandle を返す。軸タイトルの余白は ``labelpad`` で指定する。
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
        if font is None:
            raise ValueError("opentype requires an explicit font file")
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
    # Validate and shape everything before changing the axis or old handle.
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
        # Even an empty installation validates its font and options.
        VerticalText(0, 0, "", font=font, color=color, orientation=orientation).get_layout()
    for artist in artists:
        artist.get_layout()
    previous = getattr(ax, "_tategaki_handle", None)
    if previous is not None:
        previous.remove()
    handle = VerticalTickHandle(ax, artists)
    # A blended anchor tracks limits/inversion; the offset and glyph sizes are
    # in physical points, independent of data scaling and output DPI.
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
