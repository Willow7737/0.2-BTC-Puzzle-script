"""Correctness tests.

A search that runs for days is worthless if the derivation is subtly wrong, so
every primitive is pinned to a published test vector, and the search engine
itself is exercised end to end against a planted target.
"""

from __future__ import annotations

import itertools
import os
import unittest

from puzzle import (bip39, brainwallet, candidates, derive, electrum, feasibility,
                    keys, positions)
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

    def test_electrum_is_cheaper_like_for_like(self):
        """The documented ~7x, comparing modes doing comparable derivation work.

        The headline figure is BIP-44 fast path (one scheme, one index) against
        Electrum (two chains); both minimal. Compared at each mode's *default*
        breadth the gap is wider still, because BIP-39's default scans 26
        addresses per seed to Electrum's 10 - see the next test.
        """
        b = feasibility.estimate(12, 12, mode="bip39", workers=4, rate_candidate=554)
        e = feasibility.estimate(12, 12, mode="electrum", workers=4, rate_candidate=518)
        self.assertEqual(b.total_candidates, e.total_candidates)
        ratio = b.seconds / e.seconds
        self.assertGreater(ratio, 6.0, f"like-for-like ratio {ratio:.1f}")
        self.assertLess(ratio, 9.0, f"like-for-like ratio {ratio:.1f}")

    def test_electrum_cheaper_at_default_breadth_too(self):
        b = feasibility.estimate(12, 12, mode="bip39", workers=4)
        e = feasibility.estimate(12, 12, mode="electrum", workers=4)
        self.assertGreater(b.seconds / e.seconds, 10.0)

    def test_electrum_filter_is_one_in_256(self):
        e = feasibility.estimate(12, 12, mode="electrum", workers=1)
        self.assertAlmostEqual(e.checksum_valid / e.total_candidates,
                               1 / 256, delta=1e-6)

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

    def test_provenance_records_a_single_original(self):
        """Three sources, byte-identical - there is no better file."""
        import forensics
        p = forensics.PROVENANCE
        self.assertEqual(p["size"], (1600, 1200))
        self.assertEqual(len(p["sha256"]), 64)
        self.assertGreaterEqual(len(p["identical_sources"]), 3)
        self.assertIn("i.redd.it/n1x7g8ceaur51.png", p["identical_sources"])

    def test_artwork_is_not_a_downscale(self):
        """Sharp edges and energy to Nyquist: near-native resolution."""
        import forensics
        p = forensics.PROVENANCE
        self.assertFalse(p["downscaled_from_larger"])
        self.assertLess(p["edge_run_mean_px"], 2.0)
        self.assertGreater(p["single_pixel_edge_share"], 0.5)
        self.assertGreater(p["spectral_tail_mid_ratio"], 0.3)

    def test_provenance_matches_the_artwork_when_present(self):
        """If the file is here, its hash must match the recorded one."""
        import hashlib, os
        import forensics
        img = os.environ.get("PUZZLE_IMAGE", "puzzle.png")
        if not os.path.exists(img):
            self.skipTest("artwork not present")
        got = hashlib.sha256(open(img, "rb").read()).hexdigest()
        self.assertEqual(got, forensics.PROVENANCE["sha256"])
        self.assertEqual(os.path.getsize(img), forensics.PROVENANCE["bytes"])

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


class TestPassphrase(unittest.TestCase):
    """The "13th word". A search that silently ignored it would burn hours."""

    MNEMONIC = "moon tower food real black subject this time world only proof find"

    def _planted(self, passphrase):
        seed = bip39.mnemonic_to_seed(self.MNEMONIC, passphrase)
        return next(h for h, _, _ in
                    derive.iter_hash160s(seed, derive.resolve_schemes(["bip44"], depth=1)))

    def test_passphrase_changes_the_address(self):
        seen = {pp: self._planted(pp) for pp in ("", "breathe", "Breathe", "tuesday")}
        self.assertEqual(len(set(seen.values())), 4, "passphrases must not collide")

    def test_checksum_is_independent_of_passphrase(self):
        """Why one enumeration pass can serve every passphrase."""
        self.assertTrue(bip39.is_valid_mnemonic(self.MNEMONIC))
        a = bip39.mnemonic_to_seed(self.MNEMONIC, "")
        b = bip39.mnemonic_to_seed(self.MNEMONIC, "breathe")
        self.assertNotEqual(a, b)

    def test_passphrase_list_defaults_to_single(self):
        cfg = SearchConfig(pool=[], target_hash160=bytes(20))
        self.assertEqual(cfg.passphrase_list(), ("",))
        cfg2 = SearchConfig(pool=[], target_hash160=bytes(20), passphrase="x")
        self.assertEqual(cfg2.passphrase_list(), ("x",))
        cfg3 = SearchConfig(pool=[], target_hash160=bytes(20), passphrases=("a", "b"))
        self.assertEqual(cfg3.passphrase_list(), ("a", "b"))

    def test_finds_target_only_reachable_via_passphrase(self):
        target = self._planted("breathe")
        cfg = SearchConfig(pool=self.MNEMONIC.split(), target_hash160=target,
                           workers=2, prefix_len=1,
                           schemes=tuple(derive.resolve_schemes(["bip44"], depth=1)),
                           passphrases=("", "tuesday", "breathe"))
        hits, _ = run_search(cfg, Checkpoint(None))
        self.assertTrue(hits)
        self.assertEqual(hits[0].phrase, self.MNEMONIC)
        self.assertIn("breathe", hits[0].detail)

    def test_misses_when_the_right_passphrase_is_absent(self):
        """Guards against the passphrase being ignored and matching anyway."""
        target = self._planted("breathe")
        cfg = SearchConfig(pool=self.MNEMONIC.split(), target_hash160=target,
                           workers=2, prefix_len=1, limit=40_000,
                           schemes=tuple(derive.resolve_schemes(["bip44"], depth=1)),
                           passphrases=("", "tuesday"))
        hits, prog = run_search(cfg, Checkpoint(None))
        self.assertEqual(hits, [])
        self.assertGreater(prog.tested, 0)

    def test_electrum_passphrase_also_applies(self):
        seed = TestElectrum.STANDARD
        a = next(h for h, c, i in electrum.iter_hash160s(seed, "", depth=1)
                 if c == "electrum-receiving" and i == 0)
        b = next(h for h, c, i in electrum.iter_hash160s(seed, "breathe", depth=1)
                 if c == "electrum-receiving" and i == 0)
        self.assertNotEqual(a, b)


