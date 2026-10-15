"""Font + rendered-text cache. No per-frame font or surface creation."""
import os
from collections import OrderedDict

import pygame

_FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "assets", "fonts")
_FONT_CANDIDATES = ("DejaVuSans.ttf", "FreeSansBold.ttf")

_fonts = {}
_text = OrderedDict()
TEXT_CACHE_MAX = 256


def _font_path():
    for name in _FONT_CANDIDATES:
        p = os.path.join(_FONT_DIR, name)
        if os.path.isfile(p):
            return p
    return None


def clean_text(text):
    """Make text safe for pygame: replace lone surrogates, drop NULs/control chars."""
    if not isinstance(text, str):
        text = str(text)
    text = text.encode("utf-8", "replace").decode("utf-8")
    if text.isprintable():
        return text
    return "".join(" " if c in "\t\n\r" else c for c in text if c.isprintable() or c in "\t\n\r")


def get_font(size, bold=False):
    """Cached pygame Font of `size` px. `bold` uses synthetic bold."""
    key = (size, bool(bold))
    f = _fonts.get(key)
    if f is None:
        if not pygame.font.get_init():
            pygame.font.init()
        path = _font_path()
        f = pygame.font.Font(path, size)  # path None -> pygame default
        if bold:
            f.set_bold(True)
        _fonts[key] = f
    return f


def render(text, size, color, bold=False):
    """Cached rendered text Surface; same args return the same Surface object."""
    text = clean_text(text)
    key = (text, size, tuple(color), bool(bold))
    s = _text.get(key)
    if s is not None:
        _text.move_to_end(key)
        return s
    s = get_font(size, bold).render(text, True, color)
    _text[key] = s
    if len(_text) > TEXT_CACHE_MAX:
        _text.popitem(last=False)
    return s


def text_width(text, size, bold=False):
    return get_font(size, bold).size(clean_text(text))[0]


_ell = {}


def ellipsize(text, size, max_w, bold=False):
    """Return `text` truncated with an ellipsis so it fits in max_w pixels."""
    text = clean_text(text)
    if max_w <= 0:
        return ""
    key = (text, size, max_w, bool(bold))
    hit = _ell.get(key)
    if hit is not None:
        return hit
    font = get_font(size, bold)
    if font.size(text)[0] <= max_w:
        out = text
    else:
        ell = "..."
        if font.size(ell)[0] > max_w:
            out = ""
        else:
            lo, hi = 0, len(text)
            while lo < hi:  # largest n with prefix+ell fitting
                mid = (lo + hi + 1) // 2
                if font.size(text[:mid].rstrip() + ell)[0] <= max_w:
                    lo = mid
                else:
                    hi = mid - 1
            out = text[:lo].rstrip() + ell
    if len(_ell) > 2048:
        _ell.clear()
    _ell[key] = out
    return out
