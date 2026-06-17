from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import urllib.parse
import json
import os
import tempfile
import logging

from db import get_db_connection, init_db
import cache
import translate
import classifier
import factcheck
import trust_score
import explain
import image_forensics

from contextlib import asynccontextmanager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database...")
    init_db()
    
    logger.info("Preloading classification models...")
    classifier.preload_models()
    
    logger.info("Preloading translation models (if enabled)...")
    translate.preload_translation_models()
    
    yield
    logger.info("Shutting down TruthLens API...")

app = FastAPI(
    title="TruthLens API",
    description="Backend API for TruthLens misinformation detection MVP",
    lifespan=lifespan
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    text: str
    url: Optional[str] = None

class FeedbackRequest(BaseModel):
    claim_id: int
    user_vote: str  # Must be "agree" or "disagree"
    comment: Optional[str] = None

def extract_domain(url: Optional[str]) -> Optional[str]:
    """Helper to extract domain hostnames from a URL string."""
    if not url:
        return None
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc or parsed.path
        # Split port if present
        domain = netloc.split(":")[0]
        # Remove typical www prefixes
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception as e:
        logger.warning(f"Failed to parse URL domain '{url}': {e}")
        return None

@app.get("/health")
def health():
    """Simple API health check endpoint."""
    return {"status": "ok"}

@app.post("/analyze")
def analyze(payload: AnalyzeRequest):
    """
    Analyzes claim text for potential misinformation.
    Caches inputs, detects language, translates, runs classifiers, looks up factchecks,
    computes trust score, writes to DB, and returns consolidated JSON.
    """
    text = payload.text
    url = payload.url
    
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Text field cannot be empty.")
        
    # 1. Cache Check
    cache_key = cache.get_cache_key(text)
    cached_val = cache.get(cache_key)
    if cached_val:
        try:
            cached_data = json.loads(cached_val)
            cached_data["cached"] = True
            logger.info("Serving cached analysis result.")
            return cached_data
        except Exception as e:
            logger.warning(f"Error reading cache data: {e}")
            
    # 2. Multilingual detection and translation
    trans_result = translate.translate_text(text)
    working_text = trans_result["translated_text"]
    detected_lang = trans_result["detected_language"]
    trans_applied = trans_result["translation_applied"]
    
    # 3. Domain Reliability Check
    domain = extract_domain(url)
    
    # 4. Veracity Classification (using Tier 1, 2, or 3)
    class_result = classifier.classify_text(working_text)
    fake_prob = class_result["fake_probability"]
    method = class_result["method"]
    
    # 5. Fact Check Database Lookup (queries Google API first, falls back to seeds)
    factcheck_match, api_status = factcheck.lookup_factcheck_with_status(text)
    if not factcheck_match and trans_applied:
        # Retry with translated text
        factcheck_match, api_status = factcheck.lookup_factcheck_with_status(working_text)
        
    # 6. Trust Score Aggregation
    ts_result = trust_score.compute_trust_score(
        fake_probability=fake_prob,
        factcheck_match=factcheck_match,
        domain=domain,
        manipulation_score=None
    )
    score = ts_result["trust_score"]
    label = ts_result["label"]
    
    # 7. Explanation justification
    explanation = explain.generate_explanation(
        claim_text=text,
        fake_probability=fake_prob,
        factcheck_match=factcheck_match,
        trust_score=score,
        label=label,
        domain=domain,
        manipulation_score=None,
        method=method
    )
    
    # 8. Record claim in SQLite database
    claim_id = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO claims (claim_text, verdict, score, source) VALUES (?, ?, ?, ?)",
            (text, label, score, url or "Direct Entry")
        )
        conn.commit()
        claim_id = cursor.lastrowid
        conn.close()
    except Exception as e:
        logger.error(f"Failed to save claim to database: {e}")
        
    # 9. Format response
    response_data = {
        "id": claim_id,
        "trust_score": score,
        "label": label,
        "fake_probability": fake_prob,
        "explanation": explanation,
        "factcheck_match": factcheck_match,
        "factcheck_api_status": api_status,
        "method": method,
        "language": detected_lang,
        "translation_applied": trans_applied,
        "cached": False
    }
    
    # 10. Write to Cache
    try:
        cache.set(cache_key, json.dumps(response_data))
    except Exception as e:
        logger.error(f"Failed to cache result: {e}")
        
    return response_data

