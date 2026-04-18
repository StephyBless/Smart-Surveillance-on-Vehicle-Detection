"""
multi_camera_intelligence.py

Multi-Camera Network Intelligence Module
Separate file to integrate with your main a5.py project

Author: Your Name
Date: 2025
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import threading
import json
import os
from collections import defaultdict, deque
import time

# =============================================================================
# CORE CLASSES
# =============================================================================

class CameraNode:
    """Represents a single camera in the network"""
    def __init__(self, camera_id, name, location, coordinates=(0, 0)):
        self.camera_id = camera_id
        self.name = name
        self.location = location
        self.coordinates = coordinates  # (x, y) for map display
        self.video_source = None
        self.is_active = False
        self.detections = []
        self.last_detection_time = None
        
    def to_dict(self):
        return {
            'camera_id': self.camera_id,
            'name': self.name,
            'location': self.location,
            'coordinates': self.coordinates,
            'video_source': self.video_source,
            'is_active': self.is_active
        }
    
    @staticmethod
    def from_dict(data):
        camera = CameraNode(
            data['camera_id'],
            data['name'],
            data['location'],
            tuple(data['coordinates'])
        )
        camera.video_source = data.get('video_source')
        camera.is_active = data.get('is_active', False)
        return camera


class VehicleJourney:
    """Track a vehicle's journey across multiple cameras"""
    def __init__(self, vehicle_id, license_plate):
        self.vehicle_id = vehicle_id
        self.license_plate = license_plate
        self.checkpoints = []  # List of checkpoint dicts
        self.total_distance = 0
        self.total_time = 0
        self.suspicious_score = 0
        self.loop_count = 0
        self.vehicle_color = "unknown"
        self.vehicle_type = "unknown"
        self.first_seen = None
        self.last_seen = None
        
    def add_checkpoint(self, camera_id, timestamp, location, color=None, vtype=None):
        """Add a detection checkpoint"""
        checkpoint = {
            'camera_id': camera_id,
            'timestamp': timestamp,
            'location': location,
            'time_str': timestamp.strftime("%H:%M:%S")
        }
        
        self.checkpoints.append(checkpoint)
        
        if color:
            self.vehicle_color = color
        if vtype:
            self.vehicle_type = vtype
            
        # Update first and last seen
        if self.first_seen is None:
            self.first_seen = timestamp
        self.last_seen = timestamp
            
        # Calculate time between checkpoints
        if len(self.checkpoints) > 1:
            time_diff = (timestamp - self.checkpoints[-2]['timestamp']).total_seconds()
            self.total_time += time_diff
            
        # Detect loops (same camera visited again)
        camera_visits = [cp['camera_id'] for cp in self.checkpoints]
        if camera_visits.count(camera_id) > 1:
            self.loop_count += 1
            self.suspicious_score += 10
            
    def calculate_suspicious_score(self):
        """Calculate how suspicious this vehicle's behavior is"""
        score = 0
        
        # Multiple loops
        if self.loop_count > 2:
            score += 30
        
        # Too many camera appearances in short time
        if len(self.checkpoints) > 10 and self.total_time < 600:  # 10 mins
            score += 20
            
        # Unusual time patterns (late night)
        late_night_count = sum(1 for cp in self.checkpoints 
                              if 0 <= cp['timestamp'].hour < 6)
        if late_night_count > 3:
            score += 25
            
        # Same location visited multiple times
        locations = [cp['location'] for cp in self.checkpoints]
        if len(locations) != len(set(locations)):
            score += 15
            
        self.suspicious_score = min(score, 100)
        return self.suspicious_score
    
    def get_journey_summary(self):
        """Get formatted journey summary"""
        return {
            'vehicle_id': self.vehicle_id,
            'license_plate': self.license_plate,
            'total_checkpoints': len(self.checkpoints),
            'total_time_minutes': round(self.total_time / 60, 2),
            'loop_count': self.loop_count,
            'suspicious_score': self.suspicious_score,
            'vehicle_color': self.vehicle_color,
            'vehicle_type': self.vehicle_type,
            'first_seen': self.first_seen.strftime("%Y-%m-%d %H:%M:%S") if self.first_seen else "N/A",
            'last_seen': self.last_seen.strftime("%Y-%m-%d %H:%M:%S") if self.last_seen else "N/A",
            'checkpoints': self.checkpoints
        }


