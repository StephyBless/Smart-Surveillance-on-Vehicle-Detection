from ultralytics import YOLO
import cv2
import subprocess
import sys
import os

import util
from sort.sort import *
from util import get_car, read_license_plate, write_csv

# Import the search functionality (assuming it's in a separate file)
try:
    from license_plate_search import search_license_plate, interactive_search_menu
except ImportError:
    print("Warning: Search functionality not available. Make sure license_plate_search.py is in the same directory.")
    search_license_plate = None
    interactive_search_menu = None


def main():
    results = {}

    mot_tracker = Sort()

    # load models
    print("Loading models...")
    coco_model = YOLO('yolov8n.pt')
    license_plate_detector = YOLO('license_plate_detector.pt')

    # load video
    print("Loading video...")
    cap = cv2.VideoCapture('./sample.mp4')
    
    if not cap.isOpened():
        print("Error: Could not open video file './sample.mp4'")
        return

    vehicles = [2, 3, 5, 7]  # COCO class IDs for vehicles

    # read frames
    print("Processing video frames...")
    frame_nmr = -1
    ret = True
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    while ret:
        frame_nmr += 1
        ret, frame = cap.read()
        
        if ret:
            # Progress indicator
            if frame_nmr % 10 == 0:
                progress = (frame_nmr / total_frames) * 100
                print(f"Processing frame {frame_nmr}/{total_frames} ({progress:.1f}%)")
            
            results[frame_nmr] = {}
            
            # detect vehicles
            detections = coco_model(frame)[0]
            detections_ = []
            for detection in detections.boxes.data.tolist():
                x1, y1, x2, y2, score, class_id = detection
                if int(class_id) in vehicles:
                    detections_.append([x1, y1, x2, y2, score])

            # track vehicles
            track_ids = mot_tracker.update(np.asarray(detections_))

            # detect license plates
            license_plates = license_plate_detector(frame)[0]
            for license_plate in license_plates.boxes.data.tolist():
                x1, y1, x2, y2, score, class_id = license_plate

                # assign license plate to car
                xcar1, ycar1, xcar2, ycar2, car_id = get_car(license_plate, track_ids)

                if car_id != -1:
                    # crop license plate
                    license_plate_crop = frame[int(y1):int(y2), int(x1): int(x2), :]

                    # process license plate
                    license_plate_crop_gray = cv2.cvtColor(license_plate_crop, cv2.COLOR_BGR2GRAY)
                    _, license_plate_crop_thresh = cv2.threshold(license_plate_crop_gray, 64, 255, cv2.THRESH_BINARY_INV)

                    # read license plate number
                    license_plate_text, license_plate_text_score = read_license_plate(license_plate_crop_thresh)

                    if license_plate_text is not None:
                        results[frame_nmr][car_id] = {'car': {'bbox': [xcar1, ycar1, xcar2, ycar2]},
                                                      'license_plate': {'bbox': [x1, y1, x2, y2],
                                                                        'text': license_plate_text,
                                                                        'bbox_score': score,
                                                                        'text_score': license_plate_text_score}}

    cap.release()
    print("Video processing completed!")

    # write results to CSV
    print("Writing results to CSV...")
    csv_output_path = './test.csv'
    write_csv(results, csv_output_path)
    print(f"Results saved to {csv_output_path}")

    # Run interpolation if the script exists
    interpolated_csv_path = './test_interpolated.csv'
    if os.path.exists('add_missing_data.py'):
        try:
            print("Running interpolation to fill missing data...")
            subprocess.run([sys.executable, 'add_missing_data.py'], check=True)
            print(f"Interpolated results saved to {interpolated_csv_path}")
            csv_to_search = interpolated_csv_path
        except subprocess.CalledProcessError:
            print("Warning: Interpolation failed. Using original CSV file.")
            csv_to_search = csv_output_path
    else:
        print("Note: add_missing_data.py not found. Skipping interpolation.")
        csv_to_search = csv_output_path

    # Start search functionality
    if search_license_plate is not None:
        print("\n" + "="*60)
        print("PROCESSING COMPLETE!")
        print("="*60)
        
        while True:
            user_choice = input("\nWould you like to search for a specific license plate? (y/n): ").strip().lower()
            
            if user_choice in ['y', 'yes']:
                interactive_search_menu(csv_to_search)
                break
            elif user_choice in ['n', 'no']:
                print("Search skipped. You can run the search later using license_plate_search.py")
                break
            else:
                print("Please enter 'y' for yes or 'n' for no.")
    else:
        print("\nProcessing complete! Search functionality is not available.")
        print("To enable search, make sure license_plate_search.py is in the same directory.")

    print(f"\nFinal results are available in:")
    print(f"  - Original: {csv_output_path}")
    if os.path.exists(interpolated_csv_path):
        print(f"  - Interpolated: {interpolated_csv_path}")


if __name__ == "__main__":
    main()