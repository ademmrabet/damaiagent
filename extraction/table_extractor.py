# Pulls words and characters off a single pdfplumber page. Both are
# just pdfplumber's own primitives, positioned (x0/top/bottom per
# item) - that positioning is what row-clustering and geometry work
# downstream depend on.
#
# NOTE: v1's version of this file had a comment claiming it used
# "Camelot/Tabula" - it never did, it's always been plain pdfplumber.
# Wrong comments are worse than no comments; fixed here.


def extract_words(page):
    return page.extract_words()


def extract_characters(page):
    return page.chars
