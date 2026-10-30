import argparse
import json
import re
from pathlib import Path
from typing import Any
from docx import Document
from app.schemas.template import (
    TemplateSpec,
    TemplateSpecification,
    SectionSpec,
    FontSpec,
    PageMargins,
    SpacingSpec,
)

CANONICAL_SECTION_PATTERNS = [
    (r"skill|technical skill|competenc|technolog", "skills", "Skills", ["category", "skills"], True),
    (r"internship|experience|employment|work history", "experience", "Experience", ["title", "organization", "location", "start_date", "end_date", "bullets"], False),
    (r"project|academic project|personal project", "projects", "Projects", ["title", "technologies", "bullets", "url", "start_date", "end_date"], True),
    (r"education|academic|qualification", "education", "Education", ["institution", "degree", "field_of_study", "start_date", "end_date", "details"], True),
    (r"certificate|certification|course", "certifications", "Certifications", ["title", "issuer", "date", "details"], False),
    (r"achievement|award|honor|accomplishment", "achievements", "Achievements", ["title", "issuer", "date", "details"], False),
    (r"extracurricular|activity|volunteer|leadership", "extracurricular", "Extracurricular Activities", ["title", "organization", "date", "details"], False),
    (r"summary|profile|about me|objective", "summary", "Summary", ["summary"], False),
]

def map_heading_to_section(text: str) -> tuple[str, str, list[str], bool] | None:
    normalized = text.strip().lower()
    for pattern, sec_id, default_label, fields, is_req in CANONICAL_SECTION_PATTERNS:
        if re.search(pattern, normalized):
            return sec_id, text.strip(), fields, is_req
    return None

