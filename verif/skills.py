"""
Skills discovery, parsing, matching, and extraction.

Skills are the SDK's cross-run memory. On-disk format:
  skills/{name}/skill.md   — YAML frontmatter (manifest) + markdown (approach)
  skills/{name}/script.py  — parameterized, tested functions
"""

from pathlib import Path

from .config import SkillMatch


def build_skill_index(skills_dir: str) -> str:
    """Scan skills_dir for skill.md files, build one-line-per-skill index for prompt injection."""
    import yaml

    base = Path(skills_dir)
    if not base.is_dir():
        return ""
    entries = []
    for skill_md in sorted(base.rglob("skill.md")):
        try:
            text = skill_md.read_text()
            if not text.startswith("---"):
                continue
            _, fm, _ = text.split("---", 2)
            data = yaml.safe_load(fm)
            name = data.get("name", skill_md.parent.name)
            desc = data.get("description", "")
            stype = data.get("type", "utility")
            params = data.get("parameters", {})
            param_str = ", ".join(params.keys()) if params else ""
            rel = skill_md.parent.relative_to(base)
            entry = f"- {name} [{stype}]: {desc}"
            if param_str:
                entry += f" (params: {param_str})"
            entry += f" → {rel}/"
            entries.append(entry)
        except Exception:
            continue
    if not entries:
        return ""
    return f"\n\n## Available Skills (in {skills_dir})\n" + "\n".join(entries) + "\n"


def parse_skills(skills_dir: str) -> list[SkillMatch]:
    """Parse all skills from skills_dir into SkillMatch objects."""
    import yaml

    base = Path(skills_dir)
    if not base.is_dir():
        return []
    skills = []
    for skill_md in sorted(base.rglob("skill.md")):
        try:
            text = skill_md.read_text()
            if not text.startswith("---"):
                continue
            _, fm, body = text.split("---", 2)
            data = yaml.safe_load(fm)
            skills.append(SkillMatch(
                name=data.get("name", skill_md.parent.name),
                type=data.get("type", "utility"),
                description=data.get("description", ""),
                approach=body.strip(),
                dir_path=str(skill_md.parent),
            ))
        except Exception:
            continue
    return skills


def extract_rubric(approach: str) -> str | None:
    """Extract rubric criteria from a workflow skill's approach section."""
    lines = approach.split("\n")
    rubric_lines = []
    in_rubric = False
    for line in lines:
        if "rubric" in line.lower() and ("criteria" in line.lower() or line.startswith("#")):
            in_rubric = True
            continue
        if in_rubric:
            if line.startswith("#") and "rubric" not in line.lower():
                break
            if line.strip():
                rubric_lines.append(line)
    return "\n".join(rubric_lines) if rubric_lines else None


def inject_skill(prompt: str, skill_name: str, skills_dir: str) -> str:
    """Read skill files and append to delegate prompt."""
    if not skills_dir:
        return prompt
    skill_dir = Path(skills_dir) / skill_name
    parts = [prompt, f"\n\n## Skill: {skill_name}"]
    skill_md = skill_dir / "skill.md"
    if skill_md.exists():
        parts.append(skill_md.read_text())
    script = skill_dir / "script.py"
    if script.exists():
        parts.append(f"\n### script.py\n```python\n{script.read_text()}\n```")
    return "\n".join(parts)
