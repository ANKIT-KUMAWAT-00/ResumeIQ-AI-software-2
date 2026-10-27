from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.shared import Inches, Pt, RGBColor
from app.schemas.resume import ResumeJSON
from app.schemas.template import TemplateSpec
PAGE_SIZES={"A4":(8.27,11.69),"LETTER":(8.5,11.0)}
def _rgb(v): v=v.lstrip('#'); return RGBColor(int(v[:2],16),int(v[2:4],16),int(v[4:],16))
def _run(p,text,spec,size=None,bold=False,color=None):
 r=p.add_run(text); r.font.name=spec.fonts.family; r.font.size=Pt(size or spec.fonts.body_pt); r.font.bold=bold; r.font.color.rgb=_rgb(color or spec.fonts.body_color); return r
def _p(doc,text,spec,size=None,bold=False,color=None,align=None,before=None,after=None):
 p=doc.add_paragraph(); p.paragraph_format.line_spacing=spec.spacing.line_spacing; p.paragraph_format.space_before=Pt(spec.spacing.paragraph_before_pt if before is None else before); p.paragraph_format.space_after=Pt(spec.spacing.paragraph_after_pt if after is None else after)
 if align is not None: p.alignment=align
 _run(p,text,spec,size,bold,color)
 return p
def _date(doc,left,right,spec):
 p=doc.add_paragraph(); p.paragraph_format.line_spacing=spec.spacing.line_spacing; p.paragraph_format.space_after=Pt(spec.spacing.paragraph_after_pt); tab_pos=min(spec.date_tab_position_in,3.0) if hasattr(doc,'_tc') else spec.date_tab_position_in; p.paragraph_format.tab_stops.add_tab_stop(Inches(tab_pos),WD_TAB_ALIGNMENT.RIGHT); _run(p,left,spec,bold=True)
 if right: _run(p,'\t'+right,spec,spec.fonts.small_pt)
 return p
def _bullet(doc,text,spec):
 p=doc.add_paragraph(); p.paragraph_format.left_indent=Inches(spec.bullet_left_indent_in); p.paragraph_format.first_line_indent=Inches(spec.bullet_first_line_indent_in); p.paragraph_format.line_spacing=spec.spacing.line_spacing; p.paragraph_format.space_after=Pt(spec.spacing.paragraph_after_pt); _run(p,f'{spec.bullet_character}  {text}',spec); return p
