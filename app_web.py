from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_socketio import SocketIO, emit
import cv2
import numpy as np
import pandas as pd
import threading
import time
import os
import csv
import json
import base64
from datetime import datetime, timedelta
from PIL import Image
import io
from werkzeug.utils import secure_filename
import logging

# Import your existing modules
try:
    from speed import SpeedEstimationModule, TrafficViolationDetector
    from criminal_intelligence import CriminalIntelligenceSystem
    from database_alerts import RealTimeDatabaseChecker
    MODULES_AVAILABLE = True
except ImportError:
    print("Warning: Some modules not available. Running in limited mode.")
    MODULES_AVAILABLE = False

try:
    from ultralytics import YOLO
    import easyocr
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("Warning: YOLO/EasyOCR not available. Detection disabled.")

try:
    from sort.sort import Sort
    SORT_AVAILABLE = True
except ImportError:
    SORT_AVAILABLE = False
    print("Warning: SORT tracker not available.")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

socketio = SocketIO(app, cors_allowed_origins="*")

# Global variables for processing
processing_status = {
    'is_processing': False,
    'current_frame': 0,
    'total_frames': 0,
    'progress': 0,
    'results': {},
    'processed_data': [],
    'statistics': {
        'frames_processed': 0,
        'plates_detected': 0,
        'unique_plates': 0,
        'processing_fps': 0,
        'video_time': '00:00'
    }
}

# Initialize systems
class WebLPRSystem:
    def __init__(self):
        self.is_processing = False
        self.video_source = None
        self.cap = None
        self.video_fps = 30
        self.results = {}
        self.processed_data = []
        
        # AI Models
        self.coco_model = None
        self.license_plate_detector = None
        self.mot_tracker = None
        self.ocr_reader = None
        
        # Enhanced systems
        if MODULES_AVAILABLE:
            self.speed_estimator = SpeedEstimationModule(fps=self.video_fps)
            self.criminal_intelligence = CriminalIntelligenceSystem()
            self.db_checker = RealTimeDatabaseChecker()
        
        # Vehicle classes in COCO dataset
        self.vehicles = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
        
        # Settings
        self.settings = {
            'detection_confidence': 0.5,
            'tracking_enabled': True,
            'interpolation_enabled': True,
            'color_detection_enabled': True,
            'vehicle_type_detection': True
        }
        
        self.initialize_models()
    
    def initialize_models(self):
        """Initialize AI models"""
        if YOLO_AVAILABLE:
            try:
                self.coco_model = YOLO('yolov8n.pt')
                if os.path.exists('license_plate_detector.pt'):
                    self.license_plate_detector = YOLO('license_plate_detector.pt')
            except Exception as e:
                print(f"Error loading YOLO models: {e}")
        
        if SORT_AVAILABLE:
            try:
                self.mot_tracker = Sort()
            except Exception as e:
                print(f"Error initializing tracker: {e}")
        
        try:
            import easyocr
            self.ocr_reader = easyocr.Reader(['en'], gpu=False)
        except Exception as e:
            print(f"Error initializing OCR: {e}")
    
    def detect_vehicle_color(self, vehicle_crop):
        """Detect dominant color of vehicle"""
        if vehicle_crop is None or vehicle_crop.size == 0:
            return "unknown"
        
        try:
            # Convert BGR to HSV
            hsv = cv2.cvtColor(vehicle_crop, cv2.COLOR_BGR2HSV)
            
            # Define color ranges (simplified)
            dominant_colors = {
                'red': ([0, 100, 100], [10, 255, 255]),
                'blue': ([86, 100, 100], [125, 255, 255]),
                'green': ([36, 100, 100], [85, 255, 255]),
                'white': ([0, 0, 200], [180, 30, 255]),
                'black': ([0, 0, 0], [180, 255, 50]),
                'gray': ([0, 0, 51], [180, 30, 199])
            }
            
            color_counts = {}
            for color_name, (lower, upper) in dominant_colors.items():
                color_mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
                color_counts[color_name] = cv2.countNonZero(color_mask)
            
            if max(color_counts.values()) > 0:
                return max(color_counts, key=color_counts.get)
            else:
                return "unknown"
                
        except Exception as e:
            return "unknown"
    
    def read_license_plate(self, frame, x1, y1, x2, y2):
        """Read license plate text using OCR"""
        if not self.ocr_reader:
            return None, 0
        
        try:
            license_crop = frame[int(y1):int(y2), int(x1):int(x2)]
            if license_crop.size == 0:
                return None, 0
            
            gray = cv2.cvtColor(license_crop, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 64, 255, cv2.THRESH_BINARY_INV)
            
            results = self.ocr_reader.readtext(thresh)
            
            if results:
                best_result = max(results, key=lambda x: x[2])
                text = best_result[1].upper().replace(' ', '')
                confidence = best_result[2]
                
                if len(text) >= 3 and confidence > 0.5:
                    return text, confidence
            
            return None, 0
            
        except Exception as e:
            return None, 0
    
    def get_car(self, license_plate, vehicle_track_ids):
        """Get car that contains the license plate"""
        x1, y1, x2, y2, score, class_id = license_plate
        
        for track in vehicle_track_ids:
            if len(track) >= 5:
                xcar1, ycar1, xcar2, ycar2, car_id = track[:5]
                if x1 > xcar1 and y1 > ycar1 and x2 < xcar2 and y2 < ycar2:
                    return [xcar1, ycar1, xcar2, ycar2, car_id]
        return None

