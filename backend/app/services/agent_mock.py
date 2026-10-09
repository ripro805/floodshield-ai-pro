"""Mock Anthropic client for the chatbot agent.

Used in environments where ``LLM_API_KEY`` is not a real key (e.g. sandboxed
deployments, CI, smoke tests).  Selects pre-scripted tool-use sequences
based on the user message and replays them as if they came from the real
Anthropic Messages API.
"""
from __future__ import annotations

import re
import json
import uuid
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger().bind(module="agent_mock")


def _format_tool_result(tool_name: Optional[str], payload: Optional[Dict[str, Any]], district: Optional[str]) -> str:
    """Render a tool result as a short assistant reply.

    Used when the mock needs to produce an end_turn text after a tool
    has been called (iteration 2 of the agent loop).  The format mirrors
    the real LLM's typical response: a one-line answer that names the
    district and quotes the data.
    """
    if not payload:
        return "I couldn't get a clear answer for that. Please try again."
    if payload.get("ok") is False:
        err = payload.get("error") or "no data"
        code = payload.get("code") or ""
        d = payload.get("district") or district or "that district"
        prefix = f"**{d}** -- " if code in ("permission_denied", "no_env", "no_data") else ""
        return f"{prefix}Sorry -- {err}."
    d = payload.get("district") or district or "the district"
    NL = "\n"
    if tool_name == "get_disease_breakdown":
        breakdown = payload.get("disease_breakdown") or {}
        total = payload.get("total_predicted_cases")
        dom = payload.get("dominant_disease") or "(no dominant disease)"
        lines = [f"**Disease cases in {d}** (mock):",
                 f"- Dominant disease: **{dom}**"]
        if total is not None:
            lines.append(f"- Total predicted cases: **{total}**")
        for k, v in list(breakdown.items())[:6]:
            lines.append(f"- {k}: {v}")
        lines.append("INTENT: prediction")
        return NL.join(lines)
    if tool_name == "get_environmental_monitoring":
        rl = payload.get("river_level_m")
        fd = payload.get("flood_depth_cm")
        wq = payload.get("water_quality_index")
        return (
            f"**Water status in {d}** (mock):\n"
            f"- River level: **{rl} m**\n"
            f"- Flood depth: **{fd} cm**\n"
            f"- Water quality: **{wq}/100**\n"
            "INTENT: data_query"
        )
    if tool_name == "predict_flood":
        return f"**Flood prediction for {d}**: probability **{payload.get('flood_probability')}**, level **{payload.get('flood_risk_level')}**.\nINTENT: prediction"
    if tool_name == "get_weather":
        return f"**Weather in {d}**. INTENT: data_query"
    if tool_name == "get_disease_risk":
        return f"**Disease outbreak risk in {d}**: **{payload.get('predicted_outbreak_risk')}**.\nINTENT: prediction"
    if tool_name == "get_forecast":
        return f"**7/14-day forecast for {d}**: {payload.get('forecast_next_7_days_cases')} / {payload.get('forecast_next_14_days_cases')}.\nINTENT: prediction"
    if tool_name == "get_risk_score":
        return f"**Composite risk in {d}**: **{payload.get('final_risk_level')}** (score {payload.get('composite_score')}).\nINTENT: prediction"
    if tool_name == "get_satellite_flood_extent":
        return f"**Satellite flood extent for {d}**: {payload.get('event_label')}, ~{payload.get('approx_flood_area_km2')} km².\nINTENT: data_query"
    if tool_name == "get_hospital_resources":
        return f"**Hospital resources in {d}**: beds={payload.get('beds')}, ORS={payload.get('ors_stock')}, occupancy={payload.get('occupancy_percent')}%.\nINTENT: resources"
    if tool_name == "get_recommendations":
        return f"**Recommendations for {d}** (risk={payload.get('risk_level')}).\nINTENT: resources"
    if tool_name == "get_top_at_risk_districts":
        items = payload.get("top_n") or []
        names = ", ".join([str(i.get("district")) for i in items])
        return f"**Top at-risk districts today**: {names}.\nINTENT: data_query"
    if tool_name == "get_disease_knowledge":
        return f"**{payload.get('disease')}**: {payload.get('symptoms', '')[:140]}...\nINTENT: medical_guidance"
    if tool_name == "submit_incident_report":
        return f"**Incident recorded**: {payload.get('label')}, severity {payload.get('severity')}.\nINTENT: incident_report"
    if tool_name == "ui_action":
        return f"Done.\nINTENT: ui_control"
    return f"Result for {d}.\nINTENT: general"


