"""On-screen keyboard. Emits on_key(str): a character, " " for space, "\\b" for backspace.
on_enter() on ENTER, on_close() on the CLOSE key. Keys are >= 36 px tall; with the
suggested 194 px height they are ~48 px."""
import pygame

from ui import text_cache, theme

_ALPHA = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
_SYMS = ["1234567890", "-/:;()&@\"", ".,?!'#%+"]


class Keyboard:
    def __init__(self, rect, on_key=None, on_enter=None, on_close=None):
        self.rect = pygame.Rect(rect)
        self.on_key = on_key
        self.on_enter = on_enter
        self.on_close = on_close
        self.shift = False
        self.symbols = False
        self.dirty = True
        self._pressed = None
        self._layout = []
        self._build()

    def _build(self):
        rows = _SYMS if self.symbols else _ALPHA
        rh = self.rect.h / 4.0
        out = []
        gap = 2
        for ri, row in enumerate(rows):
            y = int(self.rect.y + ri * rh)
            n = len(row)
            kw = self.rect.w / float(n + 3 if ri == 2 else n)   # row 3: shift + bksp are 1.5 keys each
            x = self.rect.x
            if ri == 2:
                out.append(("SHIFT", pygame.Rect(int(x), y, int(kw * 1.5), int(rh))))
                x += kw * 1.5
            elif ri == 1:
                x += (self.rect.w - kw * n) / 2.0
            for ch in row:
                out.append((ch, pygame.Rect(int(x), y, int(kw), int(rh))))
                x += kw
            if ri == 2:
                out.append(("BKSP", pygame.Rect(int(x), y, int(self.rect.right - x), int(rh))))
        y = int(self.rect.y + 3 * rh)
        w = self.rect.w
        h = int(self.rect.bottom - y)
        out.append(("CLOSE", pygame.Rect(self.rect.x, y, int(w * .16), h)))
        out.append(("MODE", pygame.Rect(self.rect.x + int(w * .16), y, int(w * .16), h)))
        out.append((" ", pygame.Rect(self.rect.x + int(w * .32), y, int(w * .44), h)))
        out.append(("ENTER", pygame.Rect(self.rect.x + int(w * .76), y, self.rect.w - int(w * .76), h)))
        self._layout = [(lab, r.inflate(-gap, -gap)) for lab, r in out]

    def key_rects(self):
        return list(self._layout)

    def _key_at(self, pos):
        for lab, r in self._layout:
            if r.collidepoint(pos):
                return lab
        return None

    def _fire(self, lab):
        if lab == "SHIFT":
            self.shift = not self.shift
        elif lab == "MODE":
            self.symbols = not self.symbols
            self._build()
        elif lab == "BKSP":
            if self.on_key:
                self.on_key("\b")
        elif lab == "ENTER":
            if self.on_enter:
                self.on_enter()
        elif lab == "CLOSE":
            if self.on_close:
                self.on_close()
        else:
            ch = lab.upper() if (self.shift and lab.isalpha()) else lab
            if self.shift:
                self.shift = False
            if self.on_key:
                self.on_key(ch)

    def handle_touch(self, pos, kind):
        if kind == "down":
            if not self.rect.collidepoint(pos):
                return False
            self._pressed = self._key_at(pos)
            self.dirty = True
            return True
        if self._pressed is None:
            return False
        if kind == "move":
            if self._key_at(pos) != self._pressed:
                self._pressed = None
                self.dirty = True
            return True
        if kind == "up":
            lab = self._pressed
            self._pressed = None
            self.dirty = True
            if lab is not None and self._key_at(pos) == lab:
                self._fire(lab)
            return True
        if kind == "cancel":
            self._pressed = None
            self.dirty = True
            return True
        return False

    def draw(self, surface):
        pygame.draw.rect(surface, theme.BG_DARK, self.rect)
        for lab, r in self._layout:
            on = (lab == self._pressed) or (lab == "SHIFT" and self.shift)
            col = theme.PRIMARY if on else (theme.PRIMARY_DARK if lab == "ENTER" else theme.BG_LIGHT)
            pygame.draw.rect(surface, col, r, border_radius=6)
            txt = {"SHIFT": "Shift", "BKSP": "Del", "ENTER": "Go", "CLOSE": "Hide",
                   "MODE": "abc" if self.symbols else "123", " ": "space"}.get(lab, lab)
            if self.shift and lab.isalpha() and len(lab) == 1:
                txt = lab.upper()
            img = text_cache.render(txt, theme.FS_BODY, theme.TEXT)
            surface.blit(img, img.get_rect(center=r.center))
        self.dirty = False
