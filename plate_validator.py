"""
License Plate Validator & Corrector
Specialized for Indian license plate format validation and auto-correction

Indian License Plate Format:
- Structure: AA ## AA #### or AA ## A ####
- State code: 2 letters
- RTO code: 2 digits
- Series: 1-2 letters
- Number: 4 digits
- Example: KA 01 AB 1234, MH 12 C 5678

Features:
- Format validation
- Position-aware character correction
- State code verification
- Structural enforcement
"""

import re
from typing import Tuple, Optional, Dict
from difflib import SequenceMatcher


class IndianLicensePlateValidator:
    """
    Validator for Indian license plates with auto-correction
    """
    
    # Valid Indian state codes (first 2 letters)
    VALID_STATE_CODES = [
        'AP', 'AR', 'AS', 'BR', 'CG', 'GA', 'GJ', 'HR', 'HP', 'JK', 'JH',
        'KA', 'KL', 'MP', 'MH', 'MN', 'ML', 'MZ', 'NL', 'OD', 'PB', 'RJ',
        'SK', 'TN', 'TR', 'TS', 'UK', 'UP', 'WB', 'AN', 'CH', 'DN', 'DD',
        'DL', 'LD', 'PY'
    ]
    
    # Common OCR mistakes for state codes
    STATE_CODE_CORRECTIONS = {
        'KH': 'KA',  # Karnataka
        'MN': 'MH',  # Maharashtra (if followed by valid RTO)
        'DI': 'DL',  # Delhi
        'PY': 'PB',  # Sometimes confused
        'OO': 'OD',  # Odisha
        'KG': 'KA',
        'TH': 'TN',
    }
    
    # Pattern definitions
    # Format: AA DD AA DDDD or AA DD A DDDD
    PATTERN_10_CHAR = r'^[A-Z]{2}\d{2}[A-Z]{2}\d{4}$'  # KA01AB1234
    PATTERN_9_CHAR = r'^[A-Z]{2}\d{2}[A-Z]\d{4}$'      # KA01A1234
    
    def __init__(self):
        """Initialize validator"""
        self.correction_stats = {
            'total_processed': 0,
            'format_corrected': 0,
            'state_corrected': 0,
            'char_corrected': 0
        }
    
    def validate(self, plate_text: str) -> Tuple[bool, str]:
        """
        Validate and auto-correct license plate
        
        Args:
            plate_text: Input plate text (may be incorrect)
            
        Returns:
            (is_valid, corrected_text)
        """
        self.correction_stats['total_processed'] += 1
        
        # Clean input
        cleaned = self._clean_text(plate_text)
        
        if not cleaned:
            return False, plate_text
        
        # Try to correct format
        corrected = self._correct_format(cleaned)
        
        # Validate structure
        is_valid = self._is_valid_format(corrected)
        
        return is_valid, corrected
    
    def _clean_text(self, text: str) -> str:
        """
        Clean plate text
        - Remove spaces
        - Convert to uppercase
        - Remove special characters
        """
        if not text:
            return ""
        
        # Convert to uppercase
        text = text.upper().strip()
        
        # Remove spaces and special characters
        text = ''.join(c for c in text if c.isalnum())
        
        return text
    
    def _is_valid_format(self, text: str) -> bool:
        """
        Check if text matches valid Indian plate format
        
        Returns:
            True if valid format
        """
        if not text:
            return False
        
        # Check length (9 or 10 characters)
        if len(text) not in [9, 10]:
            return False
        
        # Check pattern
        if len(text) == 10:
            return bool(re.match(self.PATTERN_10_CHAR, text))
        else:  # 9 characters
            return bool(re.match(self.PATTERN_9_CHAR, text))
    
    def _correct_format(self, text: str) -> str:
        """
        Apply format correction rules
        
        Steps:
        1. Normalize length (9 or 10)
        2. Correct state code
        3. Enforce position-based character types
        4. Validate and fix structure
        """
        if not text:
            return text
        
        # Step 1: Normalize length
        if len(text) < 9:
            # Too short, pad with 0s at the end
            text = text + '0' * (9 - len(text))
        elif len(text) > 10:
            # Too long, truncate
            text = text[:10]
        
        # Step 2: Correct state code (first 2 chars)
        if len(text) >= 2:
            state_code = text[:2]
            
            # Auto-correct known mistakes
            if state_code in self.STATE_CODE_CORRECTIONS:
                text = self.STATE_CODE_CORRECTIONS[state_code] + text[2:]
                self.correction_stats['state_corrected'] += 1
            
            # If still invalid, find closest match
            if state_code not in self.VALID_STATE_CODES:
                closest = self._find_closest_state_code(state_code)
                if closest:
                    text = closest + text[2:]
                    self.correction_stats['state_corrected'] += 1
        
        # Step 3: Position-based character correction
        text = self._enforce_positions(text)
        
        return text
    
    def _enforce_positions(self, text: str) -> str:
        """
        Enforce character types at specific positions
        
        Position rules:
        - [0:2]   : Letters (state code)
        - [2:4]   : Digits (RTO code)
        - [4:5/6] : Letters (series)
        - [6:10]  : Digits (number)
        """
        if len(text) < 9:
            return text
        
        result = []
        
        # Define expected pattern
        if len(text) == 10:
            # AA DD AA DDDD
            pattern = 'LLDDLLDDDD'
        else:  # 9
            # AA DD A DDDD
            pattern = 'LLDDLDDDD'
        
        for i, (char, expected) in enumerate(zip(text, pattern)):
            if expected == 'L':
                # Should be letter
                if char.isdigit():
                    # Convert digit to letter
                    corrected = self._digit_to_letter(char)
                    result.append(corrected)
                    self.correction_stats['char_corrected'] += 1
                else:
                    result.append(char)
            else:  # 'D'
                # Should be digit
                if char.isalpha():
                    # Convert letter to digit
                    corrected = self._letter_to_digit(char)
                    result.append(corrected)
                    self.correction_stats['char_corrected'] += 1
                else:
                    result.append(char)
        
        self.correction_stats['format_corrected'] += 1
        return ''.join(result)
    
    def _letter_to_digit(self, char: str) -> str:
        """Convert commonly confused letters to digits"""
        mapping = {
            'O': '0', 'I': '1', 'L': '1', 'Z': '2', 'E': '3',
            'A': '4', 'S': '5', 'G': '6', 'T': '7', 'B': '8'
        }
        return mapping.get(char.upper(), '0')
    
    def _digit_to_letter(self, char: str) -> str:
        """Convert commonly confused digits to letters"""
        mapping = {
            '0': 'O', '1': 'I', '2': 'Z', '3': 'E',
            '4': 'A', '5': 'S', '6': 'G', '7': 'T', '8': 'B'
        }
        return mapping.get(char, 'O')
    
    def _find_closest_state_code(self, invalid_code: str) -> Optional[str]:
        """
        Find closest valid state code using string similarity
        
        Args:
            invalid_code: Invalid 2-letter code
            
        Returns:
            Closest valid state code, or None
        """
        if len(invalid_code) != 2:
            return None
        
        # Find most similar state code
        best_match = None
        best_ratio = 0.0
        
        for valid_code in self.VALID_STATE_CODES:
            ratio = SequenceMatcher(None, invalid_code, valid_code).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = valid_code
        
        # Only return if similarity is high enough
        if best_ratio >= 0.5:
            return best_match
        
        return None
    
    def format_display(self, plate_text: str) -> str:
        """
        Format plate for display with spaces
        
        Args:
            plate_text: Cleaned plate text (e.g., "KA01AB1234")
            
        Returns:
            Formatted text (e.g., "KA 01 AB 1234")
        """
        if not plate_text:
            return ""
        
        # Clean first
        cleaned = self._clean_text(plate_text)
        
        if len(cleaned) == 10:
            # AA DD AA DDDD -> AA DD AA DDDD
            return f"{cleaned[0:2]} {cleaned[2:4]} {cleaned[4:6]} {cleaned[6:10]}"
        elif len(cleaned) == 9:
            # AA DD A DDDD -> AA DD A DDDD
            return f"{cleaned[0:2]} {cleaned[2:4]} {cleaned[4:5]} {cleaned[5:9]}"
        
        return cleaned
    
    def extract_components(self, plate_text: str) -> Dict[str, str]:
        """
        Extract individual components from plate
        
        Returns:
            Dictionary with:
            - state_code: 2 letters
            - rto_code: 2 digits
            - series: 1-2 letters
            - number: 4 digits
        """
        cleaned = self._clean_text(plate_text)
        
        if len(cleaned) == 10:
            return {
                'state_code': cleaned[0:2],
                'rto_code': cleaned[2:4],
                'series': cleaned[4:6],
                'number': cleaned[6:10]
            }
        elif len(cleaned) == 9:
            return {
                'state_code': cleaned[0:2],
                'rto_code': cleaned[2:4],
                'series': cleaned[4:5],
                'number': cleaned[5:9]
            }
        
        return {}
    
    def get_stats(self) -> Dict[str, int]:
        """Get correction statistics"""
        return self.correction_stats.copy()


