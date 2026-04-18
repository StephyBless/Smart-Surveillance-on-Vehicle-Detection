"""
Criminal Intelligence Module for Enhanced License Plate Recognition System
Handles license plate cloning detection, fake plate detection, and vehicle mismatch analysis
"""

import re
import json
import numpy as np
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, List, Tuple, Optional
import cv2


class VehicleRegistrationDatabase:
    """Simulated vehicle registration database"""
    
    def __init__(self):
        self.registrations = {}
        self.load_sample_data()
    
    def load_sample_data(self):
        """Load sample registration data"""
        # Sample registration data (in real implementation, this would be from actual database)
        sample_registrations = {
            'ABC123': {'type': 'car', 'color': 'red', 'make': 'Honda', 'model': 'Civic'},
            'NBISU': {'type': 'truck', 'color': 'blue', 'make': 'Ford', 'model': 'F-150'},
            'DEF456': {'type': 'motorcycle', 'color': 'black', 'make': 'Yamaha', 'model': 'R6'},
            'GHI789': {'type': 'bus', 'color': 'white', 'make': 'Mercedes', 'model': 'Sprinter'},
            'GXISOCJ': {'type': 'car', 'color': 'white', 'make': 'Toyota', 'model': 'Camry'},
            'MNO345': {'type': 'car', 'color': 'gray', 'make': 'BMW', 'model': 'X5'},
            'CISOGJ': {'type': 'truck', 'color': 'red', 'make': 'Chevrolet', 'model': 'Silverado'},
            'STU901': {'type': 'car', 'color': 'blue', 'make': 'Nissan', 'model': 'Altima'},
        }
        self.registrations = sample_registrations
    
    def get_vehicle_info(self, plate_number: str) -> Optional[Dict]:
        """Get registered vehicle information for a license plate"""
        clean_plate = ''.join(filter(str.isalnum, plate_number.upper()))
        return self.registrations.get(clean_plate)
    
    def add_registration(self, plate_number: str, vehicle_info: Dict):
        """Add new vehicle registration"""
        clean_plate = ''.join(filter(str.isalnum, plate_number.upper()))
        self.registrations[clean_plate] = vehicle_info


class LicensePlateAnalyzer:
    """Analyzes license plates for authenticity and potential modifications"""
    
    def __init__(self):
        # Common license plate patterns for different regions
        self.plate_patterns = {
            'standard': r'^[A-Z]{3}[0-9]{3}$',  # ABC123
            'new_format': r'^[A-Z]{2}[0-9]{4}$',  # AB1234
            'commercial': r'^[0-9]{3}[A-Z]{3}$',  # 123ABC
        }
        
        # Characters commonly confused or substituted
        self.confusable_chars = {
            '0': ['O', 'Q'],
            'O': ['0', 'Q'],
            'I': ['1', 'L'],
            '1': ['I', 'L'],
            'S': ['5'],
            '5': ['S'],
            'Z': ['2'],
            '2': ['Z']
        }
    
    def analyze_plate_authenticity(self, plate_text: str, confidence_score: float) -> Dict:
        """Analyze license plate for potential modifications or fakes"""
        results = {
            'is_suspicious': False,
            'suspicion_reasons': [],
            'confidence_level': 'normal',
            'pattern_match': True,
            'character_analysis': {}
        }
        
        # Check confidence score
        if confidence_score < 0.6:
            results['is_suspicious'] = True
            results['suspicion_reasons'].append(f'Low OCR confidence: {confidence_score:.2f}')
            results['confidence_level'] = 'low'
        
        # Check format pattern
        plate_clean = ''.join(filter(str.isalnum, plate_text.upper()))
        pattern_match = any(re.match(pattern, plate_clean) for pattern in self.plate_patterns.values())
        
        if not pattern_match:
            results['is_suspicious'] = True
            results['suspicion_reasons'].append('Non-standard license plate format')
            results['pattern_match'] = False
        
        # Character analysis for potential substitutions
        char_analysis = self._analyze_characters(plate_clean)
        results['character_analysis'] = char_analysis
        
        if char_analysis['suspicious_chars']:
            results['is_suspicious'] = True
            results['suspicion_reasons'].append('Contains potentially substituted characters')
        
        return results
    
    def _analyze_characters(self, plate_text: str) -> Dict:
        """Analyze individual characters for potential substitutions"""
        analysis = {
            'suspicious_chars': [],
            'possible_substitutions': {},
            'mixed_fonts_detected': False
        }
        
        for i, char in enumerate(plate_text):
            if char in self.confusable_chars:
                analysis['possible_substitutions'][i] = {
                    'original': char,
                    'alternatives': self.confusable_chars[char]
                }
                
                # Simple heuristic: if confidence is low and char is confusable
                analysis['suspicious_chars'].append({
                    'position': i,
                    'character': char,
                    'reason': 'Commonly substituted character'
                })
        
        return analysis
    
    def generate_plate_variations(self, plate_text: str) -> List[str]:
        """Generate possible variations of a license plate considering common substitutions"""
        variations = [plate_text]
        plate_clean = ''.join(filter(str.isalnum, plate_text.upper()))
        
        for i, char in enumerate(plate_clean):
            if char in self.confusable_chars:
                for alt_char in self.confusable_chars[char]:
                    variation = plate_clean[:i] + alt_char + plate_clean[i+1:]
                    if variation not in variations:
                        variations.append(variation)
        
        return variations