class TestPositionMap(unittest.TestCase):
    """The word-plus-number construction (ANALYSIS.md)."""

    def test_confirmed_assignments(self):
        got = {a.position: sorted(a.words) for a in positions.CONFIRMED}
        self.assertEqual(got, {1: ["subject"], 3: ["tower"], 13: ["moon"]})
        for a in positions.CONFIRMED:
            self.assertEqual(a.evidence, positions.Evidence.CONFIRMED)

    def test_every_assignment_uses_real_words(self):
        for a in positions.CONFIRMED + positions.PROPOSED:
            for w in a.words:
                self.assertTrue(is_valid(w), f"{w} at position {a.position}")

    def test_position_21_forces_a_long_mnemonic(self):
        """The hour hand gives 21, so 12 words is impossible."""
        self.assertIn(21, positions.ORPHAN_NUMBERS)
        self.assertEqual(positions.VIABLE_LENGTHS, (21, 24))
        for length in positions.VIABLE_LENGTHS:
            self.assertIn(length, bip39.LENGTHS)
        self.assertNotIn(12, positions.VIABLE_LENGTHS)

    def test_map_is_not_yet_searchable(self):
        """Honest bookkeeping: even with every proposed clue, it is hopeless."""
        for length in (21, 24):
            for inc in (False, True):
                pm = positions.build(length, include_proposed=inc)
                self.assertFalse(pm.searchable())
                self.assertIn("NOT searchable", pm.verdict())

    def test_searchable_threshold(self):
        pm = positions.PositionMap(length=24)
        for i in range(1, 25):
            pm.slots[i] = frozenset({"moon"})
        self.assertTrue(pm.searchable())
        for i in range(1, 5):
            del pm.slots[i]
        self.assertFalse(pm.searchable(), "4 unresolved must not be searchable")

    def test_combinations_counts_alternatives(self):
        pm = positions.PositionMap(length=3)
        pm.slots[1] = frozenset({"moon"})
        pm.slots[2] = frozenset({"black", "day"})
        pm.slots[3] = frozenset({"tower"})
        self.assertEqual(pm.combinations(), 2)
        del pm.slots[3]
        self.assertEqual(pm.combinations(vocabulary=2048), 2 * 2048)

    def test_clock_mechanism_only_yields_odd_positions(self):
        """Consecutive numerals sum to 2n+1, so evens need another mechanism."""
        reachable = sorted(positions.midpoint_bearings())
        self.assertEqual(reachable, [3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23])
        self.assertTrue(all(p % 2 == 1 for p in reachable))

    def test_numeral_bearings_are_evenly_spaced(self):
        """~30 degree steps, with the scatter of hand-drawn numerals.

        Measured steps run 28.0 to 32.0 degrees. That scatter is the noise
        floor for every midpoint prediction, which is why a 1.3 degree match
        counts as a hit and an 8.7 degree one does not.
        """
        b = positions.NUMERAL_BEARING
        self.assertEqual(len(b), 12)
        steps = []
        for n in range(1, 13):
            m = n + 1 if n < 12 else 1
            steps.append((b[m] - b[n]) % 360)
        self.assertAlmostEqual(sum(steps), 360.0, delta=0.5)
        for n, step in zip(range(1, 13), steps):
            self.assertAlmostEqual(step, 30.0, delta=2.5, msg=f"numeral {n}")

    def test_measured_numerals_beat_interpolated_ones(self):
        """12, 1, 2, 3, 8, 9, 10, 11 are measured; 4-7 are interpolated.

        Midpoints built from two measured numerals (moon at 12+1) are firmer
        than ones involving an interpolated numeral (eye at 4+5).
        """
        measured = {12, 1, 2, 3, 8, 9, 10, 11}
        self.assertEqual(set(positions.NUMERAL_BEARING) - measured, {4, 5, 6, 7})

    def test_eye_sits_on_the_four_five_midpoint(self):
        """The eye really is on the ray - but see the chance test below."""
        got = positions.position_at(648, 843)
        self.assertIsNotNone(got)
        pos, n, m, _bearing, err = got
        self.assertEqual((pos, {n, m}), (9, {4, 5}))
        self.assertLess(err, 3.0)

    def test_eye_is_now_weak(self):
        """Four objects share its ray, and the Needle is nearer than the eye."""
        eye = positions.EYE
        self.assertEqual(eye.position, 9)
        self.assertEqual(eye.evidence, positions.Evidence.WEAK)
        self.assertNotIn(9, {a.position for a in positions.CONFIRMED})
        self.assertEqual(positions.PROPOSED_STRONG, [])

    def test_food_and_real_have_no_number(self):
        """Searched and empty - recorded so the search is not repeated."""
        self.assertEqual(sorted(positions.MARKED_WITHOUT_NUMBER), ["food", "real"])
        for word, why in positions.MARKED_WITHOUT_NUMBER.items():
            self.assertTrue(is_valid(word), f"{word} should still be BIP-39")
            self.assertIn("no adjacent numeral", why)
        placed = {w for a in positions.CONFIRMED for w in a.words}
        for w in positions.MARKED_WITHOUT_NUMBER:
            self.assertNotIn(w, placed, f"{w} must not be placed without a number")

    def test_mechanism_capacity_is_bounded_at_four(self):
        """A clock has three hands. That is a hard ceiling, not a search gap."""
        c = positions.MECHANISM_CAPACITY
        self.assertEqual(c["clock_hands"], 3)
        self.assertEqual(c["explicit_adjacent_numeral"], 1)
        self.assertEqual(c["total_reachable"],
                         c["clock_hands"] + c["explicit_adjacent_numeral"])
        self.assertLess(c["total_reachable"], c["needed_for_24"])
        # and the confirmed map never exceeds that ceiling
        pm = positions.build(24)
        self.assertLessEqual(len(pm.slots) + len(positions.ORPHAN_NUMBERS),
                             c["total_reachable"])

    def test_ray_matching_refutation_is_recorded(self):
        """The survey that closed the 'object on a ray names a word' idea."""
        r = positions.RAY_MATCHING_REFUTED
        self.assertEqual(r["objects_surveyed"], 32)
        self.assertGreater(r["max_objects_on_one_position"], 1)
        self.assertGreater(r["positions_with_multiple_objects"], 1)
        # a real effect holds across thresholds; this one does not
        ps = list(r["p_values_by_tolerance"].values())
        self.assertGreater(max(ps), 0.05)
        self.assertLess(min(ps), 0.05)

    def test_only_confirmed_mechanisms_remain(self):
        """Three clock hands plus the plinth. Nothing else is established."""
        got = {a.position for a in positions.CONFIRMED}
        self.assertEqual(got, {1, 3, 13})
        self.assertIn(21, positions.ORPHAN_NUMBERS)

    def test_chance_probability(self):
        """Default is now the full 24-ray model: 15 deg spacing."""
        self.assertAlmostEqual(positions.chance_probability(1.3), 2*1.3/15, places=6)
        self.assertAlmostEqual(positions.chance_probability(7.5), 1.0, places=6)
        self.assertGreater(positions.chance_probability(1.3), 0.17)

    def test_even_positions_come_from_on_numeral_rays(self):
        even = sorted(positions.numeral_rays())
        self.assertEqual(even, [4, 6, 8, 10, 12, 14, 16, 18, 20, 22])
        self.assertTrue(all(p % 2 == 0 for p in even))

    def test_both_alignments_cover_3_to_23_with_no_gaps(self):
        """One rule, two alignments: between numerals (odd), on one (even)."""
        got = sorted(positions.all_rays())
        self.assertEqual(got, list(range(3, 24)))

    def test_clock_cannot_reach_1_2_or_24(self):
        reach = set(positions.all_rays())
        for p in positions.CLOCK_CANNOT_REACH:
            self.assertNotIn(p, reach)
        self.assertEqual(positions.CLOCK_CANNOT_REACH, (1, 2, 24))

    def test_self_matching_axes_are_the_middle_three(self):
        self.assertEqual(sorted(positions.SELF_MATCHING_AXES), [12, 13, 14])

    def test_more_rays_means_a_worse_false_positive_rate(self):
        """Completing the mechanism weakens every single-object match."""
        self.assertAlmostEqual(positions.chance_probability(1.3, n_rays=12), 2*1.3/30, places=6)
        self.assertAlmostEqual(positions.chance_probability(1.3, n_rays=24), 2*1.3/15, places=6)
        self.assertGreater(positions.chance_probability(1.3, n_rays=24),
                           positions.chance_probability(1.3, n_rays=12))

    def test_map_refuses_to_enumerate_unresolved_positions(self):
        """A negative from guessed fillers is not a result."""
        pm = positions.build(24, include_proposed=True)
        ok, why = pm.enumerable()
        self.assertFalse(ok)
        self.assertIn("guesses", why)

    def test_json_round_trip_preserves_confidence(self):
        pm = positions.build(24, include_strong=True)
        d = pm.to_dict()
        self.assertEqual(d["phrase_length"], 24)
        self.assertEqual(d["positions"]["13"]["candidates"], ["moon"])
        self.assertEqual(d["positions"]["13"]["confidence"], "confirmed")
        # 9 lost its promotion when four objects turned up on the same ray
        self.assertEqual(d["positions"]["9"]["confidence"], "unresolved")
        self.assertEqual(d["positions"]["9"]["candidates"], [])
        self.assertEqual(d["positions"]["2"]["candidates"], [])
        self.assertEqual(d["positions"]["2"]["confidence"], "unresolved")
        self.assertTrue(d["positions"]["13"]["basis"])
        back = positions.PositionMap.from_dict(d)
        self.assertEqual(back.slots, pm.slots)
        self.assertEqual(back.length, pm.length)

        # a weak assignment still round-trips with its confidence intact
        weak = positions.build(24, include_proposed=True).to_dict()
        self.assertEqual(weak["positions"]["9"]["confidence"], "weak")
        self.assertEqual(weak["positions"]["9"]["candidates"], ["eye"])
        self.assertEqual(
            positions.PositionMap.from_dict(weak).provenance[9].evidence,
            positions.Evidence.WEAK)

    def test_unclaimed_axes_recorded(self):
        """Traced and found empty - recorded so nobody re-traces them."""
        self.assertEqual(sorted(positions.UNCLAIMED_AXES),
                         [(5, 17), (7, 19), (11, 23)])
        for (a, b), (ba, bb, note) in positions.UNCLAIMED_AXES.items():
            self.assertAlmostEqual(abs(ba - bb), 180.0, delta=1.5)
            self.assertTrue(note)

    def test_position_at_rejects_a_point_off_every_ray(self):
        """With both alignments live, only a quarter-step misses everything.

        Numerals are themselves rays now (numeral 1 -> 12+2 = 14), so the
        genuinely empty bearings sit halfway between a numeral and a midpoint.
        """
        import math
        cx, cy = positions.CLOCK_CENTRE
        gap = (positions.NUMERAL_BEARING[3] + 32.6) / 2  # numeral 3 <-> midpoint(3,4)
        th = math.radians(gap)
        x, y = cx + math.sin(th) * 150, cy - math.cos(th) * 150
        self.assertIsNone(positions.position_at(x, y))
        # ...and with the even alignment switched off, a numeral is empty again
        th1 = math.radians(positions.NUMERAL_BEARING[1])
        x1, y1 = cx + math.sin(th1) * 150, cy - math.cos(th1) * 150
        self.assertIsNone(positions.position_at(x1, y1, include_even=False))
        self.assertIsNotNone(positions.position_at(x1, y1, include_even=True))

    def test_bearing_of_is_compass_oriented(self):
        cx, cy = positions.CLOCK_CENTRE
        self.assertAlmostEqual(positions.bearing_of(cx, cy - 100), 0.0, delta=0.01)
        self.assertAlmostEqual(positions.bearing_of(cx + 100, cy), 90.0, delta=0.01)
        self.assertAlmostEqual(positions.bearing_of(cx, cy + 100), 180.0, delta=0.01)

    def test_rejects_non_bip39_word(self):
        with self.assertRaises(ValueError):
            positions.Assignment(1, frozenset({"breathe"}),
                                 positions.Evidence.WEAK, "x")


