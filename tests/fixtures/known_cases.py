
PDF_PATH = "data/raw/updated dam file.pdf"

CASES = {

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

    "2.312.2": {
        "page_index": 33,
        "expected_title": "Signature of Financing Agreements for technical cooperation funds / facilities",
        "expected_references": ["16.100", "16.200", "16.300", "16.400"],
        "status": "fixed",
    },

    "2.126": {
        "page_index": 24,
        "expected_title": "Quarterly Mission program",
        "status": "fixed",
    },

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

    "1.114.1": {
        "page_index": 16,
        "expected_title": "Preparation, review and approval of New CSP (with a 3-Year Rolling Business Plan)",
        "status": "fixed",
    },
    "1.114.2": {
        "page_index": 16,
        "expected_title": "Preparation, review and approval of New RISP (with a 3-Year Rolling Business Plan)",
        "status": "fixed",
    },
    "1.115.1": {
        "page_index": 16,
        "expected_title": "Interim CSP/RISP; Country Brief; or JCAS Follow the respective process for new CSP/RISP",
        "expected_references": ["1.114.1", "1.114.2"],
        "status": "fixed",
    },
    "1.115.2": {
        "page_index": 16,
        "expected_title": "Updated CSP/RISP (‘Extension’) Follow the respective process for new CSP/RISP",
        "expected_references": ["1.114.1", "1.114.2"],
        "status": "fixed",
    },
    "1.117.1": {
        "page_index": 17,
        "expected_title": "Preparation Mission for CSP / RISP Organization of mission Completion Report and Diagnostic Note",
        "expected_references": ["2.120"],
        "status": "fixed",
    },
    "1.117.2": {
        "page_index": 17,
        "expected_title": "CSP / RISP Dialogue Mission (during CSP / Organization of mission RISP preparation)",
        "expected_references": ["2.120"],
        "status": "fixed",
    },
}

SEE_ID_REFERENCE_PAGE_INDEX = 16
SEE_ID_COLON_REFERENCE_PAGE_INDEX = 17

THRESHOLD_VARIANT_PAGE_INDEX = 48
THRESHOLD_VARIANT_PARENT = "2.513.3"
THRESHOLD_VARIANT_IDS = ["2.513.3.a", "2.513.3.b", "2.513.3.c"]

ROW_SPLIT_PAGE_INDEX = 58
ROW_SPLIT_EXPECTED = {
    "3.111": [("I", None), ("( i )", None), ("A", None), ("A", None), ("( i )", None)],
    "3.112": [("( i )", None), ("I", None), ("I", None), ("I", None), ("( i )", None), ("A", None), ("A", None)],
    "3.113": [("( i )", None), ("( i )", None), ("I", None), ("I", None), ("A", None)],
}

ROW_SPLIT_EXPECTED_FOOTNOTES = {
    "3.111": [3, 4],
    "3.112": [2, 3, 4, 5, 6],
    "3.113": [5, 6],
}

HYPHEN_DIGIT_PAGE_INDEX = 58
HYPHEN_DIGIT_CASES = {
    "3.111": "Concerned Staff members below PL-2 level",
    "3.112": "Concerned Staff of PL-2 and PL-1 levels",
}

# "Abbreviations and Acronyms" section - pages 2-7 (0-indexed),
# confirmed via extract_abbreviations() manual review (2026-08-05).
ABBREVIATIONS_FIRST_PAGE_INDEX = 2
ABBREVIATIONS_LAST_PAGE_INDEX = 7

# A handful of manually-verified term -> definition pairs, picked to
# cover: a plain single-line entry (DDG), a multi-line-definition
# entry that spans a top-tolerance merge (RDVP), a term that itself
# wraps across two lines (Concerned VP / Manager - the def-only-
# continuation-row bug), and a term appearing on more than one page
# with slightly different wording in the source PDF (PINS).
KNOWN_ABBREVIATIONS = {
    "DDG": "Deputy Director-General",
    "RDVP": "Vice-Presidency, Regional Development, Integration, and Business Delivery",
    "PGCL": "Office of the General Counsel and Legal Services",
    "BDIR": "Board of Directors",
    "Concerned VP / Manager": "The Vice-President / Manager under whom a specific activity or responsibility falls.",
}
