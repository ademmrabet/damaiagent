
import re


def normalize_split_numbers(text):
    if not text:
        return ""

    return re.sub(r"\b(\d)\s+(\d)\b", r"\1\2", text)


def collapse_spaced_words(text):
    if not text:
        return ""

    pattern = re.compile(r'(?:\b[A-Za-z]\b(?:\s+|$)){2,}')

    def repl(match):
        letters = re.findall(r'[A-Za-z]', match.group())
        joined = ''.join(letters)

        if set(joined) <= {"I", "C", "R", "A"}:
            return match.group()

        return joined

    return pattern.sub(repl, text)


def normalize_whitespace(text):
    if not text:
        return ""

    return " ".join(text.split())


def fix_known_ocr_errors(text):
    """
    KNOWN DEBT: this is a hardcoded list of specific strings seen to
    be broken in this specific PDF ("Region alPortfolio" -> "Regional
    Portfolio"), not a general rule. It'll silently do nothing for the
    next OCR glitch that isn't already on this list. Fine for a 9-day
    build on a known, bounded set of tables; call it out explicitly
    in the report as a limitation, don't pretend it's a general fix.
    """

    if not text:
        return ""

    text = text.replace("Region alPortfolio", "Regional Portfolio")
    text = text.replace("CPPR/ RPPR", "CPPR / RPPR")

    text = re.sub(r"\b([A-Z])\s([a-z]{3,})", r"\1\2", text)

    return text


def clean(text):
    """Runs the full OCR-cleanup pipeline in the order that matters."""

    text = normalize_split_numbers(text)
    text = collapse_spaced_words(text)
    text = normalize_whitespace(text)
    text = fix_known_ocr_errors(text)

    return text
