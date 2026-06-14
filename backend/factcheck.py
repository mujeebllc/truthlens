import os
import json
import requests
import urllib.parse
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

def get_jaccard_similarity(s1: str, s2: str) -> float:
    """Computes Jaccard similarity based on overlapping alpha-numeric words."""
    w1 = set("".join(c for c in s1.lower() if c.isalnum() or c.isspace()).split())
    w2 = set("".join(c for c in s2.lower() if c.isalnum() or c.isspace()).split())
    if not w1 or not w2:
        return 0.0
    return len(w1.intersection(w2)) / len(w1.union(w2))

def map_textual_rating(rating: str) -> str:
    """Maps Google Fact Check API textualRating strings to a clean 'true' | 'false' | 'unsure' category."""
    if not rating:
        return "unsure"
    rating_lower = rating.lower()
    
    false_terms = {"false", "mostly false", "fake", "incorrect", "misleading", "pants", "fire", "myth", "not true", "untrue", "debunked"}
    true_terms = {"true", "mostly true", "correct", "accurate", "verified", "truth"}
    
    if any(term in rating_lower for term in false_terms):
        return "false"
    if any(term in rating_lower for term in true_terms):
        return "true"
    return "unsure"

def lookup_factcheck(claim_text: str) -> dict | None:
    """
    Look up fact check records.
    First tries the live Google Fact Check Tools API if GOOGLE_FACTCHECK_API_KEY is available.
    If unavailable, fails, or misses, falls back to Jaccard token-matching on seeded database claims.
    """
    api_key = os.getenv("GOOGLE_FACTCHECK_API_KEY")
    
    # 1. Google Fact Check Tools API path
    if api_key:
        try:
            encoded_query = urllib.parse.quote(claim_text)
            url = f"https://factchecktools.googleapis.com/v1alpha1/claims:search?query={encoded_query}&key={api_key}"
            logger.info("Attempting Google Fact Check Tools API lookup...")
            response = requests.get(url, timeout=4)
            if response.status_code == 200:
                data = response.json()
                claims = data.get("claims", [])
                if claims:
                    top_claim = claims[0]
                    reviews = top_claim.get("claimReview", [])
                    if reviews:
                        top_review = reviews[0]
                        rating = top_review.get("textualRating", "")
                        return {
                            "claim_text": top_claim.get("text", claim_text),
                            "verdict": map_textual_rating(rating),
                            "explanation_snippet": top_review.get("title", rating),
                            "source_name": top_review.get("publisher", {}).get("name", "Google Fact-Check"),
                            "source_url": top_review.get("url", ""),
                            "origin": "google-factcheck-api"
                        }
            else:
                logger.warning(f"Google Fact Check API responded with status {response.status_code}")
        except Exception as e:
            logger.error(f"Google Fact Check API query failed: {e}")
            
    # 2. Local seed fallback path
    try:
        seed_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "factchecks_seed.json")
        if os.path.exists(seed_path):
            with open(seed_path, "r", encoding="utf-8") as f:
                seed_claims = json.load(f)
                
            best_match = None
            best_score = 0.0
            
            for seed in seed_claims:
                score = get_jaccard_similarity(claim_text, seed["claim_text"])
                if score > best_score:
                    best_score = score
                    best_match = seed
                    
            if best_score > 0.5 and best_match:
                logger.info(f"Local seed match found (similarity {best_score:.2f})")
                return {
                    "claim_text": best_match["claim_text"],
                    "verdict": best_match["verdict"],
                    "explanation_snippet": best_match["explanation_snippet"],
                    "source_name": best_match["source_name"],
                    "source_url": best_match["source_url"],
                    "origin": "seeded-demo-data"
                }
    except Exception as e:
        logger.error(f"Local seeded factcheck lookup failed: {e}")
        
    return None
