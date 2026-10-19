import pdfplumber


# open the dam pdf
def load_pdf(path):
    return pdfplumber.open(path)