class TestExtractionHypothesis(unittest.TestCase):
    """Do 1, 3, 13, 21 index text instead of mnemonic positions? No."""

    def test_corpus_is_real_artwork_text(self):
        from puzzle import extraction as ex
        self.assertGreaterEqual(len(ex.CORPUS), 12)
        for name, (text, prov) in ex.CORPUS.items():
            self.assertTrue(text.strip(), name)
            self.assertTrue(prov.strip(), f"{name} needs provenance")

    def test_subject_is_not_word_one_of_the_amendment(self):
        """The decisive case: a number and a word marked in one passage."""
        from puzzle import extraction as ex
        words = ex.CORPUS["amendment"][0].split()
        self.assertEqual(words.index("subject") + 1, 29)
        self.assertNotEqual(words[0].lower(), "subject")

    def test_no_extraction_yields_all_bip39(self):
        """A seed phrase is all BIP-39; no convention produces that."""
        from puzzle import extraction as ex
        res = ex.sweep()
        self.assertTrue(res)
        for r in res:
            self.assertLess(r.bip39_hits, len(r.extracted),
                            f"{r.passage}/{r.unit} unexpectedly all-BIP-39")

    def test_null_model_is_nonzero(self):
        """Without a null the sweep would be meaningless."""
        from puzzle import extraction as ex
        n = ex.null_rate(ex.CORPUS["amendment"][0], "word", 4)
        self.assertGreater(n, 0.0)
        self.assertLess(n, 1.0)

    def test_extract_rejects_out_of_range(self):
        from puzzle import extraction as ex
        self.assertIsNone(ex.extract("two words", (1, 99), "word"))

    def test_source_texts_are_quoted_by_the_artwork(self):
        """Pre-registered: only texts the artwork actually references."""
        from puzzle import extraction as ex
        self.assertGreaterEqual(len(ex.SOURCE_TEXTS), 5)
        for name, (text, prov) in ex.SOURCE_TEXTS.items():
            self.assertTrue(text.strip(), name)
            self.assertTrue(prov.strip(), f"{name} needs provenance")

    def test_no_source_convention_yields_all_bip39(self):
        from puzzle import extraction as ex
        res = ex.source_sweep()
        self.assertTrue(res)
        for r in res:
            self.assertLess(r.bip39_hits, len(r.extracted),
                            f"{r.passage}/{r.unit} unexpectedly all-BIP-39")

    def test_underdetermined_classification(self):
        """The honest stopping point, with its arithmetic pinned."""
        from puzzle import extraction as ex, positions
        u = ex.UNDERDETERMINED
        self.assertEqual(u["all_bip39_results"], 0)
        self.assertEqual(u["attempts_total"],
                         u["attempts_artwork_text"] + u["attempts_source_text"])
        self.assertEqual(u["attempts_artwork_text"], len(ex.sweep()))
        self.assertEqual(u["attempts_source_text"], len(ex.source_sweep()))
        self.assertEqual(u["confirmed_positions"], len(positions.CONFIRMED))
        self.assertEqual(u["mechanism_capacity"],
                         positions.MECHANISM_CAPACITY["total_reachable"])
        self.assertLess(u["mechanism_capacity"], u["positions_needed"])

    def test_refutations_recorded(self):
        from puzzle import extraction as ex
        self.assertEqual(sorted(ex.REFUTED),
                         ["derivation_path", "source_text_indexing",
                          "text_indexing", "wordlist_indices"])
        self.assertEqual(ex.REFUTED["source_text_indexing"]["four_of_four"], 0)
        self.assertEqual(ex.REFUTED["derivation_path"]["matches"], 0)
        self.assertEqual(ex.REFUTED["text_indexing"]["four_of_four"], 0)


class TestFourthMechanismSearch(unittest.TestCase):
    """Re-examination of the artwork for an overlooked number-bearing object."""

    IMAGE = os.environ.get("PUZZLE_IMAGE", "puzzle.png")

    def test_census_covers_the_three_newly_found_numerals(self):
        from puzzle import positions
        new = [k for k, v in positions.NUMERAL_CENSUS.items() if v.get("new")]
        self.assertEqual(sorted(new),
                         ["election_date", "emancipation_range", "hoodie_date"])
        for entry in positions.NUMERAL_CENSUS.values():
            self.assertIn("role", entry, "every numeral needs a stated role")

    def test_new_numerals_are_not_promoted_to_assignments(self):
        """Catalogued is not confirmed. Nothing here may reach CONFIRMED."""
        from puzzle import positions
        confirmed = {w for a in positions.CONFIRMED for w in a.words}
        self.assertEqual(confirmed, {"subject", "tower", "moon"})
        self.assertEqual(positions.DATES_NOT_A_MECHANISM["underlined"], 0)
        self.assertEqual(positions.DATES_NOT_A_MECHANISM["on_a_pointer"], 0)

    def test_dates_overflow_a_24_position_phrase(self):
        """The hard check on the date reading, recomputed not asserted."""
        from puzzle import positions
        for spec in ("05.25.20", "11.03.20"):
            parts = [int(x) for x in spec.split(".")]
            over = [n for n in parts if not 1 <= n <= 24]
            recorded_in_range = any(
                spec in s for s in positions.DATES_NOT_A_MECHANISM["in_range"])
            self.assertEqual(not over, recorded_in_range,
                             f"{spec}: range check disagrees with the record")
        self.assertNotIn(25, range(1, 25))

    def test_capacity_bound_is_unchanged_by_the_re_examination(self):
        from puzzle import positions
        cap = positions.MECHANISM_CAPACITY
        self.assertEqual(cap["clock_hands"], 3)
        self.assertEqual(cap["explicit_adjacent_numeral"], 1)
        self.assertEqual(cap["total_reachable"], 4)

    def test_clock_has_exactly_three_hands(self):
        """Measured from the image, not argued from 'clocks have three hands'."""
        if not os.path.exists(self.IMAGE):
            self.skipTest(f"artwork not present at {self.IMAGE}")
        from puzzle import positions
        got = positions.scan_hands(self.IMAGE)
        self.assertEqual(len(got["hands"]), 3,
                         "a fourth hand would break the capacity bound")
        bearings = sorted(round(h["bearing"], 1) for h in got["hands"])
        self.assertEqual(bearings, sorted(positions.CLOCK_HAND_CENSUS["hands"]))
        self.assertEqual(len(got["peaks"]),
                         positions.CLOCK_HAND_CENSUS["peaks_above_1_7x_mean"])

    def test_the_three_hands_land_on_the_recorded_positions(self):
        if not os.path.exists(self.IMAGE):
            self.skipTest(f"artwork not present at {self.IMAGE}")
        from puzzle import positions
        got = positions.scan_hands(self.IMAGE)
        self.assertEqual({h["position"] for h in got["hands"]}, {3, 13, 21})


class TestRune2Verification(unittest.TestCase):
    """Rune 2 captions the clock. Read it with the alphabet from rune 4."""

    IMAGE = os.environ.get("PUZZLE_IMAGE", "puzzle.png")

    def setUp(self):
        if not os.path.exists(self.IMAGE):
            self.skipTest(f"artwork not present at {self.IMAGE}")

    def test_word_structure_matches_the_crib(self):
        from puzzle.runes import verify_rune2
        r = verify_rune2(self.IMAGE)
        self.assertEqual(r["word_lengths"], r["crib_word_lengths"])

    def test_crib_letter_wins_at_most_known_positions(self):
        """The decisive check, recomputed from the artwork."""
        from puzzle.runes import verify_rune2
        r = verify_rune2(self.IMAGE)
        self.assertGreaterEqual(r["top_matches"], 8)
        self.assertEqual(r["known_positions"], 10)
        self.assertEqual(r["alphabet_size"], 21)

    def test_clean_positions_sit_at_the_same_letter_baseline(self):
        from puzzle.runes import verify_rune2
        r = verify_rune2(self.IMAGE)
        self.assertLess(r["mean_distance_clean_positions"],
                        r["same_letter_baseline"] * 1.1)
        self.assertLess(r["mean_distance_clean_positions"],
                        r["different_letter_baseline"] * 0.5)

    def test_the_two_misses_are_declared_unreliable(self):
        """Positions 5 and 6 are a segmentation artefact and must be flagged."""
        from puzzle.runes import verify_rune2
        r = verify_rune2(self.IMAGE)
        misses = [e for e in r["letters"]
                  if "crib_distance" in e and e["nearest"] != e["crib"]]
        for e in misses:
            self.assertFalse(e["reliable"],
                             f"position {e['pos']} missed but is not flagged")

    def test_significance_recomputed_not_trusted(self):
        from math import comb
        from puzzle.runes import verify_rune2, RUNE2_VERIFICATION
        r = verify_rune2(self.IMAGE)
        n, k, a = r["known_positions"], r["top_matches"], r["alphabet_size"]
        p = sum(comb(n, j) * (1 / a) ** j * (1 - 1 / a) ** (n - j)
                for j in range(k, n + 1))
        self.assertLess(p, 1e-8)
        self.assertAlmostEqual(p, RUNE2_VERIFICATION["p_value"], places=11)

    def test_runes_supply_no_new_mechanism(self):
        from puzzle import positions
        from puzzle.runes import RUNES_AS_MECHANISM_SOURCE
        self.assertEqual(RUNES_AS_MECHANISM_SOURCE["new_mechanisms_found"], 0)
        self.assertEqual(positions.MECHANISM_CAPACITY["total_reachable"], 4)


class TestAuthorship(unittest.TestCase):
    """Provenance: who signed the artwork, who published it, what is unproven."""

    IMAGE = os.environ.get("PUZZLE_IMAGE", "puzzle.png")

    def test_attribution_is_recorded_as_unsupported(self):
        """The community names Charly Palmer. The record must not adopt it."""
        import forensics
        a = forensics.ATTRIBUTION
        self.assertTrue(a["verdict"].startswith("unsupported"))
        self.assertGreaterEqual(len(a["evidence_against"]), 3)
        self.assertNotEqual(a["signature"], a["community_guess"],
                            "a signature is not an identification")

    def test_signature_boxes_lie_inside_the_artwork(self):
        import forensics
        w, h = forensics.PROVENANCE["size"]
        for name, sig in forensics.SIGNATURES.items():
            x0, y0, x1, y1 = sig["box"]
            self.assertTrue(0 <= x0 < x1 <= w, name)
            self.assertTrue(0 <= y0 < y1 <= h, name)

    def test_signature_regions_carry_ink(self):
        """Both signatures must be real drawn content, not a claim."""
        if not os.path.exists(self.IMAGE):
            self.skipTest(f"artwork not present at {self.IMAGE}")
        import numpy as np
        import forensics
        from PIL import Image, ImageOps, ImageChops, ImageFilter
        im = Image.open(self.IMAGE).convert("RGB")
        for name, sig in forensics.SIGNATURES.items():
            g = ImageOps.grayscale(im.crop(sig["box"]))
            hp = ImageChops.subtract(g.filter(ImageFilter.GaussianBlur(3)), g)
            a = np.asarray(hp, dtype=float)
            self.assertGreater(a.max(), 12,
                               f"{name}: no ink found where a signature is recorded")

    def test_publication_predates_nothing_impossible(self):
        """The wallet must be funded before the puzzle was published."""
        import forensics
        p = forensics.PUBLICATION
        self.assertLess(p["wallet_created"], p["wallet_funded"])
        self.assertLess(p["wallet_funded"], p["posted"])

    def test_no_sibling_puzzle_found(self):
        import forensics
        self.assertEqual(forensics.NO_SIBLING_PUZZLE["found"], 0)
        self.assertGreaterEqual(len(forensics.NO_SIBLING_PUZZLE["searched"]), 4)

    def test_idiom_note_does_not_refute_or_endorse_black(self):
        """The phrase is idiomatic; the record must claim neither more nor less."""
        import forensics
        from puzzle import positions
        note = forensics.IDIOM_NOTE
        self.assertIn("rainy day", note["idiomatic"])
        self.assertIn("pun", note["assessment"])
        weak = {w for a in positions.PROPOSED for w in a.words
                if a.evidence is positions.Evidence.WEAK}
        self.assertIn("black", weak, "'black' must stay unpromoted")


