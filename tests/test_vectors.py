"""Correctness tests.

A search that runs for days is worthless if the derivation is subtly wrong, so
every primitive is pinned to a published test vector, and the search engine
itself is exercised end to end against a planted target.
"""

from __future__ import annotations

import itertools
import os
import unittest

from puzzle import bip39, brainwallet, candidates, derive, electrum, feasibility, keys
from puzzle._ripemd160 import ripemd160
from puzzle.search import Checkpoint, SearchConfig, count_units, run_search
from puzzle.wordlist import (INDEX, WORDS, WORDLIST_SHA256, is_valid, load_wordlist,
                             parse_words, validate)


class TestRipemd160(unittest.TestCase):
    """Vectors from the RIPEMD-160 reference specification."""

    VECTORS = {
        b"": "9c1185a5c5e9fc54612808977ee8f548b2258d31",
        b"a": "0bdc9d2d256b3ee9daae347be6f4dc835a467ffe",
        b"abc": "8eb208f7e05d987a9b044a8e98c6b087f15a0bfc",
        b"message digest": "5d0689ef49d2fae572b881b123a85ffa21595f36",
        b"abcdefghijklmnopqrstuvwxyz": "f71c27109c692c1b56bbdceb5b9d2865b3708dbc",
        b"1234567890" * 8: "9b752e45573d4b39f4dbd3323cab82bf63326bfb",
    }

    def test_reference_vectors(self):
        for msg, want in self.VECTORS.items():
            self.assertEqual(ripemd160(msg).hex(), want, msg[:16])

    def test_matches_hash160_backend(self):
        for msg in (b"", b"abc", b"the quick brown fox"):
            import hashlib
            want = ripemd160(hashlib.sha256(msg).digest())
            self.assertEqual(keys.hash160(msg), want)


class TestWordlist(unittest.TestCase):
    def test_integrity(self):
        words = load_wordlist()
        self.assertEqual(len(words), 2048)
        self.assertEqual(words[0], "abandon")
        self.assertEqual(words[-1], "zoo")

    def test_wordlist_hash_is_pinned(self):
        self.assertEqual(len(WORDLIST_SHA256), 64)

    def test_first_four_letters_are_unique(self):
        """The property BIP-39 guarantees; our suggester relies on it."""
        prefixes = {w[:4] for w in WORDS}
        self.assertEqual(len(prefixes), 2048)

    def test_hint_words_that_are_not_bip39(self):
        """The finding that reframes the puzzle - keep it under test."""
        _, invalid = validate(["breathe", "tuesday", "statue", "justice"])
        self.assertEqual(sorted(invalid), ["breathe", "justice", "statue", "tuesday"])

    def test_hint_words_that_are_bip39(self):
        valid, invalid = validate(["moon", "tower", "food", "this", "subject", "real", "black"])
        self.assertEqual(invalid, [])
        self.assertEqual(len(valid), 7)

    def test_parse_words_dedupes_and_strips_comments(self):
        self.assertEqual(parse_words("moon, tower # note\nMOON  real"),
                         ["moon", "tower", "real"])


