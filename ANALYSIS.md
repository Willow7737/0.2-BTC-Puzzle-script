# Analysis: the 0.2 BTC seed-phrase puzzle

Target address `1KfZGvwZxsvSmemoCmEV75uqcNzYBHjkHZ`
HASH160 `ccbd031e54cde2a3189fd59bc49f731367a1779e`
Balance 0.20107284 BTC · posted 2020-05-10 · unsolved

This document records what can be established about the puzzle, what the
published hints do and do not support, and why the original brute-force
approach in this repository could never have finished. Everything asserted
here is reproducible with the tooling in this repo; the claims that matter are
pinned by tests in `tests/test_vectors.py`.

---

## 1. The finding that reframes the puzzle

Two of the most widely repeated hints point at words that **do not exist in
the BIP-39 English wordlist**:

| Hint | Word | In BIP-39? | Nearest BIP-39 words |
|---|---|---|---|
| "'Breathe' can be found on George Floyd's chest as well as the Statue's Neck" | `breathe` | **No** | `bread`, `breeze` |
| Rune 3 (above Trump), Bill Cipher, translates to "Tuesday" | `tuesday` | **No** | *(no weekday is in BIP-39)* |

Verify it yourself:

```console
$ ./solve.py validate --extra "breathe,tuesday,moon,tower,black"
  INVALID  breathe      suggest: bread, rather, rate, weather, brother
  INVALID  tuesday      suggest: today, essay, turkey, say, day
  ok       moon         #1148
  ...
```

This matters because BIP-39 is a closed vocabulary of exactly 2048 words. A
mnemonic *cannot* contain `breathe`. So at most one of the following is true:

**(a) The answer is not a BIP-39 mnemonic.** The puzzle's own wording supports
this — it says "the seed **passphrase** is hidden in the picture", not "seed
phrase". A free-form passphrase hashed straight to a private key (a
*brainwallet*) accepts any vocabulary, including `breathe` and `tuesday`. This
repository's original script could not have found such a key under any
circumstances, because it only ever built BIP-39 mnemonics.

**(b) `breathe` and `tuesday` are not literal seed words.** They may encode
something else. Note that rune 2 translates to "**sum of two numbers**", rune 4
to "rainy day number **X**", and rune 3 to a *weekday*. Three of the four runes
refer to numbers or ordinals rather than to nouns. A natural reading is that
the runes encode **positions or indices**, not words — for instance which slot
a word occupies, or an index into the 2048-word list. Under this reading
"Tuesday" is a number (2 or 3, depending on whether the week starts Sunday),
not a seed word.

**(c) The hints are simply wrong.** They are community-derived, not authored by
the puzzle's creator, and no one has verified them against a solution.

Interpretation (b) is the most productive, because it is the only one that
keeps a BIP-39 search alive while explaining the non-BIP-39 hints. The tooling
here supports (a) too, via `--mode brain`.

### Words the hints support that *are* valid BIP-39

`moon` · `tower` · `food` · `this` · `subject` · `real` · `black`

Seven words. A 12-word mnemonic needs five more.

---

## 2. Why the original script could not have worked

The script this repository shipped with did:

```python
seed_words = [...]                                   # 36 words
for combination in itertools.permutations(seed_words, 12):
```

`P(36, 12)` is **599,555,620,984,320,000** orderings — six hundred quadrillion.

```console
$ ./solve.py estimate --words seedwords.txt
  total candidates    599,555,620,984,320,000 (~6e+17)
  estimated wall time 625,757 years
  VERDICT: HOPELESS. This will never finish.
```

625,757 years on four cores. Buying a thousand times more CPU brings it to 625
years. This is not a tuning problem; the pool is too big by about nine orders
of magnitude.

The cost curve is brutal, and it is the single most important thing to
internalise before starting any run:

| Pool size | Orderings | Wall time (4 cores) |
|---:|---:|---:|
| 12 | 479,001,600 | **7.5 hours** |
| 13 | 6,227,020,800 | 4.1 days |
| 14 | 43,589,145,600 | 28.5 days |
| 15 | 217,945,728,000 | 142.7 days |
| 16 | 871,782,912,000 | 2 years |
| 18 | 8,892,185,702,400 | 16 years |
| 20 | 60,339,831,552,000 | 108 years |
| 36 | 599,555,620,984,320,000 | 625,757 years |

**Each extra candidate word multiplies the work by roughly the pool size.**
Identifying one more word correctly is worth more than a data centre. Twelve
words is a tractable search; sixteen is not.

### Three further defects in the original script

1. **No checksum pre-filter.** Only 1 in 16 orderings of a 12-word set has a
   valid BIP-39 checksum (128 entropy bits + 4 checksum bits). The original
   discovered this by calling `Bip39SeedGenerator` and catching the exception —
   paying full mnemonic parsing plus Python exception overhead for every one of
   the 15 rejects. Checking the checksum directly costs one SHA-256 over 16
   bytes.
2. **One derivation path only.** It tested `m/44'/0'/0'/0/0` and nothing else.
   A 2020 wallet with a legacy `1...` address might equally sit on `m/0'/0/0`
   (bitcoinjs, blockchain.info) or `m/0/0`. Testing one path risks deriving the
   right seed and walking straight past it.