@app.post("/analyze-image")
async def analyze_image(
    file: UploadFile = File(...),
    claim_id: Optional[int] = Form(None),
    claim_text: Optional[str] = Form(None)
):
    """
    Accepts multipart image upload, performs Error Level Analysis (ELA).
    If claim_id is supplied, re-calculates the trust score by blending in manipulation score.
    If claim_text is supplied, starts a new claim analysis pipeline with the image forensics blended.
    """
    suffix = os.path.splitext(file.filename)[1] or ".jpg"
    
    # Write incoming stream to temporary file
    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    
    try:
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
            
        forensics = image_forensics.analyze_image(temp_path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.warning(f"Error removing temporary image file: {e}")
                
    manipulation_score = forensics["manipulation_score"]
    
    # A. If linked to an existing claim ID
    if claim_id is not None:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, claim_text, score, source FROM claims WHERE id = ?", (claim_id,))
            row = cursor.fetchone()
            if row:
                orig_text = row["claim_text"]
                orig_score = row["score"]
                orig_source = row["source"]
                
                # Approximate original fake probability from database score
                approx_fake_prob = 1.0 - (orig_score / 100.0)
                factcheck_match, api_status = factcheck.lookup_factcheck_with_status(orig_text)
                domain = extract_domain(orig_source) if orig_source != "Direct Entry" else None
                
                # Recalculate blending in image manipulation
                updated_ts = trust_score.compute_trust_score(
                    fake_probability=approx_fake_prob,
                    factcheck_match=factcheck_match,
                    domain=domain,
                    manipulation_score=manipulation_score
                )
                
                new_score = updated_ts["trust_score"]
                new_label = updated_ts["label"]
                
                # Update DB
                cursor.execute(
                    "UPDATE claims SET score = ?, verdict = ? WHERE id = ?",
                    (new_score, new_label, claim_id)
                )
                conn.commit()
                conn.close()
                
                # Update cache
                cache_key = cache.get_cache_key(orig_text)
                updated_response = {
                    "id": claim_id,
                    "trust_score": new_score,
                    "label": new_label,
                    "fake_probability": approx_fake_prob,
                    "explanation": explain.generate_explanation(
                        claim_text=orig_text,
                        fake_probability=approx_fake_prob,
                        factcheck_match=factcheck_match,
                        trust_score=new_score,
                        label=new_label,
                        domain=domain,
                        manipulation_score=manipulation_score,
                        method="recalculated-image-blend"
                    ),
                    "factcheck_match": factcheck_match,
                    "factcheck_api_status": api_status,
                    "method": "recalculated-image-blend",
                    "language": "en",
                    "translation_applied": False,
                    "cached": False,
                    "manipulation_score": manipulation_score,
                    "forensics": forensics
                }
                cache.set(cache_key, json.dumps(updated_response))
                
                return {
                    "claim_id": claim_id,
                    "trust_score": new_score,
                    "label": new_label,
                    "manipulation_score": manipulation_score,
                    "forensics": forensics,
                    "status": "re-blended",
                    "factcheck_api_status": api_status
                }
            conn.close()
        except Exception as e:
            logger.error(f"Failed to re-blend image manipulation score: {e}")
            
    # B. If accompanied by a new claim text
    if claim_text is not None and claim_text.strip():
        trans_result = translate.translate_text(claim_text)
        working_text = trans_result["translated_text"]
        detected_lang = trans_result["detected_language"]
        trans_applied = trans_result["translation_applied"]
        
        class_result = classifier.classify_text(working_text)
        fake_prob = class_result["fake_probability"]
        method = class_result["method"]
        
        factcheck_match, api_status = factcheck.lookup_factcheck_with_status(claim_text)
        
        ts_result = trust_score.compute_trust_score(
            fake_probability=fake_prob,
            factcheck_match=factcheck_match,
            domain=None,
            manipulation_score=manipulation_score
        )
        score = ts_result["trust_score"]
        label = ts_result["label"]
        
        explanation = explain.generate_explanation(
            claim_text=claim_text,
            fake_probability=fake_prob,
            factcheck_match=factcheck_match,
            trust_score=score,
            label=label,
            domain=None,
            manipulation_score=manipulation_score,
            method=method
        )
        
        claim_id = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO claims (claim_text, verdict, score, source) VALUES (?, ?, ?, ?)",
                (claim_text, label, score, "Image Forensics Entry")
            )
            conn.commit()
            claim_id = cursor.lastrowid
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save image-linked claim: {e}")
            
        return {
            "id": claim_id,
            "trust_score": score,
            "label": label,
            "fake_probability": fake_prob,
            "explanation": explanation,
            "factcheck_match": factcheck_match,
            "factcheck_api_status": api_status,
            "method": method,
            "language": detected_lang,
            "translation_applied": trans_applied,
            "cached": False,
            "manipulation_score": manipulation_score,
            "forensics": forensics
        }
        
    return {
        "manipulation_score": manipulation_score,
        "forensics": forensics
    }

@app.post("/feedback")
def feedback(payload: FeedbackRequest):
    """Logs user feedback (thumbs up / thumbs down) for AI verdicts."""
    claim_id = payload.claim_id
    vote = payload.user_vote
    comment = payload.comment
    
    if vote not in ["agree", "disagree"]:
        raise HTTPException(status_code=400, detail="user_vote must be 'agree' or 'disagree'")
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO feedback (claim_id, user_vote, comment) VALUES (?, ?, ?)",
            (claim_id, vote, comment)
        )
        conn.commit()
        conn.close()
        logger.info(f"Feedback '{vote}' logged for claim {claim_id}")
        return {"status": "recorded"}
    except Exception as e:
        logger.error(f"Failed to log feedback: {e}")
        raise HTTPException(status_code=500, detail="Database feedback logging failure.")

@app.get("/history")
def history():
    """Retrieves the last 20 analysed claims for the history feed."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, claim_text, verdict, score, source, created_at FROM claims "
            "ORDER BY id DESC LIMIT 20"
        )
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            results.append({
                "id": row["id"],
                "claim_text": row["claim_text"],
                "verdict": row["verdict"],
                "score": row["score"],
                "source": row["source"],
                "created_at": row["created_at"]
            })
        return results
    except Exception as e:
        logger.error(f"Failed to query history: {e}")
        raise HTTPException(status_code=500, detail="Database query failure.")
