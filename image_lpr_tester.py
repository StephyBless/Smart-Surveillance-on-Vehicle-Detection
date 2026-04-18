"""
Image-based License Plate Recognition Testing Module
Supports single/batch image processing with condition simulation
"""

import cv2
import numpy as np
from PIL import Image, ImageEnhance
import os
import re
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import easyocr


class ImageConditionSimulator:
    """Simulate various challenging conditions for testing"""
    
    def __init__(self):
        self.conditions = {
            'motion_blur': self.apply_motion_blur,
            'low_resolution': self.apply_low_resolution,
            'night_view': self.apply_night_view,
            'rain_effect': self.apply_rain_effect,
            'fog_effect': self.apply_fog_effect,
            'overexposure': self.apply_overexposure,
            'underexposure': self.apply_underexposure,
            'noise': self.apply_noise
        }
    
    def apply_motion_blur(self, image, intensity=15):
        """Simulate motion blur"""
        kernel_size = intensity
        kernel = np.zeros((kernel_size, kernel_size))
        kernel[int((kernel_size - 1) / 2), :] = np.ones(kernel_size)
        kernel = kernel / kernel_size
        return cv2.filter2D(image, -1, kernel)
    
    def apply_low_resolution(self, image, scale_factor=0.3):
        """Simulate low resolution by downscaling and upscaling"""
        height, width = image.shape[:2]
        small = cv2.resize(image, (int(width * scale_factor), int(height * scale_factor)))
        return cv2.resize(small, (width, height), interpolation=cv2.INTER_NEAREST)
    
    def apply_night_view(self, image, darkness=0.4):
        """Simulate night/low light conditions"""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        hsv[:, :, 2] = hsv[:, :, 2] * darkness
        dark_image = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        
        # Add some noise typical in night images
        noise = np.random.normal(0, 15, image.shape).astype(np.uint8)
        return cv2.add(dark_image, noise)
    
    def apply_rain_effect(self, image, intensity=50):
        """Simulate rain drops and streaks"""
        rain_image = image.copy()
        
        # Add rain drops
        for _ in range(intensity):
            x = np.random.randint(0, image.shape[1])
            y = np.random.randint(0, image.shape[0])
            length = np.random.randint(5, 20)
            cv2.line(rain_image, (x, y), (x, y + length), (200, 200, 200), 1)
        
        # Reduce contrast
        rain_image = cv2.addWeighted(rain_image, 0.8, np.ones_like(rain_image) * 128, 0.2, 0)
        return rain_image
    
    def apply_fog_effect(self, image, intensity=0.5):
        """Simulate foggy conditions"""
        fog = np.ones_like(image) * 200
        return cv2.addWeighted(image, 1 - intensity, fog, intensity, 0)
    
    def apply_overexposure(self, image, factor=1.5):
        """Simulate overexposed image"""
        return np.clip(image * factor, 0, 255).astype(np.uint8)
    
    def apply_underexposure(self, image, factor=0.5):
        """Simulate underexposed image"""
        return np.clip(image * factor, 0, 255).astype(np.uint8)
    
    def apply_noise(self, image, intensity=25):
        """Add gaussian noise"""
        noise = np.random.normal(0, intensity, image.shape).astype(np.uint8)
        return cv2.add(image, noise)
    
    def apply_condition(self, image, condition_name, **kwargs):
        """Apply a specific condition to an image"""
        if condition_name in self.conditions:
            return self.conditions[condition_name](image, **kwargs)
        return image
    
    def get_available_conditions(self):
        """Return list of available conditions"""
        return list(self.conditions.keys())


