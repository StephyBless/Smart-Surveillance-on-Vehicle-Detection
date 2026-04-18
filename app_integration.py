"""
Integration file to add Criminal Intelligence features to the main License Plate Recognition app
This file modifies your existing app.py without changing the core file structure
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from datetime import datetime
import json
import os

# Import the criminal intelligence module
from criminal_intelligence import (
    CriminalIntelligenceSystem, 
    integrate_criminal_intelligence
)


def add_intelligence_features(app_instance):
    """Add criminal intelligence features to existing app instance"""
    
    # Initialize the criminal intelligence system
    app_instance.criminal_intelligence = CriminalIntelligenceSystem()
    
    # Add intelligence-specific GUI elements
    add_intelligence_gui(app_instance)
    
    # Modify existing methods to include intelligence analysis
    enhance_processing_methods(app_instance)
    
    # Add new methods for intelligence features
    add_intelligence_methods(app_instance)


def add_intelligence_gui(app_instance):
    """Add criminal intelligence GUI elements to existing interface"""
    
    # Create new intelligence tab
    intelligence_frame = ttk.Frame(app_instance.notebook)
    app_instance.notebook.add(intelligence_frame, text="Intelligence Analysis")
    
    # Top section - Real-time alerts
    alerts_frame = ttk.LabelFrame(intelligence_frame, text="Real-time Intelligence Alerts", padding=10)
    alerts_frame.pack(fill=tk.X, padx=5, pady=5)
    
    # Alert display with color coding
    app_instance.alerts_text = tk.Text(alerts_frame, height=8, wrap=tk.WORD, font=('Consolas', 9))
    alerts_scrollbar = ttk.Scrollbar(alerts_frame, orient=tk.VERTICAL, command=app_instance.alerts_text.yview)
    app_instance.alerts_text.configure(yscrollcommand=alerts_scrollbar.set)
    
    app_instance.alerts_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    alerts_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    # Configure text tags for different alert levels
    app_instance.alerts_text.tag_configure('normal', foreground='green')
    app_instance.alerts_text.tag_configure('medium', foreground='orange', font=('Consolas', 9, 'bold'))
    app_instance.alerts_text.tag_configure('high', foreground='red', font=('Consolas', 9, 'bold'))
    
    # Middle section - Intelligence controls
    controls_frame = ttk.LabelFrame(intelligence_frame, text="Intelligence Controls", padding=10)
    controls_frame.pack(fill=tk.X, padx=5, pady=5)
    
    control_buttons_frame = ttk.Frame(controls_frame)
    control_buttons_frame.pack(fill=tk.X)
    
    ttk.Button(control_buttons_frame, text="View Threat Summary", 
              command=lambda: app_instance.show_threat_summary()).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_buttons_frame, text="Export Intelligence Report", 
              command=lambda: app_instance.export_intelligence_report()).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_buttons_frame, text="Manage Registration Database", 
              command=lambda: app_instance.open_registration_manager()).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_buttons_frame, text="Clear Alerts", 
              command=lambda: app_instance.clear_intelligence_alerts()).pack(side=tk.LEFT, padx=5)
    
    # Statistics section
    stats_frame = ttk.LabelFrame(intelligence_frame, text="Intelligence Statistics", padding=10)
    stats_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    # Create statistics display
    app_instance.intelligence_stats = {
        'total_analyses': tk.Label(stats_frame, text="Total Analyses: 0", font=('Arial', 10)),
        'high_threats': tk.Label(stats_frame, text="High Threats: 0", font=('Arial', 10), fg='red'),
        'medium_threats': tk.Label(stats_frame, text="Medium Threats: 0", font=('Arial', 10), fg='orange'),
        'cloning_alerts': tk.Label(stats_frame, text="Cloning Alerts: 0", font=('Arial', 10)),
        'mismatch_alerts': tk.Label(stats_frame, text="Mismatch Alerts: 0", font=('Arial', 10)),
        'suspicious_plates': tk.Label(stats_frame, text="Suspicious Plates: 0", font=('Arial', 10))
    }
    
    for i, (key, label) in enumerate(app_instance.intelligence_stats.items()):
        row = i // 2
        col = i % 2
        label.grid(row=row, column=col, sticky=tk.W, padx=10, pady=5)


def enhance_processing_methods(app_instance):
    """Enhance existing processing methods with intelligence analysis"""
    
    # Store original method
    original_process_frame = app_instance.process_frame_enhanced
    
    def enhanced_process_frame_with_intelligence(frame, frame_nmr):
        # Call original processing
        original_process_frame(frame, frame_nmr)
        
        # Add criminal intelligence analysis
        if frame_nmr in app_instance.results:
            for car_id, detection_data in app_instance.results[frame_nmr].items():
                if 'license_plate' in detection_data and detection_data['license_plate']['text']:
                    plate_text = detection_data['license_plate']['text']
                    confidence = detection_data['license_plate']['text_score']
                    
                    # Prepare vehicle data for analysis
                    vehicle_data = {
                        'vehicle_type': detection_data.get('vehicle_type', 'unknown'),
                        'vehicle_color': detection_data.get('vehicle_color', 'unknown'),
                        'car_bbox': detection_data['car']['bbox'],
                        'timestamp': detection_data.get('timestamp', 0)
                    }
                    
                    # Perform intelligence analysis
                    intelligence_result = app_instance.criminal_intelligence.analyze_detection(
                        plate_text, vehicle_data, confidence, detection_data.get('timestamp')
                    )
                    
                    # Add intelligence results to detection data
                    detection_data['intelligence_analysis'] = intelligence_result
                    
                    # Display real-time alerts in GUI
                    app_instance.display_intelligence_alert(intelligence_result, plate_text)
                    
                    # Update statistics
                    app_instance.update_intelligence_statistics()
    
    # Replace the method
    app_instance.process_frame_enhanced = enhanced_process_frame_with_intelligence


def add_intelligence_methods(app_instance):
    """Add new methods for criminal intelligence features"""
    
    def display_intelligence_alert(self, intelligence_result, plate_text):
        """Display intelligence alerts in real-time"""
        if not hasattr(self, 'alerts_text'):
            return
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        threat_level = intelligence_result['overall_threat_level']
        
        # Schedule GUI update on main thread
        def update_alerts():
            if intelligence_result['alerts']:
                alert_text = f"[{timestamp}] {plate_text} - {threat_level.upper()} THREAT\n"
                for alert in intelligence_result['alerts']:
                    alert_text += f"  → {alert['message']}\n"
                alert_text += "\n"
                
                self.alerts_text.insert(tk.END, alert_text, threat_level)
                self.alerts_text.see(tk.END)
                
                # Keep alerts text manageable
                if len(self.alerts_text.get("1.0", tk.END).split('\n')) > 100:
                    self.alerts_text.delete("1.0", "20.0")
        
        self.root.after(0, update_alerts)
    
    def update_intelligence_statistics(self):
        """Update intelligence statistics display"""
        if not hasattr(self, 'intelligence_stats'):
            return
            
        def update_stats():
            try:
                threat_summary = self.criminal_intelligence.get_threat_summary()
                
                # Update labels
                self.intelligence_stats['total_analyses'].config(
                    text=f"Total Analyses: {len(self.criminal_intelligence.alert_log)}")
                self.intelligence_stats['high_threats'].config(
                    text=f"High Threats: {threat_summary['threat_level_distribution'].get('high', 0)}")
                self.intelligence_stats['medium_threats'].config(
                    text=f"Medium Threats: {threat_summary['threat_level_distribution'].get('medium', 0)}")
                self.intelligence_stats['cloning_alerts'].config(
                    text=f"Cloning Alerts: {threat_summary['alert_type_distribution'].get('potential_cloning', 0)}")
                self.intelligence_stats['mismatch_alerts'].config(
                    text=f"Mismatch Alerts: {threat_summary['alert_type_distribution'].get('vehicle_mismatch', 0)}")
                self.intelligence_stats['suspicious_plates'].config(
                    text=f"Suspicious Plates: {threat_summary['alert_type_distribution'].get('suspicious_plate', 0)}")
                
                # Debug: Print to console to verify data
                if len(self.criminal_intelligence.alert_log) > 0:
                    print(f"DEBUG - Stats Update: Total={len(self.criminal_intelligence.alert_log)}, "
                          f"High={threat_summary['threat_level_distribution'].get('high', 0)}, "
                          f"Recent={threat_summary['total_detections_recent']}")
                    
            except Exception as e:
                print(f"Error updating stats: {e}")  # Debug print
        
        self.root.after(0, update_stats)
    
    def show_threat_summary(self):
        """Show detailed threat summary window"""
        threat_summary = self.criminal_intelligence.get_threat_summary()
        
        # Create summary window
        summary_window = tk.Toplevel(self.root)
        summary_window.title("Criminal Intelligence Threat Summary")
        summary_window.geometry("600x500")
        summary_window.configure(bg='#2c3e50')
        
        # Title
        title_label = tk.Label(summary_window, 
                              text="CRIMINAL INTELLIGENCE THREAT SUMMARY", 
                              font=('Arial', 14, 'bold'), 
                              bg='#2c3e50', fg='white')
        title_label.pack(pady=10)
        
        # Summary text
        summary_text = tk.Text(summary_window, wrap=tk.WORD, font=('Consolas', 10), 
                              height=25, bg='white')
        summary_scrollbar = ttk.Scrollbar(summary_window, orient=tk.VERTICAL, 
                                         command=summary_text.yview)
        summary_text.configure(yscrollcommand=summary_scrollbar.set)
        
        # Generate summary content
        content = f"""THREAT ANALYSIS REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*50}