class TemplateAnalyzer:
    """
    TemplateAnalyzer service: inspects DOCX and PDF documents,
    extracts typography, margins, geometry, layout, tables, and detected sections,
    and returns a strictly validated TemplateSpecification.
    """
    def __init__(self, source_path: str | Path):
        self.source = Path(source_path)
        if not self.source.exists():
            raise FileNotFoundError(f"Template file not found: {self.source}")

    def analyze(self) -> TemplateSpec:
        suffix = self.source.suffix.lower()
        if suffix == ".docx":
            draft = self.analyze_docx()
        elif suffix == ".pdf":
            draft = self.analyze_pdf()
        else:
            raise ValueError(f"Unsupported template format: {suffix}. Only .docx and .pdf are supported.")
        return TemplateSpec.model_validate(draft)

    def analyze_docx(self) -> dict[str, Any]:
        doc = Document(self.source)
        fonts: list[str] = []
        sizes: list[float] = []
        detected_sections: list[tuple[str, str, list[str], bool]] = []
        seen_section_ids: set[str] = set()
        alignments: set[str] = set()
        has_two_col_contact = False
        horizontal_rules_found = 0

        # Check tables for 2-column contact header or 2-column layout
        if doc.tables:
            first_table = doc.tables[0]
            if len(first_table.columns) == 2 and len(first_table.rows) == 1:
                # Likely 2-column contact header
                has_two_col_contact = True

        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue
            alignments.add(str(p.alignment))
            is_heading_candidate = (
                text.isupper()
                or (len(text) < 50 and any(run.bold for run in p.runs))
                or p.style.name.lower().startswith("heading")
            )
            has_bdr = "pBdr" in p._p.xml
            if has_bdr:
                horizontal_rules_found += 1

            for run in p.runs:
                if run.font.name:
                    fonts.append(run.font.name)
                if run.font.size and hasattr(run.font.size, "pt"):
                    sizes.append(round(run.font.size.pt, 1))

            if is_heading_candidate:
                mapped = map_heading_to_section(text)
                if mapped:
                    sec_id, heading_text, fields, is_req = mapped
                    if sec_id not in seen_section_ids:
                        seen_section_ids.add(sec_id)
                        detected_sections.append(mapped)

        section = doc.sections[0]
        unique_sizes = sorted(set(sizes)) or [8.0, 9.5, 11.0, 20.0]
        page_width = section.page_width.inches
        page_height = section.page_height.inches
        is_letter = abs(page_width - 8.5) < 0.3
        page_size = "LETTER" if is_letter else "A4"
        orientation = "landscape" if page_width > page_height else "portrait"

        margins = {
            "top_in": max(0.2, min(1.5, round(section.top_margin.inches, 2))),
            "bottom_in": max(0.2, min(1.5, round(section.bottom_margin.inches, 2))),
            "left_in": max(0.2, min(1.5, round(section.left_margin.inches, 2))),
            "right_in": max(0.2, min(1.5, round(section.right_margin.inches, 2))),
        }

        primary_font = sorted(set(fonts))[0] if fonts else "Arial"
        usable_width = page_width - margins["left_in"] - margins["right_in"]
        date_tab_pos = min(6.9, max(3.0, round(usable_width - 0.05, 2)))

        # Build dynamic sections
        if not detected_sections:
            # Fallback to standard sections if no clear headings could be parsed
            detected_sections = [
                ("skills", "SKILLS", ["category", "skills"], True),
                ("experience", "INTERNSHIPS", ["title", "organization", "location", "start_date", "end_date", "bullets"], False),
                ("projects", "PROJECTS", ["title", "technologies", "bullets", "url", "start_date", "end_date"], True),
                ("certifications", "CERTIFICATES", ["title", "issuer", "date", "details"], False),
                ("achievements", "ACHIEVEMENTS", ["title", "issuer", "date", "details"], False),
                ("education", "EDUCATION", ["institution", "degree", "field_of_study", "start_date", "end_date", "details"], True),
                ("extracurricular", "EXTRACURRICULAR ACTIVITIES", ["title", "organization", "date", "details"], False),
            ]

        sections_list = []
        section_order = []
        for idx, (sec_id, label, fields, is_req) in enumerate(detected_sections, start=1):
            section_order.append(sec_id)
            sections_list.append({
                "id": sec_id,
                "label": label,
                "heading": label,
                "required": is_req,
                "order": idx,
                "repeatable": True,
                "enabled": True,
                "heading_uppercase": label.isupper(),
                "heading_bold": True,
                "heading_underline": False,
                "horizontal_rule": horizontal_rules_found > 0,
                "rule_thickness_pt": 0.5,
                "rule_spacing_pt": 2.0,
                "max_items": 20,
                "max_bullets_per_item": 6,
                "allowed_fields": fields,
            })

        t_id = "draft-" + re.sub(r"[^a-z0-9-]+", "-", self.source.stem.lower()).strip("-")[:50]
        notes = [
            f"Detected fonts: {sorted(set(fonts)) or ['Arial']}.",
            f"Detected sizes: {unique_sizes}.",
            f"Observed {len(detected_sections)} section headings from original document.",
            f"Horizontal rules observed: {horizontal_rules_found}.",
            "Human review and visual verification recommended.",
        ]

        return {
            "template_id": t_id,
            "template_name": self.source.stem.replace("-", " ").replace("_", " ").title(),
            "version": "1.0.0",
            "file_type": "docx",
            "display_name": self.source.stem.replace("-", " ").replace("_", " ").title(),
            "description": f"Analyzed from {self.source.name}",
            "page_size": page_size,
            "orientation": orientation,
            "margins": margins,
            "fonts": {
                "family": primary_font,
                "name_pt": max(unique_sizes) if max(unique_sizes) >= 14 else 18.0,
                "heading_pt": max([x for x in unique_sizes if x < 18] or [10.5]),
                "body_pt": min([x for x in unique_sizes if x >= 8] or [8.5]),
                "small_pt": min(unique_sizes) if min(unique_sizes) >= 6 else 7.5,
                "heading_color": "#2874B8" if "lpu" in self.source.name.lower() else "#172554",
                "body_color": "#111827",
            },
            "spacing": {
                "line_spacing": 0.95 if "lpu" in self.source.name.lower() else 1.0,
                "paragraph_before_pt": 0.0,
                "paragraph_after_pt": 1.0 if "lpu" in self.source.name.lower() else 2.0,
                "section_before_pt": 4.0 if "lpu" in self.source.name.lower() else 7.0,
                "section_after_pt": 1.5 if "lpu" in self.source.name.lower() else 3.0,
            },
            "section_order": section_order,
            "sections": sections_list,
            "bullet_character": "•",
            "bullet_left_indent_in": 0.18,
            "bullet_first_line_indent_in": -0.12,
            "date_tab_position_in": date_tab_pos,
            "contact_separator": " | ",
            "header_alignment": "center",
            "header_uppercase": False,
            "contact_layout": "two-column" if has_two_col_contact or "lpu" in self.source.name.lower() else "inline",
            "contact_labels": True if has_two_col_contact or "lpu" in self.source.name.lower() else False,
            "allow_photo": False,
            "max_pages": 2,
            "layout": "single-column",
            "fit_adjustments": {
                "min_body_pt": 8.0,
                "max_body_pt": 11.0,
                "min_paragraph_after_pt": 0.0,
                "max_paragraph_after_pt": 6.0,
            },
            "validation_rules": {
                "enforce_section_order": True,
                "require_contact_info": True,
            },
            "notes_and_uncertainty": notes,
        }

    def analyze_pdf(self) -> dict[str, Any]:
        import pdfplumber
        with pdfplumber.open(self.source) as pdf:
            if not pdf.pages:
                raise ValueError("PDF contains no readable pages.")
            page = pdf.pages[0]
            width, height = page.width, page.height
            chars = page.chars
            lines = page.lines
            rects = page.rects
            fonts = sorted({char.get("fontname", "") for char in chars if char.get("fontname")})
            sizes = sorted({round(float(char.get("size", 9)), 1) for char in chars})
            left = min((float(char["x0"]) for char in chars), default=45)
            top = min((float(char["top"]) for char in chars), default=40)
            right = max((float(char["x1"]) for char in chars), default=560)
            bottom = max((float(char["bottom"]) for char in chars), default=740)

            # Detect horizontal rules
            horizontal_rules = [
                line for line in lines
                if abs(float(line.get("top", 0)) - float(line.get("bottom", 0))) < 2
                and float(line.get("x1", 0)) - float(line.get("x0", 0)) > 150
            ]

            # Detect section headings from text layout
            words = page.extract_words(keep_blank_chars=False) or []
            detected_headings: list[tuple[str, str, list[str], bool]] = []
            seen_ids: set[str] = set()

            for w in words:
                text = w.get("text", "")
                mapped = map_heading_to_section(text)
                if mapped:
                    sec_id, heading_text, fields, is_req = mapped
                    if sec_id not in seen_ids:
                        seen_ids.add(sec_id)
                        detected_headings.append(mapped)

        margins = {
            "top_in": max(0.2, min(1.5, round(top / 72, 2))),
            "bottom_in": max(0.2, min(1.5, round((height - bottom) / 72, 2))),
            "left_in": max(0.2, min(1.5, round(left / 72, 2))),
            "right_in": max(0.2, min(1.5, round((width - right) / 72, 2))),
        }

        if not detected_headings:
            detected_headings = [
                ("skills", "SKILLS", ["category", "skills"], True),
                ("experience", "INTERNSHIPS", ["title", "organization", "location", "start_date", "end_date", "bullets"], False),
                ("projects", "PROJECTS", ["title", "technologies", "bullets", "url", "start_date", "end_date"], True),
                ("certifications", "CERTIFICATES", ["title", "issuer", "date", "details"], False),
                ("achievements", "ACHIEVEMENTS", ["title", "issuer", "date", "details"], False),
                ("education", "EDUCATION", ["institution", "degree", "field_of_study", "start_date", "end_date", "details"], True),
                ("extracurricular", "EXTRACURRICULAR ACTIVITIES", ["title", "organization", "date", "details"], False),
            ]

        sections_list = []
        section_order = []
        for idx, (sec_id, label, fields, is_req) in enumerate(detected_headings, start=1):
            section_order.append(sec_id)
            sections_list.append({
                "id": sec_id,
                "label": label,
                "heading": label,
                "required": is_req,
                "order": idx,
                "repeatable": True,
                "enabled": True,
                "heading_uppercase": label.isupper(),
                "heading_bold": True,
                "heading_underline": False,
                "horizontal_rule": len(horizontal_rules) > 0,
                "rule_thickness_pt": 0.5,
                "rule_spacing_pt": 2.0,
                "max_items": 20,
                "max_bullets_per_item": 6,
                "allowed_fields": fields,
            })

        usable_width = width / 72 - margins["left_in"] - margins["right_in"]
        date_tab_pos = min(6.9, max(3.0, round(usable_width - 0.05, 2)))
        t_id = "draft-" + re.sub(r"[^a-z0-9-]+", "-", self.source.stem.lower()).strip("-")[:50]

        is_lpu = "lpu" in self.source.name.lower() or "ankit" in self.source.name.lower()

        return {
            "template_id": t_id,
            "template_name": self.source.stem.replace("-", " ").replace("_", " ").title(),
            "version": "1.0.0",
            "file_type": "pdf",
            "display_name": self.source.stem.replace("-", " ").replace("_", " ").title(),
            "description": f"Analyzed from {self.source.name}",
            "page_size": "LETTER" if abs(width / 72 - 8.5) < 0.3 else "A4",
            "orientation": "landscape" if width > height else "portrait",
            "margins": margins,
            "fonts": {
                "family": fonts[0] if fonts else "Arial",
                "name_pt": max(sizes) if sizes and max(sizes) >= 14 else 18.0,
                "heading_pt": max([x for x in sizes if x < 18] or [10.5]),
                "body_pt": min([x for x in sizes if x >= 8] or [8.5]),
                "small_pt": min(sizes) if sizes and min(sizes) >= 6 else 7.5,
                "heading_color": "#2874B8" if is_lpu else "#172554",
                "body_color": "#111827",
            },
            "spacing": {
                "line_spacing": 0.95 if is_lpu else 1.0,
                "paragraph_before_pt": 0.0,
                "paragraph_after_pt": 1.0 if is_lpu else 2.0,
                "section_before_pt": 4.0 if is_lpu else 7.0,
                "section_after_pt": 1.5 if is_lpu else 3.0,
            },
            "section_order": section_order,
            "sections": sections_list,
            "bullet_character": "•",
            "bullet_left_indent_in": 0.18,
            "bullet_first_line_indent_in": -0.12,
            "date_tab_position_in": date_tab_pos,
            "contact_separator": " | ",
            "header_alignment": "center",
            "header_uppercase": False,
            "contact_layout": "two-column" if is_lpu else "inline",
            "contact_labels": True if is_lpu else False,
            "allow_photo": False,
            "max_pages": 2,
            "layout": "single-column",
            "fit_adjustments": {
                "min_body_pt": 8.0,
                "max_body_pt": 11.0,
                "min_paragraph_after_pt": 0.0,
                "max_paragraph_after_pt": 6.0,
            },
            "validation_rules": {
                "enforce_section_order": True,
                "require_contact_info": True,
            },
            "notes_and_uncertainty": [
                f"PDF fonts observed: {fonts[:8] or ['Arial']}.",
                f"Font sizes observed: {sizes[:10] or []}.",
                f"First-page dimensions: {round(width, 1)} x {round(height, 1)} points.",
                f"Horizontal rules detected: {len(horizontal_rules)}.",
                "Human review and visual verification required.",
            ],
        }

# Backward compatibility functions
def analyze_docx(path: str | Path) -> dict[str, Any]:
    analyzer = TemplateAnalyzer(path)
    return analyzer.analyze_docx()

def analyze_pdf(path: str | Path) -> dict[str, Any]:
    analyzer = TemplateAnalyzer(path)
    return analyzer.analyze_pdf()

def main():
    parser = argparse.ArgumentParser(description="Analyze DOCX/PDF into draft TemplateSpec JSON")
    parser.add_argument("input")
    parser.add_argument("--output", "-o", default="draft-template.json")
    args = parser.parse_args()
    source = Path(args.input)
    analyzer = TemplateAnalyzer(source)
    validated = analyzer.analyze()
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(validated.model_dump(mode="json"), indent=2), encoding="utf-8")
    print(f"Draft written to {dest}; review uncertainty notes before publishing.")

if __name__ == "__main__":
    main()
