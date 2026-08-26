"""The puzzle's chronology, traced to records, and what it rules out.

The artwork is dense with historical reference: a death dated on a hoodie, an
election date drawn before the result was known, a toppled colonial bust, an
emancipation range, a cartoon cipher. This module dates each of them against
the record and against the **one date that is not a matter of interpretation**
- the block timestamp of the transaction that funded the prize.

That single fact turns out to constrain the puzzle more than any of the
imagery does. See :data:`CONSTRAINT`.

Everything here is re-derivable: :func:`verify_on_chain` re-reads the chain,
and the calendar claims are recomputed by the tests rather than asserted.
"""

from __future__ import annotations

import datetime as _dt

ADDRESS = "1KfZGvwZxsvSmemoCmEV75uqcNzYBHjkHZ"

#: The funding transaction, read from the chain rather than from folklore.
#:
#: This is the hinge of the whole module: the prize was in the address at
#: **2020-05-10 08:01:46 UTC**, so the private key - and therefore the seed
#: phrase - existed at or before that moment.
FUNDING = {
    "txid": "fcee21d44ee94c09869947c74b61669bf928358e9c2d1699fb075bb6ebf5d043",
    "block_height": 629754,
    "block_time_utc": "2020-05-10 08:01:46",
    "weekday": "Sunday",
    "amount_btc": 0.2,
    "inputs": 4,
    "outputs": 2,
    "input_type": "p2sh (SegWit-wrapped)",
    "output_type": "p2pkh (legacy)",
    "change_address": "39rEPyWKE9Ej2fQ6XJHdTpHW3qbXsqfA3H",
    "change_btc": 0.05080966,
    "note": "the funder's wallet is P2SH-SegWit while the puzzle address is "
            "legacy P2PKH - different software, so the puzzle key was "
            "generated deliberately, not just handed a wallet address",
}

#: **A correction to this repo's own record.** ``forensics.PUBLICATION`` carries
#: ``wallet_created: 2020-05-05``, taken from the community notes. That date is
#: **not on-chain and not verifiable.** A Bitcoin address has no creation
#: event; it becomes visible only when first used, and this address's first
#: appearance anywhere on the chain is the funding transaction above.
#:
#: This matters for one live hypothesis: 2020-05-05 was a Tuesday, which made
#: "rune 3's TUESDAY names the wallet's creation date" attractive. That
#: reading rests on an unverifiable date and should not be leaned on.
WALLET_CREATED_IS_UNVERIFIED = {
    "claim": "2020-05-05",
    "claimed_by": "community notes (HomelessPhD/BLM_0.2BTC)",
    "on_chain": False,
    "first_chain_appearance": "2020-05-10",
    "why": "an address has no creation event; it appears when first used",
    "affects": "the reading of rune 3's TUESDAY as the wallet's birthday",
}

#: Later payments into the address. Rune 1 reads *"I hope that many bitcoins
#: will be sent here"* - and the chain records that four separate people did.
#: A decoded rune and a public ledger agreeing is as direct as this kind of
#: tracing gets.
TIPS = (
    {"date": "2023-10-25", "btc": 0.00001000},
    {"date": "2024-12-13", "btc": 0.00100000},
    {"date": "2025-05-09", "btc": 0.00000557},
    {"date": "2025-06-02", "btc": 0.00005727},
)

#: Nothing has ever been spent from the address.
BALANCE_BTC = 0.20107284

