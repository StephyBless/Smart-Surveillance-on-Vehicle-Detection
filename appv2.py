# appv2.py
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
import math
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Optional libraries
try:
    import folium
    import webbrowser
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False
    print("Warning: folium not available. Map visualization disabled.")

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

try:
    from sort.sort import Sort
    SORT_AVAILABLE = True
except ImportError:
    SORT_AVAILABLE = False
    print("Warning: SORT tracker not available. Tracking disabled.")


class GPSLocationService:
    """Handles GPS location tracking and geofencing (demo/simulated)"""
    def __init__(self):
        self.current_location = {'lat': 0.0, 'lon': 0.0, 'timestamp': None}
        self.location_history = []
        self.geofences = []
        self.tracking_active = False
        self.location_update_interval = 10  # seconds
        self.location_thread = None

    def start_tracking(self):
        self.tracking_active = True
        self.location_thread = threading.Thread(target=self._location_tracking_loop, daemon=True)
        self.location_thread.start()

    def stop_tracking(self):
        self.tracking_active = False

    def _location_tracking_loop(self):
        while self.tracking_active:
            try:
                location = self._get_current_location()
                if location:
                    self.current_location = location
                    self.location_history.append(location.copy())
                    self._check_geofences(location)
                    if len(self.location_history) > 1000:
                        self.location_history = self.location_history[-500:]
                time.sleep(self.location_update_interval)
            except Exception as e:
                print(f"GPS tracking error: {e}")
                time.sleep(30)

    def _get_current_location(self):
        try:
            import random
            base_lat = 11.4438
            base_lon = 77.7242
            lat_offset = random.uniform(-0.001, 0.001)
            lon_offset = random.uniform(-0.001, 0.001)
            return {
                'lat': base_lat + lat_offset,
                'lon': base_lon + lon_offset,
                'timestamp': datetime.now(),
                'accuracy': random.uniform(5, 15)
            }
        except Exception as e:
            print(f"Error getting GPS location: {e}")
            return None

    def add_geofence(self, name, lat, lon, radius, alert_type="exit"):
        geofence = {
            'id': len(self.geofences),
            'name': name,
            'lat': float(lat),
            'lon': float(lon),
            'radius': float(radius),
            'alert_type': alert_type,
            'last_status': None,
            'created': datetime.now()
        }
        self.geofences.append(geofence)
        return geofence['id']

    def remove_geofence(self, geofence_id):
        self.geofences = [gf for gf in self.geofences if gf['id'] != geofence_id]

    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        R = 6371000
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        a = (math.sin(delta_lat/2) * math.sin(delta_lat/2) +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon/2) * math.sin(delta_lon/2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

    def _check_geofences(self, location):
        for geofence in self.geofences:
            distance = self._calculate_distance(
                location['lat'], location['lon'],
                geofence['lat'], geofence['lon']
            )
            inside_fence = distance <= geofence['radius']
            if geofence['last_status'] != inside_fence:
                if geofence['alert_type'] in ['exit', 'both'] and geofence['last_status'] == True and not inside_fence:
                    # create alert payload
                    alert_payload = {'geofence': geofence, 'alert_type': 'exit', 'location': location, 'timestamp': location['timestamp']}
                    # We'll expect parent to register callback
                    if hasattr(self, 'alert_callback'):
                        try:
                            self.alert_callback('geofence', alert_payload)
                        except Exception:
                            pass
                elif geofence['alert_type'] in ['enter', 'both'] and geofence['last_status'] == False and inside_fence:
                    alert_payload = {'geofence': geofence, 'alert_type': 'enter', 'location': location, 'timestamp': location['timestamp']}
                    if hasattr(self, 'alert_callback'):
                        try:
                            self.alert_callback('geofence', alert_payload)
                        except Exception:
                            pass
                geofence['last_status'] = inside_fence


class AlertSystem:
    """Simple alert management + email sending"""
    def __init__(self):
        self.alert_callbacks = []
        self.email_config = {}

    def add_callback(self, callback):
        self.alert_callbacks.append(callback)

    def configure_email(self, smtp_server, smtp_port, username, password, from_email):
        self.email_config = {
            'smtp_server': smtp_server,
            'smtp_port': smtp_port,
            'username': username,
            'password': password,
            'from_email': from_email
        }

    def send_email_alert(self, to_email, subject, message):
        try:
            if not self.email_config:
                return False
            msg = MIMEMultipart()
            msg['From'] = self.email_config['from_email']
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(message, 'plain'))
            with smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port']) as server:
                server.starttls()
                server.login(self.email_config['username'], self.email_config['password'])
                server.send_message(msg)
            return True
        except Exception as e:
            print(f"Failed to send email alert: {e}")
            return False

    def trigger_alert(self, alert_type, data):
        for callback in self.alert_callbacks:
            try:
                callback(alert_type, data)
            except Exception as e:
                print(f"Alert callback error: {e}")