# Initialize the system
lpr_system = WebLPRSystem()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_video', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file'}), 400
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file:
        filename = secure_filename(file.filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Get video info
        cap = cv2.VideoCapture(filepath)
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            
            session['video_path'] = filepath
            return jsonify({
                'success': True,
                'filename': filename,
                'fps': fps,
                'total_frames': total_frames
            })
        else:
            return jsonify({'error': 'Invalid video file'}), 400

@app.route('/start_processing', methods=['POST'])
def start_processing():
    if 'video_path' not in session:
        return jsonify({'error': 'No video uploaded'}), 400
    
    if processing_status['is_processing']:
        return jsonify({'error': 'Processing already in progress'}), 400
    
    video_path = session['video_path']
    
    # Start processing in background thread
    thread = threading.Thread(target=process_video_background, args=(video_path,))
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'message': 'Processing started'})

def process_video_background(video_path):
    """Background video processing function"""
    processing_status['is_processing'] = True
    processing_status['current_frame'] = 0
    processing_status['results'] = {}
    processing_status['processed_data'] = []
    
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            socketio.emit('processing_error', {'error': 'Cannot open video file'})
            return
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        processing_status['total_frames'] = total_frames
        lpr_system.video_fps = fps
        
        frame_nmr = -1
        start_time = time.time()
        
        while processing_status['is_processing'] and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_nmr += 1
            processing_status['current_frame'] = frame_nmr
            
            # Process frame
            process_frame(frame, frame_nmr, fps)
            
            # Update progress
            progress = (frame_nmr / total_frames) * 100
            processing_status['progress'] = progress
            
            # Emit progress update
            if frame_nmr % 10 == 0:  # Update every 10 frames
                elapsed = time.time() - start_time
                processing_fps = frame_nmr / elapsed if elapsed > 0 else 0
                video_time = frame_nmr / fps
                
                stats = {
                    'frames_processed': frame_nmr,
                    'plates_detected': len(processing_status['processed_data']),
                    'unique_plates': len(set(item.get('license_number', '') for item in processing_status['processed_data'] if item.get('license_number', '') != '0')),
                    'processing_fps': round(processing_fps, 1),
                    'video_time': f"{int(video_time//60):02d}:{int(video_time%60):02d}",
                    'progress': round(progress, 1)
                }
                
                # Send frame preview (optional, can be memory intensive)
                _, buffer = cv2.imencode('.jpg', cv2.resize(frame, (320, 240)))
                frame_b64 = base64.b64encode(buffer).decode('utf-8')
                
                socketio.emit('processing_update', {
                    'statistics': stats,
                    'frame_preview': frame_b64
                })
            
            # Small delay to prevent overwhelming
            time.sleep(0.01)
        
        cap.release()
        
        # Export results
        export_results_to_csv()
        
        processing_status['is_processing'] = False
        socketio.emit('processing_complete', {
            'total_plates': len(processing_status['processed_data']),
            'unique_plates': len(set(item.get('license_number', '') for item in processing_status['processed_data'] if item.get('license_number', '') != '0'))
        })
        
    except Exception as e:
        processing_status['is_processing'] = False
        socketio.emit('processing_error', {'error': str(e)})

