# Copyright (c) 2026 magichan (https://github.com/magichan-lab)

"""OpenType の字形整形をフォント単位で行う。追加依存は必要時に読み込む。"""

import warnings
from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path

import regex

from .orientation import cluster_orientation
from .stacking import stack_label


class UnsupportedFontError(ValueError):
    """フォントが対応する縦組み輪郭処理を提供できない場合の例外。"""


class MissingGlyphError(ValueError):
    """指定したフォントで入力書記素を描画できない場合の例外。"""


class VerticalGlyphWarning(UserWarning):
    """縦書き用の代替字形が必要な文字に代替がない場合の警告。"""


@dataclass(frozen=True)
class Run:
    """文字列内の連続した整形単位と、その用字系・方向を保持する。"""

    text: str
    start: int
    end: int
    script: str
    direction: str
    vertical_orientation: str = "U"
    rotation: int = 0  # clockwise degrees, after horizontal shaping


@dataclass(frozen=True)
class Glyph:
    """整形済み字形の ID、移動量、配置位置、回転角を保持する。"""

    glyph_id: int
    cluster: int
    x_advance: int
    y_advance: int
    x_offset: int
    y_offset: int
    x: float
    y: float
    rotation: int = 0


@dataclass(frozen=True)
class ShapedText:
    """元の文字列、ラン、書記素範囲、字形と総送り量を保持する。"""

    text: str
    runs: tuple[Run, ...]
    graphemes: tuple[tuple[int, int], ...]
    glyphs: tuple[Glyph, ...]
    advance: float


def split_runs(
    text: str, orientation="upright"
) -> tuple[tuple[Run, ...], tuple[tuple[int, int], ...]]:
    """書記素を保ちながら、入力文字列を用字系と描画方向で分割する。

    一般的な句読点には隣接する日本語の用字系を使い、該当しない場合は漢字扱いにする。
    ``mixed`` モードでは横向きのラテン文字を連結する。対応外の用字系は
    受け付けない。返す範囲は元の文字列の Python 文字インデックスである。
    """
    if orientation not in {"upright", "mixed"}:
        raise ValueError('orientation must be "upright" or "mixed"')
    stack_label(text)  # shared type/control validation; never normalize
    matches = list(regex.finditer(r"\X", text))
    scripts = []
    for match in matches:
        chars = match.group()
        script = next(
            (
                tag
                for name, tag in [
                    ("Hiragana", "Hira"),
                    ("Katakana", "Kana"),
                    ("Han", "Hani"),
                    ("Latin", "Latn"),
                ]
                if regex.search(rf"\p{{Script={name}}}", chars)
            ),
            None,
        )
        if regex.search(
            r"[^\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}"
            r"\p{Script=Latin}\p{Script=Common}\p{Script=Inherited}]",
            chars,
        ):
            raise ValueError("only Japanese, Latin and common/inherited characters are supported")
        scripts.append(script)
    runs = []
    for i, match in enumerate(matches):
        script = scripts[i]
        vo = cluster_orientation(match.group()) if orientation == "mixed" else "U"
        if script is None:
            # ASCII symbols/numbers/spaces are individual upright cells.
            if all(ord(c) < 128 for c in match.group()) or vo == "R":
                script = "Latn"
            else:
                script = next(
                    (s for s in reversed(scripts[:i]) if s in {"Hani", "Hira", "Kana"}), None
                )
                script = script or next(
                    (s for s in scripts[i + 1 :] if s in {"Hani", "Hira", "Kana"}), "Hani"
                )
        direction = "ltr" if script == "Latn" else "ttb"
        rotation = 0
        if orientation == "mixed":
            if vo == "R":
                direction, rotation = "ltr", 90
            elif vo in {"Tu", "Tr"}:
                direction = "ttb"
        run = Run(match.group(), match.start(), match.end(), script, direction, vo, rotation)
        if (
            runs
            and (direction == "ttb" or rotation)
            and vo != "Tr"
            and runs[-1].script == script
            and runs[-1].direction == direction
            and runs[-1].rotation == rotation
            and runs[-1].vertical_orientation == vo
        ):
            prev = runs.pop()
            run = replace(run, text=prev.text + run.text, start=prev.start)
        runs.append(run)
    return tuple(runs), tuple(m.span() for m in matches)


