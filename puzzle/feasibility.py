"""Search-space arithmetic and honest run-time estimates.

The original script enumerated ``permutations(36 words, 12)``. That is 3.7e18
orderings; at the measured throughput it would take longer than the age of the
universe. Printing that number before a run starts is the single most useful
thing this tool does, so the CLI always shows it and refuses hopeless runs
unless they are forced.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import comb, perm

#: Measured on a 2020-class x86-64 core. Override with --rate if yours differs.
RATE_CHECKSUM_FILTER = 657_000.0   # permutations/second/core (12-word packing + SHA-256)
RATE_BIP39_CANDIDATE = 278.0       # full PBKDF2 + 4-scheme derivation/second/core
RATE_BRAIN_CANDIDATE = 18_000.0    # SHA-256 + EC multiply + hash160/second/core

CHECKSUM_PASS_RATE = 1.0 / 16.0    # 4 checksum bits for a 12-word mnemonic

SECONDS_PER_YEAR = 365.25 * 24 * 3600


@dataclass
class Estimate:
    """The size and cost of a configured search."""

    subsets: int
    orderings: int
    total_candidates: int
    checksum_valid: int
    seconds: float
    workers: int
    mode: str

    @property
    def feasible(self) -> bool:
        """Under a week of wall-clock time on the configured worker count."""
        return self.seconds <= 7 * 24 * 3600

    @property
    def hopeless(self) -> bool:
        """Longer than a human lifetime - almost certainly a misconfiguration."""
        return self.seconds > 100 * SECONDS_PER_YEAR


def humanize(seconds: float) -> str:
    """Render a duration in units a person can act on."""
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    if seconds < 90:
        return f"{seconds:.1f} seconds"
    if seconds < 90 * 60:
        return f"{seconds / 60:.1f} minutes"
    if seconds < 48 * 3600:
        return f"{seconds / 3600:.1f} hours"
    if seconds < 365 * 24 * 3600:
        return f"{seconds / 86400:.1f} days"
    years = seconds / SECONDS_PER_YEAR
    if years < 1e6:
        return f"{years:,.0f} years"
    return f"{years:.3g} years"


def humanize_count(n: int) -> str:
    """Large integers with a magnitude hint."""
    if n < 1_000_000:
        return f"{n:,}"
    return f"{n:,} (~{n:.3g})"


def estimate(
    pool_size: int,
    phrase_len: int = 12,
    *,
    mode: str = "bip39",
    workers: int = 1,
    pinned: int = 0,
    required: int = 0,
    rate_candidate: float | None = None,
    rate_filter: float = RATE_CHECKSUM_FILTER,
) -> Estimate:
    """Estimate the size and duration of a search.

    ``pinned`` positions are fixed words, so they shrink both the pool and the
    number of slots to fill. ``required`` words must appear somewhere, which
    prunes subsets but not orderings.
    """
    free_slots = phrase_len - pinned
    free_pool = pool_size - pinned
    if free_slots < 0 or free_pool < free_slots:
        return Estimate(0, 0, 0, 0, 0.0, workers, mode)

    subsets = comb(free_pool, free_slots)
    if required:
        remaining_required = max(required - pinned, 0)
        if remaining_required:
            # subsets that contain every required word
            subsets = comb(free_pool - remaining_required, free_slots - remaining_required)
    orderings = perm(free_slots, free_slots)  # free_slots!
    total = subsets * orderings

    workers = max(1, workers)
    if mode == "brain":
        rate = rate_candidate or RATE_BRAIN_CANDIDATE
        checksum_valid = total
        seconds = total / (rate * workers)
    else:
        rate = rate_candidate or RATE_BIP39_CANDIDATE
        checksum_valid = int(total * CHECKSUM_PASS_RATE)
        seconds = (total / (rate_filter * workers)) + (checksum_valid / (rate * workers))

    return Estimate(subsets, orderings, total, checksum_valid, seconds, workers, mode)


def report(est: Estimate, pool_size: int, phrase_len: int) -> str:
    """A human-readable feasibility block for the CLI."""
    lines = [
        "Search space",
        f"  pool                {pool_size} words, choose {phrase_len}",
        f"  word subsets        {humanize_count(est.subsets)}",
        f"  orderings / subset  {humanize_count(est.orderings)}",
        f"  total candidates    {humanize_count(est.total_candidates)}",
    ]
    if est.mode != "brain":
        lines.append(f"  checksum-valid      {humanize_count(est.checksum_valid)}  (1 in 16)")
    lines += [
        f"  workers             {est.workers}",
        f"  estimated wall time {humanize(est.seconds)}",
    ]
    if est.hopeless:
        lines += [
            "",
            "  VERDICT: HOPELESS. This will never finish.",
            "  Every word removed from the pool divides the work by roughly the pool size,",
            "  so trimming is far more effective than adding CPUs. Options, best first:",
            "    --tiers A          shrink the pool to the best-evidenced words",
            "    --pin 0=moon       fix a word to a position (divides by the pool size)",
            "    --require brave    force a word to appear (prunes subsets)",
            "    --mode brain       ~65x faster per candidate, no BIP-39 restriction",
            "    --max-seconds N    accept partial coverage and report how much",
        ]
    elif not est.feasible:
        lines += ["", "  VERDICT: very long. Consider trimming the pool or pinning positions."]
    else:
        lines += ["", "  VERDICT: feasible."]
    return "\n".join(lines)
