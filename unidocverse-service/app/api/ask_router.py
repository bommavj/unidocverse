"""
ask_router.py
=============
Global Ask AI endpoint — TRUE RAG implementation.

Pipeline:
  1. Semantic search (pgvector) to retrieve relevant document chunks
  2. Build augmented context from retrieved chunks + document metadata
  3. Stream phi3:mini answer using retrieved context only

Endpoints:
  POST /api/documents/ask              — global RAG across all docs
  POST /api/documents/ask/with-context — RAG + caller-supplied structured context
  POST /api/documents/{doc_id}/ask     — per-document RAG (in qa_router.py)
"""

import json
import logging
import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import config
from app.core.database import get_db, SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["ask"])

_RAW_TEXT_LIMIT       = 2500
_TOP_K                = 3
_SIMILARITY_THRESHOLD = 0.40


# =============================================================================
# DOC-TYPE-AWARE PROMPT PROFILES
# =============================================================================

_PROMPT_PROFILES = {
    "declarations_page": {
        "role": "an insurance expert helping a policyholder understand their coverage",
        "rules": [
            "Give 3-5 bullet points maximum — one clear sentence each",
            "Focus on coverage limits, expiry dates, exclusions, and action items",
            "Mention the deductible, premium, and key coverage amounts if relevant",
            "Flag any missing coverage (e.g. earthquake, flood) if asked",
            "Do NOT list endorsement form numbers or legal codes",
        ],
    },
    "insurance_policy": {
        "role": "an insurance expert helping a policyholder understand their policy",
        "rules": [
            "Give 3-5 bullet points maximum — one clear sentence each",
            "Focus on what is covered, what is excluded, and key limits",
            "Highlight renewal dates, premium amounts, and deductibles",
        ],
    },
    "insurance_claim": {
        "role": "an insurance claims specialist helping a claimant understand their claim",
        "rules": [
            "Give 3-5 bullet points maximum — one clear sentence each",
            "Focus on claim status, amounts approved vs claimed, denial reasons",
            "Highlight any appeal deadlines or required actions",
        ],
    },
    "commission_statement": {
        "role": "an insurance accounting specialist reviewing a commission statement",
        "rules": [
            "Give 3-5 bullet points maximum — one clear sentence each",
            "Focus on total commissions, discrepancies, unmatched lines, and variance",
            "Highlight any missed commissions or policy lines that need attention",
            "Report exact dollar amounts from the data provided",
        ],
    },
    "loss_run": {
        "role": "an insurance underwriting specialist reviewing a loss run report",
        "rules": [
            "Give 3-5 bullet points maximum — one clear sentence each",
            "Focus on loss ratio, total incurred, large losses, and risk classification",
            "Highlight claim frequency and any large individual claims",
            "State the risk level clearly",
        ],
    },
    "policy_portfolio": {
        "role": "an insurance agency manager reviewing a policy portfolio",
        "rules": [
            "Give 3-5 bullet points maximum — one clear sentence each",
            "Focus on expiring policies, renewal status, premium totals, and risk",
            "Call out any urgent items needing immediate attention",
            "Be specific — use policy numbers, client names, and dates from the data",
        ],
    },
    "gap_analysis": {
        "role": "an insurance coverage specialist reviewing gap analysis results",
        "rules": [
            "Give 3-5 bullet points maximum — one clear sentence each",
            "Focus on missing coverage types, low limits, and critical gaps",
            "Prioritize by severity — critical gaps first",
            "Suggest specific lines of business to add",
        ],
    },
    "bank_statement": {
        "role": "a financial advisor reviewing a bank statement",
        "rules": [
            "Give 3-5 bullet points maximum — one clear sentence each",
            "Focus on account balance, notable transactions, and fees",
            "Highlight any overdrafts, large withdrawals, or unusual activity",
        ],
    },
    "invoice": {
        "role": "an accounts payable specialist reviewing an invoice",
        "rules": [
            "Give 3-5 bullet points maximum — one clear sentence each",
            "Focus on amount due, due date, vendor, and payment terms",
        ],
    },
    "tax_form": {
        "role": "a tax professional reviewing a tax document",
        "rules": [
            "Give 3-5 bullet points maximum — one clear sentence each",
            "Focus on income reported, taxes withheld, and key figures",
            "Do NOT provide tax advice — only summarize what is in the document",
        ],
    },
    "contract": {
        "role": "a legal assistant reviewing a contract",
        "rules": [
            "Give 3-5 bullet points maximum — one clear sentence each",
            "Focus on key obligations, termination clauses, and important dates",
            "Do NOT provide legal advice — only summarize what is in the document",
        ],
    },
    "medical_record": {
        "role": "a medical records specialist helping a patient understand their records",
        "rules": [
            "Give 3-5 bullet points maximum — one clear sentence each",
            "Focus on diagnoses, treatments, and follow-up instructions",
            "Do NOT provide medical advice — only summarize what is in the document",
        ],
    },
    "mortgage_document": {
        "role": "a mortgage specialist reviewing a mortgage document",
        "rules": [
            "Give 3-5 bullet points maximum — one clear sentence each",
            "Focus on loan amount, interest rate, monthly payment, and term",
        ],
    },
}