class TestWordSupplySweep(unittest.TestCase):
    """The sweep for a sixth marked word, and the honesty of its record."""

    def test_surface_count_is_recomputed_not_asserted(self):
        from puzzle import positions
        self.assertEqual(len(positions.SURFACE_SWEEP["surfaces_examined"]),
                         positions.WORD_SUPPLY["surfaces_swept"])

    def test_failed_detector_is_recorded_as_discarded(self):
        """A detector missing its controls must not be cited as a negative."""
        from puzzle import positions
        d = positions.DETECTOR_FAILED
        self.assertLess(d["positive_controls_recovered"],
                        d["positive_controls_total"])
        self.assertTrue(d["verdict"].startswith("discarded"))

    def test_sweep_found_nothing_and_says_so(self):
        from puzzle import positions
        self.assertEqual(positions.SURFACE_SWEEP["new_words_found"], 0)
        self.assertEqual(positions.WORD_SUPPLY["new_words"], 0)
        self.assertEqual(positions.WORD_SUPPLY["marked_words"],
                         len(positions.MARKED_WITHOUT_NUMBER) + len(positions.CONFIRMED))

    def test_word_supply_still_cannot_seed_a_search(self):
        """The point of the sweep: five words is short of any phrase length."""
        from puzzle import positions
        w = positions.WORD_SUPPLY
        self.assertLess(w["marked_words"], w["words_needed_min"])


class TestRune3Alphabet(unittest.TestCase):
    """Which alphabet does rune 3 use? Four candidates, each with a control."""

    IMAGE = os.environ.get("PUZZLE_IMAGE", "puzzle.png")

    def setUp(self):
        if not os.path.exists(self.IMAGE):
            self.skipTest(f"artwork not present at {self.IMAGE}")
        from PIL import ImageOps
        from puzzle import runes
        from puzzle.runes import load_rune4, RUNE4_SEPARATORS, signature
        self.runes = runes
        self.sigs3 = runes.strip_signatures(
            self.IMAGE, runes.RUNE3_BOX, runes.RUNE3_THRESHOLD,
            transform=ImageOps.mirror)
        mask, glyphs, _ = load_rune4(self.IMAGE)
        self.control = [signature(mask, glyphs[i]) for i in range(48)
                        if i not in RUNE4_SEPARATORS]

    def test_segmentation_is_seven_glyphs(self):
        self.assertEqual(len(self.sigs3), 7)
        self.assertEqual(len(self.runes.RUNE3_INVENTORY), 7)

    def test_segmentation_is_stable_across_thresholds(self):
        """A count that moves with the threshold is not a glyph count."""
        from PIL import ImageOps
        for t in (80, 90, 100):
            got = self.runes.strip_signatures(
                self.IMAGE, self.runes.RUNE3_BOX, t, transform=ImageOps.mirror)
            self.assertEqual(len(got), 7, f"threshold {t} gave {len(got)}")

    def test_not_the_artwork_own_alphabet(self):
        """Rune 2, a verified true match, scores far better by the same pipeline."""
        alphabet = self.runes.rune4_alphabet(self.IMAGE)
        r3 = self.runes.compare_to_reference(self.sigs3, alphabet, self.control)
        s2 = self.runes.strip_signatures(
            self.IMAGE, self.runes.RUNE2_BOX, self.runes.RUNE2_THRESHOLD)
        r2 = self.runes.compare_to_reference(s2, alphabet, self.control)
        self.assertGreater(r3["mean"], r2["mean"] + 8,
                           "rune 3 must be clearly worse than a true match")
        self.assertGreater(r3["mean"], 40)

    def test_control_is_what_makes_a_score_readable(self):
        """A mean distance with no control is uninterpretable; assert we have one."""
        alphabet = self.runes.rune4_alphabet(self.IMAGE)
        r = self.runes.compare_to_reference(self.sigs3, alphabet, self.control)
        self.assertIn("control_mean", r)
        self.assertIn("control_min", r)
        self.assertLess(r["control_min"], 30,
                        "accidental close matches happen; the record must show it")

    def test_record_marks_every_exclusion_withdrawn(self):
        """These verdicts were produced by an instrument that fails its own
        positive control. The record must say so, not quietly keep them."""
        rec = self.runes.RUNE3_ALPHABET_SEARCH
        self.assertTrue(rec["verdict"].startswith("WITHDRAWN"))
        self.assertEqual(len(rec["tested"]), 4)
        for name, entry in rec["tested"].items():
            self.assertIn("control", entry, f"{name} recorded without a control")
        w = self.runes.RUNE3_SEARCH_WITHDRAWN
        for cand in ("dscript", "latin", "cyrillic", "aurebesh", "sga",
                     "artwork_rune_alphabet"):
            self.assertIn(cand, w["withdrawn"])

    def test_aurebesh_and_sga_are_refuted_by_their_controls(self):
        """Recomputed from vendored fingerprints, not trusted as constants."""
        from PIL import ImageOps
        R = self.runes
        s2 = R.strip_signatures(self.IMAGE, R.RUNE2_BOX, R.RUNE2_THRESHOLD)
        for name in ("aurebesh", "sga"):
            ref = R.load_reference_alphabet(name)
            best = min(
                R.compare_to_reference(
                    R.strip_signatures(self.IMAGE, R.RUNE3_BOX,
                                       R.RUNE3_THRESHOLD, transform=tf),
                    ref, self.control)["mean"]
                for tf in (None, ImageOps.mirror,
                           lambda x: x.rotate(180), ImageOps.flip))
            ctrl = R.compare_to_reference([], ref, self.control)["control_mean"]
            r2 = R.compare_to_reference(s2, ref, self.control)["mean"]
            self.assertGreater(best, ctrl * 0.95,
                               f"{name}: rune 3 must not beat its control")
            self.assertLess(abs(best - r2), 8,
                            f"{name}: rune 3 must sit in the same noise band "
                            "as an unrelated strip")

    def test_reference_alphabets_are_internally_discriminable(self):
        """A reference that cannot tell its own letters apart proves nothing."""
        from puzzle.runes import distance
        for name, expected in (("aurebesh", 34), ("sga", 26)):
            ref = self.runes.load_reference_alphabet(name)
            self.assertEqual(len(ref), expected)
            keys = sorted(ref)
            ds = [distance(ref[a], ref[b])
                  for i, a in enumerate(keys) for b in keys[i+1:]]
            self.assertGreater(sum(ds) / len(ds), 50,
                               f"{name} letters are not well separated")

    def test_weak_positive_is_recorded_with_its_caveats(self):
        """The N/E match is thin and post-hoc; the record must say so."""
        wp = self.runes.RUNE3_ALPHABET_SEARCH["weak_positive"]
        self.assertGreater(wp["p_value"], 0.01, "not strong enough to claim")
        self.assertIn("post-hoc", wp["caveats"])


class TestDscriptHypothesis(unittest.TestCase):
    """Are the rune strips Dscript? If so its base-100 numerals would read
    out rune 4's trailing 'number X'."""

    IMAGE = os.environ.get("PUZZLE_IMAGE", "puzzle.png")

    def test_alphabet_carries_cyrillic_only_letters(self):
        """Dscript would transliterate; a transliteration has no soft sign."""
        from puzzle.runes import DSCRIPT_COMPARISON, RUNE4_CRIB
        recorded = set(DSCRIPT_COMPARISON["cyrillic_only_letters"])
        present = {c for c in recorded if c in RUNE4_CRIB}
        self.assertGreaterEqual(len(present), 5,
                                "the crib must actually contain the letters "
                                "the record claims Dscript cannot write")
        self.assertTrue(recorded >= {"Ь", "Ы", "Ё"})
        self.assertTrue(DSCRIPT_COMPARISON["verdict"].startswith("refuted"))

    def test_marked_letter_sits_inside_its_base_letters_spread(self):
        """Y-breve corroboration: measured, not asserted.

        The crib alignment never used diacritics, so this is a prediction it
        could not have fitted.
        """
        if not os.path.exists(self.IMAGE):
            self.skipTest(f"artwork not present at {self.IMAGE}")
        from puzzle.runes import diacritic_pairs
        d = diacritic_pairs(self.IMAGE)
        pair = d["И_Й"]
        self.assertLessEqual(pair["de_dotted"], max(pair["base_intra"]),
                             "Й must fall inside И's own instance spread")
        self.assertLess(pair["de_dotted"], d["baseline"] * 0.6)

    def test_de_dotting_does_not_move_the_uninformative_pair(self):
        """Recorded honestly: one pair corroborates, one does not."""
        if not os.path.exists(self.IMAGE):
            self.skipTest(f"artwork not present at {self.IMAGE}")
        from puzzle.runes import diacritic_pairs, DIACRITIC_EVIDENCE
        d = diacritic_pairs(self.IMAGE)
        self.assertEqual(d["Е_Ё"]["as_drawn"],
                         DIACRITIC_EVIDENCE["Е_vs_Ё"]["as_drawn"])
        self.assertGreater(d["Е_Ё"]["de_dotted"], d["baseline"] * 0.9,
                           "the record must not overstate this pair")

    def test_trailing_glyph_has_no_core_circle(self):
        """A Dscript base-100 numeral is a circle plus directional strokes."""
        if not os.path.exists(self.IMAGE):
            self.skipTest(f"artwork not present at {self.IMAGE}")
        from puzzle.runes import load_rune4, _components
        mask, glyphs, _ = load_rune4(self.IMAGE)
        g = glyphs[48]
        comps = _components(mask[g.y0:g.y1 + 1, g.x0:g.x1 + 1])
        self.assertEqual(len(comps), 1,
                         "a base-100 numeral would not be one bare stroke group")

    def test_dscript_finding_does_not_add_a_position(self):
        """The hypothesis was a route to a fourth number. It did not supply one."""
        from puzzle import positions
        self.assertEqual(positions.MECHANISM_CAPACITY["total_reachable"], 4)
        self.assertEqual(len(positions.CONFIRMED), 3)


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