class CloningDetector:
    """Detects potential license plate cloning by comparing vehicle characteristics"""
    
    def __init__(self):
        self.detection_history = {}
        self.cloning_threshold = 0.7  # Similarity threshold for cloning detection
    
    def check_for_cloning(self, plate_number: str, vehicle_data: Dict, detection_time: float) -> Dict:
        """Check if this plate/vehicle combination suggests cloning"""
        clean_plate = ''.join(filter(str.isalnum, plate_number.upper()))
        
        result = {
            'is_potential_clone': False,
            'confidence': 0.0,
            'conflicting_detections': [],
            'time_gap_analysis': {},
            'vehicle_mismatch_score': 0.0
        }
        
        if clean_plate in self.detection_history:
            # Compare with previous detections
            for prev_detection in self.detection_history[clean_plate]:
                mismatch_score = self._calculate_vehicle_mismatch(
                    vehicle_data, prev_detection['vehicle_data']
                )
                
                time_gap = abs(detection_time - prev_detection['timestamp'])
                
                # If vehicles are very different but detected close in time
                if mismatch_score > self.cloning_threshold and time_gap < 3600:  # 1 hour
                    result['is_potential_clone'] = True
                    result['confidence'] = mismatch_score
                    result['conflicting_detections'].append({
                        'previous_detection': prev_detection,
                        'mismatch_score': mismatch_score,
                        'time_gap_minutes': time_gap / 60
                    })
        
        # Store this detection
        if clean_plate not in self.detection_history:
            self.detection_history[clean_plate] = []
        
        self.detection_history[clean_plate].append({
            'vehicle_data': vehicle_data.copy(),
            'timestamp': detection_time
        })
        
        # Keep only recent detections (last 24 hours)
        current_time = detection_time
        self.detection_history[clean_plate] = [
            detection for detection in self.detection_history[clean_plate]
            if current_time - detection['timestamp'] < 86400  # 24 hours
        ]
        
        return result
    
    def _calculate_vehicle_mismatch(self, vehicle1: Dict, vehicle2: Dict) -> float:
        """Calculate how different two vehicles are (0 = identical, 1 = completely different)"""
        mismatch_score = 0.0
        comparisons = 0
        
        # Compare vehicle type
        if 'vehicle_type' in vehicle1 and 'vehicle_type' in vehicle2:
            if vehicle1['vehicle_type'] != vehicle2['vehicle_type']:
                mismatch_score += 0.5  # Type mismatch is very significant
            comparisons += 1
        
        # Compare vehicle color
        if 'vehicle_color' in vehicle1 and 'vehicle_color' in vehicle2:
            color_similarity = self._calculate_color_similarity(
                vehicle1['vehicle_color'], vehicle2['vehicle_color']
            )
            mismatch_score += (1 - color_similarity) * 0.3
            comparisons += 1
        
        # Compare bounding box size (rough vehicle size estimation)
        if 'car_bbox' in vehicle1 and 'car_bbox' in vehicle2:
            size_similarity = self._calculate_size_similarity(
                vehicle1['car_bbox'], vehicle2['car_bbox']
            )
            mismatch_score += (1 - size_similarity) * 0.2
            comparisons += 1
        
        return mismatch_score / max(comparisons, 1) if comparisons > 0 else 0.0
    
    def _calculate_color_similarity(self, color1: str, color2: str) -> float:
        """Calculate similarity between two colors"""
        if color1 == color2:
            return 1.0
        
        # Define color groups that might be confused
        similar_colors = {
            'white': ['gray', 'silver'],
            'gray': ['white', 'silver', 'black'],
            'silver': ['white', 'gray'],
            'blue': ['dark blue', 'navy'],
            'red': ['dark red', 'maroon']
        }
        
        if color1 in similar_colors and color2 in similar_colors[color1]:
            return 0.7  # Similar but not identical
        
        return 0.0  # Completely different colors
    
    def _calculate_size_similarity(self, bbox1, bbox2) -> float:
        """Calculate similarity between vehicle sizes based on bounding boxes"""
        try:
            # Parse bounding box coordinates
            if isinstance(bbox1, str):
                coords1 = [float(x) for x in bbox1.strip('[]').split()]
            else:
                coords1 = bbox1
                
            if isinstance(bbox2, str):
                coords2 = [float(x) for x in bbox2.strip('[]').split()]
            else:
                coords2 = bbox2
            
            # Calculate areas
            area1 = (coords1[2] - coords1[0]) * (coords1[3] - coords1[1])
            area2 = (coords2[2] - coords2[0]) * (coords2[3] - coords2[1])
            
            # Calculate similarity (1 = identical size, 0 = very different)
            if area1 == 0 or area2 == 0:
                return 0.0
            
            ratio = min(area1, area2) / max(area1, area2)
            return ratio
            
        except:
            return 0.5  # Default similarity if calculation fails


