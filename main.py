# The Pipeline will be like this:
# PDF -> EXTRACTION -> PARSING -> MODELING -> STORAGE -> QUERY

from Extraction.pdf_loader import load_pdf
from Extraction.table_extractor import extract_words
from parsing.row_parser import build_rows, classify_rows
from parsing.task_parser import parse_task_row
from parsing.column_parser import (detect_action_columns, cluster_columns, extract_row_actions)


pdf_path = "Data/Raw/dam_mvp_chapters.pdf"

pdf = load_pdf(pdf_path)


#for i, page in enumerate(pdf.pages):
 #   print(f"\n -- Page {i+1} --")
page = pdf.pages[23]  # Just testing on one page for now
words = extract_words(page)
rows = build_rows(words)
classified_rows = classify_rows(rows)

for row in classified_rows:
   if row["type"] == "task":
      
      parsed = parse_task_row(row["line"])
      print(parsed)
    
   else:
      print(f"[SECTION] {row['line']}")


print("\n--- COLUMN DETECTION ---")

columns = detect_action_columns(words)
clustered_columns = cluster_columns(columns)

for c in columns:
   print(c)


print("\n --- ROW ACTION TEST ---")

for row in classified_rows:
   if row["type"] == "task":
      actions = extract_row_actions(words, row["top"])

      print(row["line"])
      print(actions)
      print()
      