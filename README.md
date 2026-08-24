# 0.2 BTC Puzzle — solver toolkit

![0.2 BTC Puzzle](https://privatekeys.pw/images/puzzles/0.2-btc-puzzle.png)

Tooling for the [0.2 BTC puzzle](https://privatekeys.pw/puzzles/0.2-btc-puzzle):
a seed phrase hidden in an image, unlocking

**`1KfZGvwZxsvSmemoCmEV75uqcNzYBHjkHZ`** — 0.20107284 BTC, posted 2020-05-10, still unsolved.

> **Read [ANALYSIS.md](ANALYSIS.md) before running anything.** Three things
> change what you should actually run:
> 1. Two of the most-cited hints (`breathe`, `tuesday`) are **not BIP-39 words**.
> 2. The 36-word list this repo originally shipped would take **625,757 years**.
> 3. Nothing is hidden *under* the pixels — no metadata, uniform alpha, clean
>    LSB planes. The words are **drawn into the artwork at low contrast**, and
>    `forensics.py` recovers them.

---

## Quick start

```bash
git clone https://github.com/willow7737/0.2-BTC-Puzzle-script.git
cd 0.2-BTC-Puzzle-script
pip install -r requirements.txt     # optional: only speeds things up
./solve.py selftest                 # prove the crypto is correct
./solve.py bench                    # measure your machine
./solve.py estimate --tiers A --extra "brave,world,order,only,find"
```

There are no required dependencies — the toolkit runs on the standard library
alone. Installing `coincurve` makes it roughly 50x faster.

---

## Commands

### `validate` — are these real BIP-39 words?

Run this first, always. A single non-BIP-39 word makes an entire BIP-39 search
futile, and this is exactly the trap the published hints set.

```console
$ ./solve.py validate --words seedwords.txt
$ ./solve.py validate --extra "breathe,tuesday,moon"
  INVALID  breathe      suggest: bread, rather, rate, weather, brother
  INVALID  tuesday      suggest: today, essay, turkey, say, day
  ok       moon         #1148
```

### `estimate` — how long would that take?

```console
$ ./solve.py estimate --words seedwords.txt
  total candidates    599,555,620,984,320,000 (~6e+17)
  estimated wall time 625,757 years
  VERDICT: HOPELESS. This will never finish.

How the pool size drives cost:
   pool              candidates         wall time
     12             479,001,600         7.5 hours
     13           6,227,020,800          4.1 days
     14          43,589,145,600         28.5 days
     16         871,782,912,000            2 years
     20      60,339,831,552,000          108 years
```

**Each extra word multiplies the work by roughly the pool size.** Identifying
one more word correctly beats any amount of hardware.

### `check` — test one specific phrase

Tests a phrase against every derivation scheme *and* every brainwallet
rendering at once.

```console
$ ./solve.py check "moon tower food real black subject this time world only proof find"
BIP-39 checksum: VALID
  BIP-39 / BIP-32 derivations:
                 bip44                    /0  1HK2sUofEXTNHsFBVn1mthP62LYm59DRFN
                 bip32-legacy             /0  ...
RESULT: no match
```

### `search` — run it

```console
$ ./solve.py search --tiers A --extra "brave,world,order,only,find" \
      --workers 4 --checkpoint runs/a12.json
```

Progress is checkpointed; re-run the same command with the same `--checkpoint`
to resume exactly where it stopped. Ctrl-C is safe.

Useful flags:

| Flag | Effect |
|---|---|
| `--tiers A`…`ABCD` | candidate pools by evidence strength (see below) |
| `--extra w1,w2` | add your own words |
| `--words FILE` | load a word file (commas/newlines, `#` comments) |
| `--pin 0=moon,11=black` | fix words to positions — divides work by the pool size |
| `--require brave` | force a word to appear somewhere |
| `--mode brain` | free-form passphrase, ~65x faster, any vocabulary |
| `--schemes all` | test all six derivation schemes |
| `--passphrase X` | BIP-39 passphrase (the "13th word") |
| `--length 15` | non-12-word mnemonics |
| `--depth 1` | scan one address index per scheme — roughly doubles throughput |
| `--max-seconds N` | bounded run, reports coverage |
| `--checkpoint F` | resumable |

### `forensics.py` — read the words off the image

The seed words are not steganography; they are drawn at low contrast on clock
hands, tower shafts and monument plinths. Three tonal operations recover them:
contrast stretch, high-pass, and single-channel isolation (which reads dark
ink straight through translucent paint).

```console
$ ./forensics.py probe puzzle.png            # rules steganography in or out
  alpha: 1 distinct value(s)  -> uniform, nothing hidden
  LSB plane means: R 0.4979  G 0.4995  B 0.5053

$ ./forensics.py regions puzzle.png -o out/  # every known hiding place
  clock          MOON on the red hand, TOWER on the black hand; face is mirrored
  plinth         13th Amendment; 'Section 1' and 'subject' are underlined
  needle         FOOD on the tower shaft
  statue-base    ONLY real Bitcoin
  vertical       PAY FOR THE FUTURE / THIS IS THE FIRST PREDICTION

$ ./forensics.py runes puzzle.png            # verify rune 4 against its crib
  word lengths from image : [5, 11, 8, 2, 6, 4, 5]
  word lengths from crib  : [5, 11, 8, 2, 6, 4, 5]  -> MATCH
  recovered alphabet: ЁАБВДЕЗИЙКМНОРСТФЧШЫЬ (21 letters)

$ ./forensics.py crop puzzle.png 1295,790,1495,1000 -m channel --channel r
```

Rune 4 segments into 50 glyphs whose word lengths match the published Russian
plaintext exactly, and glyphs the crib calls the same letter are far more
alike (mean distance 27.2) than random pairs (66.7) — so the translation is
confirmed and a 21-letter cipher alphabet falls out. Its trailing "number X"
is a **placeholder asterisk, not a digit**, which closes what looked like the
puzzle's best numeric lead.

The plinth is the find that matters: under the graffiti it carries the
**13th Amendment, Section 1**, with exactly two things underlined — the word
**`subject`** and the numeral **`1`**. A seed word paired with a number. See
[ANALYSIS.md §2](ANALYSIS.md#2-what-the-image-actually-contains).

### `bench` / `selftest`

```console
$ ./solve.py bench
checksum filter :      657,069 perms/sec/core
bip39 candidate :          278 /sec/core   (PBKDF2-2048 + 4 schemes)
brain candidate :       18,154 /sec/core

$ ./solve.py selftest
Ran 49 tests in 1.326s
OK
```

---

## Candidate tiers

Pools are graded by how directly the evidence supports them, because pool size
is what decides whether a run finishes.

| Tier | Words | Basis |
|---|---|---|
| **A** (7) | moon tower food this subject real black | read directly off the artwork |
| **B** (10) | brave world order only first future seed phrase picture find | prominent rendered text |
| **C** (19) | flag mask face camera eye pyramid clock … | objects drawn in the image |
| **D** (20) | coin digital public private key network trust … | whitepaper text and rune concepts |

`candidates.BEST_13` is tier A plus the six tier-B display words — the pool
with the strongest evidence, and the one worth exhausting first
(~2 days on four cores via the BIP-44 fast path).

`puzzle/candidates.py` also lists `NOT_IN_BIP39` — hint words such as
`breathe`, `tuesday`, `statue` and `justice` that cannot appear in a mnemonic.
A test asserts every tier word is genuinely in BIP-39 and every `NOT_IN_BIP39`
word genuinely is not.

---

## What makes this fast

* **Checksum pre-filter.** Only 1 in 16 orderings of a 12-word set is a valid
  BIP-39 mnemonic. Rejecting the rest costs one SHA-256 over 16 bytes instead
  of 2048 rounds of PBKDF2-HMAC-SHA-512 — the difference between 657,000/sec
  and 278/sec per core.
* **HASH160 comparison.** The target address is decoded once; the inner loop
  compares 20-byte hashes and never Base58-encodes.
* **Cached parent nodes.** Each derivation path's parent is derived once per
  seed, so scanning five address indices costs barely more than one.
* **Deterministic work units.** Work is split into units enumerated in a fixed
  order, so runs are parallel, resumable, and divisible across machines.
* **Early exit.** A unit that finds the answer stops immediately.

---

## Layout

```
solve.py                 search CLI
forensics.py             image forensics CLI
puzzle/wordlist.py       BIP-39 wordlist, integrity check, validation
puzzle/bip39.py          checksum filter, mnemonic -> seed
puzzle/keys.py           secp256k1, HASH160, Base58Check
puzzle/_ripemd160.py     pure-Python RIPEMD-160 (OpenSSL 3 fallback)
puzzle/derive.py         BIP-32 and the six derivation schemes
puzzle/brainwallet.py    free-form passphrase mode
puzzle/search.py         parallel, checkpointed search engine
puzzle/feasibility.py    search-space arithmetic and time estimates
puzzle/candidates.py     curated candidate tiers
puzzle/runes.py          rune segmentation and crib-driven cipher recovery
data/english.txt         BIP-39 wordlist (SHA-256 pinned)
tests/test_vectors.py    49 tests: published vectors + planted targets
legacy/                  the original script, kept for reference
```

---

## Correctness

Brute force is worthless if the derivation is wrong, so every primitive is
pinned to a published test vector: RIPEMD-160 reference vectors, BIP-39 Trezor
vectors, BIP-32 test vector 1, the canonical `abandon abandon … about` BIP-44
address chain, Base58Check round-trips, and the `correct horse battery staple`
brainwallet. The search engine is tested end-to-end against planted targets on
BIP-44, on `m/0/2`, with pinned positions, and in brainwallet mode.

Derivation was additionally cross-checked against two independent
implementations (Trezor's `mnemonic` and the `bip32` package) over 200 random
mnemonics with zero disagreements.

---

## Honest expectations

This puzzle has been public and unsolved since May 2020, with many people
attacking it. **This toolkit does not solve it.** What it does is make the
search correct, measurable, and resumable, and make clear which searches are
worth starting — so you spend CPU only where it can pay off.

The best available lead is not more compute. It is decoding what the runes
mean: three of the four refer to numbers or ordinals, and if they encode word
*positions*, the search collapses from intractable to trivial. See
[ANALYSIS.md §6](ANALYSIS.md#6-open-questions).

## Safety

Never type a seed phrase you actually use into any tool, including this one.
This searches for a published puzzle key; if you find it, the funds are the
solver's by the puzzle's own terms.
