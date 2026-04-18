"""
Advanced Image Enhancement Module
Handles image quality issues, environmental conditions, and preprocessing
"""

import cv2
import numpy as np
from typing import Tuple, List, Dict, Optional
import logging

class ImageEnhancer:
    """
    Comprehensive image enhancement for license plate detection
    Addresses: motion blur, low light, weather conditions, quality issues
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Adaptive parameters
        self.clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        
        # Denoising parameters
        self.denoise_params = {
            'h': 10,
            'templateWindowSize': 7,
            'searchWindowSize': 21
        }
        
    def enhance_frame(self, frame: np.ndarray, enhancement_level: str = 'moderate') -> np.ndarray:
        """
        Master enhancement function that applies appropriate enhancements
        
        Args:
            frame: Input frame
            enhancement_level: 'light', 'moderate', 'aggressive'
        
        Returns:
            Enhanced frame
        """
        if frame is None or frame.size == 0:
            return frame
            
        try:
            # Analyze frame quality
            quality_metrics = self._analyze_quality(frame)
            
            # Apply enhancements based on quality metrics
            enhanced = frame.copy()
            
            # 1. Handle motion blur
            if quality_metrics['blur_score'] < 100:
                enhanced = self._reduce_motion_blur(enhanced)
            
            # 2. Handle low light
            if quality_metrics['brightness'] < 80:
                enhanced = self._enhance_low_light(enhanced)
            
            # 3. Handle overexposure
            elif quality_metrics['brightness'] > 180:
                enhanced = self._reduce_overexposure(enhanced)
            
            # 4. Denoise
            if quality_metrics['noise_level'] > 0.15:
                enhanced = self._denoise_frame(enhanced)
            
            # 5. Sharpen (always apply lightly)
            enhanced = self._adaptive_sharpen(enhanced, quality_metrics)
            
            # 6. Enhance contrast
            enhanced = self._enhance_contrast(enhanced)
            
            return enhanced
            
        except Exception as e:
            self.logger.error(f"Enhancement error: {e}")
            return frame
    
    def _analyze_quality(self, frame: np.ndarray) -> Dict[str, float]:
        """Analyze frame quality metrics"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Brightness
        brightness = np.mean(gray)
        
        # Blur detection (Laplacian variance)
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        # Noise estimation
        noise_level = self._estimate_noise(gray)
        
        # Contrast
        contrast = gray.std()
        
        return {
            'brightness': brightness,
            'blur_score': blur_score,
            'noise_level': noise_level,
            'contrast': contrast
        }
    
    def _estimate_noise(self, gray: np.ndarray) -> float:
        """Estimate noise level in image"""
        # Using Median Absolute Deviation
        H, W = gray.shape
        M = [[1, -2, 1],
             [-2, 4, -2],
             [1, -2, 1]]
        
        sigma = np.sum(np.sum(np.absolute(cv2.filter2D(gray.astype(float), -1, np.array(M)))))
        sigma = sigma * np.sqrt(0.5 * np.pi) / (6 * (W - 2) * (H - 2))
        
        return sigma
    
    def _reduce_motion_blur(self, frame: np.ndarray) -> np.ndarray:
        """
        Reduce motion blur using Wiener filter approximation
        """
        # Estimate motion blur kernel
        kernel_size = 9
        kernel = np.zeros((kernel_size, kernel_size))
        kernel[int((kernel_size - 1) / 2), :] = np.ones(kernel_size)
        kernel /= kernel_size
        
        # Apply deconvolution (simplified Wiener filter)
        deblurred = cv2.filter2D(frame, -1, kernel)
        
        # Sharpen to compensate
        kernel_sharpen = np.array([[-1, -1, -1],
                                   [-1,  9, -1],
                                   [-1, -1, -1]])
        sharpened = cv2.filter2D(deblurred, -1, kernel_sharpen)
        
        # Blend original and deblurred
        alpha = 0.6
        result = cv2.addWeighted(frame, 1 - alpha, sharpened, alpha, 0)
        
        return result
    
    def _enhance_low_light(self, frame: np.ndarray) -> np.ndarray:
        """
        Multi-method low-light enhancement
        """
        # Method 1: CLAHE on LAB color space
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # Apply CLAHE to L channel
        l_clahe = self.clahe.apply(l)
        
        # Merge back
        lab_clahe = cv2.merge([l_clahe, a, b])
        enhanced = cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)
        
        # Method 2: Gamma correction
        gamma = 1.5
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255
                         for i in np.arange(0, 256)]).astype("uint8")
        gamma_corrected = cv2.LUT(enhanced, table)
        
        # Method 3: Adaptive histogram equalization
        hsv = cv2.cvtColor(gamma_corrected, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        v = self.clahe.apply(v)
        hsv_enhanced = cv2.merge([h, s, v])
        final = cv2.cvtColor(hsv_enhanced, cv2.COLOR_HSV2BGR)
        
        return final
    
    def _reduce_overexposure(self, frame: np.ndarray) -> np.ndarray:
        """
        Reduce overexposure and recover details
        """
        # Inverse gamma correction
        gamma = 0.7
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255
                         for i in np.arange(0, 256)]).astype("uint8")
        
        corrected = cv2.LUT(frame, table)
        
        # Apply bilateral filter to preserve edges
        filtered = cv2.bilateralFilter(corrected, 9, 75, 75)
        
        return filtered
    
    def _denoise_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Advanced denoising while preserving edges
        """
        # Non-local means denoising
        denoised = cv2.fastNlMeansDenoisingColored(
            frame,
            None,
            h=self.denoise_params['h'],
            hColor=self.denoise_params['h'],
            templateWindowSize=self.denoise_params['templateWindowSize'],
            searchWindowSize=self.denoise_params['searchWindowSize']
        )
        
        return denoised
    
    def _adaptive_sharpen(self, frame: np.ndarray, quality_metrics: Dict) -> np.ndarray:
        """
        Adaptive sharpening based on quality metrics
        """
        # Determine sharpening strength
        if quality_metrics['blur_score'] < 100:
            strength = 1.5  # Strong sharpening
        elif quality_metrics['blur_score'] < 300:
            strength = 1.0  # Medium sharpening
        else:
            strength = 0.5  # Light sharpening
        
        # Unsharp mask
        gaussian = cv2.GaussianBlur(frame, (0, 0), 2.0)
        sharpened = cv2.addWeighted(frame, 1.0 + strength, gaussian, -strength, 0)
        
        return sharpened
    
    def _enhance_contrast(self, frame: np.ndarray) -> np.ndarray:
        """
        Enhance contrast adaptively
        """
        # Convert to LAB
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # Apply CLAHE
        l_enhanced = self.clahe.apply(l)
        
        # Merge and convert back
        enhanced_lab = cv2.merge([l_enhanced, a, b])
        enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
        
        return enhanced
    
    def handle_weather_conditions(self, frame: np.ndarray, condition: str = 'auto') -> np.ndarray:
        """
        Handle specific weather conditions
        
        Args:
            frame: Input frame
            condition: 'auto', 'rain', 'fog', 'night', 'glare'
        """
        if condition == 'auto':
            condition = self._detect_weather_condition(frame)
        
        if condition == 'rain':
            return self._handle_rain(frame)
        elif condition == 'fog':
            return self._handle_fog(frame)
        elif condition == 'night':
            return self._handle_night(frame)
        elif condition == 'glare':
            return self._handle_glare(frame)
        else:
            return frame
    
    def _detect_weather_condition(self, frame: np.ndarray) -> str:
        """Auto-detect weather condition"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = np.mean(gray)
        contrast = gray.std()
        
        if brightness < 60:
            return 'night'
        elif contrast < 30:
            return 'fog'
        elif brightness > 200:
            return 'glare'
        else:
            return 'normal'
    
    def _handle_rain(self, frame: np.ndarray) -> np.ndarray:
        """Handle rain conditions"""
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        opened = cv2.morphologyEx(frame, cv2.MORPH_OPEN, kernel)
        filtered = cv2.bilateralFilter(opened, 9, 75, 75)
        enhanced = self._enhance_contrast(filtered)
        return enhanced
    
    def _handle_fog(self, frame: np.ndarray) -> np.ndarray:
        """Handle fog/haze using dark channel prior"""
        def get_dark_channel(img, size=15):
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (size, size))
            dark = cv2.erode(img.min(axis=2), kernel)
            return dark
        
        dark_channel = get_dark_channel(frame)
        flat_frame = frame.reshape(-1, 3)
        flat_dark = dark_channel.ravel()
        
        indices = flat_dark.argsort()[-int(len(flat_dark) * 0.001):]
        atmospheric_light = flat_frame[indices].max(axis=0)
        
        transmission = 1 - 0.95 * get_dark_channel(frame / atmospheric_light.reshape(1, 1, 3))
        transmission = np.maximum(transmission, 0.1)
        
        dehazed = np.zeros_like(frame, dtype=np.float64)
        for i in range(3):
            dehazed[:, :, i] = (frame[:, :, i] - atmospheric_light[i]) / transmission + atmospheric_light[i]
        
        dehazed = np.clip(dehazed, 0, 255).astype(np.uint8)
        return dehazed
    
    def _handle_night(self, frame: np.ndarray) -> np.ndarray:
        """Handle night conditions"""
        enhanced = self._enhance_low_light(frame)
        enhanced = cv2.fastNlMeansDenoisingColored(enhanced, None, 15, 15, 7, 21)
        return enhanced
    
    def _handle_glare(self, frame: np.ndarray) -> np.ndarray:
        """Handle headlight glare"""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        
        _, bright_mask = cv2.threshold(v, 240, 255, cv2.THRESH_BINARY)
        inpainted = cv2.inpaint(frame, bright_mask, 3, cv2.INPAINT_TELEA)
        
        v_reduced = cv2.addWeighted(v, 0.8, np.zeros_like(v), 0, -20)
        v_reduced = np.clip(v_reduced, 0, 255).astype(np.uint8)
        
        hsv_reduced = cv2.merge([h, s, v_reduced])
        result = cv2.cvtColor(hsv_reduced, cv2.COLOR_HSV2BGR)
        
        final = cv2.addWeighted(result, 0.7, inpainted, 0.3, 0)
        return final


