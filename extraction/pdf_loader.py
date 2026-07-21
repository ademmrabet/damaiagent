# Opens the DAM PDF and hands back a pdfplumber document (pages,
# words, characters). This layer wasn't implicated in any bug found
# in v1 - ported essentially unchanged, just with an honest docstring.

import pdfplumber


def load_pdf(path):
    return pdfplumber.open(path)
