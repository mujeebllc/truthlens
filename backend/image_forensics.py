from PIL import Image, ImageChops, ImageStat
import os
import tempfile
import logging

logger = logging.getLogger(__name__)

def analyze_image(image_path: str) -> dict:
    """
    Performs Error Level Analysis (ELA) on an image to compute a manipulation score.
    Uses ImageStat for fast, C-optimized calculation of image difference statistics.
    
    Returns:
        dict: {
            "manipulation_score": float,
            "method": "ela-heuristic",
            "note": str
        }
    """
    try:
        # Open and normalize original image
        original = Image.open(image_path).convert("RGB")
        
        # Write to temporary file
        fd, temp_name = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        
        try:
            # Resave image at standard quality
            original.save(temp_name, "JPEG", quality=90)
            
            # Open resaved image
            resaved = Image.open(temp_name)
            
            # Compute difference image
            diff = ImageChops.difference(original, resaved)
            
            # Convert difference to grayscale
            diff_gray = diff.convert("L")
            
            # Calculate statistics using fast Pillow C-bindings
            img_stat = ImageStat.Stat(diff_gray)
            std_dev = img_stat.stddev[0]
            
            # Normalization heuristic:
            # Clean, unedited JPEGs have very uniform difference variance.
            # Local differences (edits/splicing) increase standard deviation.
            # Map standard deviation of difference to 0-1 range (std_dev of 8.0 represents max manipulation).
            manipulation_score = min(1.0, max(0.0, std_dev / 8.0))
            
        finally:
            # Ensure cleanup
            if os.path.exists(temp_name):
                try:
                    os.remove(temp_name)
                except Exception as cleanup_err:
                    logger.warning(f"Error deleting temp ELA file: {cleanup_err}")
                    
        return {
            "manipulation_score": float(round(manipulation_score, 4)),
            "method": "ela-heuristic",
            "note": "Lightweight heuristic — not a substitute for a trained deepfake CNN (e.g. EfficientNet on FaceForensics++/DFDC), which is the recommended production approach."
        }
        
    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        return {
            "manipulation_score": 0.0,
            "method": "ela-error",
            "note": f"ELA image analysis failed: {str(e)}"
        }
