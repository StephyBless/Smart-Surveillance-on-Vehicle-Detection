import pandas as pd
import ast
from difflib import SequenceMatcher


def similarity(a, b):
    """Calculate similarity between two strings"""
    return SequenceMatcher(None, a.upper(), b.upper()).ratio()


def search_license_plate(csv_file_path, target_plate=None, similarity_threshold=0.8):
    """
    Search for a target license plate in the processed CSV file
    
    Args:
        csv_file_path (str): Path to the CSV file containing license plate data
        target_plate (str): Target license plate to search for
        similarity_threshold (float): Minimum similarity score for fuzzy matching
    
    Returns:
        dict: Search results with details
    """
    try:
        # Read the CSV file
        df = pd.read_csv(csv_file_path)
        
        # Display available license plates
        print("\n" + "="*60)
        print("LICENSE PLATE SEARCH SYSTEM")
        print("="*60)
        
        # Get unique license plates (excluding '0' which represents missing data)
        valid_plates = df[df['license_number'] != '0']['license_number'].unique()
        
        print(f"\nFound {len(valid_plates)} unique license plates in the system:")
        print("-" * 40)
        for i, plate in enumerate(valid_plates, 1):
            plate_count = len(df[df['license_number'] == plate])
            print(f"{i:2d}. {plate} (appears in {plate_count} frames)")
        
        # If no target plate specified, ask user
        if target_plate is None:
            print("\n" + "-"*40)
            target_plate = input("Enter the license plate number you want to search for: ").strip().upper()
        
        if not target_plate:
            print("No license plate entered. Exiting search.")
            return None
        
        print(f"\nSearching for license plate: {target_plate}")
        print("-" * 40)
        
        # Exact match search
        exact_matches = df[df['license_number'].str.upper() == target_plate.upper()]
        
        search_results = {
            'target_plate': target_plate,
            'exact_matches': [],
            'fuzzy_matches': [],
            'summary': {}
        }
        
        if not exact_matches.empty:
            print(f"✅ EXACT MATCH FOUND!")
            print(f"License plate '{target_plate}' found in {len(exact_matches)} frames")
            
            # Get details for exact matches
            for idx, row in exact_matches.iterrows():
                frame_details = {
                    'frame_number': int(row['frame_nmr']),
                    'car_id': int(float(row['car_id'])),
                    'car_bbox': ast.literal_eval(row['car_bbox'].replace('[ ', '[').replace('   ', ' ').replace('  ', ' ').replace(' ', ',')),
                    'license_plate_bbox': ast.literal_eval(row['license_plate_bbox'].replace('[ ', '[').replace('   ', ' ').replace('  ', ' ').replace(' ', ',')),
                    'license_plate_score': float(row['license_plate_bbox_score']) if row['license_plate_bbox_score'] != '0' else 0.0,
                    'license_number_score': float(row['license_number_score']) if row['license_number_score'] != '0' else 0.0
                }
                search_results['exact_matches'].append(frame_details)
            
            # Display summary
            car_ids = exact_matches['car_id'].unique()
            frame_range = [int(exact_matches['frame_nmr'].min()), int(exact_matches['frame_nmr'].max())]
            avg_confidence = exact_matches[exact_matches['license_number_score'] != '0']['license_number_score'].astype(float).mean()
            
            print(f"\nDETAILS:")
            print(f"  • Car ID(s): {', '.join(map(str, [int(float(x)) for x in car_ids]))}")
            print(f"  • Frame range: {frame_range[0]} - {frame_range[1]}")
            print(f"  • Average confidence: {avg_confidence:.2f}")
            print(f"  • First appearance: Frame {frame_range[0]}")
            print(f"  • Last appearance: Frame {frame_range[1]}")
            
            # Find the frame with highest confidence
            if len(exact_matches[exact_matches['license_number_score'] != '0']) > 0:
                best_frame = exact_matches.loc[exact_matches[exact_matches['license_number_score'] != '0']['license_number_score'].astype(float).idxmax()]
                print(f"  • Best detection: Frame {int(best_frame['frame_nmr'])} (confidence: {float(best_frame['license_number_score']):.2f})")
            
            search_results['summary'] = {
                'found': True,
                'match_type': 'exact',
                'total_frames': len(exact_matches),
                'car_ids': [int(float(x)) for x in car_ids],
                'frame_range': frame_range,
                'average_confidence': avg_confidence,
                'best_frame': int(best_frame['frame_nmr']) if len(exact_matches[exact_matches['license_number_score'] != '0']) > 0 else frame_range[0]
            }
            
        else:
            print(f"❌ No exact match found for '{target_plate}'")
            
            # Fuzzy matching
            print(f"\n🔍 Searching for similar license plates...")
            fuzzy_matches = []
            
            for plate in valid_plates:
                sim_score = similarity(target_plate, plate)
                if sim_score >= similarity_threshold:
                    fuzzy_matches.append((plate, sim_score))
            
            if fuzzy_matches:
                fuzzy_matches.sort(key=lambda x: x[1], reverse=True)
                print(f"Found {len(fuzzy_matches)} similar license plate(s):")
                
                for plate, score in fuzzy_matches:
                    plate_data = df[df['license_number'] == plate]
                    frame_count = len(plate_data)
                    car_id = int(float(plate_data.iloc[0]['car_id']))
                    
                    print(f"  • {plate} (similarity: {score:.2f}, {frame_count} frames, car ID: {car_id})")
                    
                    # Store fuzzy match details
                    fuzzy_details = {
                        'license_plate': plate,
                        'similarity_score': score,
                        'frame_count': frame_count,
                        'car_id': car_id,
                        'frames': []
                    }
                    
                    for idx, row in plate_data.iterrows():
                        frame_details = {
                            'frame_number': int(row['frame_nmr']),
                            'car_bbox': ast.literal_eval(row['car_bbox'].replace('[ ', '[').replace('   ', ' ').replace('  ', ' ').replace(' ', ',')),
                            'license_plate_bbox': ast.literal_eval(row['license_plate_bbox'].replace('[ ', '[').replace('   ', ' ').replace('  ', ' ').replace(' ', ',')),
                            'license_number_score': float(row['license_number_score']) if row['license_number_score'] != '0' else 0.0
                        }
                        fuzzy_details['frames'].append(frame_details)
                    
                    search_results['fuzzy_matches'].append(fuzzy_details)
                
                search_results['summary'] = {
                    'found': True,
                    'match_type': 'fuzzy',
                    'total_similar': len(fuzzy_matches),
                    'best_match': fuzzy_matches[0][0],
                    'best_similarity': fuzzy_matches[0][1]
                }
            else:
                print(f"No similar license plates found (threshold: {similarity_threshold})")
                search_results['summary'] = {
                    'found': False,
                    'match_type': 'none'
                }
        
        return search_results
        
    except FileNotFoundError:
        print(f"Error: CSV file '{csv_file_path}' not found.")
        return None
    except Exception as e:
        print(f"Error occurred during search: {str(e)}")
        return None


