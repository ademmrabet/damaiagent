import re


# join digits the pdf split apart
def normalize_split_numbers(text):
    if not text:
        return ""

    return re.sub(r"\b(\d)\s+(\d)\b", r"\1\2", text)


# fix words printed letter by letter
def collapse_spaced_words(text):
    if not text:
        return ""

    pattern = re.compile(r"(?:\b[A-Za-z]\b(?:\s+|$)){2,}")

    def repl(match):
        letters = re.findall(r"[A-Za-z]", match.group())
        joined = "".join(letters)

        if set(joined) <= {"I", "C", "R", "A"}:
            return match.group()

        return joined

    return pattern.sub(repl, text)


# collapse repeated spaces
def normalize_whitespace(text):
    if not text:
        return ""

    return " ".join(text.split())


# hard-coded fixes for a few known extraction errors
def fix_known_ocr_errors(text):

    if not text:
        return ""

    text = text.replace("Region alPortfolio", "Regional Portfolio")
    text = text.replace("CPPR/ RPPR", "CPPR / RPPR")

    text = re.sub(r"\b([A-Z])\s([a-z]{3,})", r"\1\2", text)

    return text


# run all the cleaning steps in order
def clean(text):

    text = normalize_split_numbers(text)
    text = collapse_spaced_words(text)
    text = normalize_whitespace(text)
    text = fix_known_ocr_errors(text)

    return text
