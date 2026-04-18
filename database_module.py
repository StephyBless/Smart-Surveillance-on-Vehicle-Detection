"""
MODULE 4: MySQL DATABASE MODULE FOR VEHICLE THEFT DETECTION
This module handles:
1. Detected vehicles database storage
2. Stolen vehicles database storage
3. Automatic matching with severity levels (100%, 80-99%, etc.)
4. Alert generation for matched vehicles
"""

import mysql.connector
from mysql.connector import Error
from datetime import datetime
from difflib import SequenceMatcher
import json
import re


class VehicleDatabaseManager:
    """Manages both detected and stolen vehicle databases using MySQL"""
    
    def __init__(self, host='localhost', user='root', password='', database='vehicle_theft_db'):
        """
        Initialize the MySQL database manager
        
        Args:
            host: MySQL server host (default: 'localhost')
            user: MySQL username (default: 'root')
            password: MySQL password
            database: Database name (default: 'vehicle_theft_db')
        """
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.conn = None
        self.cursor = None
        
        # Severity thresholds
        self.CRITICAL_THRESHOLD = 100  # Exact match
        self.HIGH_THRESHOLD = 90       # 90-99% match
        self.MEDIUM_THRESHOLD = 80     # 80-89% match
        
        self.connect()
        self.create_database()
        self.create_tables()
    
    def connect(self):
        """Connect to MySQL server"""
        try:
            # First connect without database to create it if needed
            self.conn = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password
            )
            self.cursor = self.conn.cursor()
            print(f"✅ Connected to MySQL server: {self.host}")
        except Error as e:
            print(f"❌ MySQL connection error: {e}")
            raise
    
    def create_database(self):
        """Create the database if it doesn't exist"""
        try:
            self.cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.database}")
            self.cursor.execute(f"USE {self.database}")
            print(f"✅ Database '{self.database}' is ready")
        except Error as e:
            print(f"❌ Database creation error: {e}")
            raise
    
    def create_tables(self):
        """Create the necessary database tables"""
        try:
            # Table 1: DETECTED VEHICLES
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS detected_vehicles (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    detection_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    vehicle_number VARCHAR(20) NOT NULL,
                    car_id INT,
                    frame_number INT,
                    confidence_score DECIMAL(5,2),
                    vehicle_color VARCHAR(50),
                    vehicle_model VARCHAR(100),
                    detection_location VARCHAR(255),
                    image_path VARCHAR(500),
                    video_source VARCHAR(500),
                    additional_info TEXT,
                    matched_stolen_id INT DEFAULT NULL,
                    match_severity VARCHAR(20) DEFAULT NULL,
                    INDEX idx_vehicle_number (vehicle_number),
                    INDEX idx_detection_timestamp (detection_timestamp)
                )
            ''')
            
            # Table 2: STOLEN VEHICLES
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS stolen_vehicles (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    report_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    vehicle_number VARCHAR(20) NOT NULL UNIQUE,
                    vehicle_color VARCHAR(50),
                    vehicle_model VARCHAR(100),
                    vehicle_make VARCHAR(100),
                    vehicle_year INT,
                    owner_name VARCHAR(255),
                    owner_contact VARCHAR(100),
                    theft_date DATE,
                    theft_location VARCHAR(255),
                    case_number VARCHAR(100),
                    police_station VARCHAR(255),
                    additional_details TEXT,
                    status VARCHAR(20) DEFAULT 'ACTIVE',
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_vehicle_number (vehicle_number),
                    INDEX idx_status (status)
                )
            ''')
            
            # Table 3: MATCH ALERTS
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS match_alerts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    alert_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    detected_vehicle_id INT,
                    stolen_vehicle_id INT,
                    detected_number VARCHAR(20),
                    stolen_number VARCHAR(20),
                    match_percentage DECIMAL(5,2),
                    severity_level VARCHAR(20),
                    alert_status VARCHAR(20) DEFAULT 'NEW',
                    action_taken TEXT,
                    notes TEXT,
                    FOREIGN KEY (detected_vehicle_id) REFERENCES detected_vehicles(id),
                    FOREIGN KEY (stolen_vehicle_id) REFERENCES stolen_vehicles(id),
                    INDEX idx_severity (severity_level),
                    INDEX idx_alert_timestamp (alert_timestamp)
                )
            ''')
            
            self.conn.commit()
            print("✅ All tables created successfully")
            
        except Error as e:
            print(f"❌ Table creation error: {e}")
            raise
    
    # ==================== DETECTED VEHICLES OPERATIONS ====================
    
    def add_detected_vehicle(self, vehicle_data):
        """
        Add a detected vehicle to the database
        
        Args:
            vehicle_data: Dictionary containing vehicle information
                Required: vehicle_number
                Optional: car_id, frame_number, confidence_score, vehicle_color, 
                         vehicle_model, detection_location, image_path, video_source,
                         additional_info
        
        Returns:
            int: ID of the inserted record, or None if failed
        """
        try:
            query = '''
                INSERT INTO detected_vehicles 
                (vehicle_number, car_id, frame_number, confidence_score, 
                 vehicle_color, vehicle_model, detection_location, 
                 image_path, video_source, additional_info)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            '''
            
            values = (
                vehicle_data.get('vehicle_number'),
                vehicle_data.get('car_id'),
                vehicle_data.get('frame_number'),
                vehicle_data.get('confidence_score'),
                vehicle_data.get('vehicle_color'),
                vehicle_data.get('vehicle_model'),
                vehicle_data.get('detection_location'),
                vehicle_data.get('image_path'),
                vehicle_data.get('video_source'),
                vehicle_data.get('additional_info')
            )
            
            self.cursor.execute(query, values)
            self.conn.commit()
            
            detected_id = self.cursor.lastrowid
            print(f"✅ Detected vehicle added: {vehicle_data.get('vehicle_number')} (ID: {detected_id})")
            
            # Automatically check for matches
            self.check_and_create_matches(detected_id, vehicle_data.get('vehicle_number'))
            
            return detected_id
            
        except Error as e:
            print(f"❌ Error adding detected vehicle: {e}")
            self.conn.rollback()
            return None
    
    def get_all_detected_vehicles(self, limit=100):
        """Get all detected vehicles"""
        try:
            query = '''
                SELECT * FROM detected_vehicles 
                ORDER BY detection_timestamp DESC 
                LIMIT %s
            '''
            self.cursor.execute(query, (limit,))
            results = self.cursor.fetchall()
            
            # Get column names
            columns = [desc[0] for desc in self.cursor.description]
            
            # Convert to list of dictionaries
            vehicles = []
            for row in results:
                vehicles.append(dict(zip(columns, row)))
            
            return vehicles
            
        except Error as e:
            print(f"❌ Error fetching detected vehicles: {e}")
            return []
    
    # ==================== STOLEN VEHICLES OPERATIONS ====================
    
    def add_stolen_vehicle(self, vehicle_data):
        """
        Add a stolen vehicle to the database
        
        Args:
            vehicle_data: Dictionary containing stolen vehicle information
                Required: vehicle_number
                Optional: vehicle_color, vehicle_model, vehicle_make, vehicle_year,
                         owner_name, owner_contact, theft_date, theft_location,
                         case_number, police_station, additional_details
        
        Returns:
            int: ID of the inserted record, or None if failed
        """
        try:
            query = '''
                INSERT INTO stolen_vehicles 
                (vehicle_number, vehicle_color, vehicle_model, vehicle_make, 
                 vehicle_year, owner_name, owner_contact, theft_date, 
                 theft_location, case_number, police_station, additional_details)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            '''
            
            values = (
                vehicle_data.get('vehicle_number'),
                vehicle_data.get('vehicle_color'),
                vehicle_data.get('vehicle_model'),
                vehicle_data.get('vehicle_make'),
                vehicle_data.get('vehicle_year'),
                vehicle_data.get('owner_name'),
                vehicle_data.get('owner_contact'),
                vehicle_data.get('theft_date'),
                vehicle_data.get('theft_location'),
                vehicle_data.get('case_number'),
                vehicle_data.get('police_station'),
                vehicle_data.get('additional_details')
            )
            
            self.cursor.execute(query, values)
            self.conn.commit()
            
            stolen_id = self.cursor.lastrowid
            print(f"✅ Stolen vehicle added: {vehicle_data.get('vehicle_number')} (ID: {stolen_id})")
            
            return stolen_id
            
        except Error as e:
            print(f"❌ Error adding stolen vehicle: {e}")
            self.conn.rollback()
            return None
    
    def get_all_stolen_vehicles(self, status='ACTIVE'):
        """Get all stolen vehicles with given status"""
        try:
            query = '''
                SELECT * FROM stolen_vehicles 
                WHERE status = %s
                ORDER BY report_timestamp DESC
            '''
            self.cursor.execute(query, (status,))
            results = self.cursor.fetchall()
            
            columns = [desc[0] for desc in self.cursor.description]
            
            vehicles = []
            for row in results:
                vehicles.append(dict(zip(columns, row)))
            
            return vehicles
            
        except Error as e:
            print(f"❌ Error fetching stolen vehicles: {e}")
            return []
    
    def update_stolen_vehicle_status(self, vehicle_id, status):
        """Update the status of a stolen vehicle (e.g., 'ACTIVE', 'RECOVERED', 'CLOSED')"""
        try:
            query = '''
                UPDATE stolen_vehicles 
                SET status = %s, last_updated = CURRENT_TIMESTAMP
                WHERE id = %s
            '''
            self.cursor.execute(query, (status, vehicle_id))
            self.conn.commit()
            print(f"✅ Stolen vehicle {vehicle_id} status updated to: {status}")
            return True
            
        except Error as e:
            print(f"❌ Error updating stolen vehicle status: {e}")
            self.conn.rollback()
            return False
    
    # ==================== MATCHING AND ALERT OPERATIONS ====================
    
    def calculate_match_percentage(self, str1, str2):
        """
        Calculate similarity percentage between two strings
        
        Args:
            str1: First string (detected vehicle number)
            str2: Second string (stolen vehicle number)
        
        Returns:
            float: Match percentage (0-100)
        """
        # Clean strings: remove spaces, convert to uppercase
        clean1 = re.sub(r'[^A-Z0-9]', '', str1.upper())
        clean2 = re.sub(r'[^A-Z0-9]', '', str2.upper())
        
        # Calculate similarity using SequenceMatcher
        similarity = SequenceMatcher(None, clean1, clean2).ratio()
        
        return round(similarity * 100, 2)
    
    def determine_severity(self, match_percentage):
        """
        Determine alert severity based on match percentage
        
        Returns:
            str: 'CRITICAL', 'HIGH', 'MEDIUM', or None
        """
        if match_percentage == self.CRITICAL_THRESHOLD:
            return 'CRITICAL'
        elif match_percentage >= self.HIGH_THRESHOLD:
            return 'HIGH'
        elif match_percentage >= self.MEDIUM_THRESHOLD:
            return 'MEDIUM'
        else:
            return None
    
    def check_and_create_matches(self, detected_vehicle_id, detected_number):
        """
        Check detected vehicle against all stolen vehicles and create alerts
        
        Args:
            detected_vehicle_id: ID of the detected vehicle
            detected_number: Vehicle number of detected vehicle
        """
        try:
            # Get all active stolen vehicles
            stolen_vehicles = self.get_all_stolen_vehicles(status='ACTIVE')
            
            matches_found = []
            
            for stolen in stolen_vehicles:
                stolen_number = stolen['vehicle_number']
                
                # Calculate match percentage
                match_percentage = self.calculate_match_percentage(detected_number, stolen_number)
                
                # Determine severity
                severity = self.determine_severity(match_percentage)
                
                # Only create alert if match is above minimum threshold (80%)
                if severity:
                    matches_found.append({
                        'stolen_id': stolen['id'],
                        'stolen_number': stolen_number,
                        'match_percentage': match_percentage,
                        'severity': severity
                    })
            
            # Create alerts for all matches
            for match in matches_found:
                self.create_match_alert(
                    detected_vehicle_id=detected_vehicle_id,
                    stolen_vehicle_id=match['stolen_id'],
                    detected_number=detected_number,
                    stolen_number=match['stolen_number'],
                    match_percentage=match['match_percentage'],
                    severity_level=match['severity']
                )
            
            if matches_found:
                print(f"🚨 Found {len(matches_found)} matches for vehicle: {detected_number}")
                for match in matches_found:
                    print(f"   - {match['severity']} alert: {match['match_percentage']}% match with {match['stolen_number']}")
            
            return matches_found
            
        except Error as e:
            print(f"❌ Error checking matches: {e}")
            return []
    
    def create_match_alert(self, detected_vehicle_id, stolen_vehicle_id, 
                          detected_number, stolen_number, match_percentage, 
                          severity_level):
        """
        Create a match alert in the database
        
        Args:
            detected_vehicle_id: ID of detected vehicle
            stolen_vehicle_id: ID of stolen vehicle
            detected_number: Detected vehicle number
            stolen_number: Stolen vehicle number
            match_percentage: Match percentage
            severity_level: Alert severity (CRITICAL, HIGH, MEDIUM)
        
        Returns:
            int: Alert ID or None
        """
        try:
            query = '''
                INSERT INTO match_alerts 
                (detected_vehicle_id, stolen_vehicle_id, detected_number, 
                 stolen_number, match_percentage, severity_level)
                VALUES (%s, %s, %s, %s, %s, %s)
            '''
            
            values = (
                detected_vehicle_id,
                stolen_vehicle_id,
                detected_number,
                stolen_number,
                match_percentage,
                severity_level
            )
            
            self.cursor.execute(query, values)
            self.conn.commit()
            
            alert_id = self.cursor.lastrowid
            
            # Update detected vehicle with match info
            update_query = '''
                UPDATE detected_vehicles 
                SET matched_stolen_id = %s, match_severity = %s
                WHERE id = %s
            '''
            self.cursor.execute(update_query, (stolen_vehicle_id, severity_level, detected_vehicle_id))
            self.conn.commit()
            
            print(f"🚨 {severity_level} ALERT created! (ID: {alert_id})")
            
            return alert_id
            
        except Error as e:
            print(f"❌ Error creating match alert: {e}")
            self.conn.rollback()
            return None
    
    def get_alerts(self, severity=None, status='NEW', limit=100):
        """
        Get match alerts with optional filtering
        
        Args:
            severity: Filter by severity level (CRITICAL, HIGH, MEDIUM) or None for all
            status: Filter by alert status (default: 'NEW')
            limit: Maximum number of results
        
        Returns:
            list: List of alert dictionaries
        """
        try:
            if severity:
                query = '''
                    SELECT a.*, 
                           d.detection_location, d.detection_timestamp as detected_at,
                           s.owner_name, s.owner_contact, s.case_number, s.police_station
                    FROM match_alerts a
                    LEFT JOIN detected_vehicles d ON a.detected_vehicle_id = d.id
                    LEFT JOIN stolen_vehicles s ON a.stolen_vehicle_id = s.id
                    WHERE a.severity_level = %s AND a.alert_status = %s
                    ORDER BY a.alert_timestamp DESC
                    LIMIT %s
                '''
                self.cursor.execute(query, (severity, status, limit))
            else:
                query = '''
                    SELECT a.*, 
                           d.detection_location, d.detection_timestamp as detected_at,
                           s.owner_name, s.owner_contact, s.case_number, s.police_station
                    FROM match_alerts a
                    LEFT JOIN detected_vehicles d ON a.detected_vehicle_id = d.id
                    LEFT JOIN stolen_vehicles s ON a.stolen_vehicle_id = s.id
                    WHERE a.alert_status = %s
                    ORDER BY a.alert_timestamp DESC
                    LIMIT %s
                '''
                self.cursor.execute(query, (status, limit))
            
            results = self.cursor.fetchall()
            columns = [desc[0] for desc in self.cursor.description]
            
            alerts = []
            for row in results:
                alerts.append(dict(zip(columns, row)))
            
            return alerts
            
        except Error as e:
            print(f"❌ Error fetching alerts: {e}")
            return []
    
    def update_alert_status(self, alert_id, status, action_taken=None, notes=None):
        """Update alert status and action taken"""
        try:
            query = '''
                UPDATE match_alerts 
                SET alert_status = %s, action_taken = %s, notes = %s
                WHERE id = %s
            '''
            self.cursor.execute(query, (status, action_taken, notes, alert_id))
            self.conn.commit()
            print(f"✅ Alert {alert_id} updated to status: {status}")
            return True
            
        except Error as e:
            print(f"❌ Error updating alert: {e}")
            self.conn.rollback()
            return False
    
    # ==================== UTILITY FUNCTIONS ====================
    
    def get_statistics(self):
        """Get database statistics"""
        try:
            stats = {}
            
            # Total detected vehicles
            self.cursor.execute("SELECT COUNT(*) FROM detected_vehicles")
            stats['total_detected'] = self.cursor.fetchone()[0]
            
            # Total stolen vehicles
            self.cursor.execute("SELECT COUNT(*) FROM stolen_vehicles WHERE status = 'ACTIVE'")
            stats['total_stolen_active'] = self.cursor.fetchone()[0]
            
            # Total alerts by severity
            self.cursor.execute("""
                SELECT severity_level, COUNT(*) as count 
                FROM match_alerts 
                WHERE alert_status = 'NEW'
                GROUP BY severity_level
            """)
            
            severity_counts = {}
            for row in self.cursor.fetchall():
                severity_counts[row[0]] = row[1]
            
            stats['critical_alerts'] = severity_counts.get('CRITICAL', 0)
            stats['high_alerts'] = severity_counts.get('HIGH', 0)
            stats['medium_alerts'] = severity_counts.get('MEDIUM', 0)
            stats['total_new_alerts'] = sum(severity_counts.values())
            
            return stats
            
        except Error as e:
            print(f"❌ Error getting statistics: {e}")
            return {}
    
    def search_detected_vehicles(self, vehicle_number):
        """Search for detected vehicles by number"""
        try:
            query = '''
                SELECT * FROM detected_vehicles 
                WHERE vehicle_number LIKE %s
                ORDER BY detection_timestamp DESC
            '''
            self.cursor.execute(query, (f'%{vehicle_number}%',))
            results = self.cursor.fetchall()
            
            columns = [desc[0] for desc in self.cursor.description]
            vehicles = []
            for row in results:
                vehicles.append(dict(zip(columns, row)))
            
            return vehicles
            
        except Error as e:
            print(f"❌ Error searching detected vehicles: {e}")
            return []
    
    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        print("✅ Database connection closed")
    
    def __del__(self):
        """Destructor to ensure connection is closed"""
        try:
            self.close()
        except:
            pass


# ==================== HELPER FUNCTIONS FOR EASY INTEGRATION ====================

def create_database_instance(host='localhost', user='root', password='', database='vehicle_theft_db'):
    """
    Helper function to create a database instance
    
    Usage:
        db = create_database_instance(
            host='localhost',
            user='root',
            password='yourpassword',
            database='vehicle_theft_db'
        )
    """
    return VehicleDatabaseManager(host, user, password, database)


def format_vehicle_data_from_detection(license_number, car_id, frame_number, 
                                       confidence_score, video_source=None):
    """
    Helper function to format vehicle data from your detection system
    
    Usage in your existing code:
        vehicle_data = format_vehicle_data_from_detection(
            license_number='TN09AB1234',
            car_id=1,
            frame_number=150,
            confidence_score=0.95,
            video_source='sample_video.mp4'
        )
        db.add_detected_vehicle(vehicle_data)
    """
    return {
        'vehicle_number': license_number,
        'car_id': car_id,
        'frame_number': frame_number,
        'confidence_score': confidence_score,
        'video_source': video_source
    }