class LicensePlateValidator:
    """Validate and format license plate text"""
    
    def __init__(self):
        # Common patterns for different regions
        self.patterns = {
            'indian': r'^[A-Z]{2}[-\s]?\d{1,2}[-\s]?[A-Z]{1,2}[-\s]?\d{1,4}$',
            'us': r'^[A-Z0-9]{2,7}$',
            'european': r'^[A-Z]{1,3}[-\s]?\d{1,4}[-\s]?[A-Z]{1,3}$',
            'generic': r'^[A-Z0-9]{4,10}$'
        }
        
        # Character correction mapping (common OCR mistakes)
        self.char_corrections = {
            '0': ['O', 'D', 'Q'],
            'O': ['0', 'D', 'Q'],
            '1': ['I', 'L', 'l'],
            'I': ['1', 'l', 'L'],
            '5': ['S'],
            'S': ['5'],
            '8': ['B'],
            'B': ['8'],
            '2': ['Z'],
            'Z': ['2'],
            '6': ['G'],
            'G': ['6']
        }
    
    def clean_text(self, text):
        """Clean and format license plate text"""
        if not text:
            return ""
        
        # Remove special characters except hyphens and spaces
        text = re.sub(r'[^A-Z0-9\s-]', '', text.upper())
        
        # Remove extra spaces
        text = ' '.join(text.split())
        
        return text
    
    def validate_format(self, text, region='indian'):
        """Validate if text matches a license plate pattern"""
        clean = self.clean_text(text)
        pattern = self.patterns.get(region, self.patterns['generic'])
        return bool(re.match(pattern, clean))
    
    def format_indian_plate(self, text):
        """Format text as Indian license plate (e.g., TN09AB1234)"""
        clean = self.clean_text(text).replace(' ', '').replace('-', '')
        
        if len(clean) < 6:
            return text
        
        # Try to match Indian pattern: 2 letters, 2 digits, 1-2 letters, 1-4 digits
        match = re.match(r'^([A-Z]{2})(\d{1,2})([A-Z]{1,2})(\d{1,4})$', clean)
        if match:
            state, district, series, number = match.groups()
            return f"{state}{district}{series}{number}"
        
        return clean
    
    def suggest_corrections(self, text):
        """Suggest possible corrections for ambiguous characters"""
        suggestions = []
        text = self.clean_text(text)
        
        for i, char in enumerate(text):
            if char in self.char_corrections:
                for alt_char in self.char_corrections[char]:
                    suggestion = text[:i] + alt_char + text[i+1:]
                    suggestions.append(suggestion)
        
        return list(set(suggestions))
    
    def calculate_confidence(self, text, region='indian'):
        """Calculate confidence score for the plate text"""
        score = 0.0
        
        # Length check
        clean = self.clean_text(text)
        if 6 <= len(clean) <= 10:
            score += 0.3
        
        # Pattern match
        if self.validate_format(text, region):
            score += 0.4
        
        # Alphanumeric check
        if any(c.isalpha() for c in clean) and any(c.isdigit() for c in clean):
            score += 0.2
        
        # No special characters
        if clean.replace('-', '').replace(' ', '').isalnum():
            score += 0.1
        
        return min(score, 1.0)


