# Copyright (c) 2026 magichan (https://github.com/magichan-lab)

"""matplotlib-tategaki による縦書きラベル付き棒グラフのサンプル。

実行: python sample.py --font /path/to/JapaneseFont.ttf
保存: python sample.py --font /path/to/JapaneseFont.ttf --output sample.png
必要なライブラリ: python -m pip install 'matplotlib-tategaki[opentype]'
"""

import argparse
import os
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

from tategaki import set_xticklabels, stack_label


def main():
    """縦書きラベル付きの棒グラフを作成し、表示または保存する。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, help="縦組みに対応する単独の静的 TTF/OTF")
    parser.add_argument("--output", type=Path, help="画面表示の代わりに画像を保存するパス")
    args = parser.parse_args()

    # Windows / WSL では游明朝を探す。他の環境では --font で指定する。
    font = args.font
    if font is None:
        candidates = [
            Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/yumin.ttf",
            Path("/mnt/c/Windows/Fonts/yumin.ttf"),
        ]
        font = next((path for path in candidates if path.is_file()), None)
    if font is None or not font.is_file():
        parser.error("--font で日本語の縦組みに対応する TTF/OTF ファイルを指定してください。")

    fig, ax = plt.subplots(figsize=(7, 6))
    try:
        positions = [0, 1, 2, 3]
        ax.bar(positions, [10, 24, 36, 18], color="#548ca8")
        set_xticklabels(
            ax,
            positions,
            ["「ケーキ」", "コーヒー", "東京ABC", "きゃらめる"],
            engine="opentype",
            orientation="mixed",
            font=font,
            fontsize=16,
            pad=8,
        )
        fontproperties = FontProperties(fname=font)
        ax.set_title("商品別の売上", fontproperties=fontproperties)
        ax.set_ylabel(
            stack_label("売上数"),
            fontproperties=fontproperties,
            rotation=0,
            ha="center",
            va="center",
            linespacing=1.0,
            labelpad=20,
        )
        # 独自の縦書きラベルに合わせ、軸タイトルと図の下余白を確保する。
        ax.set_xlabel("商品", fontproperties=fontproperties, labelpad=115)
        fig.subplots_adjust(bottom=0.42)
        ax.set_axisbelow(True)
        ax.grid(axis="y", alpha=0.25)

        if args.output:
            fig.savefig(args.output, dpi=150, bbox_inches="tight")
            print(f"保存しました: {args.output}")
        else:
            plt.show()
    finally:
        plt.close(fig)


if __name__ == "__main__":
    main()
