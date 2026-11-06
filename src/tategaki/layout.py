# Copyright (c) 2026 magichan (https://github.com/magichan-lab)

"""字形の輪郭と配置を、すべてフォント単位で保持する。"""

from dataclasses import dataclass

import numpy as np
from matplotlib.path import Path
from matplotlib.transforms import Affine2D, Bbox

from .shaping import ShapedText, VerticalFont


def glyph_path(font: VerticalFont, glyph_id: int) -> Path:
    """指定した字形の輪郭を Matplotlib の読み取り専用 Path に変換する。"""
    from fontTools.pens.basePen import BasePen

    class PathPen(BasePen):
        """fontTools の輪郭命令を Matplotlib の頂点とコードに変換する。"""

        def __init__(self):
            """字形集合を設定し、頂点とコードの格納先を初期化する。"""
            super().__init__(font.glyph_set)
            self.vertices = []
            self.codes = []

        def _add(self, points, code):
            """輪郭の点列と対応する Path コードを追加する。"""
            self.vertices.extend(points)
            self.codes.extend([code] * len(points))

        def _moveTo(self, p):
            """現在位置を新しい輪郭の始点へ移す。"""
            self._add([p], Path.MOVETO)

        def _lineTo(self, p):
            """現在位置から指定点への直線を追加する。"""
            self._add([p], Path.LINETO)

        def _curveToOne(self, a, b, c):
            """二つの制御点と終点から三次ベジェ曲線を追加する。"""
            self._add([a, b, c], Path.CURVE4)

        def _qCurveToOne(self, a, b):
            """制御点と終点から二次ベジェ曲線を追加する。"""
            self._add([a, b], Path.CURVE3)

        def _closePath(self):
            """現在の輪郭を閉じる。"""
            self._add([(0, 0)], Path.CLOSEPOLY)

        def _endPath(self):
            """開いた輪郭の終端を処理する。"""
            pass

    pen = PathPen()
    font.glyph_set[font.glyph_order[glyph_id]].draw(pen)
    return Path(
        np.array(pen.vertices, dtype=float).reshape(-1, 2),
        np.array(pen.codes, dtype=Path.code_type),
        readonly=True,
    )


@dataclass(frozen=True)
class VerticalLayout:
    """整形結果、輪郭、描画範囲と論理範囲を保持する。"""

    shaped: ShapedText
    path: Path
    ink_bounds: tuple[float, float, float, float] | None
    logical_bounds: tuple[float, float, float, float]
    bounds: tuple[float, float, float, float]


def make_layout(font: VerticalFont, text: str, orientation="upright") -> VerticalLayout:
    """文字列を整形し、輪郭と描画・論理範囲を組み立てる。"""
    shaped = font.shape(text, orientation)
    outlines = {}
    paths = []
    for glyph in shaped.glyphs:
        if glyph.glyph_id not in outlines:
            outlines[glyph.glyph_id] = glyph_path(font, glyph.glyph_id)
        path = outlines[glyph.glyph_id]
        if len(path.vertices):
            paths.append(
                Affine2D()
                .rotate_deg(-glyph.rotation)
                .translate(glyph.x, glyph.y)
                .transform_path(path)
            )
    path = Path.make_compound_path(*paths) if paths else Path(np.empty((0, 2)), readonly=True)
    ink = path.get_extents() if paths else None
    columns = text.count("\n") + 1 if text else 0
    logical = Bbox.from_extents(
        -(columns - 0.5) * font.upem if columns else 0,
        -shaped.advance,
        font.upem / 2 if columns else 0,
        0,
    )
    bounds = Bbox.union([logical, ink]) if ink is not None else logical
    return VerticalLayout(
        shaped,
        path,
        tuple(ink.extents) if ink is not None else None,
        tuple(logical.extents),
        tuple(bounds.extents),
    )
