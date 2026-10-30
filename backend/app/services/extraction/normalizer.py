import re
from typing import Any
from pydantic import ValidationError
from app.schemas.resume import (
    ResumeJSON,
    ContactInfo,
    EducationEntry,
    SkillGroup,
    ResumeBullet,
    ProjectEntry,
    ExperienceEntry,
    SimpleEntry,
    ActivityEntry,
)

def _clean_str(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None

def _clean_url(val: Any) -> str | None:
    s = _clean_str(val)
    if not s:
        return None
    s = re.sub(r"^(github|linkedin|portfolio)\s*:\s*", "", s, flags=re.I).strip()
    if not s.startswith("http://") and not s.startswith("https://"):
        s = "https://" + s.lstrip("/")
    return s

def _clean_bullets(val: Any) -> list[ResumeBullet]:
    if not val:
        return []
    result: list[ResumeBullet] = []
    if isinstance(val, str):
        lines = [line.strip().lstrip("•-*▪ ") for line in val.split("\n") if line.strip()]
        for line in lines:
            if line:
                result.append(ResumeBullet(text=line[:300]))
    elif isinstance(val, list):
        for item in val:
            if isinstance(item, str) and item.strip():
                clean_t = item.strip().lstrip("•-*▪ ")
                if clean_t:
                    result.append(ResumeBullet(text=clean_t[:300]))
            elif isinstance(item, dict):
                t = _clean_str(item.get("text") or item.get("bullet") or item.get("point") or item.get("description"))
                if t:
                    result.append(ResumeBullet(text=t[:300], source_reference=_clean_str(item.get("source_reference"))))
    return result

def _clean_tech_list(val: Any) -> list[str]:
    if not val:
        return []
    if isinstance(val, str):
        return [t.strip() for t in re.split(r"[,|;•]", val) if t.strip()]
    if isinstance(val, list):
        out = []
        for x in val:
            if isinstance(x, str):
                parts = [t.strip() for t in re.split(r"[,|;•]", x) if t.strip()]
                out.extend(parts)
            elif x:
                out.append(str(x).strip())
        return out
    return []

def _split_date_range(val: Any) -> tuple[str | None, str | None]:
    s = _clean_str(val)
    if not s:
        return None, None
    parts = re.split(r"\s*(?:–|-|to)\s*", s, maxsplit=1)
    if len(parts) == 2:
        return _clean_str(parts[0]), _clean_str(parts[1])
    return s, None

class ResumeNormalizer:
    """
    Deterministic Normalization service:
    Takes loose or imperfectly structured data (from LLMs or parsers)
    and maps known field variations into the canonical ResumeJSON schema.
    Strictly forbids inventing facts or metrics.
    """
    @classmethod
    def normalize(cls, raw: dict[str, Any]) -> ResumeJSON:
        if not isinstance(raw, dict):
            raise ValueError("Input to normalizer must be a dictionary.")

        # 1. Contact normalization
        contact_raw = raw.get("contact") or raw.get("personal_information") or raw.get("personal_info") or raw
        full_name = _clean_str(
            contact_raw.get("full_name")
            or contact_raw.get("name")
            or contact_raw.get("candidate_name")
            or "Candidate"
        )
        email = _clean_str(contact_raw.get("email"))
        phone = _clean_str(contact_raw.get("phone") or contact_raw.get("mobile") or contact_raw.get("cell"))
        location = _clean_str(contact_raw.get("location") or contact_raw.get("address") or contact_raw.get("city"))

        github_raw = contact_raw.get("github_url") or contact_raw.get("github")
        linkedin_raw = contact_raw.get("linkedin_url") or contact_raw.get("linkedin")
        portfolio_raw = contact_raw.get("portfolio_url") or contact_raw.get("portfolio") or contact_raw.get("website")

        contact = ContactInfo(
            full_name=full_name or "Candidate",
            email=email,
            phone=phone,
            location=location,
            github_url=_clean_url(github_raw),
            linkedin_url=_clean_url(linkedin_raw),
            portfolio_url=_clean_url(portfolio_raw),
        )

        # 2. Summary
        summary = _clean_str(raw.get("summary") or raw.get("profile") or raw.get("about") or raw.get("objective"))

        # 3. Skills normalization
        skills_out: list[SkillGroup] = []
        skills_raw = raw.get("skills") or raw.get("technical_skills") or raw.get("skills_list")
        if isinstance(skills_raw, list):
            for item in skills_raw:
                if isinstance(item, dict):
                    cat = _clean_str(item.get("category") or item.get("name") or "Skills") or "Skills"
                    skills_list = _clean_tech_list(item.get("skills") or item.get("items") or item.get("values"))
                    if skills_list:
                        skills_out.append(SkillGroup(category=cat, skills=skills_list))
                elif isinstance(item, str) and item.strip():
                    # Formatted as "Languages : Python, C++"
                    if ":" in item:
                        cat_part, skills_part = item.split(":", 1)
                        skills_out.append(SkillGroup(category=cat_part.strip(), skills=_clean_tech_list(skills_part)))
                    else:
                        skills_out.append(SkillGroup(category="General", skills=[item.strip()]))
        elif isinstance(skills_raw, dict):
            for cat, val in skills_raw.items():
                cat_clean = _clean_str(cat) or "Skills"
                skills_out.append(SkillGroup(category=cat_clean, skills=_clean_tech_list(val)))

        # 4. Education normalization
        education_out: list[EducationEntry] = []
        edu_raw = raw.get("education") or raw.get("academics") or raw.get("qualifications") or []
        if isinstance(edu_raw, list):
            for item in edu_raw:
                if not isinstance(item, dict):
                    continue
                inst = _clean_str(item.get("institution") or item.get("school") or item.get("college") or item.get("university"))
                if not inst:
                    continue
                degree = _clean_str(item.get("degree"))
                field = _clean_str(item.get("field_of_study") or item.get("major") or item.get("branch"))
                start = _clean_str(item.get("start_date") or item.get("start"))
                end = _clean_str(item.get("end_date") or item.get("end") or item.get("year"))
                if not start and not end and item.get("date_range"):
                    start, end = _split_date_range(item.get("date_range"))
                loc = _clean_str(item.get("location") or item.get("city"))
                details_raw = item.get("details") or item.get("grade") or item.get("cgpa") or item.get("score")
                details: list[str] = []
                if isinstance(details_raw, list):
                    details = [_clean_str(d) for d in details_raw if _clean_str(d)]
                elif isinstance(details_raw, str) and details_raw.strip():
                    details = [details_raw.strip()]
                education_out.append(EducationEntry(
                    institution=inst,
                    degree=degree,
                    field_of_study=field,
                    start_date=start,
                    end_date=end,
                    location=loc,
                    details=details,
                ))

        # 5. Experience / Internships normalization
        exp_out: list[ExperienceEntry] = []
        exp_raw = raw.get("experience") or raw.get("internships") or raw.get("work_experience") or []
        if isinstance(exp_raw, list):
            for item in exp_raw:
                if not isinstance(item, dict):
                    continue
                title = _clean_str(item.get("title") or item.get("role") or item.get("position") or "Intern")
                org = _clean_str(item.get("organization") or item.get("company") or item.get("employer") or item.get("firm") or "Organization")
                loc = _clean_str(item.get("location"))
                start = _clean_str(item.get("start_date") or item.get("start"))
                end = _clean_str(item.get("end_date") or item.get("end"))
                if not start and not end and item.get("date_range"):
                    start, end = _split_date_range(item.get("date_range"))
                bullets = _clean_bullets(item.get("bullets") or item.get("description") or item.get("responsibilities"))
                exp_out.append(ExperienceEntry(
                    title=title or "Role",
                    organization=org or "Organization",
                    location=loc,
                    start_date=start,
                    end_date=end,
                    bullets=bullets,
                ))

        # 6. Projects normalization
        proj_out: list[ProjectEntry] = []
        proj_raw = raw.get("projects") or raw.get("personal_projects") or []
        if isinstance(proj_raw, list):
            for item in proj_raw:
                if not isinstance(item, dict):
                    continue
                title = _clean_str(item.get("title") or item.get("name") or "Project")
                techs = _clean_tech_list(item.get("technologies") or item.get("tools") or item.get("tech_stack"))
                bullets = _clean_bullets(item.get("bullets") or item.get("description") or item.get("details"))
                url = _clean_url(item.get("url") or item.get("github") or item.get("link"))
                start = _clean_str(item.get("start_date"))
                end = _clean_str(item.get("end_date"))
                if not start and not end and item.get("date_range"):
                    start, end = _split_date_range(item.get("date_range"))
                proj_out.append(ProjectEntry(
                    title=title or "Project",
                    technologies=techs,
                    bullets=bullets,
                    url=url,
                    start_date=start,
                    end_date=end,
                ))

        # 7. Certifications normalization
        cert_out: list[SimpleEntry] = []
        cert_raw = raw.get("certifications") or raw.get("certificates") or []
        if isinstance(cert_raw, list):
            for item in cert_raw:
                if isinstance(item, str) and item.strip():
                    cert_out.append(SimpleEntry(title=item.strip()[:300]))
                elif isinstance(item, dict):
                    t = _clean_str(item.get("title") or item.get("name") or "Certificate")
                    if t:
                        issuer = _clean_str(item.get("issuer") or item.get("organization") or item.get("platform"))
                        d = _clean_str(item.get("date") or item.get("year"))
                        details = _clean_tech_list(item.get("details"))
                        cert_out.append(SimpleEntry(title=t[:300], issuer=issuer, date=d, details=details))

        # 8. Achievements normalization
        ach_out: list[SimpleEntry] = []
        ach_raw = raw.get("achievements") or raw.get("awards") or raw.get("honors") or []
        if isinstance(ach_raw, list):
            for item in ach_raw:
                if isinstance(item, str) and item.strip():
                    ach_out.append(SimpleEntry(title=item.strip()[:300]))
                elif isinstance(item, dict):
                    t = _clean_str(item.get("title") or item.get("description") or "Achievement")
                    if t:
                        issuer = _clean_str(item.get("issuer"))
                        d = _clean_str(item.get("date") or item.get("year"))
                        details = _clean_tech_list(item.get("details"))
                        ach_out.append(SimpleEntry(title=t[:300], issuer=issuer, date=d, details=details))

        # 9. Extracurricular normalization
        act_out: list[ActivityEntry] = []
        act_raw = raw.get("extracurricular_activities") or raw.get("extracurricular") or raw.get("activities") or []
        if isinstance(act_raw, list):
            for item in act_raw:
                if isinstance(item, str) and item.strip():
                    act_out.append(ActivityEntry(title=item.strip()[:300]))
                elif isinstance(item, dict):
                    t = _clean_str(item.get("title") or item.get("role") or "Activity")
                    if t:
                        org = _clean_str(item.get("organization"))
                        d = _clean_str(item.get("date"))
                        details = _clean_tech_list(item.get("details"))
                        act_out.append(ActivityEntry(title=t[:300], organization=org, date=d, details=details))

        candidate = {
            "contact": contact.model_dump(mode="json"),
            "summary": summary,
            "skills": [s.model_dump(mode="json") for s in skills_out],
            "education": [e.model_dump(mode="json") for e in education_out],
            "experience": [e.model_dump(mode="json") for e in exp_out],
            "projects": [p.model_dump(mode="json") for p in proj_out],
            "certifications": [c.model_dump(mode="json") for c in cert_out],
            "achievements": [a.model_dump(mode="json") for a in ach_out],
            "extracurricular_activities": [a.model_dump(mode="json") for a in act_out],
        }

        return ResumeJSON.model_validate(candidate)

