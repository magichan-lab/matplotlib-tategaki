# Copyright (c) 2026 magichan (https://github.com/magichan-lab)

"""テスト用フォントで字形 ID、代替字形と輪郭形式を確認する。"""

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pytest

pytest.importorskip("uharfbuzz")
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable

from tategaki import VerticalText
from tategaki.layout import make_layout
from tategaki.shaping import (
    MissingGlyphError,
    UnsupportedFontError,
    VerticalFont,
    VerticalGlyphWarning,
    split_runs,
)


@pytest.fixture(params=[True, False], ids=["glyf", "cff"])
def font_file(tmp_path, request):
    """TrueType または CFF 形式の縦組み対応テスト用フォントを作る。"""
    is_ttf = request.param
    chars = "ABＣ東京かがきゃっケーキ「」、。$fi1\u3099\u0301\u20dd"
    cmap = {ord(c): f"u{ord(c):04X}" for c in chars}
    cmap[32] = "space"
    names = [".notdef", "space", *[n for n in dict.fromkeys(cmap.values()) if n != "space"]]
    alternates = [cmap[ord(c)] + ".vert" for c in "ー「」、。"]
    names += alternates
    names.append("fi.liga")
    builder = FontBuilder(1000, isTTF=is_ttf)
    builder.setupGlyphOrder(names)
    builder.setupCharacterMap(cmap)
    outlines = {}
    for name in names:
        pen = TTGlyphPen(None) if is_ttf else T2CharStringPen(600, None)
        if name != "space":
            pen.moveTo((50, 0))
            pen.lineTo((550, 0))
            if is_ttf:
                pen.qCurveTo((600, 800), (300, 700))
            else:
                pen.curveTo((600, 400), (400, 900), (300, 700))
            pen.lineTo((50, 700))
            pen.closePath()
        outlines[name] = pen.glyph() if is_ttf else pen.getCharString()
    if is_ttf:
        builder.setupGlyf(outlines)
    else:
        builder.setupCFF("TestVertical", {"FullName": "Test Vertical"}, outlines, {})
    builder.setupHorizontalMetrics({name: (600, 50) for name in names})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupVerticalMetrics({name: (1000, 100) for name in names})
    builder.setupVerticalHeader(ascent=500, descent=-500)
    builder.setupNameTable({"familyName": "Test Vertical", "styleName": "Regular"})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    builder.setupPost()
    substitutions = " ".join(f"sub {cmap[ord(c)]} by {cmap[ord(c)]}.vert;" for c in "ー「」、。")
    addOpenTypeFeaturesFromString(
        builder.font,
        f"""
        feature vert {{ {substitutions} }} vert;
        feature liga {{ sub u0066 u0069 by fi.liga; }} liga;
        feature kern {{ pos u0041 u0042 -100; }} kern;
    """,
    )
    filename = tmp_path / ("test.ttf" if is_ttf else "test.otf")
    builder.save(filename)
    return filename


def test_runs_keep_codepoints_and_script_context():
    """ラン分割で元の文字位置と用字系の文脈を保持することを確認する。"""
    text = "「ケーキ、東京。」Aか\u3099B"
    runs, spans = split_runs(text)
    assert "".join(r.text for r in runs) == text
    assert [(r.text, r.script, r.direction) for r in runs][-3:] == [
        ("A", "Latn", "ltr"),
        ("か\u3099", "Hira", "ttb"),
        ("B", "Latn", "ltr"),
    ]
    assert any(text[a:b] == "か\u3099" for a, b in spans)
    assert all(text[r.start : r.end] == r.text for r in runs)
    with pytest.raises(ValueError):
        split_runs("العربية")


