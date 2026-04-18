"""
Integration module for Deep Learning-Based Theft Detection IDS
Adds comprehensive threat analysis to your existing License Plate Recognition system
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from datetime import datetime, timedelta
import json
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

# Import the IDS system
from theft_ids_system import IntegratedTheftDetectionSystem


def add_ids_features(app_instance):
    """Add IDS features to existing app instance"""
    
    # Initialize the IDS system
    app_instance.ids_system = IntegratedTheftDetectionSystem()
    
    # Add IDS-specific GUI elements
    add_ids_gui(app_instance)
    
    # Enhance existing processing methods
    enhance_processing_with_ids(app_instance)
    
    # Add new methods for IDS features
    add_ids_methods(app_instance)


def add_ids_gui(app_instance):
    """Add IDS GUI elements to existing interface"""
    
    # Create new IDS tab
    ids_frame = ttk.Frame(app_instance.notebook)
    app_instance.notebook.add(ids_frame, text="🛡️ Theft Detection IDS")
    
    # Top section - System status
    status_frame = ttk.LabelFrame(ids_frame, text="IDS System Status", padding=10)
    status_frame.pack(fill=tk.X, padx=5, pady=5)
    
    # System status indicators
    app_instance.ids_status_labels = {
        'system_status': tk.Label(status_frame, text="Status: OPERATIONAL", fg='green', font=('Arial', 10, 'bold')),
        'active_threats': tk.Label(status_frame, text="Active Threats: 0", font=('Arial', 10)),
        'total_detections': tk.Label(status_frame, text="Total Detections: 0", font=('Arial', 10)),
        'avg_threat_score': tk.Label(status_frame, text="Avg Threat Score: 0.0", font=('Arial', 10)),
        'last_analysis': tk.Label(status_frame, text="Last Analysis: Never", font=('Arial', 10))
    }
    
    for label in app_instance.ids_status_labels.values():
        label.pack(anchor=tk.W, padx=5, pady=2)
    
    # Control buttons section
    controls_frame = ttk.LabelFrame(ids_frame, text="IDS Controls", padding=10)
    controls_frame.pack(fill=tk.X, padx=5, pady=5)
    
    control_buttons_frame = ttk.Frame(controls_frame)
    control_buttons_frame.pack(fill=tk.X)
    
    ttk.Button(control_buttons_frame, text="View Threat Timeline", 
              command=lambda: app_instance.show_threat_timeline()).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_buttons_frame, text="Generate Report", 
              command=lambda: app_instance.generate_ids_report()).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_buttons_frame, text="View Statistics", 
              command=lambda: app_instance.show_ids_statistics()).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_buttons_frame, text="Test IDS System", 
              command=lambda: app_instance.test_ids_system()).pack(side=tk.LEFT, padx=5)
    
    # Real-time threat monitoring
    monitoring_frame = ttk.LabelFrame(ids_frame, text="Real-time Threat Monitoring", padding=10)
    monitoring_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    # Create threat monitoring display
    columns = ('Time', 'Vehicle ID', 'License Plate', 'Threat Level', 'Fusion Score', 'Patterns', 'Actions')
    app_instance.ids_threats_tree = ttk.Treeview(monitoring_frame, columns=columns, show='headings', height=12)
    
    # Configure column widths for IDS threats
    column_widths = {
        'Time': 80,
        'Vehicle ID': 80,
        'License Plate': 100,
        'Threat Level': 80,
        'Fusion Score': 80,
        'Patterns': 150,
        'Actions': 120
    }
    
    for col in columns:
        app_instance.ids_threats_tree.heading(col, text=col)
        app_instance.ids_threats_tree.column(col, width=column_widths.get(col, 100), anchor=tk.CENTER)
    
    # Scrollbar for IDS threats treeview
    ids_scrollbar = ttk.Scrollbar(monitoring_frame, orient=tk.VERTICAL, command=app_instance.ids_threats_tree.yview)
    app_instance.ids_threats_tree.configure(yscrollcommand=ids_scrollbar.set)
    
    app_instance.ids_threats_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    ids_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    # Bind double-click event for IDS threats
    app_instance.ids_threats_tree.bind('<Double-1>', lambda e: app_instance.on_ids_threat_double_click(e))
    
    # Start periodic updates
    app_instance.update_ids_status()


def enhance_processing_with_ids(app_instance):
    """Enhance existing processing methods with IDS analysis"""
    
    # Store original method
    original_process_frame = app_instance.process_frame_enhanced
    
    def enhanced_process_frame_with_ids(frame, frame_nmr):
        # Call original processing
        original_process_frame(frame, frame_nmr)
        
        # Add IDS analysis for stolen vehicles
        if frame_nmr in app_instance.results:
            for car_id, detection_data in app_instance.results[frame_nmr].items():
                if 'license_plate' in detection_data and detection_data['license_plate']['text']:
                    
                    # Get existing database and intelligence alerts
                    database_alert = detection_data.get('database_alert', {})
                    intelligence_alert = detection_data.get('intelligence_analysis', {})
                    
                    # Perform comprehensive IDS threat analysis
                    ids_result = app_instance.ids_system.analyze_comprehensive_threat(
                        str(car_id), detection_data, database_alert
                    )
                    
                    # Add IDS results to detection data
                    detection_data['ids_analysis'] = ids_result
                    
                    # Handle significant threats
                    if ids_result['threat_level'] in ['MEDIUM', 'HIGH', 'CRITICAL']:
                        app_instance.handle_ids_threat(ids_result, detection_data['license_plate']['text'])
    
    # Replace the method
    app_instance.process_frame_enhanced = enhanced_process_frame_with_ids


def add_ids_methods(app_instance):
    """Add new methods for IDS features"""
    
    def handle_ids_threat(self, ids_result, plate_text):
        """Handle IDS threat detection"""
        threat_level = ids_result['threat_level']
        fusion_score = ids_result['fusion_score']
        
        # Schedule GUI updates on main thread
        def update_gui():
            # Add to IDS threats tree
            if hasattr(self, 'ids_threats_tree'):
                timestamp = datetime.now().strftime("%H:%M:%S")
                patterns_str = ', '.join(ids_result['detected_patterns'][:2])  # Show first 2 patterns
                if len(ids_result['detected_patterns']) > 2:
                    patterns_str += "..."
                
                actions_str = ', '.join(ids_result['recommendations'][:1])  # Show first recommendation
                
                # Add to tree with color coding
                item_id = self.ids_threats_tree.insert('', 0, values=(
                    timestamp,
                    ids_result['vehicle_id'],
                    plate_text,
                    threat_level,
                    f"{fusion_score:.2f}",
                    patterns_str,
                    actions_str
                ))
                
                # Color code based on threat level
                if threat_level == 'CRITICAL':
                    self.ids_threats_tree.set(item_id, 'Threat Level', f"🔴 {threat_level}")
                elif threat_level == 'HIGH':
                    self.ids_threats_tree.set(item_id, 'Threat Level', f"🟠 {threat_level}")
                elif threat_level == 'MEDIUM':
                    self.ids_threats_tree.set(item_id, 'Threat Level', f"🟡 {threat_level}")
            
            # Show popup for critical threats
            if threat_level == 'CRITICAL':
                self.show_critical_threat_popup(ids_result, plate_text)
            
            # Update status
            self.update_ids_status()
        
        self.root.after(0, update_gui)
        
        # Log the threat
        self.log_message(f"🛡️ IDS THREAT: {plate_text} - {threat_level} (Score: {fusion_score:.2f})")
        
        # Log detected patterns
        if ids_result['detected_patterns']:
            patterns = ', '.join(ids_result['detected_patterns'])
            self.log_message(f"   Patterns: {patterns}")
    
    def show_critical_threat_popup(self, ids_result, plate_text):
        """Show popup for critical threat alerts"""
        # Create alert popup
        alert_popup = tk.Toplevel(self.root)
        alert_popup.title("🛡️ CRITICAL THEFT THREAT")
        alert_popup.geometry("600x500")
        alert_popup.configure(bg='#c0392b')
        alert_popup.attributes('-topmost', True)
        
        # Alert header
        header_label = tk.Label(alert_popup, text="🛡️ CRITICAL THREAT DETECTED", 
                               font=('Arial', 16, 'bold'), bg='#a93226', fg='white')
        header_label.pack(fill=tk.X, pady=5)
        
        # Alert details
        details_frame = tk.Frame(alert_popup, bg='white')
        details_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        details_text = tk.Text(details_frame, wrap=tk.WORD, font=('Consolas', 10))
        details_scrollbar = ttk.Scrollbar(details_frame, orient=tk.VERTICAL, command=details_text.yview)
        details_text.configure(yscrollcommand=details_scrollbar.set)
        
        alert_content = f"""