_DEFAULT_PROFILE = {
    "role": "a document assistant helping a user understand their document",
    "rules": [
        "Give 3-5 bullet points maximum — one clear sentence each",
        "Focus on the most important and actionable information",
        "Be direct and avoid unnecessary jargon",
    ],
}

_TYPE_ALIASES = {
    "insurance_policy":       "declarations_page",
    "nonrenewal_notice":      "declarations_page",
    "renewal_notice":         "declarations_page",
    "cancellation_notice":    "declarations_page",
    "auto_insurance_claim":   "insurance_claim",
    "health_insurance_claim": "insurance_claim",
    "pay_stub":               "tax_form",
    "w2":                     "tax_form",
    "1099_misc":              "tax_form",
    "nda":                    "contract",
    "employment_contract":    "contract",
    "lab_report":             "medical_record",
    "prescription":           "medical_record",
    "credit_memo":            "invoice",
    "receipt":                "invoice",
    "purchase_order":         "invoice",
    "property_deed":          "mortgage_document",
    # AMS types
    "commission":             "commission_statement",
    "loss_run_report":        "loss_run",
    "policy_gap":             "gap_analysis",
    "portfolio":              "policy_portfolio",
}


def _get_profile(doc_type: str) -> dict:
    resolved = _TYPE_ALIASES.get(doc_type, doc_type)
    return _PROMPT_PROFILES.get(resolved, _DEFAULT_PROFILE)


def _translate_query_to_english_if_needed(query: str, lang: str) -> str:
    if lang == "en" or not query or not query.strip():
        return query
    try:
        import ollama
        client = ollama.Client()
        prompt = f"""You are a precise search query translator.
Translate this search query into English. If it is already in English, output it exactly as is.
Output ONLY the translation, no explanations, no quotes, no extra text.

Query: "{query}"

Translation:"""
        response = client.generate(
            model=config.model,
            prompt=prompt,
            options={"temperature": 0.0, "num_ctx": 4096}
        )
        translated = response.get("response", "").strip().strip('"').strip("'")
        if translated:
            logger.info(f"🔄 Translated query from '{query}' ({lang}) to English: '{translated}'")
            return translated
    except Exception as e:
        logger.error(f"❌ Query translation failed: {e}")
    return query


def _build_prompt(question: str, context: str, doc_type: str, lang: Optional[str] = None) -> str:
    profile    = _get_profile(doc_type)
    role       = profile["role"]
    rules_text = "\n".join(f"- {r}" for r in profile["rules"])

    lang_instruction = ""
    if lang == "es":
        lang_instruction = "\n- CRITICAL: You MUST write your answer in Spanish (es). Responde en español."
    elif lang == "fr":
        lang_instruction = "\n- CRITICAL: You MUST write your answer in French (fr). Réponds en français."
    elif lang == "de":
        lang_instruction = "\n- CRITICAL: You MUST write your answer in German (de). Antworte auf Deutsch."

    return f"""You are {role}.
Answer the question using ONLY the information provided below.

STRICT RULES:
{rules_text}
- Do NOT invent or assume anything not in the provided data
- Do NOT add general knowledge or typical industry norms
- If the answer is not in the data, say: "I could not find this in the provided data."{lang_instruction}

{context}

Question: {question}

Answer (bullet points only):"""


# =============================================================================
# TEXT CLEANER
# =============================================================================

def _clean_text(raw: str) -> str:
    if not raw:
        return ""
    text = raw.replace('\r\n', '\n').replace('\r', '\n')
    lines = []
    for line in text.split('\n'):
        line = re.sub(r'[ \t]+', ' ', line).strip()
        if len(line) <= 1:
            continue
        lines.append(line)
    cleaned = '\n'.join(lines)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


# =============================================================================
# CONTEXT BUILDER — from document type + metadata
# =============================================================================

