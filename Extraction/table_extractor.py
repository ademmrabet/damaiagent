# This code uses Camelot/Tabula to extract tables from the PDF FIle
# It outputs raw tables


def extract_words(page):
    return page.extract_words()


def extract_characters(page):
    return page.chars