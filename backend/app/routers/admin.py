"""
/admin -- Admin-only user management + operational/oversight endpoints

User management:
  GET    /admin/users              -- List all users
  POST   /admin/users              -- Create an operational user
  PATCH  /admin/users/{user_id}/role  -- Change a user's role
  DELETE /admin/users/{user_id}       -- Delete a user

Oversight (admin can see what operational users do):
  GET /admin/predictions/all      -- All users' prediction history (auditing)
  GET /admin/data-status          -- Coverage of every reference table by district
  GET /admin/chat-history         -- All users' chat conversations

Knowledge base (admin manages the medical grounding corpus):
  GET    /admin/knowledge         -- List all knowledge articles
  POST   /admin/knowledge         -- Create an article
  PATCH  /admin/knowledge/{id}    -- Update an article
  DELETE /admin/knowledge/{id}    -- Delete an article

RAG corpus management is also exposed here (see below).
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.auth_models import User, UserRole
from app.auth_deps import require_roles
from app.auth_schemas import UserOut
from app.auth_utils import hash_password


class UserListItem(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    district: str | None
    created_at: str | None

    model_config = ConfigDict(from_attributes=True)


class UserRolePatch(BaseModel):
    role: UserRole



class AdminCreateUser(BaseModel):
    """Payload for an admin creating a user with a privileged role.

    The /auth/signup route refuses to create anyone above citizen unless
    the caller is already logged in, and the public signup form caps role
    at citizen.  This endpoint is the admin path for provisioning
    health_worker / hospital / ngo / government / admin accounts.
    """
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2)
    role: UserRole
    district: Optional[str] = None


router = APIRouter(
    prefix="/admin",
    tags=["Admin User Management"],
    dependencies=[Depends(require_roles(UserRole.admin))],
)


@router.get("/users", response_model=List[UserListItem])
def list_all_users(db: Session = Depends(get_db)):
    """Return every user in the users table (admin only)."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [
        UserListItem(
            id=str(u.id),
            email=u.email,
            full_name=u.full_name,
            role=u.role.value,
            district=u.district,
            created_at=u.created_at.isoformat() if u.created_at else None,
        )
        for u in users
    ]


