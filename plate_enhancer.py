"""
ANPR Image Enhancement Module
Optimized for low-quality license plate images from video surveillance

Techniques used:
- CLAHE: Contrast Limited Adaptive Histogram Equalization for lighting correction
- Bilateral Filter: Edge-preserving noise reduction
- Sharpening: Enhance character boundaries
- Adaptive Thresholding: Binary conversion for OCR
- Multiple preprocessing variants for ensemble OCR
"""

import cv2
import numpy as np
from typing import List, Tuple, Dict


class LicensePlateEnhancer:
    """
    Multi-stage image enhancement specifically designed for license plates
    """
    
    def __init__(self):
        """Initialize enhancement parameters"""
        # CLAHE parameters for contrast enhancement
        self.clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        
    def enhance_plate(self, plate_img: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Apply multiple enhancement techniques and return all variants
        
        Args:
            plate_img: Input license plate image (BGR or grayscale)
            
        Returns:
            Dictionary with different enhanced versions:
            - 'original': Original image
            - 'enhanced': Main enhanced version (recommended)
            - 'variant1': CLAHE + bilateral
            - 'variant2': Adaptive threshold
            - 'variant3': Sharpened + threshold
            - 'variant4': Morphology enhanced
        """
        if plate_img is None or plate_img.size == 0:
            return {'original': plate_img}
        
        # Convert to grayscale if needed
        if len(plate_img.shape) == 3:
            gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
        else:
            gray = plate_img.copy()
        
        results = {'original': gray}
        
        # Stage 1: Resolution upscaling (if too small)
        upscaled = self._upscale_if_needed(gray)
        
        # Stage 2: Main enhanced version (best balance)
        enhanced = self._create_main_enhanced(upscaled)
        results['enhanced'] = enhanced
        
        # Stage 3: Create multiple variants for ensemble OCR
        results['variant1'] = self._variant_clahe_bilateral(upscaled)
        results['variant2'] = self._variant_adaptive_threshold(upscaled)
        results['variant3'] = self._variant_sharpened_threshold(upscaled)
        results['variant4'] = self._variant_morphology(upscaled)
        
        return results
    
    def _upscale_if_needed(self, img: np.ndarray, min_width: int = 200) -> np.ndarray:
        """
        Upscale image if it's too small for effective OCR
        
        Why: Small license plates (< 200px width) have insufficient pixel density
        for character recognition. Bicubic interpolation adds detail.
        """
        h, w = img.shape[:2]
        
        if w < min_width:
            scale_factor = min_width / w
            new_w = int(w * scale_factor)
            new_h = int(h * scale_factor)
            
            # Bicubic interpolation for smooth upscaling
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        
        return img
    
    def _create_main_enhanced(self, img: np.ndarray) -> np.ndarray:
        """
        Main enhancement pipeline - balanced for general use
        
        Pipeline:
        1. Denoise while preserving edges (Bilateral filter)
        2. Enhance contrast adaptively (CLAHE)
        3. Sharpen character boundaries
        4. Normalize intensity
        """
        # Step 1: Bilateral filter - reduces noise while keeping edges sharp
        # Why: License plates have noise from compression, but we need sharp character edges
        denoised = cv2.bilateralFilter(img, d=5, sigmaColor=50, sigmaSpace=50)
        
        # Step 2: CLAHE - improves contrast in different lighting conditions
        # Why: Handles shadows, glare, uneven lighting on plates
        contrasted = self.clahe.apply(denoised)
        
        # Step 3: Sharpening - enhance character boundaries
        # Why: Makes character edges more distinct for OCR
        kernel_sharpen = np.array([[-1, -1, -1],
                                   [-1,  9, -1],
                                   [-1, -1, -1]])
        sharpened = cv2.filter2D(contrasted, -1, kernel_sharpen)
        
        # Step 4: Normalize intensity range
        normalized = cv2.normalize(sharpened, None, 0, 255, cv2.NORM_MINMAX)
        
        return normalized
    
    def _variant_clahe_bilateral(self, img: np.ndarray) -> np.ndarray:
        """
        Variant 1: Aggressive contrast + denoising
        Good for: Low light, shadowed plates
        """
        denoised = cv2.bilateralFilter(img, d=7, sigmaColor=75, sigmaSpace=75)
        clahe_strong = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
        enhanced = clahe_strong.apply(denoised)
        return enhanced
    
    def _variant_adaptive_threshold(self, img: np.ndarray) -> np.ndarray:
        """
        Variant 2: Adaptive binary threshold
        Good for: Uneven lighting, glare
        
        Why: Converts to binary (black/white) using local statistics
        Handles scenarios where global threshold fails
        """
        # Gaussian blur to reduce noise before thresholding
        blurred = cv2.GaussianBlur(img, (5, 5), 0)
        
        # Adaptive threshold - calculates threshold for small regions
        binary = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, blockSize=11, C=2
        )
        
        return binary
    
    def _variant_sharpened_threshold(self, img: np.ndarray) -> np.ndarray:
        """
        Variant 3: Heavy sharpening + threshold
        Good for: Blurry, motion-blurred plates
        """
        # Unsharp masking for aggressive sharpening
        gaussian = cv2.GaussianBlur(img, (0, 0), 2.0)
        sharpened = cv2.addWeighted(img, 1.5, gaussian, -0.5, 0)
        
        # Otsu's threshold for automatic binary conversion
        _, binary = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return binary
    
    def _variant_morphology(self, img: np.ndarray) -> np.ndarray:
        """
        Variant 4: Morphological operations
        Good for: Removing small artifacts, connecting broken characters
        
        Why: Morphology cleans up binary images by filling gaps
        and removing small noise pixels
        """
        # CLAHE first
        enhanced = self.clahe.apply(img)
        
        # Binary threshold
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Morphological closing - connects broken characters
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
        
        # Remove small noise
        opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel, iterations=1)
        
        return opened
    
    def enhance_for_display(self, plate_img: np.ndarray) -> np.ndarray:
        """
        Enhancement optimized for human viewing (not OCR)
        Used for saving screenshots and UI display
        """
        if plate_img is None or plate_img.size == 0:
            return plate_img
        
        # Convert to grayscale if needed
        if len(plate_img.shape) == 3:
            gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
        else:
            gray = plate_img.copy()
        
        # Upscale for better visibility
        upscaled = self._upscale_if_needed(gray, min_width=300)
        
        # Apply CLAHE
        enhanced = self.clahe.apply(upscaled)
        
        # Slight sharpening
        kernel_sharpen = np.array([[0, -1, 0],
                                   [-1, 5, -1],
                                   [0, -1, 0]])
        sharpened = cv2.filter2D(enhanced, -1, kernel_sharpen)
        
        # Convert back to BGR for display
        display_img = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)
        
        return display_img


class TemporalPlateTracker:
    """
    Track the same license plate across multiple frames
    Collects OCR results from multiple frames for temporal voting
    """
    
    def __init__(self, max_frames: int = 10):
        """
        Args:
            max_frames: Maximum number of frames to track per plate
        """
        self.max_frames = max_frames
        self.tracked_plates = {}  # {track_id: {'frames': [], 'ocr_results': []}}
    
    def add_frame(self, track_id: int, plate_img: np.ndarray, frame_number: int):
        """
        Add a new frame for a tracked plate
        
        Args:
            track_id: Unique identifier for this plate (from SORT tracker)
            plate_img: Cropped license plate image
            frame_number: Current frame number
        """
        if track_id not in self.tracked_plates:
            self.tracked_plates[track_id] = {
                'frames': [],
                'images': [],
                'frame_numbers': []
            }
        
        plate_data = self.tracked_plates[track_id]
        
        # Add new frame (keep only recent frames)
        if len(plate_data['frames']) >= self.max_frames:
            plate_data['frames'].pop(0)
            plate_data['images'].pop(0)
            plate_data['frame_numbers'].pop(0)
        
        plate_data['frames'].append(plate_img)
        plate_data['images'].append(plate_img)
        plate_data['frame_numbers'].append(frame_number)
    
    def add_ocr_result(self, track_id: int, ocr_text: str, confidence: float):
        """
        Add OCR result for a specific track
        
        Args:
            track_id: Plate identifier
            ocr_text: Recognized text
            confidence: OCR confidence score
        """
        if track_id not in self.tracked_plates:
            return
        
        if 'ocr_results' not in self.tracked_plates[track_id]:
            self.tracked_plates[track_id]['ocr_results'] = []
        
        self.tracked_plates[track_id]['ocr_results'].append({
            'text': ocr_text,
            'confidence': confidence
        })
    
    def get_best_frames(self, track_id: int, top_n: int = 5) -> List[np.ndarray]:
        """
        Get the best quality frames for a tracked plate
        
        Args:
            track_id: Plate identifier
            top_n: Number of best frames to return
            
        Returns:
            List of best plate images (based on sharpness/quality)
        """
        if track_id not in self.tracked_plates:
            return []
        
        frames = self.tracked_plates[track_id]['frames']
        
        if len(frames) <= top_n:
            return frames
        
        # Calculate sharpness score for each frame (Laplacian variance)
        scored_frames = []
        for frame in frames:
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame
            
            # Higher variance = sharper image
            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
            scored_frames.append((sharpness, frame))
        
        # Sort by sharpness (descending) and return top N
        scored_frames.sort(reverse=True, key=lambda x: x[0])
        return [frame for _, frame in scored_frames[:top_n]]
    
    def get_temporal_ocr_results(self, track_id: int) -> List[Dict]:
        """
        Get all OCR results for temporal voting
        
        Returns:
            List of OCR results with text and confidence
        """
        if track_id not in self.tracked_plates:
            return []
        
        return self.tracked_plates[track_id].get('ocr_results', [])
    
    def cleanup_old_tracks(self, current_active_ids: List[int]):
        """
        Remove tracks that are no longer active
        
        Args:
            current_active_ids: List of currently active track IDs
        """
        inactive_ids = [tid for tid in self.tracked_plates.keys() 
                       if tid not in current_active_ids]
        
        for tid in inactive_ids:
            del self.tracked_plates[tid]


# Utility function for quick enhancement
def quick_enhance(plate_img: np.ndarray) -> np.ndarray:
    """
    Quick single-shot enhancement for immediate use
    
    Args:
        plate_img: Input license plate image
        
    Returns:
        Enhanced image ready for OCR
    """
    enhancer = LicensePlateEnhancer()
    variants = enhancer.enhance_plate(plate_img)
    return variants['enhanced']


if __name__ == "__main__":
    # Example usage
    print("License Plate Enhancement Module")
    print("=" * 50)
    print("\nUsage:")
    print("  from plate_enhancer import LicensePlateEnhancer")
    print("  enhancer = LicensePlateEnhancer()")
    print("  enhanced_variants = enhancer.enhance_plate(plate_img)")
    print("  best_img = enhanced_variants['enhanced']")