class TestBip39(unittest.TestCase):
    """Official Trezor BIP-39 vectors (passphrase 'TREZOR')."""

    VECTORS = [
        ("00000000000000000000000000000000",
         "abandon abandon abandon abandon abandon abandon abandon abandon "
         "abandon abandon abandon about",
         "c55257c360c07c72029aebc1b53c05ed0362ada38ead3e3e9efa3708e5349553"
         "1f09a6987599d18264c1e1c92f2cf141630c7a3c4ab7c81b2f001698e7463b04"),
        ("80808080808080808080808080808080",
         "letter advice cage absurd amount doctor acoustic avoid letter "
         "advice cage above",
         "d71de856f81a8acc65e6fc851a38d4d7ec216fd0796d0a6827a3ad6ed5511a30"
         "fa280f12eb2e47ed2ac03b5c462a0358d18d69fe4f985ec81778c1b370b652a8"),
        ("ffffffffffffffffffffffffffffffff",
         "zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo wrong",
         "ac27495480225222079d7be181583751e86f571027b0497b5b5d11218e0a8a13"
         "332572917f0f8e5a589620c6f15b11c61dee327651a14c34e18231052e48c069"),
    ]

    def test_entropy_to_mnemonic(self):
        for entropy, mnemonic, _ in self.VECTORS:
            self.assertEqual(bip39.entropy_to_mnemonic(bytes.fromhex(entropy)), mnemonic)

    def test_mnemonic_to_seed(self):
        for _, mnemonic, seed in self.VECTORS:
            self.assertEqual(bip39.mnemonic_to_seed(mnemonic, "TREZOR").hex(), seed)

    def test_checksum_validation(self):
        for _, mnemonic, _ in self.VECTORS:
            self.assertTrue(bip39.is_valid_mnemonic(mnemonic))
        self.assertFalse(bip39.is_valid_mnemonic(
            "zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo"))
        self.assertFalse(bip39.is_valid_mnemonic("moon tower food"))
        self.assertFalse(bip39.is_valid_mnemonic("notaword " * 12))

    def test_fast_filter_matches_reference(self):
        """checksum_ok_12 is the hot path; it must never disagree."""
        pool = [INDEX[w] for w in
                "moon tower food real black subject this world time proof only win".split()]
        checked = 0
        for perm in itertools.islice(itertools.permutations(pool, 12), 5000):
            fast = bip39.checksum_ok_12(perm)
            generic = bip39.checksum_ok(perm)
            reference = bip39.is_valid_mnemonic(bip39.indices_to_mnemonic(perm))
            self.assertEqual(fast, reference)
            self.assertEqual(generic, reference)
            checked += 1
        self.assertEqual(checked, 5000)

    def test_checksum_pass_rate_is_one_in_sixteen(self):
        pool = [INDEX[w] for w in
                "moon tower food real black subject this world time proof only win".split()]
        valid = sum(bip39.checksum_ok_12(p)
                    for p in itertools.islice(itertools.permutations(pool, 12), 20000))
        self.assertAlmostEqual(valid / 20000, 1 / 16, delta=0.01)


class TestKeys(unittest.TestCase):
    def test_known_privkey_to_address(self):
        priv = bytes.fromhex(
            "18E14A7B6A307F426A94F8114701E7C8E774E7F9A47E2C2035DB29A206321725")
        self.assertEqual(keys.address_from_privkey(priv, compressed=False),
                         "16UwLL9Risc3QfPqBUvKofHmBQ7wMtjvM")

    def test_privkey_one(self):
        one = (1).to_bytes(32, "big")
        self.assertEqual(keys.address_from_privkey(one, True),
                         "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH")
        self.assertEqual(keys.address_from_privkey(one, False),
                         "1EHNa6Q4Jz2uvNExL497mE43ikXhwF6kZm")
        self.assertEqual(keys.privkey_to_wif(one, False),
                         "5HpHagT65TZzG1PH3CSu63k8DbpvD8s5ip4nEB3kEsreAnchuDf")

    def test_base58_roundtrip(self):
        for addr in ("1KfZGvwZxsvSmemoCmEV75uqcNzYBHjkHZ",
                     "1LqBGSKuX5yYUonjxT5qGfpUsXKYYWeabA",
                     "1111111111111111111114oLvT2"):
            self.assertEqual(keys.address_from_hash160(keys.hash160_from_address(addr)), addr)

    def test_bad_checksum_rejected(self):
        with self.assertRaises(ValueError):
            keys.b58check_decode("1KfZGvwZxsvSmemoCmEV75uqcNzYBHjkHZZ")

    def test_target_hash160(self):
        self.assertEqual(
            keys.hash160_from_address("1KfZGvwZxsvSmemoCmEV75uqcNzYBHjkHZ").hex(),
            "ccbd031e54cde2a3189fd59bc49f731367a1779e")


