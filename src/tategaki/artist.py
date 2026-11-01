# Copyright (c) 2026 magichan (https://github.com/magichan-lab)

"""上端中央を基点に縦書きの字形輪郭を描く Artist を提供する。"""

import math

from matplotlib import colors, rcParams
from matplotlib.artist import Artist, allow_rasterization
from matplotlib.transforms import Affine2D, Bbox

from .layout import make_layout
from .shaping import VerticalFont
from .stacking import stack_label


class VerticalText(Artist):
    """座標 ``(x, y)`` を上端中央として日本語の縦書きを描く。

    変換は基点の位置だけに適用し、字形の大きさは常にポイントで指定する。
    輪郭には y 軸が上向きのフォント座標を使う。描画範囲には字形の輪郭と、
    空白セルを含む論理的な送り量の両方を含める。
    """

    def __init__(
        self, x, y, text, *, font, fontsize=12, color="black", orientation="upright", **kwargs
    ):
        """基点、文字列、フォント、文字サイズと描画属性を設定する。"""
        super().__init__()
        self._layout = None
        self._font = None
        self.set_position((x, y))
        self.set_text(text)
        self.set_font(font)
        self.set_fontsize(fontsize)
        self.set_orientation(orientation)
        self.set_color(color)
        self.set_clip_on(False)
        self.update(kwargs)

    def _invalidate(self):
        """キャッシュした配置を破棄し、再描画が必要であることを示す。"""
        self._layout = None
        self.stale = True

    def set_text(self, text):
        """文字列を検証して設定し、配置キャッシュを破棄する。"""
        stack_label(text)
        self._text = text
        self._invalidate()

    def get_text(self):
        """現在の文字列を返す。"""
        return self._text

    def set_font(self, font):
        """フォントファイルを読み込んで設定する。"""
        self._font = VerticalFont(font)
        self._invalidate()

    def set_orientation(self, orientation):
        """文字の配置方式を ``upright`` または ``mixed`` に設定する。"""
        if orientation not in {"upright", "mixed"}:
            raise ValueError('orientation must be "upright" or "mixed"')
        self._orientation = orientation
        self._invalidate()

    def set_fontsize(self, fontsize):
        """正の有限値を文字サイズとしてポイント単位で設定する。"""
        size = float(fontsize)
        if not math.isfinite(size) or size <= 0:
            raise ValueError("fontsize must be positive and finite")
        self._fontsize = size
        self.stale = True

    def get_fontsize(self):
        """文字サイズをポイント単位で返す。"""
        return self._fontsize

    def set_position(self, xy):
        """基点の座標を有限な二つの数値で設定する。"""
        x, y = map(float, xy)
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("position must be finite")
        self._position = (x, y)
        self.stale = True

    def get_position(self):
        """基点の座標を返す。"""
        return self._position

    def set_color(self, color):
        """Matplotlib が解釈できる色を設定する。"""
        colors.to_rgba(color)
        self._color = color
        self.stale = True

    def get_color(self):
        """現在の描画色を返す。"""
        return self._color

    def get_layout(self):
        """DPI に依存しないフォント単位の整形結果と輪郭を返す。"""
        if self._layout is None:
            self._layout = make_layout(self._font, self._text, self._orientation)
        return self._layout

    def _renderer(self, renderer):
        """指定された描画器、または所属する Figure の描画器を返す。"""
        if renderer is not None:
            return renderer
        fig = self.get_figure(root=True)
        if fig is None:
            raise ValueError("attach the Artist to a Figure or supply a renderer")
        return fig._get_renderer()

    def _display_transform(self, renderer):
        """フォント単位の輪郭を表示座標へ変換する変換行列を返す。"""
        scale = renderer.points_to_pixels(self._fontsize) / self._font.upem
        x, y = self.get_transform().transform(self._position)
        return Affine2D().scale(scale).translate(x, y)

    def get_window_extent(self, renderer=None):
        """字形の輪郭と論理送り量を含む表示座標の範囲を返す。"""
        renderer = self._renderer(renderer)
        return self._display_transform(renderer).transform_bbox(
            Bbox.from_extents(*self.get_layout().bounds)
        )

    def get_tightbbox(self, renderer=None):
        """クリッピングを反映した表示座標の範囲を返す。"""
        # Artist の実装により、この範囲とクリッピング領域の共通部分が返る。
        return super().get_tightbbox(self._renderer(renderer))

    @allow_rasterization
    def draw(self, renderer):
        """現在の配置から字形輪郭を描画する。"""
        if not self.get_visible():
            return
        layout = self.get_layout()
        if len(layout.path.vertices):
            gc = renderer.new_gc()
            try:
                self._set_gc_clip(gc)
                gc.set_foreground(self._color)
                gc.set_alpha(self.get_alpha())
                gc.set_linewidth(0)
                gc.set_antialiased(rcParams["patch.antialiased"])
                renderer.draw_path(
                    gc,
                    layout.path,
                    self._display_transform(renderer),
                    rgbFace=colors.to_rgba(self._color),
                )
            finally:
                gc.restore()
        self.stale = False