def test_glyph_ids_substitution_clusters_and_spacing(font_file):
    """字形 ID、縦書き代替、クラスタと送り量を確認する。"""
    font = VerticalFont(font_file)
    shaped = font.shape("「ケーキ、東京。」AB")
    assert shaped.advance == 11000
    assert [g.cluster for g in shaped.glyphs] == list(range(11))
    assert all(g.y_advance == -1000 for g in shaped.glyphs[:-2])
    for char in "「ー、。」":
        shaped_char = font.shape(char)
        assert font.glyph_order[shaped_char.glyphs[0].glyph_id].endswith(".vert")
    assert [r.text for r in font.shape("AB").runs] == ["A", "B"]
    assert font.shape("か\u3099").graphemes == ((0, 2),)
    assert font.shape("か\u3099").glyphs[0].cluster == 0
    assert make_layout(font, " ").ink_bounds is None
    assert make_layout(font, " ").logical_bounds == (-500, -1000, 500, 0)
    assert make_layout(font, "").bounds == (0, 0, 0, 0)


def test_errors_and_missing_alternate_warning(font_file, tmp_path):
    """未対応フォントや欠落字形の例外と代替字形の警告を確認する。"""
    font = VerticalFont(font_file)
    for text in ["無", "A\ufe0f", "A\u200dB"]:
        with pytest.raises(MissingGlyphError):
            font.shape(text)
    with pytest.raises(ValueError):
        font.shape("A", "sideways")
    with pytest.raises(ValueError):
        font.shape("A\n")
    with pytest.raises(TypeError):
        font.shape(None)
    # Feature coverage is checked per punctuation, not just at font loading.
    tt = TTFont(font_file)
    for lookup in tt["GSUB"].table.LookupList.Lookup:
        for table in lookup.SubTable:
            if hasattr(table, "mapping"):
                table.mapping.pop("u3001", None)
    tt.save(font_file)
    with pytest.warns(VerticalGlyphWarning, match="U\\+3001"):
        VerticalFont(font_file).shape("、")
    variable = TTFont(font_file)
    variable["fvar"] = newTable("fvar")
    variable["fvar"].axes = []
    variable["fvar"].instances = []
    variable_path = tmp_path / "variable.ttf"
    variable.save(variable_path)
    with pytest.raises(UnsupportedFontError, match="variable"):
        VerticalFont(variable_path)
    nofeature = TTFont(font_file)
    del nofeature["GSUB"]
    nofeature_path = tmp_path / "nofeature.ttf"
    nofeature.save(nofeature_path)
    with pytest.raises(UnsupportedFontError, match="vert or vrt2"):
        VerticalFont(nofeature_path)
    del tt["vhea"]
    del tt["vmtx"]
    tt.save(font_file)
    with pytest.raises(UnsupportedFontError, match="vhea/vmtx"):
        VerticalFont(font_file)
    collection = tmp_path / "collection.ttc"
    collection.write_bytes(b"ttcf")
    with pytest.raises(UnsupportedFontError, match="TTC"):
        VerticalFont(collection)


def test_outline_curves_and_extents(font_file):
    """輪郭の曲線コードと描画範囲を確認する。"""
    font = VerticalFont(font_file)
    layout = make_layout(font, "A「が")
    expected_curve = (
        matplotlib.path.Path.CURVE3 if font_file.suffix == ".ttf" else matplotlib.path.Path.CURVE4
    )
    assert expected_curve in layout.path.codes
    assert matplotlib.path.Path.CLOSEPOLY in layout.path.codes
    ink = layout.path.get_extents()
    bounds = matplotlib.transforms.Bbox.from_extents(*layout.bounds)
    assert bounds.contains(ink.x0, ink.y0)
    assert bounds.contains(ink.x1, ink.y1)


