"""Low-contrast text hidden in the artwork, and the sweep that finds it.

**This module exists because an earlier conclusion in this repository was
wrong.** ``positions.WORD_SUPPLY`` reported "no sixth marked word" after two
sweeps across 21 object surfaces and every text strip in the image. Both
sweeps ran at a *fixed* enhancement. The artwork also carries text at a
contrast so low that no single enhancement shows it - and that text contains
BIP-39 words.

The find was prompted by the archived Reddit thread (see :data:`THREAD`), where
solvers reported hidden content found with photo-forensics tools. Verifying
their claims turned up more than they described.
"""

from __future__ import annotations

#: The technique. A *level sweep* maps a narrow luminance window to full
#: contrast; a *local stretch* does the same per tile, so faint marks on flat
#: ground come up everywhere at once without amplifying noise on ground that is
#: genuinely featureless.
#:
#: ``SHT`` on the Statue's tablet is invisible at every global enhancement and
#: legible only in the window 196-212 of 255. That is the whole reason the
#: earlier sweeps missed it.
METHOD = {
    "level_sweep": "map [lo, lo+delta] to full contrast; sweep lo across the "
                   "range and watch for text appearing",
    "local_stretch": "per-tile percentile stretch, tile 48 px, 3rd-97th "
                     "percentile; tiles with range < 6 are left flat so that "
                     "featureless ground is not turned into noise",
    "why_earlier_sweeps_failed": "both ran at one fixed enhancement",
}

#: Text confirmed present, with the window that reveals it. Each was read off
#: the image directly, not inferred.
FOUND = (
    {"text": "PAY FOR THE FUTURE.",
     "where": "vertical, left margin beside the Bitcoin address",
     "box": (64, 700, 94, 1060), "orientation": "reads bottom-to-top",
     "bip39_words": ("future",)},
    {"text": "THIS IS THE FIRST PREDICTION.",
     "where": "vertical, left margin, immediately right of the line above",
     "box": (88, 700, 118, 1060), "orientation": "reads bottom-to-top",
     "bip39_words": ("this", "first")},
    {"text": "SHT",
     "where": "the Statue's tablet, below the underlined BLM and the fist",
     "box": (238, 778, 296, 806), "window": (196, 212),
     "bip39_words": ()},
    {"text": "THIS",
     "where": "inserted into the title line, which reads FIND THE SEED PHRASE "
              "IN THE **THIS** PICTURE - ungrammatical, so the word is an "
              "insertion, the same device as 'real' in ONLY real Bitcoin",
     "box": (500, 370, 860, 410),
     "bip39_words": ("this",)},
)

#: Reported by solvers in the thread and **not yet located here**. Recorded so
#: the claims are testable rather than folklore - and treated with suspicion,
#: since faint-text transcriptions are exactly the kind of reading that goes
#: wrong. A sweep for them, using the two confirmed sentences as controls,
#: recovered only one of the two controls, so it supports **no** negative:
#: their absence here is not evidence of their absence.
REPORTED_NOT_YET_FOUND = (
    {"text": "TO TEST USE WORDS", "by": "DiOnline",
     "note": "as written, only 2 of its 4 words are BIP-39 - 'test' and "
             "'use'; 'to' and 'words' are not. An earlier version of this "
             "record claimed all of them were, by silently singularising "
             "'words' and dropping 'to'. Two of four is exactly the base "
             "rate for ordinary English, so it is not evidence of anything."},
    {"text": "FIRST THE AT", "by": "DiOnline",
     "note": "likely a partial misread. The confirmed sentence THIS IS THE "
             "FIRST PREDICTION contains 'THE FIRST' adjacent, and this "
             "fragment is those two words plus a stray - so it may be the "
             "same text read badly, not a separate phrase."},
    {"text": "BITCOIN", "by": "RaTMaTaT", "where": "middle of the image"},
    {"text": "something like 5A", "by": "RaTMaTaT",
     "where": "on a clock arrow"},
    {"text": "inscriptions", "by": "RaTMaTaT",
     "where": "bottom right of the monument"},
)

#: **The correction.** ``positions.WORD_SUPPLY`` said five marked words and no
#: sixth. That is wrong: ``future``, ``first`` and ``this`` are all BIP-39 and
#: all appear in hidden text, and ``predict`` sits inside ``PREDICTION``.
#:
#: The structural argument in ``positions.MARKING_DEVICES`` is also weakened.
#: It observed four bespoke devices, none used more than twice, and concluded
#: the artwork does not mark 21 words. Low-contrast hidden text is a **fifth
#: device, and unlike the others it is repeatable** - there is no limit on how
#: many sentences can be hidden this way, and at least three separate
#: placements are already confirmed.
CORRECTION = {
    "was": "five marked words; two sweeps found no sixth",
    "now": "at least three further BIP-39 words appear in hidden low-contrast "
           "text: future, first, this",
    "why_missed": "both sweeps ran at a fixed enhancement; this text is "
                  "legible only inside a narrow luminance window",
    "affects": ("positions.WORD_SUPPLY", "positions.SURFACE_SWEEP",
                "positions.MARKING_DEVICES"),
    "device_is_repeatable": True,
    "verdict": "the word-supply bottleneck is reopened - the artwork carries "
               "more words than the visible layer shows",
}

