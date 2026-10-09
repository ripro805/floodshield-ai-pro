"""Approved medical grounding corpus used by chatbot and retrieval.

The full corpus lives in the `knowledge_articles` table (seeded from
`data/medical_knowledge_base_fixed.xlsx` on backend startup).  This module
provides:

- `MEDICAL_KNOWLEDGE_BASE`: a compact string form of the corpus, used as a
  fallback when the DB query fails (e.g. during cold-start before the
  seeder completes).  Mirrors the original 6-disease grounding text the
  chatbot was built around.
- `get_articles_from_db(db)`: fetch the live corpus from the DB.
- `format_articles_as_text(articles)`: serialise the DB rows into the
  block-of-text shape the Anthropic prompt expects.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.reference_models import KnowledgeArticle

MEDICAL_KNOWLEDGE_BASE = """
Disease Information Base:
1. Cholera: Symptoms: severe watery diarrhea, vomiting, dehydration. Causes: contaminated water/food. Prevention: safe water, hygiene, vaccines. Home Care: oral rehydration. When to see doctor: always. Emergency Contact: 999.
2. Diarrhea: Symptoms: loose stools, abdominal cramps, dehydration. Causes: bacterial, viral, food. Prevention: hygiene, safe food handling. Home Care: oral rehydration. When to see doctor: if severe/persistent. Emergency Contact: 999.
3. Typhoid: Symptoms: high fever, weakness, abdominal pain, rose spots. Causes: Salmonella bacteria, contaminated food/water. Prevention: vaccination, hygiene. Home Care: rest, fluids. When to see doctor: immediately. Emergency Contact: 999.
4. Dengue: Symptoms: sudden fever, headache, muscle pain, rash. Causes: Aedes mosquito. Prevention: mosquito control, nets. Home Care: rest, fever management. When to see doctor: if fever persists >7 days. Emergency Contact: 999.
5. Hepatitis A: Symptoms: jaundice, fatigue, abdominal pain, dark urine. Causes: contaminated food/water. Prevention: hygiene, vaccination. Home Care: rest, avoid alcohol. When to see doctor: if jaundice appears. Emergency Contact: 999.
6. Skin Disease: Symptoms: rash, itching, lesions, discoloration. Causes: fungal, bacterial, allergic. Prevention: hygiene, avoid contaminated surfaces. Home Care: keep clean/dry. When to see doctor: if spreading. Emergency Contact: 999.
"""


def get_articles_from_db(db: Session) -> list[KnowledgeArticle]:
    """Fetch every medical grounding article from the DB."""
    return list(db.query(KnowledgeArticle).order_by(KnowledgeArticle.disease_name).all())


def format_articles_as_text(articles: list[KnowledgeArticle]) -> str:
    """Serialise a list of KnowledgeArticle rows into the legacy single-
    string format the Anthropic prompt expects."""
    if not articles:
        return MEDICAL_KNOWLEDGE_BASE
    lines = ["Disease Information Base:"]
    for idx, art in enumerate(articles, start=1):
        lines.append(
            f"{idx}. {art.disease_name}: "
            f"Symptoms: {art.symptoms}. "
            f"Causes: {art.causes or 'N/A'}. "
            f"Prevention: {art.prevention_tips or 'N/A'}. "
            f"Home Care: {art.home_care_guidance or 'N/A'}. "
            f"When to see doctor: {art.when_to_see_doctor or 'N/A'}. "
            f"Emergency Contact: {art.emergency_contact_info or '999'}."
        )
    return "\n".join(lines)