class TestBip32(unittest.TestCase):
    """BIP-32 test vector 1."""

    SEED = bytes.fromhex("000102030405060708090a0b0c0d0e0f")

    def test_master(self):
        node = derive.master_from_seed(self.SEED)
        self.assertEqual(node.key.hex(),
                         "e8f32e723decf4051aefac8e2c93c9c5b214313817cdb01a1494b917c8436b35")
        self.assertEqual(node.chain_code.hex(),
                         "873dff81c02f525623fd1fe5167eac3a55a049de3d314bb42ee227ffed37d508")

    def test_deep_path(self):
        node = derive.derive_path(derive.master_from_seed(self.SEED),
                                  "m/0'/1/2'/2/1000000000")
        self.assertEqual(node.key.hex(),
                         "471b76e389e528d6de6d816857e012c5455051cad6660850e58372a6c3e6e7c8")
        self.assertEqual(node.chain_code.hex(),
                         "c783e67b921d2beb8f6b389cc646d7263b4145701dadd2161548a8b078e65e9e")

    def test_parse_path(self):
        self.assertEqual(derive.parse_path("m/44'/0'/0'/0/5"),
                         [44 + derive.HARDENED, derive.HARDENED, derive.HARDENED, 0, 5])
        self.assertEqual(derive.parse_path("m"), [])
        self.assertEqual(derive.parse_path("m/0h/1"), [derive.HARDENED, 1])


class TestBip44Addresses(unittest.TestCase):
    """The canonical 'abandon...about' wallet, cross-checked against
    independent BIP-32 implementations."""

    MNEMONIC = ("abandon abandon abandon abandon abandon abandon abandon abandon "
                "abandon abandon abandon about")
    EXPECTED = [
        "1LqBGSKuX5yYUonjxT5qGfpUsXKYYWeabA",
        "1Ak8PffB2meyfYnbXZR9EGfLfFZVpzJvQP",
        "1MNF5RSaabFwcbtJirJwKnDytsXXEsVsNb",
        "1MVGa13XFvvpKGZdX389iU8b3qwtmAyrsJ",
        "1Gka4JdwhLxRwXaC6oLNH4YuEogeeSwqW7",
    ]

    def test_bip44_chain(self):
        seed = bip39.mnemonic_to_seed(self.MNEMONIC)
        parent = derive.derive_path(derive.master_from_seed(seed), "m/44'/0'/0'/0")
        got = [keys.address_from_privkey(derive.ckd_priv(parent, i).key)
               for i in range(len(self.EXPECTED))]
        self.assertEqual(got, self.EXPECTED)

    def test_iter_hash160s_covers_bip44(self):
        seed = bip39.mnemonic_to_seed(self.MNEMONIC)
        found = {h.hex(): (s, i)
                 for h, s, i in derive.iter_hash160s(seed, derive.resolve_schemes(["all"]))}
        target = keys.hash160_from_address(self.EXPECTED[0]).hex()
        self.assertEqual(found[target], ("bip44", 0))

    def test_resolve_schemes(self):
        self.assertEqual(len(derive.resolve_schemes(["all"])), len(derive.SCHEMES))
        self.assertEqual([s.name for s in derive.resolve_schemes(["bip44"])], ["bip44"])
        with self.assertRaises(ValueError):
            derive.resolve_schemes(["nonsense"])


class TestBrainwallet(unittest.TestCase):
    def test_known_brainwallet(self):
        """The canonical weak brainwallet, drained many times over."""
        priv = brainwallet.privkey_for("correct horse battery staple")
        self.assertEqual(
            priv.hex(),
            "c4bbcb1fbec99d65bf59d85c8cb62ee2db963f0fe106f483d9afa73bd4e39a8a")
        self.assertEqual(keys.address_from_privkey(priv, compressed=False),
                         "1JwSSubhmg6iPtRjtyqhUYYH7bZg3Lfy1T")

    def test_variants(self):
        got = set(brainwallet.variants(["a", "b"], ("space", "none"), ("lower", "upper")))
        self.assertEqual(got, {"a b", "A B", "ab", "AB"})


