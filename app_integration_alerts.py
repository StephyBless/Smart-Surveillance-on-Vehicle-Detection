"""
Modified Integration module for connecting the Database Alert System to the main app.py
FIXED: Now triggers alerts for ANY detected license plate that matches the database
This file hooks into the existing license plate recognition system without modifying the main code.
"""

import threading
import time
from datetime import datetime
from database_alerts import RealTimeDatabaseChecker
import tkinter as tk
from tkinter import messagebox, ttk

class AlertSystemIntegration:
    """Integration class that connects to the main app without modifying it - DYNAMIC LICENSE PLATE MATCHING"""
    
    def __init__(self, main_app_instance):
        self.main_app = main_app_instance
        self.db_checker = RealTimeDatabaseChecker()
        self.alert_window = None
        self.active_alerts_count = 0
        self.last_checked_plates = set()
        self.processed_frame_count = 0  # Track processed frames to avoid duplicate checks
        
        # Add alert monitoring to the existing GUI
        self.setup_alert_ui()
        
        # Hook into the existing detection pipeline
        self.hook_into_detection_pipeline()
    
    def setup_alert_ui(self):
        """Add alert system UI to existing tabs"""
        # Add new tab for alerts to the existing notebook
        if hasattr(self.main_app, 'notebook'):
            self.setup_alerts_tab()
            self.setup_alert_status_indicator()
    
    def setup_alerts_tab(self):
        """Create alerts tab in the existing notebook"""
        alerts_frame = ttk.Frame(self.main_app.notebook)
        self.main_app.notebook.add(alerts_frame, text="🚨 Stolen Vehicle Alerts")
        
        # Alert mode indicator
        mode_frame = ttk.LabelFrame(alerts_frame, text="Alert Configuration", padding=10)
        mode_frame.pack(fill=tk.X, padx=5, pady=5)
        
        mode_label = tk.Label(mode_frame, 
                             text="⚙️ DYNAMIC LICENSE PLATE MATCHING MODE", 
                             font=('Arial', 12, 'bold'), fg='#27ae60')
        mode_label.pack(anchor=tk.W, padx=5, pady=2)
        
        info_label = tk.Label(mode_frame, 
                             text="Alerts trigger for ANY detected license plate that matches the stolen vehicle database.\nSystem automatically checks all detected plates in real-time.",
                             font=('Arial', 10), fg='#7f8c8d')
        info_label.pack(anchor=tk.W, padx=5, pady=2)
        
        # Alert statistics frame
        stats_frame = ttk.LabelFrame(alerts_frame, text="Alert System Status", padding=10)
        stats_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Statistics labels
        self.alert_stats_labels = {
            'system_status': tk.Label(stats_frame, text="Status: DYNAMIC MATCHING ACTIVE", fg="green", font=('Arial', 10, 'bold')),
            'alerts_today': tk.Label(stats_frame, text="Alerts Today: 0"),
            'active_cases': tk.Label(stats_frame, text="Active Stolen Vehicles: 0"),
            'last_check': tk.Label(stats_frame, text="Last Check: Never"),
            'plates_checked': tk.Label(stats_frame, text="Plates Checked: 0")
        }
        
        for label in self.alert_stats_labels.values():
            label.pack(anchor=tk.W, padx=5, pady=2)
        
        # Control buttons
        controls_frame = ttk.LabelFrame(alerts_frame, text="Controls", padding=10)
        controls_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(controls_frame, text="View Alert History", 
                  command=self.show_alert_history).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Add Stolen Vehicle", 
                  command=self.show_add_stolen_vehicle_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Test Alert System", 
                  command=self.test_alert_system).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Check Database", 
                  command=self.show_database_contents).pack(side=tk.LEFT, padx=5)
        
        # Recent alerts display
        alerts_display_frame = ttk.LabelFrame(alerts_frame, text="Recent Alerts (All Detected Plate Matches)", padding=10)
        alerts_display_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create treeview for alerts
        columns = ('Time', 'License Plate', 'Match Type', 'Case Number', 'Priority', 'Agency', 'Vehicle Mismatch')
        self.alerts_tree = ttk.Treeview(alerts_display_frame, columns=columns, show='headings', height=8)
        
        # Configure column widths
        column_widths = {
            'Time': 80,
            'License Plate': 100,
            'Match Type': 80,
            'Case Number': 100,
            'Priority': 80,
            'Agency': 120,
            'Vehicle Mismatch': 120
        }
        
        for col in columns:
            self.alerts_tree.heading(col, text=col)
            self.alerts_tree.column(col, width=column_widths.get(col, 100), anchor=tk.CENTER)
        
        # Scrollbar for alerts tree
        alerts_scrollbar = ttk.Scrollbar(alerts_display_frame, orient=tk.VERTICAL, command=self.alerts_tree.yview)
        self.alerts_tree.configure(yscrollcommand=alerts_scrollbar.set)
        
        self.alerts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        alerts_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double click for details
        self.alerts_tree.bind('<Double-1>', self.on_alert_double_click)
        
        # Update statistics periodically
        self.update_alert_statistics()
    
    def setup_alert_status_indicator(self):
        """Add alert status indicator to the main status bar"""
        if hasattr(self.main_app, 'status_label'):
            # Create alert indicator frame
            status_frame = self.main_app.status_label.master
            
            self.alert_indicator = tk.Label(status_frame, text="🚨 Alert System: DYNAMIC MATCHING", 
                                          bg='#34495e', fg='#27ae60', font=('Arial', 10, 'bold'))
            self.alert_indicator.pack(side=tk.LEFT, padx=10, pady=5)
    
    def hook_into_detection_pipeline(self):
        """Hook into the existing detection pipeline"""
        # Store reference to original process_frame_enhanced method
        if hasattr(self.main_app, 'process_frame_enhanced'):
            self.original_process_frame = self.main_app.process_frame_enhanced
            # Replace with our enhanced version
            self.main_app.process_frame_enhanced = self.enhanced_process_frame_with_alerts
    
    def enhanced_process_frame_with_alerts(self, frame, frame_nmr):
        """Enhanced frame processing that includes alert checking for ALL detected plates"""
        # Call the original processing method first
        if hasattr(self, 'original_process_frame'):
            self.original_process_frame(frame, frame_nmr)
        
        # Increment processed frame count
        self.processed_frame_count += 1
        
        # Check for stolen vehicles in the most recently processed data
        self.check_current_frame_detections(frame_nmr)
    
    def check_current_frame_detections(self, current_frame_nmr):
        """Check detections from the current frame against stolen vehicle database"""
        if not self.main_app.processed_data:
            return
        
        # Get detections from the current frame only
        current_frame_detections = [
            detection for detection in self.main_app.processed_data 
            if str(detection.get('frame_nmr', '')) == str(current_frame_nmr)
        ]
        
        if not current_frame_detections:
            return
        
        # Check each detection from this frame
        for detection in current_frame_detections:
            license_plate = detection.get('license_number', '')
            vehicle_color = detection.get('vehicle_color', 'unknown')
            vehicle_type = detection.get('vehicle_type', 'unknown')
            timestamp = detection.get('timestamp', 0)
            
            # Skip invalid plates
            if not license_plate or license_plate == '0' or len(license_plate.strip()) < 3:
                continue
            
            # Create unique key to avoid duplicate alerts for the same detection
            detection_key = f"{license_plate}_{current_frame_nmr}_{timestamp}"
            
            # Skip if we've already processed this exact detection
            if detection_key in self.last_checked_plates:
                continue
            
            # Add to checked plates
            self.last_checked_plates.add(detection_key)
            
            # Keep only recent checks to avoid memory issues
            if len(self.last_checked_plates) > 1000:
                self.last_checked_plates = set(list(self.last_checked_plates)[-500:])
            
            # Prepare detection info
            detection_info = {
                'camera_id': 'MAIN_SYSTEM',
                'timestamp': datetime.now(),
                'confidence': float(detection.get('license_number_score', 0)),
                'frame_number': current_frame_nmr,
                'vehicle_bbox': detection.get('car_bbox', ''),
                'plate_bbox': detection.get('license_plate_bbox', ''),
                'video_timestamp': timestamp
            }
            
            # Check against stolen vehicle database
            alert_result = self.db_checker.check_detection(
                license_plate=license_plate,
                vehicle_color=vehicle_color,
                vehicle_type=vehicle_type,
                detection_info=detection_info
            )
            
            if alert_result:
                # Add detected vs database vehicle info for comparison
                alert_result['detected_color'] = vehicle_color
                alert_result['detected_type'] = vehicle_type
                alert_result['detection_data'] = detection
                self.handle_stolen_vehicle_alert(alert_result)
                
                # Log the successful match
                if hasattr(self.main_app, 'log_message'):
                    self.main_app.log_message(f"🎯 LICENSE PLATE MATCH FOUND: {license_plate} - Checking database...")
            else:
                # Log that we checked this plate (for debugging)
                if hasattr(self.main_app, 'log_message'):
                    # Only log every 10th non-match to avoid spam
                    if self.processed_frame_count % 10 == 0:
                        self.main_app.log_message(f"✅ Checked plate: {license_plate} - No match in stolen database")
    
    def handle_stolen_vehicle_alert(self, alert_result):
        """Handle a stolen vehicle alert - DYNAMIC LICENSE PLATE MATCHING"""
        self.active_alerts_count += 1
        
        # Update UI on main thread
        self.main_app.root.after(0, lambda: self.show_alert_popup(alert_result))
        self.main_app.root.after(0, lambda: self.add_alert_to_tree(alert_result))
        self.main_app.root.after(0, lambda: self.update_alert_indicator())
        
        # Log to main app
        if hasattr(self.main_app, 'log_message'):
            stolen_data = alert_result['stolen_vehicle_data']
            match_type = stolen_data.get('match_type', 'EXACT')
            confidence = stolen_data.get('match_confidence', 1.0)
            
            self.main_app.log_message(
                f"🚨 STOLEN VEHICLE ALERT: {stolen_data['license_plate']} - "
                f"Case: {stolen_data['case_number']} ({stolen_data['priority_level']} priority) "
                f"[{match_type} match, {confidence:.1%} confidence]"
            )
    
    def show_alert_popup(self, alert_result):
        """Show immediate alert popup with vehicle attribute comparison"""
        stolen_data = alert_result['stolen_vehicle_data']
        detection_data = alert_result.get('detection_data', {})
        
        # Create alert window
        if self.alert_window is None or not self.alert_window.winfo_exists():
            self.alert_window = tk.Toplevel(self.main_app.root)
            self.alert_window.title("🚨 STOLEN VEHICLE DETECTED")
            self.alert_window.geometry("650x550")
            self.alert_window.configure(bg='#e74c3c')
            
            # Make it stay on top and grab attention
            self.alert_window.attributes('-topmost', True)
            self.alert_window.grab_set()
            
            # Alert header
            header_frame = tk.Frame(self.alert_window, bg='#c0392b', height=80)
            header_frame.pack(fill=tk.X, pady=5)
            header_frame.pack_propagate(False)
            
            tk.Label(header_frame, text="🚨 STOLEN VEHICLE DETECTED", 
                    font=('Arial', 16, 'bold'), bg='#c0392b', fg='white').pack(pady=5)
            tk.Label(header_frame, text="DYNAMIC LICENSE PLATE MATCH CONFIRMED", 
                    font=('Arial', 12, 'bold'), bg='#c0392b', fg='#ffeb3b').pack(pady=2)
            
            # Alert details
            details_frame = tk.Frame(self.alert_window, bg='white')
            details_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            
            # Create scrolled text for details
            details_text = tk.Text(details_frame, wrap=tk.WORD, font=('Consolas', 10))
            details_scrollbar = ttk.Scrollbar(details_frame, orient=tk.VERTICAL, command=details_text.yview)
            details_text.configure(yscrollcommand=details_scrollbar.set)
            
            details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Format alert details with vehicle attribute comparison
            alert_details = f"""
🚨 STOLEN VEHICLE ALERT 🚨
{'='*50}

ALERT ID: {alert_result['alert_id']}
DETECTION TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
MATCHING SYSTEM: DYNAMIC LICENSE PLATE DETECTION

LICENSE PLATE MATCH:
Detected Plate: {stolen_data['license_plate']}
Match Type: {stolen_data.get('match_type', 'EXACT')}
Match Confidence: {stolen_data.get('match_confidence', 1.0):.1%}

STOLEN VEHICLE INFORMATION (Database Record):
Make/Model: {stolen_data['vehicle_year']} {stolen_data['vehicle_make']} {stolen_data['vehicle_model']}
Color: {stolen_data['vehicle_color']}
License Plate: {stolen_data['license_plate']}

DETECTED VEHICLE INFORMATION:
Color: {alert_result.get('detected_color', 'Not detected')}
Type: {alert_result.get('detected_type', 'Not detected')}
Detection Frame: {detection_data.get('frame_nmr', 'N/A')}
Video Timestamp: {self.format_timestamp(detection_data.get('timestamp', 0))}

VEHICLE ATTRIBUTE COMPARISON:
"""
            
            # Add comparison details
            detected_color = alert_result.get('detected_color', 'Not detected')
            detected_type = alert_result.get('detected_type', 'Not detected')
            db_color = stolen_data['vehicle_color']
            db_make_model = f"{stolen_data['vehicle_make']} {stolen_data['vehicle_model']}"
            
            if detected_color != 'Not detected':
                if detected_color.lower() == db_color.lower():
                    alert_details += f"✅ Color Match: {detected_color} = {db_color}\n"
                else:
                    alert_details += f"⚠️ Color Difference: Detected '{detected_color}' vs Database '{db_color}'\n"
            else:
                alert_details += f"ℹ️ Color: Not detected, Database shows '{db_color}'\n"
            
            if detected_type != 'Not detected':
                alert_details += f"ℹ️ Type: Detected '{detected_type}' vs Database '{db_make_model}'\n"
            else:
                alert_details += f"ℹ️ Type: Not detected, Database shows '{db_make_model}'\n"
            
            alert_details += f"""

⚡ ALERT TRIGGERED: License plate '{stolen_data['license_plate']}' matches stolen vehicle database
   Alert generated automatically from real-time video processing.

CASE INFORMATION:
Case Number: {stolen_data['case_number']}
Reporting Agency: {stolen_data['agency']}
Priority Level: {stolen_data['priority_level']}
Theft Date: {stolen_data['theft_date']}
Theft Location: {stolen_data['theft_location']}

DETECTION TECHNICAL DETAILS:
Camera/Source: {alert_result['detection_info'].get('camera_id', 'Unknown')}
OCR Confidence: {alert_result['detection_info'].get('confidence', 'N/A')}
Frame Number: {alert_result['detection_info'].get('frame_number', 'N/A')}

⚠️ IMPORTANT: This alert was generated automatically by the license plate 
   recognition system. Vehicle attribute differences may be due to:
   - Vehicle modifications by thieves
   - Detection system limitations
   - Lighting conditions
   - Database entry variations

RECOMMENDED ACTIONS:
🔸 Contact {stolen_data['agency']} immediately
🔸 Do not approach vehicle - may be dangerous
🔸 Note location and direction of travel
🔸 Maintain visual surveillance if safely possible
🔸 Document all observations
"""
            
            details_text.insert(tk.END, alert_details)
            details_text.config(state=tk.DISABLED)
            
            # Control buttons
            button_frame = tk.Frame(self.alert_window, bg='#e74c3c')
            button_frame.pack(fill=tk.X, pady=5)
            
            tk.Button(button_frame, text="ACKNOWLEDGE ALERT", 
                     command=self.acknowledge_alert, bg='#27ae60', fg='white',
                     font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=10)
            
            tk.Button(button_frame, text="VIEW FULL DETAILS", 
                     command=lambda: self.show_full_alert_details(stolen_data),
                     bg='#3498db', fg='white', font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=10)
            
            tk.Button(button_frame, text="CLOSE", 
                     command=self.alert_window.destroy, bg='#95a5a6', fg='white',
                     font=('Arial', 12, 'bold')).pack(side=tk.RIGHT, padx=10)
    
    def format_timestamp(self, timestamp):
        """Convert timestamp to MM:SS format"""
        try:
            timestamp = float(timestamp)
            minutes = int(timestamp // 60)
            seconds = int(timestamp % 60)
            return f"{minutes:02d}:{seconds:02d}"
        except:
            return "00:00"
    
    def add_alert_to_tree(self, alert_result):
        """Add alert to the alerts tree view with vehicle mismatch info"""
        if hasattr(self, 'alerts_tree'):
            stolen_data = alert_result['stolen_vehicle_data']
            
            # Check for vehicle attribute mismatches
            detected_color = alert_result.get('detected_color', 'Not detected')
            detected_type = alert_result.get('detected_type', 'Not detected')
            db_color = stolen_data['vehicle_color']
            
            mismatch_info = "None"
            if detected_color != 'Not detected' and detected_color.lower() != db_color.lower():
                mismatch_info = f"Color: {detected_color} vs {db_color}"
            elif detected_color == 'Not detected':
                mismatch_info = "Color not detected"
            
            # Get match type
            match_type = stolen_data.get('match_type', 'EXACT')
            if match_type == 'FUZZY':
                confidence = stolen_data.get('match_confidence', 1.0)
                match_type = f"FUZZY ({confidence:.1%})"
            
            # Add to tree
            self.alerts_tree.insert('', 0, values=(
                datetime.now().strftime('%H:%M:%S'),
                stolen_data['license_plate'],
                match_type,
                stolen_data['case_number'],
                stolen_data['priority_level'],
                stolen_data['agency'],
                mismatch_info
            ))
    
    def on_alert_double_click(self, event):
        """Handle double click on alert item"""
        selection = self.alerts_tree.selection()
        if selection:
            item = self.alerts_tree.item(selection[0])
            values = item['values']
            license_plate = values[1]
            case_number = values[3]
            mismatch_info = values[6]
            
            # Show details for this alert
            detail_msg = f"License Plate: {license_plate}\n"
            detail_msg += f"Case Number: {case_number}\n"
            detail_msg += f"Vehicle Attribute Status: {mismatch_info}\n\n"
            detail_msg += "Note: Alert triggered by dynamic license plate matching.\n"
            detail_msg += "System automatically checks all detected plates against database."
            
            messagebox.showinfo("Alert Details", detail_msg)
    
    def acknowledge_alert(self):
        """Acknowledge the current alert"""
        if self.alert_window and self.alert_window.winfo_exists():
            self.alert_window.destroy()
        
        if hasattr(self.main_app, 'log_message'):
            self.main_app.log_message("Alert acknowledged by operator")
    
    def show_full_alert_details(self, stolen_data):
        """Show full details of the stolen vehicle"""
        details_window = tk.Toplevel(self.main_app.root)
        details_window.title(f"Case Details - {stolen_data['case_number']}")
        details_window.geometry("600x500")
        
        # Create detailed view
        text_widget = tk.Text(details_window, wrap=tk.WORD, font=('Consolas', 10))
        scrollbar = ttk.Scrollbar(details_window, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        full_details = f"""
STOLEN VEHICLE CASE FILE
{'='*50}

ALERT SYSTEM: DYNAMIC LICENSE PLATE MATCHING
- System automatically checks ALL detected license plates
- Alerts trigger when any detected plate matches database records
- Real-time monitoring during video processing

CASE INFORMATION:
Case Number: {stolen_data['case_number']}
Status: {stolen_data['status']}
Reporting Agency: {stolen_data['agency']}
Priority Level: {stolen_data['priority_level']}

VEHICLE DETAILS:
License Plate: {stolen_data['license_plate']}
Year: {stolen_data['vehicle_year']}
Make: {stolen_data['vehicle_make']}
Model: {stolen_data['vehicle_model']}
Color: {stolen_data['vehicle_color']}

INCIDENT DETAILS:
Theft Date: {stolen_data['theft_date']}
Theft Location: {stolen_data['theft_location']}
Report Date: {stolen_data.get('created_at', 'N/A')}

DETECTION INFORMATION:
Match Type: {stolen_data.get('match_type', 'EXACT')}
Match Confidence: {stolen_data.get('match_confidence', 1.0):.1%}
Detection Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
System Alert ID: {stolen_data.get('id', 'N/A')}

{'='*50}
IMPORTANT NOTES:
⚡ This alert was triggered by DYNAMIC license plate matching
✅ System automatically processes all detected plates
⚠️ Vehicle attributes may differ from database records due to:
   - Repainting/modification by thieves
   - OCR detection errors in vehicle recognition
   - Lighting conditions affecting color detection
   - Vehicle type misclassification

RECOMMENDED ACTIONS:
1. Contact {stolen_data['agency']} immediately
2. Do not approach vehicle - may be dangerous
3. Note vehicle location and direction of travel
4. Maintain visual surveillance if possible
5. Document all observations
6. Verify vehicle details visually when safe to do so

SYSTEM STATUS:
✅ Alert system is actively monitoring all detected plates
🔍 Checking against {stolen_data.get('total_database_records', 'multiple')} stolen vehicle records
⚡ Real-time processing enabled
        """
        
        text_widget.insert(tk.END, full_details)
        text_widget.config(state=tk.DISABLED)
        
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def update_alert_indicator(self):
        """Update the alert status indicator"""
        if hasattr(self, 'alert_indicator'):
            if self.active_alerts_count > 0:
                self.alert_indicator.configure(
                    text=f"🚨 Alert System: {self.active_alerts_count} ACTIVE ALERTS",
                    fg='#e74c3c'
                )
            else:
                self.alert_indicator.configure(
                    text="🚨 Alert System: DYNAMIC MONITORING",
                    fg='#27ae60'
                )
    
    def update_alert_statistics(self):
        """Update alert statistics display"""
        try:
            stats = self.db_checker.get_alert_statistics()
            
            if hasattr(self, 'alert_stats_labels'):
                self.alert_stats_labels['alerts_today'].configure(
                    text=f"Alerts Today: {stats['alerts_today']}")
                self.alert_stats_labels['active_cases'].configure(
                    text=f"Active Stolen Vehicles: {stats['active_stolen_vehicles']}")
                self.alert_stats_labels['last_check'].configure(
                    text=f"Last Check: {datetime.now().strftime('%H:%M:%S')}")
                self.alert_stats_labels['plates_checked'].configure(
                    text=f"Plates Checked: {len(self.last_checked_plates)}")
            
            # Schedule next update
            self.main_app.root.after(5000, self.update_alert_statistics)  # Update every 5 seconds
            
        except Exception as e:
            print(f"Error updating alert statistics: {e}")
    
    def show_alert_history(self):
        """Show alert history window"""
        history_window = tk.Toplevel(self.main_app.root)
        history_window.title("Alert History - Dynamic License Plate Matches")
        history_window.geometry("800x600")
        
        # Create treeview for history
        columns = ('Alert ID', 'Time', 'License Plate', 'Case Number', 'Status', 'Match Type')
        history_tree = ttk.Treeview(history_window, columns=columns, show='headings')
        
        for col in columns:
            history_tree.heading(col, text=col)
            history_tree.column(col, width=130, anchor=tk.CENTER)
        
        # Scrollbar
        history_scrollbar = ttk.Scrollbar(history_window, orient=tk.VERTICAL, command=history_tree.yview)
        history_tree.configure(yscrollcommand=history_scrollbar.set)
        
        history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate with recent alerts
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_checker.stolen_db.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT license_plate, detection_time, case_number 
                FROM alert_history 
                ORDER BY detection_time DESC 
                LIMIT 50
            ''')
            
            alerts = cursor.fetchall()
            conn.close()
            
            for i, alert in enumerate(alerts):
                history_tree.insert('', 'end', values=(
                    f"ALERT_{i+1:03d}",
                    alert[1],
                    alert[0],
                    alert[2] or "N/A",
                    "Processed",
                    "Dynamic Match"
                ))
                
        except Exception as e:
            print(f"Error loading alert history: {e}")
    
    def show_database_contents(self):
        """Show current database contents for verification"""
        db_window = tk.Toplevel(self.main_app.root)
        db_window.title("Stolen Vehicle Database Contents")
        db_window.geometry("800x600")
        
        # Create treeview for database contents
        columns = ('License Plate', 'Make', 'Model', 'Color', 'Year', 'Case Number', 'Agency', 'Priority')
        db_tree = ttk.Treeview(db_window, columns=columns, show='headings')
        
        for col in columns:
            db_tree.heading(col, text=col)
            db_tree.column(col, width=100, anchor=tk.CENTER)
        
        # Scrollbar
        db_scrollbar = ttk.Scrollbar(db_window, orient=tk.VERTICAL, command=db_tree.yview)
        db_tree.configure(yscrollcommand=db_scrollbar.set)
        
        db_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        db_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Load database contents
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_checker.stolen_db.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT license_plate, vehicle_make, vehicle_model, vehicle_color, 
                       vehicle_year, case_number, agency, priority_level
                FROM stolen_vehicles 
                WHERE status = 'ACTIVE'
                ORDER BY created_at DESC
            ''')
            
            records = cursor.fetchall()
            conn.close()
            
            # Add header info
            info_label = tk.Label(db_window, text=f"Database contains {len(records)} active stolen vehicle records", 
                                font=('Arial', 12, 'bold'), bg='lightblue')
            info_label.pack(fill=tk.X, pady=5)
            
            # Populate tree
            for record in records:
                db_tree.insert('', 'end', values=record)
                
            if len(records) == 0:
                db_tree.insert('', 'end', values=("No records", "", "", "", "", "", "", ""))
                
        except Exception as e:
            error_label = tk.Label(db_window, text=f"Error loading database: {e}", 
                                 font=('Arial', 10), fg='red')
            error_label.pack(pady=10)
    
    def show_add_stolen_vehicle_dialog(self):
        """Show dialog to add new stolen vehicle"""
        dialog = tk.Toplevel(self.main_app.root)
        dialog.title("Add Stolen Vehicle - Dynamic Matching System")
        dialog.geometry("400x550")
        dialog.grab_set()
        
        # Form fields
        fields = {}
        
        tk.Label(dialog, text="Add New Stolen Vehicle Report", 
                font=('Arial', 14, 'bold')).pack(pady=10)
        
        tk.Label(dialog, text="Dynamic License Plate Matching Active", 
                font=('Arial', 10), fg='#27ae60').pack(pady=2)
        tk.Label(dialog, text="System will automatically detect this plate when it appears in video", 
                font=('Arial', 9), fg='#7f8c8d').pack(pady=2)
        
        # Create form
        form_data = [
            ('License Plate*', 'license_plate'),
            ('Vehicle Make', 'make'),
            ('Vehicle Model', 'model'),
            ('Vehicle Color', 'color'),
            ('Vehicle Year', 'year'),
            ('Case Number*', 'case_number'),
            ('Reporting Agency*', 'agency'),
            ('Theft Location', 'location')
        ]
        
        for label_text, field_name in form_data:
            frame = tk.Frame(dialog)
            frame.pack(fill=tk.X, padx=20, pady=5)
            
            tk.Label(frame, text=label_text, width=15, anchor='w').pack(side=tk.LEFT)
            entry = tk.Entry(frame)
            entry.pack(side=tk.RIGHT, fill=tk.X, expand=True)
            fields[field_name] = entry
        
        # Priority selection
        priority_frame = tk.Frame(dialog)
        priority_frame.pack(fill=tk.X, padx=20, pady=5)
        
        tk.Label(priority_frame, text="Priority Level", width=15, anchor='w').pack(side=tk.LEFT)
        priority_var = tk.StringVar(value="MEDIUM")
        priority_combo = ttk.Combobox(priority_frame, textvariable=priority_var, 
                                     values=['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'])
        priority_combo.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        # Information note
        note_frame = tk.Frame(dialog, bg='#ecf0f1')
        note_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(note_frame, text="Note: System will automatically alert when this license plate\nis detected in any processed video, regardless of vehicle attributes.", 
                font=('Arial', 9), bg='#ecf0f1', fg='#34495e').pack(pady=5)
        
        def submit_stolen_vehicle():
            try:
                # Validate required fields
                required = ['license_plate', 'case_number', 'agency']
                for field in required:
                    if not fields[field].get().strip():
                        messagebox.showerror("Error", f"{field.replace('_', ' ').title()} is required")
                        return
                
                # Add to database
                license_plate = fields['license_plate'].get().strip().upper()
                
                # Add stolen vehicle to database
                import sqlite3
                conn = sqlite3.connect(self.db_checker.stolen_db.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO stolen_vehicles 
                    (license_plate, vehicle_make, vehicle_model, vehicle_color, 
                     vehicle_year, theft_date, theft_location, case_number, agency, priority_level)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    license_plate,
                    fields['make'].get().strip() or "Unknown",
                    fields['model'].get().strip() or "Unknown", 
                    fields['color'].get().strip() or "Unknown",
                    int(fields['year'].get().strip()) if fields['year'].get().strip().isdigit() else 0,
                    datetime.now().date().isoformat(),
                    fields['location'].get().strip() or "Unknown",
                    fields['case_number'].get().strip(),
                    fields['agency'].get().strip(),
                    priority_var.get()
                ))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", 
                    f"Stolen vehicle added to database successfully!\n\n"
                    f"License Plate: {license_plate}\n"
                    f"Alert Mode: DYNAMIC MATCHING\n\n"
                    f"The system will now automatically alert whenever this license plate\n"
                    f"is detected during video processing.")
                dialog.destroy()
                
                # Update statistics
                self.update_alert_statistics()
                
                if hasattr(self.main_app, 'log_message'):
                    self.main_app.log_message(f"Added stolen vehicle to database: {license_plate} (DYNAMIC MATCHING)")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add stolen vehicle: {e}")
        
        # Buttons
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=20)
        
        tk.Button(button_frame, text="Add Vehicle", command=submit_stolen_vehicle,
                 bg='#27ae60', fg='white', font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="Cancel", command=dialog.destroy,
                 bg='#95a5a6', fg='white', font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=10)
    
    def test_alert_system(self):
        """Test the alert system with the current detected plates"""
        try:
            # Check if we have any processed data
            if not self.main_app.processed_data:
                messagebox.showwarning("Test Alert System", 
                    "No license plates detected yet.\n\n"
                    "Please process a video first, then try the test again.\n"
                    "The test will check the most recently detected plates against the database.")
                return
            
            # Get the most recent detections
            recent_plates = []
            for detection in self.main_app.processed_data[-10:]:  # Last 10 detections
                plate = detection.get('license_number', '')
                if plate and plate != '0' and len(plate.strip()) >= 3:
                    recent_plates.append(plate)
            
            if not recent_plates:
                messagebox.showinfo("Test Alert System", 
                    "No valid license plates found in recent detections.\n\n"
                    "Process a video with detectable license plates and try again.")
                return
            
            # Remove duplicates and take the most recent
            unique_plates = list(set(recent_plates))[:5]  # Test up to 5 recent unique plates
            
            test_results = []
            alerts_triggered = 0
            
            for plate in unique_plates:
                # Test with the actual detected plate
                test_result = self.db_checker.check_detection(
                    license_plate=plate,
                    vehicle_color="test_color",
                    vehicle_type="test_type",
                    detection_info={
                        'camera_id': 'TEST_SYSTEM',
                        'timestamp': datetime.now(),
                        'confidence': 0.95,
                        'location': 'System Test'
                    }
                )
                
                if test_result:
                    alerts_triggered += 1
                    test_results.append(f"✅ ALERT: {plate} - MATCH FOUND")
                    # Don't actually show the alert popup for test
                else:
                    test_results.append(f"ℹ️ No match: {plate}")
            
            # Show test results
            result_msg = f"Dynamic Alert System Test Results:\n\n"
            result_msg += f"Tested {len(unique_plates)} recently detected plates:\n\n"
            result_msg += "\n".join(test_results)
            result_msg += f"\n\n🚨 Alerts triggered: {alerts_triggered}/{len(unique_plates)}\n\n"
            
            if alerts_triggered > 0:
                result_msg += "✅ Alert system is working correctly!\n"
                result_msg += "The system found matches in the stolen vehicle database."
            else:
                result_msg += "ℹ️ No matches found in database.\n"
                result_msg += "This is normal if the detected plates are not stolen vehicles.\n"
                result_msg += "You can add test plates using the 'Add Stolen Vehicle' button."
            
            messagebox.showinfo("Test Results", result_msg)
            
            if hasattr(self.main_app, 'log_message'):
                self.main_app.log_message(f"Alert system test completed - {alerts_triggered} matches found from {len(unique_plates)} plates")
                
        except Exception as e:
            messagebox.showerror("Test Failed", f"Alert system test failed: {e}")


def integrate_database_alerts(main_app_instance):
    """
    Main integration function - call this from your app.py
    MODIFIED for DYNAMIC LICENSE PLATE MATCHING
    Usage: from app_integration_alerts import integrate_database_alerts
           integrate_database_alerts(self)  # in your app's __init__ method
    """
    try:
        alert_integration = AlertSystemIntegration(main_app_instance)
        
        if hasattr(main_app_instance, 'log_message'):
            main_app_instance.log_message("🚨 Database Alert System integrated successfully")
            main_app_instance.log_message("⚡ DYNAMIC LICENSE PLATE MATCHING activated")
            main_app_instance.log_message("System will automatically check ALL detected license plates")
            main_app_instance.log_message("Real-time stolen vehicle monitoring is now ACTIVE")
        
        return alert_integration
        
    except Exception as e:
        print(f"Failed to integrate database alert system: {e}")
        if hasattr(main_app_instance, 'log_message'):
            main_app_instance.log_message(f"Alert system integration failed: {e}")
        return None