"""
Enhanced License Plate Recognition System - Main Integration
This file enhances the existing a1v5.py with all advanced capabilities
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging

# Import enhancement modules
from image_enhancement import ImageEnhancer, PlateRegionEnhancer
from advanced_ocr import AdvancedPlateOCR, PlateValidator
from advanced_detection import MultiScaleDetector, AdvancedTracker, FalsePositiveFilter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class EnhancedLPRProcessor:
    """
    Enhanced License Plate Recognition Processor
    Integrates all advanced features into a single processing pipeline
    """
    
    def __init__(self, model_path: str = 'license_plate_detector.pt'):
        self.logger = logging.getLogger(__name__)
        
        # Initialize all components
        self.logger.info("Initializing Enhanced LPR Processor...")
        
        # Enhancement modules
        self.frame_enhancer = ImageEnhancer()
        self.plate_enhancer = PlateRegionEnhancer()
        
        # Detection modules
        self.detector = MultiScaleDetector(model_path)
        self.tracker = AdvancedTracker()
        self.fp_filter = FalsePositiveFilter()
        
        # OCR modules
        self.ocr_engine = AdvancedPlateOCR()
        self.validator = PlateValidator()
        
        # Processing statistics
        self.stats = {
            'frames_processed': 0,
            'plates_detected': 0,
            'plates_recognized': 0,
            'enhancement_applied': 0,
            'false_positives_filtered': 0
        }
        
        # Quality settings
        self.settings = {
            'auto_enhance': True,
            'weather_detection': True,
            'multi_scale_detection': True,
            'advanced_ocr': True,
            'false_positive_filter': True,
            'min_ocr_confidence': 0.6
        }
        
        self.logger.info("✅ Enhanced LPR Processor initialized successfully")
    
    def process_frame(self, frame: np.ndarray, frame_number: int = 0) -> Dict:
        """
        Process a single frame with all enhancements
        
        Args:
            frame: Input frame
            frame_number: Frame number for tracking
        
        Returns:
            Dictionary with processing results
        """
        self.stats['frames_processed'] += 1
        
        results = {
            'frame_number': frame_number,
            'detections': [],
            'recognized_plates': [],
            'processing_info': {}
        }
        
        try:
            # Step 1: Frame Enhancement
            if self.settings['auto_enhance']:
                # Analyze and enhance frame
                enhanced_frame = self.frame_enhancer.enhance_frame(frame, 'moderate')
                
                # Handle weather conditions
                if self.settings['weather_detection']:
                    enhanced_frame = self.frame_enhancer.handle_weather_conditions(
                        enhanced_frame, 'auto'
                    )
                
                self.stats['enhancement_applied'] += 1
                results['processing_info']['enhanced'] = True
            else:
                enhanced_frame = frame
                results['processing_info']['enhanced'] = False
            
            # Step 2: License Plate Detection
            if self.settings['multi_scale_detection']:
                detections = self.detector.detect_multi_scale(enhanced_frame)
            else:
                # Fallback to basic detection (would need basic detector)
                detections = []
            
            self.stats['plates_detected'] += len(detections)
            results['processing_info']['raw_detections'] = len(detections)
            
            # Step 3: False Positive Filtering
            if self.settings['false_positive_filter'] and detections:
                frame_shape = enhanced_frame.shape[:2]
                filtered_detections = self.fp_filter.filter_detections(detections, frame_shape)
                
                filtered_count = len(detections) - len(filtered_detections)
                self.stats['false_positives_filtered'] += filtered_count
                
                detections = filtered_detections
                results['processing_info']['filtered_out'] = filtered_count
            
            # Step 4: Tracking
            tracked_objects = self.tracker.update(detections)
            results['processing_info']['tracked_objects'] = len(tracked_objects)
            
            # Step 5: OCR on detected plates
            for track_id, track_data in tracked_objects.items():
                bbox = track_data['bbox']
                x1, y1, x2, y2 = [int(coord) for coord in bbox]
                
                # Extract plate region
                plate_roi = enhanced_frame[y1:y2, x1:x2]
                
                if plate_roi.size == 0:
                    continue
                
                # Enhance plate region
                enhanced_plates = self.plate_enhancer.enhance_plate_region(plate_roi)
                
                # Correct perspective if needed
                for variant_name, plate_img in enhanced_plates.items():
                    corrected = self.plate_enhancer.correct_perspective(plate_img)
                    enhanced_plates[variant_name] = corrected
                
                # OCR recognition
                if self.settings['advanced_ocr']:
                    ocr_result = self.ocr_engine.recognize_plate(
                        enhanced_plates,
                        confidence_threshold=self.settings['min_ocr_confidence']
                    )
                    
                    if ocr_result['success']:
                        plate_number = ocr_result['plate_number']
                        confidence = ocr_result['confidence']
                        
                        # Validate plate
                        validation = self.validator.validate_plate(plate_number)
                        
                        if validation['valid']:
                            # Check for duplicate probability
                            duplicate_prob = self.validator.check_duplicate_probability(plate_number)
                            
                            recognized_plate = {
                                'track_id': track_id,
                                'plate_number': plate_number,
                                'confidence': confidence,
                                'bbox': bbox,
                                'validation_score': validation['score'],
                                'duplicate_probability': duplicate_prob,
                                'ocr_engine': ocr_result['engine'],
                                'frame_number': frame_number
                            }
                            
                            results['recognized_plates'].append(recognized_plate)
                            self.stats['plates_recognized'] += 1
                            
                            # Update track with plate number
                            track_data['plate_number'] = plate_number
                            track_data['plate_confidence'] = confidence
            
            # Add detection info to results
            results['detections'] = [
                {
                    'track_id': tid,
                    'bbox': track_data['bbox'],
                    'confidence': track_data['confidence'],
                    'plate_number': track_data.get('plate_number', ''),
                    'plate_confidence': track_data.get('plate_confidence', 0.0)
                }
                for tid, track_data in tracked_objects.items()
            ]
            
            results['success'] = True
            
        except Exception as e:
            self.logger.error(f"Frame processing error: {e}")
            results['success'] = False
            results['error'] = str(e)
        
        return results
    
    def process_video(self, video_path: str, output_path: str = None, 
                     callback=None) -> Dict:
        """
        Process entire video with enhancements
        
        Args:
            video_path: Path to input video
            output_path: Path to save annotated video (optional)
            callback: Callback function for progress updates
        
        Returns:
            Dictionary with overall processing results
        """
        self.logger.info(f"Processing video: {video_path}")
        
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            self.logger.error(f"Cannot open video: {video_path}")
            return {'success': False, 'error': 'Cannot open video'}
        
        # Video properties
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        self.logger.info(f"Video: {width}x{height}, {fps} FPS, {total_frames} frames")
        
        # Video writer (if output requested)
        writer = None
        if output_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        # Process frames
        all_results = []
        frame_number = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Process frame
            frame_results = self.process_frame(frame, frame_number)
            all_results.append(frame_results)
            
            # Annotate frame
            annotated_frame = self._annotate_frame(frame, frame_results)
            
            # Write to output
            if writer:
                writer.write(annotated_frame)
            
            # Callback for progress
            if callback:
                progress = (frame_number + 1) / total_frames * 100
                callback(frame_number, total_frames, progress, frame_results)
            
            frame_number += 1
            
            # Log progress
            if frame_number % 100 == 0:
                self.logger.info(f"Processed {frame_number}/{total_frames} frames")
        
        # Cleanup
        cap.release()
        if writer:
            writer.release()
        
        # Compile results
        summary = self._compile_video_results(all_results)
        
        self.logger.info("✅ Video processing complete")
        self.logger.info(f"Statistics: {self.stats}")
        
        return summary
    
    def _annotate_frame(self, frame: np.ndarray, results: Dict) -> np.ndarray:
        """
        Annotate frame with detection and recognition results
        """
        annotated = frame.copy()
        
        for detection in results.get('detections', []):
            bbox = detection['bbox']
            x1, y1, x2, y2 = [int(coord) for coord in bbox]
            
            # Draw bounding box
            color = (0, 255, 0) if detection.get('plate_number') else (0, 165, 255)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            
            # Draw plate number if recognized
            if detection.get('plate_number'):
                plate_text = detection['plate_number']
                conf = detection.get('plate_confidence', 0.0)
                
                label = f"{plate_text} ({conf:.2f})"
                
                # Background for text
                (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(annotated, (x1, y1 - text_h - 10), (x1 + text_w, y1), color, -1)
                
                # Text
                cv2.putText(annotated, label, (x1, y1 - 5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Draw track ID
            track_id = detection.get('track_id', '')
            cv2.putText(annotated, f"ID:{track_id}", (x1, y2 + 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        # Add frame info
        info_text = f"Frame: {results.get('frame_number', 0)} | Detections: {len(results.get('detections', []))}"
        cv2.putText(annotated, info_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        return annotated
    
    def _compile_video_results(self, all_results: List[Dict]) -> Dict:
        """
        Compile results from all frames
        """
        # Aggregate all recognized plates
        all_plates = {}
        
        for frame_results in all_results:
            for plate_info in frame_results.get('recognized_plates', []):
                plate_number = plate_info['plate_number']
                
                if plate_number not in all_plates:
                    all_plates[plate_number] = {
                        'plate_number': plate_number,
                        'first_seen_frame': frame_results['frame_number'],
                        'last_seen_frame': frame_results['frame_number'],
                        'detections': [],
                        'max_confidence': plate_info['confidence']
                    }
                
                all_plates[plate_number]['last_seen_frame'] = frame_results['frame_number']
                all_plates[plate_number]['detections'].append(plate_info)
                all_plates[plate_number]['max_confidence'] = max(
                    all_plates[plate_number]['max_confidence'],
                    plate_info['confidence']
                )
        
        return {
            'success': True,
            'total_frames': len(all_results),
            'unique_plates': len(all_plates),
            'plates': list(all_plates.values()),
            'statistics': self.stats.copy()
        }
    
    def get_statistics(self) -> Dict:
        """Get processing statistics"""
        return self.stats.copy()
    
    def reset_statistics(self):
        """Reset processing statistics"""
        self.stats = {
            'frames_processed': 0,
            'plates_detected': 0,
            'plates_recognized': 0,
            'enhancement_applied': 0,
            'false_positives_filtered': 0
        }
    
    def update_settings(self, settings: Dict):
        """Update processing settings"""
        self.settings.update(settings)
        self.logger.info(f"Settings updated: {settings}")


# Utility functions for integration with existing system

def create_enhanced_processor(model_path: str = 'license_plate_detector.pt') -> EnhancedLPRProcessor:
    """
    Create an enhanced processor instance
    """
    return EnhancedLPRProcessor(model_path)


def process_single_frame_enhanced(frame: np.ndarray, processor: EnhancedLPRProcessor = None) -> Dict:
    """
    Process a single frame with enhancements
    Convenience function for quick processing
    """
    if processor is None:
        processor = create_enhanced_processor()
    
    return processor.process_frame(frame)


def compare_with_stolen_vehicles(recognized_plate: str, stolen_vehicles: List[str], 
                                 fuzzy_match: bool = True) -> Dict:
    """
    Compare recognized plate with stolen vehicle database
    
    Args:
        recognized_plate: The recognized plate number
        stolen_vehicles: List of stolen vehicle plate numbers
        fuzzy_match: Whether to use fuzzy matching
    
    Returns:
        Match result dictionary
    """
    from advanced_ocr import AdvancedPlateOCR
    
    recognized_clean = recognized_plate.replace(' ', '').upper()
    
    best_match = None
    best_score = 0.0
    
    for stolen_plate in stolen_vehicles:
        stolen_clean = stolen_plate.replace(' ', '').upper()
        
        if recognized_clean == stolen_clean:
            return {
                'match': True,
                'stolen_plate': stolen_plate,
                'similarity': 1.0,
                'match_type': 'exact'
            }
        
        if fuzzy_match:
            ocr = AdvancedPlateOCR()
            similarity = ocr.fuzzy_match_plates(recognized_plate, stolen_plate)
            
            if similarity > best_score:
                best_score = similarity
                best_match = stolen_plate
    
    # Threshold for fuzzy match
    if best_score >= 0.85:
        return {
            'match': True,
            'stolen_plate': best_match,
            'similarity': best_score,
            'match_type': 'fuzzy'
        }
    
    return {
        'match': False,
        'stolen_plate': None,
        'similarity': best_score,
        'match_type': 'none'
    }


if __name__ == "__main__":
    # Test the enhanced processor
    print("Enhanced License Plate Recognition System")
    print("=" * 60)
    
    # Create processor
    processor = create_enhanced_processor()
    
    print("\n✅ Processor initialized with following capabilities:")
    print("   • Advanced frame enhancement (motion blur, low light, weather)")
    print("   • Multi-scale detection (small plates at distance)")
    print("   • False positive filtering")
    print("   • Advanced tracking with occlusion handling")
    print("   • Multi-strategy OCR (EasyOCR + Tesseract)")
    print("   • Plate validation and verification")
    print("   • Fuzzy matching for stolen vehicle detection")
    
    print("\n📊 Current Statistics:")
    print(processor.get_statistics())