CRITICAL THEFT THREAT DETECTED
{'='*60}

VEHICLE INFORMATION:
License Plate: {plate_text}
Vehicle ID: {ids_result['vehicle_id']}
Threat Level: {ids_result['threat_level']}
Fusion Score: {ids_result['fusion_score']:.3f}

COMPONENT ANALYSIS:
Database Match: {ids_result['component_scores']['database_match']:.2f}
Behavior Anomaly: {ids_result['component_scores']['behavior_anomaly']:.2f}
CAN Bus Simulation: {ids_result['component_scores']['can_simulation']:.2f}
ML Prediction: {ids_result['component_scores']['ml_prediction']:.2f}

DETECTED PATTERNS:
"""
        for pattern in ids_result['detected_patterns']:
            alert_content += f"• {pattern.replace('_', ' ').title()}\n"
        
        alert_content += f"\nRECOMMENDED ACTIONS:\n"
        for rec in ids_result['recommendations']:
            alert_content += f"• {rec}\n"
        
        alert_content += f"""
{'='*60}
DETECTION TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
EVIDENCE PACKAGE: {ids_result.get('evidence_data', {}).get('detection_data', {}).get('timestamp', 'N/A')}
"""
        
        details_text.insert(tk.END, alert_content)
        details_text.config(state=tk.DISABLED)
        
        details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Control buttons
        button_frame = tk.Frame(alert_popup, bg='#c0392b')
        button_frame.pack(fill=tk.X, pady=5)
        
        tk.Button(button_frame, text="ACKNOWLEDGE THREAT", command=alert_popup.destroy,
                 bg='#e74c3c', fg='white', font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="VIEW TIMELINE", 
                 command=lambda: self.show_vehicle_threat_timeline(ids_result['vehicle_id']),
                 bg='#3498db', fg='white', font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="CLOSE", command=alert_popup.destroy,
                 bg='#95a5a6', fg='white', font=('Arial', 12, 'bold')).pack(side=tk.RIGHT, padx=10)
    
    def show_threat_timeline(self):
        """Show threat timeline for all vehicles"""
        timeline_window = tk.Toplevel(self.root)
        timeline_window.title("Threat Timeline - All Vehicles")
        timeline_window.geometry("900x600")
        
        # Get threat statistics
        stats = self.ids_system.get_threat_statistics()
        
        # Create timeline display
        timeline_frame = tk.Frame(timeline_window)
        timeline_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Statistics summary
        stats_text = tk.Text(timeline_frame, height=8, wrap=tk.WORD, font=('Consolas', 10))
        stats_content = f"""