class VerticalFont:
    """単一の静的 sfnt フォントを読み込み、整形と輪郭生成で共有する。"""

    def __init__(self, filename):
        """フォントファイルを読み込み、縦組みに必要な表と機能を検証する。"""
        try:
            import uharfbuzz as hb
            from fontTools.ttLib import TTFont
        except ImportError as exc:
            raise ImportError(
                "VerticalText requires: pip install 'matplotlib-tategaki[opentype]'"
            ) from exc
        self.filename = str(Path(filename).resolve())
        self.data = Path(filename).read_bytes()
        if self.data[:4] == b"ttcf":
            raise UnsupportedFontError(
                "TTC collections are unsupported; supply a single static TTF/OTF"
            )
        self.ttfont = TTFont(BytesIO(self.data))
        font = self.ttfont
        if "fvar" in font or "CFF2" in font:
            raise UnsupportedFontError("variable fonts and CFF2 are unsupported")
        if not any(t in font for t in ("glyf", "CFF ")):
            raise UnsupportedFontError("only TrueType glyf and static CFF outlines are supported")
        self.features = (
            frozenset(r.FeatureTag for r in font["GSUB"].table.FeatureList.FeatureRecord)
            if "GSUB" in font and font["GSUB"].table.FeatureList
            else frozenset()
        )
        if not {"vhea", "vmtx"}.issubset(font.keys()) or not self.features.intersection(
            {"vert", "vrt2"}
        ):
            raise UnsupportedFontError(
                "font requires vhea/vmtx and a vert or vrt2 substitution feature"
            )
        self.upem = font["head"].unitsPerEm
        self.glyph_order = font.getGlyphOrder()
        self.glyph_set = font.getGlyphSet()
        self.hb = hb
        self.hb_font = hb.Font(hb.Face(self.data))
        self.hb_font.scale = (self.upem, self.upem)
        hb.ot_font_set_funcs(self.hb_font)
        self.cmap = font.getBestCmap() or {}

    def _shape(self, text, script, direction):
        """指定した用字系と方向で HarfBuzz の字形情報と位置を返す。"""
        buf = self.hb.Buffer()
        buf.add_codepoints([ord(c) for c in text])
        buf.direction = direction
        buf.script = script
        buf.language = "ja" if script != "Latn" else "en"
        buf.cluster_level = self.hb.BufferClusterLevel.MONOTONE_GRAPHEMES
        # Use HarfBuzz defaults, including its choice of vert/vrt2.
        self.hb.shape(self.hb_font, buf)
        return tuple(zip(buf.glyph_infos, buf.glyph_positions, strict=True))

    def shape(self, text: str, orientation="upright") -> ShapedText:
        """文字列を整形し、フォント単位の字形配置と送り量を返す。

        未対応の異体字列や ZWJ 列、欠落した字形は例外にする。
        縦書き用の代替字形がない場合は警告する。
        """
        runs, graphemes = split_runs(text, orientation)
        original_runs = runs
        # Unsupported variation sequences must not silently display a base glyph.
        variations = self.ttfont["cmap"].getcmap(0, 5)
        for i, char in enumerate(text):
            cp = ord(char)
            if 0xFE00 <= cp <= 0xFE0F or 0xE0100 <= cp <= 0xE01EF:
                entries = variations.uvsDict.get(cp, []) if variations else []
                if i == 0 or not any(base == ord(text[i - 1]) for base, _ in entries):
                    raise MissingGlyphError(f"unsupported variation sequence at input index {i}")
            elif char == "\u200d":
                raise MissingGlyphError("ZWJ sequences are outside this font rendering scope")
        if orientation == "mixed":
            resolved = []
            for run in runs:
                if run.vertical_orientation == "Tr":
                    vertical = self._shape(run.text, run.script, "ttb")
                    horizontal = self._shape(run.text, run.script, "ltr")
                    if [i.codepoint for i, _ in vertical] == [i.codepoint for i, _ in horizontal]:
                        run = replace(run, direction="ltr", rotation=90)
                if (
                    resolved
                    and run.rotation
                    and resolved[-1].rotation
                    and resolved[-1].script == run.script
                ):
                    previous = resolved.pop()
                    run = replace(run, text=previous.text + run.text, start=previous.start)
                resolved.append(run)
            runs = tuple(resolved)
        glyphs = []
        pen_y = 0.0
        for run in runs:
            shaped = self._shape(run.text, run.script, run.direction)
            if any(info.codepoint == 0 for info, _ in shaped):
                raise MissingGlyphError(
                    f"missing glyph in input span [{run.start}:{run.end}]: {run.text!r}"
                )
            if run.rotation:
                # Rotate the whole horizontal run clockwise. Its horizontal
                # advance becomes downward advance; preserve kerning/marks.
                center = (self.ttfont["hhea"].ascent + self.ttfont["hhea"].descent) / 2
                pen_x, horizontal_y = 0, 0
                for info, pos in shaped:
                    glyphs.append(
                        Glyph(
                            info.codepoint,
                            run.start + info.cluster,
                            pos.x_advance,
                            pos.y_advance,
                            pos.x_offset,
                            pos.y_offset,
                            horizontal_y + pos.y_offset - center,
                            pen_y - pen_x - pos.x_offset,
                            90,
                        )
                    )
                    pen_x += pos.x_advance
                    horizontal_y += pos.y_advance
                pen_y -= pen_x
            elif run.direction == "ltr":
                # One grapheme per em, with horizontal shaping for upright Latin.
                width = sum(p.x_advance for _, p in shaped)
                pen_x = -width / 2
                baseline = (
                    pen_y
                    - (self.upem + self.ttfont["hhea"].ascent + self.ttfont["hhea"].descent) / 2
                )
                for info, pos in shaped:
                    glyphs.append(
                        Glyph(
                            info.codepoint,
                            run.start + info.cluster,
                            pos.x_advance,
                            pos.y_advance,
                            pos.x_offset,
                            pos.y_offset,
                            pen_x + pos.x_offset,
                            baseline + pos.y_offset,
                        )
                    )
                    pen_x += pos.x_advance
                pen_y -= self.upem
            else:
                pen_x = 0
                for info, pos in shaped:
                    glyphs.append(
                        Glyph(
                            info.codepoint,
                            run.start + info.cluster,
                            pos.x_advance,
                            pos.y_advance,
                            pos.x_offset,
                            pos.y_offset,
                            pen_x + pos.x_offset,
                            pen_y + pos.y_offset,
                        )
                    )
                    pen_x += pos.x_advance
                    pen_y += pos.y_advance
        # These characters normally need vertical alternates. Feature presence
        # alone does not establish character coverage.
        warning_clusters = [
            (char, "Kana" if char == "ー" else "Hani")
            for char in sorted(set(text).intersection("「」『』（）［］｛｝〈〉《》【】〔〕、。ー"))
        ]
        if orientation == "mixed":
            warning_clusters = sorted(
                {
                    (text[a:b], run.script)
                    for run in original_runs
                    for a, b in graphemes
                    if run.start <= a < run.end and cluster_orientation(text[a:b]) in {"Tu", "Tr"}
                }
            )
        for char, script in warning_clusters:
            vertical = self._shape(char, script, "ttb")
            horizontal = self._shape(char, script, "ltr")
            if [i.codepoint for i, _ in vertical] == [i.codepoint for i, _ in horizontal]:
                warnings.warn(
                    f"no vertical alternate for {char!r} (U+{ord(char[0]):04X})",
                    VerticalGlyphWarning,
                    stacklevel=2,
                )
        return ShapedText(text, runs, graphemes, tuple(glyphs), -pen_y)