class PlateComparator:
    """
    Compare license plates for fuzzy matching
    Useful for stolen vehicle detection with OCR errors
    """
    
    @staticmethod
    def similarity(plate1: str, plate2: str) -> float:
        """
        Calculate similarity between two plates (0.0 to 1.0)
        
        Args:
            plate1, plate2: Plate texts to compare
            
        Returns:
            Similarity ratio (1.0 = identical)
        """
        # Clean both plates
        clean1 = ''.join(c for c in plate1.upper() if c.isalnum())
        clean2 = ''.join(c for c in plate2.upper() if c.isalnum())
        
        if not clean1 or not clean2:
            return 0.0
        
        return SequenceMatcher(None, clean1, clean2).ratio()
    
    @staticmethod
    def is_match(plate1: str, plate2: str, threshold: float = 0.85) -> bool:
        """
        Check if two plates match within threshold
        
        Args:
            plate1, plate2: Plates to compare
            threshold: Minimum similarity (default 0.85 = 85%)
            
        Returns:
            True if match
        """
        return PlateComparator.similarity(plate1, plate2) >= threshold
    
    @staticmethod
    def character_difference_count(plate1: str, plate2: str) -> int:
        """
        Count number of different characters
        
        Returns:
            Number of positions where characters differ
        """
        clean1 = ''.join(c for c in plate1.upper() if c.isalnum())
        clean2 = ''.join(c for c in plate2.upper() if c.isalnum())
        
        if len(clean1) != len(clean2):
            return max(len(clean1), len(clean2))
        
        differences = sum(1 for c1, c2 in zip(clean1, clean2) if c1 != c2)
        return differences


