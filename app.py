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
from datetime import datetime, timedelta
from PIL import Image, ImageTk
import json
from difflib import SequenceMatcher
import webcolors
from speed import SpeedEstimationModule, TrafficViolationDetector, integrate_speed_estimation
# Add this import after your existing imports
from app_integration import integrate_criminal_intelligence_features
from app_integration_alerts import integrate_database_alerts


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

class EnhancedLicensePlateRecognitionSystem:
    def __init__(self):
        self.root = tk.Tk()
        self.is_processing = False
        self.video_source = None
        self.cap = None
        self.current_frame = None
        self.video_fps = 30  # Default FPS, will be updated from video
        # Initialize Speed Estimation
        self.speed_estimator = SpeedEstimationModule(fps=self.video_fps)

        

        # Processing results with enhanced data
        self.results = {}
        self.processed_data = []
        self.interpolated_data = []
        
        # Models and trackers
        self.coco_model = None
        self.license_plate_detector = None
        self.mot_tracker = None
        self.ocr_reader = None
        
        # Vehicle classes in COCO dataset with names
        self.vehicles = {
            2: "car",
            3: "motorcycle", 
            5: "bus",
            7: "truck"
        }
        
        # Color detection setup
        self.dominant_colors = {
            'red': ([0, 100, 100], [10, 255, 255]),
            'orange': ([11, 100, 100], [25, 255, 255]),
            'yellow': ([26, 100, 100], [35, 255, 255]),
            'green': ([36, 100, 100], [85, 255, 255]),
            'blue': ([86, 100, 100], [125, 255, 255]),
            'purple': ([126, 100, 100], [145, 255, 255]),
            'pink': ([146, 100, 100], [165, 255, 255]),
            'white': ([0, 0, 200], [180, 30, 255]),
            'black': ([0, 0, 0], [180, 255, 50]),
            'gray': ([0, 0, 51], [180, 30, 199])
        }
        
        # Search functionality
        self.target_plates = []
        self.search_results = {}
        
        # Settings
        self.settings = {
            'detection_confidence': 0.5,
            'tracking_enabled': True,
            'interpolation_enabled': True,
            'save_screenshots': True,
            'output_directory': './output',
            'color_detection_enabled': True,
            'vehicle_type_detection': True
        }
        
        # Load settings and initialize
        self.load_settings()
        self.initialize_models()
        self.setup_gui()

        from multi_camera_intelligence import integrate_multi_camera_network

        self.alert_system = integrate_database_alerts(self)

        from speed import integrate_speed_estimation
        self.process_frame_enhanced = integrate_speed_estimation(self)(self.process_frame_enhanced)
        self.speed_estimator.current_zone = 'school_zone'  # 20 km/h limit
        integrate_criminal_intelligence_features(self)

        try:
            from integration_multicamera import integrate_multicamera_network
            integrate_multicamera_network(self)
        except ImportError:
            print("⚠️ Multi-Camera module not found - continuing without it")
        except Exception as e:
            print(f"⚠️ Multi-Camera integration error: {e}")
        
    def initialize_models(self):
        """Initialize AI models"""
        if YOLO_AVAILABLE:
            try:
                self.log_message("Loading YOLO models...")
                self.coco_model = YOLO('yolov8n.pt')
                
                # Try to load license plate detector
                if os.path.exists('license_plate_detector.pt'):
                    self.license_plate_detector = YOLO('license_plate_detector.pt')
                    self.log_message("License plate detector loaded successfully")
                else:
                    self.log_message("Warning: license_plate_detector.pt not found")
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
        """Setup the main GUI with enhanced features"""
        self.root.title("THEFT DETECTION SYSTEM")
        self.root.geometry("1500x950")
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
        title_label = tk.Label(main_container, text="STOLEN VEHICLE DETECTION SYSTEM", 
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
        ttk.Button(left_panel, text="Create Visualization", 
                command=self.create_visualization).pack(fill=tk.X, pady=2)
        
        # âœ… New Speed button
        ttk.Button(left_panel, text="Show Speed Violations", 
                command=self.show_speed_violations).pack(fill=tk.X, pady=2)
        
        ttk.Separator(left_panel, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # Processing statistics
        stats_frame = ttk.LabelFrame(left_panel, text="Statistics")
        stats_frame.pack(fill=tk.X, pady=5)
    
        self.stats_labels = {
            'frames_processed': tk.Label(stats_frame, text="Frames: 0", bg='white'),
            'plates_detected': tk.Label(stats_frame, text="Plates: 0", bg='white'),
            'unique_plates': tk.Label(stats_frame, text="Unique: 0", bg='white'),
            'processing_fps': tk.Label(stats_frame, text="FPS: 0", bg='white'),
            'video_time': tk.Label(stats_frame, text="Video Time: 00:00", bg='white')
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

        ttk.Button(left_panel, text="🧪 Test Camera Network", 
          command=self.test_camera_network).pack(fill=tk.X, pady=2)

    
    def show_speed_violations(self):
        """Show vehicles exceeding speed limits"""
        if not hasattr(self, 'speed_estimator'):
            messagebox.showwarning("Warning", "Speed Estimation is not initialized.")
            return
        
        violations = self.speed_estimator.get_speed_violations()
        
        if not violations:
            messagebox.showinfo("Speed Check", "No vehicles are speeding ðŸš—âœ…")
            return
        
        details = "Speed Violations Detected:\n\n"
        for v in violations:
            details += (f"Vehicle ID: {v['vehicle_id']}\n"
                        f"Speed: {v['speed']:.1f} km/h\n"
                        f"Limit: {v['limit']} km/h\n"
                        f"Excess: {v['excess']:.1f} km/h\n"
                        f"Time: {v['timestamp']}\n\n")
        
        messagebox.showwarning("Speed Violations", details)



    def setup_search_tab(self):
        """Setup the enhanced license plate search tab"""
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
        
        # Create enhanced Treeview for results
        columns = ('Plate', 'Detections', 'Car ID', 'First Time', 'Last Time', 'Duration', 'Vehicle Type', 'Color', 'Avg Confidence')
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=10)
        
        # Configure column widths
        column_widths = {
            'Plate': 100,
            'Detections': 80,
            'Car ID': 60,
            'First Time': 80,
            'Last Time': 80,
            'Duration': 70,
            'Vehicle Type': 100,
            'Color': 80,
            'Avg Confidence': 100
        }
        
        for col in columns:
            self.results_tree.heading(col, text=col)
            self.results_tree.column(col, width=column_widths.get(col, 80), anchor=tk.CENTER)
        
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
        """Setup the enhanced settings tab"""
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
        
        # Feature checkboxes
        self.tracking_var = tk.BooleanVar(value=self.settings['tracking_enabled'])
        ttk.Checkbutton(detection_frame, text="Enable Vehicle Tracking", 
                       variable=self.tracking_var).pack(anchor=tk.W)
        
        self.interpolation_var = tk.BooleanVar(value=self.settings['interpolation_enabled'])
        ttk.Checkbutton(detection_frame, text="Enable Data Interpolation", 
                       variable=self.interpolation_var).pack(anchor=tk.W)
        
        self.screenshots_var = tk.BooleanVar(value=self.settings['save_screenshots'])
        ttk.Checkbutton(detection_frame, text="Save Detection Screenshots", 
                       variable=self.screenshots_var).pack(anchor=tk.W)
        
        # New enhanced features
        self.color_detection_var = tk.BooleanVar(value=self.settings.get('color_detection_enabled', True))
        ttk.Checkbutton(detection_frame, text="Enable Vehicle Color Detection", 
                       variable=self.color_detection_var).pack(anchor=tk.W)
        
        self.vehicle_type_var = tk.BooleanVar(value=self.settings.get('vehicle_type_detection', True))
        ttk.Checkbutton(detection_frame, text="Enable Vehicle Type Detection", 
                       variable=self.vehicle_type_var).pack(anchor=tk.W)
        
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

    def setup_status_bar(self, parent):
        """Setup the status bar with green progress bar"""
        status_frame = tk.Frame(parent, bg='#34495e', height=30)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(status_frame, text="Ready", bg='#34495e', fg='white', 
                                    font=('Arial', 10))
        self.status_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        # Progress bar with green styling
        self.progress_var = tk.DoubleVar()
        
        # Configure green progress bar style
        style = ttk.Style()
        style.configure("Green.Horizontal.TProgressbar", 
                       background="#ffffff",  # Green color
                       troughcolor='#2c3e50',  # Dark background
                       borderwidth=1,
                       lightcolor="#cbcbcb",  # Light green
                       darkcolor="#9d9d9d")   # Dark green
        
        self.progress_bar = ttk.Progressbar(status_frame, 
                                          variable=self.progress_var, 
                                          mode='determinate',
                                          style="Green.Horizontal.TProgressbar")
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
            # Get video FPS for timestamp calculation
            temp_cap = cv2.VideoCapture(file_path)
            if temp_cap.isOpened():
                self.video_fps = temp_cap.get(cv2.CAP_PROP_FPS)
                temp_cap.release()
            self.log_message(f"Selected video: {os.path.basename(file_path)} (FPS: {self.video_fps:.2f})")

    def use_webcam(self):
        """Use webcam for live processing"""
        self.video_source = 0
        self.video_fps = 30  # Default for webcam
        self.log_message("Set to use webcam")

    def detect_vehicle_color(self, vehicle_crop):
        """Detect dominant color of vehicle using HSV color space"""
        if vehicle_crop is None or vehicle_crop.size == 0:
            return "unknown"
        
        try:
            # Convert BGR to HSV
            hsv = cv2.cvtColor(vehicle_crop, cv2.COLOR_BGR2HSV)
            
            # Create mask for non-black/shadow areas
            mask = cv2.inRange(hsv, (0, 0, 50), (180, 255, 255))
            
            # Get the most prominent color
            color_counts = {}
            for color_name, (lower, upper) in self.dominant_colors.items():
                color_mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
                combined_mask = cv2.bitwise_and(mask, color_mask)
                color_counts[color_name] = cv2.countNonZero(combined_mask)
            
            # Return the color with the highest count
            if max(color_counts.values()) > 0:
                return max(color_counts, key=color_counts.get)
            else:
                return "unknown"
                
        except Exception as e:
            return "unknown"

    def start_processing(self):
        """Start video processing with enhanced features"""
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
        
        self.log_message("Started enhanced video processing...")

    def stop_processing(self):
        """Stop video processing"""
        self.is_processing = False
        if self.cap:
            self.cap.release()
        self.log_message("Processing stopped")

    def processing_loop(self):
        """Enhanced processing loop with color and vehicle type detection"""
        try:
            self.cap = cv2.VideoCapture(self.video_source)
            if not self.cap.isOpened():
                self.log_message("Error: Cannot open video source")
                return
            
            total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)) if self.video_source != 0 else 0
            self.video_fps = self.cap.get(cv2.CAP_PROP_FPS) if self.video_fps == 30 else self.video_fps
            
            frame_nmr = -1
            start_time = time.time()
            
            while self.is_processing and self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret:
                    break
                
                frame_nmr += 1
                self.current_frame = frame.copy()
                
                # Update progress - use after() to schedule on main thread
                if total_frames > 0:
                    progress = (frame_nmr / total_frames) * 100
                    self.root.after(0, lambda p=progress: self.progress_var.set(p))
                
                # Process frame with enhanced detection
                self.process_frame_enhanced(frame, frame_nmr)
                
                # Update display - use after() to schedule on main thread
                self.root.after(0, lambda f=frame.copy(): self.update_video_display(f))
                
                # Update statistics - use after() to schedule on main thread
                self.root.after(0, lambda fn=frame_nmr, st=start_time: self.update_statistics_enhanced(fn, st))
                
                # Small delay to prevent overwhelming
                time.sleep(0.01)
            
            self.cap.release()
            self.log_message("Enhanced video processing completed")
            # Schedule export on main thread
            self.root.after(0, self.export_to_csv)
            
        except Exception as e:
            self.log_message(f"Error during processing: {str(e)}")
        finally:
            self.is_processing = False

    def process_frame_enhanced(self, frame, frame_nmr):
        """Process a single frame with enhanced vehicle analysis"""
        try:
            self.results[frame_nmr] = {}
            
            # Calculate timestamp
            timestamp = frame_nmr / self.video_fps
            
            # Detect vehicles
            detections = self.coco_model(frame, conf=self.confidence_var.get())[0]
            detections_ = []
            vehicle_types = {}
            
            for detection in detections.boxes.data.tolist():
                x1, y1, x2, y2, score, class_id = detection
                if int(class_id) in self.vehicles:
                    detections_.append([x1, y1, x2, y2, score])
                    # Store vehicle type
                    vehicle_types[(x1, y1, x2, y2)] = self.vehicles[int(class_id)]
            
            # Track vehicles if enabled
            if self.tracking_var.get() and self.mot_tracker:
                track_ids = self.mot_tracker.update(np.asarray(detections_))
            else:
                # Assign dummy IDs
                track_ids = [[*det, i] for i, det in enumerate(detections_)]
            
            # Detect license plates
            if self.license_plate_detector:
                license_plates = self.license_plate_detector(frame, conf=0.3)[0]
                
                for license_plate in license_plates.boxes.data.tolist():
                    x1, y1, x2, y2, score, class_id = license_plate
                    
                    # Assign to car
                    car_match = self.get_car(license_plate, track_ids)
                    if car_match:
                        xcar1, ycar1, xcar2, ycar2, car_id = car_match
                        
                        # Crop vehicle for color detection
                        vehicle_crop = frame[int(ycar1):int(ycar2), int(xcar1):int(xcar2)]
                        vehicle_color = "unknown"
                        vehicle_type = "unknown"
                        
                        if self.color_detection_var.get():
                            vehicle_color = self.detect_vehicle_color(vehicle_crop)
                        
                        if self.vehicle_type_var.get():
                            # Find matching vehicle type
                            for (vx1, vy1, vx2, vy2), vtype in vehicle_types.items():
                                if abs(vx1 - xcar1) < 50 and abs(vy1 - ycar1) < 50:
                                    vehicle_type = vtype
                                    break
                        
                        # Crop and process license plate
                        license_text, text_score = self.read_license_plate(frame, x1, y1, x2, y2)
                        
                        if license_text:
                            self.results[frame_nmr][car_id] = {
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
                            
                            # Save to processed data for search with enhanced info
                            self.processed_data.append({
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
        
        except Exception as e:
            self.log_message(f"Error processing frame {frame_nmr}: {str(e)}")

            # ========================================================================
        # CAMERA NETWORK INTEGRATION - Register detections
        # ========================================================================
            if hasattr(self, 'camera_network') and hasattr(self, 'current_camera_id'):
                try:
                    from datetime import datetime
                    
                    # Get current timestamp
                    current_timestamp = datetime.now()
                    
                    # Register each detection with camera network
                    for car_id, detection in self.results[frame_nmr].items():
                        license_plate = detection['license_plate']['text']
                        
                        # Only register valid plates (not '0' or empty)
                        if license_plate and license_plate != '0':
                            vehicle_color = detection.get('vehicle_color', 'unknown')
                            vehicle_type = detection.get('vehicle_type', 'unknown')
                            
                            # Register with camera network
                            success, result = self.camera_network.register_detection(
                                camera_id=self.current_camera_id,
                                license_plate=license_plate,
                                timestamp=current_timestamp,
                                vehicle_color=vehicle_color,
                                vehicle_type=vehicle_type
                            )
                            
                            if success:
                                # Check if suspicious
                                if hasattr(result, 'suspicious_score'):
                                    if result.suspicious_score >= 70:
                                        self.log_message(
                                            f"⚠️ SUSPICIOUS: {license_plate} "
                                            f"(Score: {result.suspicious_score})"
                                        )
                except Exception as e:
                    # Don't let camera network errors stop video processing
                    print(f"Camera network registration error: {e}")
            # ========================================================================
        
        except Exception as e:  # ← This line already exists - don't duplicate it
            self.log_message(f"Error processing frame {frame_nmr}: {str(e)}")

    def get_car(self, license_plate, vehicle_track_ids):
        """Get car that contains the license plate"""
        x1, y1, x2, y2, score, class_id = license_plate
        
        for track in vehicle_track_ids:
            if len(track) >= 5:
                xcar1, ycar1, xcar2, ycar2, car_id = track[:5]
                if x1 > xcar1 and y1 > ycar1 and x2 < xcar2 and y2 < ycar2:
                    return [xcar1, ycar1, xcar2, ycar2, car_id]
        return None

    def read_license_plate(self, frame, x1, y1, x2, y2):
        """Read license plate text using OCR"""
        if not self.ocr_reader:
            return None, 0
        
        try:
            # Crop license plate
            license_crop = frame[int(y1):int(y2), int(x1):int(x2)]
            if license_crop.size == 0:
                return None, 0
            
            # Convert to grayscale and threshold
            gray = cv2.cvtColor(license_crop, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 64, 255, cv2.THRESH_BINARY_INV)
            
            # Use OCR
            results = self.ocr_reader.readtext(thresh)
            
            if results:
                # Get the result with highest confidence
                best_result = max(results, key=lambda x: x[2])
                text = best_result[1].upper().replace(' ', '')
                confidence = best_result[2]
                
                # Basic validation
                if len(text) >= 3 and confidence > 0.5:
                    return text, confidence
            
            return None, 0
            
        except Exception as e:
            self.log_message(f"OCR error: {str(e)}")
            return None, 0

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

    def update_statistics_enhanced(self, frame_nmr, start_time):
        """Update processing statistics with enhanced info"""
        try:
            elapsed = time.time() - start_time
            fps = frame_nmr / elapsed if elapsed > 0 else 0
            
            # Calculate video timestamp
            video_time = frame_nmr / self.video_fps
            minutes = int(video_time // 60)
            seconds = int(video_time % 60)
            time_str = f"{minutes:02d}:{seconds:02d}"
            
            plates_count = sum(len(frame_data) for frame_data in self.results.values())
            unique_plates = len(set(item['license_number'] for item in self.processed_data))
            
            self.stats_labels['frames_processed'].configure(text=f"Frames: {frame_nmr}")
            self.stats_labels['plates_detected'].configure(text=f"Plates: {plates_count}")
            self.stats_labels['unique_plates'].configure(text=f"Unique: {unique_plates}")
            self.stats_labels['processing_fps'].configure(text=f"FPS: {fps:.1f}")
            self.stats_labels['video_time'].configure(text=f"Video Time: {time_str}")
            
        except Exception as e:
            pass

    def interpolate_data(self):
        """Enhanced interpolation with proper NaN handling"""
        if not self.processed_data:
            messagebox.showwarning("Warning", "No data to interpolate. Process a video first.")
            return
        
        if not SCIPY_AVAILABLE:
            messagebox.showerror("Error", "SciPy is required for interpolation but not available.")
            return
        
        self.log_message("Starting enhanced data interpolation with NaN handling...")
        
        try:
            # Convert to the format expected by interpolation function
            data_for_interp = []
            for item in self.processed_data:
                # Validate and clean data before interpolation
                try:
                    frame_nmr = float(item['frame_nmr'])
                    car_id = float(item['car_id'])
                    timestamp = float(item.get('timestamp', 0))
                    
                    # Check for NaN values and skip invalid entries
                    if (np.isnan(frame_nmr) or np.isnan(car_id) or 
                        np.isnan(timestamp)):
                        self.log_message(f"Skipping invalid data: frame {item.get('frame_nmr', 'N/A')}")
                        continue
                    
                    data_for_interp.append({
                        'frame_nmr': str(int(frame_nmr)),
                        'car_id': str(int(car_id)),
                        'car_bbox': item['car_bbox'],
                        'license_plate_bbox': item['license_plate_bbox'],
                        'license_plate_bbox_score': str(item['license_plate_bbox_score']),
                        'license_number': item['license_number'],
                        'license_number_score': str(item['license_number_score']),
                        'timestamp': str(timestamp),
                        'vehicle_color': item.get('vehicle_color', 'unknown'),
                        'vehicle_type': item.get('vehicle_type', 'unknown')
                    })
                except (ValueError, TypeError, KeyError) as e:
                    self.log_message(f"Skipping invalid data entry: {e}")
                    continue
            
            # Perform enhanced interpolation
            self.interpolated_data = self.interpolate_bounding_boxes_enhanced(data_for_interp)
            self.log_message(f"Enhanced interpolation completed. {len(self.interpolated_data)} records generated.")
            
        except Exception as e:
            self.log_message(f"Interpolation error: {str(e)}")
            messagebox.showerror("Error", f"Interpolation failed: {str(e)}")

    def test_camera_network(self):
        """Add test data to camera network"""
        if not hasattr(self, 'camera_network'):
            messagebox.showwarning("Warning", "Camera network not available")
            return
    
        from datetime import datetime, timedelta
    
    # Make sure cameras exist
        if "CAM001" not in self.camera_network.cameras:
            self.camera_network.add_camera("CAM001", "Main Gate", "Entrance", (0, 0))
        if "CAM002" not in self.camera_network.cameras:
            self.camera_network.add_camera("CAM002", "Parking Lot", "North Area", (100, 50))
        if "CAM003" not in self.camera_network.cameras:
            self.camera_network.add_camera("CAM003", "Exit Gate", "Exit Area", (200, 0))
    
    # Add test detections
        base_time = datetime.now() - timedelta(minutes=30)
    
    # Vehicle 1: Normal journey across 3 cameras
        self.camera_network.register_detection(
            camera_id="CAM001",
            license_plate="GXISOCJ",
            timestamp=base_time,
            vehicle_color="red",
            vehicle_type="car"
        )
    
        self.camera_network.register_detection(
            camera_id="CAM002",
            license_plate="TN01AB1234",  # Same vehicle
            timestamp=base_time + timedelta(minutes=5),
            vehicle_color="red",
            vehicle_type="car"
        )
        
        self.camera_network.register_detection(
            camera_id="CAM003",
            license_plate="TN01AB1234",  # Same vehicle
            timestamp=base_time + timedelta(minutes=10),
            vehicle_color="red",
            vehicle_type="car"
        )
        
        # Vehicle 2: Suspicious looping
        loop_time = base_time + timedelta(minutes=15)
        self.camera_network.register_detection(
            camera_id="CAM001",
            license_plate="GXISOCJ",
            timestamp=loop_time,
            vehicle_color="blue",
            vehicle_type="truck"
        )
        
        self.camera_network.register_detection(
            camera_id="CAM002",
            license_plate="KL09XY5678",
            timestamp=loop_time + timedelta(minutes=3),
            vehicle_color="blue",
            vehicle_type="truck"
        )
        
        # Same vehicle comes back to CAM001 (looping!)
        self.camera_network.register_detection(
            camera_id="CAM001",
            license_plate="GXISOCJ",
            timestamp=loop_time + timedelta(minutes=8),
            vehicle_color="blue",
            vehicle_type="truck"
        )
        
        # More vehicles
        for i in range(5):
            self.camera_network.register_detection(
                camera_id=f"CAM00{(i % 3) + 1}",
                license_plate=f"TN99AB{1000 + i}",
                timestamp=base_time + timedelta(minutes=i*2),
                vehicle_color=["white", "black", "grey", "silver", "green"][i],
                vehicle_type="car"
            )
        
        self.log_message("✅ Test data added: 11 detections for 7 vehicles")
        messagebox.showinfo("Success", 
            "Test data added successfully!\n\n"
            "Detections: 11\n"
            "Vehicles: 7 unique\n"
            "Cameras: 3\n\n"
            "Go to:\n"
            "Camera Network → Journey Tracking → Show All Vehicles"
    )

    def interpolate_bounding_boxes_enhanced(self, data):
        """Enhanced interpolation with NaN handling and additional attributes"""
        from scipy.interpolate import interp1d
        
        if not data:
            return []
        
        interpolated_data = []
        
        try:
            # Group data by car_id
            cars_data = {}
            for row in data:
                try:
                    car_id = int(float(row['car_id']))
                    if car_id not in cars_data:
                        cars_data[car_id] = []
                    cars_data[car_id].append(row)
                except (ValueError, TypeError):
                    continue
            
            for car_id, car_rows in cars_data.items():
                if len(car_rows) < 2:
                    self.log_message(f"Skipping car {car_id}: insufficient data points ({len(car_rows)})")
                    continue
                
                try:
                    # Sort by frame number
                    car_rows.sort(key=lambda x: int(float(x['frame_nmr'])))
                    
                    # Extract data for interpolation
                    frame_numbers = []
                    car_bboxes = []
                    lp_bboxes = []
                    timestamps = []
                    
                    for row in car_rows:
                        try:
                            frame_num = int(float(row['frame_nmr']))
                            timestamp = float(row['timestamp'])
                            
                            # Parse bounding boxes
                            car_bbox = self.parse_bbox_string(row['car_bbox'])
                            lp_bbox = self.parse_bbox_string(row['license_plate_bbox'])
                            
                            if car_bbox and lp_bbox and len(car_bbox) == 4 and len(lp_bbox) == 4:
                                # Check for NaN values in coordinates
                                if (not any(np.isnan(coord) for coord in car_bbox) and
                                    not any(np.isnan(coord) for coord in lp_bbox) and
                                    not np.isnan(timestamp)):
                                    
                                    frame_numbers.append(frame_num)
                                    car_bboxes.append(car_bbox)
                                    lp_bboxes.append(lp_bbox)
                                    timestamps.append(timestamp)
                        except (ValueError, TypeError, IndexError):
                            continue
                    
                    if len(frame_numbers) < 2:
                        continue
                    
                    # Convert to numpy arrays
                    frame_numbers = np.array(frame_numbers)
                    car_bboxes = np.array(car_bboxes)
                    lp_bboxes = np.array(lp_bboxes)
                    timestamps = np.array(timestamps)
                    
                    # Create interpolation range
                    first_frame = frame_numbers[0]
                    last_frame = frame_numbers[-1]
                    all_frames = np.arange(first_frame, last_frame + 1)
                    
                    # Interpolate bounding boxes
                    car_interp = interp1d(frame_numbers, car_bboxes, axis=0, 
                                        kind='linear', bounds_error=False, fill_value='extrapolate')
                    lp_interp = interp1d(frame_numbers, lp_bboxes, axis=0, 
                                       kind='linear', bounds_error=False, fill_value='extrapolate')
                    
                    # Interpolate timestamps
                    time_interp = interp1d(frame_numbers, timestamps, 
                                         kind='linear', bounds_error=False, fill_value='extrapolate')
                    
                    car_bboxes_interp = car_interp(all_frames)
                    lp_bboxes_interp = lp_interp(all_frames)
                    timestamps_interp = time_interp(all_frames)
                    
                    # Get vehicle attributes from original data
                    vehicle_color = car_rows[0].get('vehicle_color', 'unknown')
                    vehicle_type = car_rows[0].get('vehicle_type', 'unknown')
                    
                    # Create interpolated records
                    for i, frame_num in enumerate(all_frames):
                        try:
                            # Check for NaN in interpolated data
                            car_coords = car_bboxes_interp[i]
                            lp_coords = lp_bboxes_interp[i]
                            timestamp = timestamps_interp[i]
                            
                            if (any(np.isnan(coord) for coord in car_coords) or
                                any(np.isnan(coord) for coord in lp_coords) or
                                np.isnan(timestamp)):
                                continue
                            
                            row = {
                                'frame_nmr': str(int(frame_num)),
                                'car_id': str(int(car_id)),
                                'car_bbox': ' '.join([f"{coord:.2f}" for coord in car_coords]),
                                'license_plate_bbox': ' '.join([f"{coord:.2f}" for coord in lp_coords]),
                                'timestamp': f"{timestamp:.2f}",
                                'vehicle_color': vehicle_color,
                                'vehicle_type': vehicle_type
                            }
                            
                            # Check if this is original or interpolated data
                            if frame_num in frame_numbers:
                                # Original data
                                orig_row = next(r for r in car_rows if int(float(r['frame_nmr'])) == frame_num)
                                row['license_plate_bbox_score'] = orig_row['license_plate_bbox_score']
                                row['license_number'] = orig_row['license_number']
                                row['license_number_score'] = orig_row['license_number_score']
                            else:
                                # Interpolated data
                                row['license_plate_bbox_score'] = '0'
                                row['license_number'] = '0'
                                row['license_number_score'] = '0'
                            
                            interpolated_data.append(row)
                            
                        except Exception as e:
                            self.log_message(f"Error creating interpolated record: {e}")
                            continue
                
                except Exception as e:
                    self.log_message(f"Error interpolating car {car_id}: {e}")
                    continue
        
        except Exception as e:
            self.log_message(f"Critical interpolation error: {e}")
        
        return interpolated_data

    def format_timestamp(self, timestamp):
        """Convert timestamp to MM:SS format"""
        try:
            timestamp = float(timestamp)
            minutes = int(timestamp // 60)
            seconds = int(timestamp % 60)
            return f"{minutes:02d}:{seconds:02d}"
        except:
            return "00:00"

    def search_license_plate(self):
        """Enhanced search for a specific license plate"""
        target_plate = self.search_entry.get().strip().upper()
        if not target_plate:
            messagebox.showwarning("Warning", "Please enter a license plate number to search.")
            return
        
        # Use interpolated data if available, otherwise use original
        data_to_search = self.interpolated_data if self.interpolated_data else self.processed_data
        
        if not data_to_search:
            messagebox.showwarning("Warning", "No data to search. Process a video first.")
            return
        
        self.log_message(f"Searching for license plate: {target_plate}")
        
        # Clear previous results
        self.results_tree.delete(*self.results_tree.get_children())
        
        # Convert to DataFrame for easier searching
        df = pd.DataFrame(data_to_search)
        
        # Clean target plate
        target_clean = ''.join(filter(str.isalnum, target_plate))
        
        # Find exact matches
        exact_matches = df[df['license_number'].str.replace(' ', '').str.upper() == target_clean]
        
        results_found = False
        
        if not exact_matches.empty:
            results_found = True
            self.log_message(f"Found {len(exact_matches)} exact matches")
            
            # Group by car_id for summary
            for car_id in exact_matches['car_id'].unique():
                car_matches = exact_matches[exact_matches['car_id'] == car_id]
                
                # Get timestamps
                timestamps = car_matches['timestamp'].astype(float) if 'timestamp' in car_matches.columns else [0] * len(car_matches)
                first_time = self.format_timestamp(min(timestamps))
                last_time = self.format_timestamp(max(timestamps))
                
                # Calculate duration
                duration_seconds = max(timestamps) - min(timestamps)
                duration = self.format_timestamp(duration_seconds)
                
                frame_count = len(car_matches)
                
                # Get vehicle attributes
                vehicle_type = car_matches.iloc[0].get('vehicle_type', 'unknown')
                vehicle_color = car_matches.iloc[0].get('vehicle_color', 'unknown')
                
                # Calculate average confidence
                scores = car_matches['license_number_score']
                valid_scores = scores[scores != '0'].astype(float)
                avg_confidence = valid_scores.mean() if not valid_scores.empty else 0
                
                # Insert into treeview with enhanced data
                self.results_tree.insert('', 'end', values=(
                    target_plate, frame_count, car_id, first_time, last_time, 
                    duration, vehicle_type, vehicle_color, f"{avg_confidence:.2f}"
                ))
        
        # Fuzzy search if no exact matches
        if not results_found:
            threshold = self.similarity_var.get()
            self.log_message(f"No exact matches. Searching with similarity threshold: {threshold}")
            
            fuzzy_matches = []
            unique_plates = df['license_number'].unique()
            
            for plate in unique_plates:
                if plate and plate != '0':
                    plate_clean = ''.join(filter(str.isalnum, plate.upper()))
                    similarity = self.calculate_similarity(target_clean, plate_clean)
                    
                    if similarity >= threshold:
                        fuzzy_matches.append((plate, similarity))
            
            if fuzzy_matches:
                results_found = True
                fuzzy_matches.sort(key=lambda x: x[1], reverse=True)
                self.log_message(f"Found {len(fuzzy_matches)} fuzzy matches")
                
                for plate, similarity in fuzzy_matches:
                    plate_matches = df[df['license_number'] == plate]
                    
                    for car_id in plate_matches['car_id'].unique():
                        car_matches = plate_matches[plate_matches['car_id'] == car_id]
                        
                        timestamps = car_matches['timestamp'].astype(float) if 'timestamp' in car_matches.columns else [0] * len(car_matches)
                        first_time = self.format_timestamp(min(timestamps))
                        last_time = self.format_timestamp(max(timestamps))
                        duration_seconds = max(timestamps) - min(timestamps)
                        duration = self.format_timestamp(duration_seconds)
                        
                        frame_count = len(car_matches)
                        
                        vehicle_type = car_matches.iloc[0].get('vehicle_type', 'unknown')
                        vehicle_color = car_matches.iloc[0].get('vehicle_color', 'unknown')
                        
                        scores = car_matches['license_number_score']
                        valid_scores = scores[scores != '0'].astype(float)
                        avg_confidence = valid_scores.mean() if not valid_scores.empty else 0
                        
                        # Insert with similarity info
                        display_text = f"{plate} (sim: {similarity:.2f})"
                        self.results_tree.insert('', 'end', values=(
                            display_text, frame_count, car_id, first_time, last_time,
                            duration, vehicle_type, vehicle_color, f"{avg_confidence:.2f}"
                        ))
        
        if not results_found:
            self.log_message("No matches found")
            messagebox.showinfo("No Results", f"No license plates found matching '{target_plate}'")

    def calculate_similarity(self, a, b):
        """Calculate similarity between two strings"""
        return SequenceMatcher(None, a, b).ratio()

    def show_all_plates(self):
        """Show all detected license plates with enhanced information"""
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
            
            for car_id in plate_data['car_id'].unique():
                car_matches = plate_data[plate_data['car_id'] == car_id]
                
                # Get timestamps
                timestamps = car_matches['timestamp'].astype(float) if 'timestamp' in car_matches.columns else [0] * len(car_matches)
                first_time = self.format_timestamp(min(timestamps))
                last_time = self.format_timestamp(max(timestamps))
                duration_seconds = max(timestamps) - min(timestamps)
                duration = self.format_timestamp(duration_seconds)
                
                frame_count = len(car_matches)
                
                # Get vehicle attributes
                vehicle_type = car_matches.iloc[0].get('vehicle_type', 'unknown')
                vehicle_color = car_matches.iloc[0].get('vehicle_color', 'unknown')
                
                scores = car_matches['license_number_score']
                valid_scores = scores[scores != '0'].astype(float)
                avg_confidence = valid_scores.mean() if not valid_scores.empty else 0
                
                self.results_tree.insert('', 'end', values=(
                    plate, frame_count, car_id, first_time, last_time,
                    duration, vehicle_type, vehicle_color, f"{avg_confidence:.2f}"
                ))

    def on_result_double_click(self, event):
        """Handle double-click on search results with enhanced details"""
        selection = self.results_tree.selection()
        if not selection:
            return
        
        item = self.results_tree.item(selection[0])
        values = item['values']
        
        if len(values) >= 9:
            plate = values[0]
            car_id = values[2]
            first_time = values[3]
            last_time = values[4]
            duration = values[5]
            vehicle_type = values[6]
            vehicle_color = values[7]
            
            # Show enhanced detailed information
            detail_msg = f"License Plate: {plate}\n"
            detail_msg += f"Car ID: {car_id}\n"
            detail_msg += f"Vehicle Type: {vehicle_type.title()}\n"
            detail_msg += f"Vehicle Color: {vehicle_color.title()}\n"
            detail_msg += f"First Detection: {first_time}\n"
            detail_msg += f"Last Detection: {last_time}\n"
            detail_msg += f"Duration in Video: {duration}\n"
            detail_msg += f"Total Detections: {values[1]}\n"
            detail_msg += f"Average Confidence: {values[8]}"
            
            messagebox.showinfo("Enhanced Plate Details", detail_msg)

    def parse_bbox_string(self, bbox_str):
        """Parse bounding box string to coordinates with error handling"""
        try:
            if isinstance(bbox_str, str):
                # Remove brackets and split
                clean_str = bbox_str.strip('[]')
                coords = [float(x.strip()) for x in clean_str.split()]
                return coords if len(coords) == 4 else None
            return None
        except:
            return None

    def export_csv(self):
        """Export enhanced processed data to CSV"""
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
                self.write_enhanced_csv_data(self.processed_data, original_path)
                self.log_message(f"Enhanced original data exported to: {original_path}")
            
            # Export interpolated data if available
            if self.interpolated_data:
                interp_path = os.path.join(output_dir, 'license_plates_interpolated.csv')
                self.write_enhanced_csv_data(self.interpolated_data, interp_path)
                self.log_message(f"Enhanced interpolated data exported to: {interp_path}")
            
            messagebox.showinfo("Success", "Enhanced data exported successfully!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {str(e)}")

    def export_to_csv(self):
        """Auto-export after processing"""
        self.export_csv()

    def write_enhanced_csv_data(self, data, filepath):
        """Write enhanced data to CSV file"""
        if not data:
            return
        
        headers = ['frame_nmr', 'car_id', 'car_bbox', 'license_plate_bbox', 
                  'license_plate_bbox_score', 'license_number', 'license_number_score',
                  'timestamp', 'vehicle_color', 'vehicle_type']
        
        with open(filepath, 'w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()
            
            for item in data:
                # Convert format if needed
                if isinstance(item, dict):
                    row = {
                        'frame_nmr': str(item.get('frame_nmr', '')),
                        'car_id': str(item.get('car_id', '')),
                        'car_bbox': item.get('car_bbox', ''),
                        'license_plate_bbox': item.get('license_plate_bbox', ''),
                        'license_plate_bbox_score': str(item.get('license_plate_bbox_score', 0)),
                        'license_number': str(item.get('license_number', '')),
                        'license_number_score': str(item.get('license_number_score', 0)),
                        'timestamp': str(item.get('timestamp', 0)),
                        'vehicle_color': str(item.get('vehicle_color', 'unknown')),
                        'vehicle_type': str(item.get('vehicle_type', 'unknown'))
                    }
                    writer.writerow(row)

    def create_visualization(self):
        """Create enhanced visualization video with annotations"""
        if not self.video_source or self.video_source == 0:
            messagebox.showwarning("Warning", "Visualization requires a video file, not webcam.")
            return
        
        if not self.processed_data:
            messagebox.showwarning("Warning", "No data to visualize. Process a video first.")
            return
        
        # Ask user for visualization type
        choice = messagebox.askyesnocancel(
            "Visualization Options", 
            "Do you want to create a targeted visualization?\n\n"
            "Yes - Show only specific license plate (you'll be asked which one)\n"
            "No - Show all detected license plates\n"
            "Cancel - Cancel visualization"
        )
        
        if choice is None:  # Cancel
            return
        elif choice:  # Yes - targeted visualization
            self.create_targeted_visualization()
        else:  # No - show all
            self.create_all_plates_visualization()

    def create_targeted_visualization(self):
        """Create visualization for a specific target license plate"""
        # Get available license plates
        data_to_use = self.interpolated_data if self.interpolated_data else self.processed_data
        df = pd.DataFrame(data_to_use)
        unique_plates = df[df['license_number'] != '0']['license_number'].unique()
        
        if len(unique_plates) == 0:
            messagebox.showwarning("Warning", "No license plates found in the data.")
            return
        
        # Create selection dialog
        selection_window = tk.Toplevel(self.root)
        selection_window.title("Select Target License Plate")
        selection_window.geometry("400x300")
        selection_window.configure(bg='#2c3e50')
        
        # Center the window
        selection_window.transient(self.root)
        selection_window.grab_set()
        
        tk.Label(selection_window, text="Select License Plate to Highlight:", 
                font=('Arial', 12, 'bold'), bg='#2c3e50', fg='white').pack(pady=10)
        
        # Listbox with scrollbar
        list_frame = tk.Frame(selection_window, bg='#2c3e50')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        plate_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, 
                                  font=('Arial', 11), height=10)
        plate_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=plate_listbox.yview)
        
        # Populate listbox with plate info
        plate_info = []
        for plate in unique_plates:
            plate_data = df[df['license_number'] == plate]
            count = len(plate_data)
            car_ids = ', '.join(map(str, plate_data['car_id'].unique()))
            vehicle_type = plate_data.iloc[0].get('vehicle_type', 'unknown')
            vehicle_color = plate_data.iloc[0].get('vehicle_color', 'unknown')
            
            display_text = f"{plate} | {vehicle_color.title()} {vehicle_type.title()} | {count} detections | Car ID(s): {car_ids}"
            plate_listbox.insert(tk.END, display_text)
            plate_info.append(plate)
        
        selected_plate = [None]
        
        def on_select():
            selection = plate_listbox.curselection()
            if selection:
                selected_plate[0] = plate_info[selection[0]]
                selection_window.destroy()
        
        def on_cancel():
            selection_window.destroy()
        
        # Buttons
        button_frame = tk.Frame(selection_window, bg='#2c3e50')
        button_frame.pack(pady=10)
        
        tk.Button(button_frame, text="Create Targeted Visualization", 
                 command=on_select, bg='#27ae60', fg='white', 
                 font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="Cancel", 
                 command=on_cancel, bg='#e74c3c', fg='white', 
                 font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=10)
        
        # Wait for selection
        selection_window.wait_window()
        
        if selected_plate[0]:
            self.log_message(f"Creating targeted visualization for license plate: {selected_plate[0]}")
            
            # Create visualization in separate thread
            vis_thread = threading.Thread(target=self.create_targeted_visualization_video, 
                                        args=(data_to_use, selected_plate[0]), daemon=True)
            vis_thread.start()

    def create_all_plates_visualization(self):
        """Create visualization showing all license plates"""
        self.log_message("Creating visualization with all license plates...")
        
        try:
            # Use interpolated data if available, otherwise use original
            data_to_use = self.interpolated_data if self.interpolated_data else self.processed_data
            
            # Create visualization in separate thread
            vis_thread = threading.Thread(target=self.create_enhanced_visualization_video, 
                                        args=(data_to_use,), daemon=True)
            vis_thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Visualization failed: {str(e)}")

    def create_targeted_visualization_video(self, data, target_plate):
        """Create visualization video showing only the target license plate"""
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
            safe_filename = "".join(c for c in target_plate if c.isalnum())
            output_path = os.path.join(self.output_dir_var.get(), f'targeted_visualization_{safe_filename}.mp4')
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            
            # Convert data to pandas DataFrame and filter for target plate
            df = pd.DataFrame(data)
            target_data = df[df['license_number'] == target_plate]
            
            if target_data.empty:
                self.log_message(f"No data found for target plate: {target_plate}")
                cap.release()
                out.release()
                return
            
            self.log_message(f"Found {len(target_data)} detections for target plate: {target_plate}")
            
            frame_nmr = 0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            detections_shown = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Update progress - schedule on main thread
                progress = (frame_nmr / total_frames) * 100
                self.root.after(0, lambda p=progress: self.progress_var.set(p))
                
                # Get detections for current frame (only target plate)
                frame_data = target_data[target_data['frame_nmr'] == str(frame_nmr)]
                
                for _, row in frame_data.iterrows():
                    try:
                        # Parse bounding boxes
                        car_bbox = self.parse_bbox_string(row['car_bbox'])
                        lp_bbox = self.parse_bbox_string(row['license_plate_bbox'])
                        
                        if car_bbox and lp_bbox:
                            detections_shown += 1
                            
                            # Draw car bounding box with different color for target
                            self.draw_border(frame, 
                                           (int(car_bbox[0]), int(car_bbox[1])), 
                                           (int(car_bbox[2]), int(car_bbox[3])), 
                                           (0, 255, 255), 30)  # Yellow for target car
                            
                            # Draw license plate bounding box with highlight color
                            cv2.rectangle(frame, 
                                        (int(lp_bbox[0]), int(lp_bbox[1])), 
                                        (int(lp_bbox[2]), int(lp_bbox[3])), 
                                        (0, 255, 255), 15)  # Yellow for target plate
                            
                            # Add enhanced information with special styling
                            license_text = row['license_number']
                            vehicle_type = row.get('vehicle_type', 'unknown')
                            vehicle_color = row.get('vehicle_color', 'unknown')
                            timestamp = self.format_timestamp(row.get('timestamp', 0))
                            
                            # Calculate text position
                            text_x = int((car_bbox[0] + car_bbox[2]) / 2)
                            text_y = int(car_bbox[1]) - 120
                            
                            # Target info text with timestamp
                            info_text = f"TARGET: {license_text}"
                            detail_text = f"{vehicle_color.title()} {vehicle_type.title()} @ {timestamp}"
                            
                            # Create background for main text
                            (text_width, text_height), _ = cv2.getTextSize(
                                info_text, cv2.FONT_HERSHEY_SIMPLEX, 2.0, 4)
                            
                            cv2.rectangle(frame, 
                                        (text_x - text_width//2 - 15, text_y - text_height - 15),
                                        (text_x + text_width//2 + 15, text_y + 15),
                                        (0, 255, 255), -1)  # Yellow background
                            
                            # Add main target text
                            cv2.putText(frame, info_text,
                                      (text_x - text_width//2, text_y),
                                      cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 0, 0), 4)
                            
                            # Add detail text below
                            (detail_width, detail_height), _ = cv2.getTextSize(
                                detail_text, cv2.FONT_HERSHEY_SIMPLEX, 1.2, 2)
                            
                            detail_y = text_y + 50
                            cv2.rectangle(frame, 
                                        (text_x - detail_width//2 - 10, detail_y - detail_height - 10),
                                        (text_x + detail_width//2 + 10, detail_y + 10),
                                        (255, 255, 255), -1)  # White background
                            
                            cv2.putText(frame, detail_text,
                                      (text_x - detail_width//2, detail_y),
                                      cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2)
                    
                    except Exception as e:
                        continue  # Skip problematic annotations
                
                out.write(frame)
                frame_nmr += 1
                
                # Update status periodically - schedule on main thread
                if frame_nmr % 60 == 0:
                    self.root.after(0, lambda fn=frame_nmr, tf=total_frames, ds=detections_shown: 
                                   self.log_message(f"Processing targeted visualization frame {fn}/{tf} (shown {ds} detections)"))
            
            cap.release()
            out.release()
            
            self.log_message(f"Targeted visualization completed: {output_path}")
            self.log_message(f"Total detections highlighted: {detections_shown}")
            self.root.after(0, lambda: messagebox.showinfo("Success", 
                f"Targeted visualization created: {output_path}\n"
                f"Highlighted {detections_shown} detections of '{target_plate}'"))
            
        except Exception as e:
            self.log_message(f"Targeted visualization error: {str(e)}")

    def create_enhanced_visualization_video(self, data):
        """Create enhanced visualization video with vehicle info"""
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
                            
                            # Add enhanced information
                            if row['license_number'] != '0':
                                license_text = row['license_number']
                                vehicle_type = row.get('vehicle_type', 'unknown')
                                vehicle_color = row.get('vehicle_color', 'unknown')
                                
                                # Calculate text position
                                text_x = int((car_bbox[0] + car_bbox[2]) / 2)
                                text_y = int(car_bbox[1]) - 80
                                
                                # Enhanced info text
                                info_text = f"{license_text} | {vehicle_color.title()} {vehicle_type.title()}"
                                
                                # Create background for text
                                (text_width, text_height), _ = cv2.getTextSize(
                                    info_text, cv2.FONT_HERSHEY_SIMPLEX, 1.5, 3)
                                
                                cv2.rectangle(frame, 
                                            (text_x - text_width//2 - 10, text_y - text_height - 10),
                                            (text_x + text_width//2 + 10, text_y + 10),
                                            (255, 255, 255), -1)
                                
                                # Add enhanced text
                                cv2.putText(frame, info_text,
                                          (text_x - text_width//2, text_y),
                                          cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 3)
                    
                    except Exception as e:
                        continue  # Skip problematic annotations
                
                out.write(frame)
                frame_nmr += 1
                
                # Update status periodically - schedule on main thread
                if frame_nmr % 30 == 0:
                    self.root.after(0, lambda fn=frame_nmr, tf=total_frames: 
                                   self.log_message(f"Processing enhanced visualization frame {fn}/{tf}"))
            
            cap.release()
            out.release()
            
            self.log_message(f"Enhanced visualization completed: {output_path}")
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Enhanced visualization video created: {output_path}"))
            
        except Exception as e:
            self.log_message(f"Enhanced visualization error: {str(e)}")

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

    def browse_output_dir(self):
        """Browse for output directory"""
        directory = filedialog.askdirectory(title="Select Output Directory")
        if directory:
            self.output_dir_var.set(directory)

    def save_settings(self):
        """Save current enhanced settings"""
        self.settings.update({
            'detection_confidence': self.confidence_var.get(),
            'tracking_enabled': self.tracking_var.get(),
            'interpolation_enabled': self.interpolation_var.get(),
            'save_screenshots': self.screenshots_var.get(),
            'output_directory': self.output_dir_var.get(),
            'color_detection_enabled': self.color_detection_var.get(),
            'vehicle_type_detection': self.vehicle_type_var.get()
        })
        
        try:
            with open('enhanced_lpr_settings.json', 'w') as f:
                json.dump(self.settings, f, indent=2)
            self.log_message("Enhanced settings saved successfully")
            messagebox.showinfo("Success", "Settings saved successfully!")
        except Exception as e:
            self.log_message(f"Error saving settings: {e}")
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def load_settings(self):
        """Load enhanced settings from file"""
        try:
            with open('enhanced_lpr_settings.json', 'r') as f:
                loaded_settings = json.load(f)
                self.settings.update(loaded_settings)
        except FileNotFoundError:
            # Use default settings
            pass
        except Exception as e:
            print(f"Error loading settings: {e}")

    def run(self):
        """Run the enhanced application"""
        self.log_message("Enhanced License Plate Recognition System v2.0 Started")
        self.log_message("New features: Vehicle color detection, type identification, timestamp display")
        self.log_message("Enhanced interpolation with NaN handling and improved visualization")
        self.log_message("Select a video file to begin processing")
        
        # Check for required models
        if not YOLO_AVAILABLE:
            self.log_message("Warning: YOLO not available. Install with: pip install ultralytics")
        elif not os.path.exists('license_plate_detector.pt'):
            self.log_message("Warning: license_plate_detector.pt not found. Download from the project repository.")
        
        if not EASYOCR_AVAILABLE:
            self.log_message("Warning: EasyOCR not available. Install with: pip install easyocr")
        
        if not SCIPY_AVAILABLE:
            self.log_message("Warning: SciPy not available. Interpolation disabled. Install with: pip install scipy")
        
        self.root.mainloop()


if __name__ == "__main__":
    print("Enhanced License Plate Recognition System v2.0")
    print("=" * 60)
    print("ðŸš— New Features:")
    print("  â€¢ Vehicle color detection (red, blue, white, black, etc.)")
    print("  â€¢ Vehicle type identification (car, truck, bus, motorcycle)")
    print("  â€¢ Timestamp display instead of frame numbers")
    print("  â€¢ Enhanced NaN handling in interpolation")
    print("  â€¢ Improved visualization with vehicle info")
    print("  â€¢ Duration tracking for vehicles")
    print("=" * 60)
    
    required_packages = [
        'ultralytics', 'opencv-python', 'pandas', 'numpy', 
        'easyocr', 'scipy', 'Pillow', 'webcolors'
    ]
    
    print("Required packages:", ', '.join(required_packages))
    print("Install with: pip install " + ' '.join(required_packages))
    print("=" * 60)
    
    try:
        app = EnhancedLicensePlateRecognitionSystem()
        app.run()
    except Exception as e:
        print(f"Error starting enhanced application: {e}")
        input("Press Enter to exit...") 