def _build_structured_context(context_data: dict) -> str:
    """
    Build a structured context block from caller-supplied data.
    The shape of context_data drives the doc_type detection:

    Supported shapes:
      policy:    {policy_number, client_name, carrier, premium, coverage_summary, ...}
      client:    {client_name, policies: [...], gap_analysis: {...}, loss_runs: [...]}
      portfolio: {total_policies, active, total_premium, expiring, by_lob: {...}}
      commission:{carrier, total_amount, lines: [...], discrepancies: [...]}
      loss_run:  {carrier, loss_ratio, total_claims, total_incurred, claims: [...]}
      gap:       {score, grade, total_gaps, critical_gaps, recommendations: [...]}
    """
    if not context_data:
        return ""

    detected_type = context_data.get("_type", "")
    lines         = []

    # ── Policy ─────────────────────────────────────────────────────────────
    if "policy_number" in context_data:
        detected_type = detected_type or "declarations_page"
        lines.append("[POLICY DATA]")
        _add_if(lines, "Policy Number",  context_data.get("policy_number"))
        _add_if(lines, "Client",         context_data.get("client_name"))
        _add_if(lines, "Carrier",        context_data.get("carrier_name"))
        _add_if(lines, "Line",           context_data.get("line_of_business"))
        _add_if(lines, "Premium",        context_data.get("premium_amount"))
        _add_if(lines, "Effective",      context_data.get("effective_date"))
        _add_if(lines, "Expiry",         context_data.get("expiry_date"))
        _add_if(lines, "Days Remaining", context_data.get("days_to_expiry"))
        _add_if(lines, "Status",         context_data.get("status"))
        _add_if(lines, "Renewal Status", context_data.get("renewal_status"))
        _add_if(lines, "Risk Score",     context_data.get("risk_score"))
        _add_if(lines, "Agent",          context_data.get("assigned_agent"))
        cov = context_data.get("coverage_summary") or {}
        if cov:
            lines.append("Coverage Details:")
            for k, v in cov.items():
                try:    lines.append(f"  {k}: ${int(float(v)):,}")
                except: lines.append(f"  {k}: {v}")
        else:
            lines.append("Coverage Details: No coverage details on file")
        _add_if(lines, "Notes", context_data.get("notes"))
        lines.append("[END POLICY DATA]")

    # ── Client with policies ────────────────────────────────────────────────
    elif "client_name" in context_data and "policies" in context_data:
        detected_type = detected_type or "client_portfolio"
        lines.append("[CLIENT DATA]")
        _add_if(lines, "Client",         context_data.get("client_name"))
        _add_if(lines, "Client Number",  context_data.get("client_number"))
        _add_if(lines, "Type",           context_data.get("client_type"))
        _add_if(lines, "Status",         context_data.get("status"))
        _add_if(lines, "Email",          context_data.get("email"))
        _add_if(lines, "Phone",          context_data.get("phone"))
        _add_if(lines, "Location",       f"{context_data.get('city') or ''} {context_data.get('state') or ''}".strip())
        _add_if(lines, "Total Premium",  context_data.get("total_premium"))
        _add_if(lines, "Renewal in",     f"{context_data.get('nearest_renewal_days')} days" if context_data.get('nearest_renewal_days') else None)
        policies = context_data.get("policies") or []
        if policies:
            lines.append(f"Policies ({len(policies)}):")
            for p in policies:
                lines.append(
                    f"  [{p.get('line_of_business','?').upper()}] "
                    f"{p.get('policy_number','?')} — "
                    f"{p.get('carrier_name','?')} — "
                    f"${float(p.get('premium_amount') or 0):,.2f}/yr — "
                    f"Expires {p.get('expiry_date','?')} ({p.get('days_to_expiry','?')}d) — "
                    f"{p.get('status','?')} / {p.get('renewal_status','?')}"
                )
                cov = p.get("coverage_summary") or {}
                if cov:
                    for k, v in list(cov.items())[:4]:
                        try:    lines.append(f"    {k}: ${int(float(v)):,}")
                        except: lines.append(f"    {k}: {v}")
        else:
            lines.append("Policies: None on file")
        lines.append("[END CLIENT DATA]")

    # ── Portfolio ───────────────────────────────────────────────────────────
    elif "total_policies" in context_data:
        detected_type = detected_type or "policy_portfolio"
        lines.append("[PORTFOLIO DATA]")
        _add_if(lines, "Total Policies",  context_data.get("total_policies"))
        _add_if(lines, "Active",          context_data.get("active"))
        _add_if(lines, "Total Premium",   context_data.get("total_premium"))
        _add_if(lines, "Expiring ≤30d",   context_data.get("expiring_30"))
        _add_if(lines, "Urgent ≤7d",      context_data.get("expiring_7"))
        by_lob = context_data.get("by_lob") or {}
        if by_lob:
            lines.append("By Line of Business:")
            for k, v in by_lob.items():
                lines.append(f"  {k}: {v}")
        expiring = context_data.get("expiring_policies") or []
        if expiring:
            lines.append("Expiring Soon:")
            for p in expiring[:10]:
                lines.append(f"  {p.get('policy_number')} — {p.get('client_name')} ({p.get('days_to_expiry')}d)")
        not_started = context_data.get("not_started_renewals") or []
        if not_started:
            lines.append("Renewals Not Started (≤90d):")
            for p in not_started[:10]:
                lines.append(f"  {p.get('policy_number')} — {p.get('client_name')} ({p.get('days_to_expiry')}d)")
        lines.append("[END PORTFOLIO DATA]")

    # ── Commission Statement ────────────────────────────────────────────────
    elif "commission_amount" in context_data or "total_variance" in context_data:
        detected_type = detected_type or "commission_statement"
        lines.append("[COMMISSION DATA]")
        _add_if(lines, "Carrier",          context_data.get("carrier_name"))
        _add_if(lines, "Statement Date",   context_data.get("statement_date"))
        _add_if(lines, "Total Amount",     context_data.get("total_amount"))
        _add_if(lines, "Total Expected",   context_data.get("total_expected"))
        _add_if(lines, "Total Variance",   context_data.get("total_variance"))
        _add_if(lines, "Lines",            context_data.get("total_lines"))
        _add_if(lines, "Matched",          context_data.get("matched_lines"))
        _add_if(lines, "Unmatched",        context_data.get("unmatched_lines"))
        _add_if(lines, "Discrepancies",    context_data.get("discrepancy_lines"))
        disc = context_data.get("discrepancies") or []
        if disc:
            lines.append("Discrepancy Lines:")
            for d in disc[:5]:
                lines.append(
                    f"  {d.get('policy_number','?')} — {d.get('insured_name','?')} "
                    f"| Actual: ${float(d.get('commission_amount',0)):,.2f} "
                    f"| Variance: ${float(d.get('variance',0)):,.2f}"
                )
        lines.append("[END COMMISSION DATA]")

    # ── Loss Run ────────────────────────────────────────────────────────────
    elif "loss_ratio" in context_data:
        detected_type = detected_type or "loss_run"
        lines.append("[LOSS RUN DATA]")
        _add_if(lines, "Carrier",         context_data.get("carrier_name"))
        _add_if(lines, "Period",          f"{context_data.get('period_start')} to {context_data.get('period_end')}")
        _add_if(lines, "Total Claims",    context_data.get("total_claims"))
        _add_if(lines, "Total Incurred",  context_data.get("total_incurred"))
        _add_if(lines, "Total Paid",      context_data.get("total_paid"))
        _add_if(lines, "Total Premium",   context_data.get("total_premium"))
        _add_if(lines, "Loss Ratio",      f"{context_data.get('loss_ratio')}%")
        _add_if(lines, "Risk Level",      context_data.get("risk_level"))
        flags = context_data.get("risk_flags") or []
        if flags:
            lines.append(f"Risk Flags: {', '.join(flags)}")
        claims = context_data.get("claims") or []
        if claims:
            lines.append("Individual Claims:")
            for c in claims[:8]:
                lines.append(
                    f"  #{c.get('claim_number','?')} | {c.get('date_of_loss','?')} "
                    f"| {c.get('claim_type','?')} | ${float(c.get('amount_incurred',0)):,.0f} "
                    f"| {c.get('status','?')}"
                    + (" 🔴 LARGE" if c.get("is_large_loss") else "")
                )
        lines.append("[END LOSS RUN DATA]")

    # ── Gap Analysis ────────────────────────────────────────────────────────
    elif "overall_grade" in context_data or "total_gaps" in context_data:
        detected_type = detected_type or "gap_analysis"
        lines.append("[GAP ANALYSIS DATA]")
        _add_if(lines, "Client",        context_data.get("client_name"))
        _add_if(lines, "Score",         f"{context_data.get('overall_score') or context_data.get('score')}/100")
        _add_if(lines, "Grade",         context_data.get("overall_grade") or context_data.get("grade"))
        _add_if(lines, "Total Gaps",    context_data.get("total_gaps"))
        _add_if(lines, "Critical Gaps", context_data.get("critical_gaps"))
        _add_if(lines, "Total Premium", context_data.get("total_premium"))
        missing = context_data.get("missing_lines") or []
        if missing:
            lines.append(f"Missing Coverage: {', '.join(missing)}")
        recs = context_data.get("recommendations") or context_data.get("gaps") or []
        if recs:
            lines.append("Recommendations:")
            for r in recs[:6]:
                lines.append(f"  [{r.get('priority','?').upper()}] {r.get('title','?')} — {r.get('description','')[:120]}")
        lines.append("[END GAP ANALYSIS DATA]")

    return "\n".join(lines), detected_type


