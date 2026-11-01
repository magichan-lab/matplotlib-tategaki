# Copyright (c) 2026 magichan (https://github.com/magichan-lab)

"""Matplotlib の文字描画と固定 x 目盛りに縦書き機能を追加する。"""

from functools import WRAPPER_ASSIGNMENTS, wraps
from inspect import signature

from matplotlib.artist import allow_rasterization
from matplotlib.axes import Axes
from matplotlib.text import Text
from matplotlib.ticker import FixedLocator
from matplotlib.transforms import Affine2D

from .ticks import set_xticklabels

_originals = {}
_WRAPPER_ASSIGNMENTS = tuple(name for name in WRAPPER_ASSIGNMENTS if name != "__doc__")


class WrappedVerticalText(Text):
    """縦書きの字形を描画する、Matplotlib の Text と互換のラベル。

    配置位置は回転前の縦書き領域を基準とする。縦書きの輪郭には横書きの
    ベースラインがないため、ベースライン指定時は領域の下端を使う。
    """

    def __init__(self, *args, font, orientation="upright", **kwargs):
        """文字属性と縦書き用フォントを設定し、文字列を検証する。"""
        from .artist import VerticalText

        if font is None:
            raise ValueError("vertical text requires an explicit font file")
        self._vertical = VerticalText(0, 0, "", font=font, orientation=orientation)
        super().__init__(*args, **kwargs)
        self._vertical.set_text(self.get_text())
        self._vertical.get_layout()

    def _prepare_vertical(self, renderer):
        """現在の文字属性を縦書き Artist に反映し、描画位置を計算する。"""
        v = self._vertical
        if self.get_rotation() != 0 or self.get_bbox_patch() is not None:
            raise ValueError("vertical text does not support rotation or bbox")
        if self.get_usetex() or self.get_wrap() or self.get_path_effects():
            raise ValueError("vertical text does not support usetex, wrap or path_effects")
        if v.get_text() != self.get_text():
            v.set_text(self.get_text())
        v.set_fontsize(self.get_fontsize())
        v.set_color(self.get_color())
        v.set_alpha(self.get_alpha())
        v.set_clip_on(self.get_clip_on())
        v.set_clip_box(self.get_clip_box())
        v.set_clip_path(self.get_clip_path())
        x, y = self.get_transform().transform(self.get_unitless_position())
        scale = renderer.points_to_pixels(self.get_fontsize()) / v._font.upem
        x0, y0, x1, y1 = v.get_layout().bounds
        dx = {"left": x0, "center": (x0 + x1) / 2, "right": x1}[self.get_ha()]
        dy = {
            "top": y1,
            "center": (y0 + y1) / 2,
            "center_baseline": (y0 + y1) / 2,
            "bottom": y0,
            "baseline": y0,
        }[self.get_va()]
        v.set_transform(Affine2D().translate(x - dx * scale, y - dy * scale))
        v.set_position((0, 0))
        return v

    def get_window_extent(self, renderer=None, dpi=None):
        """指定した描画器と DPI に対する縦書き文字の表示範囲を返す。"""
        if renderer is None:
            renderer = self.get_figure(root=True)._get_renderer()
        if dpi is not None and dpi != self.get_figure(root=True).dpi:
            from matplotlib import cbook

            with cbook._setattr_cm(self.get_figure(root=True), dpi=dpi):
                return self._prepare_vertical(renderer).get_window_extent(renderer)
        return self._prepare_vertical(renderer).get_window_extent(renderer)

    @allow_rasterization
    def draw(self, renderer):
        """表示中の縦書き文字を指定した描画器に描画する。"""
        if self.get_visible():
            self._prepare_vertical(renderer).draw(renderer)
            self.stale = False


def _options(kwargs):
    """キーワード引数から書字方向を取り出し、縦書きかどうかを返す。"""
    mode = kwargs.pop("writing_mode", "horizontal-tb")
    if mode not in {"horizontal-tb", "vertical-rl"}:
        raise ValueError("writing_mode must be 'horizontal-tb' or 'vertical-rl'")
    return mode == "vertical-rl"


def _text(original):
    """Axes.text に縦書きの選択肢を追加するラッパーを作る。"""

    @wraps(original, assigned=_WRAPPER_ASSIGNMENTS)
    def wrapped(ax, x, y, s, fontdict=None, **kwargs):
        """書字方向に応じて通常または縦書きの文字を軸へ追加する。"""
        kwargs = {**(fontdict or {}), **kwargs}
        if not _options(kwargs):
            return original(ax, x, y, s, **kwargs)
        artist = WrappedVerticalText(
            x, y, s, **{"transform": ax.transData, "clip_on": False, **kwargs}
        )
        # 軸へ追加する前に、対応していない描画属性を検証する。
        artist._prepare_vertical(ax.get_figure(root=True)._get_renderer())
        if artist.get_clip_path() is None:
            artist.set_clip_path(ax.patch)
        ax._add_text(artist)
        return artist

    return wrapped