def interactive_search_menu(csv_file_path):
    """
    Interactive menu for license plate search
    """
    while True:
        print("\n" + "="*60)
        print("LICENSE PLATE SEARCH MENU")
        print("="*60)
        print("1. Search for a specific license plate")
        print("2. View all license plates")
        print("3. Search with custom similarity threshold")
        print("4. Exit")
        
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == '1':
            search_license_plate(csv_file_path)
        
        elif choice == '2':
            try:
                df = pd.read_csv(csv_file_path)
                valid_plates = df[df['license_number'] != '0']['license_number'].unique()
                
                print(f"\nAll detected license plates ({len(valid_plates)} unique):")
                print("-" * 50)
                for i, plate in enumerate(valid_plates, 1):
                    plate_data = df[df['license_number'] == plate]
                    frame_count = len(plate_data)
                    car_ids = plate_data['car_id'].unique()
                    avg_score = plate_data[plate_data['license_number_score'] != '0']['license_number_score'].astype(float).mean()
                    
                    print(f"{i:2d}. {plate}")
                    print(f"    └─ Frames: {frame_count}, Car ID(s): {', '.join(map(str, [int(float(x)) for x in car_ids]))}, Avg Score: {avg_score:.2f}")
                
            except Exception as e:
                print(f"Error reading CSV file: {str(e)}")
        
        elif choice == '3':
            try:
                threshold = float(input("Enter similarity threshold (0.0 - 1.0): "))
                if 0.0 <= threshold <= 1.0:
                    target = input("Enter target license plate: ").strip()
                    search_license_plate(csv_file_path, target, threshold)
                else:
                    print("Invalid threshold. Please enter a value between 0.0 and 1.0")
            except ValueError:
                print("Invalid input. Please enter a valid number.")
        
        elif choice == '4':
            print("Exiting search system. Goodbye!")
            break
        
        else:
            print("Invalid choice. Please enter 1, 2, 3, or 4.")


# Example usage
if __name__ == "__main__":
    # Assuming the CSV file is generated by your main processing pipeline
    csv_file = "./test_interpolated.csv"  # or "./test.csv" if using the original
    
    print("License Plate Recognition System - Search Module")
    print("Make sure you have run the main processing pipeline first to generate the CSV file.")
    
    # Start interactive search
    interactive_search_menu(csv_file)