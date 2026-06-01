# LOADS PDF FILES
# this codes handles Pages and Texts from PDF files 

import pdfplumber

def load_pdf(path):
    return pdfplumber.open(path)