@pytest.mark.parametrize("orientation", ["upright", "mixed"])
def test_predraw_bbox_raster_ink_and_mutations(font_file, orientation):
    """描画前の範囲、ラスタ描画結果と属性変更時の更新を確認する。"""
    fig = plt.figure(figsize=(4, 4), dpi=100)
    artist = VerticalText(
        0.5,
        0.9,
        "A「が",
        font=font_file,
        fontsize=24,
        transform=fig.transFigure,
        color="blue",
        orientation=orientation,
    )
    fig.add_artist(artist)
    before = artist.get_window_extent().frozen()
    np.testing.assert_allclose(artist.get_tightbbox().extents, before.extents)
    layout = artist.get_layout()
    fig.canvas.draw()
    rgba = np.asarray(fig.canvas.buffer_rgba())
    rows, cols = np.where((rgba[:, :, 2] > 128) & (rgba[:, :, 0] < 128))
    assert len(rows)
    # Image rows are y-down, display extents are y-up; allow antialiasing 1px.
    assert cols.min() >= before.x0 - 1 and cols.max() <= before.x1 + 1
    assert fig.bbox.height - rows.max() >= before.y0 - 1
    assert fig.bbox.height - rows.min() <= before.y1 + 1
    for _ in range(3):
        fig.canvas.draw()
    assert len(fig.artists) == 1
    np.testing.assert_allclose(artist.get_window_extent().extents, before.extents)
    fig.set_dpi(200)
    doubled = artist.get_window_extent().frozen()
    np.testing.assert_allclose(doubled.extents, before.extents * 2)
    assert artist.get_layout() is layout
    artist.set_fontsize(12)
    assert artist.get_window_extent().height == pytest.approx(doubled.height / 2)
    artist.set_text("A")
    assert artist.get_layout() is not layout
    assert artist.get_window_extent().height < doubled.height / 2
    artist.set_text("AB")
    first = artist.get_window_extent().frozen()
    artist.set_position((0.6, 0.8))
    moved = artist.get_window_extent().frozen()
    assert moved.x0 > first.x0 and moved.y1 < first.y1
    artist.set_transform(matplotlib.transforms.Affine2D().translate(20, 30) + fig.transFigure)
    assert artist.get_window_extent().x0 > moved.x0
    artist.set_font(font_file)
    assert artist.get_layout() is not layout
    for invalid in [0, -1, float("nan"), float("inf")]:
        with pytest.raises(ValueError):
            artist.set_fontsize(invalid)
    plt.close(fig)


@pytest.mark.parametrize("orientation", ["upright", "mixed"])
def test_direct_save_and_resize(font_file, orientation):
    """保存と Figure のサイズ変更後にも描画範囲が正しいことを確認する。"""
    fig = plt.figure(figsize=(3, 3))
    artist = VerticalText(
        0.5,
        0.95,
        "「ケーキ。」AB",
        font=font_file,
        transform=fig.transFigure,
        fontsize=14,
        orientation=orientation,
    )
    fig.add_artist(artist)
    for size, dpi in [((3, 3), 100), ((4, 4), 200)]:
        fig.set_size_inches(*size)
        fig.set_dpi(dpi)
        for fmt in ["png", "svg", "pdf"]:
            output = io.BytesIO()
            fig.savefig(output, format=fmt, dpi=dpi, bbox_inches="tight")
            assert len(output.getvalue()) > 500
    artist.remove()
    assert not fig.artists
    plt.close(fig)


def test_fixed_axis_lifecycle_and_alignment(font_file):
    """固定軸ラベルの設置・除去と位置合わせを確認する。"""
    from matplotlib.ticker import ScalarFormatter

    from tategaki import VerticalTickHandle, set_xticklabels

    fig, ax = plt.subplots()
    ax.plot([1e6, 1e6 + 2], [0, 1])
    fig.canvas.draw()
    locator, formatter = ax.xaxis.get_major_locator(), ax.xaxis.get_major_formatter()
    assert isinstance(formatter, ScalarFormatter)
    limits = ax.get_xlim()
    params = ax.xaxis.get_tick_params()
    callback_count = repr(fig.canvas.callbacks.callbacks)
    positions = [1e6, 1e6 + 2]
    handle = set_xticklabels(
        ax, positions, ["東京", "東京"], engine="opentype", font=font_file, fontsize=15, pad=8
    )
    assert isinstance(handle, VerticalTickHandle)
    count = len(ax.get_children())
    for dpi, invert in [(100, False), (200, True)]:
        fig.set_dpi(dpi)
        if invert:
            ax.invert_xaxis()
        fig.canvas.draw()
        assert not ax.xaxis.offsetText.get_text()
        assert all(not t.get_text() for t in ax.get_xticklabels())
        for p, a in zip(positions, handle.artists, strict=True):
            anchor = a.get_transform().transform(a.get_position())
            assert anchor[0] == pytest.approx(ax.transData.transform((p, 0))[0])
            assert anchor[1] == pytest.approx(ax.bbox.y0 - 8 * dpi / 72)
            assert ax.get_tightbbox().y0 <= a.get_window_extent().y0
        assert len(ax.get_children()) == count
    # Caller limit changes survive removal; a replacement owns the new state.
    changed_limits = ax.get_xlim()
    replacement = set_xticklabels(
        ax, positions, ["AB", "きゃっ"], engine="opentype", font=font_file
    )
    assert all(a.axes is None for a in handle.artists)
    handle.remove()  # Old handle must not remove the replacement.
    assert len(ax.get_children()) == count
    with pytest.raises(MissingGlyphError):
        set_xticklabels(ax, [0], ["無"], engine="opentype", font=font_file)
    assert ax._tategaki_handle is replacement
    replacement.remove()
    replacement.remove()
    assert ax.xaxis.get_major_locator() is locator
    assert ax.xaxis.get_major_formatter() is formatter
    assert ax.xaxis.get_tick_params() == params
    assert ax.get_xlim() == changed_limits
    assert repr(fig.canvas.callbacks.callbacks) == callback_count
    fig.canvas.draw()
    assert ax.xaxis.offsetText.get_text()
    # set_xticks may expand limits, and remove restores that expansion.
    ax.set_xlim(*limits)
    handle = set_xticklabels(ax, [0], ["A"], engine="opentype", font=font_file)
    handle.remove()
    assert ax.get_xlim() == limits
    assert not ax.artists
    plt.close(fig)