class VehicleMismatchAnalyzer:
    """Analyzes mismatches between detected vehicles and registration data"""
    
    def __init__(self, registration_db: VehicleRegistrationDatabase):
        self.registration_db = registration_db
        self.mismatch_threshold = 0.6
    
    def analyze_vehicle_match(self, plate_number: str, detected_vehicle: Dict) -> Dict:
        """Analyze if detected vehicle matches registration data"""
        result = {
            'has_mismatch': False,
            'mismatch_score': 0.0,
            'mismatch_details': {},
            'registered_vehicle': None,
            'recommendation': 'normal'
        }
        
        # Get registration data
        registered_vehicle = self.registration_db.get_vehicle_info(plate_number)
        result['registered_vehicle'] = registered_vehicle
        
        if not registered_vehicle:
            result['recommendation'] = 'verify_registration'
            result['mismatch_details']['registration'] = 'No registration found'
            return result
        
        # Compare vehicle characteristics
        mismatches = []
        total_score = 0.0
        
        # Check vehicle type
        if 'vehicle_type' in detected_vehicle and 'type' in registered_vehicle:
            if detected_vehicle['vehicle_type'] != registered_vehicle['type']:
                mismatches.append({
                    'attribute': 'vehicle_type',
                    'detected': detected_vehicle['vehicle_type'],
                    'registered': registered_vehicle['type'],
                    'severity': 'high'
                })
                total_score += 0.6
        
        # Check vehicle color
        if 'vehicle_color' in detected_vehicle and 'color' in registered_vehicle:
            color_match = self._check_color_compatibility(
                detected_vehicle['vehicle_color'], 
                registered_vehicle['color']
            )
            if not color_match:
                mismatches.append({
                    'attribute': 'vehicle_color',
                    'detected': detected_vehicle['vehicle_color'],
                    'registered': registered_vehicle['color'],
                    'severity': 'medium'
                })
                total_score += 0.4
        
        result['mismatch_score'] = min(total_score, 1.0)
        result['mismatch_details']['mismatches'] = mismatches
        
        if total_score >= self.mismatch_threshold:
            result['has_mismatch'] = True
            if total_score >= 0.8:
                result['recommendation'] = 'investigate_immediately'
            else:
                result['recommendation'] = 'verify_vehicle'
        
        return result
    
    def _check_color_compatibility(self, detected_color: str, registered_color: str) -> bool:
        """Check if detected color is compatible with registered color"""
        if detected_color.lower() == registered_color.lower():
            return True
        
        # Define compatible colors (accounting for lighting, age, etc.)
        compatible_colors = {
            'white': ['silver', 'gray', 'light gray'],
            'silver': ['white', 'gray', 'light gray'],
            'gray': ['silver', 'white', 'dark gray'],
            'black': ['dark gray', 'dark blue'],
            'blue': ['dark blue', 'navy'],
            'red': ['dark red', 'maroon'],
            'unknown': ['*']  # Unknown color matches anything
        }
        
        detected_lower = detected_color.lower()
        registered_lower = registered_color.lower()
        
        if detected_lower in compatible_colors:
            return registered_lower in compatible_colors[detected_lower] or '*' in compatible_colors[detected_lower]
        
        return False


