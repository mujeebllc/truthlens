import logging
from db import get_db_connection

logger = logging.getLogger(__name__)

def compute_trust_score(
    fake_probability: float,
    factcheck_match: dict | None,
    domain: str | None,
    manipulation_score: float | None = None
) -> dict:
    """
    Computes aggregated trust score (0-100) and categorizes veracity.
    
    Aggregation Logic:
      - Base score is (1 - fake_probability) * 100.
      - Blended/capped with fact check results:
          * verdict == "false": capped at 15.
          * verdict == "true": floored at 80.
          * verdict == "unsure": pulled towards 50 (50% blend).
      - Blended with domain reputation score (20% weight) if domain exists in seed table.
      - Deducts up to 20 points based on ELA image manipulation score.
      - Categorized as:
          * 0-30: "Likely False / Misinformation"
          * 31-60: "Unverified / Use Caution"
          * 61-100: "Likely Reliable"
    """
    # 1. Base score from text model probability
    score = (1.0 - fake_probability) * 100.0
    
    # 2. Fact check adjustments
    if factcheck_match:
        verdict = factcheck_match.get("verdict", "unsure")
        if verdict == "false":
            score = min(score, 15.0)
        elif verdict == "true":
            score = max(score, 80.0)
        elif verdict == "unsure":
            score = (score * 0.5) + (50.0 * 0.5)
            
    # 3. Domain reputation adjustment
    if domain:
        domain_score = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            # Clean domain name
            clean_domain = domain.strip().lower().replace("www.", "")
            cursor.execute("SELECT reliability_score FROM source_reputation WHERE domain = ? OR domain = ?", (clean_domain, domain.lower()))
            row = cursor.fetchone()
            if row:
                domain_score = row["reliability_score"]
            conn.close()
        except Exception as e:
            logger.error(f"Failed to lookup domain reputation for {domain}: {e}")
            
        if domain_score is not None:
            # 20% weight to domain, 80% weight to current score
            score = (score * 0.8) + (domain_score * 0.2)
            
    # 4. Image manipulation adjustment
    if manipulation_score is not None:
        score -= (manipulation_score * 20.0)
        
    # 5. Final clamp and round
    final_score = int(round(max(0.0, min(100.0, score))))
    
    # 6. Set qualitative label
    if final_score <= 30:
        label = "Likely False / Misinformation"
    elif final_score <= 60:
        label = "Unverified / Use Caution"
    else:
        label = "Likely Reliable"
        
    return {
        "trust_score": final_score,
        "label": label
    }
