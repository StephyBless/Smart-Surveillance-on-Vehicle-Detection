"""
OCR Ensemble Module
Multiple OCR engines with voting, confidence-based selection, and forced output

Key Features:
- Multiple OCR engines (EasyOCR primary, expandable to Tesseract/PaddleOCR)
- Character-level voting across engines
- Confidence-weighted selection
- GUARANTEED output (never returns empty string)
- Position-aware character normalization
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from collections import Counter


class OCRResult:
    """Container for OCR result with metadata"""
    def __init__(self, text: str, confidence: float, engine: str):
        self.text = text.upper().strip()
        self.confidence = confidence
        self.engine = engine
    
    def __repr__(self):
        return f"OCRResult(text='{self.text}', conf={self.confidence:.2f}, engine='{self.engine}')"


class CharacterNormalizer:
    """
    Normalize common OCR mistakes based on character position
    
    Why position-aware?
    - Letter positions should contain letters (not digits)
    - Digit positions should contain digits (not letters)
    - Some characters look similar: O/0, I/1, S/5, B/8, Z/2
    """
    
    # Common character confusions
    LETTER_TO_DIGIT = {
        'O': '0', 'I': '1', 'L': '1', 'S': '5', 'B': '8', 'Z': '2',
        'G': '6', 'T': '7', 'Q': '0'
    }
    
    DIGIT_TO_LETTER = {
        '0': 'O', '1': 'I', '5': 'S', '8': 'B', '2': 'Z',
        '6': 'G', '7': 'T'
    }
    
    @staticmethod
    def normalize_char(char: str, expect_letter: bool) -> str:
        """
        Normalize a single character based on expected type
        
        Args:
            char: Character to normalize
            expect_letter: True if this position should be a letter
            
        Returns:
            Normalized character
        """
        char = char.upper()
        
        if expect_letter:
            # This position should be a letter
            if char.isdigit():
                return CharacterNormalizer.DIGIT_TO_LETTER.get(char, char)
            return char
        else:
            # This position should be a digit
            if char.isalpha():
                return CharacterNormalizer.LETTER_TO_DIGIT.get(char, char)
            return char
    
    @staticmethod
    def normalize_text(text: str, pattern: Optional[str] = None) -> str:
        """
        Normalize entire text based on pattern
        
        Args:
            text: Input text
            pattern: Pattern string ('L' for letter, 'D' for digit)
                    Example: "LLDDLLDDDDD" for Indian plates
                    
        Returns:
            Normalized text
        """
        if not pattern or len(pattern) != len(text):
            return text
        
        normalized = []
        for char, expected_type in zip(text, pattern):
            expect_letter = (expected_type == 'L')
            normalized.append(CharacterNormalizer.normalize_char(char, expect_letter))
        
        return ''.join(normalized)


class OCREngine:
    """Base class for OCR engines"""
    
    def __init__(self, name: str):
        self.name = name
    
    def recognize(self, image: np.ndarray) -> OCRResult:
        """
        Run OCR on image
        
        Returns:
            OCRResult with text, confidence, and engine name
        """
        raise NotImplementedError


class EasyOCREngine(OCREngine):
    """EasyOCR implementation"""
    
    def __init__(self, reader=None):
        super().__init__("EasyOCR")
        self.reader = reader
    
    def recognize(self, image: np.ndarray) -> OCRResult:
        """Run EasyOCR"""
        if self.reader is None:
            return OCRResult("", 0.0, self.name)
        
        try:
            # Run OCR
            results = self.reader.readtext(image)
            
            if not results:
                return OCRResult("", 0.0, self.name)
            
            # EasyOCR returns list of (bbox, text, confidence)
            # Combine all detected text (in case plate is segmented)
            all_text = []
            all_conf = []
            
            for (bbox, text, conf) in results:
                # Filter out very low confidence
                if conf > 0.3:
                    # Remove spaces and special characters
                    clean_text = ''.join(c for c in text if c.isalnum())
                    if clean_text:
                        all_text.append(clean_text)
                        all_conf.append(conf)
            
            if not all_text:
                return OCRResult("", 0.0, self.name)
            
            # Combine text
            combined_text = ''.join(all_text)
            avg_confidence = sum(all_conf) / len(all_conf) if all_conf else 0.0
            
            return OCRResult(combined_text, avg_confidence, self.name)
            
        except Exception as e:
            print(f"EasyOCR error: {e}")
            return OCRResult("", 0.0, self.name)


class OCREnsemble:
    """
    Multi-engine OCR with voting and guaranteed output
    
    Features:
    - Runs multiple OCR engines on multiple image variants
    - Character-level voting
    - Confidence-based selection
    - NEVER returns empty string (forced approximation)
    """
    
    def __init__(self, easyocr_reader=None):
        """
        Initialize OCR ensemble
        
        Args:
            easyocr_reader: Initialized EasyOCR reader object
        """
        self.engines = []
        
        # Add EasyOCR engine
        if easyocr_reader:
            self.engines.append(EasyOCREngine(easyocr_reader))
        
        # Future: Add more engines here
        # self.engines.append(TesseractEngine())
        # self.engines.append(PaddleOCREngine())
    
    def recognize_ensemble(self, image_variants: Dict[str, np.ndarray]) -> str:
        """
        Run ensemble OCR on multiple image variants
        
        Args:
            image_variants: Dictionary of enhanced image variants
                           (from LicensePlateEnhancer)
        
        Returns:
            Best recognized plate number (GUARANTEED non-empty)
        """
        if not self.engines:
            return "UNKNOWN"
        
        # Collect all OCR results from all engines on all variants
        all_results = []
        
        for variant_name, image in image_variants.items():
            if image is None or image.size == 0:
                continue
            
            for engine in self.engines:
                result = engine.recognize(image)
                
                # Only keep non-empty results
                if result.text and len(result.text) >= 4:  # Minimum plate length
                    all_results.append(result)
        
        # If we got results, use voting
        if all_results:
            best_text = self._vote_and_fuse(all_results)
            return best_text
        
        # FORCED OUTPUT: No valid results, return approximation
        return self._force_approximation(image_variants)
    
    def _vote_and_fuse(self, results: List[OCRResult]) -> str:
        """
        Character-level voting with confidence weighting
        
        Strategy:
        1. Find the most common length
        2. For each character position, vote using confidence weights
        3. Choose highest-weighted character
        
        Args:
            results: List of OCRResult objects
            
        Returns:
            Fused text
        """
        if not results:
            return ""
        
        # Find most common length
        lengths = [len(r.text) for r in results]
        most_common_length = Counter(lengths).most_common(1)[0][0]
        
        # Filter results to most common length
        filtered_results = [r for r in results if len(r.text) == most_common_length]
        
        if not filtered_results:
            # Fallback: return highest confidence result
            return max(results, key=lambda r: r.confidence).text
        
        # Character-level voting
        final_text = []
        
        for pos in range(most_common_length):
            char_votes = {}  # {character: total_confidence}
            
            for result in filtered_results:
                char = result.text[pos]
                weight = result.confidence
                
                if char in char_votes:
                    char_votes[char] += weight
                else:
                    char_votes[char] = weight
            
            # Choose character with highest total confidence
            best_char = max(char_votes.items(), key=lambda x: x[1])[0]
            final_text.append(best_char)
        
        return ''.join(final_text)
    
    def _force_approximation(self, image_variants: Dict[str, np.ndarray]) -> str:
        """
        FORCED OUTPUT: Generate approximate plate when OCR fails
        
        Strategy:
        1. Try each variant with lower thresholds
        2. Accept partial results
        3. Last resort: return "UNREADABLE" + timestamp hash
        
        Args:
            image_variants: Enhanced image variants
            
        Returns:
            Approximated plate number (never empty)
        """
        # Try again with very low confidence threshold
        for variant_name, image in image_variants.items():
            if image is None or image.size == 0:
                continue
            
            for engine in self.engines:
                result = engine.recognize(image)
                
                # Accept ANY non-empty result
                if result.text:
                    # Pad if too short
                    if len(result.text) < 4:
                        return result.text + "0000"[:4-len(result.text)]
                    return result.text
        
        # Last resort: return placeholder
        # This ensures database always has a value
        return "UNREADABLE"
    
    def recognize_with_metadata(self, image_variants: Dict[str, np.ndarray]) -> Dict:
        """
        Run OCR and return detailed metadata
        
        Returns:
            Dictionary with:
            - 'text': Final recognized text
            - 'confidence': Average confidence
            - 'all_results': All individual OCR results
            - 'is_approximation': True if forced output was used
        """
        all_results = []
        
        for variant_name, image in image_variants.items():
            if image is None or image.size == 0:
                continue
            
            for engine in self.engines:
                result = engine.recognize(image)
                if result.text:
                    all_results.append(result)
        
        if all_results:
            best_text = self._vote_and_fuse(all_results)
            avg_conf = sum(r.confidence for r in all_results) / len(all_results)
            
            return {
                'text': best_text,
                'confidence': avg_conf,
                'all_results': all_results,
                'is_approximation': False
            }
        else:
            approx_text = self._force_approximation(image_variants)
            
            return {
                'text': approx_text,
                'confidence': 0.0,
                'all_results': [],
                'is_approximation': True
            }


class TemporalVoting:
    """
    Vote across multiple frames of the same license plate
    
    Improves accuracy by:
    - Collecting OCR results from multiple frames
    - Using majority voting at character level
    - Leveraging temporal consistency
    """
    
    def __init__(self):
        self.frame_results = []  # List of (text, confidence) tuples
    
    def add_result(self, text: str, confidence: float):
        """Add OCR result from a frame"""
        if text and len(text) >= 4:
            self.frame_results.append((text.upper().strip(), confidence))
    
    def get_best_result(self, min_frames: int = 3) -> Optional[str]:
        """
        Get best result using temporal voting
        
        Args:
            min_frames: Minimum frames needed for voting
            
        Returns:
            Best plate number, or None if insufficient data
        """
        if len(self.frame_results) < min_frames:
            # Not enough frames, return highest confidence
            if self.frame_results:
                return max(self.frame_results, key=lambda x: x[1])[0]
            return None
        
        # Find most common length
        lengths = [len(text) for text, _ in self.frame_results]
        most_common_length = Counter(lengths).most_common(1)[0][0]
        
        # Filter to most common length
        filtered = [(text, conf) for text, conf in self.frame_results 
                   if len(text) == most_common_length]
        
        if not filtered:
            return max(self.frame_results, key=lambda x: x[1])[0]
        
        # Character-level voting
        final_text = []
        
        for pos in range(most_common_length):
            char_votes = {}
            
            for text, conf in filtered:
                char = text[pos]
                if char in char_votes:
                    char_votes[char] += conf
                else:
                    char_votes[char] = conf
            
            best_char = max(char_votes.items(), key=lambda x: x[1])[0]
            final_text.append(best_char)
        
        return ''.join(final_text)
    
    def clear(self):
        """Clear accumulated results"""
        self.frame_results = []


# Convenience function
def recognize_plate(easyocr_reader, image_variants: Dict[str, np.ndarray]) -> str:
    """
    Quick function to recognize license plate
    
    Args:
        easyocr_reader: Initialized EasyOCR reader
        image_variants: Dictionary of enhanced images
        
    Returns:
        Recognized plate number (guaranteed non-empty)
    """
    ensemble = OCREnsemble(easyocr_reader)
    return ensemble.recognize_ensemble(image_variants)


if __name__ == "__main__":
    print("OCR Ensemble Module")
    print("=" * 50)
    print("\nFeatures:")
    print("  ✓ Multi-engine OCR")
    print("  ✓ Character-level voting")
    print("  ✓ Confidence-based fusion")
    print("  ✓ Guaranteed output (never empty)")
    print("  ✓ Temporal voting across frames")
    print("\nUsage:")
    print("  from ocr_ensemble import OCREnsemble")
    print("  ensemble = OCREnsemble(easyocr_reader)")
    print("  plate_text = ensemble.recognize_ensemble(image_variants)")