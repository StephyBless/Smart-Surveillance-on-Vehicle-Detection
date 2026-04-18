# database_integration.py
import sqlite3
import json
import smtplib
import requests
from datetime import datetime, timedelta
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
import threading
import hashlib
from dataclasses import dataclass
from typing import List, Dict, Optional
import logging

@dataclass
class StolenVehicle:
    license_plate: str
    vehicle_type: str
    color: str
    make: str
    model: str
    year: int
    status: str  # 'stolen', 'found', 'alert'
    reported_date: str
    last_seen: Optional[str] = None
    location: Optional[str] = None
    confidence: float = 0.0

class DatabaseManager:
    """
    Advanced database management for stolen vehicle tracking
    """
    
    def __init__(self, db_path="theft_detection.db"):
        self.db_path = db_path
        self.init_database()
        self.setup_logging()
    
    def setup_logging(self):
        logging.basicConfig(
            filename='database_operations.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def init_database(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Stolen vehicles table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stolen_vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_plate TEXT UNIQUE NOT NULL,
                vehicle_type TEXT,
                color TEXT,
                make TEXT,
                model TEXT,
                year INTEGER,
                status TEXT DEFAULT 'stolen',
                reported_date TEXT,
                last_seen TEXT,
                location TEXT,
                confidence REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Detection history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS detection_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_plate TEXT,
                vehicle_type TEXT,
                color TEXT,
                speed REAL,
                location TEXT,
                timestamp TEXT,
                frame_path TEXT,
                confidence REAL,
                is_flagged BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_plate TEXT,
                alert_type TEXT,
                message TEXT,
                priority TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        ''')
        
        # System settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        self.logger.info("Database initialized successfully")
    
    def add_stolen_vehicle(self, vehicle: StolenVehicle):
        """Add a stolen vehicle to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO stolen_vehicles 
                (license_plate, vehicle_type, color, make, model, year, status, reported_date, location)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (vehicle.license_plate, vehicle.vehicle_type, vehicle.color,
                  vehicle.make, vehicle.model, vehicle.year, vehicle.status,
                  vehicle.reported_date, vehicle.location))
            
            conn.commit()
            self.logger.info(f"Added stolen vehicle: {vehicle.license_plate}")
            return True
            
        except sqlite3.Error as e:
            self.logger.error(f"Error adding stolen vehicle: {e}")
            return False
        finally:
            conn.close()
    
    def check_stolen_vehicle(self, license_plate: str) -> Optional[StolenVehicle]:
        """Check if a license plate is in stolen database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT * FROM stolen_vehicles WHERE license_plate = ? AND status = 'stolen'
            ''', (license_plate,))
            
            result = cursor.fetchone()
            if result:
                return StolenVehicle(
                    license_plate=result[1],
                    vehicle_type=result[2],
                    color=result[3],
                    make=result[4],
                    model=result[5],
                    year=result[6],
                    status=result[7],
                    reported_date=result[8],
                    last_seen=result[9],
                    location=result[10],
                    confidence=result[11]
                )
            return None
            
        except sqlite3.Error as e:
            self.logger.error(f"Error checking stolen vehicle: {e}")
            return None
        finally:
            conn.close()
    
    def log_detection(self, license_plate: str, vehicle_type: str, color: str, 
                     speed: float, location: str, timestamp: str, 
                     frame_path: str, confidence: float):
        """Log vehicle detection"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if this is a flagged vehicle
        is_flagged = self.check_stolen_vehicle(license_plate) is not None
        
        try:
            cursor.execute('''
                INSERT INTO detection_history 
                (license_plate, vehicle_type, color, speed, location, timestamp, 
                 frame_path, confidence, is_flagged)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (license_plate, vehicle_type, color, speed, location, 
                  timestamp, frame_path, confidence, is_flagged))
            
            conn.commit()
            self.logger.info(f"Logged detection: {license_plate}")
            
        except sqlite3.Error as e:
            self.logger.error(f"Error logging detection: {e}")
        finally:
            conn.close()
    
    def get_detection_history(self, license_plate: str = None, 
                            hours: int = 24) -> List[Dict]:
        """Get recent detection history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if license_plate:
                cursor.execute('''
                    SELECT * FROM detection_history 
                    WHERE license_plate = ? AND datetime(created_at) > datetime('now', '-{} hours')
                    ORDER BY created_at DESC
                '''.format(hours), (license_plate,))
            else:
                cursor.execute('''
                    SELECT * FROM detection_history 
                    WHERE datetime(created_at) > datetime('now', '-{} hours')
                    ORDER BY created_at DESC
                '''.format(hours))
            
            results = cursor.fetchall()
            return [dict(zip([col[0] for col in cursor.description], row)) for row in results]
            
        except sqlite3.Error as e:
            self.logger.error(f"Error getting detection history: {e}")
            return []
        finally:
            conn.close()