class TestReferenceReadings(unittest.TestCase):
    """The date and numbered-source readings of 1, 3, 13, 21."""

    @classmethod
    def setUpClass(cls):
        from puzzle import references
        cls.ref = references

    def test_anchor_indices_match_the_wordlist(self):
        """Guards the whole module: every sweep is measured against these."""
        self.assertEqual(self.ref.ANCHOR_INDICES, {1: 1727, 3: 1841, 13: 1148})
        for n, w in self.ref.ANCHORS.items():
            self.assertEqual(self.ref._W[self.ref.ANCHOR_INDICES[n]], w)

    def test_affine_sweep_is_complete_and_refutes(self):
        sweep = self.ref.affine_sweep()
        self.assertEqual(sweep.tested, 2048, "must cover the whole affine family")
        self.assertEqual(sweep.hits, [])
        self.assertTrue(sweep.refuted)

    def test_affine_sweep_finds_a_fit_when_one_exists(self):
        """Positive control. A test that can only ever refute proves nothing."""
        ref = self.ref
        a, b = 37, 900
        planted = {n: (a * n + b) % 2048 for n in (1, 3, 13)}
        real = ref.ANCHOR_INDICES
        try:
            ref.ANCHOR_INDICES = planted
            sweep = ref.affine_sweep()
            self.assertIn((a, b), sweep.hits,
                          "the sweep must recover a scheme that really is there")
        finally:
            ref.ANCHOR_INDICES = real
        self.assertEqual(ref.affine_sweep().hits, [], "anchors must be restored")

    def test_affine_near_miss_is_exactly_two_schemes_naming_coin(self):
        """Pin the seductive wrong answer so it stays refuted in writing."""
        near = self.ref.affine_near_miss()
        self.assertEqual(len(near), 2)
        self.assertEqual({got for _, _, got in near}, {"coin"})

    def test_date_sweep_refutes_over_the_recorded_space(self):
        sweep = self.ref.date_sweep()
        self.assertEqual(sweep.hits, [])
        recorded = int(self.ref.REFUTED["date_reference"]["tested"]
                       .split()[0].replace(",", ""))
        self.assertEqual(sweep.tested, recorded,
                         "recompute the count; do not trust the constant")

    def test_date_sweep_finds_a_planted_date_scheme(self):
        """Positive control for the date family."""
        ref = self.ref
        y, m, how, base = 1900, 6, "MMDD", 0
        planted = {n: ref.date_index(y, m, n, how) - base for n in (1, 3, 13)}
        real = ref.ANCHOR_INDICES
        try:
            ref.ANCHOR_INDICES = planted
            sweep = ref.date_sweep(years=range(1899, 1902))
            self.assertIn(("day=n", y, m, how, base), sweep.hits)
        finally:
            ref.ANCHOR_INDICES = real

    def test_combined_date_names_no_marked_word(self):
        sweep = self.ref.combined_date_sweep()
        self.assertEqual(sweep.hits, [])
        self.assertGreater(sweep.tested, 500, "the reading space must be real")

    def test_chance_floor_is_reported_and_nonzero_for_the_big_sweep(self):
        """A sweep big enough to find something by luck must say so."""
        big = self.ref.date_sweep()
        self.assertGreater(big.expected_by_chance, 0.1,
                           "this sweep is at the noise floor; the module must "
                           "record that a single hit would not be evidence")
        self.assertLess(self.ref.affine_sweep().expected_by_chance, 0.001)

    def test_amendment_vocabulary_claim_holds_on_the_vendored_text(self):
        """Offline slice of the primary-source check: the 13th Amendment."""
        from puzzle import extraction
        text = extraction.SOURCE_TEXTS["amendment_full"][0].lower()
        self.assertIn("subject", text)
        self.assertNotIn("tower", text)
        self.assertNotIn("moon", text)
        recorded = self.ref.SOURCE_VOCABULARY["us_amendments"]
        self.assertIn(13, recorded["subject_appears_in"])
        self.assertNotIn(1, recorded["subject_appears_in"],
                         "f(1)=subject is what the Amendment reading needs")

    def test_recorded_total_matches_the_sweeps(self):
        """extraction.UNDERDETERMINED must be recomputed, not trusted."""
        from puzzle import extraction
        total = sum(s.tested for s in self.ref.run_all().values())
        self.assertEqual(
            total, extraction.UNDERDETERMINED["reference_schemes_tested"])
        self.assertEqual(
            0, extraction.UNDERDETERMINED["reference_schemes_fitting_anchors"])

    def test_word_at_rejects_out_of_range(self):
        self.assertIsNone(self.ref.word_at(2048))
        self.assertIsNone(self.ref.word_at(-1))
        self.assertEqual(self.ref.word_at(0), "abandon")




class TestRune3Decoded(unittest.TestCase):
    """Rune 3 reads TUESDAY in the Gravity Falls 'strange symbols' cipher."""

    IMAGE = os.environ.get("PUZZLE_IMAGE", "puzzle.png")
    CHART = "/home/user/homelessphd/blm_0.2btc/pictures/11_1.png"

    def setUp(self):
        from puzzle import runes
        self.runes = runes

    def test_decode_is_recorded(self):
        d = self.runes.RUNE3_DECODE
        self.assertEqual(d["reads"], "TUESDAY")
        self.assertEqual(d["glyphs"], 7)
        self.assertIn("Gravity Falls", d["cipher"])
        self.assertIn("NOT mirrored", d["orientation"])

    def test_tuesday_is_not_a_bip39_word(self):
        """It cannot be a seed word, whatever else it is."""
        from puzzle import wordlist
        self.assertFalse(wordlist.is_valid("tuesday"))
        self.assertFalse(self.runes.RUNE3_DECODE["is_bip39"])

    def test_vendored_alphabet_has_26_letters(self):
        import numpy as np
        data = np.load(self.runes.GRAVITY_FALLS, allow_pickle=False)
        letters = "".join(str(c) for c in data["letters"])
        self.assertEqual(letters, "".join(chr(ord("A") + i) for i in range(26)))
        self.assertEqual(len(data["holes"]), 26)

    def test_hole_counts_confirm_the_reading(self):
        """Six of seven positions agree topologically; p is computed exactly."""
        if not os.path.exists(self.IMAGE):
            self.skipTest(f"artwork not present at {self.IMAGE}")
        r = self.runes.verify_rune3(self.IMAGE)
        self.assertEqual(r["glyphs"], 7)
        self.assertGreaterEqual(r["agreeing_positions"], 6)
        self.assertLess(r["p_value"], 0.01)
        self.assertLess(r["expected_agreements_by_chance"], 3)

    def test_a_wrong_word_does_not_verify(self):
        """The check must be able to fail, or it checks nothing."""
        if not os.path.exists(self.IMAGE):
            self.skipTest(f"artwork not present at {self.IMAGE}")
        good = self.runes.verify_rune3(self.IMAGE, "TUESDAY")
        for decoy in ("MONDAYS", "FRIDAYS", "SUNDAYS"):
            bad = self.runes.verify_rune3(self.IMAGE, decoy)
            self.assertLess(bad["agreeing_positions"],
                            good["agreeing_positions"],
                            f"{decoy} scored as well as TUESDAY")

    def test_extraction_from_the_chart_reproduces_the_vendored_data(self):
        """If the chart is present, the vendored descriptors must match it."""
        if not os.path.exists(self.CHART):
            self.skipTest("Gravity Falls reference chart not present")
        import numpy as np
        glyphs = self.runes.gravity_falls_alphabet(self.CHART)
        self.assertEqual(len(glyphs), 26)
        data = np.load(self.runes.GRAVITY_FALLS, allow_pickle=False)
        letters = "".join(str(c) for c in data["letters"])
        for i, ch in enumerate(letters):
            self.assertEqual(self.runes._holes(glyphs[ch], close=1),
                             int(data["holes"][i]), f"letter {ch}")

    def test_the_metric_that_excluded_six_alphabets_has_no_power(self):
        """The negative control that was missing: against known ground truth
        the 12x12 fingerprint ranks the right letter at chance."""
        w = self.runes.RUNE3_SEARCH_WITHDRAWN
        self.assertAlmostEqual(w["ground_truth_mean_rank"], 13.7, places=1)
        self.assertAlmostEqual(w["chance_mean_rank"], 13.5, places=1)
        self.assertGreater(w["ground_truth_mean_rank"], w["chance_mean_rank"])
        self.assertTrue(w["verdict"].startswith("withdrawn"))

    def test_rune4_tail_is_two_components_one_being_the_border(self):
        t = self.runes.RUNE4_TAIL
        self.assertEqual(t["glyphs_past_crib"], (48, 49))
        self.assertIn("border", t["index_49"])
        self.assertTrue(t["verdict"].startswith("unresolvable"))

    def test_capacity_bound_is_not_inflated_by_the_decode(self):
        """TUESDAY names no mechanism. The bound must stay at four."""
        from puzzle import positions
        self.assertTrue(
            self.runes.RUNES_AS_MECHANISM_SOURCE["capacity_bound_unchanged"])
        self.assertEqual(
            self.runes.RUNES_AS_MECHANISM_SOURCE["new_mechanisms_found"], 0)
        self.assertEqual(positions.MECHANISM_CAPACITY["total_reachable"], 4)


