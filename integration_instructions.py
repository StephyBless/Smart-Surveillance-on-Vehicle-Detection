"""
Integration Instructions for Image Testing Module
Add these changes to your a1v6.py file
"""

# ========================================
# STEP 1: Add imports at the top of a1v6.py (after line 18)
# ========================================

# Add these lines after: from enhanced_lpr_system import EnhancedLPRProcessor

from image_lpr_tester import ImageLPRTester
from image_testing_gui import ImageTestingTab


# ========================================
# STEP 2: Initialize Image Tester in __init__ method
# ========================================

# Add this code in the __init__ method after line 120 (after self.log_message("⚙️ Enhanced processor settings applied"))

# Initialize Image Testing Module
try:
    self.image_tester = ImageLPRTester(
        enhanced_processor=self.enhanced_processor,
        license_plate_detector=self.license_plate_detector
    )
    self.log_message("✅ Image testing module initialized")
except Exception as e:
    self.log_message(f"⚠️ Image testing module initialization failed: {e}")
    self.image_tester = None


# ========================================
# STEP 3: Add Image Testing Tab in setup_gui method
# ========================================

# Add this code in setup_gui method, after all other tabs are created
# (Find where the tabs are added to the notebook and add this after the last tab)

# Add Image Testing Tab
if self.image_tester:
    try:
        self.image_testing_tab = ImageTestingTab(
            parent_notebook=self.notebook,
            image_tester=self.image_tester,
            log_callback=self.log_message
        )
        self.log_message("✅ Image testing tab added")
    except Exception as e:
        self.log_message(f"⚠️ Could not add image testing tab: {e}")


# ========================================
# COMPLETE INTEGRATION CODE BLOCK
# ========================================
# Copy this entire block and add it to your a1v6.py

"""
# At the top with other imports (around line 18):
from image_lpr_tester import ImageLPRTester
from image_testing_gui import ImageTestingTab

# In __init__ method (around line 120, after enhanced processor initialization):
        # Initialize Image Testing Module
        try:
            self.image_tester = ImageLPRTester(
                enhanced_processor=self.enhanced_processor,
                license_plate_detector=self.license_plate_detector
            )
            self.log_message("✅ Image testing module initialized")
        except Exception as e:
            self.log_message(f"⚠️ Image testing module initialization failed: {e}")
            self.image_tester = None

# In setup_gui method (after creating all other tabs, around line 217):
        # Add Image Testing Tab
        if self.image_tester:
            try:
                self.image_testing_tab = ImageTestingTab(
                    parent_notebook=self.notebook,
                    image_tester=self.image_tester,
                    log_callback=self.log_message
                )
                self.log_message("✅ Image testing tab added")
            except Exception as e:
                self.log_message(f"⚠️ Could not add image testing tab: {e}")
"""


# ========================================
# USAGE INSTRUCTIONS
# ========================================

"""
HOW TO USE THE IMAGE TESTING MODULE:

1. Launch your application normally (python a1v6.py)

2. Click on the "🖼️ Image Testing" tab

3. Upload images:
   - Click "📷 Upload Single Image" for one image
   - Click "📁 Upload Multiple Images" for batch testing

4. Select simulation conditions:
   - Check the conditions you want to test (motion blur, night view, etc.)
   - Or click "Select All" to test all conditions
   - Or click "Common Conditions" for quick selection

5. Click "▶️ Start Testing" to begin

6. View results:
   - Summary panel shows detailed statistics
   - Visual panel shows side-by-side comparisons
   
7. Export:
   - Click "💾 Export Results" to save text report
   - Click "🖼️ Save Comparison" to save visual comparison image

FEATURES:
✓ Single and batch image processing
✓ 8 different condition simulations
✓ Automatic text validation and formatting
✓ Multiple OCR methods for accuracy
✓ Visual side-by-side comparisons
✓ Detailed performance statistics
✓ Export capabilities
✓ Tests your EnhancedLPRProcessor
"""