class TestFeasibility(unittest.TestCase):
    def test_pool_growth_is_superexponential(self):
        a = feasibility.estimate(12, 12, workers=1)
        b = feasibility.estimate(13, 12, workers=1)
        self.assertEqual(a.total_candidates, 479_001_600)
        self.assertEqual(b.total_candidates, 6_227_020_800)
        self.assertGreater(b.seconds, a.seconds * 12)

    def test_original_script_is_hopeless(self):
        """36 words, 12 slots - what the repository shipped with."""
        est = feasibility.estimate(36, 12, workers=4)
        self.assertTrue(est.hopeless)
        self.assertGreater(est.seconds, 100 * feasibility.SECONDS_PER_YEAR)

    def test_pinning_shrinks_the_space(self):
        loose = feasibility.estimate(14, 12, workers=4)
        pinned = feasibility.estimate(14, 12, workers=4, pinned=3)
        self.assertLess(pinned.seconds, loose.seconds / 100)

    def test_humanize(self):
        self.assertIn("seconds", feasibility.humanize(30))
        self.assertIn("hours", feasibility.humanize(7200))
        self.assertIn("years", feasibility.humanize(1e10))


class TestCandidates(unittest.TestCase):
    def test_every_tier_word_is_bip39(self):
        self.assertEqual(candidates.audit(), {})

    def test_not_in_bip39_really_is_not(self):
        valid, _ = validate(candidates.NOT_IN_BIP39)
        self.assertEqual(valid, [])

    def test_marked_words_are_the_six_with_a_mechanism(self):
        """The words the artist singled out, not merely drew (ANALYSIS.md s2)."""
        self.assertEqual(candidates.MARKED,
                         ["moon", "tower", "food", "real", "subject", "one"])
        self.assertEqual(validate(candidates.MARKED)[1], [])

    def test_best_12_is_a_single_exhaustible_subset(self):
        """Exactly twelve words means one subset, so a run is exhaustive."""
        self.assertEqual(len(candidates.BEST_12), 12)
        self.assertEqual(len(set(candidates.BEST_12)), 12)
        self.assertEqual(validate(candidates.BEST_12)[1], [])
        for w in candidates.MARKED + candidates.FAINT:
            self.assertIn(w, candidates.BEST_12)

    def test_one_is_a_bip39_word(self):
        """The reading that the underlined numeral is a word, not an index."""
        self.assertTrue(is_valid("one"))
        self.assertIn("one", candidates.TIER_A)

    def test_best_13_is_the_documented_pool(self):
        """The 13 words recovered by direct inspection (ANALYSIS.md s2)."""
        self.assertEqual(len(candidates.BEST_13), 13)
        self.assertEqual(len(set(candidates.BEST_13)), 13, "no duplicates")
        valid, invalid = validate(candidates.BEST_13)
        self.assertEqual(invalid, [])
        for w in ("moon", "tower", "food", "subject", "real", "this", "black"):
            self.assertIn(w, candidates.BEST_13)

    def test_build_pool_dedupes_and_orders(self):
        pool = candidates.build_pool("AB")
        self.assertEqual(len(pool), len(set(pool)))
        self.assertEqual(pool[:3], ["moon", "tower", "food"])


class TestForensicsRegions(unittest.TestCase):
    """The recorded hiding places must stay inside the 1600x1200 artwork."""

    def test_regions_are_wellformed(self):
        import forensics
        for name, spec in forensics.REGIONS.items():
            x0, y0, x1, y1, scale, mode, rot, note = spec
            self.assertLess(x0, x1, name)
            self.assertLess(y0, y1, name)
            self.assertGreaterEqual(x0, 0, name)
            self.assertGreaterEqual(y0, 0, name)
            self.assertLessEqual(x1, 1600, name)
            self.assertLessEqual(y1, 1200, name)
            self.assertIn(mode, ("stretch", "highpass", "channel"), name)
            self.assertIn(rot, (0, 90, -90, 180), name)
            self.assertTrue(note, f"{name} needs a note saying what is there")

    def test_key_regions_present(self):
        import forensics
        for name in ("clock", "plinth", "needle", "statue-base", "vertical"):
            self.assertIn(name, forensics.REGIONS)