class CriminalIntelligenceSystem:
    """Main system that coordinates all criminal intelligence features"""
    
    def __init__(self):
        self.registration_db = VehicleRegistrationDatabase()
        self.plate_analyzer = LicensePlateAnalyzer()
        self.cloning_detector = CloningDetector()
        self.mismatch_analyzer = VehicleMismatchAnalyzer(self.registration_db)
        self.alert_log = []
    
    def analyze_detection(self, plate_number: str, vehicle_data: Dict, 
                         confidence_score: float, timestamp: float = None) -> Dict:
        """Comprehensive analysis of a vehicle detection"""
        if timestamp is None:
            timestamp = datetime.now().timestamp()
        
        analysis_results = {
            'plate_number': plate_number,
            'timestamp': timestamp,
            'overall_threat_level': 'normal',
            'alerts': [],
            'plate_authenticity': {},
            'cloning_analysis': {},
            'mismatch_analysis': {}
        }
        
        # 1. Analyze plate authenticity
        authenticity_result = self.plate_analyzer.analyze_plate_authenticity(
            plate_number, confidence_score
        )
        analysis_results['plate_authenticity'] = authenticity_result
        
        if authenticity_result['is_suspicious']:
            analysis_results['alerts'].append({
                'type': 'suspicious_plate',
                'severity': 'medium',
                'message': f"Suspicious license plate detected: {', '.join(authenticity_result['suspicion_reasons'])}"
            })
        
        # 2. Check for potential cloning
        cloning_result = self.cloning_detector.check_for_cloning(
            plate_number, vehicle_data, timestamp
        )
        analysis_results['cloning_analysis'] = cloning_result
        
        if cloning_result['is_potential_clone']:
            analysis_results['alerts'].append({
                'type': 'potential_cloning',
                'severity': 'high',
                'message': f"Potential license plate cloning detected (confidence: {cloning_result['confidence']:.2f})"
            })
            analysis_results['overall_threat_level'] = 'high'
        
        # 3. Check vehicle-registration mismatch
        mismatch_result = self.mismatch_analyzer.analyze_vehicle_match(
            plate_number, vehicle_data
        )
        analysis_results['mismatch_analysis'] = mismatch_result
        
        if mismatch_result['has_mismatch']:
            severity = 'high' if mismatch_result['recommendation'] == 'investigate_immediately' else 'medium'
            analysis_results['alerts'].append({
                'type': 'vehicle_mismatch',
                'severity': severity,
                'message': f"Vehicle characteristics don't match registration (score: {mismatch_result['mismatch_score']:.2f})"
            })
            
            if severity == 'high':
                analysis_results['overall_threat_level'] = 'high'
            elif analysis_results['overall_threat_level'] == 'normal':
                analysis_results['overall_threat_level'] = 'medium'
        
        # Log the analysis
        self.alert_log.append(analysis_results)
        
        # Keep only recent logs (last 1000 entries)
        if len(self.alert_log) > 1000:
            self.alert_log = self.alert_log[-1000:]
        
        return analysis_results
    
    def get_threat_summary(self) -> Dict:
        """Get summary of recent threats and statistics"""
        # Get all alerts (not just last hour) for testing purposes
        # In production, you might want to filter by time
        recent_alerts = self.alert_log[-100:] if self.alert_log else []  # Last 100 alerts
        
        threat_counts = {'normal': 0, 'medium': 0, 'high': 0}
        alert_type_counts = {}
        
        for alert_data in recent_alerts:
            threat_level = alert_data.get('overall_threat_level', 'normal')
            threat_counts[threat_level] += 1
            
            for alert in alert_data.get('alerts', []):
                alert_type = alert.get('type', 'unknown')
                if alert_type not in alert_type_counts:
                    alert_type_counts[alert_type] = 0
                alert_type_counts[alert_type] += 1
        
        # Also get time-based recent alerts (last hour) for reference
        current_time = datetime.now().timestamp()
        time_filtered_alerts = [
            alert for alert in self.alert_log 
            if current_time - alert.get('timestamp', 0) < 3600
        ]
        
        return {
            'total_detections_recent': len(recent_alerts),
            'total_detections_last_hour': len(time_filtered_alerts),
            'threat_level_distribution': threat_counts,
            'alert_type_distribution': alert_type_counts,
            'high_priority_alerts': [
                alert for alert in recent_alerts 
                if alert.get('overall_threat_level') == 'high'
            ],
            'all_recent_alerts': recent_alerts  # For debugging
        }
    
    def export_intelligence_report(self, filepath: str):
        """Export intelligence analysis to CSV file"""
        import csv
        
        # Determine file extension and create appropriate filename
        if not filepath.endswith('.csv'):
            filepath = filepath.replace('.json', '.csv')
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            # Define CSV headers
            headers = [
                'timestamp',
                'date_time',
                'plate_number',
                'overall_threat_level',
                'vehicle_type',
                'vehicle_color',
                'plate_authenticity_suspicious',
                'plate_confidence_score',
                'plate_suspicion_reasons',
                'cloning_detected',
                'cloning_confidence',
                'cloning_conflicts_count',
                'registration_mismatch',
                'mismatch_score',
                'mismatch_details',
                'total_alerts',
                'alert_types',
                'alert_messages',
                'recommendation'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            
            # Write each analysis record
            for analysis in self.alert_log:
                # Parse alerts
                alert_types = []
                alert_messages = []
                for alert in analysis.get('alerts', []):
                    alert_types.append(alert['type'])
                    alert_messages.append(alert['message'])
                
                # Parse authenticity data
                authenticity = analysis.get('plate_authenticity', {})
                
                # Parse cloning data  
                cloning = analysis.get('cloning_analysis', {})
                
                # Parse mismatch data
                mismatch = analysis.get('mismatch_analysis', {})
                
                # Format datetime
                try:
                    dt = datetime.fromtimestamp(analysis['timestamp'])
                    formatted_datetime = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    formatted_datetime = 'Unknown'
                
                # Create CSV row
                row = {
                    'timestamp': analysis['timestamp'],
                    'date_time': formatted_datetime,
                    'plate_number': analysis['plate_number'],
                    'overall_threat_level': analysis['overall_threat_level'],
                    'vehicle_type': 'Unknown',  # Will be filled from detection data if available
                    'vehicle_color': 'Unknown',  # Will be filled from detection data if available
                    'plate_authenticity_suspicious': authenticity.get('is_suspicious', False),
                    'plate_confidence_score': authenticity.get('confidence_level', 'normal'),
                    'plate_suspicion_reasons': '; '.join(authenticity.get('suspicion_reasons', [])),
                    'cloning_detected': cloning.get('is_potential_clone', False),
                    'cloning_confidence': cloning.get('confidence', 0.0),
                    'cloning_conflicts_count': len(cloning.get('conflicting_detections', [])),
                    'registration_mismatch': mismatch.get('has_mismatch', False),
                    'mismatch_score': mismatch.get('mismatch_score', 0.0),
                    'mismatch_details': self._format_mismatch_details(mismatch),
                    'total_alerts': len(analysis.get('alerts', [])),
                    'alert_types': '; '.join(alert_types),
                    'alert_messages': '; '.join(alert_messages),
                    'recommendation': mismatch.get('recommendation', 'normal')
                }
                
                writer.writerow(row)
        
        # Also create a summary CSV
        summary_filepath = filepath.replace('.csv', '_summary.csv')
        self._export_summary_csv(summary_filepath)
    
    def _format_mismatch_details(self, mismatch_data):
        """Format mismatch details for CSV"""
        if not mismatch_data.get('mismatch_details', {}).get('mismatches'):
            return 'No mismatches'
        
        details = []
        for mismatch in mismatch_data['mismatch_details']['mismatches']:
            detail = f"{mismatch['attribute']}: detected={mismatch['detected']}, registered={mismatch['registered']}"
            details.append(detail)
        
        return '; '.join(details)
    
    def _export_summary_csv(self, filepath):
        """Export summary statistics to separate CSV file"""
        import csv
        
        threat_summary = self.get_threat_summary()
        
        # Create summary data
        summary_data = [
            ['Metric', 'Value', 'Description'],
            ['Report Generated', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'Timestamp of report generation'],
            ['Total Analyses', len(self.alert_log), 'Total number of license plate analyses performed'],
            ['Detections Last Hour', threat_summary['total_detections_last_hour'], 'Vehicle detections in the past hour'],
            ['High Threat Count', threat_summary['threat_level_distribution'].get('high', 0), 'Number of high-priority threats'],
            ['Medium Threat Count', threat_summary['threat_level_distribution'].get('medium', 0), 'Number of medium-priority threats'], 
            ['Normal Detections', threat_summary['threat_level_distribution'].get('normal', 0), 'Number of normal detections'],
            ['Cloning Alerts', threat_summary['alert_type_distribution'].get('potential_cloning', 0), 'License plate cloning incidents detected'],
            ['Mismatch Alerts', threat_summary['alert_type_distribution'].get('vehicle_mismatch', 0), 'Vehicle-registration mismatches detected'],
            ['Suspicious Plates', threat_summary['alert_type_distribution'].get('suspicious_plate', 0), 'Suspicious license plates detected'],
            ['Plates in History', len(self.cloning_detector.detection_history), 'Unique plates tracked for cloning detection'],
            ['Registrations in DB', len(self.registration_db.registrations), 'Total vehicle registrations in database']
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(summary_data)


# Integration functions for main application
def integrate_criminal_intelligence(main_app_class):
    """Decorator to integrate criminal intelligence features into main app"""
    
    def decorator(cls):
        # Add criminal intelligence system to the class
        original_init = cls.__init__
        
        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self.criminal_intelligence = CriminalIntelligenceSystem()
        
        cls.__init__ = new_init
        
        # Add intelligence analysis to process_frame_enhanced
        original_process_frame = cls.process_frame_enhanced
        
        def enhanced_process_frame(self, frame, frame_nmr):
            # Call original processing
            original_process_frame(self, frame, frame_nmr)
            
            # Add criminal intelligence analysis
            if frame_nmr in self.results:
                for car_id, detection_data in self.results[frame_nmr].items():
                    if 'license_plate' in detection_data:
                        plate_text = detection_data['license_plate']['text']
                        confidence = detection_data['license_plate']['text_score']
                        
                        # Prepare vehicle data for analysis
                        vehicle_data = {
                            'vehicle_type': detection_data.get('vehicle_type', 'unknown'),
                            'vehicle_color': detection_data.get('vehicle_color', 'unknown'),
                            'car_bbox': detection_data['car']['bbox'],
                            'timestamp': detection_data.get('timestamp', 0)
                        }
                        
                        # Perform intelligence analysis
                        intelligence_result = self.criminal_intelligence.analyze_detection(
                            plate_text, vehicle_data, confidence, detection_data.get('timestamp')
                        )
                        
                        # Add intelligence results to detection data
                        detection_data['intelligence_analysis'] = intelligence_result
                        
                        # Log high-priority alerts
                        if intelligence_result['overall_threat_level'] in ['medium', 'high']:
                            alert_msg = f"INTELLIGENCE ALERT: {plate_text} - {intelligence_result['overall_threat_level'].upper()} threat level"
                            for alert in intelligence_result['alerts']:
                                alert_msg += f"\n  • {alert['message']}"
                            self.log_message(alert_msg)
        
        cls.process_frame_enhanced = enhanced_process_frame
        
        return cls
    
    return decorator


if __name__ == "__main__":
    # Test the criminal intelligence system
    ci_system = CriminalIntelligenceSystem()
    
    # Test with sample data
    test_vehicle_data = {
        'vehicle_type': 'truck',
        'vehicle_color': 'red',
        'car_bbox': [100, 100, 300, 200],
        'timestamp': datetime.now().timestamp()
    }
    
    result = ci_system.analyze_detection('ABC123', test_vehicle_data, 0.85)
    print("Criminal Intelligence Analysis Result:")
    print(json.dumps(result, indent=2, default=str))