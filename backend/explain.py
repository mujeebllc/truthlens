import os
import requests
import logging

logger = logging.getLogger(__name__)

def generate_explanation(
    claim_text: str,
    fake_probability: float,
    factcheck_match: dict | None,
    trust_score: int,
    label: str
) -> str:
    """
    Generates a human-readable explanation of the claim veracity.
    Uses Anthropic Messages API if ANTHROPIC_API_KEY is defined in environment.
    Otherwise, generates a clean template-based explanation.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    
    if api_key:
        try:
            logger.info("Attempting Anthropic Claude API for justification explanation...")
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            
            prompt = (
                f"You are a neutral fact-checking assistant. Write a 2-3 sentence neutral, concise explanation summarizing "
                f"why this claim is rated {trust_score}/100 ({label}).\n\n"
                f"Claim: \"{claim_text}\"\n"
                f"Classifier Veracity Misleading Probability: {fake_probability:.2%}\n"
            )
            if factcheck_match:
                prompt += (
                    f"Fact-Check Match Verdict: {factcheck_match['verdict']}\n"
                    f"Fact-Check Source: {factcheck_match['source_name']}\n"
                    f"Fact-Check Summary: {factcheck_match['explanation_snippet']}\n"
                )
            else:
                prompt += "Fact-Check Match: None found in database.\n"
                
            prompt += "\nOutput ONLY the 2-3 sentence explanation. Do not add introductory remarks or greeting."
            
            data = {
                "model": "claude-sonnet-4-6",  # Specified in build instructions
                "max_tokens": 200,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            
            # Direct HTTP requests call is SDK independent
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=data,
                timeout=5
            )
            
            if response.status_code == 200:
                resp_json = response.json()
                content = resp_json.get("content", [])
                if content:
                    explanation = content[0].get("text", "").strip()
                    if explanation:
                        return explanation
            else:
                # If "claude-sonnet-4-6" is not recognized, retry with a standard model name
                logger.warning(f"Anthropic returned status {response.status_code}. Retrying with claude-3-5-sonnet...")
                data["model"] = "claude-3-5-sonnet-20241022"
                response = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=data,
                    timeout=5
                )
                if response.status_code == 200:
                    resp_json = response.json()
                    content = resp_json.get("content", [])
                    if content:
                        explanation = content[0].get("text", "").strip()
                        if explanation:
                            return explanation
                            
                logger.warning(f"Fallback Anthropic retry failed: {response.text}")
        except Exception as e:
            logger.error(f"Failed to generate explanation using Anthropic API: {e}")
            
    # Template-based fallback
    if factcheck_match:
        source_name = factcheck_match.get("source_name", "Fact-Check Repository")
        snippet = factcheck_match.get("explanation_snippet", "No details provided.")
        verdict = factcheck_match.get("verdict", "unsure")
        return (
            f"This claim closely matches a known fact-check from {source_name} (Verdict: {verdict.upper()}). "
            f"Fact-check details: \"{snippet}\""
        )
    else:
        fake_pct = fake_probability * 100.0
        return (
            f"Our AI analysis detects a {fake_pct:.0f}% likelihood that this claim contains misleading or sensationalized "
            f"language patterns. No matching direct fact-check was found in the database. Please verify using primary sources."
        )