RECENT ACTIVITY:
• Total Recent Detections: {threat_summary['total_detections_recent']}
• Total Detections (Last Hour): {threat_summary['total_detections_last_hour']}
• High Priority Threats: {threat_summary['threat_level_distribution'].get('high', 0)}
• Medium Priority Threats: {threat_summary['threat_level_distribution'].get('medium', 0)}
• Normal Detections: {threat_summary['threat_level_distribution'].get('normal', 0)}

ALERT TYPE BREAKDOWN:
"""
        for alert_type, count in threat_summary['alert_type_distribution'].items():
            content += f"• {alert_type.replace('_', ' ').title()}: {count}\n"
        
        content += f"\n{'='*50}\nHIGH PRIORITY ALERTS:\n"
        
        if not threat_summary['high_priority_alerts']:
            content += "No high priority alerts in recent activity.\n"
        else:
            for alert_data in threat_summary['high_priority_alerts']:
                content += f"\nPlate: {alert_data['plate_number']}\n"
                content += f"Time: {datetime.fromtimestamp(alert_data['timestamp']).strftime('%H:%M:%S')}\n"
                for alert in alert_data['alerts']:
                    content += f"• {alert['message']}\n"
                content += "-" * 30 + "\n"
        
        # Add debug information
        content += f"\n{'='*50}\nDEBUG INFO:\n"
        content += f"Total alerts in system: {len(self.criminal_intelligence.alert_log)}\n"
        if self.criminal_intelligence.alert_log:
            latest_alert = self.criminal_intelligence.alert_log[-1]
            content += f"Latest alert time: {datetime.fromtimestamp(latest_alert['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}\n"
            content += f"Latest alert plate: {latest_alert['plate_number']}\n"
            content += f"Latest threat level: {latest_alert['overall_threat_level']}\n"
        
        summary_text.insert('1.0', content)
        summary_text.config(state='disabled')
        
        summary_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        summary_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)
        
        # Close button
        ttk.Button(summary_window, text="Close", 
                  command=summary_window.destroy).pack(pady=10)
    
    def export_intelligence_report(self):
        """Export detailed intelligence report in CSV format"""
        try:
            output_dir = self.output_dir_var.get()
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create two CSV files: detailed report and summary
            detail_filepath = os.path.join(output_dir, f'intelligence_report_{timestamp}.csv')
            summary_filepath = os.path.join(output_dir, f'intelligence_summary_{timestamp}.csv')
            
            # Export both files
            self.criminal_intelligence.export_intelligence_report(detail_filepath)
            
            # Show success message with file paths
            msg = f"Intelligence report exported successfully!\n\n"
            msg += f"Detailed Report: {detail_filepath}\n"
            msg += f"Summary Report: {summary_filepath}\n\n"
            msg += "You can now open these files in Excel, Google Sheets, or any spreadsheet application."
            
            messagebox.showinfo("Export Successful", msg)
            self.log_message(f"Intelligence reports exported: {detail_filepath} and {summary_filepath}")
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export report: {str(e)}")
            self.log_message(f"Intelligence report export failed: {str(e)}")
    
    def open_registration_manager(self):
        """Open vehicle registration database manager"""
        reg_window = tk.Toplevel(self.root)
        reg_window.title("Vehicle Registration Database Manager")
        reg_window.geometry("700x500")
        reg_window.configure(bg='#2c3e50')
        
        # Title
        title_label = tk.Label(reg_window, 
                              text="VEHICLE REGISTRATION DATABASE", 
                              font=('Arial', 14, 'bold'), 
                              bg='#2c3e50', fg='white')
        title_label.pack(pady=10)
        
        # Current registrations display
        reg_frame = ttk.LabelFrame(reg_window, text="Current Registrations", padding=10)
        reg_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Treeview for registrations
        columns = ('Plate', 'Type', 'Color', 'Make', 'Model')
        reg_tree = ttk.Treeview(reg_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            reg_tree.heading(col, text=col)
            reg_tree.column(col, width=120, anchor=tk.CENTER)
        
        # Populate with current data
        for plate, info in self.criminal_intelligence.registration_db.registrations.items():
            reg_tree.insert('', 'end', values=(
                plate, 
                info.get('type', ''), 
                info.get('color', ''), 
                info.get('make', ''), 
                info.get('model', '')
            ))
        
        reg_scrollbar = ttk.Scrollbar(reg_frame, orient=tk.VERTICAL, command=reg_tree.yview)
        reg_tree.configure(yscrollcommand=reg_scrollbar.set)
        
        reg_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        reg_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add new registration section
        add_frame = ttk.LabelFrame(reg_window, text="Add New Registration", padding=10)
        add_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Entry fields
        fields = ['Plate Number', 'Vehicle Type', 'Color', 'Make', 'Model']
        entries = {}
        
        for i, field in enumerate(fields):
            row = i // 2
            col = (i % 2) * 2
            
            ttk.Label(add_frame, text=f"{field}:").grid(row=row, column=col, 
                                                       sticky=tk.W, padx=5, pady=2)
            entries[field.lower().replace(' ', '_')] = ttk.Entry(add_frame, width=20)
            entries[field.lower().replace(' ', '_')].grid(row=row, column=col+1, 
                                                         padx=5, pady=2, sticky=tk.W)
        
        def add_registration():
            try:
                plate = entries['plate_number'].get().strip().upper()
                if not plate:
                    messagebox.showwarning("Invalid Input", "Please enter a plate number")
                    return
                
                vehicle_info = {
                    'type': entries['vehicle_type'].get().strip().lower(),
                    'color': entries['color'].get().strip().lower(),
                    'make': entries['make'].get().strip(),
                    'model': entries['model'].get().strip()
                }
                
                self.criminal_intelligence.registration_db.add_registration(plate, vehicle_info)
                
                # Refresh the treeview
                reg_tree.delete(*reg_tree.get_children())
                for plate_num, info in self.criminal_intelligence.registration_db.registrations.items():
                    reg_tree.insert('', 'end', values=(
                        plate_num, 
                        info.get('type', ''), 
                        info.get('color', ''), 
                        info.get('make', ''), 
                        info.get('model', '')
                    ))
                
                # Clear entries
                for entry in entries.values():
                    entry.delete(0, tk.END)
                
                messagebox.showinfo("Success", f"Registration added for {plate}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add registration: {str(e)}")
        
        ttk.Button(add_frame, text="Add Registration", 
                  command=add_registration).grid(row=2, column=1, pady=10)
        
        # Close button
        ttk.Button(reg_window, text="Close", 
                  command=reg_window.destroy).pack(pady=10)
    
    def clear_intelligence_alerts(self):
        """Clear the intelligence alerts display"""
        if hasattr(self, 'alerts_text'):
            self.alerts_text.delete('1.0', tk.END)
            self.log_message("Intelligence alerts cleared")
    
    # Add methods to the app instance
    import types
    app_instance.display_intelligence_alert = types.MethodType(display_intelligence_alert, app_instance)
    app_instance.update_intelligence_statistics = types.MethodType(update_intelligence_statistics, app_instance)
    app_instance.show_threat_summary = types.MethodType(show_threat_summary, app_instance)
    app_instance.export_intelligence_report = types.MethodType(export_intelligence_report, app_instance)
    app_instance.open_registration_manager = types.MethodType(open_registration_manager, app_instance)
    app_instance.clear_intelligence_alerts = types.MethodType(clear_intelligence_alerts, app_instance)


def modify_existing_search_results(app_instance):
    """Modify existing search results to include intelligence information"""
    
    original_on_result_double_click = app_instance.on_result_double_click
    
    def enhanced_result_double_click(event):
        """Enhanced double-click handler with intelligence information"""
        selection = app_instance.results_tree.selection()
        if not selection:
            return
        
        item = app_instance.results_tree.item(selection[0])
        values = item['values']
        
        if len(values) >= 9:
            plate = values[0].split(' (')[0]  # Remove similarity info if present
            
            # Get intelligence analysis for this plate
            intelligence_info = ""
            for analysis in app_instance.criminal_intelligence.alert_log:
                if analysis['plate_number'] == plate:
                    intelligence_info += f"\n--- INTELLIGENCE ANALYSIS ---\n"
                    intelligence_info += f"Threat Level: {analysis['overall_threat_level'].upper()}\n"
                    
                    if analysis['alerts']:
                        intelligence_info += "Alerts:\n"
                        for alert in analysis['alerts']:
                            intelligence_info += f"  • {alert['message']}\n"
                    
                    if analysis['mismatch_analysis']['has_mismatch']:
                        intelligence_info += f"Registration Mismatch: YES (Score: {analysis['mismatch_analysis']['mismatch_score']:.2f})\n"
                    
                    if analysis['cloning_analysis']['is_potential_clone']:
                        intelligence_info += f"Potential Cloning: YES (Confidence: {analysis['cloning_analysis']['confidence']:.2f})\n"
                    
                    break
            
            # Create enhanced detail message
            detail_msg = f"License Plate: {plate}\n"
            detail_msg += f"Car ID: {values[2]}\n"
            detail_msg += f"Vehicle Type: {values[6].title()}\n"
            detail_msg += f"Vehicle Color: {values[7].title()}\n"
            detail_msg += f"First Detection: {values[3]}\n"
            detail_msg += f"Last Detection: {values[4]}\n"
            detail_msg += f"Duration in Video: {values[5]}\n"
            detail_msg += f"Total Detections: {values[1]}\n"
            detail_msg += f"Average Confidence: {values[8]}"
            detail_msg += intelligence_info
            
            messagebox.showinfo("Enhanced Plate Details with Intelligence", detail_msg)
    
    app_instance.on_result_double_click = enhanced_result_double_click


# Main integration function
def integrate_criminal_intelligence_features(app_instance):
    """Main function to integrate all criminal intelligence features"""
    try:
        # Add core intelligence features
        add_intelligence_features(app_instance)
        
        # Modify existing functionality
        modify_existing_search_results(app_instance)
        
        # Log successful integration
        app_instance.log_message("Criminal Intelligence features integrated successfully")
        app_instance.log_message("New features: License plate cloning detection, fake plate detection, vehicle mismatch analysis")
        
        return True
        
    except Exception as e:
        print(f"Error integrating criminal intelligence features: {e}")
        return False


if __name__ == "__main__":
    print("Criminal Intelligence Integration Module")
    print("This module adds advanced criminal intelligence features to your License Plate Recognition system")
    print("Features added:")
    print("  • License Plate Cloning Detection")
    print("  • Fake/Modified Plate Detection") 
    print("  • Vehicle-Registration Mismatch Analysis")
    print("  • Real-time Intelligence Alerts")
    print("  • Threat Level Assessment")
    print("  • Registration Database Management")