def test_fixed_axis_rejects_shared_and_switches_engine(font_file):
    """共有軸の拒否と描画方式の切り替えを確認する。"""
    from tategaki import set_xticklabels

    fig, axes = plt.subplots(2, sharex=True)
    with pytest.raises(ValueError, match="shared"):
        set_xticklabels(axes[0], [0], ["A"], engine="opentype", font=font_file)
    plt.close(fig)

    fig, ax = plt.subplots(subplot_kw={"projection": "polar"})
    with pytest.raises(ValueError, match="rectilinear"):
        set_xticklabels(ax, [0], ["A"], engine="opentype", font=font_file)
    plt.close(fig)
    fig, ax = plt.subplots()
    empty = set_xticklabels(ax, [], [], engine="opentype", font=font_file)
    assert empty.artists == ()
    empty.remove()
    old = set_xticklabels(ax, [0], ["A"], engine="opentype", font=font_file)
    set_xticklabels(ax, [0], ["AB"])
    old.remove()
    assert not ax.artists
    assert ax.get_xticklabels()[0].get_text() == "A\nB"
    plt.close(fig)


def test_mixed_horizontal_shaping_and_clockwise_outline(font_file):
    """混在モードでの横組み整形と時計回りの輪郭回転を確認する。"""
    font = VerticalFont(font_file)
    shaped = font.shape("AB", "mixed")
    assert len(shaped.runs) == 1
    assert shaped.runs[0].text == "AB" and shaped.runs[0].direction == "ltr"
    assert shaped.advance == 1100  # 600 + 600 - kerning 100, rather than 2 em
    assert [g.rotation for g in shaped.glyphs] == [90, 90]
    assert [g.cluster for g in shaped.glyphs] == [0, 1]
    assert [(g.x, g.y) for g in shaped.glyphs] == [(-300, 0), (-300, -500)]
    layout = make_layout(font, "AB", "mixed")
    np.testing.assert_allclose(layout.path.vertices[:2], [(-300, -50), (-300, -550)])
    assert layout.logical_bounds == (-500, -1100, 500, 0)
    ligature = font.shape("fi", "mixed")
    assert len(ligature.glyphs) == 1 and ligature.advance == 600
    assert font.glyph_order[ligature.glyphs[0].glyph_id] == "fi.liga"
    assert len(font.shape("fi").glyphs) == 2  # upright still shapes per grapheme
    marked = font.shape("A\u0301B", "mixed")
    assert marked.graphemes == ((0, 2), (2, 3))
    assert marked.glyphs[-1].cluster == 2
    assert all(g.cluster != 1 and g.rotation == 90 for g in marked.glyphs)
    assert all(g.rotation == 0 for g in font.shape("ＣA\u20dd", "mixed").glyphs)
    assert make_layout(font, " ", "mixed").logical_bounds == (-500, -600, 500, 0)
    assert make_layout(font, "", "mixed").bounds == (0, 0, 0, 0)


