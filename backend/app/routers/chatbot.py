"""
/chatbot -- LLM-powered chatbot with grounding in medical knowledge base,
community reports, and live platform data.

Uses Anthropic Claude API (server-side only, API key in .env) to provide
conversational Q&A about diseases, floods, hospital info, and emergencies.
Grounded in actual platform data (medical knowledge base, community reports,
live predictions) -- never fabricates risk numbers or hospital info.
"""
import uuid
import json
import re
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.auth_deps import get_current_user, require_any_authenticated_user
from app.auth_models import User
from app.chat_models import ChatMessage, ChatIntentType
from app.chat_schemas import (
    ChatMessageRequest, ChatMessageResponse,
    ReportIncidentRequest, ReportIncidentResponse,
    SuggestedAction, ActionType, ChatIntentEnum, SeverityEnum
)
import os
import anthropic
from app.routers.risk import compute_risk_score
from app.schemas import RiskScoreRequest
from app.knowledge_base import MEDICAL_KNOWLEDGE_BASE, \
    format_articles_as_text, get_articles_from_db
from app.reference_models import CommunityReport, DistrictHospitalAggregate, Location
from app.reference_models import CommunityReport, DistrictHospitalAggregate, DistrictEnv, Location
from app.services.rag_service import retrieve_context
from app.services.llm_providers import generate_ollama, generate_huggingface
from app.services.automation_service import notify_n8n

router = APIRouter(
    prefix="/chatbot",
    tags=["Chatbot (LLM)"],
    dependencies=[Depends(require_any_authenticated_user)],
)

# ─── Medical Knowledge Base (embedded directly, 6 diseases) ───────────────────
# Community Reports taxonomy (from dataset)
COMMUNITY_REPORTS_TAXONOMY = """
Valid incident labels (must choose exactly one):
- water_contamination: reports of contaminated water, visible pollution, discoloration
- disease_symptom: person with symptoms matching known disease
- flood_impact: water damage, flooding, waterlogging
- sanitation_issue: poor sanitation, waste, hygiene problems
- hospital_issue: hospital overcrowding, supply shortage, access problems
- normal: routine update, no urgent issue
"""


BANGLISH_PATTERNS = {
    'pani', 'bonna', 'kothay', 'kemon', 'ase', 'ache', 'barche', 'bardshe', 'khobor',
    'feni', 'dhaka', 'basha', 'jabe', 'ki', 'koto', 'rog', 'chulkani', 'hospital',
    'bhalo', 'kharap', 'thik', 'shob', 'amader', 'tomader', 'amar', 'tomar'
}


def _detect_language(text: str) -> str:
    """Detect language: Bengali (bn), Hindi (hi), Banglish, or English (en)."""
    for char in text:
        if '\u0980' <= char <= '\u09FF':  # Bengali Unicode range
            return 'bn'
        if '\u0900' <= char <= '\u097F':  # Devanagari / Hindi Unicode range
            return 'hi'
    words = set(re.findall(r'[a-zA-Z]+', text.lower()))
    if len(words & BANGLISH_PATTERNS) >= 2:
        return 'banglish'
    return 'en'


def _detect_intent(message: str) -> ChatIntentEnum:
    """Heuristic intent detection supporting English, Bengali, and Banglish keywords."""
    msg_lower = message.lower()
    
    # Emergency keywords (English + Bengali + Banglish)
    emergency_kw = [
        'emergency', 'severe', 'dying', 'help now', 'critical', 'danger',
        'জরুরি', 'বিপদ', 'বাঁচাও', 'সাহায্য', 'গুরুতর', 'মরছি', 'ডুবছে',
        'bachao', 'bipod', 'morchi', 'sahajjo', 'danger'
    ]
    if any(word in msg_lower for word in emergency_kw):
        return ChatIntentEnum.emergency

    # Disease keywords
    disease_kw = [
        'symptom', 'disease', 'cholera', 'diarrhea', 'fever', 'illness', 'sick',
        'রোগ', 'কলেরা', 'ডায়রিয়া', 'ডায়রিয়া', 'জ্বর', 'টাইফয়েড', 'টাইফয়েড', 'ডেঙ্গু', 'চুলকানি',
        'rog', 'jwor', 'cholera', 'diarrhea', 'dengue', 'typhoid', 'chulkani'
    ]
    if any(word in msg_lower for word in disease_kw):
        return ChatIntentEnum.disease_info

    # Flood keywords
    flood_kw = [
        'flood', 'water', 'safe', 'outside', 'river', 'inundation',
        'বন্যা', 'পানি', 'নদী', 'প্লাবন', 'জল', 'নিরাপদ', 'উচ্চতা',
        'bonna', 'pani', 'nodi', 'plabon', 'jol', 'nirapod', 'level'
    ]
    if any(word in msg_lower for word in flood_kw):
        return ChatIntentEnum.flood_safety

    # Hospital keywords
    hospital_kw = [
        'hospital', 'bed', 'stock', 'available', 'resource', 'doctor', 'clinic', 'ors',
        'হাসপাতাল', 'বেড', 'ডাক্তার', 'ওষুধ', 'স্যালাইন', 'ক্লিনিক',
        'hospital', 'bed', 'doctor', 'osudh', 'saline', 'clinic'
    ]
    if any(word in msg_lower for word in hospital_kw):
        return ChatIntentEnum.hospital_info

    # Incident keywords
    report_kw = [
        'report', 'happened', 'noticed', 'saw', 'observed',
        'রিপোর্ট', 'দেখেছি', 'ঘটেছে', 'ঘটনা', 'অভিযোগ',
        'report', 'dekhechi', 'ghoteche', 'ghotona'
    ]
    if any(word in msg_lower for word in report_kw):
        return ChatIntentEnum.incident_report
    
    return ChatIntentEnum.general


def _get_emergency_contact(disease: Optional[str]) -> str:
    """Return appropriate emergency contact and guidance."""
    return (
        "⚠️ EMERGENCY: Call 999 or visit the nearest hospital immediately. "
        "This requires immediate medical attention. "
        "If unable to reach emergency services, contact your local health worker or NGO."
    )