def _label(original, axis_name):
    """軸タイトルの設定時に縦書きラベルへ切り替えるラッパーを作る。"""

    @wraps(original, assigned=_WRAPPER_ASSIGNMENTS)
    def wrapped(ax, *args, **options):
        """指定した軸のタイトルを通常または縦書きの Text で設定する。"""
        bound = signature(original).bind(ax, *args, **options)
        bound.apply_defaults()
        label = bound.arguments["xlabel" if axis_name == "xaxis" else "ylabel"]
        fontdict = bound.arguments["fontdict"]
        labelpad = bound.arguments["labelpad"]
        loc = bound.arguments["loc"]
        kwargs = bound.arguments["kwargs"]
        kwargs = {**(fontdict or {}), **kwargs}
        vertical = _options(kwargs)
        axis = getattr(ax, axis_name)
        old = axis.label
        replacement = None
        if vertical:
            font = kwargs.pop("font", None)
            orientation = kwargs.pop("orientation", "upright")
            replacement = WrappedVerticalText(text=label, font=font, orientation=orientation)
        elif isinstance(old, WrappedVerticalText):
            replacement = Text()
        if replacement is not None:
            replacement.update_from(old)
            replacement.set_position(old.get_position())
            replacement.set_figure(ax.get_figure(root=False))
            replacement.set_rotation(0 if vertical or axis_name == "xaxis" else 90)
            if vertical:
                replacement.set_va("center")
            axis.label = replacement
        try:
            result = original(ax, label, labelpad=labelpad, loc=loc, **kwargs)
            if vertical:
                result._prepare_vertical(ax.get_figure(root=True)._get_renderer())
            return result
        except Exception:
            axis.label = old
            raise

    return wrapped


def _ticks(original, with_positions):
    """x 軸の目盛り設定に縦書きラベルを追加するラッパーを作る。"""

    @wraps(original, assigned=_WRAPPER_ASSIGNMENTS)
    def wrapped(ax, *args, **options):
        """固定位置とラベルを検証し、書字方向に応じて目盛りを設定する。"""
        bound = signature(original).bind(ax, *args, **options)
        bound.apply_defaults()
        values = bound.arguments["ticks" if with_positions else "labels"]
        kwargs = {**(bound.arguments.get("fontdict") or {}), **bound.arguments["kwargs"]}
        if not _options(kwargs):
            previous = getattr(ax, "_tategaki_handle", None)
            if previous is not None:
                previous.remove()
            options.pop("writing_mode", None)
            return original(ax, *args, **options)
        if ax.name != "rectilinear":
            raise ValueError("vertical ticks require rectilinear axes")
        minor = bound.arguments["minor"]
        if minor:
            raise ValueError("vertical ticks support major ticks only")
        if with_positions:
            labels = bound.arguments["labels"]
            if labels is None:
                raise ValueError("vertical set_xticks requires explicit labels")
            positions = values
        else:
            if not isinstance(ax.xaxis.get_major_locator(), FixedLocator):
                raise ValueError("call set_xticks before vertical set_xticklabels")
            positions, labels = ax.get_xticks(), values
        return set_xticklabels(ax, positions, labels, engine="opentype", **kwargs)

    return wrapped


def enable():
    """対応する Axes メソッドで書字方向の指定を有効にする。

    繰り返し呼び出しても同じ状態を保つ。対応する pyplot 関数も、
    これらの Axes メソッドを経由して縦書きを利用できる。
    """
    if _originals:
        return
    factories = {
        "text": _text,
        "set_xlabel": lambda f: _label(f, "xaxis"),
        "set_ylabel": lambda f: _label(f, "yaxis"),
        "set_xticks": lambda f: _ticks(f, True),
        "set_xticklabels": lambda f: _ticks(f, False),
    }
    for name, factory in factories.items():
        original = getattr(Axes, name)
        wrapper = factory(original)
        _originals[name] = (original, wrapper)
        setattr(Axes, name, wrapper)


def disable():
    """元の Axes メソッドを復元する。作成済みの縦書き文字は描画され続ける。"""
    for name, (original, wrapper) in _originals.items():
        if getattr(Axes, name) is wrapper:
            setattr(Axes, name, original)
    _originals.clear()