class MultiCameraNetworkManager:
    """Manages the entire camera network"""
    def __init__(self):
        self.cameras = {}  # camera_id -> CameraNode
        self.vehicle_journeys = {}  # license_plate -> VehicleJourney
        self.active_vehicles = {}  # license_plate -> last_seen_time
        self.detection_history = []
        self.config_file = "camera_network_config.json"
        
        # Load saved configuration
        self.load_configuration()
        
    def add_camera(self, camera_id, name, location, coordinates=(0, 0)):
        """Add a new camera to the network"""
        if camera_id in self.cameras:
            return False, "Camera ID already exists"
        
        camera = CameraNode(camera_id, name, location, coordinates)
        self.cameras[camera_id] = camera
        self.save_configuration()
        return True, f"Camera {name} added successfully"
    
    def remove_camera(self, camera_id):
        """Remove a camera from the network"""
        if camera_id in self.cameras:
            del self.cameras[camera_id]
            self.save_configuration()
            return True, "Camera removed"
        return False, "Camera not found"
    
    def update_camera(self, camera_id, **kwargs):
        """Update camera properties"""
        if camera_id not in self.cameras:
            return False, "Camera not found"
        
        camera = self.cameras[camera_id]
        for key, value in kwargs.items():
            if hasattr(camera, key):
                setattr(camera, key, value)
        
        self.save_configuration()
        return True, "Camera updated"
    
    def register_detection(self, camera_id, license_plate, timestamp=None, 
                          vehicle_color=None, vehicle_type=None):
        """Register a vehicle detection from a camera"""
        if camera_id not in self.cameras:
            return False, "Camera not registered"
        
        if timestamp is None:
            timestamp = datetime.now()
        
        camera = self.cameras[camera_id]
        camera.last_detection_time = timestamp
        
        # Create or update vehicle journey
        if license_plate not in self.vehicle_journeys:
            vehicle_id = f"V{len(self.vehicle_journeys) + 1:04d}"
            self.vehicle_journeys[license_plate] = VehicleJourney(vehicle_id, license_plate)
        
        journey = self.vehicle_journeys[license_plate]
        journey.add_checkpoint(camera_id, timestamp, camera.location, 
                              vehicle_color, vehicle_type)
        journey.calculate_suspicious_score()
        
        # Update active vehicles
        self.active_vehicles[license_plate] = timestamp
        
        # Add to detection history
        detection_record = {
            'camera_id': camera_id,
            'camera_name': camera.name,
            'license_plate': license_plate,
            'vehicle_id': journey.vehicle_id,
            'timestamp': timestamp,
            'location': camera.location,
            'suspicious_score': journey.suspicious_score
        }
        self.detection_history.append(detection_record)
        
        return True, journey
    
    def get_vehicle_journey(self, license_plate):
        """Get complete journey for a vehicle"""
        if license_plate in self.vehicle_journeys:
            return self.vehicle_journeys[license_plate]
        return None
    
    def get_suspicious_vehicles(self, threshold=50):
        """Get vehicles with suspicious behavior"""
        suspicious = []
        for plate, journey in self.vehicle_journeys.items():
            if journey.suspicious_score >= threshold:
                suspicious.append(journey)
        return sorted(suspicious, key=lambda x: x.suspicious_score, reverse=True)
    
    def get_looping_vehicles(self):
        """Get vehicles that are looping (visiting same cameras)"""
        return [j for j in self.vehicle_journeys.values() if j.loop_count > 0]
    
    def calculate_travel_time(self, camera_id_1, camera_id_2, license_plate):
        """Calculate time taken between two cameras for a vehicle"""
        journey = self.get_vehicle_journey(license_plate)
        if not journey:
            return None
        
        times = []
        checkpoints = journey.checkpoints
        for i in range(len(checkpoints) - 1):
            if (checkpoints[i]['camera_id'] == camera_id_1 and 
                checkpoints[i+1]['camera_id'] == camera_id_2):
                time_diff = (checkpoints[i+1]['timestamp'] - 
                           checkpoints[i]['timestamp']).total_seconds()
                times.append(time_diff)
        
        return times
    
    def get_network_statistics(self):
        """Get overall network statistics"""
        total_cameras = len(self.cameras)
        active_cameras = sum(1 for c in self.cameras.values() if c.is_active)
        total_vehicles = len(self.vehicle_journeys)
        suspicious_vehicles = len(self.get_suspicious_vehicles())
        total_detections = len(self.detection_history)
        
        return {
            'total_cameras': total_cameras,
            'active_cameras': active_cameras,
            'total_vehicles_tracked': total_vehicles,
            'suspicious_vehicles': suspicious_vehicles,
            'total_detections': total_detections,
            'looping_vehicles': len(self.get_looping_vehicles())
        }
    
    def export_journey_data(self, filepath):
        """Export all journey data to CSV"""
        data = []
        for plate, journey in self.vehicle_journeys.items():
            summary = journey.get_journey_summary()
            for checkpoint in summary['checkpoints']:
                data.append({
                    'vehicle_id': summary['vehicle_id'],
                    'license_plate': plate,
                    'camera_id': checkpoint['camera_id'],
                    'location': checkpoint['location'],
                    'timestamp': checkpoint['timestamp'].strftime("%Y-%m-%d %H:%M:%S"),
                    'suspicious_score': summary['suspicious_score'],
                    'loop_count': summary['loop_count'],
                    'vehicle_color': summary['vehicle_color'],
                    'vehicle_type': summary['vehicle_type']
                })
        
        df = pd.DataFrame(data)
        df.to_csv(filepath, index=False)
        return len(data)
    
    def save_configuration(self):
        """Save camera network configuration"""
        config = {
            'cameras': {cid: cam.to_dict() for cid, cam in self.cameras.items()},
            'last_updated': datetime.now().isoformat()
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def load_configuration(self):
        """Load camera network configuration"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                
                for cid, cam_data in config.get('cameras', {}).items():
                    self.cameras[cid] = CameraNode.from_dict(cam_data)
            except Exception as e:
                print(f"Error loading configuration: {e}")


# =============================================================================
# GUI MODULE
# =============================================================================

class MultiCameraNetworkGUI:
    """GUI for Multi-Camera Network Intelligence"""
    def __init__(self, parent_notebook):
        self.notebook = parent_notebook
        self.manager = MultiCameraNetworkManager()
        
        # Create the main tab
        self.setup_network_tab()
    
    def setup_network_tab(self):
        """Setup the multi-camera network tab"""
        network_frame = ttk.Frame(self.notebook)
        self.notebook.add(network_frame, text="🎥 Camera Network")
        
        # Create sub-tabs
        sub_notebook = ttk.Notebook(network_frame)
        sub_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Sub-tabs
        self.setup_camera_management_tab(sub_notebook)
        self.setup_journey_tracking_tab(sub_notebook)
        self.setup_suspicious_behavior_tab(sub_notebook)
        self.setup_network_statistics_tab(sub_notebook)
    
    def setup_camera_management_tab(self, parent):
        """Camera management interface"""
        frame = ttk.Frame(parent)
        parent.add(frame, text="Camera Management")
        
        # Left panel - Camera list
        left_panel = ttk.LabelFrame(frame, text="Registered Cameras", padding=10)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Camera tree
        columns = ('ID', 'Name', 'Location', 'Status', 'Video Source')
        self.camera_tree = ttk.Treeview(left_panel, columns=columns, 
                                       show='headings', height=15)
        
        for col in columns:
            self.camera_tree.heading(col, text=col)
            width = 100 if col != 'Video Source' else 200
            self.camera_tree.column(col, width=width)
        
        scrollbar = ttk.Scrollbar(left_panel, orient=tk.VERTICAL, 
                                 command=self.camera_tree.yview)
        self.camera_tree.configure(yscrollcommand=scrollbar.set)
        
        self.camera_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Right panel - Camera controls
        right_panel = ttk.LabelFrame(frame, text="Camera Controls", padding=10)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
        
        # Add camera section
        ttk.Label(right_panel, text="Add New Camera", 
                 font=('Arial', 11, 'bold')).pack(anchor=tk.W, pady=5)
        
        ttk.Label(right_panel, text="Camera ID:").pack(anchor=tk.W)
        self.cam_id_entry = ttk.Entry(right_panel, width=30)
        self.cam_id_entry.pack(fill=tk.X, pady=2)
        
        ttk.Label(right_panel, text="Camera Name:").pack(anchor=tk.W)
        self.cam_name_entry = ttk.Entry(right_panel, width=30)
        self.cam_name_entry.pack(fill=tk.X, pady=2)
        
        ttk.Label(right_panel, text="Location:").pack(anchor=tk.W)
        self.cam_location_entry = ttk.Entry(right_panel, width=30)
        self.cam_location_entry.pack(fill=tk.X, pady=2)
        
        ttk.Label(right_panel, text="Coordinates (x,y):").pack(anchor=tk.W)
        coord_frame = ttk.Frame(right_panel)
        coord_frame.pack(fill=tk.X, pady=2)
        self.cam_x_entry = ttk.Entry(coord_frame, width=14)
        self.cam_x_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.cam_y_entry = ttk.Entry(coord_frame, width=14)
        self.cam_y_entry.pack(side=tk.LEFT)
        
        ttk.Label(right_panel, text="Video Source:").pack(anchor=tk.W, pady=(10, 0))
        video_frame = ttk.Frame(right_panel)
        video_frame.pack(fill=tk.X, pady=2)
        self.cam_video_entry = ttk.Entry(video_frame, width=20)
        self.cam_video_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(video_frame, text="Browse", width=8,
                  command=self.browse_video_source).pack(side=tk.RIGHT, padx=(5, 0))
        
        # Buttons
        ttk.Button(right_panel, text="➕ Add Camera", 
                  command=self.add_camera).pack(fill=tk.X, pady=10)
        
        ttk.Separator(right_panel, orient='horizontal').pack(fill=tk.X, pady=10)
        
        ttk.Button(right_panel, text="🔄 Refresh List", 
                  command=self.refresh_camera_list).pack(fill=tk.X, pady=2)
        ttk.Button(right_panel, text="✏️ Edit Selected", 
                  command=self.edit_camera).pack(fill=tk.X, pady=2)
        ttk.Button(right_panel, text="🗑️ Delete Selected", 
                  command=self.delete_camera).pack(fill=tk.X, pady=2)
        
        ttk.Separator(right_panel, orient='horizontal').pack(fill=tk.X, pady=10)
        
        ttk.Button(right_panel, text="💾 Save Configuration", 
                  command=self.save_config).pack(fill=tk.X, pady=2)
        
        # Initial refresh
        self.refresh_camera_list()
    
    def setup_journey_tracking_tab(self, parent):
        """Vehicle journey tracking interface"""
        frame = ttk.Frame(parent)
        parent.add(frame, text="Journey Tracking")
        
        # Top panel - Search
        search_panel = ttk.LabelFrame(frame, text="Search Vehicle Journey", padding=10)
        search_panel.pack(fill=tk.X, padx=5, pady=5)
        
        search_frame = ttk.Frame(search_panel)
        search_frame.pack(fill=tk.X)
        
        ttk.Label(search_frame, text="License Plate:").pack(side=tk.LEFT)
        self.journey_search_entry = ttk.Entry(search_frame, width=20, font=('Arial', 11))
        self.journey_search_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="🔍 Search Journey", 
                  command=self.search_journey).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="📋 Show All Vehicles", 
                  command=self.show_all_journeys).pack(side=tk.LEFT)
        
        # Middle panel - Journey details
        details_panel = ttk.LabelFrame(frame, text="Journey Details", padding=10)
        details_panel.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Journey tree
        columns = ('Vehicle ID', 'License Plate', 'Checkpoints', 'Total Time', 
                  'Loops', 'Suspicious Score', 'Color', 'Type')
        self.journey_tree = ttk.Treeview(details_panel, columns=columns, 
                                        show='headings', height=10)
        
        col_widths = {'Vehicle ID': 80, 'License Plate': 100, 'Checkpoints': 90,
                     'Total Time': 90, 'Loops': 60, 'Suspicious Score': 110,
                     'Color': 80, 'Type': 80}
        
        for col in columns:
            self.journey_tree.heading(col, text=col)
            self.journey_tree.column(col, width=col_widths.get(col, 100))
        
        scrollbar = ttk.Scrollbar(details_panel, orient=tk.VERTICAL, 
                                 command=self.journey_tree.yview)
        self.journey_tree.configure(yscrollcommand=scrollbar.set)
        
        self.journey_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double-click
        self.journey_tree.bind('<Double-1>', self.show_journey_timeline)
        
        # Bottom panel - Timeline view
        timeline_panel = ttk.LabelFrame(frame, text="Selected Journey Timeline", 
                                       padding=10)
        timeline_panel.pack(fill=tk.X, padx=5, pady=5)
        
        self.timeline_text = tk.Text(timeline_panel, height=8, wrap=tk.WORD, 
                                    font=('Consolas', 10))
        timeline_scroll = ttk.Scrollbar(timeline_panel, orient=tk.VERTICAL, 
                                       command=self.timeline_text.yview)
        self.timeline_text.configure(yscrollcommand=timeline_scroll.set)
        
        self.timeline_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        timeline_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Export button
        ttk.Button(frame, text="📤 Export Journey Data", 
                  command=self.export_journeys).pack(pady=5)
    
    def setup_suspicious_behavior_tab(self, parent):
        """Suspicious behavior detection interface"""
        frame = ttk.Frame(parent)
        parent.add(frame, text="Suspicious Behavior")
        
        # Controls panel
        control_panel = ttk.LabelFrame(frame, text="Detection Controls", padding=10)
        control_panel.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(control_panel, text="Suspicious Score Threshold:").pack(side=tk.LEFT)
        self.suspicious_threshold = tk.IntVar(value=50)
        threshold_scale = ttk.Scale(control_panel, from_=0, to=100, 
                                   variable=self.suspicious_threshold, 
                                   orient=tk.HORIZONTAL, length=200)
        threshold_scale.pack(side=tk.LEFT, padx=10)
        self.threshold_label = ttk.Label(control_panel, text="50")
        self.threshold_label.pack(side=tk.LEFT, padx=5)
        
        threshold_scale.configure(command=lambda v: self.threshold_label.configure(
            text=f"{int(float(v))}"))
        
        ttk.Button(control_panel, text="🔍 Find Suspicious Vehicles", 
                  command=self.find_suspicious).pack(side=tk.LEFT, padx=10)
        ttk.Button(control_panel, text="🔄 Show Looping Vehicles", 
                  command=self.show_looping).pack(side=tk.LEFT)
        
        # Results panel
        results_panel = ttk.LabelFrame(frame, text="Suspicious Vehicles", padding=10)
        results_panel.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        columns = ('Vehicle ID', 'License Plate', 'Score', 'Loops', 'Checkpoints', 
                  'First Seen', 'Last Seen', 'Reason')
        self.suspicious_tree = ttk.Treeview(results_panel, columns=columns, 
                                           show='headings', height=15)
        
        for col in columns:
            self.suspicious_tree.heading(col, text=col)
            width = 120 if col == 'Reason' else 90
            self.suspicious_tree.column(col, width=width)
        
        scrollbar = ttk.Scrollbar(results_panel, orient=tk.VERTICAL, 
                                 command=self.suspicious_tree.yview)
        self.suspicious_tree.configure(yscrollcommand=scrollbar.set)
        
        self.suspicious_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double-click
        self.suspicious_tree.bind('<Double-1>', self.show_suspicious_details)
    
    def setup_network_statistics_tab(self, parent):
        """Network statistics and analytics"""
        frame = ttk.Frame(parent)
        parent.add(frame, text="Network Statistics")
        
        # Stats panel
        stats_panel = ttk.LabelFrame(frame, text="Network Overview", padding=10)
        stats_panel.pack(fill=tk.X, padx=5, pady=5)
        
        # Create grid for stats
        self.stat_labels = {}
        stats_info = [
            ('Total Cameras', 'total_cameras'),
            ('Active Cameras', 'active_cameras'),
            ('Vehicles Tracked', 'total_vehicles_tracked'),
            ('Suspicious Vehicles', 'suspicious_vehicles'),
            ('Total Detections', 'total_detections'),
            ('Looping Vehicles', 'looping_vehicles')
        ]
        
        for i, (label, key) in enumerate(stats_info):
            row = i // 3
            col = i % 3
            
            stat_frame = ttk.Frame(stats_panel)
            stat_frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')
            
            ttk.Label(stat_frame, text=label + ":", 
                     font=('Arial', 10, 'bold')).pack(anchor=tk.W)
            value_label = ttk.Label(stat_frame, text="0", 
                                   font=('Arial', 14), foreground='blue')
            value_label.pack(anchor=tk.W)
            self.stat_labels[key] = value_label
        
        # Configure grid weights
        for i in range(3):
            stats_panel.columnconfigure(i, weight=1)
        
        # Refresh button
        # Create separate frame for button (avoid mixing pack/grid)
        button_frame = ttk.Frame(stats_panel)
        button_frame.grid(row=2, column=0, columnspan=3, pady=10)
   
        ttk.Button(button_frame, text="🔄 Refresh Statistics", 
              command=self.refresh_statistics).pack()

        # Recent activity panel
        activity_panel = ttk.LabelFrame(frame, text="Recent Detection Activity", 
                                       padding=10)
        activity_panel.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        columns = ('Time', 'Camera', 'License Plate', 'Location', 'Score')
        self.activity_tree = ttk.Treeview(activity_panel, columns=columns, 
                                         show='headings', height=15)
        
        for col in columns:
            self.activity_tree.heading(col, text=col)
            self.activity_tree.column(col, width=120)
        
        scrollbar = ttk.Scrollbar(activity_panel, orient=tk.VERTICAL, 
                                 command=self.activity_tree.yview)
        self.activity_tree.configure(yscrollcommand=scrollbar.set)
        
        self.activity_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Initial refresh
        self.refresh_statistics()
    
    # =========================================================================
    # CALLBACK METHODS
    # =========================================================================
    
    
    def browse_video_source(self):
        """Browse for video file"""
        filepath = filedialog.askopenfilename(
            title="Select Video Source",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
        )
        if filepath:
            self.cam_video_entry.delete(0, tk.END)
            self.cam_video_entry.insert(0, filepath)
    
    def add_camera(self):
        """Add a new camera to the network"""
        camera_id = self.cam_id_entry.get().strip()
        name = self.cam_name_entry.get().strip()
        location = self.cam_location_entry.get().strip()
        
        if not camera_id or not name or not location:
            messagebox.showwarning("Warning", "Please fill in all required fields")
            return
        
        try:
            x = float(self.cam_x_entry.get() or 0)
            y = float(self.cam_y_entry.get() or 0)
            coordinates = (x, y)
        except ValueError:
            messagebox.showerror("Error", "Invalid coordinates")
            return
        
        success, msg = self.manager.add_camera(camera_id, name, location, coordinates)
        
        if success:
            # Update video source if provided
            video_source = self.cam_video_entry.get().strip()
            if video_source:
                self.manager.update_camera(camera_id, video_source=video_source)
            
            messagebox.showinfo("Success", msg)
            self.clear_camera_entries()
            self.refresh_camera_list()
        else:
            messagebox.showerror("Error", msg)
    
    def clear_camera_entries(self):
        """Clear camera entry fields"""
        self.cam_id_entry.delete(0, tk.END)
        self.cam_name_entry.delete(0, tk.END)
        self.cam_location_entry.delete(0, tk.END)
        self.cam_x_entry.delete(0, tk.END)
        self.cam_y_entry.delete(0, tk.END)
        self.cam_video_entry.delete(0, tk.END)
    
    def refresh_camera_list(self):
        """Refresh the camera list"""
        # Clear existing items
        for item in self.camera_tree.get_children():
            self.camera_tree.delete(item)
        
        # Add cameras
        for camera_id, camera in self.manager.cameras.items():
            status = "🟢 Active" if camera.is_active else "🔴 Inactive"
            video = camera.video_source or "Not set"
            
            self.camera_tree.insert('', 'end', values=(
                camera_id, camera.name, camera.location, status, video
            ))
    
    def edit_camera(self):
        """Edit selected camera"""
        selection = self.camera_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a camera to edit")
            return
        
        item = self.camera_tree.item(selection[0])
        camera_id = item['values'][0]
        camera = self.manager.cameras.get(camera_id)
        
        if camera:
            # Populate fields
            self.cam_id_entry.delete(0, tk.END)
            self.cam_id_entry.insert(0, camera_id)
            self.cam_id_entry.configure(state='disabled')  # Can't change ID
            
            self.cam_name_entry.delete(0, tk.END)
            self.cam_name_entry.insert(0, camera.name)
            
            self.cam_location_entry.delete(0, tk.END)
            self.cam_location_entry.insert(0, camera.location)
            
            self.cam_x_entry.delete(0, tk.END)
            self.cam_x_entry.insert(0, str(camera.coordinates[0]))
            
            self.cam_y_entry.delete(0, tk.END)
            self.cam_y_entry.insert(0, str(camera.coordinates[1]))
            
            if camera.video_source:
                self.cam_video_entry.delete(0, tk.END)
                self.cam_video_entry.insert(0, camera.video_source)
    
    def delete_camera(self):
        """Delete selected camera"""
        selection = self.camera_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a camera to delete")
            return
        
        item = self.camera_tree.item(selection[0])
        camera_id = item['values'][0]
        
        if messagebox.askyesno("Confirm", f"Delete camera {camera_id}?"):
            success, msg = self.manager.remove_camera(camera_id)
            if success:
                messagebox.showinfo("Success", msg)
                self.refresh_camera_list()
            else:
                messagebox.showerror("Error", msg)
    
    def save_config(self):
        """Save camera configuration"""
        self.manager.save_configuration()
        messagebox.showinfo("Success", "Configuration saved successfully!")
    
    def search_journey(self):
        """Search for a specific vehicle journey"""
        license_plate = self.journey_search_entry.get().strip().upper()
        if not license_plate:
            messagebox.showwarning("Warning", "Please enter a license plate")
            return
        
        journey = self.manager.get_vehicle_journey(license_plate)
        if journey:
            self.display_single_journey(journey)
        else:
            messagebox.showinfo("Not Found", 
                              f"No journey found for {license_plate}")
    
    def show_all_journeys(self):
        """Show all vehicle journeys"""
        # Clear tree
        for item in self.journey_tree.get_children():
            self.journey_tree.delete(item)
        
        # Add all journeys
        for journey in self.manager.vehicle_journeys.values():
            summary = journey.get_journey_summary()
            self.journey_tree.insert('', 'end', values=(
                summary['vehicle_id'],
                summary['license_plate'],
                summary['total_checkpoints'],
                f"{summary['total_time_minutes']} min",
                summary['loop_count'],
                summary['suspicious_score'],
                summary['vehicle_color'].title(),
                summary['vehicle_type'].title()
            ))
    
    def display_single_journey(self, journey):
        """Display a single journey in the tree"""
        # Clear tree
        for item in self.journey_tree.get_children():
            self.journey_tree.delete(item)
        
        summary = journey.get_journey_summary()
        self.journey_tree.insert('', 'end', values=(
            summary['vehicle_id'],
            summary['license_plate'],
            summary['total_checkpoints'],
            f"{summary['total_time_minutes']} min",
            summary['loop_count'],
            summary['suspicious_score'],
            summary['vehicle_color'].title(),
            summary['vehicle_type'].title()
        ))
        
        # Show timeline
        self.display_journey_timeline(journey)
    
    def show_journey_timeline(self, event):
        """Show timeline for selected journey"""
        selection = self.journey_tree.selection()
        if not selection:
            return
        
        item = self.journey_tree.item(selection[0])
        license_plate = item['values'][1]
        
        journey = self.manager.get_vehicle_journey(license_plate)
        if journey:
            self.display_journey_timeline(journey)
    
    def display_journey_timeline(self, journey):
        """Display journey timeline in text widget"""
        self.timeline_text.delete('1.0', tk.END)
        
        summary = journey.get_journey_summary()
        
        # Header
        header = f"{'='*80}\n"
        header += f"JOURNEY TIMELINE - {summary['license_plate']}\n"
        header += f"Vehicle ID: {summary['vehicle_id']} | "
        header += f"Type: {summary['vehicle_type'].title()} | "
        header += f"Color: {summary['vehicle_color'].title()}\n"
        header += f"Suspicious Score: {summary['suspicious_score']}/100 | "
        header += f"Loop Count: {summary['loop_count']}\n"
        header += f"{'='*80}\n\n"
        
        self.timeline_text.insert(tk.END, header)
        
        # Checkpoints
        for i, checkpoint in enumerate(summary['checkpoints'], 1):
            camera = self.manager.cameras.get(checkpoint['camera_id'])
            camera_name = camera.name if camera else "Unknown Camera"
            
            line = f"{i}. [{checkpoint['time_str']}] "
            line += f"{camera_name} ({checkpoint['location']})\n"
            
            # Calculate time since last checkpoint
            if i > 1:
                prev_time = summary['checkpoints'][i-2]['timestamp']
                curr_time = checkpoint['timestamp']
                time_diff = (curr_time - prev_time).total_seconds()
                line += f"   ⏱️  {time_diff:.0f} seconds from previous checkpoint\n"
            
            line += "\n"
            self.timeline_text.insert(tk.END, line)
        
        # Summary
        footer = f"\n{'='*80}\n"
        footer += f"Total Duration: {summary['total_time_minutes']} minutes\n"
        footer += f"First Seen: {summary['first_seen']}\n"
        footer += f"Last Seen: {summary['last_seen']}\n"
        footer += f"{'='*80}\n"
        
        self.timeline_text.insert(tk.END, footer)
    
    def export_journeys(self):
        """Export journey data to CSV"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save Journey Data"
        )
        
        if filepath:
            try:
                count = self.manager.export_journey_data(filepath)
                messagebox.showinfo("Success", 
                                  f"Exported {count} records to {filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {str(e)}")
    
    def find_suspicious(self):
        """Find suspicious vehicles"""
        threshold = self.suspicious_threshold.get()
        suspicious = self.manager.get_suspicious_vehicles(threshold)
        
        # Clear tree
        for item in self.suspicious_tree.get_children():
            self.suspicious_tree.delete(item)
        
        if not suspicious:
            messagebox.showinfo("No Results", 
                              f"No vehicles found with suspicious score >= {threshold}")
            return
        
        # Add suspicious vehicles
        for journey in suspicious:
            summary = journey.get_journey_summary()
            
            # Determine reason
            reasons = []
            if journey.loop_count > 2:
                reasons.append("Multiple loops")
            if summary['total_checkpoints'] > 10:
                reasons.append("Too many detections")
            if len(reasons) == 0:
                reasons.append("Unusual pattern")
            
            self.suspicious_tree.insert('', 'end', values=(
                summary['vehicle_id'],
                summary['license_plate'],
                summary['suspicious_score'],
                summary['loop_count'],
                summary['total_checkpoints'],
                summary['first_seen'],
                summary['last_seen'],
                ", ".join(reasons)
            ))
        
        messagebox.showinfo("Results", 
                          f"Found {len(suspicious)} suspicious vehicles")
    
    def show_looping(self):
        """Show vehicles with looping behavior"""
        looping = self.manager.get_looping_vehicles()
        
        # Clear tree
        for item in self.suspicious_tree.get_children():
            self.suspicious_tree.delete(item)
        
        if not looping:
            messagebox.showinfo("No Results", "No looping vehicles found")
            return
        
        # Add looping vehicles
        for journey in looping:
            summary = journey.get_journey_summary()
            
            self.suspicious_tree.insert('', 'end', values=(
                summary['vehicle_id'],
                summary['license_plate'],
                summary['suspicious_score'],
                summary['loop_count'],
                summary['total_checkpoints'],
                summary['first_seen'],
                summary['last_seen'],
                "Looping detected"
            ))
        
        messagebox.showinfo("Results", f"Found {len(looping)} looping vehicles")
    
    def show_suspicious_details(self, event):
        """Show detailed information for suspicious vehicle"""
        selection = self.suspicious_tree.selection()
        if not selection:
            return
        
        item = self.suspicious_tree.item(selection[0])
        license_plate = item['values'][1]
        
        journey = self.manager.get_vehicle_journey(license_plate)
        if journey:
            summary = journey.get_journey_summary()
            
            details = f"License Plate: {summary['license_plate']}\n"
            details += f"Vehicle ID: {summary['vehicle_id']}\n"
            details += f"Type: {summary['vehicle_type'].title()} | Color: {summary['vehicle_color'].title()}\n\n"
            details += f"Suspicious Score: {summary['suspicious_score']}/100\n"
            details += f"Loop Count: {summary['loop_count']}\n"
            details += f"Total Checkpoints: {summary['total_checkpoints']}\n"
            details += f"Total Duration: {summary['total_time_minutes']} minutes\n\n"
            details += f"First Seen: {summary['first_seen']}\n"
            details += f"Last Seen: {summary['last_seen']}\n\n"
            details += "Recent Checkpoints:\n"
            
            for checkpoint in summary['checkpoints'][-5:]:
                camera = self.manager.cameras.get(checkpoint['camera_id'])
                camera_name = camera.name if camera else "Unknown"
                details += f"  • {checkpoint['time_str']} - {camera_name} ({checkpoint['location']})\n"
            
            messagebox.showinfo("Suspicious Vehicle Details", details)
    
    def refresh_statistics(self):
        """Refresh network statistics"""
        stats = self.manager.get_network_statistics()
        
        for key, value in stats.items():
            if key in self.stat_labels:
                self.stat_labels[key].configure(text=str(value))
        
        # Refresh recent activity
        for item in self.activity_tree.get_children():
            self.activity_tree.delete(item)
        
        # Show last 50 detections
        recent = sorted(self.manager.detection_history, 
                       key=lambda x: x['timestamp'], reverse=True)[:50]
        
        for detection in recent:
            self.activity_tree.insert('', 'end', values=(
                detection['timestamp'].strftime("%H:%M:%S"),
                detection['camera_name'],
                detection['license_plate'],
                detection['location'],
                detection['suspicious_score']
            ))


