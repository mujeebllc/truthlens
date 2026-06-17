from langdetect import detect
import logging

logger = logging.getLogger(__name__)

# Cache pipelines to avoid loading them repeatedly
_translation_pipelines = {}

def preload_translation_models():
    """
    Preloads translation models for supported languages into memory at startup
    if environment variable PRELOAD_TRANSLATION_MODELS is set to 'true'.
    """
    import os
    if os.getenv("PRELOAD_TRANSLATION_MODELS", "false").lower() != "true":
        logger.info("Translation models preloading is disabled (PRELOAD_TRANSLATION_MODELS != true).")
        return
        
    global _translation_pipelines
    supported_langs = {"es", "fr", "ur", "ar"}
    try:
        from transformers import pipeline
        for lang in supported_langs:
            model_name = f"Helsinki-NLP/opus-mt-{lang}-en"
            if model_name not in _translation_pipelines:
                logger.info(f"Preloading translation pipeline for: {model_name}")
                _translation_pipelines[model_name] = pipeline("translation", model=model_name)
    except Exception as e:
        logger.warning(f"Failed to preload translation models: {e}")

def detect_language(text: str) -> str:
    """Detect language of the input text, falling back to 'en' on failure."""
    if not text or not text.strip():
        return "en"
    try:
        return detect(text)
    except Exception as e:
        logger.warning(f"langdetect failed: {e}. Defaulting to 'en'.")
        return "en"

def translate_text(text: str) -> dict:
    """
    Detects language and translates to English if supported and necessary.
    Returns:
        dict: {
            "translated_text": str,
            "detected_language": str,
            "translation_applied": bool,
            "note": str | None
        }
    """
    lang = detect_language(text)
    
    if lang == "en":
        return {
            "translated_text": text,
            "detected_language": "en",
            "translation_applied": False,
            "note": None
        }
    
    supported_langs = {"es", "fr", "ur", "ar"}
    if lang not in supported_langs:
        return {
            "translated_text": text,
            "detected_language": lang,
            "translation_applied": False,
            "note": f"Language '{lang}' is not supported for translation. Analysis may be less accurate."
        }
        
    try:
        # Import transformers inside the try-except block to prevent startup errors 
        # if the user runs in heuristic mode without transformers installed.
        from transformers import pipeline
        
        model_name = f"Helsinki-NLP/opus-mt-{lang}-en"
        if model_name not in _translation_pipelines:
            logger.info(f"Loading translation pipeline for: {model_name}")
            _translation_pipelines[model_name] = pipeline("translation", model=model_name)
            
        result = _translation_pipelines[model_name](text)
        translated = result[0]["translation_text"]
        return {
            "translated_text": translated,
            "detected_language": lang,
            "translation_applied": True,
            "note": None
        }
    except Exception as e:
        logger.warning(f"Translation failed: {e}")
        return {
            "translated_text": text,
            "detected_language": lang,
            "translation_applied": False,
            "note": f"Translation model unavailable/failed: {str(e)}. Analysis may be less accurate."
        }
