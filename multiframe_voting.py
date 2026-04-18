"""
🎯 Multi-Frame Voting Module
Dramatically improves accuracy by combining OCR results from multiple video frames

Usage:
    from multiframe_voting import MultiFrameVoter
    
    voter = MultiFrameVoter(max_frames=10)
    
    # In video loop:
    for frame in video:
        plate_text, confidence = do_ocr(frame)
        voter.add_reading(plate_id, plate_text, confidence)
    
    # Get final result:
    final_text = voter.get_consensus(plate_id)
"""

from collections import Counter, defaultdict
import time


class MultiFrameVoter:
    """
    Tracks OCR readings across multiple frames and returns consensus
    """
    
    def __init__(self, max_frames=10, confidence_threshold=0.5, time_window=5.0):
        """
        Initialize multi-frame voter
        
        Args:
            max_frames: Maximum number of frames to consider per plate
            confidence_threshold: Minimum confidence to consider a reading
            time_window: Time window in seconds to keep readings
        """
        self.max_frames = max_frames
        self.confidence_threshold = confidence_threshold
        self.time_window = time_window
        
        # Storage: {plate_id: [(text, confidence, timestamp), ...]}
        self.readings = defaultdict(list)
        
        # Track last cleanup time
        self.last_cleanup = time.time()
    
    def add_reading(self, plate_id, text, confidence):
        """
        Add OCR reading for a plate
        
        Args:
            plate_id: Unique identifier for this plate (e.g., track_id)
            text: OCR text reading
            confidence: Confidence score (0.0 to 1.0)
        
        Returns:
            bool: True if reading was added
        """
        # Filter low confidence readings
        if confidence < self.confidence_threshold:
            return False
        
        # Clean text
        text = self._clean_text(text)
        if not text or len(text) < 4:  # Minimum plate length
            return False
        
        # Add reading with timestamp
        timestamp = time.time()
        self.readings[plate_id].append((text, confidence, timestamp))
        
        # Keep only recent frames
        if len(self.readings[plate_id]) > self.max_frames:
            self.readings[plate_id] = self.readings[plate_id][-self.max_frames:]
        
        # Periodic cleanup
        self._periodic_cleanup()
        
        return True
    
    def get_consensus(self, plate_id, min_readings=3):
        """
        Get consensus plate number using voting
        
        Args:
            plate_id: Plate identifier
            min_readings: Minimum readings required for consensus
        
        Returns:
            tuple: (consensus_text, confidence, reading_count) or (None, 0.0, 0)
        """
        if plate_id not in self.readings:
            return None, 0.0, 0
        
        readings = self.readings[plate_id]
        
        # Need minimum readings
        if len(readings) < min_readings:
            return None, 0.0, len(readings)
        
        # Extract texts and confidences
        texts = [r[0] for r in readings]
        confidences = [r[1] for r in readings]
        
        # Method 1: Simple majority vote
        counter = Counter(texts)
        most_common_text, votes = counter.most_common(1)[0]
        
        # Calculate average confidence for the winning text
        winning_confidences = [
            conf for txt, conf, _ in readings if txt == most_common_text
        ]
        avg_confidence = sum(winning_confidences) / len(winning_confidences)
        
        # Confidence boost based on agreement
        agreement_ratio = votes / len(texts)
        final_confidence = avg_confidence * (0.7 + 0.3 * agreement_ratio)
        
        return most_common_text, final_confidence, len(readings)
    
    def get_best_reading(self, plate_id):
        """
        Get single best reading (highest confidence)
        
        Args:
            plate_id: Plate identifier
        
        Returns:
            tuple: (text, confidence) or (None, 0.0)
        """
        if plate_id not in self.readings or not self.readings[plate_id]:
            return None, 0.0
        
        # Sort by confidence
        sorted_readings = sorted(
            self.readings[plate_id], 
            key=lambda x: x[1], 
            reverse=True
        )
        
        best_text, best_conf, _ = sorted_readings[0]
        return best_text, best_conf
    
    def _clean_text(self, text):
        """
        Clean OCR text (remove spaces, special chars)
        
        Args:
            text: Raw OCR text
        
        Returns:
            Cleaned text (uppercase, no spaces)
        """
        # Remove spaces and special characters
        text = ''.join(c for c in text if c.isalnum())
        # Convert to uppercase
        text = text.upper()
        return text
    
    def _periodic_cleanup(self):
        """Remove old readings based on time window"""
        current_time = time.time()
        
        # Cleanup every 10 seconds
        if current_time - self.last_cleanup < 10:
            return
        
        self.last_cleanup = current_time
        
        # Remove old readings
        for plate_id in list(self.readings.keys()):
            # Filter by time window
            self.readings[plate_id] = [
                (text, conf, ts) for text, conf, ts in self.readings[plate_id]
                if current_time - ts <= self.time_window
            ]
            
            # Remove empty entries
            if not self.readings[plate_id]:
                del self.readings[plate_id]
    
    def clear_plate(self, plate_id):
        """
        Clear readings for a specific plate
        
        Args:
            plate_id: Plate identifier
        """
        if plate_id in self.readings:
            del self.readings[plate_id]
    
    def get_statistics(self, plate_id):
        """
        Get statistics for a plate's readings
        
        Args:
            plate_id: Plate identifier
        
        Returns:
            dict: Statistics including reading count, unique texts, etc.
        """
        if plate_id not in self.readings:
            return {
                'reading_count': 0,
                'unique_texts': 0,
                'avg_confidence': 0.0,
                'texts': []
            }
        
        readings = self.readings[plate_id]
        texts = [r[0] for r in readings]
        confidences = [r[1] for r in readings]
        
        return {
            'reading_count': len(readings),
            'unique_texts': len(set(texts)),
            'avg_confidence': sum(confidences) / len(confidences) if confidences else 0.0,
            'texts': Counter(texts).most_common()
        }


