#!/usr/bin/env python3
"""Render all pages of every template and compare against golden PNGs.
Requires LibreOffice, pdftoppm, Pillow, and backend requirements.
Use --update intentionally to regenerate the baselines.
"""
import argparse, subprocess, sys
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.schemas.resume import ResumeJSON
from app.schemas.template import TemplateSpec
from app.services.templates.renderer import render_resume
from app.services.templates.pdf import convert_docx_to_pdf
parser=argparse.ArgumentParser();parser.add_argument('--update',action='store_true',help='Overwrite golden PNG baselines intentionally');args=parser.parse_args()
GOLDEN=ROOT/'visual_regression'/'golden';GOLDEN.mkdir(parents=True,exist_ok=True)
DATA=ResumeJSON.model_validate_json((ROOT/'sample_data'/'reference_resume.json').read_text())
OUT=ROOT/'artifacts'/'visual-regression';OUT.mkdir(parents=True,exist_ok=True)
failures=[]
for tid in ('lpu-standard','ats-clean','modern-one-page'):
 spec=TemplateSpec.model_validate_json((ROOT/'template_specs'/f'{tid}.json').read_text())
 docx=render_resume(DATA,spec,OUT/f'{tid}.docx');pdf=convert_docx_to_pdf(docx,OUT)
 prefix=OUT/tid
 subprocess.run(['pdftoppm','-png','-r','110',str(pdf),str(prefix)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 page_paths=sorted(OUT.glob(f'{tid}-*.png'),key=lambda p:int(p.stem.rsplit('-',1)[-1]))
 pages=[Image.open(p).convert('RGB') for p in page_paths]
 if not pages: failures.append(f'{tid}: no rendered page images');continue
 gap=24;width=max(im.width for im in pages);height=sum(im.height for im in pages)+gap*(len(pages)-1)
 combined=Image.new('RGB',(width,height),(255,255,255));y=0
 for im in pages: combined.paste(im,(0,y));y+=im.height+gap
 golden=GOLDEN/f'{tid}.png'
 if args.update or not golden.exists(): combined.save(golden);print(f'Updated golden: {golden.relative_to(ROOT)}');continue
 current=combined;base=Image.open(golden).convert('RGB')
 if current.size!=base.size:
  failures.append(f'{tid}: image dimensions changed from {base.size} to {current.size}');continue
 diff=ImageChops.difference(base,current);mean=sum(ImageStat.Stat(diff).mean)/3/255
 import numpy as np
 changed=float((np.asarray(diff)>35).any(axis=2).mean())
 print(f'{tid}: mean pixel difference={mean:.4f}; changed pixels={changed:.1%}; pages={len(pages)}')
 if mean>.12 or changed>.30: failures.append(f'{tid}: visual difference exceeds tolerance')
if failures:
 print('Visual regression failures:');print('\n'.join(failures));sys.exit(1)
print('Visual regression completed.')