def _add_if(lines: list, label: str, value) -> None:
    if value is not None and str(value).strip() not in ("", "None", "null"):
        lines.append(f"{label}: {value}")


# =============================================================================
# SEMANTIC RETRIEVAL — pgvector
# =============================================================================

def _semantic_retrieve(question: str, doc_type_filter: str, top_k: int) -> list:
    try:
        from app.config.model_factory import EmbeddingModelFactory
        embedding_model = EmbeddingModelFactory.get_model()
        query_vector = embedding_model.encode(question).tolist()

        db = SessionLocal()
        try:
            where_dt = "AND doc_type = :dt" if doc_type_filter else ""
            params = {
                "vec": str(query_vector),
                "threshold": _SIMILARITY_THRESHOLD,
                "top_k": top_k,
            }
            if doc_type_filter:
                params["dt"] = doc_type_filter

            rows = db.execute(text(f"""
                SELECT id, filename, doc_type, summary, raw_text,
                       1 - (embedding <=> CAST(:vec AS vector)) AS similarity
                FROM documents
                WHERE embedding IS NOT NULL AND status = 'completed'
                  {where_dt}
                  AND 1 - (embedding <=> CAST(:vec AS vector)) >= :threshold
                ORDER BY embedding <=> CAST(:vec AS vector)
                LIMIT :top_k
            """), params).fetchall()

            logger.info(f"🔍 RAG retrieval: {len(rows)} docs for '{question}'")
            if rows:
                return [{"id": str(r.id), "filename": r.filename, "doc_type": r.doc_type,
                         "summary": r.summary, "raw_text": r.raw_text,
                         "similarity": float(r.similarity)} for r in rows]

            logger.info("⚠ No semantic matches — keyword fallback")
            return _keyword_fallback(db, question, doc_type_filter, top_k, where_dt)
        finally:
            db.close()
    except Exception as e:
        logger.error(f"❌ Semantic retrieval failed: {e}", exc_info=True)
        return _keyword_fallback_standalone(question, doc_type_filter, top_k)


