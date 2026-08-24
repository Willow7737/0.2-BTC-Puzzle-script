"""The parallel search engine.

Design notes:

* Work is split into *units*. A unit is one word subset plus a fixed ordering
  of the first few free positions. Units are enumerated deterministically, so
  a run can be checkpointed and resumed by unit index.
* The inner loop applies the BIP-39 checksum filter before touching PBKDF2.
  That rejects 15 of every 16 orderings for the cost of one SHA-256.
* Comparison happens on 20-byte hash160 values, not Base58 strings, which
  keeps a big-integer encode out of the hot path.
"""

from __future__ import annotations

import itertools
import json
import multiprocessing as mp
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Sequence

from . import brainwallet
from .bip39 import checksum_ok_12, checksum_ok, mnemonic_to_seed
from .derive import Scheme, iter_hash160s
from .wordlist import INDEX


@dataclass
class SearchConfig:
    """Everything needed to define and reproduce a search."""

    pool: list[str]
    target_hash160: bytes
    phrase_len: int = 12
    mode: str = "bip39"                      # "bip39" | "brain"
    schemes: tuple[Scheme, ...] = ()
    passphrase: str = ""
    pinned: dict[int, str] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)
    joiners: tuple[str, ...] = ("space",)
    casings: tuple[str, ...] = ("lower",)
    workers: int = 1
    prefix_len: int = 1
    limit: int | None = None
    unit_limit: int | None = None      # max orderings per unit (derived from limit)
    deadline: float | None = None      # absolute time.time() cutoff

    def free_positions(self) -> list[int]:
        return [i for i in range(self.phrase_len) if i not in self.pinned]

    def free_pool(self) -> list[str]:
        used = set(self.pinned.values())
        return [w for w in self.pool if w not in used]


@dataclass
class Hit:
    """A candidate whose derived address matches the target."""

    phrase: str
    scheme: str
    index: int
    detail: str = ""

    def to_dict(self) -> dict:
        return {"phrase": self.phrase, "scheme": self.scheme, "index": self.index,
                "detail": self.detail}


@dataclass
class Progress:
    """Counters reported back from the workers."""

    tested: int = 0
    checksum_valid: int = 0
    units_done: int = 0


# --- unit enumeration -------------------------------------------------------

def iter_units(cfg: SearchConfig) -> Iterator[tuple[tuple[str, ...], tuple[str, ...]]]:
    """Yield ``(subset, prefix)`` work units in a deterministic order."""
    free_slots = len(cfg.free_positions())
    pool = cfg.free_pool()
    required = [w for w in cfg.required if w not in cfg.pinned.values()]
    prefix_len = max(0, min(cfg.prefix_len, free_slots))

    for subset in itertools.combinations(pool, free_slots):
        if required and not set(required).issubset(subset):
            continue
        if prefix_len == 0:
            yield subset, ()
        else:
            for prefix in itertools.permutations(subset, prefix_len):
                yield subset, prefix


def count_units(cfg: SearchConfig) -> int:
    """How many work units the configuration produces."""
    return sum(1 for _ in iter_units(cfg))


# --- the hot loop -----------------------------------------------------------

_WORKER_CFG: SearchConfig | None = None


def _init_worker(cfg: SearchConfig) -> None:
    global _WORKER_CFG
    _WORKER_CFG = cfg


def _positional(order: Sequence[str], cfg: SearchConfig) -> list[str]:
    """Place *order* into the free positions around any pinned words."""
    if not cfg.pinned:
        return list(order)
    out = [""] * cfg.phrase_len
    for pos, word in cfg.pinned.items():
        out[pos] = word
    for pos, word in zip(cfg.free_positions(), order):
        out[pos] = word
    return out


def _run_unit_bip39(cfg: SearchConfig, subset, prefix) -> tuple[int, int, list[Hit]]:
    target = cfg.target_hash160
    schemes = cfg.schemes
    passphrase = cfg.passphrase
    plain = not cfg.pinned and cfg.phrase_len == 12
    rest = list(subset)
    for w in prefix:
        rest.remove(w)

    tested = valid = 0
    hits: list[Hit] = []
    idx = INDEX
    check = checksum_ok_12 if cfg.phrase_len == 12 else checksum_ok
    unit_limit = cfg.unit_limit
    deadline = cfg.deadline

    for tail in itertools.permutations(rest, len(rest)):
        order = prefix + tail
        tested += 1
        # Bounds are checked every 1024 orderings: frequent enough that a small
        # --limit still bites, cheap enough to vanish next to the checksum work.
        if not tested & 0x3FF:
            if unit_limit and tested >= unit_limit:
                break
            if deadline and time.time() >= deadline:
                break
        placed = order if plain else tuple(_positional(order, cfg))
        indices = [idx[w] for w in placed]
        if not check(indices):
            continue
        valid += 1
        phrase = " ".join(placed)
        seed = mnemonic_to_seed(phrase, passphrase)
        for h160, scheme_name, address_index in iter_hash160s(seed, schemes):
            if h160 == target:
                hits.append(Hit(phrase, scheme_name, address_index,
                                f"passphrase={passphrase!r}"))
        if hits:
            break  # answer found; the rest of this unit is wasted work
    return tested, valid, hits