def _resolve_district_name(message: str) -> Optional[str]:
    """Cheap district-name extraction for the mock.  Uses the same alias
    table the real tool uses."""
    from app.services.weather_service import normalize_district_for_lookup
    from app.routers.recommend import DISTRICT_ALIASES
    from app.database import SessionLocal
    from app.reference_models import Location

    patterns = [
        # Latin district after "of" / "in" / "for" / "at"
        r"(?:of|in|for|at)\s+([A-Za-z'\- ]+?)(?:\??$|\??\s+\?|[.!?])",
        # "and <district>?" / "what about <district>?"
        r"(?:and|about|in)\s+([A-Za-z'\- ]+?)(?:\??$|\??\s+\?|[.!?])",
        # Bangla district anywhere in the message
        r"([\u0980-\u09FF]+)",
    ]
    candidates: List[str] = []
    # Bangla-script to English district names (subset of the 64 districts)
    BANGLA_TO_EN = {
        "ফেনী": "Feni",
        "সিলেট": "Sylhet",
        "ঢাকা": "Dhaka",
        "চট্টগ্রাম": "Chattogram",
        "কুমিল্লা": "Comilla",
        "বগুড়া": "Bogra",
        "রাজশাহী": "Rajshahi",
        "খুলনা": "Khulna",
        "বরিশাল": "Barishal",
        "রংপুর": "Rangpur",
        "ময়মনসিংহ": "Mymensingh",
        "কক্সবাজার": "Cox's Bazar",
    }
    for p in patterns:
        for m in re.finditer(p, message, re.IGNORECASE):
            grp = m.group(1).strip()
            # If it's a Bangla script string, try the reverse map
            if grp and any("\u0980" <= ch <= "\u09FF" for ch in grp):
                # Find the longest matching Bangla alias
                for bangla, eng in BANGLA_TO_EN.items():
                    if bangla in grp:
                        candidates.append(eng)
            else:
                candidates.append(grp)

    tokens = re.findall(r"[A-Z][A-Za-z]+", message)
    candidates.extend(tokens)
    bn_candidates = re.findall(r"[\u0980-\u09FF]+", message)
    if bn_candidates:
        candidates.append(" ".join(bn_candidates))

    db = SessionLocal()
    try:
        rows = db.query(Location.district).filter(Location.kind == "district").all()
        canonical = sorted({r[0] for r in rows if r[0]})
        cset = {c.lower() for c in canonical}
        for cand in candidates:
            cand_clean = cand.strip()
            if not cand_clean:
                continue
            low = cand_clean.lower()
            if low in cset:
                return next(c for c in canonical if c.lower() == low)
            norm = normalize_district_for_lookup(cand_clean)
            if norm in cset:
                return next(c for c in canonical if c.lower() == norm)
            aliased = DISTRICT_ALIASES.get(low)
            if aliased and aliased.lower() in cset:
                return next(c for c in canonical if c.lower() == aliased.lower())
    finally:
        db.close()
    return None


NL = "\n\n"