class TestRune1Decoded(unittest.TestCase):
    """Rune 1: three lines this repo long called unreadable."""

    IMAGE = os.environ.get("PUZZLE_IMAGE", "puzzle.png")

    def setUp(self):
        from puzzle import runes
        self.runes = runes

    def _image(self):
        if not os.path.exists(self.IMAGE):
            self.skipTest(f"artwork not present at {self.IMAGE}")
        return self.IMAGE

    def test_word_structure_matches_the_crib(self):
        """The alignment is settled by word lengths, before any glyph is read."""
        lines = self.runes.load_rune1(self._image())
        seps = self.runes.RUNE1_SEPARATORS
        for li, line in enumerate(lines):
            words, cur = [], 0
            for i in range(len(line)):
                if i in seps[li]:
                    words.append(cur); cur = 0
                else:
                    cur += 1
            words.append(cur)
            crib = [len(w) for w in self.runes.RUNE1_CRIB[li].split()]
            if li == 1:                       # one merged glyph, documented
                self.assertEqual(sum(words) + 1, sum(crib))
            else:
                self.assertEqual(words, crib, f"line {li + 1}")

    def test_same_letter_glyphs_cluster(self):
        r = self.runes.verify_rune1(self._image())
        self.assertLess(r["same_letter_mean"], 35)
        self.assertGreater(r["different_letter_mean"], 60)
        self.assertGreater(r["different_letter_mean"] - r["same_letter_mean"], 30)

    def test_cross_check_against_rune4_alphabet(self):
        """The strong check: the reference comes from a different strip."""
        r = self.runes.verify_rune1(self._image())
        self.assertGreaterEqual(r["cross_check_hits"], 30)
        self.assertGreaterEqual(r["cross_check_n"], 30)
        self.assertLess(r["cross_check_chance"], 3)

    def test_alphabet_extends_to_27_letters(self):
        ext = self.runes.extended_alphabet(self._image())
        self.assertEqual(len(ext), 27)
        for ch in self.runes.ALPHABET_EXTENSION["new_letters"]:
            self.assertIn(ch, ext)
        for ch in self.runes.ALPHABET_EXTENSION["still_missing"]:
            self.assertNotIn(ch, ext)

    def test_extension_does_not_resolve_rune4_tail(self):
        """A negative that must stay negative: the tail is still no letter."""
        img = self._image()
        ext = self.runes.extended_alphabet(img)
        mask, glyphs, _ = self.runes.load_rune4(img)
        s = self.runes.signature(mask, glyphs[48])
        best = min((min(self.runes.distance(s, r) for r in refs), name)
                   for name, refs in ext.items())
        self.assertGreater(best[0], 30, "tail must not resolve inside the "
                                        "same-letter band")
        self.assertTrue(
            self.runes.RUNE4_TAIL_AFTER_EXTENSION["verdict"].startswith(
                "not a letter"))

    def test_rune1_names_no_mechanism(self):
        """It is a wish. The capacity bound must not move."""
        from puzzle import positions
        self.assertIsNone(self.runes.RUNE1_DECODE["mechanism"])
        self.assertEqual(positions.MECHANISM_CAPACITY["total_reachable"], 4)

    def test_sweep_recovered_all_four_runes_as_controls(self):
        """A sweep that cannot find what it already knows proves nothing."""
        s = self.runes.STRIP_SWEEP
        self.assertEqual(len(s["controls_recovered"]), 4)
        self.assertEqual(s["rune_strips_found"], 4)
        self.assertEqual(s["new_cipher_strips"], 0)


class TestTuesdayAsANumber(unittest.TestCase):
    """TUESDAY points at 2 under every reading. It stays unpromoted."""

    def test_all_readings_agree_on_two(self):
        from puzzle import runes
        self.assertEqual(runes.TUESDAY_AS_A_NUMBER["all_readings_agree_on"], 2)

    def test_the_dates_really_were_tuesdays(self):
        """Recomputed, not asserted."""
        import datetime as dt
        self.assertEqual(dt.date(2020, 5, 5).isoweekday(), 2)    # wallet created
        self.assertEqual(dt.date(2020, 11, 3).isoweekday(), 2)   # election
        self.assertNotEqual(dt.date(2020, 5, 10).isoweekday(), 2)  # funding

    def test_it_is_not_promoted(self):
        """A bare ordinal with no word cannot complete a position."""
        from puzzle import runes, positions
        rec = runes.TUESDAY_AS_A_NUMBER
        self.assertFalse(rec["promoted"])
        self.assertEqual(len(rec["blockers"]), 2)
        confirmed = {a.position for a in positions.CONFIRMED}
        self.assertNotIn(2, confirmed, "position 2 must not be confirmed")

    def test_position_2_is_still_unreachable_by_the_clock(self):
        """The gap that makes the reading interesting must remain a gap."""
        from puzzle import positions
        self.assertEqual(positions.MECHANISM_CAPACITY["total_reachable"], 4)


class TestChronology(unittest.TestCase):
    """The one date that is not interpretation, and what it rules out."""

    def setUp(self):
        from puzzle import chronology
        self.c = chronology

    def test_offsets_are_recomputed_not_asserted(self):
        for e in self.c.DEPICTED_EVENTS:
            self.assertEqual(self.c.days_after_key(e["date"]),
                             e["days_after_key"], e["date"])

    def test_every_depicted_2020_event_postdates_the_key(self):
        """The constraint. If this ever fails, the argument collapses."""
        for e in self.c.DEPICTED_EVENTS:
            if e["date"] == self.c.CONSTRAINT["key_fixed_by"]:
                continue
            self.assertGreater(e["days_after_key"], 0,
                               f"{e['date']} is not after the key")
        earliest = min(e["days_after_key"] for e in self.c.DEPICTED_EVENTS
                       if e["days_after_key"] > 0)
        self.assertEqual(earliest, self.c.CONSTRAINT["gap_days"])

    def test_calendar_identities(self):
        """Memorial Day, Mother's Day and Election Day, recomputed."""
        import datetime as dt

        def nth_weekday(y, m, wd, n):
            d = dt.date(y, m, 1)
            d += dt.timedelta(days=(wd - d.weekday()) % 7)
            return d + dt.timedelta(weeks=n - 1)

        may_mondays = [d for d in (dt.date(2020, 5, i) for i in range(1, 32))
                       if d.weekday() == 0]
        self.assertEqual(may_mondays[-1], dt.date(2020, 5, 25))   # Memorial Day
        self.assertEqual(nth_weekday(2020, 5, 6, 2), dt.date(2020, 5, 10))
        first_mon = nth_weekday(2020, 11, 0, 1)
        self.assertEqual(first_mon + dt.timedelta(days=1), dt.date(2020, 11, 3))

    def test_the_prediction_is_recorded_as_withdrawn(self):
        """An earlier version claimed chronology separated the candidate
        words. It does not - every one has a pre-2020-05-10 referent."""
        rec = self.c.PREDICTION_DOES_NOT_DISCRIMINATE
        self.assertIn("withdrawn", rec["so"])
        self.assertIn("Garner", rec["actual"])
        self.assertEqual(set(rec["they_still_fail"]), {"breathe", "black"})

    def test_breathe_predates_the_key_by_its_own_referent(self):
        """The module's own referent list says 2014. Keep the two consistent."""
        years = {t["year"] for t in self.c.TIMELESS_REFERENTS}
        self.assertIn(2014, years)
        garner = [t for t in self.c.TIMELESS_REFERENTS if t["year"] == 2014][0]
        self.assertIn("breathe", garner["what"])

    def test_what_the_constraint_actually_excludes(self):
        """It excludes the two drawn dates, and no word."""
        rec = self.c.CONSTRAINT_EXCLUDES
        self.assertEqual(set(rec["excluded"]), {"05.25.20", "11.03.20"})
        self.assertIn("any candidate word", rec["does_not_exclude"])

    def test_the_excluded_dates_are_editorial_in_the_census(self):
        """Corroboration must be real: the census must agree, independently."""
        from puzzle import positions
        roles = {k: v["role"] for k, v in positions.NUMERAL_CENSUS.items()}
        self.assertTrue(roles["hoodie_date"].startswith("editorial"))
        self.assertTrue(roles["election_date"].startswith("editorial"))

    def test_wallet_created_is_flagged_unverifiable(self):
        """It is community folklore, and one hypothesis leaned on it."""
        rec = self.c.WALLET_CREATED_IS_UNVERIFIED
        self.assertFalse(rec["on_chain"])
        self.assertEqual(rec["first_chain_appearance"], "2020-05-10")

    def test_rune1_wish_is_matched_by_the_ledger(self):
        """'I hope many bitcoins will be sent here' - four people did."""
        self.assertEqual(len(self.c.TIPS), 4)
        total = sum(t["btc"] for t in self.c.TIPS)
        self.assertAlmostEqual(self.c.BALANCE_BTC, 0.2 + total, places=8)

    def test_clock_shows_no_coherent_time(self):
        """The rival to the position map, killed exhaustively."""
        from puzzle import positions
        r = positions.clock_time_consistency()
        self.assertEqual(len(r["assignments"]), 6)
        self.assertGreater(r["best_error_deg"],
                           4 * r["drawing_scatter_deg"])
        self.assertTrue(
            positions.CLOCK_SHOWS_NO_TIME["verdict"].startswith("not a time"))

    def test_on_chain_matches_the_record(self):
        """Network-gated: re-read the chain and compare."""
        try:
            got = self.c.verify_on_chain(timeout=20)
        except Exception as exc:                      # offline, rate-limited
            self.skipTest(f"chain unavailable: {exc}")
        self.assertEqual(got["block_height"], self.c.FUNDING["block_height"])
        self.assertEqual(got["block_time_utc"], self.c.FUNDING["block_time_utc"])
        self.assertEqual(got["spent_txo_sum"], 0, "the prize must be unspent")


class TestWhitepaperTypos(unittest.TestCase):
    """A known source text plus deliberate errors is a classic carrier.
    Here it is noise, and the control is what shows it."""

    def setUp(self):
        from puzzle import extraction
        self.rec = extraction.WHITEPAPER_TYPOS

    def test_typos_hit_bip39_below_the_control_rate(self):
        r = self.rec
        typo_rate = r["typo_words_in_bip39"] / r["typo_words_total"]
        ctrl_rate = r["control_words_in_bip39"] / r["control_words_total"]
        self.assertLess(typo_rate, ctrl_rate,
                        "if typos beat the control this verdict must be revisited")

    def test_the_control_words_really_are_bip39(self):
        """Recomputed, so the control cannot rot."""
        from puzzle import wordlist
        ctrl = ["problem", "solution", "transaction", "history", "earliest",
                "purposes", "company", "trusted", "system", "single"]
        hits = sum(1 for w in ctrl if wordlist.is_valid(w))
        self.assertEqual(hits, self.rec["control_words_in_bip39"])
        typo = [d["source"] for d in self.rec["deviations"]]
        self.assertEqual(sum(1 for w in typo if wordlist.is_valid(w)),
                         self.rec["typo_words_in_bip39"])

    def test_none_of_the_artwork_spellings_is_correct_english(self):
        """Each deviation must actually differ from the source."""
        for d in self.rec["deviations"]:
            self.assertNotEqual(d["artwork"], d["source"])

    def test_verdict_is_noise(self):
        self.assertTrue(self.rec["verdict"].startswith("noise"))

    def test_the_earlier_calligram_claim_is_corrected(self):
        from puzzle import extraction
        c = extraction.CALLIGRAM_CLAIM_CORRECTED
        self.assertIn("no word emphasised or altered", c["was"])
        self.assertIn("six words altered", c["now"])