# Convenience functions
def validate_indian_plate(plate_text: str) -> Tuple[bool, str]:
    """
    Quick validation function
    
    Returns:
        (is_valid, corrected_text)
    """
    validator = IndianLicensePlateValidator()
    return validator.validate(plate_text)


def format_plate(plate_text: str) -> str:
    """
    Format plate for display
    
    Returns:
        Formatted plate (e.g., "KA 01 AB 1234")
    """
    validator = IndianLicensePlateValidator()
    return validator.format_display(plate_text)


if __name__ == "__main__":
    print("License Plate Validator Module")
    print("=" * 50)
    
    # Test cases
    test_plates = [
        "KA01AB1234",      # Valid
        "KH01AB1234",      # Invalid state (KH -> KA)
        "KA0IAB1234",      # 0 instead of O
        "KA01A81234",      # B instead of 8
        "MH12C5678",       # Valid 9-char
        "DL1CAB1234",      # Missing digit
    ]
    
    validator = IndianLicensePlateValidator()
    
    print("\nTest Results:")
    for plate in test_plates:
        is_valid, corrected = validator.validate(plate)
        formatted = validator.format_display(corrected)
        status = "✓" if is_valid else "✗"
        print(f"{status} {plate:15} -> {corrected:12} [{formatted}]")
    
    print("\nStatistics:")
    stats = validator.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")