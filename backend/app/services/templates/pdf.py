import shutil, subprocess
from pathlib import Path
class PDFConversionError(RuntimeError): pass
def convert_docx_to_pdf(docx_path, output_dir=None):
 src=Path(docx_path).resolve()
 if not src.is_file() or src.suffix.lower()!='.docx': raise PDFConversionError('Input must be an existing DOCX file.')
 exe=shutil.which('libreoffice') or shutil.which('soffice')
 if not exe: raise PDFConversionError('LibreOffice was not found. Install it and ensure its CLI is on PATH.')
 dest=Path(output_dir).resolve() if output_dir else src.parent; dest.mkdir(parents=True,exist_ok=True)
 output=dest/f'{src.stem}.pdf'; output.unlink(missing_ok=True)
 result=subprocess.run([exe,'--headless','--convert-to','pdf','--outdir',str(dest),str(src)],capture_output=True,text=True,timeout=90,check=False)
 output=dest/f'{src.stem}.pdf'
 if result.returncode or not output.is_file(): raise PDFConversionError((result.stderr or result.stdout or 'PDF conversion failed').strip())
 return output