# =============================================================================
# INTEGRATION FUNCTION FOR MAIN PROJECT
# =============================================================================

def integrate_multi_camera_network(app_instance):
    """
    Integration function to add Multi-Camera Network to existing a5.py
    
    Args:
        app_instance: Instance of EnhancedLicensePlateRecognitionSystem
    
    Usage in a5.py:
        from multi_camera_intelligence import integrate_multi_camera_network
        # In __init__ method, after self.setup_gui():
        integrate_multi_camera_network(self)
    """
    # Add camera network manager to app
    app_instance.camera_network = MultiCameraNetworkManager()
    
    # Add GUI to existing notebook
    app_instance.camera_network_gui = MultiCameraNetworkGUI(app_instance.notebook)
    
    # Add method to register detections from video processing
    def register_detection_wrapper(camera_id, license_plate, timestamp=None, 
                                   vehicle_color=None, vehicle_type=None):
        """Wrapper to register detection with camera network"""
        success, result = app_instance.camera_network.register_detection(
            camera_id, license_plate, timestamp, vehicle_color, vehicle_type
        )
        if success and isinstance(result, VehicleJourney):
            # Log if suspicious
            if result.suspicious_score >= 70:
                app_instance.log_message(
                    f"⚠️ SUSPICIOUS: {license_plate} - Score: {result.suspicious_score}"
                )
    
    app_instance.register_camera_detection = register_detection_wrapper
    
    # Modify process_frame_enhanced to register with network
    original_process_frame = app_instance.process_frame_enhanced
    
    def enhanced_process_frame_with_network(frame, frame_nmr):
        """Enhanced processing with network registration"""
        # Call original processing
        original_process_frame(frame, frame_nmr)
        
        # Register detections with camera network
        if frame_nmr in app_instance.results:
            timestamp = datetime.now()
            
            for car_id, detection in app_instance.results[frame_nmr].items():
                license_plate = detection['license_plate']['text']
                vehicle_color = detection.get('vehicle_color', 'unknown')
                vehicle_type = detection.get('vehicle_type', 'unknown')
                
                # Register with camera network (use default camera or video filename)
                camera_id = getattr(app_instance, 'current_camera_id', 'CAM001')
                
                app_instance.register_camera_detection(
                    camera_id, license_plate, timestamp,
                    vehicle_color, vehicle_type
                )
    
    app_instance.process_frame_enhanced = enhanced_process_frame_with_network
    
    app_instance.log_message("✅ Multi-Camera Network Intelligence integrated successfully!")
    
    return app_instance


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_sample_camera_network():
    """Create sample camera network for testing"""
    manager = MultiCameraNetworkManager()
    
    # Add sample cameras
    cameras = [
        ("CAM001", "Main Gate", "Building Entrance", (0, 0)),
        ("CAM002", "Parking Lot A", "North Parking", (100, 50)),
        ("CAM003", "Exit Gate", "Building Exit", (200, 0)),
        ("CAM004", "Highway Junction", "NH-47 Junction", (150, -100)),
        ("CAM005", "City Center", "Downtown Area", (300, 100))
    ]
    
    for cam_id, name, location, coords in cameras:
        manager.add_camera(cam_id, name, location, coords)
    
    print(f"Created sample network with {len(cameras)} cameras")
    return manager


