"""
Skills insights: aggregate skills from the local jobs database.
"""
from flask import Blueprint, render_template, jsonify, request, current_app

from services.skills_insights_service import compute_skills_insights

skills_insights_bp = Blueprint("skills_insights", __name__)


@skills_insights_bp.route("/skills_insights")
def skills_insights_page():
    return render_template("skills_insights.html")


@skills_insights_bp.route("/api/skills_insights")
def api_skills_insights():
    config = current_app.config["CONFIG"]
    include_hidden = request.args.get("include_hidden", "false").lower() == "true"

    def _int_arg(name: str, default: int, lo: int, hi: int) -> int:
        try:
            v = int(request.args.get(name, default))
        except (TypeError, ValueError):
            v = default
        return max(lo, min(hi, v))

    top_skills = _int_arg("top_skills", 50, 5, 200)
    top_titles = _int_arg("top_titles", 30, 5, 100)
    per_group = _int_arg("per_group", 20, 5, 80)
    min_jobs_title = _int_arg("min_jobs_title", 2, 1, 50)

    payload = compute_skills_insights(
        config,
        include_hidden=include_hidden,
        top_skills=top_skills,
        top_titles=top_titles,
        per_group_skills=per_group,
        min_jobs_for_title=min_jobs_title,
    )
    return jsonify(payload)
