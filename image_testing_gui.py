"""
UPDATED: image_testing_gui.py with FIXED SCROLLING
Replace your current image_testing_gui.py with this version
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
import os
from datetime import datetime
import threading


class ImageTestingTab:
    """Image testing tab for the LPR system - FIXED VERSION"""
    
    def __init__(self, parent_notebook, image_tester, log_callback):
        self.notebook = parent_notebook
        self.image_tester = image_tester
        self.log_message = log_callback
        
        # Create tab
        self.tab = ttk.Frame(parent_notebook)
        parent_notebook.add(self.tab, text="🖼️ Image Testing")
        
        # State variables
        self.current_images = []
        self.current_results = None
        self.selected_conditions = []
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the UI for image testing tab with proper scrolling"""
        # Create main canvas with scrollbar
        main_canvas = tk.Canvas(self.tab, bg='white', highlightthickness=0)
        main_scrollbar = ttk.Scrollbar(self.tab, orient=tk.VERTICAL, command=main_canvas.yview)
        
        # Scrollable frame
        scrollable_frame = tk.Frame(main_canvas, bg='white')
        
        # Configure canvas
        scrollable_frame.bind(
            '<Configure>',
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox('all'))
        )
        
        canvas_frame = main_canvas.create_window((0, 0), window=scrollable_frame, anchor=tk.NW)
        main_canvas.configure(yscrollcommand=main_scrollbar.set)
        
        # Pack scrollbar and canvas
        main_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Adjust canvas width when window resizes
        def configure_canvas_width(event):
            canvas_width = event.width
            main_canvas.itemconfig(canvas_frame, width=canvas_width)
        
        main_canvas.bind('<Configure>', configure_canvas_width)
        
        # Mouse wheel scrolling
        def on_mousewheel(event):
            main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def bind_mousewheel(event):
            main_canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        def unbind_mousewheel(event):
            main_canvas.unbind_all("<MouseWheel>")
        
        main_canvas.bind('<Enter>', bind_mousewheel)
        main_canvas.bind('<Leave>', unbind_mousewheel)
        
        # Now build content in scrollable_frame
        # Title
        title_frame = tk.Frame(scrollable_frame, bg='#3498db', height=60)
        title_frame.pack(fill=tk.X, pady=(10, 10), padx=10)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(title_frame, 
                              text="📸 Image-Based License Plate Testing Module",
                              font=('Arial', 14, 'bold'), 
                              bg='#3498db', 
                              fg='white')
        title_label.pack(expand=True)
        
        subtitle_label = tk.Label(title_frame,
                                 text="Test your Enhanced LPR Processor under various simulated conditions",
                                 font=('Arial', 9),
                                 bg='#3498db',
                                 fg='white')
        subtitle_label.pack()
        
        # Create sections
        self.create_upload_section(scrollable_frame)
        self.create_conditions_section(scrollable_frame)
        self.create_results_section(scrollable_frame)
        self.create_control_buttons(scrollable_frame)
        
        # Add some padding at bottom
        tk.Frame(scrollable_frame, height=20, bg='white').pack()
    
    def create_upload_section(self, parent):
        """Create image upload section"""
        upload_frame = ttk.LabelFrame(parent, text="📁 Image Upload", padding=10)
        upload_frame.pack(fill=tk.X, pady=(0, 10), padx=10)
        
        # Buttons frame
        buttons_frame = tk.Frame(upload_frame, bg='white')
        buttons_frame.pack(fill=tk.X)
        
        # Single image upload
        btn_single = tk.Button(buttons_frame, 
                              text="📷 Upload Single Image",
                              command=self.upload_single_image,
                              bg='#3498db',
                              fg='white',
                              font=('Arial', 10, 'bold'),
                              padx=20,
                              pady=10,
                              cursor='hand2')
        btn_single.pack(side=tk.LEFT, padx=5)
        
        # Batch upload
        btn_batch = tk.Button(buttons_frame,
                             text="📁 Upload Multiple Images",
                             command=self.upload_batch_images,
                             bg='#2ecc71',
                             fg='white',
                             font=('Arial', 10, 'bold'),
                             padx=20,
                             pady=10,
                             cursor='hand2')
        btn_batch.pack(side=tk.LEFT, padx=5)
        
        # Clear button
        btn_clear = tk.Button(buttons_frame,
                             text="🗑️ Clear All",
                             command=self.clear_images,
                             bg='#e74c3c',
                             fg='white',
                             font=('Arial', 10, 'bold'),
                             padx=20,
                             pady=10,
                             cursor='hand2')
        btn_clear.pack(side=tk.LEFT, padx=5)
        
        # Status label
        self.upload_status = tk.Label(upload_frame,
                                     text="No images loaded",
                                     font=('Arial', 9),
                                     bg='white',
                                     fg='#7f8c8d')
        self.upload_status.pack(pady=5)
        
        # Image preview area (scrollable)
        preview_frame = ttk.LabelFrame(upload_frame, text="Preview", padding=5)
        preview_frame.pack(fill=tk.X, pady=5)
        
        # Canvas for scrolling
        canvas_frame = tk.Frame(preview_frame)
        canvas_frame.pack(fill=tk.X)
        
        self.preview_canvas = tk.Canvas(canvas_frame, bg='#ecf0f1', height=150)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, 
                                 command=self.preview_canvas.xview)
        
        self.preview_canvas.configure(xscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.preview_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        self.preview_frame_inner = tk.Frame(self.preview_canvas, bg='#ecf0f1')
        self.preview_canvas.create_window((0, 0), window=self.preview_frame_inner, 
                                         anchor=tk.NW)
    
    def create_conditions_section(self, parent):
        """Create conditions selection section"""
        conditions_frame = ttk.LabelFrame(parent, text="🌤️ Simulation Conditions", padding=10)
        conditions_frame.pack(fill=tk.X, pady=(0, 10), padx=10)
        
        # Instructions
        info_label = tk.Label(conditions_frame,
                             text="Select conditions to simulate for testing (Original image is always tested)",
                             font=('Arial', 9, 'italic'),
                             bg='white',
                             fg='#7f8c8d')
        info_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Checkboxes grid
        checkbox_frame = tk.Frame(conditions_frame, bg='white')
        checkbox_frame.pack(fill=tk.X)
        
        conditions = self.image_tester.simulator.get_available_conditions()
        self.condition_vars = {}
        
        # Create checkboxes in rows of 4
        row_frame = None
        for idx, condition in enumerate(conditions):
            if idx % 4 == 0:
                row_frame = tk.Frame(checkbox_frame, bg='white')
                row_frame.pack(fill=tk.X, pady=2)
            
            var = tk.BooleanVar(value=False)
            self.condition_vars[condition] = var
            
            # Format condition name
            display_name = condition.replace('_', ' ').title()
            
            cb = tk.Checkbutton(row_frame,
                               text=display_name,
                               variable=var,
                               font=('Arial', 9),
                               bg='white',
                               activebackground='white',
                               selectcolor='#3498db')
            cb.pack(side=tk.LEFT, padx=10, pady=2)
        
        # Quick select buttons
        quick_frame = tk.Frame(conditions_frame, bg='white')
        quick_frame.pack(fill=tk.X, pady=(10, 0))
        
        tk.Button(quick_frame,
                 text="Select All",
                 command=self.select_all_conditions,
                 bg='#95a5a6',
                 fg='white',
                 font=('Arial', 8),
                 padx=10,
                 pady=5).pack(side=tk.LEFT, padx=5)
        
        tk.Button(quick_frame,
                 text="Deselect All",
                 command=self.deselect_all_conditions,
                 bg='#95a5a6',
                 fg='white',
                 font=('Arial', 8),
                 padx=10,
                 pady=5).pack(side=tk.LEFT, padx=5)
        
        tk.Button(quick_frame,
                 text="Common Conditions (Blur, Night, Low-Res)",
                 command=self.select_common_conditions,
                 bg='#95a5a6',
                 fg='white',
                 font=('Arial', 8),
                 padx=10,
                 pady=5).pack(side=tk.LEFT, padx=5)
    
    def create_results_section(self, parent):
        """Create results display section - FIXED VERSION"""
        results_frame = ttk.LabelFrame(parent, text="📊 Test Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10), padx=10)
        
        # Set minimum height for results section
        results_frame.configure(height=700)
        
        # Create paned window for split view
        paned = ttk.PanedWindow(results_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        # Left panel - Summary (with fixed height)
        left_panel = ttk.Frame(paned)
        paned.add(left_panel, weight=1)
        
        ttk.Label(left_panel, text="Summary", 
                 font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        
        # Summary text with scrollbar
        summary_container = tk.Frame(left_panel)
        summary_container.pack(fill=tk.BOTH, expand=True)
        
        summary_scroll = ttk.Scrollbar(summary_container)
        summary_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.summary_text = tk.Text(summary_container,
                                   height=30,
                                   width=50,
                                   font=('Courier', 9),
                                   yscrollcommand=summary_scroll.set,
                                   bg='#f8f9fa',
                                   wrap=tk.WORD)
        self.summary_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        summary_scroll.config(command=self.summary_text.yview)
        
        # Right panel - Visual results (with fixed height)
        right_panel = ttk.Frame(paned)
        paned.add(right_panel, weight=2)
        
        ttk.Label(right_panel, text="Visual Comparison",
                 font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        
        # Canvas for comparison image
        canvas_container = tk.Frame(right_panel, bg='white')
        canvas_container.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbars
        v_scroll = ttk.Scrollbar(canvas_container, orient=tk.VERTICAL)
        h_scroll = ttk.Scrollbar(canvas_container, orient=tk.HORIZONTAL)
        
        self.results_canvas = tk.Canvas(canvas_container,
                                       bg='white',
                                       height=650,
                                       width=800,
                                       yscrollcommand=v_scroll.set,
                                       xscrollcommand=h_scroll.set)
        
        v_scroll.config(command=self.results_canvas.yview)
        h_scroll.config(command=self.results_canvas.xview)
        
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.results_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    def create_control_buttons(self, parent):
        """Create control buttons"""
        control_frame = tk.Frame(parent, bg='white')
        control_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Process button
        self.btn_process = tk.Button(control_frame,
                                     text="▶️ Start Testing",
                                     command=self.start_testing,
                                     bg='#27ae60',
                                     fg='white',
                                     font=('Arial', 12, 'bold'),
                                     padx=30,
                                     pady=15,
                                     cursor='hand2',
                                     state=tk.DISABLED)
        self.btn_process.pack(side=tk.LEFT, padx=5)
        
        # Export results
        btn_export = tk.Button(control_frame,
                              text="💾 Export Results",
                              command=self.export_results,
                              bg='#f39c12',
                              fg='white',
                              font=('Arial', 10, 'bold'),
                              padx=20,
                              pady=15,
                              cursor='hand2')
        btn_export.pack(side=tk.LEFT, padx=5)
        
        # Save comparison image
        btn_save_comparison = tk.Button(control_frame,
                                       text="🖼️ Save Comparison",
                                       command=self.save_comparison_image,
                                       bg='#9b59b6',
                                       fg='white',
                                       font=('Arial', 10, 'bold'),
                                       padx=20,
                                       pady=15,
                                       cursor='hand2')
        btn_save_comparison.pack(side=tk.LEFT, padx=5)
        
        # Progress label
        self.progress_label = tk.Label(control_frame,
                                      text="",
                                      font=('Arial', 10),
                                      bg='white',
                                      fg='#27ae60')
        self.progress_label.pack(side=tk.LEFT, padx=20)
    
    # Event handlers (keep all existing methods from original file)
    def upload_single_image(self):
        """Upload a single image"""
        filepath = filedialog.askopenfilename(
            title="Select Vehicle Image",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.bmp"),
                ("All files", "*.*")
            ]
        )
        
        if filepath:
            self.current_images = [filepath]
            self.update_preview()
            self.btn_process.config(state=tk.NORMAL)
            self.log_message(f"Image loaded: {os.path.basename(filepath)}")
    
    def upload_batch_images(self):
        """Upload multiple images"""
        filepaths = filedialog.askopenfilenames(
            title="Select Vehicle Images",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.bmp"),
                ("All files", "*.*")
            ]
        )
        
        if filepaths:
            self.current_images = list(filepaths)
            self.update_preview()
            self.btn_process.config(state=tk.NORMAL)
            self.log_message(f"{len(filepaths)} images loaded")
    
    def clear_images(self):
        """Clear all loaded images"""
        self.current_images = []
        self.current_results = None
        self.update_preview()
        self.btn_process.config(state=tk.DISABLED)
        self.summary_text.delete('1.0', tk.END)
        self.results_canvas.delete('all')
        self.log_message("All images cleared")
    
    def update_preview(self):
        """Update preview thumbnails"""
        # Clear existing preview
        for widget in self.preview_frame_inner.winfo_children():
            widget.destroy()
        
        if not self.current_images:
            self.upload_status.config(text="No images loaded", fg='#e74c3c')
            return
        
        # Update status
        count = len(self.current_images)
        self.upload_status.config(
            text=f"{count} image{'s' if count > 1 else ''} loaded",
            fg='#27ae60'
        )
        
        # Create thumbnails
        for idx, img_path in enumerate(self.current_images):
            try:
                # Load and resize image
                img = Image.open(img_path)
                img.thumbnail((120, 120))
                photo = ImageTk.PhotoImage(img)
                
                # Create frame for each thumbnail
                thumb_frame = tk.Frame(self.preview_frame_inner, bg='white', 
                                      relief=tk.RAISED, borderwidth=1)
                thumb_frame.pack(side=tk.LEFT, padx=5, pady=5)
                
                # Image label
                img_label = tk.Label(thumb_frame, image=photo, bg='white')
                img_label.image = photo  # Keep reference
                img_label.pack()
                
                # Filename label
                filename = os.path.basename(img_path)
                if len(filename) > 15:
                    filename = filename[:12] + "..."
                name_label = tk.Label(thumb_frame, text=filename,
                                     font=('Arial', 7), bg='white')
                name_label.pack()
                
            except Exception as e:
                self.log_message(f"Error loading preview: {e}")
        
        # Update canvas scrollregion
        self.preview_frame_inner.update_idletasks()
        self.preview_canvas.config(scrollregion=self.preview_canvas.bbox('all'))
    
    def select_all_conditions(self):
        """Select all conditions"""
        for var in self.condition_vars.values():
            var.set(True)
    
    def deselect_all_conditions(self):
        """Deselect all conditions"""
        for var in self.condition_vars.values():
            var.set(False)
    
    def select_common_conditions(self):
        """Select commonly tested conditions"""
        common = ['motion_blur', 'night_view', 'low_resolution']
        for condition, var in self.condition_vars.items():
            var.set(condition in common)
    
    def start_testing(self):
        """Start the testing process"""
        if not self.current_images:
            messagebox.showwarning("Warning", "Please upload images first!")
            return
        
        # Get selected conditions
        selected = [cond for cond, var in self.condition_vars.items() if var.get()]
        
        # Confirm if no conditions selected
        if not selected:
            response = messagebox.askyesno(
                "No Conditions Selected",
                "No simulation conditions selected. Only original images will be tested.\n\n"
                "Continue?"
            )
            if not response:
                return
        
        # Disable button during processing
        self.btn_process.config(state=tk.DISABLED, text="⏳ Processing...")
        self.progress_label.config(text="Processing images...", fg='#f39c12')
        
        # Run in thread to prevent GUI freeze
        threading.Thread(target=self._process_images, 
                        args=(selected,), daemon=True).start()
    
    def _process_images(self, conditions):
        """Process images in background thread"""
        try:
            self.log_message(f"Starting test with {len(self.current_images)} image(s)")
            self.log_message(f"Conditions: {', '.join(conditions) if conditions else 'None'}")
            
            # Process all images
            results = self.image_tester.process_batch(
                self.current_images, 
                conditions if conditions else None
            )
            
            self.current_results = results
            
            # Generate report
            report = self.image_tester.generate_comparison_report(results)
            
            # Update GUI in main thread
            self.tab.after(0, self._update_results_display, report)
            
        except Exception as e:
            self.log_message(f"Error during processing: {e}")
            self.tab.after(0, messagebox.showerror, "Error", f"Processing failed: {e}")
        finally:
            self.tab.after(0, self._processing_complete)
    
    def _update_results_display(self, report):
        """Update results display (called in main thread)"""
        # Clear previous results
        self.summary_text.delete('1.0', tk.END)
        self.results_canvas.delete('all')
        
        # Display summary
        summary = self._format_summary(report)
        self.summary_text.insert('1.0', summary)
        
        # Create and display visual comparison for first image
        if self.current_results:
            try:
                comparison_img = self.image_tester.create_visual_comparison(
                    self.current_results[0]
                )
                
                # Convert to PhotoImage
                comparison_img_rgb = cv2.cvtColor(comparison_img, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(comparison_img_rgb)
                photo = ImageTk.PhotoImage(pil_img)
                
                # Display on canvas
                self.results_canvas.create_image(0, 0, anchor=tk.NW, image=photo)
                self.results_canvas.image = photo  # Keep reference
                
                # Update scrollregion
                self.results_canvas.config(scrollregion=self.results_canvas.bbox('all'))
                
            except Exception as e:
                self.log_message(f"Error creating visual comparison: {e}")
        
        self.log_message("Testing completed successfully!")
    
    def _format_summary(self, report):
        """Format the summary report"""
        summary_lines = []
        summary_lines.append("=" * 60)
        summary_lines.append("LICENSE PLATE RECOGNITION TEST REPORT")
        summary_lines.append("=" * 60)
        summary_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        summary_lines.append("")
        
        # Overall statistics
        summary_lines.append("OVERALL STATISTICS:")
        summary_lines.append("-" * 60)
        summary_lines.append(f"Total Tests: {report['summary']['total_tests']}")
        summary_lines.append(f"Successful Detections: {report['summary']['successful_detections']}")
        summary_lines.append(f"Failed Detections: {report['summary']['failed_detections']}")
        
        if report['summary']['total_tests'] > 0:
            success_rate = (report['summary']['successful_detections'] / 
                          report['summary']['total_tests']) * 100
            summary_lines.append(f"Success Rate: {success_rate:.1f}%")
        summary_lines.append("")
        
        # Condition performance
        if report['summary']['conditions_performance']:
            summary_lines.append("CONDITION PERFORMANCE:")
            summary_lines.append("-" * 60)
            
            for condition, perf in report['summary']['conditions_performance'].items():
                summary_lines.append(f"\n{condition.replace('_', ' ').title()}:")
                summary_lines.append(f"  Tested: {perf['tested']}")
                summary_lines.append(f"  Detected: {perf['detected']}")
                summary_lines.append(f"  Success Rate: {perf['success_rate']:.1f}%")
                summary_lines.append(f"  Avg Confidence: {perf['avg_confidence']:.2f}")
        
        summary_lines.append("")
        
        # Individual results
        summary_lines.append("DETAILED RESULTS:")
        summary_lines.append("-" * 60)
        
        for idx, result in enumerate(report['detailed_results'], 1):
            summary_lines.append(f"\nImage {idx}: {result['image_name']}")
            summary_lines.append(f"Timestamp: {result['timestamp']}")
            
            # Original result
            orig = result['original']
            summary_lines.append(f"\n  Original Image:")
            summary_lines.append(f"    Detected: {'Yes' if orig['detected'] else 'No'}")
            if orig['detected']:
                summary_lines.append(f"    Plates Found: {len(orig['plates'])}")

                # Show all detected plates
                if orig.get('detected_texts'):
                    summary_lines.append("    Detected Plates:")
                    for plate in orig['detected_texts']:
                        summary_lines.append(
                            f"      - {plate['text']} (Conf: {plate['confidence']:.2f})"
                        )
                else:
                    summary_lines.append(f"    Best Text: {orig['best_text']}")
                    summary_lines.append(f"    Confidence: {orig['best_confidence']:.2f}")

            
            # Condition results
            if result['conditions_tested']:
                summary_lines.append(f"\n  Simulated Conditions:")
                for condition, data in result['conditions_tested'].items():
                    cond_result = data['result']
                    summary_lines.append(f"\n    {condition.replace('_', ' ').title()}:")
                    summary_lines.append(f"      Detected: {'Yes' if cond_result['detected'] else 'No'}")
                    if cond_result['detected']:
                        if cond_result.get('detected_texts'):
                            summary_lines.append("      Detected Plates:")
                            for plate in cond_result['detected_texts']:
                                summary_lines.append(
                                    f"        - {plate['text']} (Conf: {plate['confidence']:.2f})"
                                )
                        else:
                            summary_lines.append(f"      Text: {cond_result['best_text']}")
                            summary_lines.append(f"      Confidence: {cond_result['best_confidence']:.2f}")

        
        summary_lines.append("")
        summary_lines.append("=" * 60)
        summary_lines.append("END OF REPORT")
        summary_lines.append("=" * 60)
        
        return "\n".join(summary_lines)
    
    def _processing_complete(self):
        """Re-enable controls after processing"""
        self.btn_process.config(state=tk.NORMAL, text="▶️ Start Testing")
        self.progress_label.config(text="✅ Testing complete!", fg='#27ae60')
    
    def export_results(self):
        """Export results to file"""
        if not self.current_results:
            messagebox.showwarning("Warning", "No results to export!")
            return
        
        # Ask for save location
        filepath = filedialog.asksaveasfilename(
            title="Export Results",
            defaultextension=".txt",
            filetypes=[
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )
        
        if filepath:
            try:
                with open(filepath, 'w') as f:
                    f.write(self.summary_text.get('1.0', tk.END))
                messagebox.showinfo("Success", "Results exported successfully!")
                self.log_message(f"Results exported to: {filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {e}")
    
    def save_comparison_image(self):
        """Save the comparison visualization"""
        if not self.current_results:
            messagebox.showwarning("Warning", "No results to save!")
            return
        
        # Ask for save location
        filepath = filedialog.asksaveasfilename(
            title="Save Comparison Image",
            defaultextension=".jpg",
            filetypes=[
                ("JPEG files", "*.jpg"),
                ("PNG files", "*.png"),
                ("All files", "*.*")
            ]
        )
        
        if filepath:
            try:
                # Create comparison for first image
                comparison_img = self.image_tester.create_visual_comparison(
                    self.current_results[0],
                    output_path=filepath
                )
                messagebox.showinfo("Success", "Comparison image saved successfully!")
                self.log_message(f"Comparison saved to: {filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Save failed: {e}")
