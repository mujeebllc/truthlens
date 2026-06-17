import os
import re
import logging

logger = logging.getLogger(__name__)

_classifier_pipeline = None
_zero_shot_pipeline = None

# Model directory path relative to this file
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model", "truthlens_distilbert")

def preload_models():
    """
    Preloads DistilBERT and Zero-shot BART classifiers into memory at startup.
    This eliminates latency on the first request.
    """
    global _classifier_pipeline, _zero_shot_pipeline
    
    # Preload DistilBERT if model directory exists
    if os.path.exists(MODEL_DIR):
        try:
            from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
            if _classifier_pipeline is None:
                logger.info(f"Preloading Fine-tuned DistilBERT pipeline from: {MODEL_DIR}")
                tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
                model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
                _classifier_pipeline = pipeline("text-classification", model=model, tokenizer=tokenizer)
        except Exception as e:
            logger.error(f"Failed to preload DistilBERT pipeline: {e}")
            
    # Preload Zero-shot BART
    try:
        from transformers import pipeline
        if _zero_shot_pipeline is None:
            logger.info("Preloading Zero-Shot BART classifier (facebook/bart-large-mnli)...")
            _zero_shot_pipeline = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
    except Exception as e:
        logger.error(f"Failed to preload Zero-shot BART pipeline: {e}")

def heuristic_classify(text: str) -> float:
    """
    Tier 3: Pure heuristic rule-based classifier.
    Examines capitalized word ratios, excessive punctuation, and sensationalist keywords.
    """
    score = 0.20
    text_lower = text.lower()
    
    # 1. Sensationalist keywords/phrases
    sensational_words = [
        "cure", "miracle", "shocking", "secret", "don't want you to know", 
        "conspiracy", "exposed", "omg", "unbelievable", "mind-blowing", 
        "100% working", "free money", "hoax", "insane", "alien", "glitch",
        "secret plot", "collapsing", "never before seen", "scientists stunned"
    ]
    for word in sensational_words:
        if word in text_lower:
            score += 0.15
            
    # 2. Capitalization check (e.g. ALL CAPS words indicative of clickbait)
    letters = [c for c in text if c.isalpha()]
    if len(letters) > 8:
        cap_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if cap_ratio > 0.40:
            score += 0.20
            
    # 3. Excessive exclamation or question punctuation
    if "!!!" in text or "???" in text or "?!" in text:
        score += 0.15
        
    # 4. Absolute assertions
    absolute_words = ["always", "never", "100%", "proven fact", "guaranteed"]
    for word in absolute_words:
        if word in text_lower:
            score += 0.10
            
    # Clamp between 0.05 (almost certainly credible) and 0.95 (highly suspicious)
    return float(round(min(0.95, max(0.05, score)), 4))

def classify_text(text: str) -> dict:
    """
    Exposes a unified text classification API.
    Attempts model evaluation in the following order:
      1. Local Fine-tuned DistilBERT (LIAR dataset)
      2. Zero-shot BART (facebook/bart-large-mnli)
      3. Custom heuristic analysis (offline fallback)
    """
    global _classifier_pipeline, _zero_shot_pipeline
    
    # Tier 1: Local Fine-tuned DistilBERT model
    if os.path.exists(MODEL_DIR):
        try:
            from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
            if _classifier_pipeline is None:
                logger.info(f"Loading Fine-tuned DistilBERT pipeline from: {MODEL_DIR}")
                tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
                model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
                _classifier_pipeline = pipeline("text-classification", model=model, tokenizer=tokenizer)
                
            result = _classifier_pipeline(text)[0]
            label = result["label"].upper()  # Expect "LABEL_0" or "LABEL_1"
            score = result["score"]
            
            # Map Label 1 (False/Misleading) to fake_probability
            if label == "LABEL_1":
                fake_prob = score
            else:
                fake_prob = 1.0 - score
                
            return {
                "fake_probability": float(round(fake_prob, 4)),
                "method": "finetuned-distilbert-liar"
            }
        except Exception as e:
            logger.error(f"DistilBERT inference pipeline failed: {e}. Trying BART zero-shot fallback...")
            
    # Tier 2: Zero-shot BART classifier
    try:
        from transformers import pipeline
        if _zero_shot_pipeline is None:
            logger.info("Loading Zero-Shot BART classifier (facebook/bart-large-mnli)...")
            _zero_shot_pipeline = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
            
        candidate_labels = [
            "credible factual claim",
            "false or misleading claim",
            "satirical or unverifiable claim"
        ]
        
        result = _zero_shot_pipeline(text, candidate_labels=candidate_labels)
        labels = result["labels"]
        scores = result["scores"]
        
        # Retrieve score of the false/misleading label
        false_idx = labels.index("false or misleading claim")
        fake_prob = scores[false_idx]
        
        return {
            "fake_probability": float(round(fake_prob, 4)),
            "method": "zero-shot-bart"
        }
    except Exception as e:
        logger.error(f"Zero-shot BART pipeline failed: {e}. Falling back to heuristics...")
        
    # Tier 3: Custom Heuristics
    fake_prob = heuristic_classify(text)
    return {
        "fake_probability": fake_prob,
        "method": "heuristic"
    }