class AlertSystem:
    """
    Real-time alert system for stolen vehicle detection
    """
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.email_config = {}
        self.webhook_urls = []
        self.sms_config = {}
        self.alert_queue = []
        self.is_running = False
        
    def configure_email(self, smtp_server: str, smtp_port: int, 
                       username: str, password: str, from_email: str):
        """Configure email alerts"""
        self.email_config = {
            'smtp_server': smtp_server,
            'smtp_port': smtp_port,
            'username': username,
            'password': password,
            'from_email': from_email
        }
    
    def add_webhook(self, url: str):
        """Add webhook URL for external notifications"""
        self.webhook_urls.append(url)
    
    def send_email_alert(self, to_emails: List[str], subject: str, 
                        message: str, priority: str = 'normal'):
        """Send email alert"""
        if not self.email_config:
            return False
        
        try:
            msg = MimeMultipart()
            msg['From'] = self.email_config['from_email']
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = f"[{priority.upper()}] {subject}"
            
            # Add priority headers
            if priority == 'high':
                msg['X-Priority'] = '1'
                msg['X-MSMail-Priority'] = 'High'
            
            msg.attach(MimeText(message, 'html'))
            
            with smtplib.SMTP(self.email_config['smtp_server'], 
                            self.email_config['smtp_port']) as server:
                server.starttls()
                server.login(self.email_config['username'], 
                           self.email_config['password'])
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            print(f"Email alert failed: {e}")
            return False
    
    def send_webhook_alert(self, data: Dict):
        """Send webhook notification"""
        for url in self.webhook_urls:
            try:
                response = requests.post(url, json=data, timeout=10)
                if response.status_code == 200:
                    print(f"Webhook sent successfully to {url}")
                else:
                    print(f"Webhook failed for {url}: {response.status_code}")
            except Exception as e:
                print(f"Webhook error for {url}: {e}")
    
    def create_alert(self, license_plate: str, vehicle_info: Dict, 
                    detection_info: Dict):
        """Create comprehensive alert for stolen vehicle detection"""
        
        timestamp = datetime.now().isoformat()
        
        # Email alert
        subject = f"STOLEN VEHICLE DETECTED: {license_plate}"
        
        email_message = f"""
        <html>
        <body>
        <h2 style="color: red;">STOLEN VEHICLE ALERT</h2>
        
        <h3>Vehicle Information:</h3>
        <ul>
        <li><strong>License Plate:</strong> {license_plate}</li>
        <li><strong>Vehicle Type:</strong> {vehicle_info.get('vehicle_type', 'Unknown')}</li>
        <li><strong>Color:</strong> {vehicle_info.get('color', 'Unknown')}</li>
        <li><strong>Make/Model:</strong> {vehicle_info.get('make', 'Unknown')} {vehicle_info.get('model', 'Unknown')}</li>
        </ul>
        
        <h3>Detection Information:</h3>
        <ul>
        <li><strong>Detection Time:</strong> {timestamp}</li>
        <li><strong>Location:</strong> {detection_info.get('location', 'Unknown')}</li>
        <li><strong>Speed:</strong> {detection_info.get('speed', 0):.1f} km/h</li>
        <li><strong>Confidence:</strong> {detection_info.get('confidence', 0):.2f}</li>
        </ul>
        
        <p style="color: red;"><strong>IMMEDIATE ACTION REQUIRED</strong></p>
        </body>
        </html>
        """
        
        # Webhook data
        webhook_data = {
            'alert_type': 'stolen_vehicle_detected',
            'license_plate': license_plate,
            'vehicle_info': vehicle_info,
            'detection_info': detection_info,
            'timestamp': timestamp,
            'priority': 'high'
        }
        
        # Log alert to database
        self.log_alert(license_plate, 'stolen_vehicle_detection', 
                      f"Vehicle detected at {detection_info.get('location', 'unknown location')}", 
                      'high')
        
        # Send notifications
        self.send_webhook_alert(webhook_data)
        
        # Add to email queue (would be sent to configured recipients)
        return {
            'subject': subject,
            'message': email_message,
            'webhook_data': webhook_data
        }
    
    def log_alert(self, license_plate: str, alert_type: str, 
                 message: str, priority: str):
        """Log alert to database"""
        conn = sqlite3.connect(self.db_manager.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO alerts (license_plate, alert_type, message, priority)
                VALUES (?, ?, ?, ?)
            ''', (license_plate, alert_type, message, priority))
            
            conn.commit()
            
        except sqlite3.Error as e:
            print(f"Error logging alert: {e}")
        finally:
            conn.close()


class RealTimeMonitor:
    """
    Real-time monitoring system for continuous vehicle tracking
    """
    
    def __init__(self, db_manager: DatabaseManager, alert_system: AlertSystem):
        self.db_manager = db_manager
        self.alert_system = alert_system
        self.active_vehicles = {}  # Currently being tracked
        self.monitoring_thread = None
        self.is_monitoring = False
        
    def start_monitoring(self):
        """Start real-time monitoring"""
        self.is_monitoring = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        print("Real-time monitoring started")
    
    def stop_monitoring(self):
        """Stop real-time monitoring"""
        self.is_monitoring = False
        if self.monitoring_thread:
            self.monitoring_thread.join()
        print("Real-time monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_monitoring:
            try:
                # Check for stale vehicle tracks
                self._cleanup_stale_tracks()
                
                # Check for pattern anomalies
                self._detect_anomalies()
                
                # Update vehicle statuses
                self._update_vehicle_statuses()
                
                threading.Event().wait(5)  # Check every 5 seconds
                
            except Exception as e:
                print(f"Monitoring loop error: {e}")
    
    def update_vehicle_position(self, license_plate: str, position: tuple, 
                              timestamp: str, vehicle_info: Dict):
        """Update vehicle position in real-time tracking"""
        
        # Check if this is a stolen vehicle
        stolen_vehicle = self.db_manager.check_stolen_vehicle(license_plate)
        
        if stolen_vehicle:
            # Create immediate alert
            alert_info = self.alert_system.create_alert(
                license_plate, 
                vehicle_info,
                {
                    'location': f"Coordinates: {position}",
                    'timestamp': timestamp,
                    'speed': vehicle_info.get('speed', 0),
                    'confidence': vehicle_info.get('confidence', 0)
                }
            )
            print(f"ALERT CREATED for stolen vehicle: {license_plate}")
        
        # Update active tracking
        self.active_vehicles[license_plate] = {
            'position': position,
            'timestamp': timestamp,
            'vehicle_info': vehicle_info,
            'is_stolen': stolen_vehicle is not None
        }
        
        # Log to database
        self.db_manager.log_detection(
            license_plate=license_plate,
            vehicle_type=vehicle_info.get('vehicle_type', 'unknown'),
            color=vehicle_info.get('color', 'unknown'),
            speed=vehicle_info.get('speed', 0),
            location=f"Coordinates: {position}",
            timestamp=timestamp,
            frame_path=vehicle_info.get('frame_path', ''),
            confidence=vehicle_info.get('confidence', 0)
        )
    
    def _cleanup_stale_tracks(self):
        """Remove vehicles that haven't been seen recently"""
        current_time = datetime.now()
        stale_threshold = timedelta(minutes=5)
        
        stale_vehicles = []
        for license_plate, info in self.active_vehicles.items():
            last_seen = datetime.fromisoformat(info['timestamp'])
            if current_time - last_seen > stale_threshold:
                stale_vehicles.append(license_plate)
        
        for vehicle in stale_vehicles:
            del self.active_vehicles[vehicle]
    
    def _detect_anomalies(self):
        """Detect suspicious patterns in vehicle behavior"""
        # Implementation for detecting anomalous behavior
        # Such as vehicles appearing in multiple locations quickly
        # or unusual movement patterns
        pass
    
    def _update_vehicle_statuses(self):
        """Update vehicle statuses in database"""
        for license_plate, info in self.active_vehicles.items():
            if info['is_stolen']:
                # Update last seen information for stolen vehicles
                conn = sqlite3.connect(self.db_manager.db_path)
                cursor = conn.cursor()
                try:
                    cursor.execute('''
                        UPDATE stolen_vehicles 
                        SET last_seen = ?, location = ? 
                        WHERE license_plate = ?
                    ''', (info['timestamp'], f"Coordinates: {info['position']}", 
                          license_plate))
                    conn.commit()
                except sqlite3.Error as e:
                    print(f"Error updating vehicle status: {e}")
                finally:
                    conn.close()


# Integration example
def integrate_database_system(main_app):
    """
    Integration function to add database system to main app
    """
    # Initialize components
    main_app.db_manager = DatabaseManager()
    main_app.alert_system = AlertSystem(main_app.db_manager)
    main_app.monitor = RealTimeMonitor(main_app.db_manager, main_app.alert_system)
    
    # Start real-time monitoring
    main_app.monitor.start_monitoring()
    
    # Add database logging to processing
    def enhanced_processing_with_db(original_method):
        def wrapper(frame, frame_nmr):
            # Call original processing
            result = original_method(frame, frame_nmr)
            
            # Add database logging for each detected vehicle
            if hasattr(main_app, 'results') and frame_nmr in main_app.results:
                timestamp = datetime.now().isoformat()
                
                for car_id, data in main_app.results[frame_nmr].items():
                    if 'license_plate' in data:
                        license_plate = data['license_plate'].get('text', '')
                        if license_plate and license_plate != '0':
                            # Update real-time monitoring
                            bbox = data['car']['bbox']
                            center_pos = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
                            
                            vehicle_info = {
                                'vehicle_type': data.get('vehicle_type', 'unknown'),
                                'color': data.get('vehicle_color', 'unknown'),
                                'speed': data.get('speed_kmh', 0),
                                'confidence': data['license_plate'].get('text_score', 0),
                                'frame_path': f'frame_{frame_nmr}.jpg'
                            }
                            
                            main_app.monitor.update_vehicle_position(
                                license_plate, center_pos, timestamp, vehicle_info
                            )
            
            return result
        return wrapper
    
    return enhanced_processing_with_db