def simulate_vehicle_detections(manager):
    """Simulate vehicle detections for testing"""
    import random
    
    plates = ["TN01AB1234", "TN02CD5678", "KL09EF9012", "TN01AB1234"]  # Note duplicate
    colors = ["red", "blue", "white", "black"]
    types = ["car", "truck", "motorcycle"]
    
    base_time = datetime.now()
    
    # Simulate detections
    for i in range(50):
        plate = random.choice(plates)
        camera_id = f"CAM00{random.randint(1, 5)}"
        timestamp = base_time + timedelta(minutes=i*2)
        color = random.choice(colors)
        vtype = random.choice(types)
        
        manager.register_detection(camera_id, plate, timestamp, color, vtype)
    
    print(f"Simulated 50 detections")
    print(f"Tracked {len(manager.vehicle_journeys)} unique vehicles")
    print(f"Suspicious vehicles: {len(manager.get_suspicious_vehicles())}")


# =============================================================================
# STANDALONE TESTING
# =============================================================================

def run_standalone_test():
    """Run as standalone application for testing"""
    root = tk.Tk()
    root.title("Multi-Camera Network Intelligence - Standalone Test")
    root.geometry("1200x800")
    
    # Create notebook
    notebook = ttk.Notebook(root)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # Initialize GUI
    app = MultiCameraNetworkGUI(notebook)
    
    # Create sample network
    print("\n" + "="*60)
    print("Creating sample camera network...")
    for cam_id, name, location, coords in [
        ("CAM001", "Main Gate", "Building Entrance", (0, 0)),
        ("CAM002", "Parking Lot A", "North Parking", (100, 50)),
        ("CAM003", "Exit Gate", "Building Exit", (200, 0))
    ]:
        app.manager.add_camera(cam_id, name, location, coords)
    
    # Simulate some detections
    print("Simulating vehicle detections...")
    simulate_vehicle_detections(app.manager)
    
    # Refresh displays
    app.refresh_camera_list()
    app.show_all_journeys()
    app.refresh_statistics()
    
    print("="*60)
    print("✅ Standalone test application running!")
    print("You can now:")
    print("  - Manage cameras")
    print("  - View vehicle journeys")
    print("  - Detect suspicious behavior")
    print("  - View network statistics")
    print("="*60 + "\n")
    
    root.mainloop()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("MULTI-CAMERA NETWORK INTELLIGENCE SYSTEM")
    print("="*60)
    print("\nThis module can be used in two ways:")
    print("\n1. INTEGRATED MODE (Recommended):")
    print("   Add to your a5.py:")
    print("   from multi_camera_intelligence import integrate_multi_camera_network")
    print("   # In __init__, after self.setup_gui():")
    print("   integrate_multi_camera_network(self)")
    print("\n2. STANDALONE MODE (Testing):")
    print("   Run this file directly to test the module")
    print("="*60 + "\n")
    
    response = input("Run in STANDALONE test mode? (y/n): ")
    if response.lower() == 'y':
        run_standalone_test()
    else:
        print("\nTo integrate with your main project:")
        print("1. Save this file as 'multi_camera_intelligence.py'")
        print("2. Add these lines to a5.py after self.setup_gui():")
        print("\n   from multi_camera_intelligence import integrate_multi_camera_network")
        print("   integrate_multi_camera_network(self)")
        print("\n3. Run your main a5.py application")
        print("\nDone! ✅")