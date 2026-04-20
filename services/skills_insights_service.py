"""
Aggregate in-demand skills from the local jobs database.

Uses structured skills from job_cache when the description hash matches;
otherwise falls back to keyword scanning of job_description.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

# Longer phrases first so "node.js" wins over "node", "react native" over "react", etc.
_DESCRIPTION_SKILL_PHRASES: Tuple[str, ...] = tuple(
    sorted(
        {
            ".net",
            "asp.net",
            "amazon web services",
            "angular",
            "ansible",
            "apache kafka",
            "aws",
            "azure",
            "bash",
            "c#",
            "c++",
            "ci/cd",
            "circleci",
            "cloudformation",
            "css",
            "databricks",
            "django",
            "docker",
            "elasticsearch",
            "elixir",
            "fastapi",
            "flask",
            "gcp",
            "git",
            "github actions",
            "gitlab",
            "golang",
            "graphql",
            "grpc",
            "hadoop",
            "html",
            "javascript",
            "jenkins",
            "jest",
            "kafka",
            "kubernetes",
            "linux",
            "mongodb",
            "mysql",
            "next.js",
            "nginx",
            "node.js",
            "nodejs",
            "nosql",
            "numpy",
            "pandas",
            "php",
            "postgresql",
            "postgres",
            "powershell",
            "pyspark",
            "python",
            "pytorch",
            "react native",
            "react.js",
            "react",
            "redis",
            "redux",
            "ruby on rails",
            "ruby",
            "rust",
            "scala",
            "scikit-learn",
            "selenium",
            "snowflake",
            "spark",
            "spring boot",
            "spring",
            "sql",
            "sqlite",
            "swift",
            "tableau",
            "tailwind",
            "tensorflow",
            "terraform",
            "typescript",
            "vue.js",
            "vue",
        },
        key=len,
        reverse=True,
    )
)

_DISPLAY_ALIASES = {
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "react.js": "React",
    "vue.js": "Vue",
    "next.js": "Next.js",
    "asp.net": "ASP.NET",
    "amazon web services": "AWS",
    "golang": "Go",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "scikit-learn": "scikit-learn",
    "ci/cd": "CI/CD",
    "github actions": "GitHub Actions",
    "ruby on rails": "Ruby on Rails",
    "apache kafka": "Kafka",
    "react native": "React Native",
}

_PLACEHOLDER_SKILLS = frozenset(
    {
        "",
        "string",
        "n/a",
        "na",
        "none",
        "tbd",
        "example",
        "skills",
        "technical skills",
    }
)


def _md5_hex(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _normalize_skill_label(raw: str) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    low = s.lower()
    if low in _PLACEHOLDER_SKILLS:
        return None
    if len(s) > 80:
        return None
    canon = low.rstrip(".")
    display = _DISPLAY_ALIASES.get(canon, s.strip())
    return display


def _skills_from_job_json(job_json: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    skills = job_json.get("skills")
    if isinstance(skills, list):
        for item in skills:
            label = _normalize_skill_label(item)
            if label:
                out.append(label)
    return out


def _compile_description_matcher() -> re.Pattern:
    escaped = [re.escape(p.strip()) for p in _DESCRIPTION_SKILL_PHRASES if p.strip()]
    # word boundaries; allow + and # inside token
    parts = []
    for e in escaped:
        if e.replace("\\", "") in (".NET", "C\\#", "C\\+\\+"):
            parts.append(rf"(?<![A-Za-z0-9#+]){e}(?![A-Za-z0-9#+])")
        else:
            parts.append(rf"\b{e}\b")
    return re.compile("|".join(parts), re.IGNORECASE)


_DESC_SKILL_RE = _compile_description_matcher()


def _skills_from_description(text: str) -> List[str]:
    if not text or not isinstance(text, str):
        return []
    found: Set[str] = set()
    for m in _DESC_SKILL_RE.finditer(text):
        raw = m.group(0).strip()
        label = _normalize_skill_label(raw)
        if label:
            low = label.lower()
            key = _DISPLAY_ALIASES.get(low, label)
            found.add(key)
    return sorted(found, key=lambda x: x.lower())


def _generalize_job_title(title: Optional[str]) -> str:
    t = (title or "").lower()
    if not t.strip():
        return "Unknown title"
    if any(
        k in t
        for k in (
            "devops",
            "sre",
            "site reliability",
            "platform engineer",
            "infrastructure engineer",
            "cloud engineer",
        )
    ):
        return "DevOps / SRE / Platform"
    if any(
        k in t
        for k in (
            "data scientist",
            "machine learning",
            "ml engineer",
            "ai engineer",
            "deep learning",
            "nlp engineer",
            "computer vision",
        )
    ):
        return "Data / ML / AI"
    if any(k in t for k in ("data engineer", "etl", "analytics engineer")):
        return "Data engineering / Analytics"
    if any(k in t for k in ("frontend", "front-end", "front end", "ui engineer", "react developer")):
        return "Frontend"
    if any(k in t for k in ("backend", "back-end", "back end", "api engineer")):
        return "Backend"
    if "full stack" in t or "fullstack" in t or "full-stack" in t:
        return "Full stack"
    if any(k in t for k in ("mobile", "ios", "android", "react native")):
        return "Mobile"
    if any(k in t for k in ("qa", "quality assurance", "test engineer", "sdet")):
        return "QA / Test"
    if any(
        k in t
        for k in (
            "manager",
            "director",
            "head of",
            "vp ",
            "vice president",
            "lead",
            "principal",
            "staff ",
        )
    ):
        return "Leadership / Staff+"
    if "security" in t or "cyber" in t:
        return "Security"
    if "software" in t and "engineer" in t:
        return "Software engineering (general)"
    if "developer" in t:
        return "Developer (general)"
    return "Other / mixed"


def _clean_display_title(title: Optional[str]) -> str:
    if not title:
        return "Unknown title"
    s = " ".join(str(title).split())
    return s[:120] if len(s) > 120 else s


def _load_skill_union_by_description_hash(conn: sqlite3.Connection) -> Dict[str, Set[str]]:
    """Union skills from all cache rows sharing the same job description hash."""
    out: Dict[str, Set[str]] = defaultdict(set)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT job_description_hash, job_json
            FROM job_cache
            WHERE job_description_hash IS NOT NULL AND job_description_hash != ''
            """
        )
        for h, blob in cur.fetchall():
            if not h or not blob:
                continue
            try:
                data = json.loads(blob)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            for s in _skills_from_job_json(data):
                out[h].add(s)
    except sqlite3.OperationalError:
        pass
    return dict(out)