def _keyword_fallback(db, question, doc_type_filter, top_k, where_dt) -> list:
    stopwords = {
        "the","a","an","is","are","was","were","what","which","who",
        "how","when","where","find","show","tell","me","about","this",
        "that","and","or","in","of","for","to","it","do","does","i",
        "me","my","myself","we","our","ours","ourselves","you","your",
        "yours","yourself","yourselves","he","him","his","himself",
        "she","her","hers","herself","its","itself","they","them",
        "their","theirs","themselves","am","is","are","was","were",
        "be","been","being","have","has","had","having","do","does",
        "did","doing","would","should","could","ought","i'm","you're",
        "he's","she's","it's","we're","they're","i've","you've",
        "we've","they've","i'd","you'd","he'd","she'd","we'd",
        "they'd","i'll","you'll","he'll","she'll","we'll","they'll",
        "isn't","aren't","wasn't","weren't","hasn't","haven't",
        "hadn't","doesn't","don't","didn't","won't","wouldn't",
        "shan't","shouldn't","can't","cannot","couldn't","mustn't",
        "let's","that's","who's","what's","here's","there's",
        "when's","where's","why's","how's","but","if","or","because",
        "as","until","while","of","at","by","for","with","about",
        "against","between","into","through","during","before","after",
        "above","below","to","from","up","down","in","out","on","off",
        "over","under","again","further","then","once","here","there",
        "when","where","why","how","all","any","both","each","few",
        "more","most","other","some","such","no","nor","not","only",
        "own","same","so","than","too","very","can","will","just",
        "should","now","please", "document", "documents", "file", 
        "files", "search", "get", "give", "related", "hello", 
        "hi", "hey", "query", "question", "name", "wife", "husband"
    }
    words = [w for w in re.findall(r'\w+', question.lower())
             if w not in stopwords and len(w) > 2]
    params = {"top_k": top_k}
    if doc_type_filter:
        params["dt"] = doc_type_filter

    if not words:
        return []
    else:
        conds = " OR ".join(
            f"(LOWER(filename) LIKE :w{i} OR LOWER(COALESCE(summary,'')) LIKE :w{i}"
            f" OR LOWER(COALESCE(raw_text,'')) LIKE :w{i})"
            for i, _ in enumerate(words)
        )
        for i, w in enumerate(words):
            params[f"w{i}"] = f"%{w}%"
        rows = db.execute(text(f"""
            SELECT id, filename, doc_type, summary, raw_text, 0.6 AS similarity
            FROM documents WHERE status='completed' {where_dt}
              AND ({conds})
            ORDER BY created_at DESC LIMIT :top_k
        """), params).fetchall()

    return [{"id": str(r.id), "filename": r.filename, "doc_type": r.doc_type,
             "summary": r.summary, "raw_text": r.raw_text,
             "similarity": float(r.similarity)} for r in rows]


def _keyword_fallback_standalone(question, doc_type_filter, top_k) -> list:
    db = SessionLocal()
    try:
        where_dt = "AND doc_type = :dt" if doc_type_filter else ""
        return _keyword_fallback(db, question, doc_type_filter, top_k, where_dt)
    finally:
        db.close()


def _build_augmented_context(docs: list) -> str:
    docs_sorted = sorted(docs, key=lambda d: d["similarity"], reverse=True)
    blocks = []
    for doc in docs_sorted:
        summary = (doc.get("summary") or "").strip()[:300]
        content = _clean_text(doc.get("raw_text") or "")[:_RAW_TEXT_LIMIT]
        sim = doc.get("similarity", 0)
        parts = [
            f"Document: {doc['filename']} (relevance: {sim:.0%})",
            f"Type: {doc.get('doc_type') or 'unknown'}",
        ]
        if summary: parts.append(f"Summary: {summary}")
        if content: parts.append(f"Content:\n{content}")
        blocks.append("\n".join(parts))
    return "\n\n---\n\n".join(blocks)


# =============================================================================
# STREAMING HELPER
# =============================================================================