class TestElectrum(unittest.TestCase):
    """Official vectors from Electrum's own tests/test_wallet_vertical.py.

    Electrum does not use BIP-39: different checksum, different PBKDF2 salt,
    and the script type is encoded in the seed. A BIP-39-only search would
    walk straight past an Electrum wallet, so this path has to be right.
    """

    STANDARD = ("cycle rocket west magnet parrot shuffle foot correct "
                "salt library feed song")
    SEGWIT = ("bitter grass shiver impose acquire brush forget axis "
              "eager alone wine silver")
    TWOFA_SW = ("universe topic remind silver february ranch shine worth "
                "innocent cattle enhance wise")

    def test_seed_types(self):
        self.assertEqual(electrum.seed_type(self.STANDARD), "standard")
        self.assertEqual(electrum.seed_type(self.SEGWIT), "segwit")
        self.assertEqual(electrum.seed_type(self.TWOFA_SW), "2fa_segwit")

    def test_non_electrum_phrase_has_no_type(self):
        bip39 = ("abandon abandon abandon abandon abandon abandon abandon "
                 "abandon abandon abandon abandon about")
        self.assertIsNone(electrum.seed_type(bip39))

    def test_standard_wallet_addresses(self):
        """m/0/0 receiving and m/1/0 change, straight off the master node."""
        got = {(c, i): keys.address_from_hash160(h)
               for h, c, i in electrum.iter_hash160s(self.STANDARD, depth=1)}
        self.assertEqual(got[("electrum-receiving", 0)],
                         "1NNkttn1YvVGdqBW4PR6zvc3Zx3H5owKRf")
        self.assertEqual(got[("electrum-change", 0)],
                         "1KSezYMhAJMWqFbVFB2JshYg69UpmEXR4D")

    def test_salt_is_electrum_not_mnemonic(self):
        """The one-byte difference that makes this a separate search space."""
        self.assertNotEqual(electrum.mnemonic_to_seed(self.STANDARD),
                            bip39.mnemonic_to_seed(self.STANDARD))

    def test_normalisation(self):
        self.assertEqual(electrum.normalize_text("  Cycle   ROCKET \n west "),
                         "cycle rocket west")

    def test_legacy_prefix_is_standard(self):
        """Only the standard type yields a 1... address; segwit gives bc1."""
        self.assertEqual(electrum.LEGACY_PREFIX, electrum.SEED_PREFIX)
        self.assertTrue(electrum.is_seed_type(self.STANDARD))
        self.assertFalse(electrum.is_seed_type(self.SEGWIT))

    def test_filter_rate_is_one_in_256(self):
        """8 checksum bits, versus BIP-39's 4 - what makes this mode cheap."""
        pool = candidates.BEST_12
        n = ok = 0
        for p in itertools.islice(itertools.permutations(pool, 12), 20000):
            ok += electrum.is_seed_type(" ".join(p))
            n += 1
        self.assertAlmostEqual(ok / n, 1 / 256, delta=0.002)


class TestElectrumSearch(unittest.TestCase):
    def test_finds_planted_electrum_target(self):
        seed = TestElectrum.STANDARD
        target = next(h for h, c, i in electrum.iter_hash160s(seed, depth=1)
                      if c == "electrum-receiving" and i == 0)
        cfg = SearchConfig(pool=seed.split(), target_hash160=target, mode="electrum",
                           workers=2, prefix_len=1, electrum_depth=1)
        hits, _ = run_search(cfg, Checkpoint(None))
        self.assertTrue(hits, "engine failed to find a planted Electrum target")
        self.assertEqual(hits[0].phrase, seed)
        self.assertEqual(hits[0].scheme, "electrum-receiving")


