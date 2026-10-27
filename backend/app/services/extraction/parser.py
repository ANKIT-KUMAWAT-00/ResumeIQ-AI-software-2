from pathlib import Path
from io import BytesIO
import zipfile

def extract_text(data: bytes, filename: str) -> str:
 suffix=Path(filename).suffix.lower()
 if suffix==".docx":
  from docx import Document
  try:
   with zipfile.ZipFile(BytesIO(data)) as archive:
    infos=archive.infolist()
    if len(infos)>2000 or sum(x.file_size for x in infos)>50*1024*1024: raise ValueError("DOCX expands beyond the safe parsing limit.")
    if not any(x.filename=='word/document.xml' for x in infos): raise ValueError("DOCX document body is missing.")
  except zipfile.BadZipFile as exc: raise ValueError("DOCX archive is invalid.") from exc
  doc=Document(BytesIO(data)); parts=[p.text for p in doc.paragraphs if p.text.strip()]
  for table in doc.tables:
   for row in table.rows: parts.append(" | ".join(c.text.strip() for c in row.cells))
  text="\n".join(parts)
 elif suffix==".pdf":
  import pdfplumber
  with pdfplumber.open(BytesIO(data)) as pdf:
   if len(pdf.pages)>20: raise ValueError("Resume PDF exceeds the 20-page parsing limit.")
   text="\n".join(p.extract_text() or "" for p in pdf.pages)
  if len(text.strip())<40:
   # OCR is an optional fallback only when installed; temporary images remain in memory.
   try:
    import pytesseract
    from pdf2image import convert_from_bytes
    text="\n".join(pytesseract.image_to_string(im) for im in convert_from_bytes(data,first_page=1,last_page=10))
   except Exception: pass
 else: raise ValueError("Only PDF and DOCX documents are supported.")
 text=text.strip()
 if not text: raise ValueError("No readable text found. Try a text-based PDF or DOCX file.")
 return text[:60000]