#: The archived Reddit thread, supplied as a PDF and read by OCR. It is
#: **testimony, not evidence** - solvers speculating - with two exceptions
#: that are checkable and were checked.
THREAD = {
    "source": "web.archive.org snapshot of reddit.com/user/stsh_n, post "
              "j79zvj 'Bitcoin puzzle (2000$)', supplied as a 34-page PDF",
    "confirms_independently": (
        "the three Russian rune plaintexts match this repo's decodes of "
        "runes 1, 2 and 4 exactly, relayed by u/Amadeus407",
        "u/DiOnline states the puzzle's creator and the person who posted it "
        "are different people - which is what forensics.ATTRIBUTION concluded "
        "from the two signatures and the medium mismatch",
    ),
    "new_leads": (
        "hidden sentences exist and are findable with forensic filters",
        "'breathe' is in the Electrum v1 wordlist though not in BIP-39",
        "solvers counted 28 unique rune glyphs excluding TUESDAY, consistent "
        "with this repo's 27-letter Cyrillic alphabet plus a separator",
        "u/Amadeus407: 'Verbatim spelling. It might make a difference.'",
    ),
    "caution": "most of the thread is unverified speculation and several "
               "claims in it contradict each other; only the items above are "
               "carried into this repository, and only after checking",
}


def local_stretch(image_path, tile: int = 48, lo: int = 3, hi: int = 97,
                  flat_range: int = 6):
    """Per-tile percentile stretch. Returns a uint8 array.

    This is what surfaced ``PAY FOR THE FUTURE.`` and
    ``THIS IS THE FIRST PREDICTION.`` Tiles whose range is below *flat_range*
    are set to mid-grey rather than stretched, so genuinely featureless ground
    does not become noise - without that guard the output is unreadable.
    """
    import numpy as np
    from PIL import Image

    a = np.asarray(Image.open(image_path).convert("L")).astype(float)
    out = np.zeros_like(a)
    for y in range(0, a.shape[0], tile):
        for x in range(0, a.shape[1], tile):
            b = a[y:y + tile, x:x + tile]
            p1, p2 = np.percentile(b, lo), np.percentile(b, hi)
            if p2 - p1 < flat_range:
                out[y:y + tile, x:x + tile] = 128
            else:
                out[y:y + tile, x:x + tile] = np.clip(
                    (b - p1) * 255.0 / (p2 - p1), 0, 255)
    return out.astype("uint8")


def level_window(image_path, box, lo: int, width: int = 18):
    """Map luminance ``[lo, lo+width]`` to full contrast over *box*.

    ``level_window(img, (238, 778, 296, 806), 196)`` renders ``SHT``.
    """
    import numpy as np
    from PIL import Image

    g = np.asarray(Image.open(image_path).convert("L").crop(box)).astype(float)
    return np.clip((g - lo) * 255.0 / width, 0, 255).astype("uint8")


def hidden_bip39_words() -> set:
    """Every BIP-39 word confirmed to appear in hidden text."""
    out = set()
    for entry in FOUND:
        out.update(entry["bip39_words"])
    return out


#: The left margin, read in full. Beneath the target address, in faint hand:
#:
#:     ``1KfZGvwZxsvSmemoCmEV75uqcNzYBHjkHZ``
#:     ``PAY FOR THE FUTURE.``
#:     ``THIS IS THE FIRST PREDICTION.``
#:
#: The placement is the interesting part. These sit directly under the address
#: the prize is held at, which reads as the artist captioning the donation
#: rather than instructing a solver.
#:
#: **"THIS IS THE FIRST PREDICTION" corroborates rune 4.** Rune 4 ends
#: ``НОМЕР`` - "number" - followed by a glyph this repository has shown to be
#: unidentifiable from internal evidence. An artwork that calls itself *the
#: first* of something is an artwork with a number, and the natural reading of
#: the pair is that the trailing glyph is **1**.
#:
#: That is an inference, not a measurement: the glyph does not resemble a hand
#: drawn ``1`` (it reads as a vertical stroke crossed by diagonals), and the
#: cipher is a substitution, so shape carries no information anyway. What the
#: sentence supplies is a *reason to expect* a number there, which is more than
#: the artwork offered before.
#:
#: It also revives a question already answered once: a "first" implies a
#: series. ``forensics.NO_SIBLING_PUZZLE`` searched and found none. Either the
#: series was never continued, or it exists somewhere unsearched.
LEFT_MARGIN = {
    "lines": ("1KfZGvwZxsvSmemoCmEV75uqcNzYBHjkHZ",
              "PAY FOR THE FUTURE.",
              "THIS IS THE FIRST PREDICTION."),
    "placement": "directly beneath the target address",
    "reads_as": "the artist captioning the donation, not instructing a solver",
    "corroborates": "rune 4's trailing 'НОМЕР X' - an artwork calling itself "
                    "the first is an artwork with a number",
    "inferred_x": 1,
    "inference_not_measurement": True,
    "implies_a_series": "and forensics.NO_SIBLING_PUZZLE found none",
}

