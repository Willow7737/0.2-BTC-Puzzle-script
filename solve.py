#!/usr/bin/env python3
"""Command-line front end for the 0.2 BTC puzzle toolkit.

    ./solve.py validate  seedwords.txt      # are these real BIP-39 words?
    ./solve.py estimate  --tiers AB         # how long would that take?
    ./solve.py check     "twelve words ..." # test one specific phrase
    ./solve.py bench                        # measure this machine
    ./solve.py search    --tiers A --extra brave,world,order,only,find
    ./solve.py selftest                     # prove the crypto is correct
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from puzzle import brainwallet, candidates, feasibility
from puzzle.bip39 import checksum_ok_12, is_valid_mnemonic, mnemonic_to_seed
from puzzle.derive import DEFAULT_SCHEMES, SCHEMES, iter_hash160s, resolve_schemes
from puzzle.keys import (
    EC_BACKEND,
    RIPEMD160_BACKEND,
    address_from_hash160,
    hash160_from_address,
)
from puzzle.search import Checkpoint, SearchConfig, count_units, run_search
from puzzle.wordlist import INDEX, WORDS, parse_words, suggest, validate

TARGET_ADDRESS = "1KfZGvwZxsvSmemoCmEV75uqcNzYBHjkHZ"


# --- helpers ----------------------------------------------------------------

def _resolve_pool(args) -> list[str]:
    """Assemble the candidate pool from tiers, a file, and --extra."""
    pool: list[str] = []
    if getattr(args, "tiers", None):
        pool.extend(candidates.build_pool(args.tiers))
    if getattr(args, "words", None):
        path = Path(args.words)
        if not path.exists():
            sys.exit(f"error: word file not found: {path}")
        for w in parse_words(path.read_text()):
            if w not in pool:
                pool.append(w)
    if getattr(args, "extra", None):
        for w in parse_words(args.extra):
            if w not in pool:
                pool.append(w)
    return pool


def _require_valid(pool: list[str], mode: str) -> list[str]:
    """In BIP-39 mode a non-BIP-39 word makes the whole search pointless."""
    if mode == "brain":
        return pool
    good, bad = validate(pool)
    if bad:
        print("error: these are not BIP-39 words and cannot appear in a mnemonic:\n")
        for w in bad:
            print(f"    {w:<12}  did you mean: {', '.join(suggest(w, 4)) or '(no close match)'}")
        print("\nRemove them, replace them, or use --mode brain (free-form passphrase).")
        sys.exit(2)
    return good


def _parse_pinned(spec: str | None, phrase_len: int) -> dict[int, str]:
    """``--pin 0=moon,11=black`` -> ``{0: 'moon', 11: 'black'}`` (1-based off)."""
    pinned: dict[int, str] = {}
    if not spec:
        return pinned
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            sys.exit(f"error: --pin entry {item!r} must look like POSITION=word")
        pos_s, word = item.split("=", 1)
        try:
            pos = int(pos_s)
        except ValueError:
            sys.exit(f"error: --pin position {pos_s!r} is not a number")
        if not 0 <= pos < phrase_len:
            sys.exit(f"error: --pin position {pos} outside 0..{phrase_len - 1}")
        pinned[pos] = word.strip().lower()
    return pinned


def _target_hash160(address: str) -> bytes:
    try:
        return hash160_from_address(address)
    except ValueError as exc:
        sys.exit(f"error: bad target address {address!r}: {exc}")


# --- commands ---------------------------------------------------------------

def cmd_validate(args) -> int:
    pool = _resolve_pool(args)
    if not pool:
        sys.exit("error: no words given (use --words FILE, --tiers, or --extra)")
    good, bad = validate(pool)
    print(f"{len(pool)} candidate words: {len(good)} valid BIP-39, {len(bad)} invalid\n")
    for w in pool:
        if w in INDEX:
            print(f"  ok       {w:<12} #{INDEX[w]:>4}")
        else:
            print(f"  INVALID  {w:<12} suggest: {', '.join(suggest(w, 5)) or '(none)'}")
    if bad:
        print(f"\n{len(bad)} word(s) cannot appear in a BIP-39 mnemonic.")
        print("A single invalid word makes an entire BIP-39 search futile.")
    return 1 if bad else 0


def cmd_estimate(args) -> int:
    pool = _resolve_pool(args)
    if not pool:
        sys.exit("error: no words given")
    pinned = _parse_pinned(args.pin, args.length)
    est = feasibility.estimate(
        len(pool), args.length, mode=args.mode,
        workers=args.workers, pinned=len(pinned),
        required=len(parse_words(args.require or "")),
    )
    print(feasibility.report(est, len(pool), args.length))
    print("\nHow the pool size drives cost (no pinning, this many workers):")
    print(f"  {'pool':>5}  {'candidates':>22}  {'wall time':>16}")
    for n in range(args.length, args.length + 9):
        e = feasibility.estimate(n, args.length, mode=args.mode, workers=args.workers)
        mark = "  <-- your pool" if n == len(pool) else ""
        print(f"  {n:>5}  {e.total_candidates:>22,}  {feasibility.humanize(e.seconds):>16}{mark}")
    return 0


def cmd_check(args) -> int:
    """Test one phrase against the target across every scheme."""
    phrase = " ".join(parse_words(args.phrase)) if "," in args.phrase else args.phrase.strip()
    words = phrase.split()
    _target_hash160(args.target)  # reject a malformed target before doing work
    print(f"phrase : {phrase}")
    print(f"words  : {len(words)}")
    print(f"target : {args.target}\n")

    found = False
    if len(words) in (12, 15, 18, 21, 24) and all(w in INDEX for w in words):
        valid = is_valid_mnemonic(phrase)
        print(f"BIP-39 checksum: {'VALID' if valid else 'INVALID'}")
        if valid:
            seed = mnemonic_to_seed(phrase, args.passphrase)
            print(f"seed   : {seed.hex()[:32]}...\n")
            print("  BIP-39 / BIP-32 derivations:")
            for h160, scheme, idx in iter_hash160s(seed, list(SCHEMES)):
                addr = address_from_hash160(h160)
                hit = addr == args.target
                found |= hit
                print(f"    {'*** MATCH ***' if hit else '             '} "
                      f"{scheme:<24} /{idx}  {addr}")
    else:
        print("Not a well-formed BIP-39 mnemonic; testing as a passphrase only.\n")

    print("\n  Brainwallet renderings:")
    for rendering in brainwallet.variants(words, ("space", "none", "dash"),
                                          ("lower", "upper", "title", "asis")):
        for h160, label in brainwallet.iter_hash160s(rendering):
            addr = address_from_hash160(h160)
            hit = addr == args.target
            found |= hit
            if hit or args.verbose:
                print(f"    {'*** MATCH ***' if hit else '             '} "
                      f"{label:<14} {addr}  <- {rendering!r}")
    if not args.verbose and not found:
        print("    (no match; use --verbose to list every rendering)")

    print("\nRESULT:", "MATCH FOUND" if found else "no match")
    return 0 if found else 1


def cmd_bench(args) -> int:
    import itertools

    print(f"backends: secp256k1={EC_BACKEND}  ripemd160={RIPEMD160_BACKEND}")
    print(f"cpus    : {os.cpu_count()}\n")

    pool = [INDEX[w] for w in candidates.build_pool("A")[:7] +
            ["world", "order", "only", "find", "brave"]]
    n, t0, valid = 250_000, time.perf_counter(), 0
    for k, p in enumerate(itertools.permutations(pool, 12)):
        if k >= n:
            break
        valid += checksum_ok_12(p)
    filt = n / (time.perf_counter() - t0)
    print(f"checksum filter : {filt:>12,.0f} perms/sec/core (pass rate {valid/n:.4f})")

    phrase = " ".join(WORDS[i] for i in pool)
    schemes = resolve_schemes(list(DEFAULT_SCHEMES))
    n2, t0 = 200, time.perf_counter()
    for _ in range(n2):
        seed = mnemonic_to_seed(phrase)
        for _ in iter_hash160s(seed, schemes):
            pass
    bip = n2 / (time.perf_counter() - t0)
    print(f"bip39 candidate : {bip:>12,.0f} /sec/core (PBKDF2 + {len(schemes)} schemes)")

    n3, t0 = 3000, time.perf_counter()
    for i in range(n3):
        for _ in brainwallet.iter_hash160s(f"{phrase}{i}", (True,)):
            pass
    brain = n3 / (time.perf_counter() - t0)
    print(f"brain candidate : {brain:>12,.0f} /sec/core (SHA-256 + EC + hash160)")

    print("\nPut these in feasibility.py, or pass --rate, for accurate estimates.")
    print(f"  RATE_CHECKSUM_FILTER = {filt:,.0f}")
    print(f"  RATE_BIP39_CANDIDATE = {bip:,.0f}")
    print(f"  RATE_BRAIN_CANDIDATE = {brain:,.0f}")
    return 0


def cmd_selftest(args) -> int:
    import subprocess
    here = Path(__file__).resolve().parent
    return subprocess.call([sys.executable, "-m", "unittest", "discover", "-s",
                            str(here / "tests"), "-t", str(here), "-v"])


def cmd_search(args) -> int:
    pool = _resolve_pool(args)
    if not pool:
        sys.exit("error: no words given (use --tiers, --words FILE, or --extra)")
    pool = _require_valid(pool, args.mode)
    pinned = _parse_pinned(args.pin, args.length)
    required = parse_words(args.require or "")
    target = _target_hash160(args.target)

    for w in list(pinned.values()) + required:
        if w not in pool:
            pool.append(w)

    est = feasibility.estimate(len(pool), args.length, mode=args.mode,
                               workers=args.workers, pinned=len(pinned),
                               required=len(required))
    print(feasibility.report(est, len(pool), args.length))
    print()
    if est.hopeless and not args.force:
        print("Refusing to start a search that cannot finish. Re-run with --force")
        print("if you really want to burn the CPU, or shrink the pool first.")
        return 2

    cfg = SearchConfig(
        pool=pool, target_hash160=target, phrase_len=args.length, mode=args.mode,
        schemes=tuple(resolve_schemes(
            args.schemes.split(",") if args.schemes else list(DEFAULT_SCHEMES),
            depth=args.depth)),
        passphrase=args.passphrase, pinned=pinned, required=required,
        joiners=tuple(args.joiners.split(",")), casings=tuple(args.casings.split(",")),
        workers=args.workers, prefix_len=args.prefix_len, limit=args.limit,
    )

    ckpt = Checkpoint(Path(args.checkpoint) if args.checkpoint else None)
    total_units = count_units(cfg)
    if ckpt.done:
        print(f"resuming: {len(ckpt.done)}/{total_units} work units already done")
    print(f"pool ({len(pool)}): {' '.join(pool)}")
    if pinned:
        print("pinned : " + ", ".join(f"{k}={v}" for k, v in sorted(pinned.items())))
    print(f"target : {args.target}")
    print(f"mode   : {args.mode}   workers: {args.workers}   units: {total_units}")
    if args.max_seconds:
        print(f"time cap: {args.max_seconds}s")
    print("\nsearching (ctrl-c to stop; progress is checkpointed)\n")

    def on_progress(p, total, elapsed):
        rate = p.tested / elapsed if elapsed else 0
        pct = 100.0 * p.units_done / total if total else 0
        remaining = (total - p.units_done) / (p.units_done / elapsed) if p.units_done else 0
        print(f"  {p.tested:>15,} tested  {p.checksum_valid:>12,} checksum-ok  "
              f"{rate:>10,.0f}/s  {pct:5.1f}%  eta {feasibility.humanize(remaining)}")

    deadline = time.time() + args.max_seconds if args.max_seconds else None
    t0 = time.time()
    try:
        hits, progress = run_search(cfg, ckpt, on_progress, deadline)
    except KeyboardInterrupt:
        print("\ninterrupted; progress saved to checkpoint")
        return 130

    elapsed = time.time() - t0
    print(f"\ntested {progress.tested:,} orderings "
          f"({progress.checksum_valid:,} checksum-valid) in {feasibility.humanize(elapsed)}")
    print(f"units completed: {progress.units_done}/{total_units}")
    if progress.units_truncated:
        print(f"units cut short : {progress.units_truncated} "
              f"(not checkpointed; they will be re-searched on resume)")

    if hits:
        print("\n" + "=" * 70)
        for h in hits:
            print(f"MATCH  scheme={h.scheme} index={h.index}")
            print(f"  phrase: {h.phrase}")
        print("=" * 70)
        if args.out:
            Path(args.out).write_text(json.dumps([h.to_dict() for h in hits], indent=2))
            print(f"written to {args.out}")
        return 0

    print("\nno match in the space covered.")
    if progress.units_done < total_units:
        print("Search was cut short - rerun with the same --checkpoint to continue.")
    return 1


# --- argument parsing -------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="solve.py",
        description="Toolkit for the 0.2 BTC seed-phrase puzzle.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="command", required=True)

    def pool_args(sp):
        sp.add_argument("--words", metavar="FILE", help="file of candidate words")
        sp.add_argument("--tiers", help="candidate tiers to include, e.g. A, AB, ABCD")
        sp.add_argument("--extra", help="extra comma-separated words")

    sp = sub.add_parser("validate", help="check candidate words against BIP-39")
    pool_args(sp)
    sp.add_argument("words_pos", nargs="?", metavar="FILE", help=argparse.SUPPRESS)
    sp.set_defaults(func=cmd_validate)

    sp = sub.add_parser("estimate", help="size and time a search without running it")
    pool_args(sp)
    sp.add_argument("--length", type=int, default=12)
    sp.add_argument("--mode", choices=("bip39", "brain"), default="bip39")
    sp.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    sp.add_argument("--pin")
    sp.add_argument("--require")
    sp.set_defaults(func=cmd_estimate)

    sp = sub.add_parser("check", help="test one phrase against the target")
    sp.add_argument("phrase")
    sp.add_argument("--target", default=TARGET_ADDRESS)
    sp.add_argument("--passphrase", default="")
    sp.add_argument("--verbose", action="store_true")
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("bench", help="measure this machine's throughput")
    sp.set_defaults(func=cmd_bench)

    sp = sub.add_parser("selftest", help="run the crypto test vectors")
    sp.set_defaults(func=cmd_selftest)

    sp = sub.add_parser("search", help="run the search")
    pool_args(sp)
    sp.add_argument("--target", default=TARGET_ADDRESS)
    sp.add_argument("--length", type=int, default=12, help="mnemonic length")
    sp.add_argument("--mode", choices=("bip39", "brain"), default="bip39")
    sp.add_argument("--schemes", help=f"comma list or 'all'; default: {','.join(DEFAULT_SCHEMES)}")
    sp.add_argument("--depth", type=int,
                    help="address indices to scan per scheme (default 5). "
                         "--depth 1 roughly doubles throughput")
    sp.add_argument("--passphrase", default="", help="BIP-39 passphrase (13th word)")
    sp.add_argument("--pin", help="fix words to positions, e.g. 0=moon,11=black")
    sp.add_argument("--require", help="words that must appear somewhere")
    sp.add_argument("--joiners", default="space", help="brain mode: space,none,dash,comma")
    sp.add_argument("--casings", default="lower", help="brain mode: lower,upper,title,asis")
    sp.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    sp.add_argument("--prefix-len", type=int, default=2, help="work-splitting granularity")
    sp.add_argument("--limit", type=int, help="stop after N orderings")
    sp.add_argument("--max-seconds", type=int, help="stop after N seconds")
    sp.add_argument("--checkpoint", help="checkpoint file for resumable runs")
    sp.add_argument("--out", help="write hits to this JSON file")
    sp.add_argument("--force", action="store_true", help="run even if hopeless")
    sp.set_defaults(func=cmd_search)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "words_pos", None) and not getattr(args, "words", None):
        args.words = args.words_pos
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
