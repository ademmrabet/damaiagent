# Real DAM pages/tasks already diagnosed by hand against the actual
# PDF (data/raw/updated dam file.pdf - the 79-page source, chosen
# over the old 66-page MVP subset because it includes the glossary,
# abbreviations, and authority-code legend). Same task ids, different
# page numbers than the original diagnosis - re-verified against this
# file directly, not assumed to carry over.
#
# Each case documents an actual bug that was found and either fixed
# or knowingly deferred, with the page/row evidence to back it up.

PDF_PATH = "data/raw/updated dam file.pdf"

CASES = {

    # v1 bug: title text trailing after the actions row got stolen by
    # the NEXT task (2.312.1) because both tasks happen to have a
    # bare identifier row nearby. Fixed in task_blocks.py by only
    # forward-attaching a stray line when nothing is currently open.
    "2.311": {
        "page_index": 33,
        "expected_title": "Finalization / Update of Loan / Grant agreement for Signature",
        "status": "fixed",
    },
    "2.312.1": {
        "page_index": 33,
        "expected_title": "Signature of Financing Agreements for ADB or ADF loans, grants, or guarantees",
        "status": "fixed",
    },

    # v1 bug: "See DAM 16.100, 16.200..." cross-reference text got
    # digit-stripped into "See DAM ., ., ., and ." instead of being
    # extracted as references and removed cleanly from the title.
    "2.312.2": {
        "page_index": 33,
        "expected_title": "Signature of Financing Agreements for technical cooperation funds / facilities",
        "expected_references": ["16.100", "16.200", "16.300", "16.400"],
        "status": "fixed",
    },

    # KNOWN UNRESOLVED, on purpose: 2.126's title line ("Quarterly
    # Mission program") and what looks like ITS OWN actions
    # ("( i ) I C C R A ( i )") sit at top=386.49 and top=386.34 - two
    # physically distinct PDF lines less than a point apart that
    # build_rows()'s round(top) clustering merges into one row, which
    # then gets misread as a continuation of the PRECEDING task
    # (2.125). This isn't a row-order problem task_blocks.py can fix
    # with text alone - it needs x-position (2.126's title starts at
    # the same x0 as every other title, ~86-91; the actions start in
    # a completely different x-range past 300) to separate correctly.
    # That's explicitly the next stage's job (normalize + validate
    # extracted characters, geometry-aware). Left failing here on
    # purpose rather than papering over it with a text heuristic that
    # would just break the 2.311 fix above.
    "2.126": {
        "page_index": 24,
        "expected_title": "Quarterly Mission program",
        "status": "deferred_to_geometry_stage",
    },

    # v1-equivalent bug, found via a screenshot of the real table
    # (page 48): 3.225 is a "redirect" row whose whole line is a
    # complete, period-terminated sentence; 3.226's title genuinely
    # starts on the next line, before 3.226's own identifier appears.
    # Fixed by treating a period-terminated open task as finished,
    # rather than blindly attaching the next stray line to it.
    "3.225": {
        "page_index": 60,
        "expected_title": "Communication to Government",
        "expected_references": ["2.114", "2.115", "2.116", "2.117"],
        "status": "fixed",
    },
    "3.226": {
        "page_index": 60,
        "expected_title": "Communication with Co-Financiers of projects and third parties",
        "status": "fixed",
    },
}