#: Every dated thing the artwork depicts, against the record.
#:
#: ``days_after_key`` is measured from the funding transaction. The column is
#: the point of the table: **every 2020 event the artwork shows is positive.**
DEPICTED_EVENTS = (
    {"date": "2020-05-10", "days_after_key": 0,
     "what": "the prize is funded; the seed phrase exists by now",
     "also": "Mother's Day 2020 (2nd Sunday in May)",
     "source": "block 629754"},
    {"date": "2020-05-16", "days_after_key": 6,
     "what": "first of three acts of vandalism on the Leopold II statue, "
             "Ekeren",
     "source": "Wikipedia, Statue of Leopold II of Belgium, Ekeren"},
    {"date": "2020-05-25", "days_after_key": 15,
     "what": "George Floyd killed in Minneapolis; drawn as 05.25.20 on the "
             "hoodie, above 'I can't BREATHE'",
     "also": "Memorial Day 2020 (last Monday in May)",
     "source": "contemporaneous reporting"},
    {"date": "2020-06-04", "days_after_key": 25,
     "what": "decision to remove the Leopold II statue, Ekeren; the bust in "
             "the artwork is red-painted and gagged, matching the "
             "photographs",
     "source": "community notes cite a 2020-06-04 photograph"},
    {"date": "2020-06-09", "days_after_key": 30,
     "what": "Leopold II statue removed from Ekeren",
     "source": "CNN, Forbes, 2020-06-09/10"},
    {"date": "2020-06-30", "days_after_key": 51,
     "what": "Leopold II bust removed in Ghent, on the 60th anniversary of "
             "Congolese independence",
     "source": "contemporaneous reporting"},
    {"date": "2020-10-08", "days_after_key": 151,
     "what": "the artwork is published to Reddit by u/stsh_n",
     "source": "the post itself"},
    {"date": "2020-11-03", "days_after_key": 177,
     "what": "US presidential election; drawn as 11.03.20 under the red VS - "
             "and drawn *before* it happened, since publication precedes it "
             "by 26 days",
     "also": "Election Day is the Tuesday after the first Monday in November",
     "source": "US federal election calendar"},
)

#: Referents in the artwork that are **older** than the key, and so could have
#: fed the seed.
TIMELESS_REFERENTS = (
    {"year": 1776, "what": "the Statue of Liberty's tablet date, JULY IV "
                           "MDCCLXXVI - replaced in the artwork by a phone"},
    {"year": 1865, "what": "the 13th Amendment; its Section 1 is the plinth "
                           "text carrying the underlined 'subject' and '1'. "
                           "Also the year Leopold II became king, which is "
                           "why '1865 - 202...?' reads two ways"},
    {"year": 1886, "what": "the Statue of Liberty dedicated"},
    {"year": 1932, "what": "Huxley, *Brave New World* - the artwork's "
                           "'WELCOME TO THE BRAVE NEW WORLD' acrostic"},
    {"year": 1962, "what": "the Space Needle, built for the Seattle World's "
                           "Fair - the shaft carries 'food'"},
    {"year": 2008, "what": "the Bitcoin whitepaper, 2008-10-31 - its text is "
                           "the calligram the acrostic is built from"},
    {"year": 2012, "what": "*Gravity Falls* begins; its Journal 3 'Author's' "
                           "symbol substitution cipher is what rune 3 is "
                           "written in, and Bill Cipher is why the Great "
                           "Seal's pyramid is drawn as it is"},
    {"year": 2014, "what": "Eric Garner; 'I can't breathe' enters use six "
                           "years before the death the artwork dates"},
)

#: **The constraint.** The seed phrase was fixed on or before 2020-05-10.
#: Every 2020 event the artwork depicts happened afterwards - the earliest by
#: six days, the death it dates by fifteen, the election it draws by 177.
#:
#: So the BLM layer **cannot have determined the seed**. It is a carrier, not
#: a source. Whatever the phrase is, it was chosen from things that already
#: existed on 2020-05-10.
#:
#: This is consistent with the authorship finding in ``forensics``: a signed
#: base artwork plus a cipher layer, plausibly two hands and certainly two
#: dates.
CONSTRAINT = {
    "key_fixed_by": "2020-05-10",
    "earliest_depicted_2020_event": "2020-05-16",
    "gap_days": 6,
    "conclusion": "the artwork's 2020 content post-dates the key, so it "
                  "cannot encode the seed; it carries clues chosen earlier",
    "prediction": "the seed cannot be built from the events depicted; note this does NOT separate the candidate words, all of which have older referents - see PREDICTION_DOES_NOT_DISCRIMINATE",
}

