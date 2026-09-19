
import pdfplumber


def load_pdf(path):
    return pdfplumber.open(path)