def test_mixed_vertical_alternates_and_fallback(font_file):
    """混在モードでの縦書き代替字形と代替不可時の処理を確認する。"""
    font = VerticalFont(font_file)
    for char in "「ー、。」":
        glyph = font.shape(char, "mixed").glyphs[0]
        assert glyph.rotation == 0
        assert font.glyph_order[glyph.glyph_id].endswith(".vert")
    tt = TTFont(font_file)
    for lookup in tt["GSUB"].table.LookupList.Lookup:
        for table in lookup.SubTable:
            if hasattr(table, "mapping"):
                for char in "ー、":
                    table.mapping.pop(f"u{ord(char):04X}", None)
    tt.save(font_file)
    font = VerticalFont(font_file)
    with pytest.warns(VerticalGlyphWarning, match="U\\+30FC"):
        rotated = font.shape("ー", "mixed")
    assert rotated.glyphs[0].rotation == 90 and rotated.advance == 600
    with pytest.warns(VerticalGlyphWarning, match="U\\+3001"):
        upright = font.shape("、", "mixed")
    assert upright.glyphs[0].rotation == 0 and upright.advance == 1000
    for text in ["無", "A\ufe0f", "A\u200dB"]:
        with pytest.raises(MissingGlyphError):
            font.shape(text, "mixed")


def test_mixed_bbox_updates_save_and_axis_lifecycle(font_file):
    """混在モードの範囲更新、保存と軸ラベルの状態遷移を確認する。"""
    from tategaki import set_xticklabels

    fig, ax = plt.subplots(figsize=(5, 5), layout="constrained")
    locator, formatter = ax.xaxis.get_major_locator(), ax.xaxis.get_major_formatter()
    ax.set_xlabel("Category", labelpad=100)
    handle = set_xticklabels(
        ax,
        [0, 1],
        ["AB", "「ケーキ。」"],
        engine="opentype",
        orientation="mixed",
        font=font_file,
        pad=8,
    )
    artist = handle.artists[0]
    initial = artist.get_layout()
    before = artist.get_window_extent().frozen()
    artist.set_orientation("upright")
    assert artist.get_layout() is not initial
    assert artist.get_window_extent().height > before.height
    artist.set_orientation("mixed")
    np.testing.assert_allclose(artist.get_window_extent().extents, before.extents)
    with pytest.raises(ValueError):
        artist.set_orientation("sideways")
    assert artist.get_layout().shaped.advance == 1100
    with pytest.raises(MissingGlyphError):
        set_xticklabels(ax, [0], ["無"], engine="opentype", orientation="mixed", font=font_file)
    assert ax._tategaki_handle is handle
    with pytest.raises(ValueError):
        set_xticklabels(ax, [0], ["A"], orientation="mixed")
    assert ax._tategaki_handle is handle
    for size, dpi in [((5, 5), 100), ((6, 6), 200)]:
        fig.set_size_inches(*size)
        fig.set_dpi(dpi)
        ax.invert_xaxis()
        for fmt in ["png", "svg", "pdf"]:
            output = io.BytesIO()
            fig.savefig(output, format=fmt, dpi=dpi, bbox_inches="tight")
            assert len(output.getvalue()) > 500
        assert len(ax.artists) == 2
        for a in handle.artists:
            bbox = a.get_window_extent()
            assert ax.get_tightbbox().y0 <= bbox.y0
            assert not bbox.overlaps(ax.xaxis.label.get_window_extent())
    replacement = set_xticklabels(ax, [0], ["AB"], engine="opentype", font=font_file)
    assert artist.axes is None
    handle.remove()
    replacement.remove()
    assert ax.xaxis.get_major_locator() is locator
    assert ax.xaxis.get_major_formatter() is formatter
    assert not ax.artists
    empty = set_xticklabels(ax, [], [], engine="opentype", orientation="mixed", font=font_file)
    empty.remove()
    plt.close(fig)