class ConfidenceFilter:
    """
    Helper class to filter and validate OCR results
    """
    
    @staticmethod
    def is_valid_indian_plate(text):
        """
        Basic validation for Indian license plate format
        
        Args:
            text: Plate text
        
        Returns:
            bool: True if format seems valid
        """
        # Clean text
        text = ''.join(c for c in text if c.isalnum()).upper()
        
        # Minimum length
        if len(text) < 8:
            return False
        
        # Should contain both letters and numbers
        has_letters = any(c.isalpha() for c in text)
        has_numbers = any(c.isdigit() for c in text)
        
        return has_letters and has_numbers
    
    @staticmethod
    def calculate_similarity(text1, text2):
        """
        Calculate similarity between two plate texts
        
        Args:
            text1: First plate text
            text2: Second plate text
        
        Returns:
            float: Similarity score (0.0 to 1.0)
        """
        from difflib import SequenceMatcher
        
        # Clean texts
        text1 = ''.join(c for c in text1 if c.isalnum()).upper()
        text2 = ''.join(c for c in text2 if c.isalnum()).upper()
        
        return SequenceMatcher(None, text1, text2).ratio()


# 🧪 TESTING FUNCTIONS
def test_voting():
    """Test the voting mechanism"""
    print("🧪 Testing Multi-Frame Voting")
    print("=" * 50)
    
    voter = MultiFrameVoter(max_frames=10, confidence_threshold=0.3)
    
    # Simulate OCR readings for a plate
    plate_id = 1
    
    # Add some readings (simulating video frames)
    test_readings = [
        ("KA01AB1234", 0.85),
        ("KA01AB1234", 0.90),
        ("KA01AB1234", 0.88),
        ("KA01AB1Z34", 0.75),  # Misread
        ("KA01AB1234", 0.92),
        ("KA01AB1234", 0.87),
        ("KA01AB1234", 0.89),
        ("KA01AB12B4", 0.70),  # Misread
        ("KA01AB1234", 0.91),
        ("KA01AB1234", 0.86),
    ]
    
    print("\n📊 Adding readings:")
    for text, conf in test_readings:
        voter.add_reading(plate_id, text, conf)
        print(f"  Added: {text} (confidence: {conf:.2f})")
    
    # Get consensus
    print("\n🎯 Getting consensus...")
    consensus, confidence, count = voter.get_consensus(plate_id)
    
    print(f"\n✅ RESULT:")
    print(f"  Consensus: {consensus}")
    print(f"  Confidence: {confidence:.2f}")
    print(f"  Based on: {count} readings")
    
    # Get statistics
    stats = voter.get_statistics(plate_id)
    print(f"\n📈 Statistics:")
    print(f"  Total readings: {stats['reading_count']}")
    print(f"  Unique texts: {stats['unique_texts']}")
    print(f"  Avg confidence: {stats['avg_confidence']:.2f}")
    print(f"  Text distribution:")
    for text, votes in stats['texts']:
        print(f"    {text}: {votes} votes")
    
    print("\n" + "=" * 50)


if __name__ == "__main__":
    test_voting()