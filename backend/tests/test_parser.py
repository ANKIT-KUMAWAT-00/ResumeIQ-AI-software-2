from io import BytesIO
from pathlib import Path
from docx import Document
from app.services.extraction.parser import extract_text
ROOT=Path(__file__).resolve().parents[2]

def test_docx_text_extraction_reads_paragraphs_and_tables():
 doc=Document();doc.add_paragraph('Ankit Kumawat');table=doc.add_table(rows=1,cols=2);table.cell(0,0).text='Education';table.cell(0,1).text='Lovely Professional University'
 stream=BytesIO();doc.save(stream);text=extract_text(stream.getvalue(),'resume.docx')
 assert 'Ankit Kumawat' in text and 'Lovely Professional University' in text

def test_supplied_reference_pdf_text_is_extractable():
 path=ROOT/'sample_data/reference_resume.pdf'
 if path.exists():
  text=extract_text(path.read_bytes(),'reference_resume.pdf')
  assert 'ANKIT KUMAWAT' in text.upper() and 'RESUMEIQ AI' in text.upper()
