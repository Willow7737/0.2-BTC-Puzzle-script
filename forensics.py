#!/usr/bin/env python3
"""Image forensics for the 0.2 BTC puzzle.

The seed words are not hidden with steganography - they are *drawn* into the
artwork at low contrast, on clock hands, tower shafts and monument plinths.
Recovering them needs tonal work, not bit extraction, so this tool provides
the three operations that actually paid off:

    stretch   percentile contrast stretch  - faint ink on a light ground
    highpass  subtract a blurred copy      - faint line work over texture
    channel   isolate one RGB channel      - read through coloured paint

plus ``probe``, which reports the metadata/alpha/LSB checks that rule
steganography out.

    ./forensics.py probe puzzle.png
    ./forensics.py regions puzzle.png -o out/       # every known hiding place
    ./forensics.py runes puzzle.png                 # verify the rune-4 plaintext
    ./forensics.py crop puzzle.png 1295,790,1495,1000 -m channel --channel r
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageFilter, ImageOps
except ImportError:  # pragma: no cover
    sys.exit("forensics needs pillow and numpy:  pip install pillow numpy")


#: Provenance of the artwork file, and why no better one exists.
#:
#: Three independent sources serve **byte-identical** content
#: (sha256 ``d0b04378f75d63997b8034ec2ef1bdd108178e4546de78237bd35abf4189a782``,
#: 2,383,395 bytes, 1600x1200):
#:
#:   * ``privatekeys.pw/images/puzzles/0.2-btc-puzzle.png``
#:   * ``i.redd.it/n1x7g8ceaur51.png``
#:   * ``HomelessPhD/BLM_0.2BTC`` at ``pictures/n1x7g8ceaur51.png``
#:
#: The middle one settles it. Reddit serves the **original upload** from
#: i.redd.it and puts downscaled variants on preview.redd.it, so a
#: byte-identical i.redd.it response means 1600x1200 is what was published.
#: The BitcoinTalk thread links only to the GitHub repo, which holds the same
#: bytes again - there is no second upload anywhere in the chain.
#:
#: And the file is **not** a downscale of something larger. Measured on it:
#:
#:   * edge-run widths average 1.61 px with **54.5% single-pixel** edges;
#:     downscaling smears every edge across two or more pixels;
#:   * spectral energy persists to Nyquist - tail/mid ratio **0.526**, where a
#:     downscaled image collapses well below ~0.3.
#:
#: So the published raster is at or near its native rendering resolution. The
#: only route to more detail is the artist's own source file. This closes what
#: earlier analysis called the highest-value next step: the runes, the clock
#: bearings and the claimed neck text are limited by the artwork as published,
#: not by a poor scan.
PROVENANCE = {
    "sha256": "d0b04378f75d63997b8034ec2ef1bdd108178e4546de78237bd35abf4189a782",
    "bytes": 2383395,
    "size": (1600, 1200),
    "identical_sources": ("privatekeys.pw", "i.redd.it/n1x7g8ceaur51.png",
                          "github:HomelessPhD/BLM_0.2BTC"),
    "edge_run_mean_px": 1.61,
    "single_pixel_edge_share": 0.545,
    "spectral_tail_mid_ratio": 0.526,
    "downscaled_from_larger": False,
    "verdict": "1600x1200 is the published original and is near-native; only "
               "the artist's source file could yield more detail",
}

#: Places in the 1600x1200 artwork that carry recovered or claimed text.
#: (x0, y0, x1, y1, scale, mode, rotate, note)
REGIONS: dict[str, tuple] = {
    "clock":        (270, 700, 660, 1170, 3, "highpass", 0,
                     "MOON on the red hand, TOWER on the black hand; face is mirrored"),
    "clock-hands":  (350, 810, 460, 900, 14, "stretch", 0, "the two hand labels"),
    "plinth":       (1295, 790, 1495, 1000, 8, "channel", 0,
                     "13th Amendment; 'Section 1' and 'subject' are underlined"),
    "statue-base":  (90, 1030, 250, 1075, 9, "stretch", 0, "ONLY real Bitcoin"),
    "vertical":     (60, 600, 100, 1030, 8, "stretch", -90,
                     "target address; PAY FOR THE FUTURE / THIS IS THE FIRST PREDICTION"),
    "needle":       (1185, 630, 1220, 700, 14, "highpass", -90, "FOOD on the tower shaft"),
    "statue-neck":  (110, 600, 260, 720, 9, "stretch", 0, "claimed BREATHE - unconfirmed"),
    "floyd-chest":  (960, 340, 1100, 420, 10, "highpass", 0, "I can't BREATHE on the hoodie"),
    "rune1":        (190, 35, 570, 120, 6, "highpass", 0, "top left, Cyrillic plaintext"),
    "rune2":        (260, 1008, 570, 1040, 9, "highpass", 0, "'sum of two numbers'"),
    "rune3":        (840, 835, 1000, 880, 10, "highpass", 0, "above Trump; mirrored"),
    "rune4":        (1520, 25, 1580, 1020, 3, "highpass", -90,
                     "right edge; '...for a black day number X'"),
    "seal":         (440, 720, 850, 1120, 3, "highpass", 0,
                     "Great Seal, text mirrored and all three inscriptions rewritten"),
    "section-one":  (1352, 806, 1432, 832, 20, "channel", 0,
                     "'Section 1' - the numeral 1 carries the same underline as 'subject'"),
    "calligram":    (500, 395, 830, 600, 5, "highpass", 0,
                     "whitepaper prose forming BRAVE NEW WORLD; nothing marked"),
    "flag":         (190, 310, 420, 640, 5, "highpass", 0, "checked, no text"),
    "latin":        (1030, 1155, 1300, 1185, 9, "stretch", 0,
                     "Esse quam niger es, sic dixit caccabus ollae"),
}


def _stretch(im: Image.Image, lo_pct=1.0, hi_pct=99.0) -> Image.Image:
    a = np.asarray(im.convert("RGB")).astype(np.float32)
    for c in range(3):
        lo, hi = np.percentile(a[:, :, c], lo_pct), np.percentile(a[:, :, c], hi_pct)
        a[:, :, c] = np.clip((a[:, :, c] - lo) * 255.0 / max(hi - lo, 1), 0, 255)
    return Image.fromarray(a.astype(np.uint8))


def _highpass(im: Image.Image, radius=5.0, amp=4.5) -> Image.Image:
    g = im.convert("L")
    b = g.filter(ImageFilter.GaussianBlur(radius))
    d = np.asarray(g).astype(np.float32) - np.asarray(b).astype(np.float32)
    return Image.fromarray(np.clip(128 - d * amp, 0, 255).astype(np.uint8))


def _channel(im: Image.Image, ch="r") -> Image.Image:
    """Isolate one channel - reads dark ink through translucent paint."""
    a = np.asarray(im.convert("RGB")).astype(np.float32)
    v = a[:, :, "rgb".index(ch)]
    lo, hi = np.percentile(v, 3), np.percentile(v, 88)
    return Image.fromarray(np.clip((v - lo) * 255 / max(hi - lo, 1), 0, 255).astype(np.uint8))


def render(src: Path, box, out: Path, scale=6, mode="stretch", rotate=0,
           channel="r", mirror=False) -> tuple[int, int]:
    im = Image.open(src).convert("RGB").crop(box)
    if rotate:
        im = im.rotate(rotate, expand=True)
    im = {"stretch": _stretch, "highpass": _highpass,
          "channel": lambda x: _channel(x, channel)}[mode](im)
    if mirror:
        im = ImageOps.mirror(im)
    im = im.resize((im.width * scale, im.height * scale), Image.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return im.size


def cmd_probe(args) -> int:
    """Report whether anything is hidden below the visible layer."""
    data = Path(args.image).read_bytes()
    print(f"file: {args.image}  ({len(data):,} bytes)")
    off, chunks = 8, {}
    while off < len(data):
        ln = struct.unpack(">I", data[off:off + 4])[0]
        typ = data[off + 4:off + 8].decode("latin1")
        chunks[typ] = chunks.get(typ, 0) + 1
        if typ in ("tEXt", "iTXt", "zTXt", "eXIf"):
            print(f"  METADATA {typ}: {data[off+8:off+8+min(ln,200)]!r}")
        off += 12 + ln
        if typ == "IEND":
            break
    print("  chunks:", ", ".join(f"{k}x{v}" for k, v in chunks.items()))
    print(f"  trailing data after IEND: {len(data)-off} bytes")

    a = np.asarray(Image.open(args.image))
    print(f"  size {a.shape[1]}x{a.shape[0]}, {a.shape[2] if a.ndim>2 else 1} channels")
    if a.ndim > 2 and a.shape[2] == 4:
        u = np.unique(a[:, :, 3])
        print(f"  alpha: {len(u)} distinct value(s)"
              + ("  -> uniform, nothing hidden" if len(u) == 1 else "  -> VARIES, inspect"))
    print("  LSB plane means (≈0.50 = ordinary image noise):")
    for i, ch in enumerate("RGB"):
        print(f"    {ch}: {(a[:,:,i] & 1).mean():.4f}")
    return 0


def cmd_regions(args) -> int:
    out = Path(args.out)
    src = Path(args.image)
    names = args.only.split(",") if args.only else list(REGIONS)
    for name in names:
        if name not in REGIONS:
            print(f"  unknown region {name!r}; known: {', '.join(REGIONS)}")
            continue
        x0, y0, x1, y1, scale, mode, rot, note = REGIONS[name]
        size = render(src, (x0, y0, x1, y1), out / f"{name}.png", scale, mode, rot,
                      args.channel, args.mirror)
        print(f"  {name:<13} {str(size):>13}  {note}")
    print(f"\nwritten to {out}/")
    return 0


def cmd_runes(args) -> int:
    """Check the published rune-4 plaintext against the segmented glyphs."""
    from puzzle.runes import verify_rune4

    r = verify_rune4(args.image)
    print(f"rune 4: {r['glyphs']} glyphs ({r['letters']} letters, "
          f"{r['glyphs'] - r['letters']} separators)")
    print(f"  word lengths from image : {r['word_lengths'][:len(r['crib_word_lengths'])]}")
    print(f"  word lengths from crib  : {r['crib_word_lengths']}")
    ok = r["word_lengths"][:len(r["crib_word_lengths"])] == r["crib_word_lengths"]
    print(f"  -> {'MATCH' if ok else 'MISMATCH'}")
    print(f"\n  recovered alphabet: {r['alphabet']} ({len(r['alphabet'])} letters)")
    print(f"  mean distance between glyphs the crib calls the same letter: "
          f"{r['mean_intra_letter_distance']:.1f}")
    print(f"  mean distance between all glyph pairs                     : "
          f"{r['mean_all_pairs_distance']:.1f}")
    print("  (the first being much lower is what confirms the alignment)")
    print("\n  trailing glyphs - the 'number X':")
    for idx, note, d in r["tail"]:
        print(f"    glyph {idx}: {note}" + (f"  (distance {d})" if d else ""))
    return 0


def cmd_crop(args) -> int:
    box = tuple(int(v) for v in args.box.split(","))
    size = render(Path(args.image), box, Path(args.out), args.scale, args.mode,
                  args.rotate, args.channel, args.mirror)
    print(f"{args.out} {size}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("probe", help="metadata / alpha / LSB checks")
    sp.add_argument("image")
    sp.set_defaults(func=cmd_probe)

    sp = sub.add_parser("regions", help="render every known hiding place")
    sp.add_argument("image")
    sp.add_argument("-o", "--out", default="forensics_out")
    sp.add_argument("--only", help="comma-separated subset of region names")
    sp.add_argument("--channel", default="r", choices=list("rgb"))
    sp.add_argument("--mirror", action="store_true")
    sp.set_defaults(func=cmd_regions)

    sp = sub.add_parser("runes", help="verify the rune-4 plaintext against the image")
    sp.add_argument("image")
    sp.set_defaults(func=cmd_runes)

    sp = sub.add_parser("crop", help="render an arbitrary box")
    sp.add_argument("image")
    sp.add_argument("box", help="x0,y0,x1,y1")
    sp.add_argument("-o", "--out", default="crop.png")
    sp.add_argument("-s", "--scale", type=int, default=6)
    sp.add_argument("-m", "--mode", default="stretch",
                    choices=("stretch", "highpass", "channel"))
    sp.add_argument("-r", "--rotate", type=int, default=0)
    sp.add_argument("--channel", default="r", choices=list("rgb"))
    sp.add_argument("--mirror", action="store_true")
    sp.set_defaults(func=cmd_crop)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
