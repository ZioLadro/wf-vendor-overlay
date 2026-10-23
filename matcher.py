"""Fuzzy match dei nomi letti dall'OCR con il catalogo di warframe.market (con memo)."""
import re
from collections import namedtuple

from rapidfuzz import fuzz, process

Match = namedtuple("Match", "slug name score")


def norm(s: str) -> str:
    s = s.lower().replace("&", "and")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


class Matcher:
    def __init__(self, pairs):
        self.pairs = [(p[0], p[1]) for p in pairs]      # [(nome, slug)]
        self._norms = [norm(n) for n, _ in self.pairs]
        self._memo = {}

    def match(self, text: str, threshold: int = 90):
        n = norm(text)
        if len(n) < 4:
            return None
        key = (n, threshold)
        if key in self._memo:
            return self._memo[key]
        res = process.extractOne(n, self._norms, scorer=fuzz.ratio, score_cutoff=threshold)
        m = None
        if res:
            _, score, idx = res
            name, slug = self.pairs[idx]
            m = Match(slug, name, score)
        if len(self._memo) > 5000:
            self._memo.clear()
        self._memo[key] = m
        return m