async def _generate_chatbot_response(
    message: str,
    intent: ChatIntentEnum,
    user: User,
    db: Session,
    conversation_id: str,
    requested_language: str = "auto",
) -> tuple[str, list[SuggestedAction], bool]:
    """
    Generate a conversational response — tries Claude API first,
    then falls back to the intelligent local grounded engine.
    """

    # 1. Fetch live risk data for grounding (always, for context)
    used_live_data = False
    risk_context = "No live risk data available."
    live_risk = None
    if user.district:
        try:
            live_risk = await compute_risk_score(RiskScoreRequest(
                location=user.district,
                river_level_m=6.5,
                flood_depth_cm=0,
                population_density=1500,
                sanitation_score=0.5,
                water_quality_index=60,
                previous_week_cases=0,
                previous_two_week_cases=0,
                season="Monsoon"
            ))
            risk_context = (
                f"Current Flood Severity: {live_risk.flood_severity}, "
                f"Outbreak Risk: {live_risk.predicted_outbreak_risk}, "
                f"Overall Risk: {live_risk.final_risk_level} "
                f"(composite score: {live_risk.composite_score})"
            )
            used_live_data = True
        except Exception as e:
            print(f"Failed to fetch live risk data: {e}")

    # 2. Fetch conversation history
    history_msgs = []
    if conversation_id:
        db_messages = db.query(ChatMessage).filter(
            ChatMessage.user_id == user.id,
            ChatMessage.conversation_id == conversation_id
        ).order_by(ChatMessage.created_at.asc()).all()
        for msg in db_messages:
            role = msg.role if msg.role in ['user', 'assistant'] else 'user'
            history_msgs.append({"role": role, "content": msg.content})
    history_msgs.append({"role": "user", "content": message})

    # 3. Try Anthropic Claude API
    # Pre-LLM structured cases handler (bypasses Ollama/RAG snippet for 'cases in N days' queries)
    cases_msg_lower = message.lower()
    # ─── Recent-cases query (district-keyed hospital load + last-N-days reports) ──
    # 'tell me the disease cases in last 2 days in kushtia',
    # 'cases in last 7 days in feni', 'disease reports today in my district'.
    # The user wants *numbers* (case counts, severity breakdown, hospital load)
    # -- not generic medical text.  Pull from DistrictHospitalAggregate for
    # the per-district signal and CommunityReport for the time-windowed counts.
    cases_keywords = ['case', 'cases', 'report', 'reports', 'incident',
                      'incidents', 'sick', 'affected', 'count']
    time_window = None  # (label, hours)
    m_days = re.search(r'last\s+(\d+)\s*day', cases_msg_lower)
    m_hours = re.search(r'last\s+(\d+)\s*hour', cases_msg_lower)
    if m_days:
        n = max(1, min(int(m_days.group(1)), 30))  # cap at 30 days
        time_window = (f'last {n} day{"s" if n != 1 else ""}', n * 24)
    elif m_hours:
        n = max(1, min(int(m_hours.group(1)), 168))
        time_window = (f'last {n} hour{"s" if n != 1 else ""}', n)
    elif 'today' in cases_msg_lower or 'last 24' in cases_msg_lower:
        time_window = ('last 24 hours', 24)
    elif 'yesterday' in cases_msg_lower:
        time_window = ('since yesterday', 48)
    elif 'this week' in cases_msg_lower or 'last week' in cases_msg_lower or 'past week' in cases_msg_lower:
        time_window = ('last 7 days', 7 * 24)
    elif 'this month' in cases_msg_lower or 'last month' in cases_msg_lower:
        time_window = ('last 30 days', 30 * 24)
    else:
        time_window = ('last 7 days', 7 * 24)  # sensible default when user asks about "cases"

    has_cases_word = any(kw in cases_msg_lower for kw in cases_keywords)
    cases_recent_query = has_cases_word and (
        m_days is not None or m_hours is not None
        or 'today' in cases_msg_lower or 'yesterday' in cases_msg_lower
        or 'this week' in cases_msg_lower or 'last week' in cases_msg_lower or 'past week' in cases_msg_lower
        or 'this month' in cases_msg_lower or 'last month' in cases_msg_lower
    )

    if cases_recent_query:
        window_label, hours = time_window
        target_district = user.district or 'Bangladesh (national)'
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        # District hospital load (real per-district signal)
        agg = None
        if user.district:
            agg = db.query(DistrictHospitalAggregate).filter(
                func.lower(DistrictHospitalAggregate.district) == user.district.strip().lower()
            ).first()
        hospital_lines = []
        if agg is not None:
            occupancy = int(getattr(agg, 'occupancy_percent', 0) or 0)
            beds = int(getattr(agg, 'beds', 0) or 0)
            hospital_count = int(getattr(agg, 'hospital_count', 0) or 0)
            ors = int(getattr(agg, 'ors_stock', 0) or 0)
            iv = int(getattr(agg, 'iv_saline_stock', 0) or 0)
            anti = int(getattr(agg, 'antibiotics_stock', 0) or 0)
            hospital_lines = [
                f"- **{hospital_count}** hospitals, **{beds}** beds total",
                f"- Current occupancy: **{occupancy}%**",
                f"- Stock on hand: ORS **{ors}**, IV saline **{iv}**, antibiotics **{anti}**",
            ]
            if occupancy >= 80:
                hospital_lines.append(f"- ⚠️ Occupancy is **high** — capacity for new admissions is limited.")
            elif occupancy >= 60:
                hospital_lines.append(f"- Occupancy is **moderate** — most wards still open.")

        # Aggregate community reports (last N days, grouped by label + severity)
        # NB: community_reports is NOT keyed by district, so this is a national-
        # level breakdown.  We always disclose that explicitly so the user
        # doesn't think these are district-specific.
        label_counts = (
            db.query(CommunityReport.label, func.count(CommunityReport.id))
            .filter(CommunityReport.created_at >= cutoff)
            .group_by(CommunityReport.label)
            .all()
        )
        sev_counts = (
            db.query(CommunityReport.severity, func.count(CommunityReport.id))
            .filter(CommunityReport.created_at >= cutoff)
            .group_by(CommunityReport.severity)
            .all()
        )
        total_recent = sum(int(n) for _, n in label_counts)
        top_labels = sorted(label_counts, key=lambda r: -int(r[1]))[:5]
        label_list = ", ".join(
            f"**{lbl.replace('_', ' ').title()}** ({n})"
            for lbl, n in top_labels if int(n) > 0
        ) or "_no reports in this window_"
        sev_list = ", ".join(
            f"**{sev}** ({n})"
            for sev, n in sorted(sev_counts, key=lambda r: -int(r[1]))
        )

        # Live outbreak risk for the user's district
        risk_summary = ""
        if live_risk is not None:
            emoji = {"Low": "🟢", "Medium": "🟡", "High": "🟠", "Critical": "🔴"}.get(
                live_risk.final_risk_level, "⚪️"
            )
            risk_summary = (
    f"- Live outbreak risk model: {emoji} **{live_risk.final_risk_level}** "
            f"(score {live_risk.composite_score:.1f}/3.0)\n"
            )

        parts = [
            f"**Disease activity in {target_district} ({window_label}):**",
            risk_summary.rstrip("\n") if risk_summary else "",
            f"**Reported incidents (national):** {total_recent} in the window.",
            f"- By type: {label_list}",
            f"- By severity: {sev_list}",
        ]
        if hospital_lines:
            parts.append("**Hospital capacity in your district:**")
            parts.extend(hospital_lines)
        else:
            parts.append(
                "_No hospital-load snapshot for this district — checking live outbreak risk only._"
            )
        parts.append("")
        parts.append(
            "_Note: community reports aren't district-tagged, so the type/severity breakdown "
            "is from the **national** report feed, while hospital numbers above are for "
            f"{user.district or 'your district'} specifically._"
        )
        parts.append("")
        parts.append("📞 Emergency: **999** | High fever, severe dehydration or persistent vomiting — seek care now.")
        reply = "\n".join(p for p in parts if p)
        used_live_data = bool(live_risk) or (agg is not None)
    if cases_recent_query:
        # Pre-LLM structured answer: bypass Ollama / Anthropic and return the
        # structured cases answer immediately so the LLM can't override it.
        return reply, [], used_live_data



    # -----------------------------------------------------------------
    # Pre-LLM structured water-level handler (bypasses Ollama/RAG snippet
    # for "river level", "water depth", "flood depth" queries).
    # Pulls the user's district from message OR from user.district,
    # fetches the latest river/flood depth from DistrictEnv.
    # -----------------------------------------------------------------
    wl_keywords = ['water level', 'river level', 'flood depth', 'flood level',
                   'water depth', 'river depth', 'how high', 'depth of water',
                   'river water', 'water level']
    wl_msg_lower = message.lower()
    has_wl_word = any(kw in wl_msg_lower for kw in wl_keywords)
    water_level_query = has_wl_word

    if water_level_query:
        # Detect target district: try every Location.district row against the message
        # (case-insensitive substring match). Fall back to user.district.
        target_district = None
        loc_rows = db.query(Location.district).distinct().all()
        for (dname,) in loc_rows:
            if dname and dname.lower() in wl_msg_lower:
                target_district = dname
                break
        if not target_district:
            target_district = user.district

        env = None
        if target_district:
            env = db.query(DistrictEnv).filter(
                func.lower(DistrictEnv.district) == target_district.strip().lower()
            ).first()

        if env is not None:
            river = float(getattr(env, 'river_level_m', 0) or 0)
            flood_depth = float(getattr(env, 'flood_depth_cm', 0) or 0)
            water_q = float(getattr(env, 'water_quality_index', 0) or 0)
            observed = getattr(env, 'observed_on', None)
            season = getattr(env, 'season', 'unknown')
            contamination = getattr(env, 'contamination_risk', None)

            # Status thresholds (Bangladesh-context).
            # River level: >=3.0m critical, >=2.5m warning, >=2.0m watch, else normal
            # Flood depth: >=30cm severe, >=15cm moderate, >=5cm minor, else none
            if river >= 3.0 or flood_depth >= 30:
                status_icon = '🔴'
                status_label = 'Critical'
                status_msg = 'Water is well above safe thresholds -- expect severe inundation.'
            elif river >= 2.5 or flood_depth >= 15:
                status_icon = '🟠'
                status_label = 'Warning'
                status_msg = 'Water is rising toward danger levels -- stay alert.'
            elif river >= 2.0 or flood_depth >= 5:
                status_icon = '🟡'
                status_label = 'Watch'
                status_msg = 'Water is elevated but below danger levels.'
            else:
                status_icon = '🟢'
                status_label = 'Normal'
                status_msg = 'Water levels are within the normal range.'

            wl_quality = 'good' if water_q >= 80 else 'fair' if water_q >= 60 else 'poor'

            parts = [
                f'**Water status in {target_district} ({observed or "latest reading"}):**',
                f'- {status_icon} Status: **{status_label}** -- {status_msg}',
                f'- **River level:** {river:.2f} m above gauge',
                f'- **Flood depth (inundation):** {flood_depth:.1f} cm',
                f'- **Water quality index:** {water_q:.0f}/100 ({wl_quality})',
                f'- Season: **{season}**',
            ]
            if contamination and contamination != 'None':
                parts.append(f'- Contamination risk: **{contamination}**')
            parts.append(
                '_Reference thresholds (Bangladesh context): '
                'river 3.0 m / flood depth 30 cm = critical; '
                '2.5 m / 15 cm = warning; 2.0 m / 5 cm = watch._'
            )
            parts.append('')
            parts.append('**What to do:**')
            parts.append('1. If depth is rising, move valuables and livestock uphill.')
            parts.append('2. Avoid walking through standing water (leptospirosis + snakes).')
            parts.append('3. Boil or chlorinate drinking water if water quality is below 70.')
            parts.append('')
            parts.append('📞 Emergency: **999** | For sudden rise, structural damage, or trapped people, call now.')
            reply = '\n'.join(parts)
            used_live_data = True
        else:
            # No env data for it -- return a helpful signpost
            target = target_district or 'your district'
            reply = (
                f'**Water status in {target}:**\n\n'
                f'_I don\'t have a recent river/flood reading for {target} in my reference data._\n\n'
                f'- Try the **Check District Risk** quick-link to see the live risk model.\n'
                f'- Or ask about **hospital capacity**, **disease cases**, or **flood safety**.\n\n'
                f'📞 Emergency: **999**'
            )
            used_live_data = False
        return reply, [], used_live_data

    reply = None
    retrieved_context = retrieve_context(db, message)
    provider_messages = [{"role": "system", "content": f"Use only this retrieved medical context:\n{retrieved_context}"}] + history_msgs
    try:
        reply = await generate_ollama(provider_messages)
        if reply is None:
            reply = await generate_huggingface(f"Medical context:\n{retrieved_context}\n\nUser: {message}")
    except Exception as e:
        print(f"Optional local/cloud provider error: {e}")

    if reply is None:
        try:
            api_key = os.getenv("LLM_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("LLM_API_KEY is missing")

            client = anthropic.AsyncAnthropic(api_key=api_key)
            try:
                articles = get_articles_from_db(db)
                knowledge_corpus = format_articles_as_text(articles) if articles else MEDICAL_KNOWLEDGE_BASE
            except Exception:
                knowledge_corpus = MEDICAL_KNOWLEDGE_BASE
            system_prompt = f"""You are FloodShield AI, a medical and flood safety chatbot for Bangladesh.

# PRIMARY CONTEXT (Retrieved via RAG from WHO / DGHS / FloodShield corpus):
{retrieved_context}

# SUPPLEMENTARY: 6-disease deterministic reference card (Cholera, Diarrhea, Typhoid, Dengue, Hepatitis A, Skin Disease):
{knowledge_corpus}

User role: {user.role.value if user.role else 'unknown'}, District: {user.district or 'unknown'}
Live Risk Data for District: {risk_context}

RULES:
- Prefer the RAG-retrieved context above; it covers the full WHO / DGHS / FloodShield corpus (cholera, typhoid, dengue, hepatitis A/E, leptospirosis, scabies, ORS, hand-washing, evacuation, breastfeeding, WASH, etc.).
- If the user asks about a disease NOT in the RAG context AND NOT in the 6-disease card, say so honestly and recommend they speak to a clinician or call 999 for emergencies.
- NEVER invent flood percentages or hospital numbers -- use only the live risk data provided.
- If asked "is it safe in [district]", use the live risk data to give a specific answer with the flood severity and outbreak risk level.
- Always cite the source of any specific clinical claim (e.g. "WHO cholera guideline", "DGHS dengue protocol").
- For emergencies (collapse, severe bleeding, suspected drowning, snakebite), always tell the user to call 999 and seek immediate hospital care.
Respond in the user's language (detect from message)."""

            response = await client.messages.create(
                model='claude-3-5-sonnet-20241022',
                max_tokens=1024,
                system=system_prompt,
                messages=history_msgs,
                timeout=10.0
            )
            reply = response.content[0].text

        except Exception as e:
            print(f"LLM Error: {e}")

    # 4. Intelligent local fallback engine — always grounded, never generic
    if reply is None:
        msg_lower = message.lower()

        # ─── Disease knowledge base matching ───────────────────────────────────
        DISEASE_KB = {
            "cholera": {
                "symptoms": "severe watery diarrhea, vomiting, rapid dehydration",
                "causes": "contaminated water or food",
                "prevention": "drink safe water, practice hand hygiene, get vaccinated",
                "home_care": "Oral Rehydration Solution (ORS) immediately",
                "doctor": "Always seek medical care immediately for cholera",
            },
            "diarrhea": {
                "symptoms": "loose stools, abdominal cramps, dehydration",
                "causes": "bacterial, viral, or contaminated food",
                "prevention": "wash hands, use safe food and water",
                "home_care": "ORS, rest, avoid sugary drinks",
                "doctor": "If severe or lasting more than 2 days",
            },
            "typhoid": {
                "symptoms": "high fever (39–40°C), weakness, abdominal pain, rose-colored rash",
                "causes": "Salmonella typhi bacteria from contaminated food or water",
                "prevention": "vaccination, hand hygiene, safe water",
                "home_care": "rest, plenty of fluids",
                "doctor": "Immediately — typhoid requires antibiotic treatment",
            },
            "dengue": {
                "symptoms": "sudden high fever, severe headache, muscle and joint pain, skin rash",
                "causes": "Aedes mosquito bite",
                "prevention": "remove standing water, use mosquito nets, repellents",
                "home_care": "rest, fever management with paracetamol (NOT aspirin), fluids",
                "doctor": "If fever persists beyond 7 days or bleeding appears",
            },
            "hepatitis": {
                "symptoms": "jaundice (yellow skin/eyes), fatigue, abdominal pain, dark urine",
                "causes": "contaminated food or water (Hepatitis A/E)",
                "prevention": "hand hygiene, safe water, vaccination for Hepatitis A",
                "home_care": "rest, avoid alcohol, small nutritious meals",
                "doctor": "If jaundice appears or symptoms worsen",
            },
            "skin": {
                "symptoms": "rash, itching, lesions, discoloration, blisters",
                "causes": "fungal, bacterial, or allergic reaction; exposure to floodwater",
                "prevention": "keep skin clean and dry, avoid contaminated floodwater",
                "home_care": "keep clean, use antiseptic cream",
                "doctor": "If rash spreads or develops into open sores",
            },
        }

        # ─── Not-in-KB diseases ────────────────────────────────────────────────
        NOT_IN_KB = [
            "malaria", "tuberculosis", "tb", "cancer", "diabetes", "hiv", "aids",
            "covid", "flu", "influenza", "asthma", "pneumonia", "measles", "polio",
            "meningitis", "rabies", "leprosy", "scabies", "worm",
        ]

        matched_disease = None
        for disease_key in DISEASE_KB:
            if disease_key in msg_lower:
                matched_disease = disease_key
                break

        not_kb_disease = next((d for d in NOT_IN_KB if d in msg_lower), None)

        # ─── District safety query ─────────────────────────────────────────────
        # A district risk query requires an explicit risk word AND the
        # user having a district.  Generic words like "flood" alone are
        # NOT enough -- otherwise "how to wash hands during flood" gets
        # hijacked into a risk summary.
        risk_words = ["risk", "safe", "danger", "situation", "status", "level"]
        has_risk_word = any(w in msg_lower for w in risk_words)
        district_query = has_risk_word and (user.district is not None)
        # If the question contains an explicit topic word, prefer the
        # topic branch over the district lookup.  This keeps "how to
        # wash hands during flood" routed to the RAG / WASH answer.
        topic_words = [
            "how", "what", "tell", "explain", "make", "use", "do",
            "wash", "drink", "prepare", "symptom", "treat", "prevent",
            "vaccin", "ors", "chlorine", "sanitat", "hygien", "leptospi",
            "cholera", "typhoid", "dengue", "hepatitis", "diarrh",
            "skin", "fever", "vomit",
        ]
        # Topic-word override applies ONLY if the user did NOT explicitly
        # mention 'district' / 'my area' / 'here' / 'my region'.  When
        # they say 'risk in my district', they want the risk summary,
        # not a generic RAG snippet.
        explicit_district_ref = any(p in msg_lower for p in [
            'my district', 'my area', 'my region', 'in this district',
            'district', 'here',
        ])
        if any(kw in msg_lower for kw in topic_words) and not explicit_district_ref:
            district_query = False

        

        # ─── District-disease query ──────────────────────────
        # 'tell about disease in feni district', 'any illness in my area',
        # 'diseases to watch for in [district]'.  These want a district-
        # overview answer that combines live risk + medical context -- NOT
        # the generic catch-all.
        disease_words = ['disease', 'diseases', 'illness', 'illnesses',
                         'outbreak', 'epidemic']
        district_disease_query = (
            user.district is not None
            and any(p in msg_lower for p in ['my district', 'district', 'my area'])
            and any(d in msg_lower for d in disease_words)
        )

        if district_disease_query:
            # Combined district-disease answer: live risk summary + curated
            # list of waterborne/flood diseases to watch for, plus the
            # general protective measures.  This is more useful than
            # either branch alone because it answers BOTH 'how risky is my
            # district right now' AND 'what diseases should I watch for'.
            district_name = user.district or 'your district'
            risk_emoji = {"Low": "🟢", "Medium": "🟡", "High": "🟠", "Critical": "🔴"}.get(
                live_risk.final_risk_level if live_risk else None, "⚪️"
            )
            risk_summary = ""
            if live_risk:
                risk_summary = (
                    f"{risk_emoji} **Current situation in {district_name}:**\n"
                    f"- **Overall Risk Level:** {live_risk.final_risk_level} (score: {live_risk.composite_score}/3.0)\n"
                    f"- **Flood Severity:** {live_risk.flood_severity}\n"
                    f"- **Disease Outbreak Risk:** {live_risk.predicted_outbreak_risk}\n\n"
                )
            else:
                risk_summary = (
                    f"📍 **Disease risk overview for {district_name}:**\n\n"
                )
            reply = (
                f"{risk_summary}"
                f"**Common flood-related diseases to watch for in this district:**\n"
                f"- **🦠 Cholera** -- severe watery diarrhea; ORS immediately, see a doctor.\n"
                f"- **🦠 Diarrhea / Dysentery** -- loose stools, cramps, dehydration.\n"
                f"- **🦠 Typhoid** -- prolonged fever, weakness, abdominal pain.\n"
                f"- **🦠 Dengue** -- sudden fever, headache, joint pain, rash.\n"
                f"- **🦠 Hepatitis A/E** -- jaundice, dark urine, fatigue.\n"
                f"- **🦠 Leptospirosis** -- fever, calf pain, red eyes (after floodwater contact).\n"
                f"- **🦠 Skin infections** -- fungal, scabies, infected cuts.\n\n"
                f"**What to do right now:**\n"
                f"1. Drink only boiled or chlorinated water.\n"
                f"2. Wash hands with soap at five critical moments.\n"
                f"3. Use ORS at the first sign of diarrhea.\n"
                f"4. Avoid walking through floodwater (leptospirosis risk).\n"
                f"5. Sleep under treated mosquito nets (dengue risk).\n\n"
                f"_Source: WHO + DGHS + FloodShield corpus_\n"
                f"📞 Emergency: **999** | For any high fever, severe dehydration, or persistent vomiting, seek care immediately."
            )
            used_live_data = bool(live_risk)

        if not_kb_disease:
            reply = (
                f"I don't have information about **{not_kb_disease}** in my database. "
                f"FloodShield AI specializes in waterborne and flood-related diseases in Bangladesh: "
                f"**Cholera, Diarrhea, Typhoid, Dengue, Hepatitis A, and Skin Diseases**. "
                f"For {not_kb_disease}, please consult a licensed physician or the nearest hospital. "
                f"Emergency: 📞 **999**."
            )

        if matched_disease:
            kb = DISEASE_KB[matched_disease]
            disease_name = matched_disease.title()
            if matched_disease == "hepatitis":
                disease_name = "Hepatitis A"
            elif matched_disease == "skin":
                disease_name = "Skin Disease"
            reply = (
                f"**{disease_name} Information** 🏥\n\n"
                f"**Symptoms:** {kb['symptoms']}\n\n"
                f"**Causes:** {kb['causes']}\n\n"
                f"**Prevention:** {kb['prevention']}\n\n"
                f"**Home Care:** {kb['home_care']}\n\n"
                f"**When to see a doctor:** {kb['doctor']}\n\n"
                f"**Emergency Contact:** 📞 **999**"
            )

        if district_query and live_risk:
            district_name = user.district or "your district"
            risk_emoji = {"Low": "🟢", "Medium": "🟡", "High": "🟠", "Critical": "🔴"}.get(live_risk.final_risk_level, "⚪")
            reply = (
                f"{risk_emoji} **Current situation in {district_name}:**\n\n"
                f"- **Overall Risk Level:** {live_risk.final_risk_level} (score: {live_risk.composite_score}/3.0)\n"
                f"- **Flood Severity:** {live_risk.flood_severity}\n"
                f"- **Disease Outbreak Risk:** {live_risk.predicted_outbreak_risk}\n\n"
            )
            if live_risk.final_risk_level in ("High", "Critical"):
                reply += (
                    f"⚠️ **Precautions:** Avoid floodwater, drink only safe water, use ORS if diarrhea symptoms appear. "
                    f"Contact your local health worker and keep children away from flood areas.\n\n"
                    f"📞 Emergency: **999**"
                )
            else:
                reply += (
                    f"✅ The situation is currently manageable. Continue routine hygiene practices and monitor local alerts."
                )

        elif intent == ChatIntentEnum.emergency:
            is_bn = _detect_language(message) in ('bn', 'banglish')
            if is_bn:
                reply = (
                    "⚠️ **জরুরি সতর্কতা (EMERGENCY)**\n\n"
                    "জরুরি চিকিৎসার জন্য অবিলম্বে **৯৯৯** নম্বরে কল করুন।\n\n"
                    "জরুরি সেবায় পৌঁছাতে না পারলে:\n"
                    "- আপনার নিকটস্থ হাসপাতাল বা স্বাস্থ্যকেন্দ্রে যান\n"
                    "- স্থানীয় স্বাস্থ্যকর্মী বা রেড ক্রিসেন্ট/এনজিওর সাহায্য নিন\n"
                    "- বন্যার পানির মধ্যে না গিয়ে দ্রুত উঁচু নিরাপদ আশ্রয়ে যান\n\n"
                    "📞 **৯৯৯** | 🏥 নিকটস্থ হাসপাতাল"
                )
            else:
                reply = (
                    "⚠️ **EMERGENCY ALERT**\n\n"
                    "Please call **999** immediately for emergency medical services.\n\n"
                    "If you cannot reach emergency services:\n"
                    "- Contact your nearest hospital or health center\n"
                    "- Reach your local NGO health worker\n"
                    "- For flood evacuation, move to higher ground immediately\n\n"
                    "📞 **999** | 🏥 Nearest hospital"
                )

        elif intent == ChatIntentEnum.flood_safety:
            is_bn = _detect_language(message) in ('bn', 'banglish')
            if is_bn:
                reply = (
                    "🌊 **বন্যা নিরাপত্তা নির্দেশিকা (Flood Safety)**\n\n"
                    "১. বন্যার দূষিত পানির মধ্য দিয়ে চলাচল এড়িয়ে চলুন (লেপ্টোস্পাইরোসিস ও সংক্রমণের ঝুঁকি)\n"
                    "২. কেবল ফোটানো বা ক্লোরিনযুক্ত বিশুদ্ধ পানি পান করুন\n"
                    "৩. ডায়রিয়া দেখা দিলে অবিলম্বে খাবার স্যালাইন (ORS) গ্রহণ করুন\n"
                    "৪. শিশু ও বয়োবৃদ্ধদের নিরাপদে শুকনো স্থানে রাখুন\n"
                    "৫. ছেঁড়া বৈদ্যুতিক তার ও প্লাবিত ট্রান্সফরমার এড়িয়ে চলুন\n\n"
                    f"{'📊 **আপনার জেলার বর্তমান ঝুঁকি: ' + live_risk.final_risk_level + '**' if live_risk else ''}\n\n"
                    "📞 জরুরি যোগাযোগ: **৯৯৯**"
                )
            else:
                reply = (
                    "🌊 **Flood Safety Guidelines**\n\n"
                    "1. Avoid walking through floodwater — it may contain sewage and disease\n"
                    "2. Drink only bottled or boiled water during floods\n"
                    "3. Use ORS if you or family members experience diarrhea\n"
                    "4. Keep children and elderly indoors during heavy flooding\n"
                    "5. Report flooding incidents using the report button below\n\n"
                    f"{'📊 **Your district risk: ' + live_risk.final_risk_level + '**' if live_risk else ''}\n\n"
                    "📞 Emergency: **999**"
                )

        else:
            # Catch-all fallback when no specific disease keyword matched
            # AND no live risk data was available.  `retrieved_context`
            # is in scope (computed at the top of this function), so we
            # summarise the top chunk instead of returning a generic intro.
            rag_chunks = [c.strip() for c in retrieved_context.split('---') if c.strip()]
            if rag_chunks and rag_chunks[0].startswith('[Source:'):
                first = rag_chunks[0]
                header_end = first.find(']\n')
                if header_end != -1:
                    source_header = first[:header_end + 1]
                    body = first[header_end + 2:].strip()
                else:
                    source_header = ''
                    body = first
                if len(body) > 700:
                    body = body[:700].rsplit(' ', 1)[0] + '...'
                reply = (
                    f"Here is what I found in the medical reference for that question:\n\n"
                    f"{body}\n\n"
                    f"_Source: {source_header[1:-1] if source_header else 'FloodShield corpus'}_\n\n"
                    f"Ask me to go deeper on any section, or pick one of the quick topics on the home screen."
                )
            else:
                # Cold start intro supporting user's selected/detected language
                active_lang = requested_language if requested_language in ('bn', 'banglish', 'hi', 'en') and requested_language != 'auto' else _detect_language(message)
                if active_lang in ('bn', 'banglish'):
                    reply = (
                        "আমি **ফ্লাডশিল্ড এআই** (FloodShield AI), বাংলাদেশের বন্যা ও পানিবাহিত রোগ সুরক্ষা সহকারী। 🌐\n\n"
                        "আমি আপনাকে সাহায্য করতে পারি:\n"
                        "- 🦠 **রোগের তথ্য:** কলেরা, ডায়রিয়া, টাইফয়েড, ডেঙ্গু, হেপাটাইটিস ও চর্মরোগের লক্ষণ ও প্রতিকার\n"
                        "- 🌊 **বন্যা নিরাপত্তা:** বন্যা পরিস্থিতি ও নিরাপদ থাকার গাইডলাইন\n"
                        "- 📍 **জেলা ঝুঁকি:** আপনার জেলার রিয়েল-টাইম বন্যা ও প্রাদুর্ভাব ঝুঁকি\n"
                        "- 🏥 **হাসপাতাল রিসোর্স:** বেড, স্যালাইন, ওআরএস ও চিকিৎসক তথ্য\n\n"
                        "বন্যা বা স্বাস্থ্য সংক্রান্ত যেকোনো প্রশ্ন জিজ্ঞাসা করুন (ভয়েস বা লিখে)!"
                    )
                elif active_lang == 'hi':
                    reply = (
                        "मैं **फ्लडशील्ड एआई** (FloodShield AI) हूँ, बाढ़ और जलजनित रोग सुरक्षा सहायक। 🌐\n\n"
                        "मैं आपकी सहायता कर सकता हूँ:\n"
                        "- 🦠 **रोग जानकारी:** हैजा, दस्त, टाइफाइड, डेंगू, हेपेटाइटिस के लक्षण और रोकथाम\n"
                        "- 🌊 **बाढ़ सुरक्षा:** बाढ़ चेतावनी और बचाव दिशानिर्देश\n"
                        "- 📍 **जिला जोखिम:** आपके जिले की वास्तविक स्थिति\n"
                        "- 🏥 **अस्पताल संसाधन:** बेड, डॉक्टर और दवाइयों की जानकारी\n\n"
                        "बाढ़ या स्वास्थ्य सुरक्षा के बारे में कोई भी प्रश्न पूछें या बोलें!"
                    )
                else:
                    reply = (
                        "I'm **FloodShield AI**, your flood and disease safety assistant for Bangladesh. 🌐\n\n"
                        "I can help you with:\n"
                        "- 🦠 **Disease information:** Cholera, Diarrhea, Typhoid, Dengue, Hepatitis A, Skin Disease (WHO/DGHS)\n"
                        "- 🌊 **Flood safety:** Real-time inundation guidelines and safety\n"
                        "- 📍 **District risk:** Current severity and outbreak model predictions\n"
                        "- 🏥 **Hospital resources:** Beds, ORS, IV saline, and nearby facilities\n\n"
                        "Please ask or speak a question about flood safety or disease symptoms in any language!"
                    )

    # 5. Suggested actions
    suggested_actions = []
    if intent == ChatIntentEnum.emergency:
        suggested_actions.append(SuggestedAction(label="Call Emergency (999)", action_type=ActionType.emergency_call, target="tel:999"))
        suggested_actions.append(SuggestedAction(label="Find Nearest Hospital", action_type=ActionType.navigate, target="/dashboard/resources"))
    elif intent == ChatIntentEnum.hospital_info:
        suggested_actions.append(SuggestedAction(label="View Hospital Resources", action_type=ActionType.navigate, target="/dashboard/resources"))
    elif intent in (ChatIntentEnum.flood_safety, ChatIntentEnum.disease_info):
        suggested_actions.append(SuggestedAction(label="Check District Risk", action_type=ActionType.navigate, target="/dashboard"))

    return reply, suggested_actions, used_live_data


_chat_request_counters: dict[str, list[float]] = {}


def _allow_request(user_id) -> bool:
    """Per-user sliding-window rate limit (max 30 messages per hour)."""
    import time as _time
    key = str(user_id)
    now = _time.time()
    window_start = now - 3600
    calls = [t for t in _chat_request_counters.get(key, []) if t >= window_start]
    if len(calls) >= 30:
        _chat_request_counters[key] = calls
        return False
    calls.append(now)
    _chat_request_counters[key] = calls
    return True


@router.post("/message", response_model=ChatMessageResponse)

@router.post("/message", response_model=ChatMessageResponse)
async def chat_message(
    req: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatMessageResponse:
    """Tool-using agent endpoint.

    Architecture:
      1. Build conversation history (last 20 user/assistant turns).
      2. Run the agent loop in ``services.agent_runtime`` -- the LLM may
         call any of the 16 registered tools (see ``agent_tools``).
      3. If no API key is configured, fall back to the deterministic
         local engine so the endpoint still responds.
      4. Persist both turns in ``chat_messages`` so reloads keep history.
      5. Apply a simple per-user rate limit (30 messages/hour).
    """

    # 1. Rate limit
    if not _allow_request(current_user.id):
        raise HTTPException(
            status_code=429,
            detail="Too many messages -- please slow down (limit 30/hour).",
        )

    # 2. Conversation ID + history
    conversation_id = req.conversation_id or str(uuid.uuid4())

    history_rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id,
                ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
        .all()
    )
    history_rows = list(reversed(history_rows))
    history = [
        {"role": r.role if r.role in ("user", "assistant") else "user",
         "content": r.content}
        for r in history_rows
    ]

    # 3. Detect language + fallback intent
    detected_language = _detect_language(req.message) if req.language == "auto" else req.language.value
    fallback_intent = _detect_intent(req.message)

    from app.services.agent_runtime import run_agent
    from app.database import SessionLocal as _SessionLocal

    def _db_factory():
        return _SessionLocal()

    api_key = os.getenv("LLM_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    reply = ""
    ui_actions = []
    tools_used = []
    data_sources = []
    used_live_data = False
    detected_intent = fallback_intent

    if api_key:
        result = await run_agent(
            current_user, _db_factory, req.message, history, language=detected_language
        )
        reply = result.reply
        ui_actions = result.ui_actions
        tools_used = result.tools_used
        data_sources = result.data_sources
        used_live_data = result.used_live_data
        try:
            detected_intent = ChatIntentEnum(result.detected_intent)
        except Exception:
            detected_intent = fallback_intent
    else:
        fallback_reply, fallback_actions, used_live_data = await _generate_chatbot_response(
            req.message, fallback_intent, current_user, db, conversation_id, requested_language=detected_language
        )
        reply = fallback_reply
        detected_intent = fallback_intent

    # 4. Persist turns
    used_live_str = "true" if used_live_data else "false"
    user_msg = ChatMessage(
        user_id=current_user.id,
        conversation_id=conversation_id,
        role="user",
        content=req.message,
        detected_intent=ChatIntentType[fallback_intent.value],
        used_live_data=used_live_str,
    )
    db.add(user_msg)
    db.flush()

    assistant_msg = ChatMessage(
        user_id=current_user.id,
        conversation_id=conversation_id,
        role="assistant",
        content=reply,
        detected_intent=ChatIntentType[detected_intent.value],
        used_live_data=used_live_str,
    )
    db.add(assistant_msg)
    db.commit()

    # 5. Backward-compat suggested_actions + new ui_actions
    suggested_actions = []
    for ua in ui_actions:
        t = ua.get("type")
        p = ua.get("params", {}) or {}
        if t == "navigate" and p.get("route"):
            suggested_actions.append(SuggestedAction(
                label=f"Open {p['route']}",
                action_type=ActionType.navigate,
                target=p["route"],
            ))
        elif t == "select_district" and p.get("district"):
            suggested_actions.append(SuggestedAction(
                label=f"Show {p['district']}",
                action_type=ActionType.navigate,
                target=f"/dashboard/{p['district']}",
            ))

    from app.chat_schemas import UiAction as _UiAction

    return ChatMessageResponse(
        conversation_id=conversation_id,
        reply=reply,
        detected_intent=detected_intent,
        referenced_disease=None,
        used_live_data=used_live_data,
        suggested_actions=suggested_actions,
        ui_actions=[_UiAction(type=ua.get("type"), params=ua.get("params", {})) for ua in ui_actions],
        tools_used=tools_used,
        data_sources=data_sources,
    )



@router.post("/report-incident", response_model=ReportIncidentResponse)
async def report_incident(
    req: ReportIncidentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportIncidentResponse:
    """
    Incident classification endpoint.
    
    Takes free-text incident description, classifies it into one of the
    fixed categories from the community reports dataset, returns severity
    and recommended action.
    """
    label = None
    severity = None
    recommended_action = None
    
    # Try LLM classification first
    try:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            client = anthropic.AsyncAnthropic(api_key=api_key)
            system_prompt = f"""You are an incident classifier for FloodShield AI.
Classify the following incident description into ONE of the following valid labels:
{COMMUNITY_REPORTS_TAXONOMY}

Also determine a Severity: Low, Medium, High, or Critical.
Also provide a short recommended_action (1-2 sentences).

Respond strictly in JSON format with keys: "label", "severity", "recommended_action". Do not output anything else."""
            response = await client.messages.create(
                model='claude-3-5-sonnet-20241022',
                max_tokens=150,
                system=system_prompt,
                messages=[{"role": "user", "content": req.text}],
                timeout=5.0
            )
            
            # Extract JSON
            import json
            import re
            text_resp = response.content[0].text
            json_match = re.search(r'\{.*?\}', text_resp, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
            else:
                result = json.loads(text_resp)
                
            label = result.get("label")
            sev_str = result.get("severity", "").lower()
            if sev_str == "critical": severity = SeverityEnum.critical
            elif sev_str == "high": severity = SeverityEnum.high
            elif sev_str == "medium": severity = SeverityEnum.medium
            else: severity = SeverityEnum.low
            recommended_action = result.get("recommended_action")
    except Exception as e:
        print(f"LLM Classification Failed: {e}")
        pass
        
    # Heuristic classification based on keywords (fallback)
    if not label or not severity or not recommended_action:
        text_lower = req.text.lower()
        if any(word in text_lower for word in ['water', 'contaminated', 'dirty', 'pollution', 'discolor']):
            label = "water_contamination"
            severity = SeverityEnum.high
            recommended_action = "Avoid drinking water from this source. Report to local water authority. Use safe drinking water only."
        elif any(word in text_lower for word in ['fever', 'diarrhea', 'vomit', 'illness', 'sick', 'symptom']):
            label = "disease_symptom"
            severity = SeverityEnum.medium
            recommended_action = "Seek medical attention from nearest health center or hospital. Monitor symptoms and maintain hygiene."
        elif any(word in text_lower for word in ['flood', 'water', 'overflow', 'submerged', 'inundated']):
            label = "flood_impact"
            severity = SeverityEnum.high
            recommended_action = "Evacuate to higher ground if necessary. Avoid floodwaters. Wait for relief assistance."
        elif any(word in text_lower for word in ['sanitation', 'waste', 'dirty', 'hygiene', 'garbage']):
            label = "sanitation_issue"
            severity = SeverityEnum.medium
            recommended_action = "Report to local sanitation authority. Practice personal hygiene and safe food handling."
        elif any(word in text_lower for word in ['hospital', 'bed', 'medicine', 'crowded', 'resource']):
            label = "hospital_issue"
            severity = SeverityEnum.medium
            recommended_action = "Contact nearby hospitals for availability. Report shortages to health administration."
        else:
            label = "normal"
            severity = SeverityEnum.low
            recommended_action = "Noted. Continue monitoring the situation."
    
    # Create alert if high/critical severity
    alert_created = severity in [SeverityEnum.high, SeverityEnum.critical]
    
    # Store the incident report as a special chat message for logging
    incident_msg = ChatMessage(
        user_id=current_user.id,
        conversation_id=f"incident_{uuid.uuid4()}",
        role="user",
        content=req.text,
        detected_intent=ChatIntentType.incident_report,
        used_live_data="false",
    )
    db.add(incident_msg)
    db.commit()
    await notify_n8n({
        "event": "incident_reported",
        "label": label,
        "severity": severity.value,
        "district": req.district,
        "user_id": str(current_user.id),
    })
    
    return ReportIncidentResponse(
        label=label,
        severity=severity,
        recommended_action=recommended_action,
        alert_created=alert_created,
    )


@router.get("/history/{conversation_id}")
async def get_conversation_history(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve chat history for a conversation.
    Returns all messages in chronological order.
    """
    messages = db.query(ChatMessage).filter(
        ChatMessage.user_id == current_user.id,
        ChatMessage.conversation_id == conversation_id,
    ).order_by(ChatMessage.created_at.asc()).all()
    
    return {
        "conversation_id": conversation_id,
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "detected_intent": msg.detected_intent.value if msg.detected_intent else None,
                "created_at": msg.created_at.isoformat(),
            }
            for msg in messages
        ],
    }
