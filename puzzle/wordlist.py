"""BIP-39 English wordlist: loading, integrity checking, and validation.

The wordlist is vendored at ``data/english.txt`` and verified against the
SHA-256 published with BIP-0039, so a corrupted or substituted list cannot
silently poison a multi-day search.
"""

from __future__ import annotations

import hashlib
from difflib import get_close_matches
from pathlib import Path
from typing import Iterable, Sequence

#: SHA-256 of the canonical BIP-0039 English wordlist.
WORDLIST_SHA256 = "2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda"

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "english.txt"


class WordlistError(RuntimeError):
    """Raised when the wordlist is missing, corrupt, or the wrong length."""


def load_wordlist(path: str | Path | None = None, verify: bool = True) -> list[str]:
    """Read the BIP-39 English wordlist and return its 2048 words in order."""
    p = Path(path) if path is not None else _DEFAULT_PATH
    try:
        raw = p.read_bytes()
    except OSError as exc:  # pragma: no cover - depends on the filesystem
        raise WordlistError(f"cannot read wordlist at {p}: {exc}") from exc

    if verify:
        digest = hashlib.sha256(raw).hexdigest()
        if digest != WORDLIST_SHA256:
            raise WordlistError(
                f"wordlist at {p} failed integrity check\n"
                f"  expected sha256 {WORDLIST_SHA256}\n"
                f"  got      sha256 {digest}"
            )

    words = raw.decode("utf-8").split()
    if len(words) != 2048:
        raise WordlistError(f"expected 2048 words, found {len(words)} in {p}")
    return words


WORDS: list[str] = load_wordlist()
INDEX: dict[str, int] = {w: i for i, w in enumerate(WORDS)}


def is_valid(word: str) -> bool:
    """True if *word* is in the BIP-39 English wordlist."""
    return word in INDEX


def normalise(word: str) -> str:
    """Lowercase and strip a user-supplied word."""
    return word.strip().lower()


def suggest(word: str, limit: int = 6) -> list[str]:
    """Plausible BIP-39 replacements for a word that is not in the list.

    BIP-39 words are uniquely determined by their first four letters, so
    prefix matches are ranked ahead of generic edit-distance matches.
    """
    word = normalise(word)
    if not word:
        return []
    ranked: list[str] = []
    for n in (4, 3):
        if len(word) >= n:
            ranked.extend(w for w in WORDS if w.startswith(word[:n]) and w not in ranked)
        if ranked:
            break
    for w in get_close_matches(word, WORDS, n=limit, cutoff=0.6):
        if w not in ranked:
            ranked.append(w)
    return ranked[:limit]


def parse_words(text: str) -> list[str]:
    """Parse a candidate-word file: commas, whitespace and newlines all split.

    ``#`` starts a comment. Order is preserved and duplicates are removed,
    because a duplicated word silently shrinks the real search space.
    """
    cleaned: list[str] = []
    for line in text.splitlines():
        line = line.split("#", 1)[0]
        for chunk in line.replace(",", " ").split():
            w = normalise(chunk)
            if w and w not in cleaned:
                cleaned.append(w)
    return cleaned


def validate(words: Sequence[str]) -> tuple[list[str], list[str]]:
    """Split *words* into ``(valid, invalid)`` against the BIP-39 list."""
    valid = [w for w in words if is_valid(w)]
    invalid = [w for w in words if not is_valid(w)]
    return valid, invalid


def to_indices(words: Iterable[str]) -> list[int]:
    """Map words to their BIP-39 indices, raising on an unknown word."""
    out = []
    for w in words:
        try:
            out.append(INDEX[w])
        except KeyError:
            raise WordlistError(f"{w!r} is not a BIP-39 word") from None
    return out


#: **The wordlist question, settled: it is BIP-39, and ``breathe`` is not a
#: seed word.**
#:
#: A solver in the archived thread noted that ``breathe`` is absent from BIP-39
#: but present in **Electrum's v1 wordlist** - 1626 words, a different scheme
#: from the Electrum seeds ``puzzle.electrum`` already implements, and one that
#: produces exactly the kind of legacy ``1...`` address this puzzle targets.
#: That is a real possibility and it was tested rather than dismissed.
#:
#: The test: a correct wordlist must contain **every word the artwork
#: deliberately marks or hides**. Those are ``subject``, ``tower``, ``moon``
#: (confirmed pairs), ``food`` and ``real`` (marked, no number), and ``first``,
#: ``future`` and ``this`` (hidden low-contrast text).
#:
#: ==============  =========
#: wordlist        covers
#: ==============  =========
#: BIP-39          **8 of 8**
#: Electrum v1     6 of 8 - missing ``food`` and ``this``
#: ==============  =========
#:
#: **The decisive pair is ``breathe`` and ``food``.** ``breathe`` is in
#: Electrum v1 and not BIP-39; ``food`` is in BIP-39 and not Electrum v1. **No
#: wordlist contains both**, so at most one of them can be a seed word - and
#: the artwork settles which. ``food`` is *deliberately written down the Space
#: Needle's shaft*. ``breathe`` is plain visible text on a hoodie, which
#: section 1 of ANALYSIS.md established years of searching had over-read.
#:
#: The marked one wins. So the scheme is BIP-39, and the ``breathe`` anomaly
#: that has run through this analysis since section 1 is resolved: it is not a
#: seed word, and it never was.
#:
#: This is the wall the community hit and could not get past. u/hmm_dimasiki:
#: *"if we take as a basis that the whole seed phrase should be composed of the
#: same set of words, then how to explain that the word 'food' is not in this
#: set."* The answer is that ``breathe`` is the one to drop, not ``food``.
WORDLIST_IS_BIP39 = {
    "candidates": ("BIP-39", "Electrum v1"),
    "electrum_v1_size": 1626,
    "must_contain": ("subject", "tower", "moon", "food", "real",
                     "first", "future", "this"),
    "bip39_covers": 8,
    "electrum_v1_covers": 6,
    "electrum_v1_missing": ("food", "this"),
    "decisive_pair": {"breathe": "Electrum v1 only", "food": "BIP-39 only"},
    "no_list_contains_both": True,
    "which_is_marked": "food - written down the Space Needle's shaft; "
                       "breathe is plain visible text on a hoodie",
    "verdict": "BIP-39; breathe is not a seed word",
    "resolves": "the anomaly running through this analysis since section 1",
}