def _make_stream(prompt: str, source_doc: dict = None):
    async def _stream():
        try:
            if source_doc:
                yield f"data: {json.dumps({'source_document': source_doc})}\n\n"
            import ollama
            client = ollama.Client()
            stream = client.generate(
                model=config.model,
                prompt=prompt,
                stream=True,
                options={
                    "temperature": 0.0,
                    "num_predict": 500,
                    "stop": ["Question:", "---", "\n\n\n", "Note:"],
                    "num_ctx": 4096
                },
            )
            for chunk in stream:
                token = chunk.get("response", "")
                if token:
                    yield f"data: {json.dumps({'token': token})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            logger.error(f"❌ Generation failed: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    return StreamingResponse(_stream(), media_type="text/event-stream")


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/ask")
async def ask_all_documents(request: dict, raw_request: Request, db: Session = Depends(get_db)):
    """
    Global RAG — semantic search across all documents.
    Optionally accepts a 'context_data' dict to inject structured data
    alongside the RAG results (used by Policy, Portfolio, Commission, etc.)
    """
    question        = (request.get("question") or "").strip()
    doc_type_filter = (request.get("doc_type") or "").strip() or None
    context_data    = request.get("context_data") or {}

    if not question:
        raise HTTPException(status_code=400, detail="Question required")

    from app.core.language import get_request_language
    lang = request.get("lang") or get_request_language(raw_request, db)

    logger.info(f"🌐 RAG ask: '{question}' | filter={doc_type_filter or 'all'} | lang={lang} | context_keys={list(context_data.keys())}")

    # Build structured context block if caller provided data
    structured_ctx  = ""
    detected_type   = doc_type_filter or ""
    if context_data:
        result = _build_structured_context(context_data)
        structured_ctx, detected_type = result if isinstance(result, tuple) else (result, detected_type)

    # Semantic RAG retrieval
    search_question = _translate_query_to_english_if_needed(question, lang)
    docs = _semantic_retrieve(search_question, doc_type_filter, _TOP_K)

    source_doc = None
    if docs:
        top_doc = docs[0]
        source_doc = {
            "id": top_doc.get("id"),
            "filename": top_doc.get("filename"),
            "doc_type": top_doc.get("doc_type")
        }

    # Build final context — structured data first, then RAG docs
    parts = []
    if structured_ctx:
        parts.append(structured_ctx)
    if docs:
        parts.append(_build_augmented_context(docs))
        if not detected_type:
            detected_type = docs[0].get("doc_type") or "document"

    if not parts:
        async def _empty():
            yield f"data: {json.dumps({'token': 'No documents found matching your query.'})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        return StreamingResponse(_empty(), media_type="text/event-stream")

    context = "\n\n".join(parts)
    prompt  = _build_prompt(question, context, detected_type or "document", lang)
    logger.info(f"📝 Prompt: doc_type={detected_type}, length={len(prompt)} chars")

    return _make_stream(prompt, source_doc=source_doc)


class ContextAskRequest(BaseModel):
    question:     str
    context_data: dict = {}
    doc_type:     str  = ""
    lang:         Optional[str] = None


@router.post("/ask/with-context")
async def ask_with_context(req: ContextAskRequest, raw_request: Request, db: Session = Depends(get_db)):
    """
    Ask with explicit structured context — no RAG retrieval needed.
    Used when the caller already has all the data (policy detail, portfolio, etc.)
    The context_data shape auto-detects the doc_type and builds the right prompt profile.
    """
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question required")

    from app.core.language import get_request_language
    lang = req.lang or get_request_language(raw_request, db)

    structured_ctx = ""
    detected_type  = req.doc_type

    if req.context_data:
        result = _build_structured_context(req.context_data)
        structured_ctx, auto_type = result if isinstance(result, tuple) else (result, "")
        if not detected_type:
            detected_type = auto_type

    if not structured_ctx:
        raise HTTPException(status_code=400, detail="context_data is required for this endpoint")

    prompt = _build_prompt(req.question, structured_ctx, detected_type or "document", lang)
    logger.info(f"📝 Context ask: doc_type={detected_type}, context={len(structured_ctx)} chars")

    return _make_stream(prompt)


class VoiceIntentRequest(BaseModel):
    query: str


