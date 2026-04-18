"""
integration_multicamera.py

Safe integration wrapper for Multi-Camera Network Intelligence
This file prevents import errors and provides fallback functionality

Place this file in the same directory as a5.py
"""

def integrate_multicamera_network(app_instance):
    """
    Safely integrate multi-camera network into main application
    
    Args:
        app_instance: Instance of EnhancedLicensePlateRecognitionSystem
        
    Returns:
        bool: True if integration successful, False otherwise
    """
    try:
        print("🔄 Loading Multi-Camera Network Intelligence...")
        
        # Import required components
        from multi_camera_intelligence import (
            MultiCameraNetworkManager,
            MultiCameraNetworkGUI,
            VehicleJourney
        )
        
        # Initialize camera network manager
        app_instance.camera_network = MultiCameraNetworkManager()
        print("✅ Camera Network Manager initialized")
        
        # Add GUI to existing notebook
        app_instance.camera_network_gui = MultiCameraNetworkGUI(app_instance.notebook)
        print("✅ Camera Network GUI added")
        
        # Add method to register detections
        def register_detection(camera_id, license_plate, timestamp=None, 
                              vehicle_color=None, vehicle_type=None):
            """Register vehicle detection with camera network"""
            try:
                success, result = app_instance.camera_network.register_detection(
                    camera_id, license_plate, timestamp, vehicle_color, vehicle_type
                )
                
                if success and isinstance(result, VehicleJourney):
                    # Alert if suspicious
                    if result.suspicious_score >= 70:
                        msg = f"⚠️ SUSPICIOUS VEHICLE: {license_plate} (Score: {result.suspicious_score})"
                        app_instance.log_message(msg)
                        
                return success
            except Exception as e:
                print(f"Detection registration error: {e}")
                return False
        
        # Attach method to app instance
        app_instance.register_camera_detection = register_detection
        print("✅ Detection registration enabled")
        
        # Set default camera ID (can be changed when processing video)
        app_instance.current_camera_id = "CAM001"
        
        # Add helper method to set camera for current video
        def set_current_camera(camera_id):
            """Set which camera is processing current video"""
            app_instance.current_camera_id = camera_id
            print(f"📹 Current camera set to: {camera_id}")
        
        app_instance.set_current_camera = set_current_camera
        
        # Log success
        app_instance.log_message("✅ Multi-Camera Network Intelligence integrated successfully!")
        print("=" * 60)
        print("✅ MULTI-CAMERA NETWORK READY!")
        print("=" * 60)
        
        return True
        
    except ImportError as e:
        print(f"⚠️  Import Error: {e}")
        print("⚠️  Make sure 'multi_camera_intelligence.py' is in the same folder")
        app_instance.log_message("⚠️ Multi-Camera Network module not found")
        return False
        
    except AttributeError as e:
        print(f"⚠️  Attribute Error: {e}")
        print("⚠️  Make sure app has 'notebook' attribute")
        return False
        
    except Exception as e:
        print(f"❌ Multi-Camera Network integration failed: {e}")
        import traceback
        traceback.print_exc()
        
        if hasattr(app_instance, 'log_message'):
            app_instance.log_message(f"⚠️ Multi-Camera setup error: {str(e)}")
        
        return False


def add_multicamera_to_existing_app():
    """
    Instructions for adding to existing app
    
    Add this to your a5.py __init__ method (at the very end):
    
    # Multi-Camera Network Integration
    from integration_multicamera import integrate_multicamera_network
    integrate_multicamera_network(self)
    """
    pass


# Test function
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("MULTI-CAMERA NETWORK INTEGRATION TESTER")
    print("=" * 60)
    
    # Test if main module can be imported
    print("\n1. Testing if multi_camera_intelligence.py exists...")
    try:
        import multi_camera_intelligence
        print("   ✅ Module found!")
    except ImportError:
        print("   ❌ Module NOT found!")
        print("   Make sure 'multi_camera_intelligence.py' is in this folder")
        exit(1)
    
    # Test if components can be imported
    print("\n2. Testing component imports...")
    try:
        from multi_camera_intelligence import (
            MultiCameraNetworkManager,
            MultiCameraNetworkGUI,
            VehicleJourney,
            CameraNode
        )
        print("   ✅ All components imported successfully!")
    except ImportError as e:
        print(f"   ❌ Component import failed: {e}")
        exit(1)
    
    # Test manager creation
    print("\n3. Testing manager creation...")
    try:
        manager = MultiCameraNetworkManager()
        print("   ✅ Manager created successfully!")
        
        # Test adding a camera
        success, msg = manager.add_camera("TEST001", "Test Camera", "Test Location", (0, 0))
        if success:
            print("   ✅ Can add cameras!")
        else:
            print(f"   ⚠️  Camera add returned: {msg}")
            
    except Exception as e:
        print(f"   ❌ Manager creation failed: {e}")
        exit(1)
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print("\nYou can now integrate with a5.py:")
    print("\n  1. Make sure all files are in the same folder:")
    print("     - a5.py")
    print("     - multi_camera_intelligence.py")
    print("     - integration_multicamera.py")
    print("\n  2. Add to a5.py at the END of __init__ method:")
    print("     from integration_multicamera import integrate_multicamera_network")
    print("     integrate_multicamera_network(self)")
    print("\n  3. Run your main application: python a5.py")
    print("\n" + "=" * 60 + "\n")