THREAT DETECTION SYSTEM - TIMELINE OVERVIEW
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*60}

CURRENT STATUS:
• Active Threats: {stats['active_threats']}
• System Status: {stats['system_status']}
• Unique Vehicles Monitored: {stats['unique_vehicles_monitored']}
• Average Threat Score: {stats['average_threat_score']:.3f}

THREAT DISTRIBUTION (Last 24 Hours):
"""
        for level, count in stats['threat_distribution'].items():
            stats_content += f"• {level}: {count}\n"
        
        stats_text.insert(tk.END, stats_content)
        stats_text.config(state=tk.DISABLED)
        stats_text.pack(fill=tk.X, pady=5)
        
        # Timeline tree
        columns = ('Time', 'Vehicle ID', 'Threat Level', 'Score', 'Patterns')
        timeline_tree = ttk.Treeview(timeline_frame, columns=columns, show='headings')
        
        for col in columns:
            timeline_tree.heading(col, text=col)
            timeline_tree.column(col, width=150, anchor=tk.CENTER)
        
        # Scrollbar for timeline
        timeline_scrollbar = ttk.Scrollbar(timeline_frame, orient=tk.VERTICAL, command=timeline_tree.yview)
        timeline_tree.configure(yscrollcommand=timeline_scrollbar.set)
        
        # Get recent threats for display
        recent_threats = []
        for vehicle_id, history in self.ids_system.detection_history.items():
            for detection in history[-10:]:  # Last 10 detections per vehicle
                recent_threats.append({
                    'vehicle_id': vehicle_id,
                    'timestamp': detection.get('timestamp', 0),
                    'threat_level': detection.get('threat_level', 'LOW'),
                    'fusion_score': detection.get('fusion_score', 0),
                    'patterns': detection.get('patterns', [])
                })
        
        # Sort by timestamp (most recent first)
        recent_threats.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Populate timeline tree
        for threat in recent_threats[:50]:  # Show last 50 threats
            time_str = datetime.fromtimestamp(threat['timestamp']).strftime("%H:%M:%S")
            patterns_str = ', '.join(threat['patterns'][:2])
            if len(threat['patterns']) > 2:
                patterns_str += "..."
            
            timeline_tree.insert('', 'end', values=(
                time_str,
                threat['vehicle_id'],
                threat['threat_level'],
                f"{threat['fusion_score']:.2f}",
                patterns_str
            ))
        
        timeline_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        timeline_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Control buttons for timeline
        control_frame = tk.Frame(timeline_window)
        control_frame.pack(fill=tk.X, pady=5)
        
        tk.Button(control_frame, text="Refresh", 
                 command=lambda: self.refresh_timeline(timeline_tree),
                 font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        tk.Button(control_frame, text="Export Timeline", 
                 command=lambda: self.export_timeline(),
                 font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        tk.Button(control_frame, text="Close", 
                 command=timeline_window.destroy,
                 font=('Arial', 10, 'bold')).pack(side=tk.RIGHT, padx=5)
    
    def show_vehicle_threat_timeline(self, vehicle_id):
        """Show detailed timeline for specific vehicle"""
        timeline_window = tk.Toplevel(self.root)
        timeline_window.title(f"Vehicle Threat Timeline - ID: {vehicle_id}")
        timeline_window.geometry("800x500")
        
        # Get vehicle-specific timeline
        vehicle_timeline = self.ids_system.get_vehicle_threat_timeline(vehicle_id)
        
        # Create display
        timeline_frame = tk.Frame(timeline_window)
        timeline_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Vehicle info header
        info_label = tk.Label(timeline_frame, 
                             text=f"Threat History for Vehicle ID: {vehicle_id}",
                             font=('Arial', 14, 'bold'))
        info_label.pack(pady=10)
        
        # Timeline details
        details_text = tk.Text(timeline_frame, wrap=tk.WORD, font=('Consolas', 10))
        details_scrollbar = ttk.Scrollbar(timeline_frame, orient=tk.VERTICAL, command=details_text.yview)
        details_text.configure(yscrollcommand=details_scrollbar.set)
        
        timeline_content = f"VEHICLE THREAT TIMELINE - ID: {vehicle_id}\n"
        timeline_content += "=" * 60 + "\n\n"
        
        if not vehicle_timeline:
            timeline_content += "No threat history found for this vehicle.\n"
        else:
            for i, entry in enumerate(vehicle_timeline, 1):
                timeline_content += f"DETECTION #{i}\n"
                timeline_content += f"Time: {entry['timestamp']}\n"
                timeline_content += f"Threat Level: {entry['threat_level']}\n"
                timeline_content += f"Fusion Score: {entry['fusion_score']:.3f}\n"
                timeline_content += f"Patterns: {', '.join(entry['detected_patterns'])}\n"
                timeline_content += f"Recommendations: {', '.join(entry['recommendations'])}\n"
                timeline_content += "-" * 40 + "\n\n"
        
        details_text.insert(tk.END, timeline_content)
        details_text.config(state=tk.DISABLED)
        
        details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Close button
        tk.Button(timeline_window, text="Close", command=timeline_window.destroy,
                 font=('Arial', 10, 'bold')).pack(pady=5)
    
    def generate_ids_report(self):
        """Generate comprehensive IDS report"""
        try:
            # Generate report data
            report_data = self.ids_system.generate_threat_report()
            
            # Create report window
            report_window = tk.Toplevel(self.root)
            report_window.title("IDS Threat Detection Report")
            report_window.geometry("800x700")
            
            # Report display
            report_frame = tk.Frame(report_window)
            report_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            report_text = tk.Text(report_frame, wrap=tk.WORD, font=('Consolas', 10))
            report_scrollbar = ttk.Scrollbar(report_frame, orient=tk.VERTICAL, command=report_text.yview)
            report_text.configure(yscrollcommand=report_scrollbar.set)
            
            # Format report content
            report_content = f"""
