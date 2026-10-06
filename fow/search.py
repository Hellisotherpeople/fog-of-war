"""Shared, accent-insensitive text filtering for menus and readable records."""
import unicodedata

import tcod.event as E


def normalized(text):
    return "".join(c for c in unicodedata.normalize("NFKD", str(text)).casefold()
                   if not unicodedata.combining(c))


class Search:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.query = ""
        self.typing = False

    def matches(self, text):
        haystack = normalized(text)
        return all(word in haystack for word in normalized(self.query).split())

    def key(self, key):
        """changed/handled/accept, or None for normal navigation and actions."""
        if not self.enabled:
            return None
        if key.sym == E.KeySym.ESCAPE and (self.typing or self.query):
            self.query, self.typing = "", False
            return "changed"
        if key.char == "/" and not self.typing:
            self.typing = True
            return "handled"
        if not self.typing:
            return None
        if key.sym in (E.KeySym.RETURN, E.KeySym.KP_ENTER):
            self.typing = False
            return "accept"
        if key.sym == E.KeySym.BACKSPACE:
            self.query = self.query[:-1]
            return "changed"
        if key.sym == E.KeySym.DELETE:
            self.query = ""
            return "changed"
        char = " " if key.sym == E.KeySym.SPACE else key.char
        if char and char.isprintable():
            self.query = (self.query + char)[:80]
            return "changed"
        if key.sym in (E.KeySym.UP, E.KeySym.DOWN, E.KeySym.KP_8, E.KeySym.KP_2,
                       E.KeySym.PAGEUP, E.KeySym.PAGEDOWN):
            return None
        return "handled"

    def prompt(self):
        if self.typing or self.query:
            return f"/ {self.query[-38:]}{'_' if self.typing else ''}  Enter select; Esc clear"
        return "/ search"


def advance(indices, selected, step):
    if not indices:
        return selected
    return indices[(indices.index(selected) + step) % len(indices)] if selected in indices else indices[0]


def typing_in(state):
    """The event loop normally reserves digits; let text fields receive them."""
    if getattr(getattr(state, "search", None), "typing", False) or getattr(state, "typing", False):
        return True
    popups = getattr(state, "popups", getattr(getattr(state, "play", None), "popups", ()))
    menu = getattr(getattr(state, "inv_screen", None), "menu", None)
    return bool(popups and popups[-1].search.typing or menu and menu.search.typing)
