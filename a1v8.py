import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import cv2
import numpy as np
import pandas as pd
import threading
import time
import os
import csv
import ast
from datetime import datetime
from PIL import Image, ImageTk
import json
from difflib import SequenceMatcher
# Add this after line 14 (after: from difflib import SequenceMatcher)
import json
from database_module import VehicleDatabaseManager, format_vehicle_data_from_detection
from enhanced_lpr_system import EnhancedLPRProcessor


# Try to import required libraries with fallbacks
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("Warning: ultralytics not available. YOLO detection disabled.")

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    print("Warning: easyocr not available. OCR disabled.")

try:
    from scipy.interpolate import interp1d
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("Warning: scipy not available. Interpolation disabled.")

# Import SORT tracker (assuming it's available)
try:
    from sort.sort import Sort
    SORT_AVAILABLE = True
except ImportError:
    SORT_AVAILABLE = False
    print("Warning: SORT tracker not available. Tracking disabled.")

class LicensePlateRecognitionSystem:
    def __init__(self):
        self.root = tk.Tk()
        self.is_processing = False
        self.video_source = None
        self.cap = None
        self.current_frame = None
        
        # Processing results
        self.results = {}
        self.processed_data = []
        self.interpolated_data = []
        
        # Models and trackers
        self.coco_model = None
        self.license_plate_detector = None
        self.mot_tracker = None
        self.ocr_reader = None
        
        # Vehicle classes in COCO dataset
        self.vehicles = [2, 3, 5, 7]  # car, motorcycle, bus, truck
        
        # Search functionality
        self.target_plates = []
        self.search_results = {}
        
        # Settings
        self.settings = {
            'detection_confidence': 0.20,  # CHANGED: Lower for more detections
            'tracking_enabled': True,
            'interpolation_enabled': True,
            'save_screenshots': True,
            'output_directory': './output'
        }
        
        # Load settings and initialize
        self.load_settings()

        # Add this after line 82 (after: self.load_settings())
        # Initialize database connection
        try:
            with open('db_config.json', 'r') as f:
                db_config = json.load(f)
            
            self.db = VehicleDatabaseManager(
                host=db_config['host'],
                user=db_config['user'],
                password=db_config['password'],
                database=db_config['database']
            )
            print("✅ Database connected successfully")
        except Exception as e:
            print(f"⚠️ Database connection failed: {e}")
            self.db = None


        self.enhanced_processor = EnhancedLPRProcessor('license_plate_detector.pt')
        self.log_message("✅ Enhanced processor initialized")

        # Configure enhanced processor settings
        self.enhanced_processor.update_settings({
            'auto_enhance': True,
            'weather_detection': True,
            'multi_scale_detection': True,
            'advanced_ocr': True,
            'false_positive_filter': True,
            'min_ocr_confidence': 0.6
        })

        self.log_message("⚙️ Enhanced processor settings applied")

        # Performance presets
        self.fast_settings = {
            'auto_enhance': True,
            'weather_detection': False,
            'multi_scale_detection': False,
            'min_ocr_confidence': 0.7
        }

        self.accurate_settings = {
            'auto_enhance': True,
            'weather_detection': True,
            'multi_scale_detection': True,
            'min_ocr_confidence': 0.5
        }

        self.initialize_models()
        self.setup_gui()


    def apply_processing_mode(self, mode='accurate'):
        """Switch between fast and accurate modes"""
        if mode == 'fast':
            self.enhanced_processor.update_settings(self.fast_settings)
            self.log_message("⚡ Fast mode activated")
        elif mode == 'accurate':
            self.enhanced_processor.update_settings(self.accurate_settings)
            self.log_message("🎯 Accurate mode activated")

        
    def initialize_models(self):
        """Initialize AI models"""
        if YOLO_AVAILABLE:
            try:
                self.log_message("Loading YOLO models...")
                self.coco_model = YOLO('yolov8n.pt')
            
            # Try multiple possible model files
                model_options = [
                    'license_plate_detector.pt',
                    'best.pt',
                    'yolov8n.pt'  # Fallback
                ]
            
                for model_path in model_options:
                    if os.path.exists(model_path):
                        self.license_plate_detector = YOLO(model_path)
                        self.log_message(f"✅ License plate detector loaded: {model_path}")
                        break
                    else:
                        self.license_plate_detector = YOLO('yolov8n.pt')
                        self.log_message("⚠️ Using YOLOv8n as fallback")
                
            except Exception as e:
                self.log_message(f"Error loading YOLO models: {e}")
        
        if SORT_AVAILABLE:
            try:
                self.mot_tracker = Sort()
                self.log_message("SORT tracker initialized")
            except Exception as e:
                self.log_message(f"Error initializing tracker: {e}")
        
        if EASYOCR_AVAILABLE:
            try:
                self.ocr_reader = easyocr.Reader(['en'], gpu=False)
                self.log_message("EasyOCR reader initialized")
            except Exception as e:
                self.log_message(f"Error initializing OCR: {e}")

    

    def setup_gui(self):
        """Setup the main GUI"""
        self.root.title("THEFT IDENTIFICATION")
        self.root.geometry("1400x900")
        self.root.configure(bg='#2c3e50')
        
        # Style configuration
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'))
        style.configure('Header.TLabel', font=('Arial', 12, 'bold'))
        
        # Main container
        main_container = tk.Frame(self.root, bg='#2c3e50')
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_label = tk.Label(main_container, text="SMART STOLEN VEHICLE DETECTION SYSTEM", 
                              font=('Arial', 18, 'bold'), bg='#2c3e50', fg='white')
        title_label.pack(pady=10)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create tabs
        self.setup_processing_tab()
        self.setup_search_tab()
        self.setup_results_tab()
        self.setup_settings_tab()

        self.setup_database_tab()
        
        # Status bar
        self.setup_status_bar(main_container)

    def setup_processing_tab(self):
        """Setup the video processing tab"""
        processing_frame = ttk.Frame(self.notebook)
        self.notebook.add(processing_frame, text="Video Processing")
        
        # Left panel - Controls
        left_panel = ttk.LabelFrame(processing_frame, text="Controls", padding=10)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        # Video source selection
        ttk.Label(left_panel, text="Video Source:", style='Header.TLabel').pack(anchor=tk.W)
        ttk.Button(left_panel, text="Select Video File", 
                  command=self.select_video_file).pack(fill=tk.X, pady=2)
        ttk.Button(left_panel, text="Use Webcam", 
                  command=self.use_webcam).pack(fill=tk.X, pady=2)
        
        ttk.Separator(left_panel, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # Processing controls
        ttk.Label(left_panel, text="Processing:", style='Header.TLabel').pack(anchor=tk.W)
        ttk.Button(left_panel, text="Start Processing", 
                  command=self.start_processing).pack(fill=tk.X, pady=2)
        ttk.Button(left_panel, text="Stop Processing", 
                  command=self.stop_processing).pack(fill=tk.X, pady=2)
        
        ttk.Separator(left_panel, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # Data operations
        ttk.Label(left_panel, text="Data Operations:", style='Header.TLabel').pack(anchor=tk.W)
        ttk.Button(left_panel, text="Interpolate Missing Data", 
                  command=self.interpolate_data).pack(fill=tk.X, pady=2)
        ttk.Button(left_panel, text="Export to CSV", 
                  command=self.export_csv).pack(fill=tk.X, pady=2)
        
        
        
        ttk.Separator(left_panel, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # Processing statistics
        stats_frame = ttk.LabelFrame(left_panel, text="Statistics")
        stats_frame.pack(fill=tk.X, pady=5)
        
        self.stats_labels = {
            'frames_processed': tk.Label(stats_frame, text="Frames: 0", bg='white'),
            'video_time': tk.Label(stats_frame, text="Time: 0:00 / 0:00", bg='white'),
            'plates_detected': tk.Label(stats_frame, text="Plates: 0", bg='white'),
            'unique_plates': tk.Label(stats_frame, text="Unique: 0", bg='white'),
            'processing_fps': tk.Label(stats_frame, text="FPS: 0", bg='white')
        }
        
        for label in self.stats_labels.values():
            label.pack(anchor=tk.W, padx=5)
        
        # Right panel - Video display
        right_panel = ttk.LabelFrame(processing_frame, text="Live Preview", padding=10)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Video display
        self.video_label = tk.Label(right_panel, bg="black", text="No video loaded", 
                                   fg="white", font=('Arial', 14))
        self.video_label.pack(expand=True, fill=tk.BOTH)

    def setup_search_tab(self):
        """Setup the license plate search tab"""
        search_frame = ttk.Frame(self.notebook)
        self.notebook.add(search_frame, text="Search & Analysis")
        
        # Top panel - Search controls
        search_controls = ttk.LabelFrame(search_frame, text="Search Controls", padding=10)
        search_controls.pack(fill=tk.X, padx=5, pady=5)
        
        # Search input frame
        input_frame = ttk.Frame(search_controls)
        input_frame.pack(fill=tk.X)
        
        ttk.Label(input_frame, text="Target License Plate:").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(input_frame, font=('Arial', 12))
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(input_frame, text="Search", 
                  command=self.search_license_plate).pack(side=tk.LEFT)
        
        # Search options
        options_frame = ttk.Frame(search_controls)
        options_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(options_frame, text="Similarity Threshold:").pack(side=tk.LEFT)
        self.similarity_var = tk.DoubleVar(value=0.8)
        similarity_scale = ttk.Scale(options_frame, from_=0.5, to=1.0, 
                                   variable=self.similarity_var, orient=tk.HORIZONTAL)
        similarity_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        ttk.Button(options_frame, text="Show All Plates", 
                  command=self.show_all_plates).pack(side=tk.RIGHT)
        
        # Results display
        results_frame = ttk.LabelFrame(search_frame, text="Search Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create Treeview for results
        columns = ('Plate', 'Frames', 'Car ID', 'First Frame', 'Last Frame', 'Match Info')
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            self.results_tree.heading(col, text=col)
            if col == 'Match Info':
                self.results_tree.column(col, width=250, anchor=tk.CENTER)  # Wider column
            else:
                self.results_tree.column(col, width=120, anchor=tk.CENTER)
        
        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)
        
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double-click event
        self.results_tree.bind('<Double-1>', self.on_result_double_click)

    def setup_results_tab(self):
        """Setup the detailed results tab"""
        results_frame = ttk.Frame(self.notebook)
        self.notebook.add(results_frame, text="Detailed Results")
        
        # Results text area with scrollbar
        text_frame = ttk.Frame(results_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.results_text = tk.Text(text_frame, wrap=tk.WORD, font=('Consolas', 10))
        results_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=results_scrollbar.set)
        
        self.results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        results_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def setup_settings_tab(self):
        """Setup the settings tab"""
        settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(settings_frame, text="Settings")
        
        # Detection settings
        detection_frame = ttk.LabelFrame(settings_frame, text="Detection Settings", padding=10)
        detection_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Confidence threshold
        ttk.Label(detection_frame, text="Detection Confidence Threshold:").pack(anchor=tk.W)
        self.confidence_var = tk.DoubleVar(value=self.settings['detection_confidence'])
        confidence_scale = ttk.Scale(detection_frame, from_=0.1, to=0.9, 
                                   variable=self.confidence_var, orient=tk.HORIZONTAL)
        confidence_scale.pack(fill=tk.X, pady=2)
        
        # Checkboxes for features
        self.tracking_var = tk.BooleanVar(value=self.settings['tracking_enabled'])
        ttk.Checkbutton(detection_frame, text="Enable Vehicle Tracking", 
                       variable=self.tracking_var).pack(anchor=tk.W)
        
        self.interpolation_var = tk.BooleanVar(value=self.settings['interpolation_enabled'])
        ttk.Checkbutton(detection_frame, text="Enable Data Interpolation", 
                       variable=self.interpolation_var).pack(anchor=tk.W)
        
        self.screenshots_var = tk.BooleanVar(value=self.settings['save_screenshots'])
        ttk.Checkbutton(detection_frame, text="Save Detection Screenshots", 
                       variable=self.screenshots_var).pack(anchor=tk.W)
        
        # Output settings
        output_frame = ttk.LabelFrame(settings_frame, text="Output Settings", padding=10)
        output_frame.pack(fill=tk.X, padx=5, pady=5)
        
        dir_frame = ttk.Frame(output_frame)
        dir_frame.pack(fill=tk.X)
        
        ttk.Label(dir_frame, text="Output Directory:").pack(side=tk.LEFT)
        self.output_dir_var = tk.StringVar(value=self.settings['output_directory'])
        ttk.Entry(dir_frame, textvariable=self.output_dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(dir_frame, text="Browse", command=self.browse_output_dir).pack(side=tk.RIGHT)
        
        # Save settings button
        ttk.Button(output_frame, text="Save Settings", 
                  command=self.save_settings).pack(pady=10)
        ttk.Button(detection_frame, text="Fast Mode",
           command=lambda: self.apply_processing_mode('fast')).pack(pady=5)

        ttk.Button(detection_frame, text="Accurate Mode",
           command=lambda: self.apply_processing_mode('accurate')).pack(pady=5)


    def setup_status_bar(self, parent):
        """Setup the status bar"""
        status_frame = tk.Frame(parent, bg='#34495e', height=30)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(status_frame, text="Ready", bg='#34495e', fg='white', 
                                    font=('Arial', 10))
        self.status_label.pack(side=tk.LEFT, padx=10, pady=5)

        style = ttk.Style()
        style.theme_use('clam')  # Use 'clam' theme for color customization
        style.configure("Custom.Horizontal.TProgressbar",
                       troughcolor='#34495e',  # Background color
                       bordercolor='#2c3e50',   # Border color
                       background="#000000",    # Progress bar color (BLUE)
                       lightcolor='#5dade2',    # Highlight color
                       darkcolor='#2874a6') 
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(status_frame, style="Custom.Horizontal.TProgressbar", variable=self.progress_var, mode='determinate')
        self.progress_bar.pack(side=tk.RIGHT, padx=10, pady=5, fill=tk.X, expand=True)

    def log_message(self, message):
        """Log message to results tab and status - FIXED for threading"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        # Schedule GUI updates on the main thread using after()
        if hasattr(self, 'results_text'):
            self.root.after(0, lambda: self._update_results_text(log_entry))
        
        if hasattr(self, 'status_label'):
            status_text = message[:50] + "..." if len(message) > 50 else message
            self.root.after(0, lambda: self.status_label.configure(text=status_text))
        
        print(log_entry.strip())

    def _update_results_text(self, log_entry):
        """Helper method to update results text on main thread"""
        self.results_text.insert(tk.END, log_entry)
        self.results_text.see(tk.END)

    def select_video_file(self):
        """Select video file for processing"""
        file_path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv"), ("All files", "*.*")]
        )
        if file_path:
            self.video_source = file_path
            self.log_message(f"Selected video: {os.path.basename(file_path)}")

    def use_webcam(self):
        """Use webcam for live processing"""
        self.video_source = 0
        self.log_message("Set to use webcam")

    def start_processing(self):
        """Start video processing"""
        if not self.video_source:
            messagebox.showerror("Error", "Please select a video source first")
            return
        
        if not YOLO_AVAILABLE or not self.coco_model or not self.license_plate_detector:
            messagebox.showerror("Error", "Required models are not available. Please check YOLO installation.")
            return
        
        self.is_processing = True
        self.results = {}
        
        # Clear previous results
        self.processed_data.clear()
        self.interpolated_data.clear()
        
        # Start processing in separate thread
        self.processing_thread = threading.Thread(target=self.processing_loop, daemon=True)
        self.processing_thread.start()
        
        self.log_message("Started video processing...")

    def stop_processing(self):
        """Stop video processing"""
        self.is_processing = False
        if self.cap:
            self.cap.release()
        self.log_message("Processing stopped")

    def processing_loop(self):
        """Enhanced video processing with all improvements"""

        if self.cap is None:
            self.cap = cv2.VideoCapture(self.video_source)

            if not self.cap.isOpened():
                messagebox.showerror("Error", "Cannot open video source!")
                return

        frame_count = 0
        start_time = time.time()

        # Get video properties
        video_fps = self.cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        total_seconds = total_frames / video_fps if video_fps > 0 else 0

        while self.is_processing:
            # Set position BEFORE reading
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_count)
            
            ret, frame = self.cap.read()

            if not ret:
                break
            
            # CALL YOUR MAIN PROCESSING METHOD
            self.process_frame(frame, frame_count)

            # Display updated frame
            self.root.after(0, lambda f=frame.copy(): self.update_video_display(f))

            # Update statistics
            self.root.after(0, lambda fc=frame_count: 
                            self.update_statistics(fc, start_time))

            # Update progress
            self.root.after(0, lambda fc=frame_count: 
                            self.update_progress(fc))

            # Refresh DB alerts occasionally
            if frame_count % 300 == 0:  # Changed from 30 to 300 for better performance
                self.root.after(0, self.refresh_alerts)
                self.root.after(0, self.update_db_statistics)

            frame_count += 20  # Increment AFTER processing

        self.cap.release()


    def process_frame(self, frame, frame_nmr):
        """Process a single frame - ENHANCED VERSION"""
        try:
            self.results[frame_nmr] = {}
            
            # ENHANCEMENT: Improve frame quality
            enhanced = cv2.detailEnhance(frame, sigma_s=10, sigma_r=0.15)
            
            # Detect vehicles
            detections = self.coco_model(frame, conf=0.15)[0]
            detections_ = []
            
            for detection in detections.boxes.data.tolist():
                x1, y1, x2, y2, score, class_id = detection
                if int(class_id) in self.vehicles:
                    detections_.append([x1, y1, x2, y2, score])

            # ADD HERE - Draw vehicle bounding boxes
            for detection in detections_:
                x1, y1, x2, y2, score = detection
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                cv2.putText(frame, f'Vehicle {score:.2f}', (int(x1), int(y1)-10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Track vehicles if enabled
            if self.tracking_var.get() and self.mot_tracker and detections_:
                track_ids = self.mot_tracker.update(np.asarray(detections_))
            else:
                track_ids = [[*det, i] for i, det in enumerate(detections_)]
            
            # ENHANCEMENT: Better license plate detection with multiple thresholds
            if self.license_plate_detector:
                plates = self.license_plate_detector(enhanced, conf=0.20)[0]
                all_plates = plates.boxes.data.tolist()

                # Remove duplicates
                all_plates = self.remove_duplicate_detections(all_plates)

                for license_plate in all_plates:
                    x1, y1, x2, y2, score, class_id = license_plate
                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 2)
                    cv2.putText(frame, f'Plate {score:.2f}', (int(x1), int(y1)-10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                
                for license_plate in all_plates:
                    x1, y1, x2, y2, score, class_id = license_plate
                    
                    # Assign to car
                    car_match = self.get_car(license_plate, track_ids)
                    if car_match:
                        xcar1, ycar1, xcar2, ycar2, car_id = car_match
                        
                        # ENHANCEMENT: Better OCR
                        license_text, text_score = self.read_license_plate_improved(
                            frame, x1, y1, x2, y2
                        )

                        if license_text:
                            formatted_text, format_confidence = self.format_license_plate(license_text)
                            if formatted_text:
                                license_text = formatted_text
                                text_score = (text_score + format_confidence) / 2  # Average confidence
                            

                        
                        if license_text and len(license_text) >= 3:
                            self.results[frame_nmr][car_id] = {
                                'car': {'bbox': [xcar1, ycar1, xcar2, ycar2]},
                                'license_plate': {
                                    'bbox': [x1, y1, x2, y2],
                                    'text': license_text,
                                    'bbox_score': score,
                                    'text_score': text_score
                                }
                            }
                            
                            # Save to processed data for search
                            self.processed_data.append({
                                'frame_nmr': frame_nmr,
                                'car_id': car_id,
                                'car_bbox': f"[{xcar1} {ycar1} {xcar2} {ycar2}]",
                                'license_plate_bbox': f"[{x1} {y1} {x2} {y2}]",
                                'license_plate_bbox_score': score,
                                'license_number': license_text,
                                'license_number_score': text_score
                            })

                            # Save to database if connected
                            if self.db and license_text and license_text != '0':
                                try:
                                    vehicle_data = format_vehicle_data_from_detection(
                                        license_number=license_text,
                                        car_id=int(car_id),
                                        frame_number=int(frame_nmr),
                                        confidence_score=float(text_score) if text_score else 0,
                                        video_source=self.video_source if hasattr(self, 'video_source') else None
                                    )
                                    self.db.add_detected_vehicle(vehicle_data)
                                except Exception as db_error:
                                    print(f"Database save error: {db_error}")
        
        except Exception as e:
            self.log_message(f"Error processing frame {frame_nmr}: {str(e)}")

    def get_car(self, license_plate, vehicle_track_ids):
        """Get car that contains the license plate"""
        x1, y1, x2, y2, score, class_id = license_plate
        
        # Calculate center of license plate
        plate_center_x = (x1 + x2) / 2
        plate_center_y = (y1 + y2) / 2
        
        best_match = None
        min_distance = float('inf')
        
        for track in vehicle_track_ids:
            if len(track) >= 5:
                xcar1, ycar1, xcar2, ycar2, car_id = track[:5]
                
                # Strategy 1: Check if plate is inside car (original method)
                if x1 > xcar1 and y1 > ycar1 and x2 < xcar2 and y2 < ycar2:
                    return [xcar1, ycar1, xcar2, ycar2, car_id]
                
                # Strategy 2: Check if plate is NEAR the car (NEW - more flexible)
                # Calculate center of car
                car_center_x = (xcar1 + xcar2) / 2
                car_center_y = (ycar1 + ycar2) / 2
                
                # Calculate distance between plate and car centers
                distance = ((plate_center_x - car_center_x) ** 2 + 
                        (plate_center_y - car_center_y) ** 2) ** 0.5
                
                # Check if plate is in the general vicinity of the car
                # (within 1.5x the car's height)
                car_height = ycar2 - ycar1
                max_distance = car_height * 1.5
                
                if distance < max_distance and distance < min_distance:
                    # Also check vertical alignment (plate should be near bottom-middle of car)
                    if y1 > ycar1 and y2 < ycar2 + car_height * 0.5:  # Allow plate below car
                        min_distance = distance
                        best_match = [xcar1, ycar1, xcar2, ycar2, car_id]
        
        return best_match

    def read_license_plate_improved(self, frame, x1, y1, x2, y2):
        """Read license plate text using OCR - ENHANCED VERSION"""
        if not self.ocr_reader:
            return None, 0
        
        try:
            # Add padding for better crop
            h, w = frame.shape[:2]
            padding = 15
            x1 = max(0, int(x1) - padding)
            y1 = max(0, int(y1) - padding)
            x2 = min(w, int(x2) + padding)
            y2 = min(h, int(y2) + padding)
            
            crop = frame[y1:y2, x1:x2]
            if crop.size == 0:
                return None, 0
            
            # Upscale for better OCR
            scale = 3
            crop = cv2.resize(crop, (crop.shape[1]*scale, crop.shape[0]*scale), 
                            interpolation=cv2.INTER_CUBIC)
            
            # Try multiple preprocessing methods
            all_results = []
            
            # Method 1: Grayscale + Otsu threshold
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            _, thresh1 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Method 2: CLAHE + threshold
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            _, thresh2 = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Method 3: Adaptive threshold
            adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                            cv2.THRESH_BINARY, 11, 2)
            
            # Method 4: Inverted threshold (for dark plates)
            _, inv_thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # Try OCR on each version
            for img in [thresh1, thresh2, adaptive, inv_thresh]:
                try:
                    results = self.ocr_reader.readtext(img, detail=1)
                    all_results.extend(results)
                except:
                    continue
            
            if not all_results:
                return None, 0
            
            # Get best result by confidence
            best = max(all_results, key=lambda x: x[2])
            text = best[1].upper().replace(' ', '').replace('-', '')
            conf = best[2]
            
            # Clean text - keep only alphanumeric
            text = ''.join(c for c in text if c.isalnum())
            
            # Validate
            if len(text) >= 3 and conf > 0.3:
                return text, conf
            
            return None, 0
            
        except Exception as e:
            self.log_message(f"OCR error: {str(e)}")
            return None, 0
        

    def format_license_plate(self, raw_text):
        """
        Intelligent Indian plate formatter.
        No rejection. No X padding.
        Uses real state codes and digit corrections.
        """

        if not raw_text:
            raw_text = ""

        clean = ''.join(c for c in raw_text.upper() if c.isalnum())

        # Valid Indian state codes
        valid_states = ['KA','AP','AS','BR','CG','GA','GJ','HR','HP','JH',
                        'AR','KL','MP','MH','MN','ML','MZ','NL','OD','PB',
                        'RJ','SK','TN','TS','TR','UP','UK','WB','DL','AN',
                        'CH','DD','LD','PY']

        # Common OCR corrections for digits
        digit_map = {
            'O': '0',
            'Q': '0',
            'I': '1',
            'L': '1',
            'Z': '2',
            'S': '5',
            'B': '8',
            'G': '6'
        }

        # --- 1️⃣ Extract state ---
        ocr_state = clean[:2] if len(clean) >= 2 else ""
        if ocr_state in valid_states:
            state = ocr_state
        else:
            state = None

            if len(ocr_state) >= 1:
                first_letter = ocr_state[0]
                possible = [s for s in valid_states if s[0] == first_letter]

                if possible:
                    if len(ocr_state) >= 2:
                        second_letter = ocr_state[1]
                        for s in possible:
                            if s[1] == second_letter:
                                state = s
                                break

                    if not state:
                        state = possible[0]

            if not state:
                state = valid_states[0]   # very last fallback (rare case)


        remaining = clean[2:]

        # --- 2️⃣ Extract digits and letters ---
        letters = ''.join(c for c in remaining if c.isalpha())
        digits = ''.join(digit_map.get(c, c) for c in remaining if c.isdigit() or c in digit_map)

        # --- 3️⃣ RTO (2 digits) ---
        rto = digits[:2] if len(digits) >= 2 else digits.zfill(2)

        # --- 4️⃣ Series (2 letters) ---
        series = letters[:2]
        if len(series) < 2:
            # If missing, reuse last two letters from state (safe meaningful fallback)
            series = (series + state)[0:2]

        # --- 5️⃣ Number (last 4 digits) ---
        number = digits[2:6]
        number = ''.join(digit_map.get(c, c) for c in number)

        if len(number) < 4:
            number = number.zfill(4)

        formatted = f"{state}{rto}{series}{number}"

        return formatted, 0.9


    def remove_duplicate_detections(self, detections, iou_threshold=0.5):
        """Remove duplicate detections using IoU"""
        if not detections:
            return []
        
        # Sort by confidence
        detections = sorted(detections, key=lambda x: x[4], reverse=True)
        
        keep = []
        for det in detections:
            x1, y1, x2, y2 = det[:4]
            
            # Check if overlaps with any kept detection
            is_duplicate = False
            for kept_det in keep:
                kx1, ky1, kx2, ky2 = kept_det[:4]
                
                # Calculate IoU
                xi1 = max(x1, kx1)
                yi1 = max(y1, ky1)
                xi2 = min(x2, kx2)
                yi2 = min(y2, ky2)
                
                inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
                box1_area = (x2 - x1) * (y2 - y1)
                box2_area = (kx2 - kx1) * (ky2 - ky1)
                union_area = box1_area + box2_area - inter_area
                
                iou = inter_area / union_area if union_area > 0 else 0
                
                if iou > iou_threshold:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                keep.append(det)
        
        return keep


    def update_video_display(self, frame):
        """Update the video display"""
        try:
            # Resize frame for display
            display_frame = cv2.resize(frame, (640, 480))
            
            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            
            # Convert to PIL and then to PhotoImage
            pil_image = Image.fromarray(rgb_frame)
            photo = ImageTk.PhotoImage(pil_image)
            
            # Update label
            self.video_label.configure(image=photo)
            self.video_label.image = photo
            
        except Exception as e:
            pass  # Ignore display errors

    def update_progress(self, frame_count):
        """Update progress bar based on video progress"""
        if self.cap:
            total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if total_frames > 0:
                progress = (frame_count / total_frames) * 100
                self.progress_var.set(progress)


    def update_statistics(self, frame_nmr, start_time):
        """Update processing statistics"""
        try:
            elapsed = time.time() - start_time
            fps = frame_nmr / elapsed if elapsed > 0 else 0
            
            plates_count = sum(len(frame_data) for frame_data in self.results.values())
            unique_plates = len(set(item['license_number'] for item in self.processed_data))
            
            # Calculate video time
            if self.cap:
                video_fps = self.cap.get(cv2.CAP_PROP_FPS)
                total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
                
                # Current video time in seconds
                current_seconds = frame_nmr / video_fps if video_fps > 0 else 0
                total_seconds = total_frames / video_fps if video_fps > 0 else 0
                
                # Format time as MM:SS
                current_time = f"{int(current_seconds//60)}:{int(current_seconds%60):02d}"
                total_time = f"{int(total_seconds//60)}:{int(total_seconds%60):02d}"
                
                self.stats_labels['video_time'].configure(text=f"Time: {current_time} / {total_time}")
            
            self.stats_labels['frames_processed'].configure(text=f"Frames: {frame_nmr}")
            self.stats_labels['plates_detected'].configure(text=f"Plates: {plates_count}")
            self.stats_labels['unique_plates'].configure(text=f"Unique: {unique_plates}")
            self.stats_labels['processing_fps'].configure(text=f"FPS: {fps:.1f}")
            
        except Exception as e:
            pass

    def interpolate_data(self):
        """Interpolate missing data between frames"""
        if not self.processed_data:
            messagebox.showwarning("Warning", "No data to interpolate. Process a video first.")
            return
        
        if not SCIPY_AVAILABLE:
            messagebox.showerror("Error", "SciPy is required for interpolation but not available.")
            return
        
        self.log_message("Starting data interpolation...")
        
        try:
            # Convert to the format expected by interpolation function
            data_for_interp = []
            for item in self.processed_data:
                data_for_interp.append({
                    'frame_nmr': str(item['frame_nmr']),
                    'car_id': str(item['car_id']),
                    'car_bbox': item['car_bbox'],
                    'license_plate_bbox': item['license_plate_bbox'],
                    'license_plate_bbox_score': str(item['license_plate_bbox_score']),
                    'license_number': item['license_number'],
                    'license_number_score': str(item['license_number_score'])
                })
            
            # Perform interpolation
            self.interpolated_data = self.interpolate_bounding_boxes(data_for_interp)
            self.log_message(f"Interpolation completed. {len(self.interpolated_data)} records generated.")
            
        except Exception as e:
            self.log_message(f"Interpolation error: {str(e)}")
            messagebox.showerror("Error", f"Interpolation failed: {str(e)}")

    def interpolate_bounding_boxes(self, data):
        """Interpolate bounding boxes for missing frames"""
        from scipy.interpolate import interp1d
        
        # Extract data
        frame_numbers = np.array([int(row['frame_nmr']) for row in data])
        car_ids = np.array([int(float(row['car_id'])) for row in data])
        car_bboxes = np.array([list(map(float, row['car_bbox'][1:-1].split())) for row in data])
        license_plate_bboxes = np.array([list(map(float, row['license_plate_bbox'][1:-1].split())) for row in data])
        
        interpolated_data = []
        unique_car_ids = np.unique(car_ids)
        
        for car_id in unique_car_ids:
            # Filter data for specific car
            car_mask = car_ids == car_id
            car_frame_numbers = frame_numbers[car_mask]
            car_bboxes_filtered = car_bboxes[car_mask]
            license_plate_bboxes_filtered = license_plate_bboxes[car_mask]
            
            if len(car_frame_numbers) < 2:
                # Not enough data for interpolation
                continue
            
            # Create interpolation functions
            first_frame = car_frame_numbers[0]
            last_frame = car_frame_numbers[-1]
            
            # Interpolate for all frames between first and last
            all_frames = np.arange(first_frame, last_frame + 1)
            
            # Car bbox interpolation
            car_interp = interp1d(car_frame_numbers, car_bboxes_filtered, 
                                axis=0, kind='linear', bounds_error=False, fill_value='extrapolate')
            car_bboxes_interp = car_interp(all_frames)
            
            # License plate bbox interpolation
            lp_interp = interp1d(car_frame_numbers, license_plate_bboxes_filtered, 
                               axis=0, kind='linear', bounds_error=False, fill_value='extrapolate')
            lp_bboxes_interp = lp_interp(all_frames)
            
            # Create interpolated records
            for i, frame_num in enumerate(all_frames):
                row = {
                    'frame_nmr': str(frame_num),
                    'car_id': str(car_id),
                    'car_bbox': ' '.join(map(str, car_bboxes_interp[i])),
                    'license_plate_bbox': ' '.join(map(str, lp_bboxes_interp[i]))
                }
                
                # Check if this is original data or interpolated
                if frame_num in car_frame_numbers:
                    # Original data - find the original record
                    orig_idx = np.where(car_frame_numbers == frame_num)[0][0]
                    orig_record = [d for d in data if int(d['frame_nmr']) == frame_num and int(float(d['car_id'])) == car_id][0]
                    row['license_plate_bbox_score'] = orig_record['license_plate_bbox_score']
                    row['license_number'] = orig_record['license_number']
                    row['license_number_score'] = orig_record['license_number_score']
                else:
                    # Interpolated data
                    row['license_plate_bbox_score'] = '0'
                    row['license_number'] = '0'
                    row['license_number_score'] = '0'
                
                interpolated_data.append(row)
        
        return interpolated_data

    def export_csv(self):
        """Export processed data to CSV"""
        if not self.processed_data and not self.interpolated_data:
            messagebox.showwarning("Warning", "No data to export. Process a video first.")
            return
        
        try:
            # Create output directory if it doesn't exist
            output_dir = self.output_dir_var.get()
            os.makedirs(output_dir, exist_ok=True)
            
            # Export original data
            if self.processed_data:
                original_path = os.path.join(output_dir, 'license_plates.csv')
                self.write_csv_data(self.processed_data, original_path)
                self.log_message(f"Original data exported to: {original_path}")
            
            # Export interpolated data if available
            if self.interpolated_data:
                interp_path = os.path.join(output_dir, 'license_plates_interpolated.csv')
                self.write_csv_data(self.interpolated_data, interp_path)
                self.log_message(f"Interpolated data exported to: {interp_path}")
            
            messagebox.showinfo("Success", "Data exported successfully!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {str(e)}")

    def export_to_csv(self):
        """Auto-export after processing"""
        self.export_csv()

    def write_csv_data(self, data, filepath):
        """Write data to CSV file"""
        if not data:
            return
        
        headers = ['frame_nmr', 'car_id', 'car_bbox', 'license_plate_bbox', 
                  'license_plate_bbox_score', 'license_number', 'license_number_score']
        
        with open(filepath, 'w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()
            
            for item in data:
                # Convert format if needed
                if isinstance(item, dict):
                    if 'car_bbox' in item and not item['car_bbox'].startswith('['):
                        # Convert list format to string format
                        row = {
                            'frame_nmr': str(item.get('frame_nmr', '')),
                            'car_id': str(item.get('car_id', '')),
                            'car_bbox': item.get('car_bbox', ''),
                            'license_plate_bbox': item.get('license_plate_bbox', ''),
                            'license_plate_bbox_score': str(item.get('license_plate_bbox_score', 0)),
                            'license_number': str(item.get('license_number', '')),
                            'license_number_score': str(item.get('license_number_score', 0))
                        }
                    else:
                        row = item
                    writer.writerow(row)

    def create_visualization(self):
        """Create visualization video with annotations"""
        if not self.video_source or self.video_source == 0:
            messagebox.showwarning("Warning", "Visualization requires a video file, not webcam.")
            return
        
        if not self.processed_data:
            messagebox.showwarning("Warning", "No data to visualize. Process a video first.")
            return
        
        self.log_message("Creating visualization video...")
        
        try:
            # Use interpolated data if available, otherwise use original
            data_to_use = self.interpolated_data if self.interpolated_data else self.processed_data
            
            # Create visualization in separate thread
            vis_thread = threading.Thread(target=self.create_visualization_video, 
                                        args=(data_to_use,), daemon=True)
            vis_thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Visualization failed: {str(e)}")

    def create_visualization_video(self, data):
        """Create the actual visualization video"""
        try:
            cap = cv2.VideoCapture(self.video_source)
            if not cap.isOpened():
                self.log_message("Error: Cannot open video file for visualization")
                return
            
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Create output video writer
            output_path = os.path.join(self.output_dir_var.get(), 'visualization.mp4')
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            
            # Convert data to pandas DataFrame for easier processing
            df = pd.DataFrame(data)
            
            # Get best license plate crop for each car
            license_plates = {}
            for car_id in df['car_id'].unique():
                car_data = df[df['car_id'] == car_id]
                # Find frame with highest confidence
                if 'license_number_score' in car_data.columns:
                    valid_scores = car_data[car_data['license_number_score'] != '0']
                    if not valid_scores.empty:
                        best_row = valid_scores.loc[valid_scores['license_number_score'].astype(float).idxmax()]
                        license_plates[car_id] = {
                            'text': best_row['license_number'],
                            'frame': int(best_row['frame_nmr'])
                        }
            
            frame_nmr = 0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Update progress - schedule on main thread
                progress = (frame_nmr / total_frames) * 100
                self.root.after(0, lambda p=progress: self.progress_var.set(p))
                
                # Get detections for current frame
                frame_data = df[df['frame_nmr'] == str(frame_nmr)]
                
                for _, row in frame_data.iterrows():
                    try:
                        # Parse bounding boxes
                        car_bbox = self.parse_bbox_string(row['car_bbox'])
                        lp_bbox = self.parse_bbox_string(row['license_plate_bbox'])
                        
                        if car_bbox and lp_bbox:
                            # Draw car bounding box
                            self.draw_border(frame, 
                                           (int(car_bbox[0]), int(car_bbox[1])), 
                                           (int(car_bbox[2]), int(car_bbox[3])), 
                                           (0, 255, 0), 25)
                            
                            # Draw license plate bounding box
                            cv2.rectangle(frame, 
                                        (int(lp_bbox[0]), int(lp_bbox[1])), 
                                        (int(lp_bbox[2]), int(lp_bbox[3])), 
                                        (0, 0, 255), 12)
                            
                            # Add license plate text if available
                            car_id = row['car_id']
                            if car_id in license_plates and row['license_number'] != '0':
                                text = row['license_number']
                                
                                # Calculate text position
                                text_x = int((car_bbox[0] + car_bbox[2]) / 2)
                                text_y = int(car_bbox[1]) - 50
                                
                                # Create background for text
                                (text_width, text_height), _ = cv2.getTextSize(
                                    text, cv2.FONT_HERSHEY_SIMPLEX, 2, 3)
                                
                                cv2.rectangle(frame, 
                                            (text_x - text_width//2 - 10, text_y - text_height - 10),
                                            (text_x + text_width//2 + 10, text_y + 10),
                                            (255, 255, 255), -1)
                                
                                # Add text
                                cv2.putText(frame, text,
                                          (text_x - text_width//2, text_y),
                                          cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
                    
                    except Exception as e:
                        continue  # Skip problematic annotations
                
                out.write(frame)
                frame_nmr += 1
                
                # Update status periodically - schedule on main thread
                if frame_nmr % 30 == 0:
                    self.root.after(0, lambda fn=frame_nmr, tf=total_frames: 
                                   self.log_message(f"Processing visualization frame {fn}/{tf}"))
            
            cap.release()
            out.release()
            
            self.log_message(f"Visualization completed: {output_path}")
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Visualization video created: {output_path}"))
            
        except Exception as e:
            self.log_message(f"Visualization error: {str(e)}")

    def parse_bbox_string(self, bbox_str):
        """Parse bounding box string to coordinates"""
        try:
            if isinstance(bbox_str, str):
                # Remove brackets and split
                clean_str = bbox_str.strip('[]')
                coords = [float(x.strip()) for x in clean_str.split()]
                return coords if len(coords) == 4 else None
            return None
        except:
            return None

    def draw_border(self, img, top_left, bottom_right, color=(0, 255, 0), thickness=10, line_length_x=200, line_length_y=200):
        """Draw decorative border around detection"""
        x1, y1 = top_left
        x2, y2 = bottom_right

        cv2.line(img, (x1, y1), (x1, y1 + line_length_y), color, thickness)
        cv2.line(img, (x1, y1), (x1 + line_length_x, y1), color, thickness)
        cv2.line(img, (x1, y2), (x1, y2 - line_length_y), color, thickness)
        cv2.line(img, (x1, y2), (x1 + line_length_x, y2), color, thickness)
        cv2.line(img, (x2, y1), (x2 - line_length_x, y1), color, thickness)
        cv2.line(img, (x2, y1), (x2, y1 + line_length_y), color, thickness)
        cv2.line(img, (x2, y2), (x2, y2 - line_length_y), color, thickness)
        cv2.line(img, (x2, y2), (x2 - line_length_x, y2), color, thickness)

    def search_license_plate(self):
        """Search for license plates with fuzzy matching"""
        target_plate = self.search_entry.get().strip().upper()
        
        if not target_plate:
            messagebox.showwarning("Warning", "Please enter a license plate number")
            return
        
        if not self.processed_data:
            messagebox.showwarning("Warning", "No data available. Process a video first.")
            return
        
        # Clear previous results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        self.log_message(f"Searching for: {target_plate}")
        
        # Get similarity threshold
        similarity_threshold = self.similarity_var.get()
        min_matching_chars = 6  # Minimum matching characters
        
        matches = []
        
        for item in self.processed_data:
            detected_plate = item['license_number'].upper()
            
            # METHOD 1: Character matching count
            matching_chars = sum(1 for a, b in zip(target_plate, detected_plate) if a == b)
            max_len = max(len(target_plate), len(detected_plate))
            char_match_ratio = matching_chars / max_len if max_len > 0 else 0
            
            # METHOD 2: Sequence similarity (your existing method)
            from difflib import SequenceMatcher
            sequence_similarity = SequenceMatcher(None, target_plate, detected_plate).ratio()
            
            # METHOD 3: Check if at least 6 characters match
            chars_match = matching_chars >= min_matching_chars
            
            # Accept if EITHER:
            # - At least 6 characters match, OR
            # - Similarity is above threshold
            if chars_match or sequence_similarity >= similarity_threshold:
                matches.append({
                    'plate': detected_plate,
                    'frame': item['frame_nmr'],
                    'car_id': item['car_id'],
                    'confidence': item['license_number_score'],
                    'similarity': sequence_similarity,
                    'matching_chars': matching_chars
                })
        
        # Group by plate number
        plate_groups = {}
        for match in matches:
            plate = match['plate']
            if plate not in plate_groups:
                plate_groups[plate] = {
                    'frames': [],
                    'car_ids': set(),
                    'confidences': [],
                    'similarity': match['similarity'],
                    'matching_chars': match['matching_chars']
                }
            
            plate_groups[plate]['frames'].append(match['frame'])
            plate_groups[plate]['car_ids'].add(match['car_id'])
            plate_groups[plate]['confidences'].append(match['confidence'])
        
        # Sort by matching characters first, then similarity
        sorted_plates = sorted(
            plate_groups.items(),
            key=lambda x: (x[1]['matching_chars'], x[1]['similarity']),
            reverse=True
        )
        
        # Display results
        if sorted_plates:
            self.log_message(f"Found {len(sorted_plates)} matching plates")
            
            for plate, data in sorted_plates:
                frames = data['frames']
                car_ids = list(data['car_ids'])
                avg_conf = sum(data['confidences']) / len(data['confidences'])
                similarity = data['similarity']
                matching_chars = data['matching_chars']
                
                # Insert with color coding based on match quality
                if matching_chars >= 8:
                    tag = 'excellent'  # Green
                elif matching_chars >= 6:
                    tag = 'good'  # Yellow
                else:
                    tag = 'partial'  # Orange
                
                self.results_tree.insert('', 'end', values=(
                    plate,
                    len(frames),
                    ', '.join(map(str, car_ids)) if car_ids else '-',
                    min(frames),
                    max(frames),
                    f"{avg_conf:.2f} ({matching_chars}/{len(target_plate)} chars, {similarity*100:.0f}%)"
                ), tags=(tag,))
            
            # Configure tags for color coding
            self.results_tree.tag_configure('excellent', background='#90EE90')  # Light green
            self.results_tree.tag_configure('good', background='#FFFFE0')  # Light yellow
            self.results_tree.tag_configure('partial', background='#FFE4B5')  # Light orange
            
        else:
            self.log_message(f"No matches found for: {target_plate}")
            messagebox.showinfo("Search Results", f"No matches found for {target_plate}")
        
        # Store search results
        self.search_results = {
            'target': target_plate,
            'matches': plate_groups
        }

    def calculate_similarity(self, a, b):
        """Calculate similarity between two strings"""
        return SequenceMatcher(None, a, b).ratio()

    def show_all_plates(self):
        """Show all detected license plates"""
        data_to_show = self.interpolated_data if self.interpolated_data else self.processed_data
        
        if not data_to_show:
            messagebox.showwarning("Warning", "No data available. Process a video first.")
            return
        
        # Clear previous results
        self.results_tree.delete(*self.results_tree.get_children())
        
        # Convert to DataFrame
        df = pd.DataFrame(data_to_show)
        
        # Get unique license plates (excluding '0')
        unique_plates = df[df['license_number'] != '0']['license_number'].unique()
        
        self.log_message(f"Displaying {len(unique_plates)} unique license plates")
        
        for plate in unique_plates:
            plate_data = df[df['license_number'] == plate]

            first_frame = plate_data['frame_nmr'].astype(int).min()
            last_frame = plate_data['frame_nmr'].astype(int).max()
            frame_count = len(plate_data)

            scores = plate_data['license_number_score']
            valid_scores = scores[scores != '0'].astype(float)
            avg_confidence = valid_scores.mean() if not valid_scores.empty else 0

            self.results_tree.insert('', 'end', values=(
                plate,
                frame_count,
                "—",   # remove car_id column or keep single representative
                first_frame,
                last_frame,
                f"{avg_confidence:.2f}"
            ))


    def on_result_double_click(self, event):
        """Handle double-click on search results"""
        selection = self.results_tree.selection()
        if not selection:
            return
        
        item = self.results_tree.item(selection[0])
        values = item['values']
        
        if len(values) >= 6:
            plate = values[0]
            car_id = values[2]
            first_frame = values[3]
            
            # Show detailed information
            detail_msg = f"License Plate: {plate}\n"
            detail_msg += f"Car ID: {car_id}\n"
            detail_msg += f"First Frame: {first_frame}\n"
            detail_msg += f"Last Frame: {values[4]}\n"
            detail_msg += f"Total Frames: {values[1]}\n"
            detail_msg += f"Average Confidence: {values[5]}"
            
            messagebox.showinfo("Plate Details", detail_msg)

    def browse_output_dir(self):
        """Browse for output directory"""
        directory = filedialog.askdirectory(title="Select Output Directory")
        if directory:
            self.output_dir_var.set(directory)

    def save_settings(self):
        """Save current settings"""
        self.settings.update({
            'detection_confidence': self.confidence_var.get(),
            'tracking_enabled': self.tracking_var.get(),
            'interpolation_enabled': self.interpolation_var.get(),
            'save_screenshots': self.screenshots_var.get(),
            'output_directory': self.output_dir_var.get()
        })
        
        try:
            with open('lpr_settings.json', 'w') as f:
                json.dump(self.settings, f, indent=2)
            self.log_message("Settings saved successfully")
            messagebox.showinfo("Success", "Settings saved successfully!")
        except Exception as e:
            self.log_message(f"Error saving settings: {e}")
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def load_settings(self):
        """Load settings from file"""
        try:
            with open('lpr_settings.json', 'r') as f:
                loaded_settings = json.load(f)
                self.settings.update(loaded_settings)
        except FileNotFoundError:
            # Use default settings
            pass
        except Exception as e:
            print(f"Error loading settings: {e}")


    def setup_database_tab(self):
        """Setup the database management tab"""
        db_frame = ttk.Frame(self.notebook)
        self.notebook.add(db_frame, text="Database")
        
        # Create left and right panels
        left_panel = ttk.LabelFrame(db_frame, text="Stolen Vehicles Database", padding=10)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        right_panel = ttk.LabelFrame(db_frame, text="Alerts", padding=10)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Stolen Vehicles Section
        ttk.Label(left_panel, text="Add Stolen Vehicle:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=5)
        
        # Input fields
        input_frame = ttk.Frame(left_panel)
        input_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(input_frame, text="Vehicle Number:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.stolen_number_entry = ttk.Entry(input_frame, width=20)
        self.stolen_number_entry.grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(input_frame, text="Color:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.stolen_color_entry = ttk.Entry(input_frame, width=20)
        self.stolen_color_entry.grid(row=1, column=1, padx=5, pady=2)
        
        ttk.Label(input_frame, text="Model:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.stolen_model_entry = ttk.Entry(input_frame, width=20)
        self.stolen_model_entry.grid(row=2, column=1, padx=5, pady=2)
        
        ttk.Button(left_panel, text="Add to Stolen Database", 
                command=self.add_stolen_vehicle_gui).pack(pady=10)
        
        # Stolen vehicles list
        ttk.Label(left_panel, text="Registered Stolen Vehicles:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=5)
        
        stolen_tree_frame = ttk.Frame(left_panel)
        stolen_tree_frame.pack(fill=tk.BOTH, expand=True)
        
        stolen_scroll = ttk.Scrollbar(stolen_tree_frame)
        stolen_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.stolen_tree = ttk.Treeview(stolen_tree_frame, 
                                    columns=('Number', 'Color', 'Model', 'Status'),
                                    show='headings', 
                                    yscrollcommand=stolen_scroll.set)
        
        self.stolen_tree.heading('Number', text='Vehicle Number')
        self.stolen_tree.heading('Color', text='Color')
        self.stolen_tree.heading('Model', text='Model')
        self.stolen_tree.heading('Status', text='Status')
        
        self.stolen_tree.column('Number', width=120)
        self.stolen_tree.column('Color', width=80)
        self.stolen_tree.column('Model', width=100)
        self.stolen_tree.column('Status', width=80)
        
        self.stolen_tree.pack(fill=tk.BOTH, expand=True)
        stolen_scroll.config(command=self.stolen_tree.yview)
        
        ttk.Button(left_panel, text="Refresh Stolen Vehicles", 
                command=self.refresh_stolen_vehicles).pack(pady=5)
        
        # Alerts Section
        ttk.Label(right_panel, text="Match Alerts:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=5)
        
        # Alert filters
        filter_frame = ttk.Frame(right_panel)
        filter_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(filter_frame, text="Severity:").pack(side=tk.LEFT, padx=5)
        self.alert_severity_var = tk.StringVar(value='ALL')
        severity_combo = ttk.Combobox(filter_frame, textvariable=self.alert_severity_var, 
                                    values=['ALL', 'CRITICAL', 'HIGH', 'MEDIUM'], 
                                    state='readonly', width=15)
        severity_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(filter_frame, text="Refresh Alerts", 
                command=self.refresh_alerts).pack(side=tk.LEFT, padx=5)
        
        # Alerts tree
        alerts_tree_frame = ttk.Frame(right_panel)
        alerts_tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        alerts_scroll = ttk.Scrollbar(alerts_tree_frame)
        alerts_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.alerts_tree = ttk.Treeview(alerts_tree_frame,
                                    columns=('Severity', 'Detected', 'Stolen', 'Match%', 'Time'),
                                    show='headings',
                                    yscrollcommand=alerts_scroll.set)
        
        self.alerts_tree.heading('Severity', text='Severity')
        self.alerts_tree.heading('Detected', text='Detected #')
        self.alerts_tree.heading('Stolen', text='Stolen #')
        self.alerts_tree.heading('Match%', text='Match %')
        self.alerts_tree.heading('Time', text='Time')
        
        self.alerts_tree.column('Severity', width=80)
        self.alerts_tree.column('Detected', width=100)
        self.alerts_tree.column('Stolen', width=100)
        self.alerts_tree.column('Match%', width=70)
        self.alerts_tree.column('Time', width=150)
        
        # Color code by severity
        self.alerts_tree.tag_configure('CRITICAL', background='#ff4444', foreground='white')
        self.alerts_tree.tag_configure('HIGH', background='#ffaa44', foreground='white')
        self.alerts_tree.tag_configure('MEDIUM', background='#ffff44', foreground='black')
        
        self.alerts_tree.pack(fill=tk.BOTH, expand=True)
        alerts_scroll.config(command=self.alerts_tree.yview)
        
        # Statistics
        stats_frame = ttk.LabelFrame(right_panel, text="Database Statistics", padding=10)
        stats_frame.pack(fill=tk.X, pady=10)
        
        self.stats_label = tk.Label(stats_frame, text="Loading...", justify=tk.LEFT, 
                                    bg='white', font=('Arial', 9))
        self.stats_label.pack(fill=tk.X)
        
        # Initial refresh
        self.refresh_stolen_vehicles()
        self.refresh_alerts()
        self.update_db_statistics()

    def add_stolen_vehicle_gui(self):
        """Add stolen vehicle from GUI"""
        if not self.db:
            messagebox.showerror("Error", "Database not connected!")
            return
        
        number = self.stolen_number_entry.get().strip()
        color = self.stolen_color_entry.get().strip()
        model = self.stolen_model_entry.get().strip()
        
        if not number:
            messagebox.showwarning("Warning", "Vehicle number is required!")
            return
        
        vehicle_data = {
            'vehicle_number': number,
            'vehicle_color': color,
            'vehicle_model': model
        }
        
        vehicle_id = self.db.add_stolen_vehicle(vehicle_data)
        
        if vehicle_id:
            messagebox.showinfo("Success", f"Stolen vehicle {number} added to database!")
            # Clear entries
            self.stolen_number_entry.delete(0, tk.END)
            self.stolen_color_entry.delete(0, tk.END)
            self.stolen_model_entry.delete(0, tk.END)
            # Refresh list
            self.refresh_stolen_vehicles()
            self.log_message(f"Stolen vehicle added: {number}")
        else:
            messagebox.showerror("Error", "Failed to add stolen vehicle!")

    def refresh_stolen_vehicles(self):
        """Refresh the stolen vehicles list"""
        if not self.db:
            return
        
        # Clear tree
        for item in self.stolen_tree.get_children():
            self.stolen_tree.delete(item)
        
        # Fetch and display
        vehicles = self.db.get_all_stolen_vehicles(status='ACTIVE')
        
        for vehicle in vehicles:
            self.stolen_tree.insert('', 'end', values=(
                vehicle['vehicle_number'],
                vehicle.get('vehicle_color', 'N/A'),
                vehicle.get('vehicle_model', 'N/A'),
                vehicle['status']
            ))

    def refresh_alerts(self):
        """Refresh the alerts list"""
        if not self.db:
            return
        
        # Clear tree
        for item in self.alerts_tree.get_children():
            self.alerts_tree.delete(item)
        
        # Get severity filter
        severity = self.alert_severity_var.get()
        if severity == 'ALL':
            severity = None
        
        # Fetch alerts
        alerts = self.db.get_alerts(severity=severity, status='NEW', limit=100)
        
        for alert in alerts:
            # Format timestamp
            timestamp = str(alert.get('alert_timestamp', ''))
            if len(timestamp) > 19:
                timestamp = timestamp[:19]
            
            self.alerts_tree.insert('', 'end', 
                                values=(
                                    alert['severity_level'],
                                    alert['detected_number'],
                                    alert['stolen_number'],
                                    f"{alert['match_percentage']}%",
                                    timestamp
                                ),
                                tags=(alert['severity_level'],))

    def update_db_statistics(self):
        """Update database statistics"""
        if not self.db:
            self.stats_label.config(text="Database not connected")
            return
        
        stats = self.db.get_statistics()
        
        stats_text = f"""
    📊 Database Statistics:
    ━━━━━━━━━━━━━━━━━━━━━
    Total Detected: {stats['total_detected']}
    Active Stolen: {stats['total_stolen_active']}

    🚨 New Alerts:
    🔴 Critical: {stats['critical_alerts']}
    🟠 High: {stats['high_alerts']}
    🟡 Medium: {stats['medium_alerts']}
    
    Total Alerts: {stats['total_new_alerts']}
        """
        
        self.stats_label.config(text=stats_text)

    def run(self):
        """Run the application"""
        self.log_message("License Plate Recognition System Started")
        self.log_message("Select a video file to begin processing")
        
        # Check for required models
        if not YOLO_AVAILABLE:
            self.log_message("Warning: YOLO not available. Install with: pip install ultralytics")
        elif not os.path.exists('license_plate_detector.pt'):
            self.log_message("Warning: license_plate_detector.pt not found. Download from the project repository.")
        
        if not EASYOCR_AVAILABLE:
            self.log_message("Warning: EasyOCR not available. Install with: pip install easyocr")
        
        self.root.mainloop()


if __name__ == "__main__":
    print("Advanced License Plate Recognition System")
    print("=" * 50)
    
    required_packages = [
        'ultralytics', 'opencv-python', 'pandas', 'numpy', 
        'easyocr', 'scipy', 'Pillow', 'difflib'
    ]
    
    print("Required packages:", ', '.join(required_packages))
    print("Install with: pip install " + ' '.join(required_packages))
    print("=" * 50)
    
    try:
        app = LicensePlateRecognitionSystem()
        app.run()
    except Exception as e:
        print(f"Error starting application: {e}")
        input("Press Enter to exit...")