def _scenario_for_message(
    message: str,
    last_district: Optional[str] = None,
    history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Return a script: ``[{"tool_use": {...}}, {"text": "..."}]``."""
    msg = message.strip()
    lower = msg.lower()

    # Follow-up: "and Dhaka?" or "what about Sylhet?" -- the user is
    # continuing the previous question type with a new district.  Because
    # the runtime only persists the assistant's text into the chat history,
    # the mock falls back to reading the previous *user* message and
    # re-running the scenario classifier on it.
    if history and (lower.startswith("and ") or lower.startswith("what about ") or
                    lower.startswith("and the ") or lower.startswith("in ") or
                    lower.startswith("how about ") or lower.startswith("now ")):
        # Find the previous user message (skip the current one, which is
        # the LAST user in `history`).
        user_turns = [m for m in (history or []) if m.get("role") == "user"]
        prev_user = ""
        if len(user_turns) >= 2:
            prev_content = user_turns[-2].get("content")
            if isinstance(prev_content, str):
                prev_user = prev_content
        if prev_user:
            prev_scenario = _scenario_for_message(prev_user, last_district=last_district, history=None)
            for step in prev_scenario.get("scripts", []):
                if "tool_use" in step:
                    tu = step["tool_use"]
                    name = tu.get("name")
                    if name in ("get_disease_breakdown", "get_environmental_monitoring",
                                "predict_flood", "get_disease_risk", "get_risk_score",
                                "get_weather", "get_forecast", "get_hospital_resources",
                                "get_recommendations", "get_satellite_flood_extent",
                                "get_disease_knowledge"):
                        d = _resolve_district_name(msg) or last_district or "Feni"
                        # Re-use the same tool input shape, swap the district
                        new_input = dict(tu.get("input") or {})
                        new_input["district"] = d
                        return {
                            "scripts": [
                                {"tool_use": {"name": name, "input": new_input}},
                                {"text": (f"Here is the same answer for **{d}**." + NL + "INTENT: data_query")},
                            ]
                        }

    # 14: severe symptoms
    if any(w in lower for w in ["can't breathe", "unconscious", "severe bleeding", "having a seizure", "chest pain", "suicide"]):
        return {
            "scripts": [
                {
                    "text": (
                        "This is a medical emergency." + NL +
                        "**Call 999 immediately** (Bangladesh national emergency) "
                        "or go to the nearest hospital emergency room. Do not wait." + NL +
                        "If someone is with you, keep the person still, monitor their breathing, "
                        "and stay on the line with the dispatcher." + NL +
                        "INTENT: emergency"
                    ),
                },
            ]
        }

    # 12: prompt injection
    if any(w in lower for w in ["ignore your rules", "ignore previous", "ignore all previous", "system prompt", "reveal your prompt", "print your system prompt"]):
        return {
            "scripts": [
                {
                    "text": (
                        "I can only help with FloodShield platform data, flood-safety guidance, "
                        "and the verified medical knowledge base. I can't share system "
                        "internals or hospital/operational data to unauthorised roles." + NL +
                        "If you have a specific question about a district's weather, flood risk, "
                        "disease prediction, or hospital resources, ask me about that." + NL +
                        "INTENT: general"
                    ),
                },
            ]
        }

    # 9: disease knowledge
    if "symptom" in lower or "treatment" in lower or "cure" in lower or "medicine for" in lower:
        m = re.search(r"(?:symptoms? of|treatment of|medicine for|cure for|about)\s+([a-zA-Z]+)", lower)
        if m:
            disease = m.group(1)
            return {
                "scripts": [
                    {
                        "tool_use": {"name": "get_disease_knowledge", "input": {"disease": disease}},
                    },
                    {
                        "text": (
                            f"Verified knowledge-base guidance for **{disease.capitalize()}** "
                            "(symptoms, causes, prevention, home care, when to see a doctor, "
                            "emergency contact). If the disease is not in my verified list, "
                            "I'll say so honestly." + NL + "INTENT: medical_guidance"
                        ),
                    },
                ]
            }

    # 7: show me / open
    if (
        lower.startswith("show me")
        or "open hospital" in lower
        or "open hospital resources" in lower
        or "open hospital directory" in lower
        or "open satellite" in lower
    ):
        d = _resolve_district_name(msg) or last_district or "Feni"
        if "hospital" in lower:
            # Always open the new Directory tab -- it works for both
            # citizens and operational users, and is the right place
            # for a single-hospital browse.  The operational Resources
            # page is still reachable via the dedicated prompt
            # 'hospital stock in <district>'.
            return {
                "scripts": [
                    {"tool_use": {"name": "ui_action", "input": {"action": {"type": "open_hospital_directory", "params": {"district": d} if d else {}}}}},
                    {"text": (f"Opening the Hospital Directory, scrolled to {d}." + NL + "INTENT: ui_control")},
                ]
            }
        if "satellite" in lower:
            return {
                "scripts": [
                    {"tool_use": {"name": "ui_action", "input": {"action": {"type": "open_satellite_view", "params": {}}}}},
                    {"text": ("Opening the satellite view. I'll use the latest registered SAR flood extent exports." + NL + "INTENT: ui_control")},
                ]
            }
        return {
            "scripts": [
                {"tool_use": {"name": "ui_action", "input": {"action": {"type": "select_district", "params": {"district": d}}}}},
                {"text": (f"Opening {d}'s dashboard and zooming the map." + NL + "INTENT: ui_control")},
            ]
        }

    # 5: top at risk
    if "most at risk" in lower or "top 5" in lower or "top 10" in lower or "highest risk" in lower:
        n = 10 if "top 10" in lower else 5
        return {
            "scripts": [
                {"tool_use": {"name": "get_top_at_risk_districts", "input": {"n": n}}},
                {"text": (f"Top {n} at-risk districts right now, ranked the same way as the dashboard's ranking panel." + NL + "INTENT: prediction")},
            ]
        }

    # 6: forecast
    if "rise next week" in lower or "forecast" in lower or "next 7 days" in lower or "next week" in lower or "next two weeks" in lower or "next 14 days" in lower:
        d = _resolve_district_name(msg) or last_district or "Feni"
        return {
            "scripts": [
                {"tool_use": {"name": "get_forecast", "input": {"district": d}}},
                {"text": (f"FloodShield Model 3 (LSTM) forecast for **{d}** based on the last 8 weeks of real data. Tool returns next-7-day and next-14-day predicted cases (or honest 'unavailable' when fewer than 8 real weeks are available)." + NL + "INTENT: prediction")},
            ]
        }

    # 4: weather
    if "weather" in lower or "temperature" in lower or "rainfall today" in lower or "humidity" in lower:
        d = _resolve_district_name(msg) or last_district or "Feni"
        return {
            "scripts": [
                {"tool_use": {"name": "get_weather", "input": {"district": d}}},
                {"text": (f"Here is the live weather for **{d}** (temperature, humidity, rainfall). data_source will say `live_api` or `fallback`." + NL + "INTENT: data_query")},
            ]
        }

    # 8: hospital stock
    if "hospital stock" in lower or "hospital resources" in lower or "ors stock" in lower or "beds available" in lower:
        d = _resolve_district_name(msg) or last_district or "Feni"
        return {
            "scripts": [
                {"tool_use": {"name": "get_hospital_resources", "input": {"district": d}}},
                {"text": (f"Hospital capacity (beds, occupancy, ORS, IV saline, antibiotics) for **{d}** from the district hospital aggregate." + NL + "INTENT: resources")},
            ]
        }

    # 3: flood prediction
    if "flood prediction" in lower or "flood forecast" in lower or "chances of flood" in lower or "risk of flood" in lower or "will there be flood" in lower:
        d = _resolve_district_name(msg) or last_district or "Feni"
        return {
            "scripts": [
                {"tool_use": {"name": "predict_flood", "input": {"district": d}}},
                {"text": (f"FloodShield Model 1 (binary flood classifier) returns the latest probability and risk level for **{d}**. See the Used line for the actual numbers." + NL + "INTENT: prediction")},
            ]
        }

    # 2: water level
    if "water level" in lower or "river level" in lower or "panir star" in lower or "পানির স্তর" in msg or "জলের স্তর" in msg or "how high is the water" in lower:
        d = _resolve_district_name(msg) or last_district or "Feni"
        return {
            "scripts": [
                {"tool_use": {"name": "get_environmental_monitoring", "input": {"district": d}}},
                {"text": (f"Here is the latest river level and water-quality index for **{d}** from the database. See the Used line for the tool and the observed-on date." + NL + "INTENT: data_query")},
            ]
        }

    # 1: disease cases
    if "disease cases" in lower or "disease case" in lower or "disease count" in lower or "case count" in lower or "disease in" in lower or "diseases in" in lower or "outbreak" in lower or "disease situation" in lower:
        d = _resolve_district_name(msg) or last_district or "Feni"
        return {
            "scripts": [
                {"tool_use": {"name": "get_disease_breakdown", "input": {"district": d}}},
                {"text": (f"Here is the latest Model 2B per-disease breakdown for **{d}** (see the Used line below for the exact tool and date). The total predicted cases and the dominant disease are returned by the tool." + NL + "INTENT: data_query")},
            ]
        }

    # risk
    if "is it safe" in lower or "safe in" in lower or "risk in" in lower:
        d = _resolve_district_name(msg) or last_district or "Feni"
        return {
            "scripts": [
                {"tool_use": {"name": "get_environmental_monitoring", "input": {"district": d}}},
                {"tool_use": {"name": "get_disease_breakdown", "input": {"district": d}}},
                {"tool_use": {"name": "get_risk_score", "input": {"district": d}}},
                {"text": (f"Here's a combined risk snapshot for **{d}** based on environment, disease and composite risk." + NL + "INTENT: prediction")},
            ]
        }

    return {
        "scripts": [
            {
                "text": (
                    "I can answer questions about flood risk, weather, river levels, "
                    "disease cases, hospital resources, and run any of the platform's "
                    "predictions. Try asking: 'disease cases of Feni', 'water level of "
                    "Sylhet', 'show me Chattogram', or 'top 5 districts most at risk'." + NL +
                    "INTENT: general"
                ),
            }
        ]
    }


class MockBlock:
    def __init__(self, type_: str, **fields):
        self.type = type_
        for k, v in fields.items():
            setattr(self, k, v)


class MockResponse:
    def __init__(self, content_blocks: List[MockBlock], stop_reason: str = "end_turn", model: str = "mock"):
        self.content = content_blocks
        self.stop_reason = stop_reason
        self.model = model


class MockAnthropic:
    def __init__(self, scenarios: Optional[Dict[str, Any]] = None):
        self._last_tool_use: Optional[str] = None
        self._last_district: Optional[str] = None
        self._last_disease: Optional[str] = None

    class _Messages:
        def __init__(self, outer):
            self.outer = outer

        async def create(self, *, model, max_tokens, system, tools, messages, timeout=None):
            last_user = ""
            for m in reversed(messages or []):
                if m.get("role") == "user":
                    content = m.get("content")
                    if isinstance(content, str):
                        last_user = content
                        break
                    if isinstance(content, list):
                        last_user = " ".join(
                            (b.get("content") if isinstance(b.get("content"), str) else "")
                            for b in content if isinstance(b, dict)
                        )
            import sys as _s
            # Determine which tools have already been called
            already_called: set = set()
            last_assistant_emitted_tool = False
            for m in messages or []:
                if m.get("role") != "assistant":
                    continue
                content = m.get("content")
                if not isinstance(content, list):
                    continue
                for b in content:
                    if hasattr(b, "type") and b.type == "tool_use":
                        already_called.add(b.name)
                        last_assistant_emitted_tool = True
                    elif isinstance(b, dict) and b.get("type") == "tool_use":
                        already_called.add(b.get("name"))
                        last_assistant_emitted_tool = True
            print(f"[MOCK] msg={last_user!r}, history_len={len(messages or [])}, already_called={already_called}, last_assistant_emitted_tool={last_assistant_emitted_tool}", file=_s.stderr)
            # If the previous turn was a tool_use, this iteration is the
            # post-tool result turn -- return an end_turn that summarises
            # the latest tool result.  This is how a real LLM behaves
            # after seeing a successful tool call result.
            if last_assistant_emitted_tool:
                tool_payload = None
                tool_name = None
                for m in reversed(messages or []):
                    if m.get("role") != "user":
                        continue
                    c = m.get("content")
                    if not isinstance(c, list):
                        continue
                    for b in c:
                        if isinstance(b, dict) and b.get("type") == "tool_result":
                            try:
                                tool_payload = json.loads(b.get("content") or "{}")
                            except Exception:
                                tool_payload = {"raw": b.get("content")}
                            tool_use_id = b.get("tool_use_id")
                            for mm in reversed(messages or []):
                                if mm.get("role") != "assistant":
                                    continue
                                cc = mm.get("content") or []
                                if not isinstance(cc, list):
                                    continue
                                for bb in cc:
                                    if isinstance(bb, dict) and bb.get("id") == tool_use_id:
                                        tool_name = bb.get("name")
                                    elif hasattr(bb, "id") and getattr(bb, "id", None) == tool_use_id:
                                        tool_name = getattr(bb, "name", None)
                            break
                    if tool_payload is not None:
                        break
                summary_text = _format_tool_result(tool_name, tool_payload, self.outer._last_district)
                blocks = [MockBlock(type_="text", text=summary_text)]
                print(f"[MOCK]   post-tool summary: {summary_text[:120]!r}", file=_s.stderr)
                return MockResponse(content_blocks=blocks, stop_reason="end_turn", model="mock")
            scenario = _scenario_for_message(
                last_user,
                last_district=self.outer._last_district,
                history=messages or [],
            )
            steps_str = []
            for s in scenario["scripts"]:
                if "tool_use" in s:
                    steps_str.append(f"tool_use:{s['tool_use']['name']}")
                else:
                    steps_str.append("text")
            print(f"[MOCK]   scenario={steps_str}", file=_s.stderr)
            blocks: List[MockBlock] = []
            stop_reason = "end_turn"
            saw_tool = False
            for step in scenario["scripts"]:
                if "tool_use" in step:
                    tu = step["tool_use"]
                    name = tu.get("name")
                    inp = tu.get("input") or {}
                    # Allow re-issuing a tool call when the *input district*
                    # differs from the last district the mock used.  This is
                    # how a real LLM re-invokes `get_disease_breakdown` with
                    # a new district argument; the already-called check is
                    # too coarse when the input changes.
                    is_new_district_call = (
                        "district" in inp
                        and isinstance(inp["district"], str)
                        and self.outer._last_district is not None
                        and inp["district"].lower() != self.outer._last_district.lower()
                    )
                    if name in already_called and not is_new_district_call:
                        continue
                    self.outer._last_tool_use = name
                    if "district" in inp and isinstance(inp["district"], str):
                        self.outer._last_district = inp["district"]
                    elif "name" in inp and name == "resolve_district" and isinstance(inp.get("name"), str):
                        self.outer._last_district = inp["name"]
                    blocks.append(
                        MockBlock(
                            type_="tool_use",
                            id=f"toolu_{uuid.uuid4().hex[:12]}",
                            name=name,
                            input=inp,
                        )
                    )
                    saw_tool = True
                elif "text" in step:
                    if saw_tool:
                        continue
                    blocks.append(MockBlock(type_="text", text=step["text"]))
            if saw_tool:
                stop_reason = "tool_use"
            print(f"[MOCK]   blocks={[('text:'+b.text[:30]) if b.type=='text' else ('tool_use:'+b.name) for b in blocks]}, stop_reason={stop_reason}", file=_s.stderr)
            return MockResponse(content_blocks=blocks, stop_reason=stop_reason, model="mock")

    def __getattr__(self, item):
        if item == "messages":
            return self._Messages(self)
        raise AttributeError(item)


MOCK_SCENARIOS: Dict[str, Any] = {}