class ImageLPRTester:
    """Main class for image-based license plate recognition testing"""
    
    def __init__(self, enhanced_processor, license_plate_detector, formatter=None):
        self.enhanced_processor = enhanced_processor
        self.license_plate_detector = license_plate_detector
        self.formatter = formatter
        self.simulator = ImageConditionSimulator()
        self.validator = LicensePlateValidator()
        self.ocr_reader = None
        
        # Initialize OCR
        try:
            self.ocr_reader = easyocr.Reader(['en'], gpu=False)
        except:
            pass
        
        # Results storage
        self.test_results = []
    
    def detect_license_plate_region(self, image):
        """Detect license plate region in image"""
        results = self.license_plate_detector(image, conf=0.25)
        
        detected_plates = []
        for result in results:
            boxes = result.boxes
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                
                # Extract plate region
                plate_img = image[y1:y2, x1:x2]
                detected_plates.append({
                    'bbox': (x1, y1, x2, y2),
                    'confidence': conf,
                    'image': plate_img
                })
        
        return detected_plates
    
    def extract_text_from_plate(self, plate_image):
        """Extract text using improved OCR logic from enhanced processor"""
        
        results = []

        if not self.enhanced_processor:
            return results

        try:
            # ---- Apply same preprocessing as improved OCR ----
            import cv2
            import numpy as np

            crop = plate_image.copy()

            # Upscale
            scale = 3
            crop = cv2.resize(crop, (crop.shape[1]*scale, crop.shape[0]*scale),
                            interpolation=cv2.INTER_CUBIC)

            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            gray = clahe.apply(gray)

            adaptive = cv2.adaptiveThreshold(
                gray, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11, 2
            )

            # Run OCR
            ocr_results = self.ocr_reader.readtext(adaptive, detail=1)

            if not ocr_results:
                return results

            # Sort left-to-right
            ocr_results = sorted(ocr_results, key=lambda x: x[0][0][0])

            combined_text = ""
            total_conf = 0

            for res in ocr_results:
                combined_text += res[1]
                total_conf += res[2]

            text = combined_text.upper().replace(" ", "").replace("-", "")
            text = ''.join(c for c in text if c.isalnum())
            conf = total_conf / len(ocr_results)

            # Apply your formatter
            if self.formatter:
                formatted_text, format_conf = self.formatter(text)
            else:
                formatted_text = text
                format_conf = 0

            if formatted_text:
                conf = (conf + format_conf) / 2

            results.append({
                'method': 'Improved_OCR',
                'text': formatted_text,
                'confidence': conf
            })

        except Exception as e:
            print("Image OCR error:", e)

        return results

    
    def preprocess_for_ocr(self, plate_image):
        """Preprocess plate image for better OCR"""
        # Convert to grayscale
        gray = cv2.cvtColor(plate_image, cv2.COLOR_BGR2GRAY)
        
        # Apply bilateral filter to reduce noise while keeping edges
        filtered = cv2.bilateralFilter(gray, 11, 17, 17)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            filtered, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return morph
    
    def process_single_image(self, image_path, apply_conditions=None):
        """Process a single image with optional condition simulation"""
        # Load image
        if isinstance(image_path, str):
            image = cv2.imread(image_path)
            image_name = os.path.basename(image_path)
        else:
            image = image_path
            image_name = "uploaded_image"
        
        if image is None:
            return None
        
        results = {
            'image_name': image_name,
            'original_image': image.copy(),
            'conditions_tested': {},
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Test original image
        results['original'] = self._test_image_condition(image, 'Original')
        
        # Apply and test conditions if specified
        if apply_conditions:
            for condition in apply_conditions:
                if condition in self.simulator.get_available_conditions():
                    modified_image = self.simulator.apply_condition(image.copy(), condition)
                    condition_result = self._test_image_condition(modified_image, condition)
                    results['conditions_tested'][condition] = {
                        'result': condition_result,
                        'modified_image': modified_image
                    }
        
        return results
    
    def _test_image_condition(self, image, condition_name):
        """Test license plate detection and recognition on an image"""
        result = {
            'condition': condition_name,
            'detected': False,
            'plates': [],
            'best_text': '',
            'best_confidence': 0.0,
            'all_readings': [],
            'detected_texts': []

        }
        
        # Detect plates
        detected_plates = self.detect_license_plate_region(image)
        
        if detected_plates:
            result['detected'] = True
            
            for plate_data in detected_plates:
                plate_best_text = ''
                plate_best_conf = 0

                plate_img = plate_data['image']
                
                # Extract text
                text_results = self.extract_text_from_plate(plate_img)
                
                # Process each text result
                for text_data in text_results:
                    text = text_data['text']
                    conf = text_data['confidence']
                    method = text_data['method']
                    
                    # Clean and validate
                    clean_text = self.validator.clean_text(text)
                    formatted_text = self.validator.format_indian_plate(clean_text)
                    validation_conf = self.validator.calculate_confidence(formatted_text)
                    
                    # Combined confidence
                    combined_conf = (conf + validation_conf) / 2
                    
                    reading = {
                        'raw_text': text,
                        'cleaned_text': clean_text,
                        'formatted_text': formatted_text,
                        'ocr_confidence': conf,
                        'validation_confidence': validation_conf,
                        'combined_confidence': combined_conf,
                        'method': method,
                        'bbox': plate_data['bbox']
                    }
                    
                    result['all_readings'].append(reading)
                    
                    # Update best result
                    # Prefer valid Indian format plates first
                    # Determine best for this specific plate
                    is_valid = self.validator.validate_format(formatted_text, region='indian')

                    if is_valid:
                        if combined_conf + 0.1 > plate_best_conf:
                            plate_best_conf = combined_conf
                            plate_best_text = formatted_text
                    else:
                        if plate_best_text == '' and combined_conf > plate_best_conf:
                            plate_best_conf = combined_conf
                            plate_best_text = formatted_text

                if plate_best_text:
                    result['detected_texts'].append({
                        'text': plate_best_text,
                        'confidence': plate_best_conf,
                        'bbox': plate_data['bbox']
                    })

                    # Also update global best
                    if plate_best_conf > result['best_confidence']:
                        result['best_confidence'] = plate_best_conf
                        result['best_text'] = plate_best_text
                
                result['plates'].append({
                    'bbox': plate_data['bbox'],
                    'detection_confidence': plate_data['confidence'],
                    'plate_image': plate_img
                })
                

        
        return result
    
    def process_batch(self, image_paths, conditions=None):
        """Process multiple images"""
        batch_results = []
        
        for image_path in image_paths:
            result = self.process_single_image(image_path, conditions)
            if result:
                batch_results.append(result)
        
        return batch_results
    
    def generate_comparison_report(self, results):
        """Generate a detailed comparison report"""
        report = {
            'summary': {
                'total_tests': 0,
                'successful_detections': 0,
                'failed_detections': 0,
                'conditions_performance': {}
            },
            'detailed_results': results
        }
        
        # Analyze results
        for result in results:
            # Original image
            report['summary']['total_tests'] += 1
            if result['original']['detected']:
                report['summary']['successful_detections'] += 1
            else:
                report['summary']['failed_detections'] += 1
            
            # Conditions
            for condition, data in result['conditions_tested'].items():
                if condition not in report['summary']['conditions_performance']:
                    report['summary']['conditions_performance'][condition] = {
                        'tested': 0,
                        'detected': 0,
                        'avg_confidence': 0.0
                    }
                
                perf = report['summary']['conditions_performance'][condition]
                perf['tested'] += 1
                
                if data['result']['detected']:
                    perf['detected'] += 1
                    perf['avg_confidence'] += data['result']['best_confidence']
        
        # Calculate averages
        for condition, perf in report['summary']['conditions_performance'].items():
            if perf['detected'] > 0:
                perf['avg_confidence'] /= perf['detected']
                perf['success_rate'] = (perf['detected'] / perf['tested']) * 100
            else:
                perf['success_rate'] = 0.0
        
        return report
    
    def create_visual_comparison(self, result, output_path=None):
        """Create a visual comparison image showing all conditions"""
        images_to_show = []
        titles = []
        
        # Original image with detection
        original_img = result['original_image'].copy()
        if result['original']['detected']:
            for plate in result['original']['plates']:
                x1, y1, x2, y2 = plate['bbox']
                cv2.rectangle(original_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(original_img, result['original']['best_text'], 
                          (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        images_to_show.append(original_img)
        titles.append(f"Original: {result['original']['best_text']}")
        
        # Condition images
        for condition, data in result['conditions_tested'].items():
            cond_img = data['modified_image'].copy()
            if data['result']['detected']:
                for plate in data['result']['plates']:
                    x1, y1, x2, y2 = plate['bbox']
                    cv2.rectangle(cond_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(cond_img, data['result']['best_text'], 
                              (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            images_to_show.append(cond_img)
            conf = data['result']['best_confidence']
            titles.append(f"{condition}: {data['result']['best_text']} ({conf:.2f})")
        
        # Create grid layout
        n_images = len(images_to_show)
        cols = 3
        rows = (n_images + cols - 1) // cols
        
        # Resize all images to same size
        target_size = (400, 300)
        resized_images = [cv2.resize(img, target_size) for img in images_to_show]
        
        # Create canvas
        canvas_width = target_size[0] * cols
        canvas_height = (target_size[1] + 30) * rows
        canvas = np.ones((canvas_height, canvas_width, 3), dtype=np.uint8) * 255
        
        # Place images
        for idx, (img, title) in enumerate(zip(resized_images, titles)):
            row = idx // cols
            col = idx % cols
            
            y_start = row * (target_size[1] + 30)
            x_start = col * target_size[0]
            
            # Place image
            canvas[y_start:y_start+target_size[1], x_start:x_start+target_size[0]] = img
            
            # Add title
            cv2.putText(canvas, title, (x_start + 10, y_start + target_size[1] + 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        
        if output_path:
            cv2.imwrite(output_path, canvas)
        
        return canvas