def compute_skills_insights(
    config_dict: Dict[str, Any],
    *,
    include_hidden: bool = False,
    top_skills: int = 50,
    top_titles: int = 30,
    per_group_skills: int = 20,
    min_jobs_for_title: int = 2,
) -> Dict[str, Any]:
    """
    Build skill frequency tables overall, by coarse role bucket, and by specific job title.

    Returns a JSON-serializable dict.
    """
    db_path = config_dict.get("db_path", "./data/my_database.db")
    table = config_dict.get("jobs_tablename", "jobs")
    where_clause = "" if include_hidden else " WHERE (hidden = 0 OR hidden IS NULL)"

    conn = sqlite3.connect(db_path)
    try:
        cache_union = _load_skill_union_by_description_hash(conn)
        cur = conn.cursor()
        cur.execute(f'PRAGMA table_info("{table}")')
        col_names = [r[1] for r in cur.fetchall()]
        has_source = "source" in col_names
        fields = "id, title, job_description" + (", source" if has_source else "")
        cur.execute(f'SELECT {fields} FROM "{table}"{where_clause}')
        rows = cur.fetchall()
    finally:
        conn.close()

    overall: Counter[str] = Counter()
    by_bucket: Dict[str, Counter[str]] = defaultdict(Counter)
    by_title: Dict[str, Counter[str]] = defaultdict(Counter)
    title_job_counts: Counter[str] = Counter()
    bucket_job_counts: Counter[str] = Counter()
    source_stats: Counter[str] = Counter()

    jobs_with_structured = 0
    jobs_with_fallback = 0
    jobs_no_desc = 0
    jobs_with_any_skill = 0

    def counter_to_list(c: Counter[str], n: int) -> List[Dict[str, Any]]:
        return [{"skill": k, "job_count": int(v)} for k, v in c.most_common(n)]

    for row in rows:
        if has_source:
            _jid, title, job_description, source = row
            source_stats[(source or "unknown").strip() or "unknown"] += 1
        else:
            _jid, title, job_description = row

        desc = (job_description or "").strip()
        if not desc:
            jobs_no_desc += 1
            continue

        dh = _md5_hex(desc)
        structured = cache_union.get(dh)
        if structured:
            skill_list = sorted(structured)
            if skill_list:
                jobs_with_structured += 1
            else:
                skill_list = _skills_from_description(desc)
                if skill_list:
                    jobs_with_fallback += 1
        else:
            skill_list = _skills_from_description(desc)
            if skill_list:
                jobs_with_fallback += 1

        bucket = _generalize_job_title(title)
        disp_title = _clean_display_title(title)
        title_job_counts[disp_title] += 1

        if not skill_list:
            continue

        jobs_with_any_skill += 1
        bucket_job_counts[bucket] += 1
        for sk in skill_list:
            overall[sk] += 1
            by_bucket[bucket][sk] += 1
            by_title[disp_title][sk] += 1

    title_summaries: List[Dict[str, Any]] = []
    for t, cnt in title_job_counts.most_common(top_titles * 3):
        if cnt < min_jobs_for_title:
            continue
        if not by_title[t]:
            continue
        title_summaries.append(
            {
                "title": t,
                "job_count": int(cnt),
                "top_skills": counter_to_list(by_title[t], per_group_skills),
            }
        )
        if len(title_summaries) >= top_titles:
            break

    bucket_names = set(by_bucket.keys()) | set(bucket_job_counts.keys())
    bucket_summaries = [
        {
            "bucket": name,
            "job_count": int(bucket_job_counts[name]),
            "top_skills": counter_to_list(by_bucket[name], per_group_skills),
        }
        for name in sorted(bucket_names, key=lambda b: (-bucket_job_counts[b], b))
    ]

    return {
        "meta": {
            "jobs_scanned": len(rows),
            "jobs_with_description": len(rows) - jobs_no_desc,
            "jobs_with_at_least_one_skill_tag": jobs_with_any_skill,
            "jobs_structured_skills": jobs_with_structured,
            "jobs_keyword_skills_only": jobs_with_fallback,
            "jobs_empty_description": jobs_no_desc,
            "distinct_descriptions_in_job_cache": len(cache_union),
        },
        "overall_top_skills": counter_to_list(overall, top_skills),
        "by_role_bucket": bucket_summaries,
        "by_job_title": title_summaries,
        "by_source": [{"source": k, "job_count": int(v)} for k, v in source_stats.most_common()],
    }
