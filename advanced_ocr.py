"""
Advanced OCR Module for License Plate Recognition
Handles: fancy fonts, damaged plates, multi-line plates, regional variations
"""

import cv2
import numpy as np
import re
from typing import List, Dict, Tuple, Optional
import logging

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


class AdvancedPlateOCR:
    """
    Advanced OCR system with multiple recognition strategies
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize OCR engines
        self.ocr_engines = []
        
        if EASYOCR_AVAILABLE:
            try:
                self.easyocr_reader = easyocr.Reader(['en'], gpu=False)
                self.ocr_engines.append('easyocr')
                self.logger.info("EasyOCR initialized")
            except Exception as e:
                self.logger.error(f"EasyOCR init error: {e}")
        
        if TESSERACT_AVAILABLE:
            self.ocr_engines.append('tesseract')
            self.logger.info("Tesseract available")
        
        # License plate patterns for different regions
        self.plate_patterns = {
            'standard': r'^[A-Z0-9]{2,4}\s*[A-Z0-9]{2,4}$',  # AB12 CD34
            'us_style': r'^[A-Z0-9]{1,3}\s*[A-Z0-9]{2,4}$',  # ABC 1234
            'eu_style': r'^[A-Z]{1,3}\s*[0-9]{1,4}\s*[A-Z]{1,3}$',  # AA 1234 BB
            'india_old': r'^[A-Z]{2}\s*[0-9]{1,2}\s*[A-Z]{1,2}\s*[0-9]{1,4}$',  # DL 01 AB 1234
            'india_new': r'^[A-Z]{2}\s*[0-9]{2}\s*[A-Z]{2}\s*[0-9]{4}$',  # DL 01 AB 1234
            'flexible': r'^[A-Z0-9]{4,10}$'  # Fallback: 4-10 alphanumeric
        }
        
        # Character correction mappings
        self.char_corrections = {
            '0': ['O', 'D', 'Q'],
            'O': ['0', 'D', 'Q'],
            '1': ['I', 'L', '|'],
            'I': ['1', 'L', '|'],
            'L': ['1', 'I', '|'],
            '5': ['S'],
            'S': ['5'],
            '8': ['B'],
            'B': ['8'],
            '2': ['Z'],
            'Z': ['2'],
            '6': ['G'],
            'G': ['6']
        }
    
    def recognize_plate(self, plate_images: Dict, confidence_threshold: float = 0.5) -> Dict:
        """
        Multi-strategy OCR recognition
        
        Args:
            plate_images: Dict of preprocessed plate images
            confidence_threshold: Minimum confidence score
        
        Returns:
            Dict with best result and all attempts
        """
        all_results = []
        
        # Try OCR on each image variant
        for variant_name, image in plate_images.items():
            if image is None or image.size == 0:
                continue
            
            # Try each OCR engine
            for engine in self.ocr_engines:
                try:
                    if engine == 'easyocr':
                        result = self._recognize_easyocr(image)
                    elif engine == 'tesseract':
                        result = self._recognize_tesseract(image)
                    else:
                        continue
                    
                    if result:
                        result['variant'] = variant_name
                        result['engine'] = engine
                        all_results.append(result)
                        
                except Exception as e:
                    self.logger.error(f"OCR error ({engine}, {variant_name}): {e}")
        
        # Post-process and rank results
        processed_results = []
        for result in all_results:
            processed = self._post_process_result(result)
            if processed['confidence'] >= confidence_threshold:
                processed_results.append(processed)
        
        # Select best result
        if processed_results:
            best_result = max(processed_results, key=lambda x: x['confidence'])
            
            return {
                'success': True,
                'plate_number': best_result['text'],
                'confidence': best_result['confidence'],
                'engine': best_result['engine'],
                'variant': best_result['variant'],
                'all_attempts': processed_results
            }
        
        return {
            'success': False,
            'plate_number': '',
            'confidence': 0.0,
            'all_attempts': all_results
        }
    
    def _recognize_easyocr(self, image: np.ndarray) -> Dict:
        """EasyOCR recognition"""
        results = self.easyocr_reader.readtext(image, detail=1, paragraph=False)
        
        if not results:
            return None
        
        # Combine all detected text
        texts = []
        confidences = []
        
        for bbox, text, conf in results:
            # Filter out non-alphanumeric
            cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
            if cleaned:
                texts.append(cleaned)
                confidences.append(conf)
        
        if not texts:
            return None
        
        combined_text = ''.join(texts)
        avg_confidence = sum(confidences) / len(confidences)
        
        return {
            'text': combined_text,
            'confidence': avg_confidence,
            'raw_results': results
        }
    
    def _recognize_tesseract(self, image: np.ndarray) -> Dict:
        """Tesseract OCR recognition"""
        # Configure Tesseract for license plates
        custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        
        text = pytesseract.image_to_string(image, config=custom_config)
        data = pytesseract.image_to_data(image, config=custom_config, output_type=pytesseract.Output.DICT)
        
        # Calculate average confidence
        confidences = [int(conf) for conf in data['conf'] if conf != '-1']
        avg_confidence = sum(confidences) / len(confidences) / 100 if confidences else 0
        
        # Clean text
        cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
        
        if not cleaned:
            return None
        
        return {
            'text': cleaned,
            'confidence': avg_confidence,
            'raw_text': text
        }
    
    def _post_process_result(self, result: Dict) -> Dict:
        """
        Post-process OCR result with corrections and validation
        """
        text = result['text']
        confidence = result['confidence']
        
        # 1. Remove common OCR errors
        text = self._apply_character_corrections(text)
        
        # 2. Format spacing
        text = self._format_spacing(text)
        
        # 3. Validate against patterns
        validation_score = self._validate_plate_format(text)
        
        # 4. Adjust confidence based on validation
        adjusted_confidence = confidence * validation_score
        
        return {
            'text': text,
            'confidence': adjusted_confidence,
            'original_text': result['text'],
            'original_confidence': confidence,
            'validation_score': validation_score,
            'engine': result.get('engine', 'unknown'),
            'variant': result.get('variant', 'unknown')
        }
    
    def _apply_character_corrections(self, text: str) -> str:
        """
        Apply intelligent character corrections
        """
        corrected = text
        
        # Context-based corrections
        # If character at start/end is digit-like, prefer letter
        # If character in middle is letter-like, prefer digit
        
        result = list(corrected)
        
        for i, char in enumerate(result):
            # Position-based heuristics
            if i < 2 or i >= len(result) - 2:
                # Likely letters at start/end
                if char in ['0', '1', '5', '8']:
                    if char == '0':
                        result[i] = 'O'
                    elif char == '1':
                        result[i] = 'I'
                    elif char == '5':
                        result[i] = 'S'
                    elif char == '8':
                        result[i] = 'B'
            else:
                # Likely numbers in middle
                if char in ['O', 'I', 'S', 'B']:
                    if char == 'O':
                        result[i] = '0'
                    elif char == 'I':
                        result[i] = '1'
                    elif char == 'S':
                        result[i] = '5'
                    elif char == 'B':
                        result[i] = '8'
        
        return ''.join(result)
    
    def _format_spacing(self, text: str) -> str:
        """
        Add appropriate spacing to plate number
        """
        # Remove existing spaces
        text = text.replace(' ', '')
        
        # Try to identify natural groupings
        if len(text) == 6:
            # Format: AB 1234 or AB1 234
            if text[:2].isalpha() and text[2:].isdigit():
                return f"{text[:2]} {text[2:]}"
            elif text[:3].isalpha() and text[3:].isdigit():
                return f"{text[:3]} {text[3:]}"
        
        elif len(text) == 7:
            # Format: AB 12 CD or ABC 1234
            if text[:2].isalpha() and text[2:4].isdigit():
                return f"{text[:2]} {text[2:4]} {text[4:]}"
            elif text[:3].isalpha() and text[3:].isdigit():
                return f"{text[:3]} {text[3:]}"
        
        elif len(text) == 8:
            # Format: AB 12 CD 34 or AB12 CD34
            if text[:2].isalpha():
                return f"{text[:2]} {text[2:4]} {text[4:6]} {text[6:]}"
        
        elif len(text) == 10:
            # Format: DL 01 AB 1234
            return f"{text[:2]} {text[2:4]} {text[4:6]} {text[6:]}"
        
        return text
    
    def _validate_plate_format(self, text: str) -> float:
        """
        Validate plate format against known patterns
        Returns score 0.0-1.0
        """
        # Remove spaces for pattern matching
        text_no_space = text.replace(' ', '')
        
        # Check length
        if len(text_no_space) < 4 or len(text_no_space) > 12:
            return 0.3
        
        # Check against patterns
        for pattern_name, pattern in self.plate_patterns.items():
            if re.match(pattern, text):
                return 1.0
        
        # Partial validation
        # Check if it has reasonable mix of letters and numbers
        letters = sum(c.isalpha() for c in text_no_space)
        digits = sum(c.isdigit() for c in text_no_space)
        
        if letters > 0 and digits > 0:
            ratio = min(letters, digits) / max(letters, digits)
            return 0.5 + (ratio * 0.3)  # 0.5-0.8 range
        
        return 0.4  # Low confidence for all letters or all digits
    
    def recognize_multi_line_plate(self, plate_image: np.ndarray) -> Dict:
        """
        Handle multi-line license plates
        """
        try:
            gray = cv2.cvtColor(plate_image, cv2.COLOR_BGR2GRAY) if len(plate_image.shape) == 3 else plate_image
            
            # Detect text lines using horizontal projection
            projection = np.sum(gray < 128, axis=1)
            
            # Find peaks (text lines)
            from scipy.signal import find_peaks
            peaks, _ = find_peaks(projection, height=gray.shape[1] * 0.3, distance=10)
            
            if len(peaks) < 2:
                # Not multi-line, use standard recognition
                return None
            
            # Split into lines and recognize each
            lines = []
            for i in range(len(peaks)):
                # Define line boundaries
                if i == 0:
                    y_start = 0
                else:
                    y_start = (peaks[i-1] + peaks[i]) // 2
                
                if i == len(peaks) - 1:
                    y_end = gray.shape[0]
                else:
                    y_end = (peaks[i] + peaks[i+1]) // 2
                
                line_img = plate_image[y_start:y_end, :]
                
                # Recognize this line
                line_result = self.recognize_plate({'line': line_img})
                if line_result['success']:
                    lines.append(line_result['plate_number'])
            
            # Combine lines
            if lines:
                combined = ' '.join(lines)
                return {
                    'success': True,
                    'plate_number': combined,
                    'confidence': 0.8,
                    'multi_line': True,
                    'lines': lines
                }
            
        except Exception as e:
            self.logger.error(f"Multi-line recognition error: {e}")
        
        return None
    
    def handle_damaged_plate(self, plate_image: np.ndarray) -> Dict:
        """
        Attempt to recognize damaged or partially occluded plates
        """
        try:
            # Apply aggressive preprocessing
            gray = cv2.cvtColor(plate_image, cv2.COLOR_BGR2GRAY) if len(plate_image.shape) == 3 else plate_image
            
            # Morphological reconstruction to fill gaps
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            
            # Try inpainting missing regions
            _, mask = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY_INV)
            inpainted = cv2.inpaint(gray, mask, 3, cv2.INPAINT_TELEA)
            
            # Recognize
            result = self.recognize_plate({'damaged': inpainted})
            
            if result['success']:
                result['damaged_plate'] = True
                # Lower confidence due to damage
                result['confidence'] *= 0.8
            
            return result
            
        except Exception as e:
            self.logger.error(f"Damaged plate recognition error: {e}")
            return {'success': False}
    
    def fuzzy_match_plates(self, detected: str, reference: str) -> float:
        """
        Fuzzy matching for plates (handles small OCR errors)
        Returns similarity score 0.0-1.0
        """
        from difflib import SequenceMatcher
        
        # Normalize
        det = detected.replace(' ', '').upper()
        ref = reference.replace(' ', '').upper()
        
        # Base similarity
        base_score = SequenceMatcher(None, det, ref).ratio()
        
        # Check character-by-character with corrections
        if len(det) == len(ref):
            matches = 0
            for i, (d, r) in enumerate(zip(det, ref)):
                if d == r:
                    matches += 1
                elif d in self.char_corrections.get(r, []) or r in self.char_corrections.get(d, []):
                    matches += 0.5  # Partial match for similar characters
            
            char_score = matches / len(det)
            
            # Weighted average
            final_score = (base_score * 0.4) + (char_score * 0.6)
            return final_score
        
        return base_score


class PlateValidator:
    """
    Validate and verify license plate numbers
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Regional validation rules
        self.regional_rules = {
            'US': {
                'length_range': (5, 8),
                'pattern': r'^[A-Z0-9]{5,8}$'
            },
            'EU': {
                'length_range': (6, 9),
                'pattern': r'^[A-Z]{1,3}[0-9]{2,4}[A-Z]{0,3}$'
            },
            'INDIA': {
                'length_range': (8, 10),
                'pattern': r'^[A-Z]{2}[0-9]{1,2}[A-Z]{1,2}[0-9]{4}$'
            }
        }
    
    def validate_plate(self, plate_number: str, region: str = None) -> Dict:
        """
        Validate plate number format and structure
        """
        # Clean plate number
        plate = plate_number.replace(' ', '').upper()
        
        # Basic checks
        if len(plate) < 4 or len(plate) > 12:
            return {
                'valid': False,
                'reason': 'Invalid length',
                'score': 0.0
            }
        
        # Check for valid characters
        if not re.match(r'^[A-Z0-9]+$', plate):
            return {
                'valid': False,
                'reason': 'Invalid characters',
                'score': 0.0
            }
        
        # Region-specific validation
        if region and region in self.regional_rules:
            rules = self.regional_rules[region]
            
            if not (rules['length_range'][0] <= len(plate) <= rules['length_range'][1]):
                return {
                    'valid': False,
                    'reason': f'Invalid length for {region}',
                    'score': 0.3
                }
            
            if not re.match(rules['pattern'], plate):
                return {
                    'valid': False,
                    'reason': f'Invalid format for {region}',
                    'score': 0.5
                }
        
        # If all checks pass
        return {
            'valid': True,
            'reason': 'Valid format',
            'score': 1.0,
            'plate': plate
        }
    
    def check_duplicate_probability(self, plate_number: str) -> float:
        """
        Estimate probability that plate might be a duplicate/fake
        Based on suspicious patterns
        """
        plate = plate_number.replace(' ', '').upper()
        
        suspicion_score = 0.0
        
        # Check for sequential characters (suspicious)
        sequential = sum(1 for i in range(len(plate)-1) 
                        if ord(plate[i+1]) == ord(plate[i]) + 1)
        if sequential >= 3:
            suspicion_score += 0.3
        
        # Check for repeated characters (suspicious)
        from collections import Counter
        char_counts = Counter(plate)
        max_repeat = max(char_counts.values())
        if max_repeat >= 3:
            suspicion_score += 0.2
        
        # Check for common fake patterns
        fake_patterns = ['0000', '1111', '9999', 'AAAA', 'TEST']
        for pattern in fake_patterns:
            if pattern in plate:
                suspicion_score += 0.5
        
        return min(suspicion_score, 1.0)