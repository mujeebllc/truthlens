import os
import requests
import logging

logger = logging.getLogger(__name__)

def generate_explanation(
    claim_text: str,
    fake_probability: float,
    factcheck_match: dict | None,
    trust_score: int,
    label: str,
    domain: str | None = None,
    manipulation_score: float | None = None,
    method: str | None = None
) -> str:
    """
    Generates a human-readable explanation of the claim veracity.
    Uses Google Gemini API if GEMINI_API_KEY/GOOGLE_API_KEY/GOOGLE_FACTCHECK_API_KEY is defined.
    Otherwise, uses Anthropic Messages API if ANTHROPIC_API_KEY is defined in environment.
    Falls back to a rich, structured, template-based explanation.
    """
    
    # 1. Google Gemini API path
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_FACTCHECK_API_KEY")
    if gemini_key:
        try:
            logger.info("Attempting Google Gemini API for justification explanation...")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
            headers = {"Content-Type": "application/json"}
            
            prompt = (
                f"You are a professional fact-checking AI reviewer. Write a detailed, neutral, and objective 2-3 sentence audit review "
                f"explaining the veracity of the following claim based on the provided metrics and fact-checking results.\n\n"
                f"Claim: \"{claim_text}\"\n"
                f"Veracity Score: {trust_score}/100 (Label: {label})\n"
                f"Classifier Misleading probability: {fake_probability:.2%}\n"
            )
            if domain:
                prompt += f"Source Domain: {domain}\n"
            if manipulation_score is not None:
                prompt += f"Image Manipulation/ELA Score: {manipulation_score:.2%}\n"
            if method:
                prompt += f"Classifier Method: {method}\n"
            if factcheck_match:
                prompt += (
                    f"Fact-Check Verification Verdict: {factcheck_match['verdict'].upper()}\n"
                    f"Fact-Check Source: {factcheck_match['source_name']}\n"
                    f"Fact-Check Summary: {factcheck_match['explanation_snippet']}\n"
                )
            else:
                prompt += "No matching historical fact-check was found in the database.\n"
                
            prompt += "\nOutput ONLY the 2-3 sentence review text. Do not add markdown styling, bullet points, introductory remarks, or greetings."
            
            data = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }]
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=5)
            if response.status_code == 200:
                resp_json = response.json()
                candidates = resp_json.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        explanation = parts[0].get("text", "").strip()
                        if explanation:
                            return explanation
            else:
                logger.warning(f"Gemini API returned status {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"Failed to generate explanation using Gemini API: {e}")

    # 2. Anthropic Claude API path
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            logger.info("Attempting Anthropic Claude API for justification explanation...")
            headers = {
                "x-api-key": anthropic_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            
            prompt = (
                f"You are a professional fact-checking AI reviewer. Write a detailed, neutral, and objective 2-3 sentence audit review "
                f"explaining the veracity of the following claim based on the provided metrics and fact-checking results.\n\n"
                f"Claim: \"{claim_text}\"\n"
                f"Veracity Score: {trust_score}/100 (Label: {label})\n"
                f"Classifier Misleading probability: {fake_probability:.2%}\n"
            )
            if domain:
                prompt += f"Source Domain: {domain}\n"
            if manipulation_score is not None:
                prompt += f"Image Manipulation/ELA Score: {manipulation_score:.2%}\n"
            if method:
                prompt += f"Classifier Method: {method}\n"
            if factcheck_match:
                prompt += (
                    f"Fact-Check Verification Verdict: {factcheck_match['verdict'].upper()}\n"
                    f"Fact-Check Source: {factcheck_match['source_name']}\n"
                    f"Fact-Check Summary: {factcheck_match['explanation_snippet']}\n"
                )
            else:
                prompt += "No matching historical fact-check was found in the database.\n"
                
            prompt += "\nOutput ONLY the 2-3 sentence review text. Do not add markdown styling, bullet points, introductory remarks, or greetings."
            
            data = {
                "model": "claude-3-5-sonnet-latest",
                "max_tokens": 200,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            
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
                logger.warning(f"Anthropic returned status {response.status_code}. Retrying with fallback model...")
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
        except Exception as e:
            logger.error(f"Failed to generate explanation using Anthropic API: {e}")
            
    # 3. Premium Template-based fallback
    parts = []
    
    # A. Fact-check status
    if factcheck_match:
        source_name = factcheck_match.get("source_name", "Fact-Check Repository")
        snippet = factcheck_match.get("explanation_snippet", "No details provided.")
        verdict = factcheck_match.get("verdict", "unsure")
        origin_str = "Google Fact-Check Tools API" if factcheck_match.get("origin") == "google-factcheck-api" else "Local Seed Database"
        parts.append(
            f"🔍 FACT-CHECK MATCH: This statement matches a verified record from {source_name} "
            f"({origin_str}), which rated it as {verdict.upper()}. "
            f"Review snippet: \"{snippet}\""
        )
    else:
        parts.append(
            f"🔍 FACT-CHECK STATUS: No matching verification record was found in either the "
            f"Google Fact Check database or our local index."
        )

    # B. Classifier Analysis
    fake_pct = fake_probability * 100.0
    style_indicators = []
    
    text_lower = claim_text.lower()
    sensational_words = ["cure", "miracle", "shocking", "secret", "conspiracy", "exposed", "unbelievable"]
    matched_sensational = [w for w in sensational_words if w in text_lower]
    if matched_sensational:
        style_indicators.append(f"sensational words ({', '.join(matched_sensational)})")
    if "!!!" in claim_text or "???" in claim_text:
        style_indicators.append("exclamation/question spam")
    letters = [c for c in claim_text if c.isalpha()]
    if letters:
        cap_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if cap_ratio > 0.30:
            style_indicators.append("high capitalization")
            
    style_str = f" containing {', '.join(style_indicators)}" if style_indicators else ""
    
    if fake_probability > 0.6:
        parts.append(
            f"🤖 STYLISTIC ANALYSIS: The neural classifier detected a high likelihood ({fake_pct:.0f}%) "
            f"of sensationalism or misleading rhetoric{style_str}. The text patterns strongly align "
            f"with known disinformation frameworks."
        )
    elif fake_probability > 0.3:
        parts.append(
            f"🤖 STYLISTIC ANALYSIS: The classifier flags a moderate risk ({fake_pct:.0f}%) of "
            f"sensationalized language{style_str}. The wording is partially biased or lacks typical neutral editorial tone."
        )
    else:
        parts.append(
            f"🤖 STYLISTIC ANALYSIS: The text uses standard, objective language patterns ({fake_pct:.0f}% misleading probability). "
            f"No sensationalist rhetoric or structural patterns typical of clickbait were identified."
        )

    # C. Domain check
    if domain:
        parts.append(
            f"🌐 SOURCE REPUTATION: The claim was submitted from {domain}. Please verify "
            f"the credibility of this publisher against standard journalistic practices."
        )
        
    # D. Image check
    if manipulation_score is not None:
        manip_pct = manipulation_score * 100.0
        if manipulation_score > 0.6:
            parts.append(
                f"🖼️ FORENSIC AUDIT: Error Level Analysis (ELA) detected critical compression differences ({manip_pct:.1f}%), "
                f"strongly suggesting the image has been digitally altered or manipulated."
            )
        elif manipulation_score > 0.2:
            parts.append(
                f"🖼️ FORENSIC AUDIT: ELA scan highlights moderate pixel anomalies ({manip_pct:.1f}%), "
                f"indicating potential localized resaving or minor edits."
            )
        else:
            parts.append(
                f"🖼️ FORENSIC AUDIT: ELA scan shows consistent compression layers ({manip_pct:.1f}%), "
                f"suggesting the image is likely original and has not undergone structural manipulation."
            )

    # E. Synthesis summary
    parts.append(
        f"🎯 SUMMARY: Overall veracity score is {trust_score}/100, which classifies this claim as '{label}'. "
        f"We recommend cross-referencing this information with multiple primary sources."
    )
    
    return "\n\n".join(parts)