class TestRuneAnalysis(unittest.TestCase):
    """Rune-4 crib verification. Skipped unless the artwork is available."""

    IMAGE = os.environ.get("PUZZLE_IMAGE", "puzzle.png")

    def setUp(self):
        if not os.path.exists(self.IMAGE):
            self.skipTest(f"artwork not present at {self.IMAGE}; "
                          "set PUZZLE_IMAGE to run this test")

    def test_crib_word_lengths_match(self):
        from puzzle.runes import verify_rune4
        r = verify_rune4(self.IMAGE)
        n = len(r["crib_word_lengths"])
        self.assertEqual(r["word_lengths"][:n], r["crib_word_lengths"])

    def test_repeated_letters_look_alike(self):
        """What makes the alignment more than a coincidence of counts."""
        from puzzle.runes import verify_rune4
        r = verify_rune4(self.IMAGE)
        self.assertLess(r["mean_intra_letter_distance"],
                        r["mean_all_pairs_distance"] * 0.6)

    def test_trailing_glyph_is_not_a_letter(self):
        """'number X' is a placeholder symbol, not a recoverable digit."""
        from puzzle.runes import verify_rune4
        r = verify_rune4(self.IMAGE)
        chars = [t for t in r["tail"] if t[2] is not None]
        self.assertTrue(chars, "expected one non-solid trailing glyph")
        for _, _, d in chars:
            self.assertGreater(d, r["mean_intra_letter_distance"])


class TestRuneConstants(unittest.TestCase):
    """Checks that need no image."""

    def test_crib_is_consistent_with_separator_count(self):
        from puzzle import runes
        words = runes.RUNE4_CRIB.split()
        self.assertEqual(len(words), 7)
        self.assertEqual(sum(len(w) for w in words), 41)
        # 7 separators: six between the seven crib words, one before "number X"
        self.assertEqual(len(runes.RUNE4_SEPARATORS), 7)

    def test_box_inside_artwork(self):
        from puzzle import runes
        x0, y0, x1, y1 = runes.RUNE4_BOX
        self.assertTrue(0 <= x0 < x1 <= 1600)
        self.assertTrue(0 <= y0 < y1 <= 1200)