#: **The prediction, checked - and it does not discriminate.** Recorded as a
#: correction to an earlier version of this module, which claimed it did.
#:
#: The constraint is sound, but the test built on it was overstated. It listed
#: ``breathe`` and ``black`` as excluded by chronology. They are not:
#:
#: * ``breathe`` comes from *"I can't breathe"*, which enters use with **Eric
#:   Garner in 2014** - as :data:`TIMELESS_REFERENTS` in this very module
#:   already recorded. The artwork attaches it to a 2020 death, but the phrase
#:   is six years older than the key.
#: * ``black`` reaches back to **BLM's founding in 2013**, and independently to
#:   the Russian idiom ``НА ЧЁРНЫЙ ДЕНЬ`` and the Latin kettle proverb, both
#:   older still.
#:
#: So every candidate word in play has a pre-2020-05-10 referent, and the
#: chronology separates none of them. ``breathe`` and ``black`` fail for the
#: reasons they always did - ``breathe`` is not in the BIP-39 wordlist at all,
#: and ``black`` literalises an idiom - not because of any date.
PREDICTION_DOES_NOT_DISCRIMINATE = {
    "claimed": "confirmed words predate the key while breathe and black do not",
    "actual": "every candidate has a pre-2020-05-10 referent; breathe traces "
              "to Eric Garner 2014 and black to BLM 2013, the Russian idiom "
              "and the Latin proverb",
    "so": "the chronology excludes no word, and the earlier 'two independent "
          "lines converge' claim is withdrawn",
    "they_still_fail": {"breathe": "not a BIP-39 word",
                        "black": "literalises a fixed idiom"},
}

#: What the constraint **does** exclude, which is narrower and still useful.
#:
#: Things that exist *only* because of the events the artwork depicts cannot
#: encode a seed fixed on 2020-05-10. The clearest cases are the two dates the
#: artwork draws as numerals: ``05.25.20`` and ``11.03.20``. Neither can be a
#: puzzle number, whatever else it is - the first names a death fifteen days
#: after the key, the second an election 177 days after it, drawn 26 days
#: before it happened.
#:
#: ``positions.NUMERAL_CENSUS`` already classes both as *editorial* rather than
#: puzzle-marked, on the separate grounds that neither is underlined or paired
#: with a word. The chronology reaches the same verdict independently.
CONSTRAINT_EXCLUDES = {
    "excluded": ("05.25.20", "11.03.20"),
    "why": "both name events postdating the key, so neither can be a number "
           "the seed was built from",
    "corroborates": "positions.NUMERAL_CENSUS, which calls both editorial on "
                    "the independent grounds that neither is underlined nor "
                    "paired with a word",
    "does_not_exclude": "any candidate word - see "
                        "PREDICTION_DOES_NOT_DISCRIMINATE",
}


def verify_on_chain(timeout: int = 30) -> dict:
    """Re-read the funding transaction and the address from a public API.

    Returns the block time, the number of payments, and the balance, so the
    constants above can be checked rather than trusted. Requires network.
    """
    import json
    import urllib.request

    def get(url):
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.load(r)

    tx = get(f"https://mempool.space/api/tx/{FUNDING['txid']}")
    addr = get(f"https://mempool.space/api/address/{ADDRESS}")
    cs = addr["chain_stats"]
    when = _dt.datetime.utcfromtimestamp(tx["status"]["block_time"])
    return {
        "block_height": tx["status"]["block_height"],
        "block_time_utc": when.strftime("%Y-%m-%d %H:%M:%S"),
        "weekday": when.strftime("%A"),
        "payments_in": cs["funded_txo_count"],
        "spent_txo_sum": cs["spent_txo_sum"],
        "balance_btc": (cs["funded_txo_sum"] - cs["spent_txo_sum"]) / 1e8,
    }


def days_after_key(date: str) -> int:
    """How long after the seed was fixed did *date* happen?"""
    key = _dt.date.fromisoformat(CONSTRAINT["key_fixed_by"])
    return (_dt.date.fromisoformat(date) - key).days