@router.post("/voice/intent")
async def voice_intent_classification(req: VoiceIntentRequest):
    """
    Classify the voice command intent (redirect, search, or answer).
    """
    q = req.query.lower().strip()

    # 1. Calendar/Schedule intents
    if any(w in q for w in ["schedule", "calendar", "appointment", "meeting", "events today", "today looks like", "what is today"]):
        return {
            "action": "redirect",
            "route": "/calendar",
            "confidence": 1.0
        }

    # 2. Documents intents
    if any(w in q for w in ["show documents", "open documents", "my documents", "view documents", "documents list"]):
        return {
            "action": "redirect",
            "route": "/documents",
            "confidence": 1.0
        }

    # 3. Search intents
    search_match = re.search(r'(?:search|find)(?:\s+the)?(?:\s+documents?)?(?:\s+for)?\s+(.+)', q)
    if search_match:
        term = search_match.group(1).strip()
        if term:
            return {
                "action": "redirect",
                "route": "/search",
                "search_term": term,
                "confidence": 1.0
            }

    # 4. LLM-based fallback
    try:
        import ollama
        client = ollama.Client()
        prompt = f"""Classify the user query into one of these actions:
- REDIRECT_DOCUMENTS (user wants to see, view, open, or list documents/files/library)
- REDIRECT_CALENDAR (user wants to see, view, open, or check calendar, appointments, schedule, agenda, timeline)
- SEARCH (user wants to search or find a specific term)
- ANSWER (user is asking a question about document contents or general assistance)

Query: "{req.query}"

Output ONLY a JSON block like:
{{"action": "REDIRECT_DOCUMENTS" | "REDIRECT_CALENDAR" | "SEARCH" | "ANSWER", "search_term": "extracted search term if action is SEARCH otherwise null"}}"""

        response = client.generate(
            model=config.model,
            prompt=prompt,
            options={"temperature": 0.0, "num_ctx": 4096}
        )
        res_text = response.get("response", "").strip()
        json_match = re.search(r'\{.*\}', res_text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            act = data.get("action")
            term = data.get("search_term")
            if act == "REDIRECT_DOCUMENTS":
                return {"action": "redirect", "route": "/documents", "confidence": 0.9}
            elif act == "REDIRECT_CALENDAR":
                return {"action": "redirect", "route": "/calendar", "confidence": 0.9}
            elif act == "SEARCH":
                return {"action": "redirect", "route": "/search", "search_term": term, "confidence": 0.9}
    except Exception as e:
        logger.error(f"LLM voice intent classification error: {e}")

    return {
        "action": "answer",
        "route": None,
        "search_term": None,
        "confidence": 0.5
    }


# =============================================================================
# PER-DOCUMENT ASK — moved from qa_router.py
# Uses pre-stored pgvector chunks (document_chunks table)
# Falls back to in-memory chunking if no chunks stored
# =============================================================================

from pydantic import BaseModel as _BaseModel

class QuestionRequest(_BaseModel):
    question: str
    lang: Optional[str] = None


def _assess_confidence(answer: str) -> float:
    """Heuristic confidence score based on answer content."""
    if not answer or len(answer) < 10:
        return 0.0
    low_conf = ["not available", "not found", "cannot find",
                "not in the document", "no information", "i could not"]
    if any(p in answer.lower() for p in low_conf):
        return 0.2
    if len(answer) > 200:
        return 0.9
    if len(answer) > 80:
        return 0.75
    return 0.6


@router.post("/{doc_id}/ask")
async def ask_document(doc_id: str, request: QuestionRequest, raw_request: Request, db: Session = Depends(get_db)):
    """
    Per-document RAG Q&A.

    Pipeline:
      1. Load document + check supports_qa capability
      2. RETRIEVE  — pgvector similarity on document_chunks (pre-embedded)
      3. AUGMENT   — build context from top-K chunks + doc metadata
      4. GENERATE  — stream phi3:mini from augmented context
      5. Fallback  — in-memory chunking if no stored chunks
    """
    from app.models.document import Document

    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # caps = (doc.doc_metadata or {}).get("capabilities", {})
        # if not caps.get("supports_qa", False):
        #     async def _no_qa():
        #         yield f"data: {json.dumps({'token': 'This document does not have enough text content to answer questions.'})}\n\n"
        #         yield f"data: {json.dumps({'done': True, 'confidence': 0.0, 'supports_qa': False})}\n\n"
        #     return StreamingResponse(_no_qa(), media_type="text/event-stream",
        #                              headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

        question = request.question.strip()
        logger.info(f"📄 Per-doc ask: doc={doc_id} | q='{question}'")

        # ── RETRIEVE ────────────────────────────────────────────────────────
        # Try pgvector chunk search first (fast, pre-embedded)
        # Detect whole-document intent — use all chunks
        _whole_doc_keywords = ["whole document", "entire document", "full document",
                                "everything", "all points", "summarize", "summary",
                                "bulleted list", "bullet points", "read the"]
        _wants_all = any(kw in question.lower() for kw in _whole_doc_keywords)
        _top_k = 12 if _wants_all else 4
        _max_prompt_chars = 6000 if _wants_all else 3000

        from app.core.language import get_request_language
        lang = request.lang or doc.language or get_request_language(raw_request, db)
        search_question = _translate_query_to_english_if_needed(question, lang)

        chunks = _retrieve_doc_chunks(doc_id, search_question, top_k=_top_k)

        # Fallback: in-memory chunking from raw_text
        if not chunks and doc.raw_text:
            logger.info("⚠ No stored chunks — falling back to in-memory chunking")
            chunks = _inmemory_chunks(search_question, doc.raw_text, top_k=4)

        # ── AUGMENT ─────────────────────────────────────────────────────────
        q_type  = _detect_q_type(question)
        # Cap context for whole-doc requests to keep phi3:mini focused
        _max_chars = _max_prompt_chars if '_max_prompt_chars' in dir() else 6000
        if _wants_all and len(chunks) > 10:
            # Join all chunks but cap total chars — phi3:mini degrades above 12k
            joined = "\n\n---\n\n".join(chunks)
            chunks = [joined[:_max_chars]]
        context = _build_doc_context(chunks, doc, q_type)

        # ── GENERATE ────────────────────────────────────────────────────────
        # Use doc-type-aware prompt from the shared _build_prompt
        prompt = _build_prompt(question, context, doc.doc_type or "document", lang)
        logger.info(f"📝 Per-doc prompt: doc_type={doc.doc_type}, q_type={q_type}, len={len(prompt)}")

        async def _stream():
            full_answer = ""
            try:
                import ollama as _ollama
                client = _ollama.Client()
                stream = client.generate(
                    model=config.model,
                    prompt=prompt,
                    stream=True,
                    options={
                        "temperature": 0.1,
                        "num_predict": 400,
                        "num_ctx": 4096,
                        "stop": ["Question:", "---", "\n\n\n"],
                    },
                )
                for chunk in stream:
                    token = chunk.get("response", "")
                    if token:
                        full_answer += token
                        yield f"data: {json.dumps({'token': token})}\n\n"

                confidence = _assess_confidence(full_answer)
                yield f"data: {json.dumps({'done': True, 'confidence': confidence, 'question_type': q_type})}\n\n"

            except Exception as e:
                logger.error(f"❌ Per-doc generation failed: {e}", exc_info=True)
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(
            _stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    finally:
        pass


# ── Per-doc helpers ────────────────────────────────────────────────────────────

def _detect_q_type(question: str) -> str:
    q = question.lower()
    if any(w in q for w in ["how much", "total", "amount", "balance", "fee", "cost", "sum"]):
        return "numeric"
    if any(w in q for w in ["when", "date", "period", "month", "year", "due"]):
        return "temporal"
    if any(w in q for w in ["who", "name", "holder", "owner", "party", "company"]):
        return "entity"
    if any(w in q for w in ["list", "what are", "show me", "enumerate",
                              "bulleted", "bullet", "points", "summarize",
                              "summary", "key points", "main points"]):
        return "list"
    return "general"


def _retrieve_doc_chunks(doc_id: str, question: str, top_k: int = 6, max_k: int = 50) -> list:
    """pgvector similarity search on pre-stored document_chunks."""
    try:
        from app.config.model_factory import EmbeddingModelFactory
        emb_model    = EmbeddingModelFactory.get_model()
        query_vector = emb_model.encode(question, show_progress_bar=False).tolist()

        db = SessionLocal()
        try:
            rows = db.execute(text("""
                SELECT chunk_text,
                       1 - (embedding <=> CAST(:vec AS vector)) AS similarity
                FROM document_chunks
                WHERE document_id = :doc_id
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:vec AS vector)
                LIMIT :top_k
            """), {"vec": str(query_vector), "doc_id": str(doc_id), "top_k": min(top_k, max_k)}).fetchall()

            logger.info(f"🔍 Chunk retrieval: {len(rows)} chunks for {doc_id}")
            return [r.chunk_text for r in rows if r.chunk_text]
        finally:
            db.close()
    except Exception as e:
        logger.error(f"❌ Chunk retrieval failed: {e}")
        return []


def _inmemory_chunks(question: str, raw_text: str, top_k: int = 4) -> list:
    """In-memory chunking fallback when no stored chunks exist."""
    import numpy as np

    chunk_size, overlap = 400, 80
    chunks, start = [], 0
    while start < len(raw_text):
        chunks.append(raw_text[start: start + chunk_size])
        start += chunk_size - overlap

    if not chunks:
        return []

    try:
        from app.config.model_factory import EmbeddingModelFactory
        emb_model = EmbeddingModelFactory.get_model()
        keywords  = [w for w in question.lower().split() if len(w) > 3]
        forced    = [c for c in chunks if any(kw in c.lower() for kw in keywords)]
        q_emb     = emb_model.encode(question, show_progress_bar=False)
        c_embs    = emb_model.encode(chunks, show_progress_bar=False, batch_size=32)
        scores    = np.dot(c_embs, q_emb) / (np.linalg.norm(c_embs, axis=1) * np.linalg.norm(q_emb) + 1e-9)
        top_idx   = np.argsort(scores)[::-1]
        semantic  = [chunks[i] for i in top_idx if chunks[i] not in forced]
        return (forced[:top_k] + semantic[:max(0, top_k - len(forced))])[:top_k + len(forced)]
    except Exception:
        # Last resort: first N chunks
        return chunks[:top_k]


def _build_doc_context(chunks: list, doc, q_type: str) -> str:
    """Build augmented context from retrieved chunks + document metadata."""
    parts = []

    if chunks:
        parts.append("Relevant Document Sections:\n" + "\n\n---\n\n".join(chunks))

    if doc.doc_type:
        parts.append(f"Document Type: {doc.doc_type.replace('_', ' ').title()}")

    meta = doc.doc_metadata or {}

    if doc.summary:
        parts.append(f"Document Summary: {doc.summary[:400]}")

    # Include key extracted fields from metadata
    extracted = meta.get("extracted_fields") or meta.get("fields") or {}
    if extracted:
        field_lines = "\n".join(
            f"  {k}: {v}" for k, v in list(extracted.items())[:15]
            if v and str(v).strip()
        )
        if field_lines:
            parts.append(f"Extracted Fields:\n{field_lines}")

    # Include AI insights
    insights = meta.get("insights") or []
    if insights:
        insight_lines = "\n".join(
            f"  - {i.get('title','')}: {i.get('detail','')}"
            for i in insights[:4] if i.get("title")
        )
        parts.append(f"Document Insights:\n{insight_lines}")

    return "\n\n".join(parts)