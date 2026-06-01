from Extraction.pdf_loader import load_pdf
from Extraction.table_extractor import extract_characters
from parsing.geometry_parser import extract_action_metadata, classify_relative_position


pdf_path = "../Data/Raw/dam_mvp_chapters.pdf"
pdf = load_pdf(pdf_path)
page = pdf.pages[23]

chars = extract_characters(page)

for c in chars:

    if (
        c["text"] == "R"
        and abs(c["x0"] - 465.0) < 3
        and abs(c["top"] - 342.8) < 3
    ):

        result = extract_action_metadata(c, chars)

        print(result)

        break