def render_resume(resume: ResumeJSON, template: TemplateSpec, output_path: str|Path)->Path:
 out=Path(output_path); out.parent.mkdir(parents=True,exist_ok=True); doc=Document(); sec=doc.sections[0]
 width,height=PAGE_SIZES[template.page_size]
 if template.orientation=='landscape': width,height=height,width
 sec.page_width,sec.page_height=Inches(width),Inches(height); sec.top_margin=Inches(template.margins.top_in); sec.bottom_margin=Inches(template.margins.bottom_in); sec.left_margin=Inches(template.margins.left_in); sec.right_margin=Inches(template.margins.right_in)
 c=resume.contact; name=c.full_name.upper() if template.header_uppercase else c.full_name
 header_align=WD_ALIGN_PARAGRAPH.LEFT if template.header_alignment=='left' else WD_ALIGN_PARAGRAPH.CENTER
 _p(doc,name,template,template.fonts.name_pt,True,template.fonts.heading_color,header_align,after=2)
 def display_url(value): return str(value).replace('https://','').replace('http://','') if value else None
 if template.contact_layout=='two-column':
  table=doc.add_table(rows=1,cols=2); table.autofit=False; table.columns[0].width=Inches(3.2); table.columns[1].width=Inches(3.2)
  for cell in table.rows[0].cells:
   cell.width=Inches(3.2)
   if cell.paragraphs: cell.paragraphs[0].text=''
   from docx.oxml import OxmlElement
   from docx.oxml.ns import qn
   pr=cell._tc.get_or_add_tcPr(); borders=OxmlElement('w:tcBorders')
   for edge in ('top','left','bottom','right','insideH','insideV'):
    el=OxmlElement('w:'+edge);el.set(qn('w:val'),'nil');borders.append(el)
   pr.append(borders)
  left=[('LinkedIn',display_url(c.linkedin_url)),('GitHub',display_url(c.github_url))]
  right=[('Email',c.email),('Mobile',c.phone)]
  if c.location: right.append(('Location',c.location))
  if c.portfolio_url: right.append(('Portfolio',display_url(c.portfolio_url)))
  for label,value in left:
   if value: _p(table.cell(0,0),(label+': ' if template.contact_labels else '')+value,template,template.fonts.small_pt,align=WD_ALIGN_PARAGRAPH.LEFT,after=1)
  for label,value in right:
   if value: _p(table.cell(0,1),(label+': ' if template.contact_labels else '')+value,template,template.fonts.small_pt,align=WD_ALIGN_PARAGRAPH.RIGHT,after=1)
 else:
  contacts=[c.email,c.phone,c.location,display_url(c.github_url),display_url(c.linkedin_url),display_url(c.portfolio_url)]; contacts=[x for x in contacts if x]
  if template.contact_labels:
   contacts=[('Email: '+c.email if c.email else None),('Mobile: '+c.phone if c.phone else None),('Location: '+c.location if c.location else None),('GitHub: '+display_url(c.github_url) if c.github_url else None),('LinkedIn: '+display_url(c.linkedin_url) if c.linkedin_url else None),('Portfolio: '+display_url(c.portfolio_url) if c.portfolio_url else None)]; contacts=[x for x in contacts if x]
  if contacts: _p(doc,template.contact_separator.join(contacts),template,template.fonts.small_pt,align=header_align,after=4)
 if resume.summary: _p(doc,resume.summary,template,after=3)
 section_targets=[]
 if template.layout=='two-column':
  table=doc.add_table(rows=1,cols=2); table.autofit=False
  usable=width-template.margins.left_in-template.margins.right_in
  table.columns[0].width=Inches(usable/2); table.columns[1].width=Inches(usable/2)
  for cell in table.rows[0].cells:
   cell.width=Inches(usable/2)
   if cell.paragraphs: cell.paragraphs[0].text=''
  section_targets=[table.rows[0].cells[0],table.rows[0].cells[1]]
 data={"education":resume.education,"skills":resume.skills,"projects":resume.projects,"experience":resume.experience,"certifications":resume.certifications,"achievements":resume.achievements,"extracurricular":resume.extracurricular_activities}
 cfgs={s.id:s for s in template.sections}
 visible_index=0
 for sid in template.section_order or list(cfgs):
  cfg=cfgs[sid]; entries=data.get(sid,[])
  if not cfg.enabled or not entries: continue
  container=section_targets[visible_index % 2] if section_targets else doc
  visible_index+=1
  hp=_p(container,cfg.label.upper() if cfg.heading_uppercase else cfg.label,template,template.fonts.heading_pt,cfg.heading_bold,template.fonts.heading_color,before=template.spacing.section_before_pt,after=template.spacing.section_after_pt)
  if cfg.heading_underline:
   for r in hp.runs: r.font.underline=True
  if cfg.horizontal_rule:
   pPr=hp._p.get_or_add_pPr(); from docx.oxml import OxmlElement; from docx.oxml.ns import qn
   borders=OxmlElement('w:pBdr'); bottom=OxmlElement('w:bottom'); bottom.set(qn('w:val'),'single'); bottom.set(qn('w:sz'),str(int(cfg.rule_thickness_pt*8))); bottom.set(qn('w:space'),str(int(cfg.rule_spacing_pt))); bottom.set(qn('w:color'),template.fonts.heading_color.lstrip('#')); borders.append(bottom); pPr.append(borders)
  allowed=set(cfg.allowed_fields) or {'institution','degree','field_of_study','start_date','end_date','details','category','skills','title','technologies','bullets','url','organization','location','issuer','date'}
  if sid=='skills':
   for e in entries[:cfg.max_items]:
    category=e.category if 'category' in allowed else ''
    skills=', '.join(e.skills) if 'skills' in allowed else ''
    text=(category+(': ' if category and skills else '')+skills).strip()
    if text: _p(container,text,template)
  elif sid=='education':
   for e in entries[:cfg.max_items]:
    institution=e.institution if 'institution' in allowed else ''
    dates=_dates(e.start_date if 'start_date' in allowed else None,e.end_date if 'end_date' in allowed else None)
    if institution: _date(container,institution,dates,template)
    degree='; '.join(x for x in [e.degree if 'degree' in allowed else None,e.field_of_study if 'field_of_study' in allowed else None] if x)
    if degree: _p(container,degree,template,template.fonts.body_pt,after=1)
    if e.location and 'location' in allowed: _p(container,e.location,template,template.fonts.small_pt)
    if 'details' in allowed:
     for d in e.details: _bullet(container,d,template)
  elif sid in ('projects','experience'):
   for e in entries[:cfg.max_items]:
    if sid=='projects':
     title=e.title if 'title' in allowed else ''
     dates=_dates(e.start_date if 'start_date' in allowed else None,e.end_date if 'end_date' in allowed else None)
     if title: _date(container,title,dates,template)
     if e.technologies and 'technologies' in allowed: _p(container,'Technologies: '+', '.join(e.technologies),template,template.fonts.small_pt)
     if e.url and 'url' in allowed: _p(container,str(e.url),template,template.fonts.small_pt)
    else:
     title=e.title if 'title' in allowed else ''; organization=e.organization if 'organization' in allowed else ''
     dates=_dates(e.start_date if 'start_date' in allowed else None,e.end_date if 'end_date' in allowed else None)
     if title or organization: _date(container,f'{title} — {organization}'.strip(' —'),dates,template)
     if e.location and 'location' in allowed: _p(container,e.location,template,template.fonts.small_pt)
    if 'bullets' in allowed:
     for b in e.bullets[:cfg.max_bullets_per_item]: _bullet(container,b.text,template)
  else:
   for e in entries[:cfg.max_items]:
    if sid=='achievements':
     if 'title' in allowed: _bullet(container,e.title,template)
     if 'details' in allowed:
      for detail in e.details: _bullet(container,detail,template)
     continue
    if sid=='certifications':
     title=e.title if 'title' in allowed else ''; issuer=e.issuer if 'issuer' in allowed else None
     left=title + ((' | '+issuer) if title and issuer else (issuer or ''))
     date=e.date if 'date' in allowed else ''
     if left: _date(container,left,date or '',template)
     elif date: _p(container,date,template,template.fonts.small_pt)
     if 'details' in allowed:
      for detail in e.details: _bullet(container,detail,template)
     continue
    title=e.title if 'title' in allowed else ''
    date=getattr(e,'date',None) if 'date' in allowed else None
    if title: _date(container,title,date or '',template)
    if getattr(e,'issuer',None) and 'issuer' in allowed: _p(container,e.issuer,template,template.fonts.small_pt)
    if getattr(e,'organization',None) and 'organization' in allowed: _p(container,e.organization,template,template.fonts.small_pt)
    if 'details' in allowed:
     for d in getattr(e,'details',[]): _bullet(container,d,template)
 doc.core_properties.title=f'{c.full_name} — Resume'; doc.core_properties.subject=f'ResumeIQ AI template {template.template_id} v{template.version}'; doc.save(out); _fit_to_page(out,template); return out
