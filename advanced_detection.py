"""
Advanced Detection Module
Handles: small plates, multiple vehicles, overlapping, false positives
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
import logging

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False


class MultiScaleDetector:
    """Multi-scale detection for improved small object detection"""
    
    def __init__(self, model_path: str):
        self.logger = logging.getLogger(__name__)
        self.model = None
        
        if YOLO_AVAILABLE:
            try:
                self.model = YOLO(model_path)
                self.logger.info(f"Model loaded: {model_path}")
            except Exception as e:
                self.logger.error(f"Model loading error: {e}")
        
        self.scales = [0.75, 1.0, 1.25, 1.5]
        self.min_confidence = 0.15
        self.nms_threshold = 0.3
    
    def detect_multi_scale(self, frame: np.ndarray) -> List[Dict]:
        """Perform multi-scale detection"""
        if self.model is None:
            return []
        
        all_detections = []
        original_h, original_w = frame.shape[:2]
        
        for scale in self.scales:
            if scale != 1.0:
                scaled_w = int(original_w * scale)
                scaled_h = int(original_h * scale)
                scaled_frame = cv2.resize(frame, (scaled_w, scaled_h))
            else:
                scaled_frame = frame
            
            try:
                results = self.model(scaled_frame, conf=self.min_confidence, verbose=False)
                
                for result in results:
                    boxes = result.boxes
                    
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        confidence = float(box.conf[0])
                        class_id = int(box.cls[0])
                        
                        x1_orig = int(x1 / scale)
                        y1_orig = int(y1 / scale)
                        x2_orig = int(x2 / scale)
                        y2_orig = int(y2 / scale)
                        
                        box_area = (x2_orig - x1_orig) * (y2_orig - y1_orig)
                        frame_area = original_h * original_w
                        area_ratio = box_area / frame_area
                        
                        detection = {
                            'bbox': [x1_orig, y1_orig, x2_orig, y2_orig],
                            'confidence': confidence,
                            'class_id': class_id,
                            'scale': scale,
                            'area_ratio': area_ratio
                        }
                        
                        all_detections.append(detection)
                        
            except Exception as e:
                self.logger.error(f"Detection error at scale {scale}: {e}")
        
        final_detections = self._apply_nms_multi_scale(all_detections)
        return final_detections
    
    def _apply_nms_multi_scale(self, detections: List[Dict]) -> List[Dict]:
        """Apply Non-Maximum Suppression"""
        if not detections:
            return []
        
        boxes = [d['bbox'] for d in detections]
        confidences = [d['confidence'] for d in detections]
        boxes_cv = [[b[0], b[1], b[2]-b[0], b[3]-b[1]] for b in boxes]
        
        indices = cv2.dnn.NMSBoxes(boxes_cv, confidences, 
                                   self.min_confidence, self.nms_threshold)
        
        if len(indices) > 0:
            indices = indices.flatten()
            return [detections[i] for i in indices]
        
        return []


class AdvancedTracker:
    """Enhanced tracking with occlusion handling"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.tracks = {}
        self.next_track_id = 1
        self.max_disappeared = 30
        self.iou_threshold = 0.3
        self.track_history = {}
        self.max_history = 30
    
    def update(self, detections: List[Dict]) -> Dict[int, Dict]:
        """Update tracks with new detections"""
        for track_id in self.tracks:
            self.tracks[track_id]['updated'] = False
        
        if detections and self.tracks:
            matched_pairs = self._match_detections_to_tracks(detections)
            
            for det_idx, track_id in matched_pairs:
                self._update_track(track_id, detections[det_idx])
                detections[det_idx]['matched'] = True
        
        for detection in detections:
            if not detection.get('matched', False):
                self._create_new_track(detection)
        
        self._handle_disappeared_tracks()
        self._update_track_history()
        
        return self.get_active_tracks()
    
    def _match_detections_to_tracks(self, detections: List[Dict]) -> List[Tuple[int, int]]:
        """Match detections to existing tracks"""
        matched_pairs = []
        
        if not self.tracks or not detections:
            return matched_pairs
        
        track_ids = list(self.tracks.keys())
        cost_matrix = np.zeros((len(detections), len(track_ids)))
        
        for i, detection in enumerate(detections):
            det_bbox = detection['bbox']
            
            for j, track_id in enumerate(track_ids):
                track_bbox = self.tracks[track_id]['bbox']
                iou = self._calculate_iou(det_bbox, track_bbox)
                cost_matrix[i, j] = 1 - iou
        
        matches = self._greedy_matching(cost_matrix, self.iou_threshold)
        
        for det_idx, track_idx in matches:
            track_id = track_ids[track_idx]
            matched_pairs.append((det_idx, track_id))
        
        return matched_pairs
    
    def _calculate_iou(self, bbox1: List[float], bbox2: List[float]) -> float:
        """Calculate Intersection over Union"""
        x1_1, y1_1, x2_1, y2_1 = bbox1
        x1_2, y1_2, x2_2, y2_2 = bbox2
        
        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)
        
        if x2_i < x1_i or y2_i < y1_i:
            return 0.0
        
        intersection = (x2_i - x1_i) * (y2_i - y1_i)
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0
    
    def _greedy_matching(self, cost_matrix: np.ndarray, threshold: float) -> List[Tuple[int, int]]:
        """Greedy matching algorithm"""
        matches = []
        cost_threshold = 1 - threshold
        
        used_detections = set()
        used_tracks = set()
        
        det_indices, track_indices = np.where(cost_matrix < cost_threshold)
        costs = cost_matrix[det_indices, track_indices]
        sorted_indices = np.argsort(costs)
        
        for idx in sorted_indices:
            det_idx = det_indices[idx]
            track_idx = track_indices[idx]
            
            if det_idx not in used_detections and track_idx not in used_tracks:
                matches.append((det_idx, track_idx))
                used_detections.add(det_idx)
                used_tracks.add(track_idx)
        
        return matches
    
    def _update_track(self, track_id: int, detection: Dict):
        """Update existing track"""
        track = self.tracks[track_id]
        track['bbox'] = detection['bbox']
        track['confidence'] = detection['confidence']
        track['updated'] = True
        track['disappeared_count'] = 0
        track['total_detections'] += 1
        
        if 'plate_number' in detection:
            track['plate_number'] = detection['plate_number']
    
    def _create_new_track(self, detection: Dict):
        """Create new track"""
        track_id = self.next_track_id
        self.next_track_id += 1
        
        self.tracks[track_id] = {
            'track_id': track_id,
            'bbox': detection['bbox'],
            'confidence': detection['confidence'],
            'updated': True,
            'disappeared_count': 0,
            'total_detections': 1,
            'first_frame': True
        }
        
        if 'plate_number' in detection:
            self.tracks[track_id]['plate_number'] = detection['plate_number']
    
    def _handle_disappeared_tracks(self):
        """Handle tracks that weren't updated"""
        to_remove = []
        
        for track_id, track in self.tracks.items():
            if not track['updated']:
                track['disappeared_count'] += 1
                
                if track['disappeared_count'] > self.max_disappeared:
                    to_remove.append(track_id)
        
        for track_id in to_remove:
            del self.tracks[track_id]
            if track_id in self.track_history:
                del self.track_history[track_id]
    
    def _update_track_history(self):
        """Update position history for all tracks"""
        for track_id, track in self.tracks.items():
            if track_id not in self.track_history:
                self.track_history[track_id] = []
            
            self.track_history[track_id].append(track['bbox'].copy())
            
            if len(self.track_history[track_id]) > self.max_history:
                self.track_history[track_id].pop(0)
    
    def get_active_tracks(self) -> Dict[int, Dict]:
        """Get all active tracks"""
        return {tid: track for tid, track in self.tracks.items() 
                if track['disappeared_count'] < 5}


class FalsePositiveFilter:
    """Filter false positive detections"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.min_aspect_ratio = 1.5
        self.max_aspect_ratio = 6.0
        self.min_size_ratio = 0.001
        self.max_size_ratio = 0.15
    
    def filter_detections(self, detections: List[Dict], frame_shape: Tuple[int, int]) -> List[Dict]:
        """Filter false positive detections"""
        filtered = []
        frame_h, frame_w = frame_shape
        frame_area = frame_h * frame_w
        
        for detection in detections:
            x1, y1, x2, y2 = detection['bbox']
            
            width = x2 - x1
            height = y2 - y1
            area = width * height
            
            if width <= 0 or height <= 0:
                continue
            
            aspect_ratio = width / height
            if not (self.min_aspect_ratio <= aspect_ratio <= self.max_aspect_ratio):
                continue
            
            size_ratio = area / frame_area
            if not (self.min_size_ratio <= size_ratio <= self.max_size_ratio):
                continue
            
            if x1 < 5 or y1 < 5 or x2 > frame_w - 5 or y2 > frame_h - 5:
                detection['confidence'] *= 0.8
            
            filtered.append(detection)
        
        return filtered