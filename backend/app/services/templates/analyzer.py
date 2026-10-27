import argparse
import json
import re
from pathlib import Path
from docx import Document
from app.schemas.template import TemplateSpec

SECTIONS = [
    ('education','Education',['institution','degree','field_of_study','start_date','end_date','details']),
    ('skills','Skills',['category','skills']),
    ('projects','Projects',['title','technologies','bullets','url','start_date','end_date']),
    ('experience','Experience',['title','organization','location','start_date','end_date','bullets']),
    ('certifications','Certifications',['title','issuer','date','details']),
    ('achievements','Achievements',['title','issuer','date','details']),
    ('extracurricular','Extracurricular Activities',['title','organization','date','details']),
]

def base(source, page_size='LETTER', orientation='portrait', margins=None, font='Arial', sizes=None, notes=None):
    sizes = sizes or [8, 9.5, 11, 20]
    return {
        'template_id': 'draft-' + re.sub(r'[^a-z0-9-]+', '-', source.stem.lower()).strip('-')[:65],
        'version': '0.1.0-draft',
        'display_name': 'Draft from ' + source.name,
        'description': 'Analyzer-generated draft; administrator review required.',
        'page_size': page_size,
        'orientation': orientation,
        'margins': margins or {'top_in':.55,'bottom_in':.55,'left_in':.65,'right_in':.65},
        'fonts': {'family':font,'name_pt':max(sizes),'heading_pt':max([x for x in sizes if x<18] or [11]),'body_pt':min([x for x in sizes if x>=8] or [9.5]),'small_pt':min(sizes),'heading_color':'#172554','body_color':'#111827'},
        'spacing': {'line_spacing':1,'paragraph_before_pt':0,'paragraph_after_pt':2,'section_before_pt':7,'section_after_pt':3},
        'section_order': [x[0] for x in SECTIONS],
        'sections': [{'id':i,'label':label,'allowed_fields':fields} for i,label,fields in SECTIONS],
        'bullet_character':'•','bullet_left_indent_in':.18,'bullet_first_line_indent_in':-.12,
        'date_tab_position_in':6.9,'contact_separator':' | ','allow_photo':False,
        'max_pages':2,'layout':'single-column',
        'fit_adjustments':{'min_body_pt':8,'max_body_pt':11,'min_paragraph_after_pt':0,'max_paragraph_after_pt':6},
        'notes_and_uncertainty':notes or ['Layout details not reliably exposed; human review required.'],
    }

def analyze_docx(path):
    source=Path(path);doc=Document(source);fonts=[];sizes=[];headings=[]
    for paragraph in doc.paragraphs:
        if paragraph.text.strip() and (paragraph.text.isupper() or any(run.bold for run in paragraph.runs)):
            headings.append(paragraph.text[:80])
        for run in paragraph.runs:
            if run.font.name: fonts.append(run.font.name)
            if run.font.size: sizes.append(round(run.font.size.pt,1))
    section=doc.sections[0];unique=sorted(set(sizes)) or [8,9.5,11,20]
    alignments=sorted({str(p.alignment) for p in doc.paragraphs if p.text.strip()})
    tab_count=sum(1 for p in doc.paragraphs if len(p.paragraph_format.tab_stops)>0)
    border_count=sum(1 for p in doc.paragraphs if 'pBdr' in p._p.xml)
    draft=base(source,'LETTER' if abs(section.page_width.inches-8.5)<.3 else 'A4','landscape' if section.page_width>section.page_height else 'portrait',
        {'top_in':round(section.top_margin.inches,2),'bottom_in':round(section.bottom_margin.inches,2),'left_in':round(section.left_margin.inches,2),'right_in':round(section.right_margin.inches,2)},
        sorted(set(fonts))[0] if fonts else 'Arial',unique,
        [f'Detected fonts: {sorted(set(fonts)) or "none"}.',f'Detected sizes: {unique}.',f'Potential headings: {headings[:15]}.',f'Paragraph alignments observed: {alignments}.',f'Paragraphs with tab stops: {tab_count}.',f'Paragraph borders observed in OOXML: {border_count}.','Exact semantic section mappings and visual fidelity require review.'])
    usable=section.page_width.inches-section.left_margin.inches-section.right_margin.inches
    draft['date_tab_position_in']=min(6.9,max(3.0,usable-.05))
    return draft

def analyze_pdf(path):
    import pdfplumber
    source=Path(path)
    with pdfplumber.open(source) as pdf:
        if not pdf.pages: raise ValueError('PDF contains no pages.')
        page=pdf.pages[0];width,height=page.width,page.height;chars=page.chars;words=page.extract_words() or [];lines=page.lines;rects=page.rects
        fonts=sorted({char.get('fontname','') for char in chars if char.get('fontname')})
        sizes=sorted({round(float(char.get('size',9)),1) for char in chars})
        left=min((float(char['x0']) for char in chars),default=45);top=min((float(char['top']) for char in chars),default=40)
        right=max((float(char['x1']) for char in chars),default=560);bottom=max((float(char['bottom']) for char in chars),default=740)
        horizontal_rules=[{'x0':round(float(line.get('x0',0)),1),'x1':round(float(line.get('x1',0)),1),'top':round(float(line.get('top',0)),1)} for line in lines if abs(float(line.get('top',0))-float(line.get('bottom',0)))<2 and float(line.get('x1',0))-float(line.get('x0',0))>150]
    margins={'top_in':max(.2,min(1.5,round(top/72,2))),'bottom_in':max(.2,min(1.5,round((height-bottom)/72,2))),'left_in':max(.2,min(1.5,round(left/72,2))),'right_in':max(.2,min(1.5,round((width-right)/72,2)))}
    draft=base(source,'LETTER' if abs(width/72-8.5)<.3 else 'A4','landscape' if width>height else 'portrait',margins,fonts[0] if fonts else 'Arial',sizes or [8,9.5,11,20],
        [f'PDF fonts observed: {fonts[:12] or "none"}.',f'Font sizes observed: {sizes[:20] or "none"}.',f'First-page dimensions: {round(width,1)} x {round(height,1)} points.',f'PDF line objects: {len(lines)}; rectangle objects: {len(rects)}; likely horizontal rules: {horizontal_rules[:12]}.','Paragraph styles, exact tab stops, and some spacing are estimated from positioned glyphs. Human review is required.'])
    usable=width/72-margins['left_in']-margins['right_in']
    draft['date_tab_position_in']=min(6.9,max(3.0,usable-.05))
    return draft

def main():
    parser=argparse.ArgumentParser(description='Analyze DOCX/PDF into draft TemplateSpec JSON')
    parser.add_argument('input');parser.add_argument('--output','-o',default='draft-template.json');args=parser.parse_args();source=Path(args.input)
    draft=analyze_docx(source) if source.suffix.lower()=='.docx' else analyze_pdf(source) if source.suffix.lower()=='.pdf' else None
    if draft is None: parser.error('Input must be .docx or .pdf')
    validated=TemplateSpec.model_validate(draft);dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(validated.model_dump(mode='json'),indent=2),encoding='utf-8')
    print(f'Draft written to {dest}; review uncertainty notes before publishing.')
if __name__=='__main__': main()