def _run_unit_brain(cfg: SearchConfig, subset, prefix) -> tuple[int, int, list[Hit]]:
    target = cfg.target_hash160
    rest = list(subset)
    for w in prefix:
        rest.remove(w)

    tested = 0
    hits: list[Hit] = []
    unit_limit = cfg.unit_limit
    deadline = cfg.deadline
    for tail in itertools.permutations(rest, len(rest)):
        order = prefix + tail
        placed = order if not cfg.pinned else tuple(_positional(order, cfg))
        tested += 1
        if not tested & 0x3FF:
            if unit_limit and tested >= unit_limit:
                break
            if deadline and time.time() >= deadline:
                break
        for phrase in brainwallet.variants(placed, cfg.joiners, cfg.casings):
            for h160, label in brainwallet.iter_hash160s(phrase):
                if h160 == target:
                    hits.append(Hit(phrase, f"brainwallet-{label}", 0))
        if hits:
            break  # answer found; the rest of this unit is wasted work
    return tested, tested, hits


def _run_unit(args) -> tuple[int, int, int, list[dict]]:
    """Worker entry point: returns ``(unit_id, tested, valid, hits)``."""
    unit_id, subset, prefix = args
    cfg = _WORKER_CFG
    assert cfg is not None
    runner = _run_unit_brain if cfg.mode == "brain" else _run_unit_bip39
    tested, valid, hits = runner(cfg, subset, prefix)
    return unit_id, tested, valid, [h.to_dict() for h in hits]


# --- checkpointing ----------------------------------------------------------

class Checkpoint:
    """Records completed unit ids so an interrupted run can resume."""

    def __init__(self, path: Path | None):
        self.path = Path(path) if path else None
        self.done: set[int] = set()
        self.meta: dict = {}
        if self.path and self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                self.done = set(data.get("done", []))
                self.meta = data.get("meta", {})
            except (json.JSONDecodeError, OSError):
                self.done = set()

    def save(self, meta: dict | None = None) -> None:
        if not self.path:
            return
        if meta:
            self.meta.update(meta)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps({"done": sorted(self.done), "meta": self.meta}))
        tmp.replace(self.path)


# --- driver -----------------------------------------------------------------

def run_search(cfg: SearchConfig, checkpoint: Checkpoint | None = None,
               on_progress=None, deadline: float | None = None) -> tuple[list[Hit], Progress]:
    """Execute the search, returning any hits and the final counters."""
    units = list(iter_units(cfg))
    checkpoint = checkpoint or Checkpoint(None)
    pending = [(i, s, p) for i, (s, p) in enumerate(units) if i not in checkpoint.done]

    progress = Progress(units_done=len(checkpoint.done))
    hits: list[Hit] = []
    total_units = len(units)
    started = time.time()
    last_report = started

    if not pending:
        return hits, progress

    workers = max(1, min(cfg.workers, len(pending)))
    # Workers inherit cfg by fork, so the per-unit bounds must be set first:
    # a unit can span billions of orderings and would otherwise ignore both
    # --limit and --max-seconds until it finished.
    if cfg.limit and cfg.unit_limit is None:
        cfg.unit_limit = max(1, cfg.limit // workers)
    if deadline is not None:
        cfg.deadline = deadline
    ctx = mp.get_context("fork" if hasattr(os, "fork") else "spawn")
    with ctx.Pool(workers, initializer=_init_worker, initargs=(cfg,)) as pool:
        try:
            for unit_id, tested, valid, raw_hits in pool.imap_unordered(
                _run_unit, pending, chunksize=1
            ):
                progress.tested += tested
                progress.checksum_valid += valid
                progress.units_done += 1
                checkpoint.done.add(unit_id)
                for h in raw_hits:
                    hits.append(Hit(**h))

                now = time.time()
                if hits:
                    checkpoint.save({"hits": [h.to_dict() for h in hits]})
                    pool.terminate()
                    break
                if now - last_report >= 5.0:
                    last_report = now
                    checkpoint.save({"tested": progress.tested})
                    if on_progress:
                        on_progress(progress, total_units, now - started)
                if cfg.limit and progress.tested >= cfg.limit:
                    pool.terminate()
                    break
                if deadline and now >= deadline:
                    pool.terminate()
                    break
        except KeyboardInterrupt:
            pool.terminate()
            checkpoint.save({"tested": progress.tested})
            raise

    checkpoint.save({"tested": progress.tested})
    return hits, progress
