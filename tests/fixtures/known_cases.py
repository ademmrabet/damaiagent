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

    # RESOLVED with the task_blocks.py v3 fix (see module docstring):
    # a real screenshot of page 12 showed 2.126's title+actions are
    # genuinely on ONE row, textbook title-above-identifier - the
    # earlier "two lines merged by row-rounding" theory was wrong,
    # caught by seeing the actual table instead of guessing from
    # coordinates alone.
    "2.126": {
        "page_index": 24,
        "expected_title": "Quarterly Mission program",
        "status": "fixed",
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

# threshold_variant cases (2.513.3 -> (a)/(b)/(c) by loan amount) -
# separate from CASES above since they need id reconstruction, not
# just a title check. Page 48, confirmed via screenshot.
THRESHOLD_VARIANT_PAGE_INDEX = 48
THRESHOLD_VARIANT_PARENT = "2.513.3"
THRESHOLD_VARIANT_IDS = ["2.513.3.a", "2.513.3.b", "2.513.3.c"]
