import csv
import numpy as np
from scipy.interpolate import interp1d


def interpolate_bounding_boxes(data):
    """Interpolate bounding boxes with proper NaN handling"""
    
    # Filter out invalid data first
    valid_data = []
    for row in data:
        try:
            # Test if we can convert the values
            frame_num = int(float(row['frame_nmr']))
            car_id = int(float(row['car_id']))
            
            # Test if bounding boxes are valid
            car_bbox = list(map(float, row['car_bbox'][1:-1].split()))
            lp_bbox = list(map(float, row['license_plate_bbox'][1:-1].split()))
            
            # Check for NaN values
            if (np.isnan(frame_num) or np.isnan(car_id) or 
                any(np.isnan(coord) for coord in car_bbox) or 
                any(np.isnan(coord) for coord in lp_bbox)):
                print(f"Skipping row with NaN values: frame {row['frame_nmr']}, car {row['car_id']}")
                continue
                
            valid_data.append(row)
            
        except (ValueError, TypeError, IndexError) as e:
            print(f"Skipping invalid row: {e}")
            continue
    
    if not valid_data:
        print("No valid data found for interpolation")
        return []
    
    print(f"Processing {len(valid_data)} valid rows out of {len(data)} total rows")
    
    # Extract necessary data columns from valid data only
    frame_numbers = np.array([int(float(row['frame_nmr'])) for row in valid_data])
    car_ids = np.array([int(float(row['car_id'])) for row in valid_data])
    car_bboxes = np.array([list(map(float, row['car_bbox'][1:-1].split())) for row in valid_data])
    license_plate_bboxes = np.array([list(map(float, row['license_plate_bbox'][1:-1].split())) for row in valid_data])

    interpolated_data = []
    unique_car_ids = np.unique(car_ids)
    
    for car_id in unique_car_ids:
        try:
            frame_numbers_ = [p['frame_nmr'] for p in valid_data if int(float(p['car_id'])) == int(float(car_id))]
            print(f"Processing car {car_id} with frames: {frame_numbers_}")

            # Filter data for a specific car ID
            car_mask = car_ids == car_id
            car_frame_numbers = frame_numbers[car_mask]
            car_bboxes_car = car_bboxes[car_mask]
            license_plate_bboxes_car = license_plate_bboxes[car_mask]
            
            if len(car_frame_numbers) < 2:
                print(f"Skipping car {car_id}: insufficient data points ({len(car_frame_numbers)})")
                continue
            
            car_bboxes_interpolated = []
            license_plate_bboxes_interpolated = []

            first_frame_number = car_frame_numbers[0]
            last_frame_number = car_frame_numbers[-1]

            for i in range(len(car_bboxes_car)):
                frame_number = car_frame_numbers[i]
                car_bbox = car_bboxes_car[i]
                license_plate_bbox = license_plate_bboxes_car[i]

                if i > 0:
                    prev_frame_number = car_frame_numbers[i-1]
                    prev_car_bbox = car_bboxes_interpolated[-1]
                    prev_license_plate_bbox = license_plate_bboxes_interpolated[-1]

                    if frame_number - prev_frame_number > 1:
                        # Interpolate missing frames' bounding boxes
                        frames_gap = frame_number - prev_frame_number
                        x = np.array([prev_frame_number, frame_number])
                        x_new = np.linspace(prev_frame_number, frame_number, num=frames_gap, endpoint=False)
                        
                        # Car bbox interpolation
                        interp_func = interp1d(x, np.vstack((prev_car_bbox, car_bbox)), axis=0, kind='linear')
                        interpolated_car_bboxes = interp_func(x_new)
                        
                        # License plate bbox interpolation
                        interp_func = interp1d(x, np.vstack((prev_license_plate_bbox, license_plate_bbox)), axis=0, kind='linear')
                        interpolated_license_plate_bboxes = interp_func(x_new)

                        car_bboxes_interpolated.extend(interpolated_car_bboxes[1:])
                        license_plate_bboxes_interpolated.extend(interpolated_license_plate_bboxes[1:])

                car_bboxes_interpolated.append(car_bbox)
                license_plate_bboxes_interpolated.append(license_plate_bbox)

            # Create interpolated records
            for i in range(len(car_bboxes_interpolated)):
                try:
                    frame_number = first_frame_number + i
                    
                    # Check for NaN in interpolated coordinates
                    car_coords = car_bboxes_interpolated[i]
                    lp_coords = license_plate_bboxes_interpolated[i]
                    
                    if (any(np.isnan(coord) for coord in car_coords) or 
                        any(np.isnan(coord) for coord in lp_coords)):
                        print(f"Skipping frame {frame_number} for car {car_id}: NaN in interpolated coordinates")
                        continue
                    
                    row = {}
                    row['frame_nmr'] = str(int(frame_number))
                    row['car_id'] = str(int(car_id))
                    row['car_bbox'] = ' '.join([f"{coord:.2f}" for coord in car_coords])
                    row['license_plate_bbox'] = ' '.join([f"{coord:.2f}" for coord in lp_coords])

                    if str(int(frame_number)) not in frame_numbers_:
                        # Imputed row, set the following fields to '0'
                        row['license_plate_bbox_score'] = '0'
                        row['license_number'] = '0'
                        row['license_number_score'] = '0'
                    else:
                        # Original row, retrieve values from the input data if available
                        original_rows = [p for p in valid_data if 
                                       int(float(p['frame_nmr'])) == int(frame_number) and 
                                       int(float(p['car_id'])) == int(car_id)]
                        if original_rows:
                            original_row = original_rows[0]
                            row['license_plate_bbox_score'] = original_row.get('license_plate_bbox_score', '0')
                            row['license_number'] = original_row.get('license_number', '0')
                            row['license_number_score'] = original_row.get('license_number_score', '0')
                        else:
                            row['license_plate_bbox_score'] = '0'
                            row['license_number'] = '0'
                            row['license_number_score'] = '0'

                    interpolated_data.append(row)
                    
                except Exception as e:
                    print(f"Error processing frame {frame_number} for car {car_id}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error processing car {car_id}: {e}")
            continue

    return interpolated_data


def main():
    # Load the CSV file
    try:
        with open('test.csv', 'r') as file:
            reader = csv.DictReader(file)
            data = list(reader)
        print(f"Loaded {len(data)} rows from test.csv")
    except FileNotFoundError:
        print("Error: test.csv file not found")
        return
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return

    if not data:
        print("No data found in CSV file")
        return

    # Interpolate missing data
    interpolated_data = interpolate_bounding_boxes(data)

    if not interpolated_data:
        print("No interpolated data generated")
        return

    print(f"Generated {len(interpolated_data)} interpolated records")

    # Write updated data to a new CSV file
    header = ['frame_nmr', 'car_id', 'car_bbox', 'license_plate_bbox', 
              'license_plate_bbox_score', 'license_number', 'license_number_score']
    
    try:
        with open('test_interpolated.csv', 'w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=header)
            writer.writeheader()
            writer.writerows(interpolated_data)
        print("Successfully wrote interpolated data to test_interpolated.csv")
    except Exception as e:
        print(f"Error writing output file: {e}")


if __name__ == "__main__":
    main()