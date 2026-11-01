# Copyright (c) 2026 magichan (https://github.com/magichan-lab)

"""書記素を保った縦積みと、日本語 OpenType による縦組みを提供する。"""

from .stacking import stack_label
from .ticks import VerticalTickHandle, set_xticklabels
from .wrapping import disable, enable

__all__ = [
    "stack_label",
    "set_xticklabels",
    "VerticalText",
    "VerticalTickHandle",
    "enable",
    "disable",
]


def __getattr__(name):
    """必要になったときに ``VerticalText`` を読み込む。"""
    if name == "VerticalText":
        from .artist import VerticalText

        return VerticalText
    raise AttributeError(name)