class TestSearchEngine(unittest.TestCase):
    """End-to-end: plant a target the engine must find."""

    POOL = ("abandon abandon abandon abandon abandon abandon abandon abandon "
            "abandon abandon abandon about").split()

    def _planted(self, mnemonic, scheme="bip44", index=0):
        seed = bip39.mnemonic_to_seed(mnemonic)
        for h, s, i in derive.iter_hash160s(seed, derive.resolve_schemes(["all"])):
            if s == scheme and i == index:
                return h
        raise AssertionError("scheme not produced")

    def test_finds_planted_bip39_target(self):
        mnemonic = "moon tower food real black subject this time world only proof find"
        self.assertTrue(bip39.is_valid_mnemonic(mnemonic), "fixture must be checksum-valid")
        target = self._planted(mnemonic)
        cfg = SearchConfig(
            pool=mnemonic.split(), target_hash160=target, workers=2, prefix_len=1,
            schemes=tuple(derive.resolve_schemes(["bip44"])),
        )
        hits, progress = run_search(cfg, Checkpoint(None))
        self.assertTrue(hits, "engine failed to find a planted target")
        self.assertEqual(hits[0].phrase, mnemonic)
        self.assertEqual(hits[0].scheme, "bip44")
        self.assertGreater(progress.tested, 0)

    def test_finds_planted_target_on_unusual_scheme(self):
        """A wallet on m/0/0 must not be missed just because BIP-44 is default."""
        mnemonic = "moon tower food real black subject this time world only proof find"
        target = self._planted(mnemonic, scheme="bip32-root", index=2)
        cfg = SearchConfig(
            pool=mnemonic.split(), target_hash160=target, workers=2, prefix_len=1,
            schemes=tuple(derive.resolve_schemes(["all"])),
        )
        hits, _ = run_search(cfg, Checkpoint(None))
        self.assertTrue(hits)
        self.assertEqual(hits[0].scheme, "bip32-root")
        self.assertEqual(hits[0].index, 2)

    def test_finds_planted_brainwallet(self):
        words = ["moon", "tower", "food", "black"]
        phrase = "moon tower food black"
        target = keys.hash160(keys.pubkey_from_privkey(
            brainwallet.privkey_for(phrase), True))
        cfg = SearchConfig(pool=words, target_hash160=target, phrase_len=4,
                           mode="brain", workers=2, prefix_len=1)
        hits, _ = run_search(cfg, Checkpoint(None))
        self.assertTrue(hits)
        self.assertEqual(hits[0].phrase, phrase)

    def test_pinned_positions_are_respected(self):
        mnemonic = "moon tower food real black subject this time world only proof find"
        target = self._planted(mnemonic)
        cfg = SearchConfig(
            pool=mnemonic.split(), target_hash160=target, workers=2, prefix_len=1,
            pinned={0: "moon", 11: "find"},
            schemes=tuple(derive.resolve_schemes(["bip44"])),
        )
        hits, progress = run_search(cfg, Checkpoint(None))
        self.assertTrue(hits)
        self.assertEqual(hits[0].phrase, mnemonic)
        # 10 free slots, not 12: the space really did shrink
        self.assertLess(progress.tested, 3_628_801)

    def test_no_false_positive(self):
        cfg = SearchConfig(
            pool="moon tower food real black subject this world time proof only find".split(),
            target_hash160=bytes(20), workers=2, prefix_len=1, limit=4_000,
            schemes=tuple(derive.resolve_schemes(["bip44"])),
        )
        hits, _ = run_search(cfg, Checkpoint(None))
        self.assertEqual(hits, [])

    def test_truncated_units_are_not_checkpointed(self):
        """A unit cut short by --limit must be re-searched on resume.

        Marking it done would silently leave a hole in the covered space,
        which is the worst possible failure mode for a multi-day run.
        """
        pool = "moon tower food real black subject this time world only proof find".split()
        cfg = SearchConfig(pool=pool, target_hash160=bytes(20), workers=2,
                           prefix_len=1, limit=4_000,
                           schemes=tuple(derive.resolve_schemes(["bip44"])))
        ckpt = Checkpoint(None)
        hits, progress = run_search(cfg, ckpt)
        self.assertEqual(hits, [])
        self.assertGreater(progress.units_truncated, 0,
                           "fixture should truncate at least one unit")
        self.assertEqual(len(ckpt.done), progress.units_done)
        self.assertNotIn(0, ckpt.done, "unit 0 was cut short and must not be marked done")

    def test_checkpoint_resume_skips_completed_units(self):
        pool = "moon tower food real black subject this world time proof only find".split()
        cfg = SearchConfig(pool=pool, target_hash160=bytes(20), workers=1, prefix_len=1)
        total = count_units(cfg)
        ckpt = Checkpoint(None)
        ckpt.done = set(range(total))
        hits, progress = run_search(cfg, ckpt)
        self.assertEqual(progress.tested, 0)
        self.assertEqual(hits, [])

    def test_required_words_filter_subsets(self):
        pool = "moon tower food real black subject this world time proof only find brave".split()
        cfg = SearchConfig(pool=pool, target_hash160=bytes(20), required=["brave"],
                           workers=1, prefix_len=0)
        for subset, _ in itertools.islice(
                __import__("puzzle.search", fromlist=["iter_units"]).iter_units(cfg), 50):
            self.assertIn("brave", subset)


if __name__ == "__main__":
    unittest.main(verbosity=2)
