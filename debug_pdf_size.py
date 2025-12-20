from pypdf import PdfReader
from pathlib import Path
import os

pdf_path = "warren_county_form_template.pdf"
if not os.path.exists(pdf_path):
    print(f"File not found: {pdf_path}")
else:
    reader = PdfReader(pdf_path)
    page = reader.pages[0]
    print(f"Page width: {page.mediabox.width}")
    print(f"Page height: {page.mediabox.height}")
