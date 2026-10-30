from typing import Any, Literal
from pydantic import Field, model_validator
from app.schemas.resume import StrictModel

class PageMargins(StrictModel):
    top_in: float = Field(default=0.55, ge=0.2, le=1.5)
    bottom_in: float = Field(default=0.55, ge=0.2, le=1.5)
    left_in: float = Field(default=0.65, ge=0.2, le=1.5)
    right_in: float = Field(default=0.65, ge=0.2, le=1.5)

class FontSpec(StrictModel):
    family: str = Field(default="Arial", min_length=1, max_length=80)
    name_pt: float = Field(default=20, ge=12, le=36)
    heading_pt: float = Field(default=11, ge=8, le=22)
    body_pt: float = Field(default=9.5, ge=7, le=14)
    small_pt: float = Field(default=8, ge=6, le=12)
    heading_color: str = Field(default="#172554", pattern=r"^#[0-9A-Fa-f]{6}$")
    body_color: str = Field(default="#111827", pattern=r"^#[0-9A-Fa-f]{6}$")

class SpacingSpec(StrictModel):
    line_spacing: float = Field(default=1.0, ge=0.8, le=2.0)
    paragraph_before_pt: float = Field(default=0.0, ge=0.0, le=24.0)
    paragraph_after_pt: float = Field(default=2.0, ge=0.0, le=24.0)
    section_before_pt: float = Field(default=7.0, ge=0.0, le=30.0)
    section_after_pt: float = Field(default=3.0, ge=0.0, le=18.0)

class SectionSpec(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    label: str = Field(min_length=1, max_length=80)
    heading: str | None = Field(default=None, max_length=80)
    required: bool = False
    order: int = 0
    repeatable: bool = True
    enabled: bool = True
    heading_uppercase: bool = True
    heading_bold: bool = True
    heading_underline: bool = False
    horizontal_rule: bool = False
    rule_thickness_pt: float = Field(default=0.5, ge=0.1, le=3.0)
    rule_spacing_pt: float = Field(default=2.0, ge=0.0, le=12.0)
    max_items: int = Field(default=20, ge=0, le=100)
    max_bullets_per_item: int = Field(default=6, ge=0, le=30)
    allowed_fields: list[str] = Field(default_factory=list, max_length=30)
    field_mappings: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def sync_label_and_heading(self):
        if not self.heading and self.label:
            self.heading = self.label
        elif self.heading and not self.label:
            self.label = self.heading
        return self

class TemplateSpec(StrictModel):
    template_id: str = Field(pattern=r"^[a-z0-9-]+$", min_length=2, max_length=80)
    template_name: str | None = Field(default=None, max_length=120)
    version: str = "1.0.0"
    file_type: Literal["docx", "pdf", "builtin"] = "builtin"
    display_name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    page_size: Literal["A4", "LETTER"] = "A4"
    orientation: Literal["portrait", "landscape"] = "portrait"
    margins: PageMargins = Field(default_factory=PageMargins)
    fonts: FontSpec = Field(default_factory=FontSpec)
    spacing: SpacingSpec = Field(default_factory=SpacingSpec)
    section_order: list[str] = Field(default_factory=list, max_length=20)
    sections: list[SectionSpec] = Field(default_factory=list, max_length=20)
    bullet_character: Literal["•", "–", "-", "▪"] = "•"
    bullet_left_indent_in: float = Field(default=0.18, ge=0.0, le=0.8)
    bullet_first_line_indent_in: float = Field(default=-0.12, ge=-0.5, le=0.0)
    date_tab_position_in: float = Field(default=6.9, ge=3.0, le=10.0)
    contact_separator: str = Field(default=" | ", max_length=10)
    header_alignment: Literal["left", "center"] = "center"
    header_uppercase: bool = False
    contact_layout: Literal["inline", "two-column"] = "inline"
    contact_labels: bool = False
    allow_photo: bool = False
    max_pages: int = Field(default=2, ge=1, le=5)
    layout: Literal["single-column", "two-column"] = "single-column"
    fit_adjustments: dict[str, float] = Field(
        default_factory=lambda: {
            "min_body_pt": 8.0,
            "max_body_pt": 11.0,
            "min_paragraph_after_pt": 0.0,
            "max_paragraph_after_pt": 6.0,
        }
    )
    validation_rules: dict[str, Any] = Field(default_factory=dict)
    notes_and_uncertainty: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def sync_name(self):
        if not self.template_name:
            self.template_name = self.display_name
        return self

    @model_validator(mode="after")
    def refs(self):
        ids = [s.id for s in self.sections]
        if len(ids) != len(set(ids)):
            raise ValueError("Section IDs must be unique")
        if len(self.section_order) != len(set(self.section_order)):
            raise ValueError("Section order must be unique")
        if set(self.section_order) - set(ids):
            raise ValueError("section_order references unknown section")
        if any(not 0 <= v <= 36 for v in self.fit_adjustments.values()):
            raise ValueError("fit adjustment out of range")
        if self.fit_adjustments.get("min_body_pt", 0) > self.fit_adjustments.get("max_body_pt", 36):
            raise ValueError("minimum body size cannot exceed maximum body size")
        if self.fit_adjustments.get("min_paragraph_after_pt", 0) > self.fit_adjustments.get("max_paragraph_after_pt", 36):
            raise ValueError("minimum paragraph spacing cannot exceed maximum")
        width, height = (8.27, 11.69) if self.page_size == "A4" else (8.5, 11.0)
        usable = (height if self.orientation == "landscape" else width) - self.margins.left_in - self.margins.right_in
        if self.date_tab_position_in > usable:
            raise ValueError("date tab stop must fit within usable page width")
        if self.allow_photo:
            raise ValueError("Photo placement is not supported by this renderer; set allow_photo=false")
        return self

# Explicit alias for template specification
TemplateSpecification = TemplateSpec