class EnhancedLicensePlateRecognitionSystem:
    def __init__(self):
        # GUI and app state
        self.root = tk.Tk()
        self.is_processing = False
        self.video_source = None
        self.cap = None
        self.current_frame = None
        self.video_fps = 30

        # Data and results
        self.results = {}
        self.processed_data = []
        self.interpolated_data = []

        # Models
        self.coco_model = None
        self.license_plate_detector = None
        self.mot_tracker = None
        self.ocr_reader = None

        # Vehicle mapping
        self.vehicles = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

        # Color detection parameters
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

        # Search/watchlist
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
            'vehicle_type_detection': True,
            'gps_tracking_enabled': True,
            'geofencing_enabled': True,
            'location_update_interval': 10,
            'email_alerts_enabled': False,
            'alert_email': ''
        }

        # GPS and alerts
        self.gps_service = GPSLocationService()
        self.alert_system = AlertSystem()
        # connect gps_service alerts to local handler if needed
        self.gps_service.alert_callback = self._gps_alert_callback

        # Load settings, init models and GUI
        self.load_settings()
        self.initialize_models()
        self.setup_gui()
        self.setup_alert_system()

    # -----------------------------
    # Initialization helpers
    # -----------------------------
    def initialize_models(self):
        if YOLO_AVAILABLE:
            try:
                self.log_message("Loading YOLO models...")
                self.coco_model = YOLO('yolov8n.pt')
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

    def setup_alert_system(self):
        self.alert_system.add_callback(self.handle_alert)

    def _gps_alert_callback(self, kind, payload):
        try:
            self.handle_alert(kind, payload)
        except Exception:
            pass

    def handle_alert(self, alert_type, data):
        if alert_type == 'geofence':
            self.handle_geofence_alert(data)
        elif alert_type == 'theft':
            self.handle_theft_alert(data)

    def handle_geofence_alert(self, data):
        geofence = data.get('geofence', {})
        alert_type = data.get('alert_type', '')
        location = data.get('location', {})
        timestamp = data.get('timestamp', datetime.now())
        message = f"GEOFENCE ALERT!\n\n"
        message += f"Geofence: {geofence.get('name', 'N/A')}\n"
        message += f"Action: Vehicle {alert_type}\n"
        if location:
            message += f"Location: {location.get('lat', 0):.6f}, {location.get('lon', 0):.6f}\n"
        message += f"Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"

        # show dialog on main thread
        try:
            self.root.after(0, lambda: messagebox.showwarning("Geofence Alert", message))
        except Exception:
            pass

        if self.settings.get('email_alerts_enabled') and self.settings.get('alert_email'):
            try:
                self.alert_system.send_email_alert(self.settings['alert_email'],
                                                   f"Vehicle Geofence Alert - {geofence.get('name', '')}",
                                                   message)
            except Exception:
                pass
        self.log_message(f"GEOFENCE ALERT: {geofence.get('name', 'N/A')} - Vehicle {alert_type}")

    def handle_theft_alert(self, data):
        license_plate = data.get('license_plate', 'N/A')
        location = data.get('location')
        message = f"THEFT ALERT!\n\nLicense Plate: {license_plate}\n"
        if location:
            try:
                message += f"Location: {location['lat']:.6f}, {location['lon']:.6f}\n"
                message += f"Time: {location['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}\n"
            except Exception:
                pass
        try:
            self.root.after(0, lambda: messagebox.showerror("Theft Alert", message))
        except Exception:
            pass

        if self.settings.get('email_alerts_enabled') and self.settings.get('alert_email'):
            try:
                self.alert_system.send_email_alert(self.settings['alert_email'],
                                                   f"THEFT ALERT - {license_plate}",
                                                   message)
            except Exception:
                pass
        self.log_message(f"THEFT ALERT: {license_plate}")

    # -----------------------------
    # GUI Setup
    # -----------------------------
    def setup_gui(self):
        self.root.title("STOLEN VEHICLE DETECTION SYSTEM WITH GPS TRACKING")
        self.root.geometry("1500x950")
        self.root.configure(bg='#2c3e50')

        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'))
        style.configure('Header.TLabel', font=('Arial', 12, 'bold'))

        main_container = tk.Frame(self.root, bg='#2c3e50')
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        title_label = tk.Label(main_container, text="STOLEN VEHICLE DETECTION SYSTEM", font=('Arial', 18, 'bold'),
                               bg='#2c3e50', fg='white')
        title_label.pack(pady=10)

        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self.setup_processing_tab()
        self.setup_search_tab()
        self.setup_gps_tracking_tab()
        self.setup_geofencing_tab()
        self.setup_results_tab()
        self.setup_settings_tab()

        self.setup_status_bar(main_container)

    def setup_processing_tab(self):
        processing_frame = ttk.Frame(self.notebook)
        self.notebook.add(processing_frame, text="Video Processing")

        left_panel = ttk.LabelFrame(processing_frame, text="Controls", padding=10)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        ttk.Label(left_panel, text="Video Source:", style='Header.TLabel').pack(anchor=tk.W)
        ttk.Button(left_panel, text="Select Video File", command=self.select_video_file).pack(fill=tk.X, pady=2)
        ttk.Button(left_panel, text="Use Webcam", command=self.use_webcam).pack(fill=tk.X, pady=2)

        ttk.Separator(left_panel, orient='horizontal').pack(fill=tk.X, pady=10)

        ttk.Label(left_panel, text="Processing:", style='Header.TLabel').pack(anchor=tk.W)
        ttk.Button(left_panel, text="Start Processing", command=self.start_processing).pack(fill=tk.X, pady=2)
        ttk.Button(left_panel, text="Stop Processing", command=self.stop_processing).pack(fill=tk.X, pady=2)

        ttk.Separator(left_panel, orient='horizontal').pack(fill=tk.X, pady=10)

        ttk.Label(left_panel, text="GPS Tracking:", style='Header.TLabel').pack(anchor=tk.W)
        ttk.Button(left_panel, text="Start GPS Tracking", command=self.start_gps_tracking).pack(fill=tk.X, pady=2)
        ttk.Button(left_panel, text="Stop GPS Tracking", command=self.stop_gps_tracking).pack(fill=tk.X, pady=2)
        ttk.Button(left_panel, text="View Current Location", command=self.show_current_location).pack(fill=tk.X, pady=2)

        ttk.Label(left_panel, text="Data Operations:", style='Header.TLabel').pack(anchor=tk.W)
        ttk.Button(left_panel, text="Interpolate Missing Data", command=self.interpolate_data).pack(fill=tk.X, pady=2)
        ttk.Button(left_panel, text="Export to CSV", command=self.export_csv).pack(fill=tk.X, pady=2)
        ttk.Button(left_panel, text="Create Visualization", command=self.create_visualization).pack(fill=tk.X, pady=2)

        ttk.Separator(left_panel, orient='horizontal').pack(fill=tk.X, pady=10)

        stats_frame = ttk.LabelFrame(left_panel, text="Statistics")
        stats_frame.pack(fill=tk.X, pady=5)

        self.stats_labels = {
            'frames_processed': tk.Label(stats_frame, text="Frames: 0", bg='white'),
            'plates_detected': tk.Label(stats_frame, text="Plates: 0", bg='white'),
            'unique_plates': tk.Label(stats_frame, text="Unique: 0", bg='white'),
            'processing_fps': tk.Label(stats_frame, text="FPS: 0", bg='white'),
            'video_time': tk.Label(stats_frame, text="Video Time: 00:00", bg='white'),
            'gps_status': tk.Label(stats_frame, text="GPS: Inactive", bg='white'),
            'current_location': tk.Label(stats_frame, text="Location: Unknown", bg='white')
        }

        for label in self.stats_labels.values():
            label.pack(anchor=tk.W, padx=5)

        right_panel = ttk.LabelFrame(processing_frame, text="Live Preview", padding=10)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.video_label = tk.Label(right_panel, bg="black", text="No video loaded", fg="white", font=('Arial', 14))
        self.video_label.pack(expand=True, fill=tk.BOTH)

    def setup_search_tab(self):
        search_frame = ttk.Frame(self.notebook)
        self.notebook.add(search_frame, text="Search & Analysis")

        search_controls = ttk.LabelFrame(search_frame, text="Search Controls", padding=10)
        search_controls.pack(fill=tk.X, padx=5, pady=5)

        input_frame = ttk.Frame(search_controls)
        input_frame.pack(fill=tk.X)

        ttk.Label(input_frame, text="Target License Plate:").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(input_frame, font=('Arial', 12))
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(input_frame, text="Search", command=self.search_license_plate).pack(side=tk.LEFT)
        ttk.Button(input_frame, text="Add to Watch List", command=self.add_to_watch_list).pack(side=tk.LEFT, padx=5)

        options_frame = ttk.Frame(search_controls)
        options_frame.pack(fill=tk.X, pady=5)

        ttk.Label(options_frame, text="Similarity Threshold:").pack(side=tk.LEFT)
        self.similarity_var = tk.DoubleVar(value=0.8)
        similarity_scale = ttk.Scale(options_frame, from_=0.5, to=1.0, variable=self.similarity_var, orient=tk.HORIZONTAL)
        similarity_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        ttk.Button(options_frame, text="Show All Plates", command=self.show_all_plates).pack(side=tk.RIGHT)

        results_frame = ttk.LabelFrame(search_frame, text="Search Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ('Plate', 'Detections', 'Car ID', 'First Time', 'Last Time', 'Duration', 'Vehicle Type', 'Color', 'Avg Confidence')
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=10)
        column_widths = {
            'Plate': 100, 'Detections': 80, 'Car ID': 60, 'First Time': 80, 'Last Time': 80, 'Duration': 70,
            'Vehicle Type': 100, 'Color': 80, 'Avg Confidence': 100
        }
        for col in columns:
            self.results_tree.heading(col, text=col)
            self.results_tree.column(col, width=column_widths.get(col, 80), anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.results_tree.bind('<Double-1>', self.on_result_double_click)

    def setup_gps_tracking_tab(self):
        gps_frame = ttk.Frame(self.notebook)
        self.notebook.add(gps_frame, text="Live GPS Tracking")

        control_panel = ttk.LabelFrame(gps_frame, text="GPS Controls", padding=10)
        control_panel.pack(fill=tk.X, padx=5, pady=5)

        controls_frame = ttk.Frame(control_panel)
        controls_frame.pack(fill=tk.X)

        ttk.Button(controls_frame, text="Start GPS Tracking", command=self.start_gps_tracking).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Stop GPS Tracking", command=self.stop_gps_tracking).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Show Live Map", command=self.show_live_map).pack(side=tk.LEFT, padx=5)

        info_frame = ttk.LabelFrame(gps_frame, text="Current Location", padding=10)
        info_frame.pack(fill=tk.X, padx=5, pady=5)

        self.gps_info_labels = {
            'status': tk.Label(info_frame, text="Status: Inactive", font=('Arial', 12, 'bold')),
            'latitude': tk.Label(info_frame, text="Latitude: --", font=('Arial', 11)),
            'longitude': tk.Label(info_frame, text="Longitude: --", font=('Arial', 11)),
            'last_update': tk.Label(info_frame, text="Last Update: --", font=('Arial', 11))
        }
        for label in self.gps_info_labels.values():
            label.pack(anchor=tk.W, padx=5, pady=2)
        self.update_gps_display()

    def setup_geofencing_tab(self):
        geo_frame = ttk.Frame(self.notebook)
        self.notebook.add(geo_frame, text="Geofencing")
        controls_panel = ttk.LabelFrame(geo_frame, text="Geofence Management", padding=10)
        controls_panel.pack(fill=tk.X, padx=5, pady=5)

        add_frame = ttk.Frame(controls_panel)
        add_frame.pack(fill=tk.X, pady=5)

        ttk.Label(add_frame, text="Name:").pack(side=tk.LEFT)
        self.geofence_name_entry = ttk.Entry(add_frame, width=15)
        self.geofence_name_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(add_frame, text="Lat:").pack(side=tk.LEFT)
        self.geofence_lat_entry = ttk.Entry(add_frame, width=12)
        self.geofence_lat_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(add_frame, text="Lon:").pack(side=tk.LEFT)
        self.geofence_lon_entry = ttk.Entry(add_frame, width=12)
        self.geofence_lon_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(add_frame, text="Radius(m):").pack(side=tk.LEFT)
        self.geofence_radius_entry = ttk.Entry(add_frame, width=8)
        self.geofence_radius_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(add_frame, text="Alert:").pack(side=tk.LEFT)
        self.alert_type_var = tk.StringVar(value="exit")
        alert_combo = ttk.Combobox(add_frame, textvariable=self.alert_type_var, values=["enter", "exit", "both"], width=8, state="readonly")
        alert_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(add_frame, text="Add Geofence", command=self.add_geofence).pack(side=tk.LEFT, padx=10)

    def setup_results_tab(self):
        results_frame = ttk.Frame(self.notebook)
        self.notebook.add(results_frame, text="Detailed Results")

        text_frame = ttk.Frame(results_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.results_text = tk.Text(text_frame, wrap=tk.WORD, font=('Consolas', 10))
        results_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=results_scrollbar.set)
        self.results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        results_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def setup_settings_tab(self):
        settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(settings_frame, text="Settings")

        gps_frame = ttk.LabelFrame(settings_frame, text="GPS & Geofencing Settings", padding=10)
        gps_frame.pack(fill=tk.X, padx=5, pady=5)

        self.gps_tracking_var = tk.BooleanVar(value=self.settings.get('gps_tracking_enabled', True))
        ttk.Checkbutton(gps_frame, text="Enable GPS Tracking", variable=self.gps_tracking_var).pack(anchor=tk.W)

        self.geofencing_var = tk.BooleanVar(value=self.settings.get('geofencing_enabled', True))
        ttk.Checkbutton(gps_frame, text="Enable Geofencing Alerts", variable=self.geofencing_var).pack(anchor=tk.W)

        ttk.Label(gps_frame, text="Location Update Interval (seconds):").pack(anchor=tk.W)
        self.update_interval_var = tk.IntVar(value=self.settings.get('location_update_interval', 10))
        interval_scale = ttk.Scale(gps_frame, from_=5, to=60, variable=self.update_interval_var, orient=tk.HORIZONTAL)
        interval_scale.pack(fill=tk.X, pady=2)

        alert_frame = ttk.LabelFrame(settings_frame, text="Alert Settings", padding=10)
        alert_frame.pack(fill=tk.X, padx=5, pady=5)

        self.email_alerts_var = tk.BooleanVar(value=self.settings.get('email_alerts_enabled', False))
        ttk.Checkbutton(alert_frame, text="Enable Email Alerts", variable=self.email_alerts_var).pack(anchor=tk.W)

        email_frame = ttk.Frame(alert_frame)
        email_frame.pack(fill=tk.X, pady=5)
        ttk.Label(email_frame, text="Alert Email:").pack(side=tk.LEFT)
        self.alert_email_var = tk.StringVar(value=self.settings.get('alert_email', ''))
        ttk.Entry(email_frame, textvariable=self.alert_email_var, width=30).pack(side=tk.LEFT, padx=5)

        detection_frame = ttk.LabelFrame(settings_frame, text="Detection Settings", padding=10)
        detection_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(detection_frame, text="Detection Confidence Threshold:").pack(anchor=tk.W)
        self.confidence_var = tk.DoubleVar(value=self.settings['detection_confidence'])
        confidence_scale = ttk.Scale(detection_frame, from_=0.1, to=0.9, variable=self.confidence_var, orient=tk.HORIZONTAL)
        confidence_scale.pack(fill=tk.X, pady=2)

        self.tracking_var = tk.BooleanVar(value=self.settings['tracking_enabled'])
        ttk.Checkbutton(detection_frame, text="Enable Vehicle Tracking", variable=self.tracking_var).pack(anchor=tk.W)

        self.interpolation_var = tk.BooleanVar(value=self.settings['interpolation_enabled'])
        ttk.Checkbutton(detection_frame, text="Enable Data Interpolation", variable=self.interpolation_var).pack(anchor=tk.W)

        self.screenshots_var = tk.BooleanVar(value=self.settings['save_screenshots'])
        ttk.Checkbutton(detection_frame, text="Save Detection Screenshots", variable=self.screenshots_var).pack(anchor=tk.W)

        self.color_detection_var = tk.BooleanVar(value=self.settings.get('color_detection_enabled', True))
        ttk.Checkbutton(detection_frame, text="Enable Vehicle Color Detection", variable=self.color_detection_var).pack(anchor=tk.W)

        self.vehicle_type_var = tk.BooleanVar(value=self.settings.get('vehicle_type_detection', True))
        ttk.Checkbutton(detection_frame, text="Enable Vehicle Type Detection", variable=self.vehicle_type_var).pack(anchor=tk.W)

        output_frame = ttk.LabelFrame(settings_frame, text="Output Settings", padding=10)
        output_frame.pack(fill=tk.X, padx=5, pady=5)

        dir_frame = ttk.Frame(output_frame)
        dir_frame.pack(fill=tk.X)
        ttk.Label(dir_frame, text="Output Directory:").pack(side=tk.LEFT)
        self.output_dir_var = tk.StringVar(value=self.settings['output_directory'])
        ttk.Entry(dir_frame, textvariable=self.output_dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(dir_frame, text="Browse", command=self.browse_output_dir).pack(side=tk.RIGHT)

        ttk.Button(output_frame, text="Save Settings", command=self.save_settings).pack(pady=10)

    def setup_status_bar(self, parent):
        status_frame = tk.Frame(parent, bg='#34495e', height=30)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)

        self.status_label = tk.Label(status_frame, text="Ready", bg='#34495e', fg='white', font=('Arial', 10))
        self.status_label.pack(side=tk.LEFT, padx=10, pady=5)

        self.progress_var = tk.DoubleVar()
        style = ttk.Style()
        style.configure("Green.Horizontal.TProgressbar",
                        background="#ffffff",
                        troughcolor='#2c3e50',
                        borderwidth=1,
                        lightcolor="#cbcbcb",
                        darkcolor="#9d9d9d")
        self.progress_bar = ttk.Progressbar(status_frame, variable=self.progress_var, mode='determinate',
                                            style="Green.Horizontal.TProgressbar")
        self.progress_bar.pack(side=tk.RIGHT, padx=10, pady=5, fill=tk.X, expand=True)

    # -----------------------------
    # Logging and helpers
    # -----------------------------
    def log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        if hasattr(self, 'results_text'):
            try:
                self.root.after(0, lambda: self._update_results_text(log_entry))
            except Exception:
                pass
        if hasattr(self, 'status_label'):
            status_text = message[:50] + "..." if len(message) > 50 else message
            try:
                self.root.after(0, lambda: self.status_label.configure(text=status_text))
            except Exception:
                pass
        print(log_entry.strip())

    def _update_results_text(self, log_entry):
        try:
            self.results_text.insert(tk.END, log_entry)
            self.results_text.see(tk.END)
        except Exception:
            pass

    # -----------------------------
    # Video source and processing
    # -----------------------------
    def select_video_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv"), ("All files", "*.*")]
        )
        if file_path:
            self.video_source = file_path
            temp_cap = cv2.VideoCapture(file_path)
            if temp_cap.isOpened():
                self.video_fps = temp_cap.get(cv2.CAP_PROP_FPS) or self.video_fps
                temp_cap.release()
            self.log_message(f"Selected video: {os.path.basename(file_path)} (FPS: {self.video_fps:.2f})")

    def use_webcam(self):
        self.video_source = 0
        self.video_fps = 30
        self.log_message("Set to use webcam")

    def start_processing(self):
        if not self.video_source:
            messagebox.showerror("Error", "Please select a video source first")
            return
        if not YOLO_AVAILABLE or not self.coco_model or not self.license_plate_detector:
            messagebox.showerror("Error", "Required models are not available. Please check YOLO installation.")
            return
        self.is_processing = True
        self.results = {}
        self.processed_data.clear()
        self.interpolated_data.clear()
        self.processing_thread = threading.Thread(target=self.processing_loop, daemon=True)
        self.processing_thread.start()
        self.log_message("Started enhanced video processing...")

    def stop_processing(self):
        self.is_processing = False
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
        self.log_message("Processing stopped")

    def processing_loop(self):
        try:
            self.cap = cv2.VideoCapture(self.video_source)
            if not self.cap.isOpened():
                self.log_message("Error: Cannot open video source")
                return

            total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)) if self.video_source != 0 else 0
            self.video_fps = self.cap.get(cv2.CAP_PROP_FPS) or self.video_fps

            frame_nmr = -1
            start_time = time.time()

            while self.is_processing and self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret:
                    break

                frame_nmr += 1
                self.current_frame = frame.copy()

                if total_frames > 0:
                    progress = (frame_nmr / total_frames) * 100
                    try:
                        self.root.after(0, lambda p=progress: self.progress_var.set(p))
                    except Exception:
                        pass

                # Main frame processing (GPS integrated)
                self.process_frame_with_gps(frame, frame_nmr)

                try:
                    self.root.after(0, lambda f=frame.copy(): self.update_video_display(f))
                except Exception:
                    pass

                try:
                    self.root.after(0, lambda fn=frame_nmr, st=start_time: self.update_statistics_enhanced(fn, st))
                except Exception:
                    pass

                time.sleep(0.01)

            try:
                self.cap.release()
            except Exception:
                pass

            self.log_message("Enhanced video processing completed")
            try:
                self.root.after(0, self.export_csv)  # ensure correct method name
            except Exception:
                pass

        except Exception as e:
            self.log_message(f"Error during processing: {str(e)}")
        finally:
            self.is_processing = False

    # -----------------------------
    # Frame processing & OCR
    # -----------------------------
    def process_frame_with_gps(self, frame, frame_nmr):
        try:
            self.results[frame_nmr] = {}
            timestamp = frame_nmr / (self.video_fps or 1)
            current_gps = None
            if self.gps_service.tracking_active and self.gps_service.current_location.get('timestamp'):
                current_gps = self.gps_service.current_location.copy()

            # Detect vehicles
            detections = self.coco_model(frame, conf=self.confidence_var.get())[0]
            detections_ = []
            vehicle_types = {}

            for detection in detections.boxes.data.tolist():
                x1, y1, x2, y2, score, class_id = detection
                if int(class_id) in self.vehicles:
                    detections_.append([x1, y1, x2, y2, score])
                    vehicle_types[(x1, y1, x2, y2)] = self.vehicles[int(class_id)]

            # Track vehicles using SORT if enabled
            if self.tracking_var.get() and self.mot_tracker:
                try:
                    track_ids = self.mot_tracker.update(np.asarray(detections_))
                except Exception:
                    track_ids = [[*det, i] for i, det in enumerate(detections_)]
            else:
                track_ids = [[*det, i] for i, det in enumerate(detections_)]

            # Detect license plates
            if self.license_plate_detector:
                license_plates = self.license_plate_detector(frame, conf=0.3)[0]
                for license_plate in license_plates.boxes.data.tolist():
                    x1, y1, x2, y2, score, class_id = license_plate
                    car_match = self.get_car(license_plate, track_ids)
                    if car_match:
                        xcar1, ycar1, xcar2, ycar2, car_id = car_match
                        vehicle_crop = frame[int(ycar1):int(ycar2), int(xcar1):int(xcar2)]
                        vehicle_color = "unknown"
                        vehicle_type = "unknown"

                        if self.color_detection_var.get():
                            vehicle_color = self.detect_vehicle_color(vehicle_crop)

                        if self.vehicle_type_var.get():
                            for (vx1, vy1, vx2, vy2), vtype in vehicle_types.items():
                                if abs(vx1 - xcar1) < 50 and abs(vy1 - ycar1) < 50:
                                    vehicle_type = vtype
                                    break

                        license_text, text_score = self.read_license_plate(frame, x1, y1, x2, y2)

                        if license_text:
                            if license_text in self.target_plates:
                                # push theft alert payload
                                self.alert_system.trigger_alert('theft', {
                                    'license_plate': license_text,
                                    'location': current_gps,
                                    'vehicle_type': vehicle_type,
                                    'vehicle_color': vehicle_color
                                })
                                # local handler too
                                try:
                                    self.handle_theft_alert({
                                        'license_plate': license_text,
                                        'location': current_gps
                                    })
                                except Exception:
                                    pass

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
                                'vehicle_type': vehicle_type,
                                'gps_location': current_gps
                            }

                            processed_entry = {
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
                            }

                            if current_gps:
                                processed_entry.update({
                                    'gps_latitude': current_gps.get('lat', ''),
                                    'gps_longitude': current_gps.get('lon', ''),
                                    'gps_timestamp': current_gps.get('timestamp').isoformat() if current_gps.get('timestamp') else '',
                                    'gps_accuracy': current_gps.get('accuracy', '')
                                })
                            self.processed_data.append(processed_entry)

        except Exception as e:
            self.log_message(f"Error processing frame {frame_nmr}: {str(e)}")

    def get_car(self, license_plate, vehicle_track_ids):
        try:
            x1, y1, x2, y2, score, class_id = license_plate
        except Exception:
            return None
        try:
            for track in vehicle_track_ids:
                if len(track) >= 5:
                    xcar1, ycar1, xcar2, ycar2, car_id = track[:5]
                    if x1 > xcar1 and y1 > ycar1 and x2 < xcar2 and y2 < ycar2:
                        return [xcar1, ycar1, xcar2, ycar2, car_id]
            return None
        except Exception:
            return None

    def read_license_plate(self, frame, x1, y1, x2, y2):
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
            self.log_message(f"OCR error: {str(e)}")
            return None, 0

    def detect_vehicle_color(self, vehicle_crop):
        if vehicle_crop is None or getattr(vehicle_crop, 'size', 0) == 0:
            return "unknown"
        try:
            hsv = cv2.cvtColor(vehicle_crop, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, (0, 0, 50), (180, 255, 255))
            color_counts = {}
            for color_name, (lower, upper) in self.dominant_colors.items():
                color_mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
                combined_mask = cv2.bitwise_and(mask, color_mask)
                color_counts[color_name] = cv2.countNonZero(combined_mask)
            if color_counts and max(color_counts.values()) > 0:
                return max(color_counts, key=color_counts.get)
            return "unknown"
        except Exception:
            return "unknown"

    def update_video_display(self, frame):
        try:
            display_frame = cv2.resize(frame, (640, 480))
            rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_frame)
            photo = ImageTk.PhotoImage(pil_image)
            self.video_label.configure(image=photo)
            self.video_label.image = photo
        except Exception:
            pass

    def update_statistics_enhanced(self, frame_nmr, start_time):
        try:
            elapsed = time.time() - start_time
            fps = frame_nmr / elapsed if elapsed > 0 else 0
            video_time = frame_nmr / (self.video_fps or 1)
            minutes = int(video_time // 60)
            seconds = int(video_time % 60)
            time_str = f"{minutes:02d}:{seconds:02d}"
            plates_count = sum(len(frame_data) for frame_data in self.results.values())
            unique_plates = len(set(item['license_number'] for item in self.processed_data if 'license_number' in item))
            self.stats_labels['frames_processed'].configure(text=f"Frames: {frame_nmr}")
            self.stats_labels['plates_detected'].configure(text=f"Plates: {plates_count}")
            self.stats_labels['unique_plates'].configure(text=f"Unique: {unique_plates}")
            self.stats_labels['processing_fps'].configure(text=f"FPS: {fps:.1f}")
            self.stats_labels['video_time'].configure(text=f"Video Time: {time_str}")
            # GPS status
            gps_status = "Active" if self.gps_service.tracking_active else "Inactive"
            self.stats_labels['gps_status'].configure(text=f"GPS: {gps_status}")
            loc = self.gps_service.current_location
            if loc and loc.get('timestamp'):
                self.stats_labels['current_location'].configure(text=f"Location: {loc.get('lat',0):.6f},{loc.get('lon',0):.6f}")
            else:
                self.stats_labels['current_location'].configure(text="Location: Unknown")
        except Exception:
            pass

    # -----------------------------
    # Interpolation & data cleaning
    # -----------------------------
    def interpolate_data(self):
        if not self.processed_data:
            messagebox.showwarning("Warning", "No data to interpolate. Process a video first.")
            return
        if not SCIPY_AVAILABLE:
            messagebox.showerror("Error", "SciPy is required for interpolation but not available.")
            return
        self.log_message("Starting enhanced data interpolation with NaN handling...")
        try:
            data_for_interp = []
            for item in self.processed_data:
                try:
                    frame_nmr = float(item['frame_nmr'])
                    car_id = float(item['car_id'])
                    timestamp = float(item.get('timestamp', 0))
                    if (np.isnan(frame_nmr) or np.isnan(car_id) or np.isnan(timestamp)):
                        self.log_message(f"Skipping invalid data: frame {item.get('frame_nmr', 'N/A')}")
                        continue
                    data_for_interp.append({
                        'frame_nmr': str(int(frame_nmr)),
                        'car_id': str(int(car_id)),
                        'car_bbox': item['car_bbox'],
                        'license_plate_bbox': item['license_plate_bbox'],
                        'license_plate_bbox_score': str(item.get('license_plate_bbox_score', '0')),
                        'license_number': item.get('license_number', '0'),
                        'license_number_score': str(item.get('license_number_score', '0')),
                        'timestamp': str(timestamp),
                        'vehicle_color': item.get('vehicle_color', 'unknown'),
                        'vehicle_type': item.get('vehicle_type', 'unknown')
                    })
                except (ValueError, TypeError, KeyError) as e:
                    self.log_message(f"Skipping invalid data entry: {e}")
                    continue
            self.interpolated_data = self.interpolate_bounding_boxes_enhanced(data_for_interp)
            self.log_message(f"Enhanced interpolation completed. {len(self.interpolated_data)} records generated.")
        except Exception as e:
            self.log_message(f"Interpolation error: {str(e)}")
            messagebox.showerror("Error", f"Interpolation failed: {str(e)}")

    def interpolate_bounding_boxes_enhanced(self, data):
        if not SCIPY_AVAILABLE:
            return []
        from scipy.interpolate import interp1d
        if not data:
            return []
        interpolated_data = []
        try:
            cars_data = {}
            for row in data:
                try:
                    car_id = int(float(row['car_id']))
                    cars_data.setdefault(car_id, []).append(row)
                except Exception:
                    continue

            for car_id, car_rows in cars_data.items():
                if len(car_rows) < 2:
                    self.log_message(f"Skipping car {car_id}: insufficient data points ({len(car_rows)})")
                    continue
                try:
                    car_rows.sort(key=lambda x: int(float(x['frame_nmr'])))
                    frame_numbers = []
                    car_bboxes = []
                    lp_bboxes = []
                    timestamps = []
                    for row in car_rows:
                        try:
                            frame_num = int(float(row['frame_nmr']))
                            timestamp = float(row['timestamp'])
                            car_bbox = self.parse_bbox_string(row['car_bbox'])
                            lp_bbox = self.parse_bbox_string(row['license_plate_bbox'])
                            if car_bbox and lp_bbox and len(car_bbox) == 4 and len(lp_bbox) == 4:
                                if (not any(np.isnan(coord) for coord in car_bbox) and
                                        not any(np.isnan(coord) for coord in lp_bbox) and
                                        not np.isnan(timestamp)):
                                    frame_numbers.append(frame_num)
                                    car_bboxes.append(car_bbox)
                                    lp_bboxes.append(lp_bbox)
                                    timestamps.append(timestamp)
                        except Exception:
                            continue

                    if len(frame_numbers) < 2:
                        continue

                    frame_numbers = np.array(frame_numbers)
                    car_bboxes = np.array(car_bboxes)
                    lp_bboxes = np.array(lp_bboxes)
                    timestamps = np.array(timestamps)

                    first_frame = frame_numbers[0]
                    last_frame = frame_numbers[-1]
                    all_frames = np.arange(first_frame, last_frame + 1)

                    car_interp = interp1d(frame_numbers, car_bboxes, axis=0, kind='linear', bounds_error=False, fill_value='extrapolate')
                    lp_interp = interp1d(frame_numbers, lp_bboxes, axis=0, kind='linear', bounds_error=False, fill_value='extrapolate')
                    time_interp = interp1d(frame_numbers, timestamps, kind='linear', bounds_error=False, fill_value='extrapolate')

                    car_bboxes_interp = car_interp(all_frames)
                    lp_bboxes_interp = lp_interp(all_frames)
                    timestamps_interp = time_interp(all_frames)

                    vehicle_color = car_rows[0].get('vehicle_color', 'unknown')
                    vehicle_type = car_rows[0].get('vehicle_type', 'unknown')

                    for i, frame_num in enumerate(all_frames):
                        try:
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
                            if frame_num in frame_numbers:
                                orig_row = next(r for r in car_rows if int(float(r['frame_nmr'])) == frame_num)
                                row['license_plate_bbox_score'] = orig_row.get('license_plate_bbox_score', '0')
                                row['license_number'] = orig_row.get('license_number', '0')
                                row['license_number_score'] = orig_row.get('license_number_score', '0')
                            else:
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

    def parse_bbox_string(self, bbox_str):
        try:
            if isinstance(bbox_str, str):
                clean_str = bbox_str.strip('[]')
                coords = [float(x.strip()) for x in clean_str.split()]
                return coords if len(coords) == 4 else None
            return None
        except Exception:
            return None

    # -----------------------------
    # Search & results
    # -----------------------------
    def format_timestamp(self, timestamp):
        try:
            timestamp = float(timestamp)
            minutes = int(timestamp // 60)
            seconds = int(timestamp % 60)
            return f"{minutes:02d}:{seconds:02d}"
        except Exception:
            return "00:00"

    def search_license_plate(self):
        target_plate = self.search_entry.get().strip().upper()
        if not target_plate:
            messagebox.showwarning("Warning", "Please enter a license plate number to search.")
            return
        data_to_search = self.interpolated_data if self.interpolated_data else self.processed_data
        if not data_to_search:
            messagebox.showwarning("Warning", "No data to search. Process a video first.")
            return
        self.log_message(f"Searching for license plate: {target_plate}")
        self.results_tree.delete(*self.results_tree.get_children())
        df = pd.DataFrame(data_to_search)
        target_clean = ''.join(filter(str.isalnum, target_plate))
        exact_matches = df[df['license_number'].astype(str).str.replace(' ', '').str.upper() == target_clean] if 'license_number' in df.columns else pd.DataFrame()
        results_found = False
        if not exact_matches.empty:
            results_found = True
            self.log_message(f"Found {len(exact_matches)} exact matches")
            for car_id in exact_matches['car_id'].unique():
                car_matches = exact_matches[exact_matches['car_id'] == car_id]
                timestamps = car_matches['timestamp'].astype(float) if 'timestamp' in car_matches.columns else [0] * len(car_matches)
                first_time = self.format_timestamp(min(timestamps))
                last_time = self.format_timestamp(max(timestamps))
                duration_seconds = max(timestamps) - min(timestamps)
                duration = self.format_timestamp(duration_seconds)
                frame_count = len(car_matches)
                vehicle_type = car_matches.iloc[0].get('vehicle_type', 'unknown')
                vehicle_color = car_matches.iloc[0].get('vehicle_color', 'unknown')
                scores = car_matches['license_number_score'] if 'license_number_score' in car_matches.columns else pd.Series([])
                valid_scores = scores[scores != '0'].astype(float) if not scores.empty else pd.Series([])
                avg_confidence = valid_scores.mean() if not valid_scores.empty else 0
                self.results_tree.insert('', 'end', values=(target_plate, frame_count, car_id, first_time, last_time, duration, vehicle_type, vehicle_color, f"{avg_confidence:.2f}"))
        if not results_found:
            threshold = self.similarity_var.get()
            self.log_message(f"No exact matches. Searching with similarity threshold: {threshold}")
            fuzzy_matches = []
            unique_plates = df['license_number'].unique() if 'license_number' in df.columns else []
            for plate in unique_plates:
                if plate and plate != '0':
                    plate_clean = ''.join(filter(str.isalnum, str(plate).upper()))
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
                        scores = car_matches['license_number_score'] if 'license_number_score' in car_matches.columns else pd.Series([])
                        valid_scores = scores[scores != '0'].astype(float) if not scores.empty else pd.Series([])
                        avg_confidence = valid_scores.mean() if not valid_scores.empty else 0
                        display_text = f"{plate} (sim: {similarity:.2f})"
                        self.results_tree.insert('', 'end', values=(display_text, frame_count, car_id, first_time, last_time, duration, vehicle_type, vehicle_color, f"{avg_confidence:.2f}"))
        if not results_found:
            self.log_message("No matches found")
            messagebox.showinfo("No Results", f"No license plates found matching '{target_plate}'")

    def calculate_similarity(self, a, b):
        return SequenceMatcher(None, a, b).ratio()

    def show_all_plates(self):
        data_to_show = self.interpolated_data if self.interpolated_data else self.processed_data
        if not data_to_show:
            messagebox.showwarning("Warning", "No data available. Process a video first.")
            return
        self.results_tree.delete(*self.results_tree.get_children())
        df = pd.DataFrame(data_to_show)
        if 'license_number' not in df.columns:
            messagebox.showinfo("No Data", "No license_number field in processed data.")
            return
        unique_plates = df[df['license_number'] != '0']['license_number'].unique()
        self.log_message(f"Displaying {len(unique_plates)} unique license plates")
        for plate in unique_plates:
            plate_data = df[df['license_number'] == plate]
            for car_id in plate_data['car_id'].unique():
                car_matches = plate_data[plate_data['car_id'] == car_id]
                timestamps = car_matches['timestamp'].astype(float) if 'timestamp' in car_matches.columns else [0] * len(car_matches)
                first_time = self.format_timestamp(min(timestamps))
                last_time = self.format_timestamp(max(timestamps))
                duration_seconds = max(timestamps) - min(timestamps)
                duration = self.format_timestamp(duration_seconds)
                frame_count = len(car_matches)
                vehicle_type = car_matches.iloc[0].get('vehicle_type', 'unknown')
                vehicle_color = car_matches.iloc[0].get('vehicle_color', 'unknown')
                scores = car_matches['license_number_score'] if 'license_number_score' in car_matches.columns else pd.Series([])
                valid_scores = scores[scores != '0'].astype(float) if not scores.empty else pd.Series([])
                avg_confidence = valid_scores.mean() if not valid_scores.empty else 0
                self.results_tree.insert('', 'end', values=(plate, frame_count, car_id, first_time, last_time, duration, vehicle_type, vehicle_color, f"{avg_confidence:.2f}"))

    def on_result_double_click(self, event):
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

    # -----------------------------
    # Geofencing & watchlist
    # -----------------------------
    def add_geofence(self):
        try:
            name = self.geofence_name_entry.get().strip()
            lat = float(self.geofence_lat_entry.get())
            lon = float(self.geofence_lon_entry.get())
            radius = float(self.geofence_radius_entry.get())
            alert_type = self.alert_type_var.get()
            if not name or radius <= 0:
                messagebox.showerror("Error", "Please enter valid name and radius > 0")
                return
            geofence_id = self.gps_service.add_geofence(name, lat, lon, radius, alert_type)
            self.geofence_name_entry.delete(0, tk.END)
            self.geofence_lat_entry.delete(0, tk.END)
            self.geofence_lon_entry.delete(0, tk.END)
            self.geofence_radius_entry.delete(0, tk.END)
            self.log_message(f"Geofence '{name}' added (ID: {geofence_id})")
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numeric values")

    def add_to_watch_list(self):
        plate = self.search_entry.get().strip().upper()
        if not plate:
            messagebox.showwarning("Warning", "Please enter a license plate number")
            return
        if plate not in self.target_plates:
            self.target_plates.append(plate)
            self.log_message(f"Added '{plate}' to watch list for theft detection")
            messagebox.showinfo("Watch List", f"License plate '{plate}' added to watch list.")
        else:
            messagebox.showinfo("Already Watching", f"License plate '{plate}' is already in watch list")

    # -----------------------------
    # GPS UI & map
    # -----------------------------
    def start_gps_tracking(self):
        if not self.gps_service.tracking_active:
            self.gps_service.location_update_interval = self.settings.get('location_update_interval', 10)
            self.gps_service.start_tracking()
            self.log_message("GPS tracking started")

    def stop_gps_tracking(self):
        if self.gps_service.tracking_active:
            self.gps_service.stop_tracking()
            self.log_message("GPS tracking stopped")

    def show_current_location(self):
        location = self.gps_service.current_location
        if location.get('timestamp'):
            message = f"Current Location:\n\n"
            message += f"Latitude: {location['lat']:.6f}\n"
            message += f"Longitude: {location['lon']:.6f}\n"
            message += f"Last Update: {location['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
            messagebox.showinfo("Current Location", message)
        else:
            messagebox.showwarning("No Location", "GPS location not available")

    def show_live_map(self):
        if not FOLIUM_AVAILABLE:
            messagebox.showerror("Error", "Folium not available. Install with: pip install folium")
            return
        location = self.gps_service.current_location
        if not location.get('timestamp'):
            messagebox.showwarning("No Location", "GPS location not available")
            return
        try:
            m = folium.Map(location=[location['lat'], location['lon']], zoom_start=15)
            folium.Marker([location['lat'], location['lon']], popup=f"Current Location\n{location['timestamp'].strftime('%H:%M:%S')}",
                          icon=folium.Icon(color='red', icon='info-sign')).add_to(m)
            if len(self.gps_service.location_history) > 1:
                coordinates = [[loc['lat'], loc['lon']] for loc in self.gps_service.location_history[-10:]]
                folium.PolyLine(coordinates, color='blue', weight=3, opacity=0.7).add_to(m)
            for geofence in self.gps_service.geofences:
                color = 'green' if geofence['alert_type'] == 'enter' else 'red'
                folium.Circle(location=[geofence['lat'], geofence['lon']], radius=geofence['radius'],
                              popup=f"Geofence: {geofence['name']}", color=color, fillOpacity=0.2).add_to(m)
            output_dir = self.output_dir_var.get() if hasattr(self, 'output_dir_var') else self.settings.get('output_directory', './output')
            os.makedirs(output_dir, exist_ok=True)
            map_path = os.path.join(output_dir, 'live_map.html')
            m.save(map_path)
            webbrowser.open(f'file://{os.path.abspath(map_path)}')
            self.log_message(f"Live map opened: {map_path}")
        except Exception as e:
            messagebox.showerror("Map Error", f"Failed to create map: {str(e)}")

    def update_gps_display(self):
        try:
            location = self.gps_service.current_location
            if location.get('timestamp'):
                self.gps_info_labels['status'].configure(
                    text="Status: Active" if self.gps_service.tracking_active else "Status: Inactive",
                    fg='green' if self.gps_service.tracking_active else 'red'
                )
                self.gps_info_labels['latitude'].configure(text=f"Latitude: {location['lat']:.6f}")
                self.gps_info_labels['longitude'].configure(text=f"Longitude: {location['lon']:.6f}")
                self.gps_info_labels['last_update'].configure(text=f"Last Update: {location['timestamp'].strftime('%H:%M:%S')}")
            else:
                self.gps_info_labels['status'].configure(text="Status: No Data", fg='orange')
        except Exception:
            pass
        try:
            self.root.after(5000, self.update_gps_display)
        except Exception:
            pass

    # -----------------------------
    # Export, visualization, settings
    # -----------------------------
    def export_csv(self):
        if not self.processed_data and not self.interpolated_data:
            messagebox.showwarning("Warning", "No data to export. Process a video first.")
            return
        try:
            output_dir = self.output_dir_var.get() if hasattr(self, 'output_dir_var') else self.settings.get('output_directory', './output')
            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            processed_path = os.path.join(output_dir, f"processed_{timestamp}.csv")
            interpolated_path = os.path.join(output_dir, f"interpolated_{timestamp}.csv")
            # Save processed_data
            if self.processed_data:
                keys = sorted({k for d in self.processed_data for k in d.keys()})
                with open(processed_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=keys)
                    writer.writeheader()
                    for row in self.processed_data:
                        writer.writerow(row)
                self.log_message(f"Processed data exported: {processed_path}")
            # Save interpolated_data
            if self.interpolated_data:
                keys = sorted({k for d in self.interpolated_data for k in d.keys()})
                with open(interpolated_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=keys)
                    writer.writeheader()
                    for row in self.interpolated_data:
                        writer.writerow(row)
                self.log_message(f"Interpolated data exported: {interpolated_path}")
            messagebox.showinfo("Export Complete", f"Exported processed and interpolated data to:\n{output_dir}")
        except Exception as e:
            self.log_message(f"Export error: {e}")
            messagebox.showerror("Export Error", str(e))

    def create_visualization(self):
        try:
            # lightweight visualization: open processed CSV as DataFrame and show basic counts
            data_to_show = self.interpolated_data if self.interpolated_data else self.processed_data
            if not data_to_show:
                messagebox.showwarning("Warning", "No data available to visualize.")
                return
            df = pd.DataFrame(data_to_show)
            plate_counts = df['license_number'].value_counts() if 'license_number' in df.columns else pd.Series()
            top = plate_counts.head(10)
            msg = f"Top {len(top)} detected plates:\n" + "\n".join([f"{i}: {c}" for i, c in top.items()])
            messagebox.showinfo("Visualization Summary", msg)
        except Exception as e:
            self.log_message(f"Visualization error: {e}")
            messagebox.showerror("Visualization Error", str(e))

    def browse_output_dir(self):
        d = filedialog.askdirectory(title="Select Output Directory")
        if d:
            self.output_dir_var.set(d)
            self.log_message(f"Output directory set to: {d}")

    def save_settings(self):
        try:
            self.settings['detection_confidence'] = float(self.confidence_var.get())
            self.settings['tracking_enabled'] = bool(self.tracking_var.get())
            self.settings['interpolation_enabled'] = bool(self.interpolation_var.get())
            self.settings['save_screenshots'] = bool(self.screenshots_var.get())
            self.settings['output_directory'] = self.output_dir_var.get()
            self.settings['color_detection_enabled'] = bool(self.color_detection_var.get())
            self.settings['vehicle_type_detection'] = bool(self.vehicle_type_var.get())
            self.settings['gps_tracking_enabled'] = bool(self.gps_tracking_var.get())
            self.settings['geofencing_enabled'] = bool(self.geofencing_var.get())
            self.settings['location_update_interval'] = int(self.update_interval_var.get())
            self.settings['email_alerts_enabled'] = bool(self.email_alerts_var.get())
            self.settings['alert_email'] = self.alert_email_var.get().strip()
            # persist to file
            os.makedirs(self.settings['output_directory'], exist_ok=True)
            cfg_path = os.path.join(self.settings['output_directory'], 'settings.json')
            with open(cfg_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, default=str)
            self.log_message("Settings saved")
            messagebox.showinfo("Settings", "Settings saved successfully.")
        except Exception as e:
            self.log_message(f"Save settings error: {e}")
            messagebox.showerror("Error", str(e))

    def load_settings(self):
        try:
            cfg_path = os.path.join(self.settings.get('output_directory', './output'), 'settings.json')
            if os.path.exists(cfg_path):
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.settings.update(loaded)
        except Exception:
            pass

    # -----------------------------
    # Start / run
    # -----------------------------
    def run(self):
        try:
            self.root.protocol("WM_DELETE_WINDOW", self._on_close)
            self.root.mainloop()
        except KeyboardInterrupt:
            self._on_close()

    def _on_close(self):
        try:
            self.is_processing = False
            if self.cap:
                try:
                    self.cap.release()
                except Exception:
                    pass
            try:
                self.root.destroy()
            except Exception:
                pass
        except Exception:
            pass


if __name__ == "__main__":
    app = EnhancedLicensePlateRecognitionSystem()
    app.run()