3. **`random.shuffle(seed_words)` before enumerating.** Non-deterministic, so a
   run could not be resumed, reproduced, or divided between machines. Two runs
   would redo overlapping work while leaving other regions untouched.

---

## 3. What this toolkit does instead

| Problem | Fix | Measured effect |
|---|---|---|
| No checksum filter | Direct 132-bit packing + SHA-256 | 657,000 rejects/sec/core |
| PBKDF2 on every candidate | Only on the 1-in-16 that pass | ~16x fewer PBKDF2 calls |
| Base58 encode per candidate | Compare 20-byte HASH160 | big-int encode out of the hot path |
| Single derivation path | 6 schemes, parent node cached | ~26 addresses per seed |
| Single core | `multiprocessing`, unit-partitioned | ~4x on this machine |
| Not resumable | Deterministic units + checkpoint file | resume after interruption |
| No idea how long | Feasibility model, refuses hopeless runs | see `estimate` |
| BIP-39 only | `--mode brain` for free-form passphrases | ~65x faster per candidate |

Measured on 4 cores (`./solve.py bench`):

```
checksum filter :      657,069 perms/sec/core
bip39 candidate :          278 /sec/core   (PBKDF2-2048 + 4 schemes)
brain candidate :       18,154 /sec/core   (SHA-256 + EC + hash160)
```

PBKDF2 dominates BIP-39 mode: 2048 rounds of HMAC-SHA-512 is deliberately
expensive, and no amount of engineering removes it. The checksum filter is what
keeps it off 15 of every 16 candidates.

---

## 4. Recommended search order

Ranked by probability-per-CPU-hour.

**1 — Exhaust 12-word pools built from tier A plus five tier-B words.**
Seven hint-supported words plus five from the prominent rendered text
("BRAVE NEW WORLD", "Order and stability", "ONLY real Bitcoin", "FIND THE SEED
PHRASE IN THIS PICTURE"). Each such pool is 7.5 hours on four cores, and there
are only C(8,5) = 56 ways to pick the five. That is the highest-value region.

```console
$ ./solve.py search --tiers A --extra "brave,world,order,only,find" \
      --workers 4 --checkpoint runs/a12.json
```

**2 — Brainwallet mode on the same vocabulary, including the non-BIP-39 words.**
Sixty-five times cheaper per candidate and the only mode that can accommodate
`breathe`. If interpretation (a) is right, this is where the answer lives.

```console
$ ./solve.py search --mode brain --tiers A \
      --extra "breathe,tuesday,brave,world,only" \
      --joiners space,none --casings lower,title --workers 4
```

**3 — Pin positions using the runes.** If the runes encode positions, pinning
even one word divides the work by the pool size; pinning three makes a 15-word
pool cheaper than an unpinned 12-word one.

```console
$ ./solve.py search --tiers AB --pin 0=moon,11=black --workers 4
```

**4 — Only then widen the pool.** Adding tier C or D words without pinning
pushes the run past a year.

---

## 5. Coverage so far

A bounded run against the highest-value pool, to demonstrate the engine and
establish a baseline:

```
pool     moon tower food this subject real black brave world order only find
mode     bip39, 4 schemes (bip44, bip32-legacy, bip32-root, master)
result   15,505,408 orderings tested (968,858 checksum-valid) in 15.0 minutes
         385 of 11,880 work units = 3.2% of this pool
         no match
```

Sustained 17,228 orderings/sec on four cores. Completing this one pool takes
about 7.5 hours; the checkpoint means it can be resumed in slices. Nothing is
ruled out yet - 3.2% of one candidate pool is a baseline, not a result.

## 6. Open questions

- **Is the phrase 12 words?** Nothing establishes the length. `--length`
  accepts 15/18/21/24, and brainwallet mode accepts any length. A 24-word
  phrase is unsearchable by permutation and would need the word *order* to be
  determined by the image.
- **What do the runes encode?** The "sum of two numbers" / "Tuesday" /
  "number X" cluster is the strongest untapped signal in the puzzle. If they
  give positions, the search collapses from intractable to trivial. Decoding
  them is worth more than any amount of brute force.
- **Is there a BIP-39 passphrase?** `--passphrase` is supported. If the image
  hides a 13th-word passphrase, every phrase-only search misses.
- **Is the wallet even on the first address?** The schemes here scan five
  address indices per path. A deposit to a later index would be missed.
- **Was the image ever edited?** The hints mention hidden text under the Statue
  of Liberty's base recovered with error-level analysis. A systematic forensic
  pass over the full-resolution original may hold words nobody has listed.

---

## 7. Verification

Every cryptographic primitive is pinned to a published test vector, and the
search engine is tested against planted targets it must find:

```console
$ ./solve.py selftest
Ran 41 tests in 0.974s
OK
```

Covered: RIPEMD-160 reference vectors; BIP-39 Trezor vectors (entropy →
mnemonic → seed); BIP-32 test vector 1; the canonical
`abandon abandon … about` BIP-44 address chain; Base58Check round-trips; the
`correct horse battery staple` brainwallet; agreement between the fast checksum
filter and full mnemonic validation over 5,000 permutations; and end-to-end
recovery of planted targets on BIP-44, on `m/0/2`, with pinned positions, and
in brainwallet mode.

Derivation was additionally cross-checked against two independent
implementations — Trezor's `mnemonic` and the `bip32` package — over 200 random
mnemonics, with zero disagreements.