THEFT DETECTION SYSTEM - COMPREHENSIVE REPORT
Generated: {report_data['generated_at']}
Report Period: {report_data['report_period']}
{'='*80}

EXECUTIVE SUMMARY:
• Total Threat Detections: {report_data['total_threats']}
• High-Risk Detections: {report_data['high_risk_detections']}
• System Status: {report_data['system_performance']['system_status']}

THREAT LEVEL BREAKDOWN:
"""
            for level, count in report_data['threat_level_breakdown'].items():
                report_content += f"• {level}: {count}\n"
            
            report_content += f"""
MOST COMMON THREAT PATTERNS:
"""
            for pattern, count in report_data['most_common_patterns']:
                report_content += f"• {pattern.replace('_', ' ').title()}: {count} occurrences\n"
            
            report_content += f"""
HIGH-RISK VEHICLES:
"""
            for vehicle in report_data['high_risk_vehicles']:
                report_content += f"• Vehicle ID: {vehicle['vehicle_id']}, "
                report_content += f"License: {vehicle['license_plate']}, "
                report_content += f"Score: {vehicle['score']:.3f}\n"
            
            report_content += f"""
{'='*80}
SYSTEM PERFORMANCE METRICS:
• Active Threats: {report_data['system_performance']['active_threats']}
• Unique Vehicles Monitored: {report_data['system_performance']['unique_vehicles_monitored']}
• Average Threat Score: {report_data['system_performance']['average_threat_score']:.3f}
• 24h Detection Total: {report_data['system_performance']['total_detections_24h']}