def process_frame(frame, frame_nmr, fps):
    """Process a single frame"""
    if not lpr_system.coco_model or not lpr_system.license_plate_detector:
        return
    
    try:
        processing_status['results'][frame_nmr] = {}
        timestamp = frame_nmr / fps
        
        # Detect vehicles
        detections = lpr_system.coco_model(frame, conf=lpr_system.settings['detection_confidence'])[0]
        detections_ = []
        vehicle_types = {}
        
        for detection in detections.boxes.data.tolist():
            x1, y1, x2, y2, score, class_id = detection
            if int(class_id) in lpr_system.vehicles:
                detections_.append([x1, y1, x2, y2, score])
                vehicle_types[(x1, y1, x2, y2)] = lpr_system.vehicles[int(class_id)]
        
        # Track vehicles
        if lpr_system.settings['tracking_enabled'] and lpr_system.mot_tracker:
            track_ids = lpr_system.mot_tracker.update(np.asarray(detections_))
        else:
            track_ids = [[*det, i] for i, det in enumerate(detections_)]
        
        # Detect license plates
        license_plates = lpr_system.license_plate_detector(frame, conf=0.3)[0]
        
        for license_plate in license_plates.boxes.data.tolist():
            x1, y1, x2, y2, score, class_id = license_plate
            
            car_match = lpr_system.get_car(license_plate, track_ids)
            if car_match:
                xcar1, ycar1, xcar2, ycar2, car_id = car_match
                
                # Detect vehicle attributes
                vehicle_crop = frame[int(ycar1):int(ycar2), int(xcar1):int(xcar2)]
                vehicle_color = "unknown"
                vehicle_type = "unknown"
                
                if lpr_system.settings['color_detection_enabled']:
                    vehicle_color = lpr_system.detect_vehicle_color(vehicle_crop)
                
                if lpr_system.settings['vehicle_type_detection']:
                    for (vx1, vy1, vx2, vy2), vtype in vehicle_types.items():
                        if abs(vx1 - xcar1) < 50 and abs(vy1 - ycar1) < 50:
                            vehicle_type = vtype
                            break
                
                # Read license plate
                license_text, text_score = lpr_system.read_license_plate(frame, x1, y1, x2, y2)
                
                if license_text:
                    # Store results
                    processing_status['results'][frame_nmr][car_id] = {
                        'car': {'bbox': [xcar1, ycar1, xcar2, ycar2]},
                        'license_plate': {
                            'bbox': [x1, y1, x2, y2],
                            'text': license_text,
                            'bbox_score': score,
                            'text_score': text_score
                        },
                        'timestamp': timestamp,
                        'vehicle_color': vehicle_color,
                        'vehicle_type': vehicle_type
                    }
                    
                    # Add to processed data
                    processing_status['processed_data'].append({
                        'frame_nmr': frame_nmr,
                        'car_id': car_id,
                        'car_bbox': f"[{xcar1} {ycar1} {xcar2} {ycar2}]",
                        'license_plate_bbox': f"[{x1} {y1} {x2} {y2}]",
                        'license_plate_bbox_score': score,
                        'license_number': license_text,
                        'license_number_score': text_score,
                        'timestamp': timestamp,
                        'vehicle_color': vehicle_color,
                        'vehicle_type': vehicle_type
                    })
                    
                    # Check for stolen vehicles if available
                    if MODULES_AVAILABLE and hasattr(lpr_system, 'db_checker'):
                        alert_result = lpr_system.db_checker.check_detection(
                            license_plate=license_text,
                            vehicle_color=vehicle_color,
                            vehicle_type=vehicle_type,
                            detection_info={
                                'camera_id': 'WEB_SYSTEM',
                                'timestamp': datetime.now(),
                                'confidence': text_score,
                                'frame_number': frame_nmr
                            }
                        )
                        
                        if alert_result:
                            # Emit stolen vehicle alert
                            socketio.emit('stolen_vehicle_alert', {
                                'license_plate': license_text,
                                'case_number': alert_result['stolen_vehicle_data']['case_number'],
                                'priority': alert_result['stolen_vehicle_data']['priority_level'],
                                'agency': alert_result['stolen_vehicle_data']['agency'],
                                'frame_number': frame_nmr,
                                'timestamp': timestamp
                            })
    
    except Exception as e:
        print(f"Error processing frame {frame_nmr}: {str(e)}")

def export_results_to_csv():
    """Export results to CSV file"""
    if not processing_status['processed_data']:
        return
    
    os.makedirs('output', exist_ok=True)
    filepath = os.path.join('output', f'results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
    
    headers = ['frame_nmr', 'car_id', 'car_bbox', 'license_plate_bbox', 
               'license_plate_bbox_score', 'license_number', 'license_number_score',
               'timestamp', 'vehicle_color', 'vehicle_type']
    
    with open(filepath, 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(processing_status['processed_data'])
    
    session['results_file'] = filepath

@app.route('/stop_processing', methods=['POST'])
def stop_processing():
    processing_status['is_processing'] = False
    return jsonify({'success': True, 'message': 'Processing stopped'})

@app.route('/search_plate', methods=['POST'])
def search_plate():
    data = request.get_json()
    target_plate = data.get('plate', '').strip().upper()
    similarity_threshold = data.get('threshold', 0.8)
    
    if not target_plate or not processing_status['processed_data']:
        return jsonify({'error': 'No plate specified or no data available'})
    
    # Search logic (simplified)
    results = []
    for item in processing_status['processed_data']:
        plate = item.get('license_number', '')
        if plate and target_plate in plate.upper():
            results.append({
                'frame': item['frame_nmr'],
                'car_id': item['car_id'],
                'plate': plate,
                'confidence': item.get('license_number_score', 0),
                'vehicle_type': item.get('vehicle_type', 'unknown'),
                'vehicle_color': item.get('vehicle_color', 'unknown'),
                'timestamp': item.get('timestamp', 0)
            })
    
    return jsonify({'results': results, 'total_found': len(results)})

@app.route('/get_statistics')
def get_statistics():
    return jsonify(processing_status['statistics'])

@app.route('/download_results')
def download_results():
    if 'results_file' in session and os.path.exists(session['results_file']):
        return send_file(session['results_file'], as_attachment=True)
    else:
        return jsonify({'error': 'No results file available'}), 404

# Socket.IO events
@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('connected', {'status': 'Connected to LPR System'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs('output', exist_ok=True)
    
    # For development
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
    
    # For production (IBM Cloud)
    # port = int(os.environ.get('PORT', 5000))
    # socketio.run(app, host='0.0.0.0', port=port)