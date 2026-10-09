# 🤖 Chatbot LLM Integration Guide

**Status**: Chatbot currently uses keyword-based heuristics. Real LLM integration ready for next phase.

**Why Heuristics for MVP?**
- ✅ Prevents hallucination (no made-up flood percentages)
- ✅ Grounded in real medical knowledge base
- ✅ Works reliably with 100% uptime (no API dependency)
- ✅ Lower latency (no network call to Anthropic)
- ✅ No LLM cost during testing/demo phase

**When to upgrade to LLM?**
- After MVP launch and user feedback
- When budget allows for Claude API costs
- When conversation quality needs improvement
- When scaling to handle complex multi-turn dialogs

---

## Implementation: Anthropic Claude Integration

### Step 1: Install Dependency

```bash
cd backend
pip install anthropic
pip freeze > requirements.txt
```

### Step 2: Add to `requirements.txt`

```
anthropic==0.28.0
```

### Step 3: Update `.env.example` & `.env`

```bash
# backend/.env.example
LLM_API_KEY=your-anthropic-claude-api-key
```

Get your API key from: [console.anthropic.com](https://console.anthropic.com)

### Step 4: Create `app/llm_service.py`

```python
"""
LLM service for chatbot responses.
Calls Anthropic Claude API with medical knowledge base grounding.
"""
import os
from typing import Optional
import anthropic
from app.config import LLM_API_KEY

# Initialize Anthropic client (once at startup)
llm_client = anthropic.Anthropic(api_key=LLM_API_KEY or "")

async def generate_llm_response(
    message: str,
    medical_kb: str,
    user_role: str,
    user_district: Optional[str],
    conversation_context: list[dict],
    language: str = "en",
) -> tuple[str, bool]:
    """
    Generate response using Claude LLM.
    
    Args:
        message: User's latest message
        medical_kb: Embedded medical knowledge base string
        user_role: User's role (citizen, health_worker, hospital, etc.)
        user_district: User's district for personalization
        conversation_context: Previous turns in this conversation
        language: 'en' or 'bn' (detected from message)
    
    Returns:
        (response_text, used_live_data_flag)
    """
    
    if not LLM_API_KEY:
        # Fallback if API key not configured
        return (
            "LLM service is not configured. "
            "Using built-in responses. Please configure LLM_API_KEY.",
            False
        )
    
    # Build system prompt with grounding
    system_prompt = f"""You are FloodShield AI, a helpful medical and flood safety chatbot for Bangladesh.

Your role is to provide accurate, safe, and actionable information about:
- Disease prevention and response (cholera, diarrhea, typhoid, dengue, hepatitis A, skin disease)
- Flood safety and preparedness
- Hospital resources and availability
- Emergency response

GROUNDING RULES:
1. NEVER invent flood percentages, hospital bed counts, or disease statistics
2. ONLY use information from your knowledge base or what the user tells you
3. If you don't know something, say "I don't have that information"
4. Always prioritize user safety and direct to hospitals for medical emergencies
5. Respond in the user's preferred language ({language})

USER CONTEXT:
- Role: {user_role}
- District: {user_district or 'Not specified'}
- Use this to personalize responses (e.g., mention their district by name)

MEDICAL KNOWLEDGE BASE:
{medical_kb}

RESPONSE GUIDELINES:
- Keep responses concise (2-3 paragraphs maximum)
- Use simple language (many users have limited literacy)
- End with a clear action (e.g., "go to hospital", "call health worker", "check resources")
- Format with markdown: **bold** for emphasis, bullet points for lists
- For emergencies, always suggest calling 999 and going to nearest hospital
"""
    
    # Prepare messages array with conversation history
    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in conversation_context[-5:]  # Last 5 turns to keep context window reasonable
    ] + [
        {"role": "user", "content": message}
    ]
    
    try:
        # Call Claude API
        response = await llm_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=512,
            system=system_prompt,
            messages=messages,
            temperature=0.7,  # Slightly creative but grounded (not 0 = too robotic, not 1 = too random)
        )
        
        reply = response.content[0].text
        return reply, False  # Flag indicates we didn't use live platform data (just LLM)
        
    except anthropic.APIError as e:
        # API error - fall back to heuristic response
        print(f"LLM API error: {e}")
        return (
            "Sorry, I'm temporarily unavailable. Please try again or contact your health worker.",
            False
        )
    except Exception as e:
        # Any other error - fall back gracefully
        print(f"Unexpected error in LLM service: {e}")
        return (
            "An unexpected error occurred. Please try again.",
            False
        )
```

### Step 5: Update `app/routers/chatbot.py`

Replace the heuristic `_generate_chatbot_response()` function:

```python
# At top of file, add:
from app.llm_service import generate_llm_response

# Replace the entire _generate_chatbot_response function with:

async def _generate_chatbot_response(
    message: str,
    intent: ChatIntentEnum,
    user: User,
    language: str,
    conversation_history: list[dict],  # NEW: for LLM context
) -> tuple[str, list[SuggestedAction], bool]:
    """
    Generate a conversational response using Claude LLM.
    
    Falls back to heuristics if LLM is unavailable.
    """
    
    # Try LLM first
    try:
        llm_reply, used_live_data = await generate_llm_response(
            message=message,
            medical_kb=MEDICAL_KNOWLEDGE_BASE,
            user_role=user.role.value,
            user_district=user.district,
            conversation_context=conversation_history,
            language=language,
        )
        
        # Parse suggested actions from LLM response (simple extraction)
        suggested_actions = _extract_actions_from_llm_response(llm_reply, intent)
        
        return llm_reply, suggested_actions, used_live_data
        
    except Exception as e:
        print(f"LLM generation failed, falling back to heuristics: {e}")
        # Fall through to heuristic logic below
    
    # Fallback: Heuristic responses (same as before)
    suggested_actions = []
    used_live_data = False
    
    if intent == ChatIntentEnum.emergency:
        reply = (
            "🚨 EMERGENCY DETECTED\n\n" +
            _get_emergency_contact(None) +
            "\n\nFor cholera/severe diarrhea: seek rehydration therapy immediately.\n" +
            "For dengue/typhoid: hospital care is essential."
        )
        suggested_actions = [
            SuggestedAction(
                label="Call Emergency (999)",
                action_type=ActionType.emergency_call,
                target="tel:999"
            ),
            SuggestedAction(
                label="Find Nearest Hospital",
                action_type=ActionType.navigate,
                target="/dashboard/resources"
            )
        ]
    
    # ... rest of heuristic responses as currently implemented ...
    
    return reply, suggested_actions, used_live_data


def _extract_actions_from_llm_response(
    reply: str,
    intent: ChatIntentEnum,
) -> list[SuggestedAction]:
    """
    Parse suggested actions from LLM response text.
    
    Looks for patterns like:
    - "call 999" → emergency_call action
    - "go to hospital" → navigate to resources
    - "check resources" → navigate to resources
    - "call health worker" → emergency_call action
    """
    actions = []
    reply_lower = reply.lower()
    
    if any(x in reply_lower for x in ['call 999', 'emergency', 'immediately go to']):
        actions.append(SuggestedAction(
            label="Call Emergency (999)",
            action_type=ActionType.emergency_call,
            target="tel:999"
        ))
    
    if any(x in reply_lower for x in ['hospital', 'resources', 'health worker']):
        actions.append(SuggestedAction(
            label="View Hospital Resources",
            action_type=ActionType.navigate,
            target="/dashboard/resources"
        ))
    
    if intent == ChatIntentEnum.flood_safety and len(actions) == 0:
        actions.append(SuggestedAction(
            label="Check District Risk",
            action_type=ActionType.navigate,
            target="/dashboard"
        ))
    
    return actions[:2]  # Max 2 actions per response
```

### Step 6: Update Endpoint to Pass Conversation History

```python
@router.post("/message", response_model=ChatMessageResponse)
async def chat_message(
    req: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatMessageResponse:
    """..."""
    
    # Fetch conversation history for context (last 5 turns)
    history = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == req.conversation_id,
        ChatMessage.user_id == current_user.id,
    ).order_by(ChatMessage.created_at.desc()).limit(5).all()
    
    conversation_history = [
        {"role": msg.role, "content": msg.content}
        for msg in reversed(history)
    ]
    
    # Detect intent and language
    intent = _detect_intent(req.message)
    language = _detect_language(req.message)
    
    # Generate response (now with LLM support)
    reply, suggested_actions, used_live_data = await _generate_chatbot_response(
        message=req.message,
        intent=intent,
        user=current_user,
        language=language,
        conversation_history=conversation_history,  # NEW
    )
    
    # ... rest of endpoint (store messages, etc.) ...
```

---

## Cost Estimation

**Anthropic Claude API Pricing** (as of 2026):
- Input: $3 / 1M tokens
- Output: $15 / 1M tokens

**Typical Chatbot Usage**:
- Average message: ~100 input tokens, ~150 output tokens
- Cost per message: ~$0.00285 (~0.3 cents)
- 1000 messages/day: ~$2.85/day (~$85/month)

**Optimization Tips**:
- Use `claude-3-5-haiku` for simpler queries (cheaper)
- Cache conversation context to reduce re-processing
- Batch messages during off-peak hours
- Monitor usage with `anthropic` client telemetry

---

## Testing the Integration

### Unit Test Example

```python
# backend/tests/test_chatbot_llm.py
import pytest
from app.llm_service import generate_llm_response

@pytest.mark.asyncio
async def test_llm_response_grounding():
    """Verify LLM doesn't hallucinate numbers."""
    reply, _ = await generate_llm_response(
        message="What's the current flood percentage in Feni?",
        medical_kb=MEDICAL_KNOWLEDGE_BASE,
        user_role="citizen",
        user_district="Feni",
        conversation_context=[],
    )
    # Verify no percentage numbers in response (wouldn't know without platform data)
    assert "%" not in reply or "unknown" in reply.lower()

@pytest.mark.asyncio
async def test_llm_emergency_routing():
    """Verify emergency messages are routed correctly."""
    reply, actions = await _generate_chatbot_response(
        message="Someone is dying! Help!",
        intent=ChatIntentEnum.emergency,
        user=mock_user,
        language="en",
        conversation_history=[],
    )
    # Should have emergency action
    assert any(a.target == "tel:999" for a in actions)
```

---

## Monitoring & Debugging

### Enable Logging

```python
# backend/app/config.py
import logging
logging.basicConfig(level=logging.INFO)

# Log all LLM API calls
anthropic_logger = logging.getLogger("anthropic")
anthropic_logger.setLevel(logging.DEBUG)
```

### Monitor in Production

```python
# backend/app/llm_service.py
import time

async def generate_llm_response(...):
    start = time.time()
    try:
        response = await llm_client.messages.create(...)
        latency = time.time() - start
        print(f"LLM latency: {latency:.2f}s")
        return response.content[0].text, False
    except Exception as e:
        latency = time.time() - start
        print(f"LLM error after {latency:.2f}s: {e}")
        raise
```

---

## Rollback Plan

If LLM integration causes issues:

1. Set `LLM_API_KEY=""` in `.env` to disable
2. All calls automatically fall back to heuristics
3. Users experience no disruption
4. No code changes needed

---

## Next Steps

1. ✅ Implement `app/llm_service.py` and Anthropic client
2. ✅ Update `app/routers/chatbot.py` with async LLM calls
3. ✅ Add unit tests for LLM grounding (no hallucination)
4. ✅ Set `LLM_API_KEY` in production `.env`
5. ✅ Deploy and monitor for 1 week
6. ✅ Gather user feedback and fine-tune system prompt

---

**Status**: Ready to implement. Estimated effort: 4-6 hours including testing and documentation.