RECOMMENDATIONS:
• Regular monitoring of high-risk vehicles
• Investigation of recurring threat patterns
• System performance optimization if needed
• Evidence preservation for legal proceedings
"""
            
            report_text.insert(tk.END, report_content)
            report_text.config(state=tk.DISABLED)
            
            report_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            report_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Control buttons
            button_frame = tk.Frame(report_window)
            button_frame.pack(fill=tk.X, pady=5)
            
            tk.Button(button_frame, text="Save Report", 
                     command=lambda: self.save_ids_report(report_content),
                     font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
            tk.Button(button_frame, text="Close", command=report_window.destroy,
                     font=('Arial', 10, 'bold')).pack(side=tk.RIGHT, padx=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {str(e)}")
    
    def show_ids_statistics(self):
        """Show detailed IDS statistics with charts"""
        try:
            stats_window = tk.Toplevel(self.root)
            stats_window.title("IDS Statistics Dashboard")
            stats_window.geometry("900x700")
            
            # Get statistics
            stats = self.ids_system.get_threat_statistics()
            
            # Create notebook for different stat views
            stats_notebook = ttk.Notebook(stats_window)
            stats_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Overview tab
            overview_frame = ttk.Frame(stats_notebook)
            stats_notebook.add(overview_frame, text="Overview")
            
            overview_text = tk.Text(overview_frame, wrap=tk.WORD, font=('Consolas', 12))
            overview_content = f"""
IDS SYSTEM STATISTICS DASHBOARD
{'='*50}

SYSTEM STATUS: {stats['system_status']}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

CURRENT METRICS:
• Active Threats: {stats['active_threats']}
• Unique Vehicles Monitored: {stats['unique_vehicles_monitored']}
• Average Threat Score: {stats['average_threat_score']:.3f}
• Total Detections (24h): {stats['total_detections_24h']}

THREAT DISTRIBUTION:
"""
            for level, count in stats['threat_distribution'].items():
                percentage = (count / max(stats['total_detections_24h'], 1)) * 100
                overview_content += f"• {level}: {count} ({percentage:.1f}%)\n"
            
            overview_text.insert(tk.END, overview_content)
            overview_text.config(state=tk.DISABLED)
            overview_text.pack(fill=tk.BOTH, expand=True)
            
            # Charts tab (if matplotlib is available)
            try:
                charts_frame = ttk.Frame(stats_notebook)
                stats_notebook.add(charts_frame, text="Charts")
                
                # Create threat level pie chart
                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
                
                # Pie chart of threat levels
                if stats['threat_distribution']:
                    levels = list(stats['threat_distribution'].keys())
                    counts = list(stats['threat_distribution'].values())
                    colors = ['red', 'orange', 'yellow', 'green'][:len(levels)]
                    
                    ax1.pie(counts, labels=levels, colors=colors, autopct='%1.1f%%')
                    ax1.set_title('Threat Level Distribution')
                
                # Bar chart of detection trends (simulated data)
                hours = list(range(24))
                detections = np.random.poisson(2, 24)  # Simulated hourly detections
                ax2.bar(hours, detections, color='skyblue')
                ax2.set_title('Hourly Detection Pattern')
                ax2.set_xlabel('Hour of Day')
                ax2.set_ylabel('Detections')
                
                canvas = FigureCanvasTkAgg(fig, charts_frame)
                canvas.draw()
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                
            except ImportError:
                # Matplotlib not available, show text-based charts
                charts_frame = ttk.Frame(stats_notebook)
                stats_notebook.add(charts_frame, text="Text Charts")
                
                chart_text = tk.Text(charts_frame, wrap=tk.WORD, font=('Consolas', 10))
                chart_content = "Graphical charts require matplotlib.\n\nText-based visualization:\n\n"
                
                for level, count in stats['threat_distribution'].items():
                    bar = '█' * min(count, 50)  # Simple text bar
                    chart_content += f"{level:10}: {bar} ({count})\n"
                
                chart_text.insert(tk.END, chart_content)
                chart_text.config(state=tk.DISABLED)
                chart_text.pack(fill=tk.BOTH, expand=True)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to show statistics: {str(e)}")
    
    def test_ids_system(self):
        """Test the IDS system with sample data"""
        try:
            self.log_message("Testing IDS system...")
            
            # Create test detection data
            test_detection = {
                'license_plate': {'text': 'TEST123', 'text_score': 0.9},
                'car': {'bbox': [100, 100, 300, 200]},
                'timestamp': datetime.now().timestamp(),
                'vehicle_type': 'car',
                'vehicle_color': 'red'
            }
            
            # Simulate stolen vehicle database alert
            test_database_alert = {
                'stolen_match_found': True,
                'confidence_score': 0.95,
                'status': 'STOLEN',
                'report_date': '2024-01-01'
            }
            
            # Run comprehensive threat analysis
            ids_result = self.ids_system.analyze_comprehensive_threat(
                'TEST_VEHICLE_001', test_detection, test_database_alert
            )
            
            # Show test results
            self.show_test_results(ids_result)
            
        except Exception as e:
            messagebox.showerror("Test Error", f"IDS test failed: {str(e)}")
    
    def show_test_results(self, ids_result):
        """Display IDS test results"""
        test_window = tk.Toplevel(self.root)
        test_window.title("IDS System Test Results")
        test_window.geometry("600x500")
        
        test_text = tk.Text(test_window, wrap=tk.WORD, font=('Consolas', 10))
        test_scrollbar = ttk.Scrollbar(test_window, orient=tk.VERTICAL, command=test_text.yview)
        test_text.configure(yscrollcommand=test_scrollbar.set)
        
        test_content = f"""