class TestChosenVersusInherited(unittest.TestCase):
    """The community's 24-word table, evaluated on principled grounds."""

    def setUp(self):
        from puzzle import positions
        self.p = positions
        self.rec = positions.CHOSEN_VERSUS_INHERITED

    def test_chosen_set_matches_what_the_repo_actually_holds(self):
        """If these ever diverge, one of them is stale."""
        confirmed = {a.position for a in self.p.CONFIRMED}
        chosen = set(self.rec["chosen"])
        self.assertTrue(confirmed.issubset(chosen),
                        "every confirmed position must be a chosen number")
        self.assertEqual(chosen, confirmed | {9, 11})

    def test_inherited_numbers_carry_no_evidence(self):
        self.assertEqual(
            self.rec["likelihood_ratio_of_an_inherited_number"], 1.0)
        self.assertEqual(self.rec["community_table_adds"], 0)

    def test_the_two_sets_do_not_overlap(self):
        self.assertEqual(
            set(self.rec["chosen"]) & set(self.rec["inherited"]), set())

    def test_pyramid_is_chosen_but_still_rejected(self):
        """Chosen is necessary, not sufficient - it still has to measure up."""
        self.assertIn(11, self.rec["chosen"])
        confirmed = {a.position for a in self.p.CONFIRMED}
        self.assertNotIn(11, confirmed)


class TestVisibleWordsAreNotThePhrase(unittest.TestCase):
    """The simplest reading of 'find the seed phrase in this picture'."""

    def test_visible_words_underperform_ordinary_english(self):
        from puzzle import extraction
        r = extraction.VISIBLE_WORDS_ARE_NOT_THE_PHRASE
        self.assertLess(r["artwork_rate"], r["control_rate"])

    def test_control_rate_is_recomputed(self):
        from puzzle import wordlist
        ctrl = ("house table river silver garden window pencil bottle jacket "
                "candle market pillow ticket rocket forest planet dinner "
                "summer flower orange button carpet dragon hammer island "
                "ladder monkey needle pepper ribbon").split()
        rate = sum(1 for w in ctrl if wordlist.is_valid(w)) / len(ctrl)
        self.assertAlmostEqual(rate, 0.80, places=2)


class TestHourHandIsTheLength(unittest.TestCase):
    """The blank hand names the phrase length rather than a position."""

    def setUp(self):
        from puzzle import positions
        self.p = positions
        self.rec = positions.HOUR_HAND_IS_THE_LENGTH

    def test_21_is_a_valid_bip39_length(self):
        self.assertIn(21, self.rec["bip39_lengths"])

    def test_clock_reach_is_recomputed(self):
        reach = sorted(self.p.all_rays())
        self.assertEqual((reach[0], reach[-1]), self.rec["clock_reaches"])
        self.assertEqual(reach, list(range(3, 24)))

    def test_the_counting_argument(self):
        """21 is saturated by the available mechanisms; 24 is one short."""
        reach = set(self.p.all_rays())
        available = len(self.rec["non_clock_available"])
        for length, gaps in self.rec["non_clock_needed"].items():
            computed = tuple(sorted(set(range(1, length + 1)) - reach))
            self.assertEqual(computed, gaps, f"length {length}")
        self.assertEqual(len(self.rec["non_clock_needed"][21]), available)
        self.assertGreater(len(self.rec["non_clock_needed"][24]), available)

    def test_the_blank_hand_really_is_blank(self):
        """Two hands carry words, one does not - the anomaly must be real."""
        census = self.p.CLOCK_HAND_CENSUS["hands"]
        labelled = [v for v in census.values()
                    if "TOWER" in v or "MOON" in v]
        blank = [v for v in census.values() if "unlabelled" in v]
        self.assertEqual(len(labelled), 2)
        self.assertEqual(len(blank), 1)
        self.assertIn("21", blank[0])

    def test_it_claims_no_tractability_gain(self):
        self.assertFalse(self.rec["changes_tractability"])
        self.assertTrue(self.rec["confidence"].startswith("inference"))


class TestLineOrientationIsNotAMechanism(unittest.TestCase):
    """A mechanism proposed, tested, and killed by its own control."""

    def setUp(self):
        from puzzle import positions
        self.rec = positions.LINE_ORIENTATION_IS_NOT_A_MECHANISM

    def test_the_match_equals_the_control(self):
        r = self.rec
        self.assertAlmostEqual(r["control_artwork_edges_within_1_7_deg"],
                               r["control_uniform_within_1_7_deg"], places=3)
        self.assertGreaterEqual(r["control_artwork_edges_within_1_7_deg"], 0.20,
                                "if arbitrary edges stopped matching, revisit")

    def test_ray_spacing_makes_any_orientation_match(self):
        """The structural reason, recomputed from the ray set."""
        from puzzle import positions
        rays = sorted({b % 180 for e in positions.all_rays().values()
                       for _, _, b in e})
        gaps = [rays[i + 1] - rays[i] for i in range(len(rays) - 1)]
        self.assertLessEqual(max(gaps), 15.1)
        self.assertLessEqual(max(gaps) / 2, 7.6)

    def test_food_and_real_still_have_no_number(self):
        from puzzle import positions
        self.assertTrue(self.rec["verdict"].startswith("refuted"))
        marked = set(positions.MARKED_WITHOUT_NUMBER)
        self.assertEqual(marked, {"food", "real"})


class TestMarkingDevices(unittest.TestCase):
    """Four bespoke devices, none used twice, against 21 words needed."""

    def setUp(self):
        from puzzle import positions
        self.p = positions
        self.rec = positions.MARKING_DEVICES

    def test_the_catalogue_matches_the_known_words(self):
        marked = set()
        for words in self.rec["devices"].values():
            marked.update(words)
        confirmed = {w for a in self.p.CONFIRMED for w in a.words}
        self.assertTrue(confirmed.issubset(marked))
        self.assertEqual(marked & set(self.p.MARKED_WITHOUT_NUMBER),
                         {"food", "real"})
        self.assertEqual(len(marked), self.rec["words_marked"])

    def test_no_device_is_used_more_than_twice(self):
        uses = max(len(w) for w in self.rec["devices"].values())
        self.assertEqual(uses, self.rec["max_uses_of_any_device"])
        self.assertLessEqual(uses, 2)

    def test_the_shortfall_is_stated(self):
        self.assertGreater(self.rec["words_needed"], self.rec["words_marked"] * 4)

    def test_the_bar_for_overturning_it_is_recorded(self):
        """A conclusion this strong must say what would break it."""
        self.assertIn("survives a control", self.rec["what_would_overturn_it"])

    def test_underline_used_once(self):
        self.assertEqual(self.p.UNDERLINE_SWEEP["genuine_outside_the_plinth"], 0)


class TestCountsMustBeReadable(unittest.TestCase):
    """A count a solver cannot recover cannot be the intended clue."""

    def setUp(self):
        from puzzle import positions
        self.p = positions
        self.rec = positions.COUNTS_MUST_BE_READABLE

    def test_flag_star_count_is_unreadable_not_deviant(self):
        r = self.rec
        self.assertNotEqual(r["flag_stars_detected"], r["flag_stars_canonical"])
        self.assertTrue(r["verdict"].endswith("unreadable count"))
        # rows of a real 50-star canton alternate 6 and 5; these do not
        self.assertNotIn(set(r["flag_star_rows"]), [{5, 6}])

    def test_it_is_a_separate_filter_from_chosen_versus_inherited(self):
        chosen = set(self.p.CHOSEN_VERSUS_INHERITED["chosen"])
        inherited = set(self.p.CHOSEN_VERSUS_INHERITED["inherited"])
        self.assertTrue(chosen and inherited)
        self.assertIn("cannot be the intended clue", self.rec["principle"])

    def test_creator_posts_recorded_as_environment_blocked(self):
        rec = self.p.CREATOR_POSTS_UNREACHABLE
        self.assertIn("reddit.com", rec["routes_tried"])
        self.assertIn("web.archive.org", rec["routes_tried"])
        self.assertTrue(rec["snapshot_exists"])
        self.assertIn("open to any browser", rec["verdict"])


class TestHiddenText(unittest.TestCase):
    """Low-contrast text the earlier fixed-enhancement sweeps could not see."""

    IMAGE = os.environ.get("PUZZLE_IMAGE", "puzzle.png")

    def setUp(self):
        from puzzle import hidden_text
        self.h = hidden_text

    def test_hidden_words_are_bip39(self):
        from puzzle import wordlist
        found = self.h.hidden_bip39_words()
        self.assertTrue(found)
        for w in found:
            self.assertTrue(wordlist.is_valid(w), w)

    def test_the_new_words_are_not_already_in_the_marked_set(self):
        """If they were already known this would not be a correction."""
        from puzzle import positions
        known = {w for a in positions.CONFIRMED for w in a.words}
        known |= set(positions.MARKED_WITHOUT_NUMBER)
        self.assertEqual(self.h.hidden_bip39_words() & known, set())

    def test_correction_names_what_it_supersedes(self):
        c = self.h.CORRECTION
        self.assertIn("positions.WORD_SUPPLY", c["affects"])
        self.assertIn("positions.MARKING_DEVICES", c["affects"])
        self.assertTrue(c["device_is_repeatable"])
        from puzzle import positions
        self.assertIn("SUPERSEDED", positions.MARKING_DEVICES)

    def test_sht_is_readable_only_in_a_narrow_window(self):
        """The whole point: no global enhancement shows it.

        Contrast is the wrong measure - a badly chosen window clips to a
        high-contrast field with no text in it. What distinguishes the right
        window is that the strokes *resolve*, so count ink components.
        """
        if not os.path.exists(self.IMAGE):
            self.skipTest("artwork not present")
        import numpy as np
        from scipy import ndimage

        box = (252, 782, 292, 802)          # tight on the text, flat ground
        def components(lo):
            w = self.h.level_window(self.IMAGE, box, lo)
            return ndimage.label(w < 128, np.ones((3, 3)))[1]

        peak = components(204)
        self.assertGreaterEqual(peak, 6, "the text must resolve into strokes")
        for lo in (120, 150, 185, 225):
            self.assertLess(components(lo), peak,
                            f"window {lo} should not resolve the text")

    def test_local_stretch_runs_and_preserves_shape(self):
        if not os.path.exists(self.IMAGE):
            self.skipTest("artwork not present")
        from PIL import Image
        out = self.h.local_stretch(self.IMAGE)
        self.assertEqual(out.shape, Image.open(self.IMAGE).size[::-1])

    def test_reported_but_unlocated_claims_are_kept_separate(self):
        """Other people's claims must not be recorded as findings."""
        found = {e["text"] for e in self.h.FOUND}
        reported = {e["text"] for e in self.h.REPORTED_NOT_YET_FOUND}
        self.assertEqual(found & reported, set())
        self.assertIn("TO TEST USE WORDS", reported)