@router.post("/users", response_model=UserListItem, status_code=status.HTTP_201_CREATED)
def create_user_as_admin(payload: AdminCreateUser, db: Session = Depends(get_db)):
    """Create a new user with a privileged role (admin only).

    Use this to provision health_worker / hospital / ngo / government / admin
    accounts.  The public /auth/signup route caps role at `citizen`, so this
    endpoint is the only sanctioned path for elevated roles.
    """
    if payload.role == UserRole.citizen:
        # Citizens can self-register via /auth/signup; sending them here
        # means the admin typed the wrong form.
        raise HTTPException(
            status_code=422,
            detail="Use /auth/signup for citizen accounts. This endpoint is for "
                   "operational roles (health_worker, hospital, ngo, government, admin).",
        )

    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"An account with email '{payload.email}' already exists.",
        )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        district=payload.district,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return UserListItem(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        district=user.district,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


@router.patch("/users/{user_id}/role", response_model=UserListItem)
def update_user_role(user_id: str, payload: UserRolePatch, db: Session = Depends(get_db)):
    """Change the role of a user by UUID (admin only)."""
    import uuid
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid user_id format (must be UUID)")

    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")

    user.role = payload.role
    db.commit()
    db.refresh(user)
    return UserListItem(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        district=user.district,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: str, db: Session = Depends(get_db)):
    """Permanently delete a user by UUID (admin only)."""
    import uuid
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid user_id format (must be UUID)")

    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")

    db.delete(user)
    db.commit()


# ─── RAG corpus management ──────────────────────────────────────────────
@router.get("/rag/status")
def rag_status(db: Session = Depends(get_db)):
    """Return RAG corpus stats: document count, chunk count, per-source breakdown."""
    from app.services.rag_service import corpus_stats
    return corpus_stats(db)


@router.post("/rag/ingest")
def rag_ingest(db: Session = Depends(get_db)):
    """Re-run the corpus seeder. Idempotent: skips slugs that already exist.

    For a forced full rebuild, drop the rag_documents rows first (or wipe
    the tables via SQL). The embedder is cached on disk after the first
    run, so subsequent ingests are fast (~5-10 s for ~150 chunks).
    """
    from app.services.seed_rag import seed_rag_corpus
    summary = seed_rag_corpus(db)
    return summary


@router.post("/rag/rebuild")
def rag_rebuild(db: Session = Depends(get_db)):
    """Drop all RAG tables and re-create + re-seed from the corpus.

    Useful after a model swap (e.g. changing RAG_EMBED_MODEL) -- otherwise
    vectors from the old model would coexist with new ones.
    """
    from sqlalchemy import text
    from app.rag_schema import ensure_rag_schema
    from app.services.seed_rag import seed_rag_corpus
    from app.database import engine as _engine

    with _engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS rag_chunks CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS rag_documents CASCADE"))

    ensure_rag_schema(_engine)
    summary = seed_rag_corpus(db)
    return {"status": "rebuilt", **summary}


@router.post("/rag/retrieve")
def rag_retrieve(
    payload: dict,
    db: Session = Depends(get_db),
):
    """Debug endpoint: show the top-K chunks the chatbot would see for a query.

    Useful for verifying that retrieval is picking the right source for a
    given question (e.g. "cholera protocol" -> WHO cholera doc).

    Returns the formatted context block plus the structured chunks
    (source, chunk_index, distance) so an admin can audit relevance.
    """
    from app.services.rag_service import retrieve_context
    from app.rag_embedder import embed_query
    from app.reference_models import RagChunk
    from sqlalchemy import text

    query = payload.get("query", "")
    limit = int(payload.get("limit", 4))
    if not query:
        raise HTTPException(status_code=422, detail="query is required")

    # If RAG corpus is empty, the retrieve_context will fall back to the
    # legacy KB; we still want to report the empty case clearly.
    chunk_count = db.query(RagChunk).count()

    context = retrieve_context(db, query, limit=limit)
    structured: list[dict] = []
    if chunk_count > 0:
        query_vec = embed_query(query)
        vec_str = "[" + ",".join(f"{x:.6f}" for x in query_vec) + "]"
        sql = text("""
            SELECT d.title, c.chunk_index, c.embedding <=> CAST(:vec AS vector) AS distance,
                   LEFT(c.text, 400) AS preview
            FROM rag_chunks c JOIN rag_documents d ON d.id = c.document_id
            ORDER BY c.embedding <=> CAST(:vec AS vector)
            LIMIT :limit
        """)
        rows = db.execute(sql, {"vec": vec_str, "limit": limit}).fetchall()
        structured = [
            {
                "title": r[0],
                "chunk_index": int(r[1]),
                "distance": float(r[2]),
                "preview": r[3],
            }
            for r in rows
        ]
    return {
        "query": query,
        "limit": limit,
        "corpus_size": chunk_count,
        "context_block": context,
        "chunks": structured,
    }

# ──────────────────────────────────────────────────────────────────────
# Gap 2: Cross-user prediction history (admin only)
#
# /history/predictions returns the calling user's own history.  Admins
# need to audit *every* operational prediction across the system for
# fairness, model-drift review, and compliance.
# ──────────────────────────────────────────────────────────────────────
@router.get("/predictions/all")
def list_all_predictions(
    model_name: Optional[str] = None,
    district: Optional[str] = None,
    risk_level: Optional[str] = None,
    user_email: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    from app.prediction_models import PredictionHistory

    limit = max(1, min(limit, 500))
    query = db.query(PredictionHistory, User).join(User, User.id == PredictionHistory.user_id)
    if model_name:
        query = query.filter(PredictionHistory.model_name == model_name)
    if district:
        query = query.filter(PredictionHistory.district.ilike(f"%{district}%"))
    if risk_level:
        query = query.filter(PredictionHistory.risk_level == risk_level)
    if user_email:
        query = query.filter(User.email.ilike(f"%{user_email}%"))
    rows = query.order_by(PredictionHistory.created_at.desc()).limit(limit).all()

    return {
        "count": len(rows),
        "items": [
            {
                "id": str(pred.id),
                "user_email": user.email,
                "user_role": user.role.value,
                "model_name": pred.model_name,
                "district": pred.district,
                "risk_level": pred.risk_level,
                "probability": pred.probability,
                "created_at": pred.created_at.isoformat(),
            }
            for pred, user in rows
        ],
    }


# ──────────────────────────────────────────────────────────────────────
# Gap 4: Knowledge-article CRUD (admin)
# ──────────────────────────────────────────────────────────────────────
from app.reference_models import KnowledgeArticle


class KnowledgeArticleIn(BaseModel):
    disease_name: str = Field(..., min_length=2, max_length=80)
    symptoms: str
    causes: Optional[str] = None
    prevention_tips: Optional[str] = None
    home_care_guidance: Optional[str] = None
    when_to_see_doctor: Optional[str] = None
    emergency_contact_info: Optional[str] = None
    reference: Optional[str] = None

class KnowledgeArticlePatch(BaseModel):
    """PATCH payload -- every field optional so admins can fix one cell."""
    disease_name: Optional[str] = Field(None, min_length=2, max_length=80)
    symptoms: Optional[str] = None
    causes: Optional[str] = None
    prevention_tips: Optional[str] = None
    home_care_guidance: Optional[str] = None
    when_to_see_doctor: Optional[str] = None
    emergency_contact_info: Optional[str] = None
    reference: Optional[str] = None


def _knowledge_to_dict(row):
    return {
        "id": str(row.id),
        "disease_name": row.disease_name,
        "symptoms": row.symptoms,
        "causes": row.causes,
        "prevention_tips": row.prevention_tips,
        "home_care_guidance": row.home_care_guidance,
        "when_to_see_doctor": row.when_to_see_doctor,
        "emergency_contact_info": row.emergency_contact_info,
        "reference": row.reference,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/knowledge")
def list_knowledge(db: Session = Depends(get_db)):
    rows = db.query(KnowledgeArticle).order_by(KnowledgeArticle.disease_name.asc()).all()
    return {"count": len(rows), "items": [_knowledge_to_dict(r) for r in rows]}


@router.post("/knowledge", status_code=status.HTTP_201_CREATED)
def create_knowledge(payload: KnowledgeArticleIn, db: Session = Depends(get_db)):
    existing = db.query(KnowledgeArticle).filter(
        func.lower(KnowledgeArticle.disease_name) == payload.disease_name.lower()
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"An article for '{payload.disease_name}' already exists.",
        )
    row = KnowledgeArticle(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return _knowledge_to_dict(row)


@router.patch("/knowledge/{article_id}")
def update_knowledge(article_id: str, payload: KnowledgeArticlePatch, db: Session = Depends(get_db)):
    row = db.query(KnowledgeArticle).filter(KnowledgeArticle.id == article_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Knowledge article not found.")
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Provide at least one field to update.")
    for key, value in updates.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return _knowledge_to_dict(row)


@router.delete("/knowledge/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge(article_id: str, db: Session = Depends(get_db)):
    row = db.query(KnowledgeArticle).filter(KnowledgeArticle.id == article_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Knowledge article not found.")
    db.delete(row)
    db.commit()
    return None

# ──────────────────────────────────────────────────────────────────────
# Gap 5: Admin data-status (district coverage report)
#
# A quick "is every district populated?" sanity report.  Lists every
# canonical district in `locations` and the count of rows each
# reference table has for that district, so an admin can spot gaps
# (a district with 0 hospitals, 0 weekly_history rows, etc.) at a
# glance instead of running ad-hoc SQL.
# ──────────────────────────────────────────────────────────────────────
@router.get("/data-status")
def data_status(db: Session = Depends(get_db)):
    from app.reference_models import (
        Location, Hospital, DistrictHospitalAggregate, DistrictEnv,
    )
    from app.history_models import WeeklyHistory

    districts = sorted({
        row.district
        for row in db.query(Location).filter(Location.kind == "district").all()
        if row.district
    })

    def counts_of(model, column):
        rows = (
            db.query(column, func.count(model.id))
            .group_by(column)
            .all()
        )
        return {k: v for k, v in rows}

    hospital_counts = counts_of(Hospital, Hospital.district)
    agg_counts = counts_of(DistrictHospitalAggregate, DistrictHospitalAggregate.district)
    env_counts = counts_of(DistrictEnv, DistrictEnv.district)
    history_counts = counts_of(WeeklyHistory, WeeklyHistory.district)

    items = []
    fully_covered = 0
    for district in districts:
        h = hospital_counts.get(district, 0)
        a = 1 if agg_counts.get(district, 0) > 0 else 0
        e = 1 if env_counts.get(district, 0) > 0 else 0
        w = history_counts.get(district, 0)
        is_fully_covered = (h > 0 and a and e and w >= 8)
        if is_fully_covered:
            fully_covered += 1
        items.append({
            "district": district,
            "hospitals": h,
            "has_aggregate": bool(a),
            "has_environment": bool(e),
            "weekly_history_rows": w,
            "is_fully_covered": is_fully_covered,
        })

    return {
        "total_districts": len(districts),
        "fully_covered": fully_covered,
        "missing_coverage": len(districts) - fully_covered,
        "items": items,
    }


# ──────────────────────────────────────────────────────────────────────
# Gap 6: Cross-user chat history (admin)
# ──────────────────────────────────────────────────────────────────────
@router.get("/chat-history")
def list_chat_history(
    user_email: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    from app.chat_models import ChatMessage

    limit = max(1, min(limit, 500))

    convo_q = (
        db.query(
            ChatMessage.conversation_id,
            func.max(ChatMessage.created_at).label("last_active"),
            func.count(ChatMessage.id).label("message_count"),
        )
        .group_by(ChatMessage.conversation_id)
        .order_by(func.max(ChatMessage.created_at).desc())
    )
    if user_email:
        convo_q = (
            convo_q.join(User, User.id == ChatMessage.user_id)
            .filter(User.email.ilike(f"%{user_email}%"))
        )
    conversations = convo_q.limit(limit).all()

    items = []
    for convo_id, last_active, msg_count in conversations:
        first_user = (
            db.query(ChatMessage)
            .filter(ChatMessage.conversation_id == convo_id, ChatMessage.role == "user")
            .order_by(ChatMessage.created_at.asc())
            .first()
        )
        last_msg = (
            db.query(ChatMessage)
            .filter(ChatMessage.conversation_id == convo_id)
            .order_by(ChatMessage.created_at.desc())
            .first()
        )
        owner = (
            db.query(User).filter(User.id == last_msg.user_id).first()
            if last_msg else None
        )
        items.append({
            "conversation_id": convo_id,
            "user_email": owner.email if owner else None,
            "user_role": owner.role.value if owner else None,
            "message_count": msg_count,
            "last_active": last_active.isoformat() if last_active else None,
            "first_user_message": first_user.content if first_user else None,
            "last_message_preview": last_msg.content[:160] if last_msg else None,
        })

    return {"count": len(items), "items": items}


@router.get("/chat-history/{conversation_id}")
def get_chat_conversation(conversation_id: str, db: Session = Depends(get_db)):
    from app.chat_models import ChatMessage

    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    owner = db.query(User).filter(User.id == rows[0].user_id).first()
    return {
        "conversation_id": conversation_id,
        "user_email": owner.email if owner else None,
        "user_role": owner.role.value if owner else None,
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "detected_intent": m.detected_intent.value if m.detected_intent else None,
                "referenced_disease": m.referenced_disease,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in rows
        ],
    }
