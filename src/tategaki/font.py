# Copyright (c) 2026 magichan (https://github.com/magichan-lab)

"""Matplotlib のフォント設定から縦書き用のファイルを選ぶ。"""

from matplotlib.font_manager import FontProperties, findfont


def resolve_font(font):
    """明示したパス、または現在の rcParams に一致するフォントパスを返す。"""
    if font is not None:
        return font
    return findfont(FontProperties(), fallback_to_default=False)
