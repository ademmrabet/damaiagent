import re


def normalize_split_numbers(text):

    if not text:
        return ""

    return re.sub(
        r"\b(\d)\s+(\d)\b",
        r"\1\2",
        text
    )


def collapse_spaced_words(text):

    if not text:
        return ""

    pattern = re.compile(
        r'(?:\b[A-Za-z]\b(?:\s+|$)){2,}'
    )

    def repl(match):

        token = match.group()

        letters = re.findall(
            r'[A-Za-z]',
            token
        )

        joined = ''.join(letters)

        # Do not collapse action sequences
        if joined in {
            "IA",
            "IC",
            "IR",
            "RA",
            "CA",
            "CR"
        }:
            return token

        return joined

    return pattern.sub(
        repl,
        text
    )


def normalize_whitespace(text):

    if not text:
        return ""

    return " ".join(
        text.split()
    )

def fix_known_ocr_errors(text):

    if not text:
        return ""

    text = text.replace(
        "Region alPortfolio",
        "Regional Portfolio"
    )

    text = text.replace(
        "CPPR/ RPPR",
        "CPPR / RPPR"
    )

    return text