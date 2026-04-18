"""
Real-time Database Alert System - Modified for License Plate Only Matching
Simulates connections to law enforcement databases for stolen vehicle detection
Only triggers alerts based on license plate matches, ignoring vehicle attributes
NOW WITH WORKING EMAIL NOTIFICATIONS
"""
import json
import sqlite3
import time
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import queue
import requests
from difflib import SequenceMatcher
import os

class StolenVehicleDatabase:
    """Simulated stolen vehicle database with license plate only checking"""
    
    def __init__(self, db_path="stolen_vehicles.db"):
        self.db_path = db_path
        self.init_database()
        self.populate_sample_data()
    
    def init_database(self):
        """Initialize the stolen vehicle database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stolen_vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_plate TEXT NOT NULL,
                vehicle_make TEXT,
                vehicle_model TEXT,
                vehicle_color TEXT,
                vehicle_year INTEGER,
                theft_date TEXT,
                theft_location TEXT,
                case_number TEXT,
                agency TEXT,
                priority_level TEXT,
                status TEXT DEFAULT 'ACTIVE',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_plate TEXT,
                detection_time TEXT,
                case_number TEXT,
                alert_sent BOOLEAN DEFAULT 0,
                email_sent BOOLEAN DEFAULT 0,
                acknowledged BOOLEAN DEFAULT 0,
                acknowledged_by TEXT,
                acknowledged_at TEXT,
                officers_notified TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def populate_sample_data(self):
        """Populate database with sample stolen vehicle data"""
        sample_vehicles = [
            ("ABC123", "Toyota", "Camry", "red", 2020, "2024-01-15", "Downtown", "CASE001", "Metro PD", "HIGH"),
            ("XYZ789", "Honda", "Civic", "blue", 2019, "2024-01-20", "Mall Parking", "CASE002", "City Police", "MEDIUM"),
            ("GXISOCJ", "Ford", "F150", "black", 2021, "2024-01-25", "Residential", "CASE003", "Sheriff Dept", "HIGH"),
            ("GHI999", "BMW", "X5", "white", 2022, "2024-02-01", "Hotel", "CASE004", "State Police", "CRITICAL"),
            ("GXISOGJ", "Mercedes", "C300", "silver", 2020, "2024-02-05", "Airport", "CASE005", "FBI Auto Theft", "CRITICAL"),
            ("NBISU", "Nissan", "Altima", "gray", 2018, "2024-02-10", "Shopping Center", "CASE006", "Metro PD", "MEDIUM"),
            ("PQR333", "Chevrolet", "Malibu", "green", 2019, "2024-02-12", "Restaurant", "CASE007", "City Police", "LOW"),
            ("STU444", "Jeep", "Cherokee", "red", 2021, "2024-02-14", "Gas Station", "CASE008", "Highway Patrol", "HIGH")
        ]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if data already exists
        cursor.execute("SELECT COUNT(*) FROM stolen_vehicles")
        if cursor.fetchone()[0] == 0:
            cursor.executemany('''
                INSERT INTO stolen_vehicles 
                (license_plate, vehicle_make, vehicle_model, vehicle_color, 
                 vehicle_year, theft_date, theft_location, case_number, agency, priority_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', sample_vehicles)
            conn.commit()
        
        conn.close()
    
    def check_stolen_vehicle(self, license_plate):
        """Check if a license plate matches stolen vehicle records - LICENSE PLATE ONLY"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Clean the input license plate
        clean_plate = ''.join(filter(str.isalnum, license_plate.upper()))
        
        # Exact match - only check license plate
        cursor.execute('''
            SELECT * FROM stolen_vehicles 
            WHERE REPLACE(REPLACE(license_plate, ' ', ''), '-', '') = ? AND status = 'ACTIVE'
        ''', (clean_plate,))
        
        exact_match = cursor.fetchone()
        
        if exact_match:
            conn.close()
            match_data = self._format_vehicle_record(exact_match)
            match_data['match_type'] = 'EXACT'
            match_data['match_confidence'] = 1.0
            return match_data
        
        # Fuzzy match for OCR errors - only on license plate
        cursor.execute('''
            SELECT * FROM stolen_vehicles 
            WHERE status = 'ACTIVE'
        ''')
        
        all_records = cursor.fetchall()
        conn.close()
        
        # Check for similar plates (to handle OCR errors)
        best_match = None
        best_similarity = 0
        
        for record in all_records:
            stored_plate = ''.join(filter(str.isalnum, record[1].upper()))
            similarity = SequenceMatcher(None, clean_plate, stored_plate).ratio()
            
            # Use higher threshold for fuzzy matching (90% similarity)
            if similarity >= 0.90 and similarity > best_similarity:
                best_similarity = similarity
                best_match = record
        
        if best_match:
            match_data = self._format_vehicle_record(best_match)
            match_data['similarity_score'] = best_similarity
            match_data['match_type'] = 'FUZZY'
            match_data['match_confidence'] = best_similarity
            return match_data
        
        return None
    
    def _format_vehicle_record(self, record):
        """Format database record into dictionary"""
        return {
            'id': record[0],
            'license_plate': record[1],
            'vehicle_make': record[2],
            'vehicle_model': record[3],
            'vehicle_color': record[4],
            'vehicle_year': record[5],
            'theft_date': record[6],
            'theft_location': record[7],
            'case_number': record[8],
            'agency': record[9],
            'priority_level': record[10],
            'status': record[11],
            'match_type': 'EXACT'
        }
    
    def log_detection(self, license_plate, case_number=None):
        """Log a detection event"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO alert_history (license_plate, detection_time, case_number)
            VALUES (?, ?, ?)
        ''', (license_plate, datetime.now().isoformat(), case_number))
        
        alert_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return alert_id
    
    def acknowledge_alert(self, alert_id, acknowledged_by="System Admin"):
        """Mark an alert as acknowledged"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE alert_history 
            SET acknowledged = 1, acknowledged_by = ?, acknowledged_at = ?
            WHERE id = ?
        ''', (acknowledged_by, datetime.now().isoformat(), alert_id))
        
        conn.commit()
        conn.close()
        print(f"✅ Alert {alert_id} acknowledged by {acknowledged_by}")

class AlertNotificationSystem:
    """Handles various types of notifications for stolen vehicle alerts"""
    
    def __init__(self):
        self.notification_queue = queue.Queue()
        self.email_config = {
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'username': 'stephybless11@gmail.com',  # Your email
            'password': 'afav tcww etnn khtw',  # Your app password
            'recipient': 'stephybless11@gmail.com',  # Send to yourself
            'enabled': True  # ENABLED for email alerts
        }
        
        self.sms_config = {
            'api_key': 'twilio_api_key',  # Simulated
            'enabled': False  # Disabled for demo
        }
        
        # Start notification worker thread
        self.worker_thread = threading.Thread(target=self._process_notifications, daemon=True)
        self.worker_thread.start()
    
    def send_alert(self, vehicle_data, detection_info):
        """Queue an alert for processing"""
        alert_data = {
            'timestamp': datetime.now(),
            'vehicle_data': vehicle_data,
            'detection_info': detection_info,
            'alert_id': f"ALERT_{int(time.time())}"
        }
        
        self.notification_queue.put(alert_data)
        return alert_data['alert_id']
    
    def send_acknowledgment_email(self, alert_data, acknowledged_by="System Admin"):
        """Send email notification when alert is acknowledged"""
        if not self.email_config['enabled']:
            print("📧 Email notifications disabled")
            return False
            
        try:
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = self.email_config['username']
            msg['To'] = self.email_config['recipient']
            msg['Subject'] = f"🚨 STOLEN VEHICLE ALERT ACKNOWLEDGED - {alert_data['alert_id']}"
            
            # Create email body
            vehicle_data = alert_data['vehicle_data']
            detection_info = alert_data['detection_info']
            
            body = f"""
STOLEN VEHICLE ALERT ACKNOWLEDGMENT

Alert ID: {alert_data['alert_id']}
Acknowledged By: {acknowledged_by}
Acknowledgment Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

=== STOLEN VEHICLE DETAILS ===
License Plate: {vehicle_data['license_plate']}
Case Number: {vehicle_data['case_number']}
Priority Level: {vehicle_data['priority_level']}
Reporting Agency: {vehicle_data['agency']}

Vehicle Information:
- Make/Model: {vehicle_data['vehicle_year']} {vehicle_data['vehicle_make']} {vehicle_data['vehicle_model']}
- Color: {vehicle_data['vehicle_color']}
- Theft Date: {vehicle_data['theft_date']}
- Theft Location: {vehicle_data['theft_location']}

=== DETECTION DETAILS ===
Match Type: {vehicle_data.get('match_type', 'EXACT')}
Match Confidence: {vehicle_data.get('match_confidence', 1.0):.2%}
Detection Time: {alert_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}
Camera/Source: {detection_info.get('camera_id', 'Unknown')}
Location: {detection_info.get('location', 'Unknown')}

Detected Vehicle Attributes:
- Detected Color: {detection_info.get('detected_vehicle_color', 'Not detected')}
- Detected Type: {detection_info.get('detected_vehicle_type', 'Not detected')}

IMPORTANT: This alert was triggered based on LICENSE PLATE MATCH ONLY.
Vehicle attribute mismatches are noted but do not prevent alerts.

Please take appropriate action as per department protocol.

---
Automated Alert System
Law Enforcement Vehicle Monitoring
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port'])
            server.starttls()
            server.login(self.email_config['username'], self.email_config['password'])
            
            text = msg.as_string()
            server.sendmail(self.email_config['username'], self.email_config['recipient'], text)
            server.quit()
            
            print(f"📧 ACKNOWLEDGMENT EMAIL SENT to {self.email_config['recipient']}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send acknowledgment email: {e}")
            return False
    
    def _process_notifications(self):
        """Process notification queue in background thread"""
        while True:
            try:
                alert_data = self.notification_queue.get(timeout=1)
                self._send_immediate_alert(alert_data)
                self.notification_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Notification error: {e}")
    
    def _send_immediate_alert(self, alert_data):
        """Send immediate notifications"""
        vehicle_data = alert_data['vehicle_data']
        detection_info = alert_data['detection_info']
        
        # Console alert (always enabled for demo)
        self._send_console_alert(alert_data)
        
        # Email alert (now enabled)
        if self.email_config['enabled']:
            self._send_email_alert(alert_data)
        
        # SMS alert (disabled for demo)
        if self.sms_config['enabled']:
            self._send_sms_alert(alert_data)
        
        # Log to file
        self._log_alert_to_file(alert_data)
    
    def _send_console_alert(self, alert_data):
        """Send alert to console (for demonstration)"""
        vehicle_data = alert_data['vehicle_data']
        detection_info = alert_data['detection_info']
        
        print("\n" + "="*60)
        print(f"🚨 STOLEN VEHICLE ALERT - {alert_data['alert_id']}")
        print("="*60)
        print(f"LICENSE PLATE MATCH: {vehicle_data['license_plate']}")
        print(f"MATCH TYPE: {vehicle_data.get('match_type', 'EXACT')}")
        
        if vehicle_data.get('match_confidence'):
            print(f"MATCH CONFIDENCE: {vehicle_data['match_confidence']:.2%}")
        
        print(f"PRIORITY: {vehicle_data['priority_level']}")
        print(f"CASE NUMBER: {vehicle_data['case_number']}")
        print(f"AGENCY: {vehicle_data['agency']}")
        
        print(f"\nSTOLEN VEHICLE DETAILS (from database):")
        print(f"  Make/Model: {vehicle_data['vehicle_year']} {vehicle_data['vehicle_make']} {vehicle_data['vehicle_model']}")
        print(f"  Color: {vehicle_data['vehicle_color']}")
        print(f"  Theft Date: {vehicle_data['theft_date']}")
        print(f"  Theft Location: {vehicle_data['theft_location']}")
        
        print(f"\nDETECTED VEHICLE INFO:")
        detected_color = detection_info.get('detected_vehicle_color', 'Not detected')
        detected_type = detection_info.get('detected_vehicle_type', 'Not detected')
        print(f"  Detected Color: {detected_color}")
        print(f"  Detected Type: {detected_type}")
        
        # Show if there's a mismatch but still alerting
        if (detected_color != 'Not detected' and 
            detected_color.lower() != vehicle_data['vehicle_color'].lower()):
            print(f"  ⚠️  COLOR MISMATCH: Database shows {vehicle_data['vehicle_color']}, detected {detected_color}")
            print(f"  ℹ️  Alert triggered based on LICENSE PLATE match only")
        
        print(f"\nDETECTION INFO:")
        print(f"  Time: {alert_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Source: {detection_info.get('camera_id', 'Unknown')}")
        print("\n🔔 Type 'acknowledge' to acknowledge this alert and send email notification")
        print("="*60)
    
    def _send_email_alert(self, alert_data):
        """Send immediate email alert"""
        try:
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = self.email_config['username']
            msg['To'] = self.email_config['recipient']
            msg['Subject'] = f"🚨 STOLEN VEHICLE DETECTED - {alert_data['alert_id']}"
            
            # Create email body
            vehicle_data = alert_data['vehicle_data']
            detection_info = alert_data['detection_info']
            
            body = f"""
STOLEN VEHICLE ALERT - IMMEDIATE NOTIFICATION

Alert ID: {alert_data['alert_id']}
Detection Time: {alert_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}

=== STOLEN VEHICLE DETECTED ===
License Plate: {vehicle_data['license_plate']}
Case Number: {vehicle_data['case_number']}
Priority Level: {vehicle_data['priority_level']}
Reporting Agency: {vehicle_data['agency']}

Vehicle Information (from database):
- Make/Model: {vehicle_data['vehicle_year']} {vehicle_data['vehicle_make']} {vehicle_data['vehicle_model']}
- Color: {vehicle_data['vehicle_color']}
- Theft Date: {vehicle_data['theft_date']}
- Theft Location: {vehicle_data['theft_location']}

=== DETECTION DETAILS ===
Match Type: {vehicle_data.get('match_type', 'EXACT')}
Match Confidence: {vehicle_data.get('match_confidence', 1.0):.2%}
Camera/Source: {detection_info.get('camera_id', 'Unknown')}
Detection Location: {detection_info.get('location', 'Unknown')}

Detected Vehicle Attributes:
- Detected Color: {detection_info.get('detected_vehicle_color', 'Not detected')}
- Detected Type: {detection_info.get('detected_vehicle_type', 'Not detected')}

*** IMPORTANT ***
This alert is based on LICENSE PLATE MATCH ONLY.
Vehicle attribute differences are noted but do not prevent alerts.

IMMEDIATE ACTION REQUIRED
Please respond according to department protocol.

---
Automated Alert System
Law Enforcement Vehicle Monitoring
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port'])
            server.starttls()
            server.login(self.email_config['username'], self.email_config['password'])
            
            text = msg.as_string()
            server.sendmail(self.email_config['username'], self.email_config['recipient'], text)
            server.quit()
            
            print(f"📧 IMMEDIATE EMAIL ALERT SENT to {self.email_config['recipient']}")
            
        except Exception as e:
            print(f"❌ Failed to send immediate email alert: {e}")
    
    def _send_sms_alert(self, alert_data):
        """Send SMS alert (simulated)"""
        try:
            # This would contain actual SMS sending logic via Twilio/etc
            print(f"📱 SMS ALERT SENT: {alert_data['alert_id']}")
        except Exception as e:
            print(f"SMS alert failed: {e}")
    
    def _log_alert_to_file(self, alert_data):
        """Log alert to file"""
        try:
            with open("stolen_vehicle_alerts.log", "a") as f:
                log_entry = {
                    'alert_id': alert_data['alert_id'],
                    'timestamp': alert_data['timestamp'].isoformat(),
                    'license_plate': alert_data['vehicle_data']['license_plate'],
                    'case_number': alert_data['vehicle_data']['case_number'],
                    'priority': alert_data['vehicle_data']['priority_level'],
                    'match_type': alert_data['vehicle_data'].get('match_type', 'EXACT'),
                    'match_confidence': alert_data['vehicle_data'].get('match_confidence', 1.0)
                }
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            print(f"Failed to log alert: {e}")

class RealTimeDatabaseChecker:
    """Main class that integrates with the license plate recognition system - LICENSE PLATE ONLY MATCHING"""
    
    def __init__(self):
        self.stolen_db = StolenVehicleDatabase()
        self.notification_system = AlertNotificationSystem()
        self.active_alerts = {}
        self.recent_alerts = {}  # Store recent alert data for acknowledgment
        self.check_frequency = 0.5  # Check every 0.5 seconds
        
    def check_detection(self, license_plate, vehicle_color=None, vehicle_type=None, detection_info=None):
        """
        Check a detected license plate against stolen vehicle databases
        MODIFIED: Only checks license plate, ignores vehicle_color and vehicle_type for matching
        """
        if not license_plate or license_plate == '0':
            return None
        
        # Clean the license plate
        clean_plate = ''.join(filter(str.isalnum, license_plate.upper()))
        
        # Check against stolen vehicle database - ONLY using license plate
        stolen_match = self.stolen_db.check_stolen_vehicle(clean_plate)
        
        if stolen_match:
            # Log the detection and get the alert_id
            db_alert_id = self.stolen_db.log_detection(clean_plate, stolen_match['case_number'])
            
            # Send alert if not already sent recently
            alert_key = f"{clean_plate}_{stolen_match['case_number']}"
            current_time = datetime.now()
            
            # Check if we've already alerted for this plate in the last 5 minutes
            if (alert_key not in self.active_alerts or 
                (current_time - self.active_alerts[alert_key]).seconds > 300):
                
                # Prepare detection info - include detected attributes for reference
                if detection_info is None:
                    detection_info = {
                        'camera_id': 'CAM001',
                        'timestamp': current_time,
                        'confidence': 0.85
                    }
                
                # Add detected vehicle attributes to detection_info for logging
                detection_info['detected_vehicle_color'] = vehicle_color or 'Not detected'
                detection_info['detected_vehicle_type'] = vehicle_type or 'Not detected'
                
                # Send alert
                alert_id = self.notification_system.send_alert(stolen_match, detection_info)
                self.active_alerts[alert_key] = current_time
                
                # Store alert data for potential acknowledgment
                self.recent_alerts[alert_id] = {
                    'timestamp': current_time,
                    'vehicle_data': stolen_match,
                    'detection_info': detection_info,
                    'alert_id': alert_id,
                    'db_alert_id': db_alert_id
                }
                
                return {
                    'alert_triggered': True,
                    'alert_id': alert_id,
                    'db_alert_id': db_alert_id,
                    'stolen_vehicle_data': stolen_match,
                    'detection_info': detection_info,
                    'matching_criteria': 'LICENSE_PLATE_ONLY'
                }
        
        return None
    
    def acknowledge_alert(self, alert_id=None, acknowledged_by="System Admin"):
        """Acknowledge an alert and send email notification"""
        if alert_id is None:
            # Get the most recent alert
            if not self.recent_alerts:
                print("❌ No recent alerts to acknowledge")
                return False
            alert_id = list(self.recent_alerts.keys())[-1]
        
        if alert_id not in self.recent_alerts:
            print(f"❌ Alert {alert_id} not found or too old")
            return False
        
        alert_data = self.recent_alerts[alert_id]
        
        # Mark as acknowledged in database
        self.stolen_db.acknowledge_alert(alert_data['db_alert_id'], acknowledged_by)
        
        # Send acknowledgment email
        email_sent = self.notification_system.send_acknowledgment_email(alert_data, acknowledged_by)
        
        if email_sent:
            print(f"✅ Alert {alert_id} acknowledged and email notification sent!")
        else:
            print(f"⚠️ Alert acknowledged but email failed to send")
        
        return True
    
    def acknowledge_latest_alert(self, acknowledged_by="System Admin"):
        """Acknowledge the most recent alert"""
        return self.acknowledge_alert(None, acknowledged_by)
    
    def get_alert_statistics(self):
        """Get statistics about alerts"""
        conn = sqlite3.connect(self.stolen_db.db_path)
        cursor = conn.cursor()
        
        # Count total alerts today
        today = datetime.now().date()
        cursor.execute('''
            SELECT COUNT(*) FROM alert_history 
            WHERE DATE(detection_time) = ?
        ''', (today,))
        
        alerts_today = cursor.fetchone()[0]
        
        # Count acknowledged alerts today
        cursor.execute('''
            SELECT COUNT(*) FROM alert_history 
            WHERE DATE(detection_time) = ? AND acknowledged = 1
        ''', (today,))
        
        acknowledged_today = cursor.fetchone()[0]
        
        # Count active stolen vehicles
        cursor.execute('''
            SELECT COUNT(*) FROM stolen_vehicles 
            WHERE status = 'ACTIVE'
        ''')
        
        active_cases = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'alerts_today': alerts_today,
            'acknowledged_today': acknowledged_today,
            'pending_acknowledgment': alerts_today - acknowledged_today,
            'active_stolen_vehicles': active_cases,
            'active_monitoring_sessions': len(self.active_alerts)
        }
    
    def add_stolen_vehicle(self, license_plate, make, model, color, year, case_number, agency, priority="MEDIUM"):
        """Add a new stolen vehicle to the database"""
        conn = sqlite3.connect(self.stolen_db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO stolen_vehicles 
            (license_plate, vehicle_make, vehicle_model, vehicle_color, 
             vehicle_year, theft_date, case_number, agency, priority_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (license_plate.upper(), make, model, color, year, 
              datetime.now().date().isoformat(), case_number, agency, priority))
        
        conn.commit()
        conn.close()
        
        print(f"Added stolen vehicle to database: {license_plate} - {case_number}")

# Example usage and testing
if __name__ == "__main__":
    # Initialize the system
    db_checker = RealTimeDatabaseChecker()
    
    print("Real-time Database Alert System Initialized")
    print("*** LICENSE PLATE ONLY MATCHING MODE ***")
    print("*** EMAIL NOTIFICATIONS ENABLED ***")
    print(f"📧 Email alerts will be sent to: stephybless11@gmail.com")
    print("Alerts will trigger based solely on license plate matches")
    print("Vehicle color/type mismatches will be noted but won't prevent alerts")
    print("Monitoring for stolen vehicles...")
    
    # Test with sample detections - including mismatched vehicle attributes
    test_cases = [
        {"plate": "ABC123", "color": "blue", "type": "truck"},  # Color/type mismatch but should still alert
        {"plate": "XYZ789", "color": "red", "type": "car"},     # Another mismatch
        {"plate": "TEST999", "color": "white", "type": "car"},  # No match expected
        {"plate": "GHI999", "color": "black", "type": "sedan"}, # Should match despite type difference
    ]
    
    for i, test_case in enumerate(test_cases):
        print(f"\nTesting plate: {test_case['plate']} (detected as {test_case['color']} {test_case['type']})")
        result = db_checker.check_detection(
            license_plate=test_case['plate'],
            vehicle_color=test_case['color'],
            vehicle_type=test_case['type'],
            detection_info={
                'camera_id': 'CAM001',
                'timestamp': datetime.now(),
                'confidence': 0.92,
                'location': 'Main Street Camera'
            }
        )
        
        if result:
            print(f"✅ ALERT TRIGGERED: {result['alert_id']} (Matching: {result['matching_criteria']})")
            print("📧 Immediate email alert sent!")
            
            # Simulate acknowledgment for the first alert
            if i == 0:
                time.sleep(2)
                print("\n--- SIMULATING ALERT ACKNOWLEDGMENT ---")
                db_checker.acknowledge_latest_alert("Officer Smith")
                
        else:
            print("❌ No match found - license plate not in stolen vehicle database")
        
        time.sleep(1)  # Simulate real-time detection intervals
    
    # Show statistics
    stats = db_checker.get_alert_statistics()
    print(f"\nSystem Statistics:")
    print(f"Alerts Today: {stats['alerts_today']}")
    print(f"Acknowledged Today: {stats['acknowledged_today']}")
    print(f"Pending Acknowledgment: {stats['pending_acknowledgment']}")
    print(f"Active Stolen Vehicles: {stats['active_stolen_vehicles']}")
    print(f"Active Monitoring: {stats['active_monitoring_sessions']}")
    
    # Interactive mode for testing acknowledgments
    print(f"\n" + "="*60)
    print("INTERACTIVE MODE")
    print("Commands:")
    print("- 'ack' or 'acknowledge': Acknowledge latest alert")
    print("- 'stats': Show statistics")
    print("- 'quit': Exit")
    print("="*60)
    
    while True:
        try:
            command = input("\nEnter command: ").strip().lower()
            
            if command in ['quit', 'exit', 'q']:
                break
            elif command in ['ack', 'acknowledge']:
                db_checker.acknowledge_latest_alert("Manual User")
            elif command == 'stats':
                stats = db_checker.get_alert_statistics()
                print(f"Alerts Today: {stats['alerts_today']}")
                print(f"Acknowledged Today: {stats['acknowledged_today']}")
                print(f"Pending Acknowledgment: {stats['pending_acknowledgment']}")
                print(f"Active Stolen Vehicles: {stats['active_stolen_vehicles']}")
            else:
                print("Unknown command. Use 'ack', 'stats', or 'quit'")
                
        except KeyboardInterrupt:
            print("\n\nShutting down alert system...")
            break
        except Exception as e:
            print(f"Error: {e}")
    
    print("Alert system stopped.")