IDS SYSTEM TEST RESULTS
{'='*50}

OVERALL ASSESSMENT:
Vehicle ID: {ids_result['vehicle_id']}
License Plate: {ids_result['license_plate']}
Threat Level: {ids_result['threat_level']}
Fusion Score: {ids_result['fusion_score']:.3f}

COMPONENT ANALYSIS:
Database Match: {ids_result['component_scores']['database_match']:.2f}
Behavior Anomaly: {ids_result['component_scores']['behavior_anomaly']:.2f}
CAN Bus Simulation: {ids_result['component_scores']['can_simulation']:.2f}
ML Prediction: {ids_result['component_scores']['ml_prediction']:.2f}

DETECTED PATTERNS:
"""
        for pattern in ids_result['detected_patterns']:
            test_content += f"• {pattern.replace('_', ' ').title()}\n"
        
        test_content += f"""
RECOMMENDED ACTIONS:
"""
        for rec in ids_result['recommendations']:
            test_content += f"• {rec}\n"
        
        test_content += f"""
{'='*50}
TEST STATUS: {'PASSED' if ids_result['fusion_score'] > 0.5 else 'WARNING'}
System is functioning correctly and detecting threats appropriately.
"""
        
        test_text.insert(tk.END, test_content)
        test_text.config(state=tk.DISABLED)
        
        test_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        test_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        
        # Close button
        tk.Button(test_window, text="Close", command=test_window.destroy,
                 font=('Arial', 10, 'bold')).pack(pady=5)
    
    def update_ids_status(self):
        """Update IDS status display"""
        try:
            stats = self.ids_system.get_threat_statistics()
            
            # Update status labels
            if hasattr(self, 'ids_status_labels'):
                status_color = 'green' if stats['system_status'] == 'OPERATIONAL' else 'red'
                self.ids_status_labels['system_status'].config(
                    text=f"Status: {stats['system_status']}", fg=status_color
                )
                self.ids_status_labels['active_threats'].config(
                    text=f"Active Threats: {stats['active_threats']}"
                )
                self.ids_status_labels['total_detections'].config(
                    text=f"Total Detections: {stats['total_detections_24h']}"
                )
                self.ids_status_labels['avg_threat_score'].config(
                    text=f"Avg Threat Score: {stats['average_threat_score']:.3f}"
                )
                self.ids_status_labels['last_analysis'].config(
                    text=f"Last Analysis: {datetime.now().strftime('%H:%M:%S')}"
                )
            
            # Schedule next update
            self.root.after(5000, self.update_ids_status)  # Update every 5 seconds
            
        except Exception as e:
            pass  # Silently handle update errors
    
    def on_ids_threat_double_click(self, event):
        """Handle double-click on IDS threat tree item"""
        selection = self.ids_threats_tree.selection()
        if not selection:
            return
        
        item = self.ids_threats_tree.item(selection[0])
        values = item['values']
        
        if len(values) >= 7:
            vehicle_id = values[1]
            plate = values[2]
            threat_level = values[3]
            score = values[4]
            
            # Show detailed threat information
            detail_msg = f"Vehicle ID: {vehicle_id}\n"
            detail_msg += f"License Plate: {plate}\n"
            detail_msg += f"Threat Level: {threat_level}\n"
            detail_msg += f"Fusion Score: {score}\n"
            detail_msg += f"Time: {values[0]}\n"
            detail_msg += f"Patterns: {values[5]}\n"
            detail_msg += f"Actions: {values[6]}"
            
            messagebox.showinfo("Threat Details", detail_msg)
    
    def save_ids_report(self, report_content):
        """Save IDS report to file"""
        try:
            from tkinter import filedialog
            
            filename = filedialog.asksaveasfilename(
                title="Save IDS Report",
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            
            if filename:
                with open(filename, 'w') as f:
                    f.write(report_content)
                messagebox.showinfo("Success", f"Report saved to: {filename}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save report: {str(e)}")
    
    def export_timeline(self):
        """Export threat timeline data"""
        try:
            from tkinter import filedialog
            import csv
            
            filename = filedialog.asksaveasfilename(
                title="Export Timeline",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            
            if filename:
                # Collect timeline data
                timeline_data = []
                for vehicle_id, history in self.ids_system.detection_history.items():
                    for detection in history:
                        timeline_data.append({
                            'timestamp': datetime.fromtimestamp(detection.get('timestamp', 0)).isoformat(),
                            'vehicle_id': vehicle_id,
                            'threat_level': detection.get('threat_level', 'LOW'),
                            'fusion_score': detection.get('fusion_score', 0),
                            'patterns': '; '.join(detection.get('patterns', []))
                        })
                
                # Write to CSV
                with open(filename, 'w', newline='') as csvfile:
                    if timeline_data:
                        fieldnames = timeline_data[0].keys()
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(timeline_data)
                
                messagebox.showinfo("Success", f"Timeline exported to: {filename}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export timeline: {str(e)}")
    
    def refresh_timeline(self, timeline_tree):
        """Refresh the timeline display"""
        try:
            # Clear existing items
            timeline_tree.delete(*timeline_tree.get_children())
            
            # Reload recent threats
            recent_threats = []
            for vehicle_id, history in self.ids_system.detection_history.items():
                for detection in history[-10:]:
                    recent_threats.append({
                        'vehicle_id': vehicle_id,
                        'timestamp': detection.get('timestamp', 0),
                        'threat_level': detection.get('threat_level', 'LOW'),
                        'fusion_score': detection.get('fusion_score', 0),
                        'patterns': detection.get('patterns', [])
                    })
            
            # Sort and repopulate
            recent_threats.sort(key=lambda x: x['timestamp'], reverse=True)
            
            for threat in recent_threats[:50]:
                time_str = datetime.fromtimestamp(threat['timestamp']).strftime("%H:%M:%S")
                patterns_str = ', '.join(threat['patterns'][:2])
                if len(threat['patterns']) > 2:
                    patterns_str += "..."
                
                timeline_tree.insert('', 'end', values=(
                    time_str,
                    threat['vehicle_id'],
                    threat['threat_level'],
                    f"{threat['fusion_score']:.2f}",
                    patterns_str
                ))
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh timeline: {str(e)}")
    
    # Bind all methods to the app instance
    import types
    
    app_instance.handle_ids_threat = types.MethodType(handle_ids_threat, app_instance)
    app_instance.show_critical_threat_popup = types.MethodType(show_critical_threat_popup, app_instance)
    app_instance.show_threat_timeline = types.MethodType(show_threat_timeline, app_instance)
    app_instance.show_vehicle_threat_timeline = types.MethodType(show_vehicle_threat_timeline, app_instance)
    app_instance.generate_ids_report = types.MethodType(generate_ids_report, app_instance)
    app_instance.show_ids_statistics = types.MethodType(show_ids_statistics, app_instance)
    app_instance.test_ids_system = types.MethodType(test_ids_system, app_instance)
    app_instance.show_test_results = types.MethodType(show_test_results, app_instance)
    app_instance.update_ids_status = types.MethodType(update_ids_status, app_instance)
    app_instance.on_ids_threat_double_click = types.MethodType(on_ids_threat_double_click, app_instance)
    app_instance.save_ids_report = types.MethodType(save_ids_report, app_instance)
    app_instance.export_timeline = types.MethodType(export_timeline, app_instance)
    app_instance.refresh_timeline = types.MethodType(refresh_timeline, app_instance)


# Alternative integration approach using class inheritance
class IDSIntegratedApp:
    """Mixin class to add IDS functionality to existing LPR system"""
    
    def __init__(self):
        # Initialize IDS system
        self.ids_system = IntegratedTheftDetectionSystem()
        self.ids_active = True
        
        # Add IDS to existing tabs if notebook exists
        if hasattr(self, 'notebook'):
            self.setup_ids_tab()
        
        # Start IDS monitoring
        self.start_ids_monitoring()
    
    def setup_ids_tab(self):
        """Setup the IDS tab in existing notebook"""
        add_ids_gui(self)
        add_ids_methods(self)
    
    def start_ids_monitoring(self):
        """Start background IDS monitoring"""
        def ids_monitor():
            while self.ids_active:
                try:
                    # Perform periodic IDS tasks
                    self.cleanup_old_threats()
                    time.sleep(30)  # Check every 30 seconds
                except Exception as e:
                    print(f"IDS monitoring error: {e}")
                    time.sleep(60)  # Wait longer on error
        
        ids_thread = threading.Thread(target=ids_monitor, daemon=True)
        ids_thread.start()
    
    def cleanup_old_threats(self):
        """Clean up old threat data to prevent memory issues"""
        try:
            cutoff_time = datetime.now().timestamp() - (24 * 3600)  # 24 hours ago
            
            # Clean up detection history
            for vehicle_id in list(self.ids_system.detection_history.keys()):
                history = self.ids_system.detection_history[vehicle_id]
                # Keep only recent detections
                self.ids_system.detection_history[vehicle_id] = [
                    h for h in history if h.get('timestamp', 0) > cutoff_time
                ]
                
                # Remove empty histories
                if not self.ids_system.detection_history[vehicle_id]:
                    del self.ids_system.detection_history[vehicle_id]
            
            # Clean up active threats that are resolved
            for vehicle_id in list(self.ids_system.active_threats.keys()):
                threat = self.ids_system.active_threats[vehicle_id]
                if threat.get('timestamp', 0) < cutoff_time - 3600:  # 1 hour grace period
                    del self.ids_system.active_threats[vehicle_id]
                    
        except Exception as e:
            print(f"Cleanup error: {e}")


# Main integration function
def integrate_ids_system_complete(app_class):
    """
    Complete integration of IDS system with existing License Plate Recognition app
    
    Usage:
    from ids_integration import integrate_ids_system_complete
    
    # Apply to your existing app class
    @integrate_ids_system_complete
    class YourLPRApp:
        # ... existing code ...
    
    # Or apply to instance
    app = YourExistingApp()
    integrate_ids_system_complete(app)
    """
    
    if isinstance(app_class, type):
        # Class decorator
        original_init = app_class.__init__
        
        def new_init(self, *args, **kwargs):
            # Call original initialization
            original_init(self, *args, **kwargs)
            
            # Add IDS features
            add_ids_features(self)
            
            self.log_message("IDS Integration: Advanced Theft Detection System activated")
            self.log_message("IDS Features: Multi-modal threat analysis, behavioral monitoring, CAN simulation")
            
        app_class.__init__ = new_init
        return app_class
    else:
        # Instance integration
        add_ids_features(app_class)
        return app_class


# Standalone IDS launcher for testing
def launch_ids_test():
    """Launch standalone IDS test interface"""
    import tkinter as tk
    from tkinter import ttk
    
    root = tk.Tk()
    root.title("IDS System Test Interface")
    root.geometry("800x600")
    
    # Create mock app instance for testing
    class MockApp:
        def __init__(self):
            self.root = root
            self.notebook = ttk.Notebook(root)
            self.notebook.pack(fill=tk.BOTH, expand=True)
            
            # Mock processed data
            self.processed_data = []
            self.results = {}
            
        def log_message(self, message):
            print(f"[IDS] {message}")
    
    # Create mock app and integrate IDS
    mock_app = MockApp()
    add_ids_features(mock_app)
    
    root.mainloop()


if __name__ == "__main__":
    print("IDS Integration Module")
    print("=" * 50)
    print("Advanced Theft Detection System Integration")
    print("Features:")
    print("  • Multi-modal threat fusion")
    print("  • Behavioral pattern analysis") 
    print("  • CAN bus anomaly simulation")
    print("  • Machine learning predictions")
    print("  • Real-time threat monitoring")
    print("  • Comprehensive reporting")
    print("=" * 50)
    
    # Launch test interface
    response = input("Launch IDS test interface? (y/n): ")
    if response.lower().startswith('y'):
        launch_ids_test()
    else:
        print("Integration module ready for import.")
        print("Usage: from ids_integration import add_ids_features")