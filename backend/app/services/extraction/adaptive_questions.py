from typing import Any
from app.schemas.resume import ResumeJSON
from app.schemas.template import TemplateSpec
from app.schemas.questions import AdaptiveQuestion, MissingInformationReport

class AdaptiveQuestionEngine:
    """
    Adaptive Information Collection Service:
    Compares normalized ResumeJSON against the selected TemplateSpecification.
    Identifies missing required fields, incomplete entries, and ambiguous information,
    generating targeted questions without asking for already known facts.
    """
    @classmethod
    def generate_questions(
        cls,
        resume: ResumeJSON,
        template: TemplateSpec,
        resume_id: int,
    ) -> MissingInformationReport:
        questions: list[AdaptiveQuestion] = []
        missing_required = 0
        missing_optional = 0

        # 1. Contact checks
        c = resume.contact
        if not c.email:
            missing_required += 1
            questions.append(
                AdaptiveQuestion(
                    field_path="contact.email",
                    section_id="contact",
                    question="What is your primary email address?",
                    input_type="text",
                    required=True,
                    help_text="Required for interview scheduling and contact placement.",
                )
            )
        if not c.phone:
            missing_required += 1
            questions.append(
                AdaptiveQuestion(
                    field_path="contact.phone",
                    section_id="contact",
                    question="What is your contact phone / mobile number?",
                    input_type="text",
                    required=True,
                    help_text="Format: +91-XXXXXXXXXX or your international format.",
                )
            )

        # Template contact layout check
        if template.contact_layout == "two-column":
            if not c.linkedin_url:
                missing_required += 1
                questions.append(
                    AdaptiveQuestion(
                        field_path="contact.linkedin_url",
                        section_id="contact",
                        question="What is your LinkedIn profile URL?",
                        input_type="url",
                        required=True,
                        help_text="The selected template displays LinkedIn in the top contact grid.",
                    )
                )
            if not c.github_url:
                missing_optional += 1
                questions.append(
                    AdaptiveQuestion(
                        field_path="contact.github_url",
                        section_id="contact",
                        question="What is your GitHub profile URL?",
                        input_type="url",
                        required=False,
                        help_text="Displays in the contact header for technical roles.",
                    )
                )

        # 2. Check sections according to TemplateSpecification
        template_sections = {s.id: s for s in template.sections if s.enabled}

        # Education
        edu_spec = template_sections.get("education")
        if edu_spec:
            if not resume.education and edu_spec.required:
                missing_required += 1
                questions.append(
                    AdaptiveQuestion(
                        field_path="education",
                        section_id="education",
                        question="Please provide your highest educational qualification (institution, degree, graduation year).",
                        input_type="textarea",
                        required=True,
                        help_text="The selected template requires an Education section.",
                    )
                )
            else:
                for idx, entry in enumerate(resume.education):
                    if not entry.degree and not entry.field_of_study:
                        missing_required += 1
                        questions.append(
                            AdaptiveQuestion(
                                field_path=f"education.{idx}.degree",
                                section_id="education",
                                question=f"What degree/major did you pursue at {entry.institution}?",
                                input_type="text",
                                required=True,
                                current_value=entry.degree,
                            )
                        )
                    if not entry.end_date and not entry.start_date:
                        missing_optional += 1
                        questions.append(
                            AdaptiveQuestion(
                                field_path=f"education.{idx}.end_date",
                                section_id="education",
                                question=f"What is your graduation or completion date/year for {entry.institution}?",
                                input_type="text",
                                required=False,
                                help_text="e.g. 'Aug 2024 – Present' or '2024'",
                            )
                        )

        # Skills
        skills_spec = template_sections.get("skills")
        if skills_spec:
            if not resume.skills and skills_spec.required:
                missing_required += 1
                questions.append(
                    AdaptiveQuestion(
                        field_path="skills",
                        section_id="skills",
                        question="What are your core technical skills and tools?",
                        input_type="textarea",
                        required=True,
                        help_text="e.g. Languages: Python, JavaScript; Frameworks: React, FastAPI.",
                    )
                )

        # Projects
        proj_spec = template_sections.get("projects")
        if proj_spec and not resume.projects:
            if proj_spec.required:
                missing_required += 1
            else:
                missing_optional += 1
            questions.append(
                AdaptiveQuestion(
                    field_path="projects",
                    section_id="projects",
                    question="Please list at least one key project you have built or worked on.",
                    input_type="textarea",
                    required=proj_spec.required,
                    help_text="Include project title, tech stack, and key accomplishments.",
                )
            )
        elif proj_spec:
            for idx, proj in enumerate(resume.projects):
                    if not proj.technologies:
                        missing_optional += 1
                        questions.append(
                            AdaptiveQuestion(
                                field_path=f"projects.{idx}.technologies",
                                section_id="projects",
                                question=f"Which technologies / libraries did you use in '{proj.title}'?",
                                input_type="text",
                                required=False,
                                help_text="Comma-separated list (e.g. React, Python, PostgreSQL).",
                            )
                        )
                    if not proj.bullets:
                        missing_required += 1
                        questions.append(
                            AdaptiveQuestion(
                                field_path=f"projects.{idx}.bullets",
                                section_id="projects",
                                question=f"Describe what you built and achieved in '{proj.title}'.",
                                input_type="textarea",
                                required=True,
                                help_text="Bullet points detailing system architecture, features, or impact.",
                            )
                        )

        # Experience
        exp_spec = template_sections.get("experience")
        if exp_spec and exp_spec.required and not resume.experience:
            missing_required += 1
            questions.append(
                AdaptiveQuestion(
                    field_path="experience",
                    section_id="experience",
                    question=f"Please provide your internship or work experience for the {exp_spec.label} section.",
                    input_type="textarea",
                    required=True,
                )
            )

        is_complete = missing_required == 0

        return MissingInformationReport(
            resume_id=resume_id,
            template_id=template.template_id,
            is_complete=is_complete,
            missing_required_count=missing_required,
            missing_optional_count=missing_optional,
            questions=questions,
        )

    @classmethod
    def apply_answers(cls, resume: ResumeJSON, answers: dict[str, Any]) -> ResumeJSON:
        """
        Incorporate user answers into canonical ResumeJSON deterministically.
        """
        data = resume.model_dump(mode="json")

        for path, val in answers.items():
            if val is None or str(val).strip() == "":
                continue

            parts = path.split(".")
            if parts[0] == "contact" and len(parts) == 2:
                field = parts[1]
                if field in data["contact"]:
                    data["contact"][field] = str(val).strip()
            elif parts[0] == "projects" and len(parts) == 3:
                try:
                    idx = int(parts[1])
                    field = parts[2]
                    if 0 <= idx < len(data["projects"]):
                        if field == "technologies":
                            if isinstance(val, list):
                                data["projects"][idx]["technologies"] = val
                            else:
                                data["projects"][idx]["technologies"] = [
                                    t.strip() for t in str(val).split(",") if t.strip()
                                ]
                        elif field == "bullets":
                            if isinstance(val, str):
                                lines = [line.strip().lstrip("•-*▪ ") for line in val.split("\n") if line.strip()]
                                data["projects"][idx]["bullets"] = [{"text": l} for l in lines]
                        elif field == "url":
                            data["projects"][idx]["url"] = str(val).strip()
                except (ValueError, IndexError):
                    pass
            elif parts[0] == "education" and len(parts) == 3:
                try:
                    idx = int(parts[1])
                    field = parts[2]
                    if 0 <= idx < len(data["education"]):
                        data["education"][idx][field] = str(val).strip()
                except (ValueError, IndexError):
                    pass

        return ResumeJSON.model_validate(data)