class PlateRegionEnhancer:
    """
    Specialized enhancement for detected license plate regions
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def enhance_plate_region(self, plate_img: np.ndarray) -> Dict:
        """
        Specialized enhancement pipeline for license plate region
        Returns multiple versions for robust OCR
        """
        if plate_img is None or plate_img.size == 0:
            return {'original': plate_img}
        
        try:
            # 1. Resize for better OCR
            h, w = plate_img.shape[:2]
            if h < 64:
                scale = 64 / h
                plate_img = cv2.resize(plate_img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            
            # 2. Convert to grayscale
            if len(plate_img.shape) == 3:
                gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = plate_img.copy()
            
            # 3. Denoise
            denoised = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)
            
            # 4. Morphological operations
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            morph = cv2.morphologyEx(denoised, cv2.MORPH_CLOSE, kernel)
            
            # 5. Multiple thresholding methods
            _, otsu = cv2.threshold(morph, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            adaptive = cv2.adaptiveThreshold(morph, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                            cv2.THRESH_BINARY, 11, 2)
            
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
            enhanced = clahe.apply(morph)
            _, custom = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            return {
                'original': plate_img,
                'enhanced': enhanced,
                'otsu': otsu,
                'adaptive': adaptive,
                'custom': custom
            }
            
        except Exception as e:
            self.logger.error(f"Plate enhancement error: {e}")
            return {'original': plate_img}
    
    def correct_perspective(self, plate_img: np.ndarray) -> np.ndarray:
        """Correct perspective distortion"""
        if plate_img is None or plate_img.size == 0:
            return plate_img
        
        try:
            gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY) if len(plate_img.shape) == 3 else plate_img
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                largest_contour = max(contours, key=cv2.contourArea)
                epsilon = 0.02 * cv2.arcLength(largest_contour, True)
                corners = cv2.approxPolyDP(largest_contour, epsilon, True)
                
                if len(corners) == 4:
                    corners = corners.reshape(4, 2).astype("float32")
                    corners = self._order_points(corners)
                    
                    widths = [np.linalg.norm(corners[1] - corners[0]), np.linalg.norm(corners[2] - corners[3])]
                    heights = [np.linalg.norm(corners[3] - corners[0]), np.linalg.norm(corners[2] - corners[1])]
                    
                    maxWidth = int(max(widths))
                    maxHeight = int(max(heights))
                    
                    dst = np.array([[0, 0], [maxWidth - 1, 0], 
                                   [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]], dtype="float32")
                    
                    M = cv2.getPerspectiveTransform(corners, dst)
                    warped = cv2.warpPerspective(plate_img, M, (maxWidth, maxHeight))
                    return warped
            
            return plate_img
            
        except Exception as e:
            self.logger.error(f"Perspective correction error: {e}")
            return plate_img
    
    def _order_points(self, pts: np.ndarray) -> np.ndarray:
        """Order points clockwise from top-left"""
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return rect