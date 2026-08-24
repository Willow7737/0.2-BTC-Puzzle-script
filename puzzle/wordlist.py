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