class TestLeftMarginAndSweep(unittest.TestCase):
    """The margin sentences, and a sweep that supports no negative."""

    def setUp(self):
        from puzzle import hidden_text
        self.h = hidden_text

    def test_margin_lines_are_recorded_in_order(self):
        lines = self.h.LEFT_MARGIN["lines"]
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("1KfZ"))
        self.assertIn("FIRST PREDICTION", lines[2])

    def test_the_number_is_an_inference_not_a_measurement(self):
        rec = self.h.LEFT_MARGIN
        self.assertEqual(rec["inferred_x"], 1)
        self.assertTrue(rec["inference_not_measurement"])
        from puzzle import runes
        # the glyph itself must stay recorded as unidentifiable
        self.assertTrue(runes.RUNE4_TAIL_IS_UNIDENTIFIABLE["verdict"]
                        .startswith("unidentifiable"))

    def test_sweep_supports_no_negative(self):
        s = self.h.HIDDEN_SWEEP
        self.assertLess(s["controls_recovered"], s["controls"])
        self.assertIn("supports no negative", s["verdict"])

    def test_reported_fragment_is_not_all_bip39(self):
        """A claim this repo briefly got wrong; keep it pinned."""
        from puzzle import wordlist
        as_written = ["to", "test", "use", "words"]
        hits = [w for w in as_written if wordlist.is_valid(w)]
        self.assertEqual(len(hits), 2)
        note = [e for e in self.h.REPORTED_NOT_YET_FOUND
                if e["text"] == "TO TEST USE WORDS"][0]["note"]
        self.assertIn("2 of its 4", note)


class TestClockArrowClaim(unittest.TestCase):
    """A reported marking on the hour hand, searched for under controls."""

    def setUp(self):
        from puzzle import hidden_text
        self.rec = hidden_text.CLOCK_ARROW_CLAIM

    def test_this_negative_is_control_backed(self):
        """Unlike HIDDEN_SWEEP, this one recovers both controls."""
        from puzzle import hidden_text
        self.assertIn("TOWER", self.rec["half_width_48px"])
        self.assertIn("MOON", self.rec["half_width_48px"])
        self.assertIn("supported", self.rec["verdict"])
        # the other sweep must stay marked as supporting no negative
        self.assertIn("supports no negative",
                      hidden_text.HIDDEN_SWEEP["verdict"])

    def test_the_discarded_width_is_recorded(self):
        """A setting that failed its controls must not be quietly dropped."""
        self.assertIn("discarded", self.rec["half_width_18px"])

    def test_it_strengthens_the_length_deduction(self):
        from puzzle import positions
        self.assertIn("HOUR_HAND_IS_THE_LENGTH", self.rec["strengthens"])
        self.assertEqual(positions.HOUR_HAND_IS_THE_LENGTH["saturated_at"], 21)

    def test_the_claim_is_not_promoted_to_a_finding(self):
        from puzzle import hidden_text
        found = {e["text"] for e in hidden_text.FOUND}
        self.assertNotIn("5A", found)


class TestWordlistIsBip39(unittest.TestCase):
    """Electrum v1 tested and excluded; the breathe anomaly resolved."""

    def setUp(self):
        from puzzle import wordlist
        self.w = wordlist
        self.rec = wordlist.WORDLIST_IS_BIP39

    def test_bip39_holds_every_marked_or_hidden_word(self):
        for word in self.rec["must_contain"]:
            self.assertTrue(self.w.is_valid(word), word)
        self.assertEqual(self.rec["bip39_covers"],
                         len(self.rec["must_contain"]))

    def test_electrum_v1_is_short_by_exactly_food_and_this(self):
        self.assertEqual(set(self.rec["electrum_v1_missing"]), {"food", "this"})
        self.assertLess(self.rec["electrum_v1_covers"],
                        self.rec["bip39_covers"])

    def test_breathe_and_food_cannot_share_a_wordlist(self):
        """The constraint that decides the scheme."""
        self.assertTrue(self.rec["no_list_contains_both"])
        self.assertFalse(self.w.is_valid("breathe"))
        self.assertTrue(self.w.is_valid("food"))

    def test_the_marked_word_is_the_one_kept(self):
        from puzzle import positions
        self.assertIn("food", positions.MARKED_WITHOUT_NUMBER)
        self.assertTrue(self.rec["verdict"].startswith("BIP-39"))


class TestStatusCommand(unittest.TestCase):
    """The scoreboard must recompute, not restate."""

    def test_status_runs_and_reports_the_gap(self):
        import subprocess, sys
        r = subprocess.run([sys.executable, "solve.py", "status"],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout
        self.assertIn("phrase length          : 21", out)
        self.assertIn("BIP-39", out)
        self.assertIn("NOT searchable", out)

    def test_the_counts_match_the_records(self):
        from puzzle import positions, hidden_text
        confirmed = len(positions.CONFIRMED)
        unbound = set(positions.MARKED_WITHOUT_NUMBER) | \
            hidden_text.hidden_bip39_words()
        self.assertEqual(confirmed, 3)
        self.assertEqual(len(unbound), 5)
        length = positions.HOUR_HAND_IS_THE_LENGTH["saturated_at"]
        self.assertEqual(length - confirmed - 1, 17)


class TestRebuiltDetector(unittest.TestCase):
    """The rebuild: it must recover both sentence controls, or say nothing."""

    IMAGE = os.environ.get("PUZZLE_IMAGE", "puzzle.png")

    def setUp(self):
        from puzzle import hidden_text
        self.h = hidden_text
        if not os.path.exists(self.IMAGE):
            self.skipTest("artwork not present")

    @staticmethod
    def _overlaps(a, b):
        return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])

    def test_both_sentence_controls_are_recovered(self):
        """The whole point of the rebuild - the first sweep managed one."""
        _, _, strips = self.h.detect(self.IMAGE)
        for name, box in (("PAY FOR THE FUTURE", (64, 700, 94, 1060)),
                          ("THIS IS THE FIRST PREDICTION", (88, 700, 118, 1060))):
            self.assertTrue(any(self._overlaps(b, box) for b, _ in strips),
                            f"control not recovered: {name}")

    def test_the_band_is_relative_to_local_ground(self):
        """Relative-to-mode is what excludes the artwork's black line work."""
        import numpy as np
        from PIL import Image
        g = np.asarray(Image.open(self.IMAGE).convert("L")).astype(int)
        mask = self.h.faint_ink(g)
        # black line work must be excluded almost entirely
        self.assertLess(mask[g < 60].mean(), 0.01)

    def test_scope_limit_is_recorded_not_glossed(self):
        scope = self.h.DETECTOR_SCOPE
        self.assertEqual(scope["sentence_controls_passed"],
                         scope["sentence_controls_total"])
        self.assertIn("SHT", scope["short_mark_control"])
        self.assertIn("sentences only", scope["negative_covers"])

    def test_the_negative_is_scoped_to_sentences(self):
        rec = self.h.REBUILT_SWEEP
        self.assertEqual(rec["new_sentences_found"], 0)
        self.assertIn("supported", rec["verdict"])
        self.assertIn("short marks are out of scope", rec["caveat"])

    def test_it_supersedes_the_broken_sweep(self):
        """The old sweep must stay marked as supporting nothing."""
        self.assertIn("supports no negative", self.h.HIDDEN_SWEEP["verdict"])


class TestBindingCensus(unittest.TestCase):
    """The obstacle stated precisely: bindings, not words."""

    def setUp(self):
        from puzzle import positions
        self.p = positions
        self.rec = positions.BINDING_CENSUS

    def test_the_census_covers_every_known_numeral(self):
        self.assertEqual(self.rec["numerals_total"],
                         len(self.p.NUMERAL_CENSUS))

    def test_exactly_one_numeral_binds_a_word(self):
        binds = [k for k, v in self.p.NUMERAL_CENSUS.items()
                 if "pairing" in v["role"]]
        self.assertEqual(len(binds), self.rec["numerals_that_bind"])
        self.assertEqual(binds, ["section_1"])

    def test_bindings_total_matches_the_position_records(self):
        confirmed = len(self.p.CONFIRMED)
        self.assertEqual(confirmed + 1, self.rec["bindings_total"])
        self.assertEqual(sum(self.rec["devices"].values()),
                         self.rec["bindings_total"])

    def test_unbound_words_are_the_ones_with_no_position(self):
        from puzzle import hidden_text
        unbound = set(self.p.MARKED_WITHOUT_NUMBER) | \
            hidden_text.hidden_bip39_words()
        self.assertEqual(set(self.rec["unbound_words"]), unbound)

    def test_every_third_device_search_is_recorded(self):
        """A negative is only worth stating if you can point at the searches."""
        self.assertEqual(len(self.rec["third_device_searches"]), 4)
        for name in ("UNDERLINE_SWEEP",
                     "LINE_ORIENTATION_IS_NOT_A_MECHANISM"):
            self.assertTrue(hasattr(self.p, name), name)