#: The sweep for further hidden sentences, and why it proves nothing.
#:
#: The strip detector was re-run over the locally stretched image, looking for
#: rows of letter-sized components in a mid-grey band - faint strokes, not the
#: artwork's black line work. It returns 135 candidates; the 22 outside the
#: known text blocks were all rendered and inspected, and every one is content
#: already catalogued: the address, the pyramid's brickwork, the ``Order and
#: stability`` banner, ``MOON`` on its hand, the Great Seal's lettering.
#:
#: **But it recovered only one of its two positive controls.** ``PAY FOR THE
#: FUTURE.`` was found; ``THIS IS THE FIRST PREDICTION.`` was not, though it
#: sits a few pixels away and is equally legible by eye. A detector that misses
#: half its controls cannot support a negative, so this one does not: there may
#: be more hidden text, and this sweep is not the instrument to rule it out.
HIDDEN_SWEEP = {
    "candidates": 135,
    "inspected_outside_known_blocks": 22,
    "new_text_found": 0,
    "controls": 2,
    "controls_recovered": 1,
    "verdict": "supports no negative - the detector misses half its controls",
}


#: **The reported "5A on the clock arrow" is not there.** A controlled search.
#:
#: u/RaTMaTaT wrote: *"On the clockwise arrow, it looks like something similar
#: to 5A."* ``Clockwise arrow`` is almost certainly machine translation of the
#: Russian *часовая стрелка* - which means **hour hand**. That made it the most
#: valuable unchecked claim in the thread, because the hour hand is the one
#: that points at 21 and carries **no word**. A marking on it would be the
#: word-and-number pair the puzzle has been short of.
#:
#: Each hand was straightened into a strip by sampling along its ray from the
#: hub at (473, 940) with perpendicular offsets, then swept across every
#: luminance window.
#:
#: **The instrument was fixed until it passed its controls.** At a half-width
#: of 18 px it recovered neither ``TOWER`` nor ``MOON`` - the labels sit
#: *beside* the hands, not on the ray - so every reading at that width was
#: discarded. At 48 px both controls come back plainly.
#:
#: With controls passing, the hour hand carries **nothing** at any window. The
#: letter-sized components it does produce are rune 2's glyphs, which fall
#: inside the widened strip, and dithering in the hand's own gradient. The
#: monument's lower right, also reported to carry inscriptions, shows only the
#: plinth's steps.
#:
#: **This negative is supported**, unlike the earlier hidden-text sweep: the
#: detector recovers both of its positive controls.
#:
#: It also strengthens :data:`positions.HOUR_HAND_IS_THE_LENGTH`. That reading
#: turns on the hour hand being *deliberately* blank while the other two carry
#: words. The blankness has now survived a search designed to overturn it.
CLOCK_ARROW_CLAIM = {
    "claim": "something similar to 5A on the hour hand",
    "by": "u/RaTMaTaT",
    "translation_note": "'clockwise arrow' renders Russian часовая стрелка, "
                        "which means hour hand",
    "why_it_mattered": "the hour hand points at 21 and carries no word; a "
                       "marking on it would be a word-and-number pair",
    "method": "straighten each hand into a strip along its ray from the hub, "
              "then sweep every luminance window",
    "half_width_18px": "recovered neither control - readings discarded",
    "half_width_48px": "both TOWER and MOON recovered",
    "hour_hand_result": "nothing at any window; the components found are "
                        "rune 2's glyphs and gradient dithering",
    "monument_lower_right": "plinth steps only, no inscriptions",
    "verdict": "not present - and this negative is supported, the detector "
               "recovers both controls",
    "strengthens": "positions.HOUR_HAND_IS_THE_LENGTH - the blankness "
                   "survived a search designed to overturn it",
}