def _dates(start,end): return f'{start} – {end}' if start and end else (start or end or '')


def _fit_to_page(path: Path, template: TemplateSpec) -> None:
    """Try bounded spacing/font adjustments when LibreOffice is available; never remove content."""
    import shutil, tempfile
    if not (shutil.which('libreoffice') or shutil.which('soffice')):
        return
    from app.services.templates.pdf import convert_docx_to_pdf, PDFConversionError
    import pdfplumber
    minimum_body=float(template.fit_adjustments.get('min_body_pt',template.fonts.body_pt))
    minimum_after=float(template.fit_adjustments.get('min_paragraph_after_pt',0))
    for _ in range(10):
        try:
            with tempfile.TemporaryDirectory(prefix='resumeiq-fit-') as temp:
                pdf=convert_docx_to_pdf(path,temp)
                with pdfplumber.open(pdf) as parsed:
                    pages=len(parsed.pages)
        except (PDFConversionError, Exception):
            return
        if pages <= template.max_pages:
            return
        doc=Document(path); changed=False
        for paragraph in doc.paragraphs:
            fmt=paragraph.paragraph_format
            if fmt.space_after is not None and fmt.space_after.pt > minimum_after:
                fmt.space_after=Pt(max(minimum_after,fmt.space_after.pt-.5)); changed=True
            for run in paragraph.runs:
                size=run.font.size.pt if run.font.size else template.fonts.body_pt
                if size <= template.fonts.body_pt+.1 and size > minimum_body:
                    run.font.size=Pt(max(minimum_body,size-.25)); changed=True
        if not changed:
            return
        doc.save(path)
