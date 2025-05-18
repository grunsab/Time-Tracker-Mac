import os
import tempfile
from typing import Optional # Add Optional for type hinting
from AppKit import NSWorkspace, NSBitmapImageRep, NSPNGFileType
from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGWindowListExcludeDesktopElements, kCGNullWindowID, CGWindowListCreateImage, CGRectMake, CGRectNull, CGMainDisplayID, CGDisplayPixelsWide, CGDisplayPixelsHigh
from Quartz import kCGWindowImageDefault # Explicitly import if not covered by above
# Attempt to get kCGWindowListOptionIncludingWindow if not directly available
from Quartz.CoreGraphics import kCGWindowListOptionIncludingWindow 

from PIL import Image # For potential fallback or direct saving if NSBitmapImageRep is tricky

# Ensure the .cache directory exists at the project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCREENSHOT_TEMP_DIR = os.path.join(PROJECT_ROOT, ".cache", "screenshots")
os.makedirs(SCREENSHOT_TEMP_DIR, exist_ok=True)

def capture_active_window_to_temp_file() -> Optional[str]:
    """
    Captures the active application's main window on macOS and saves it to a temporary PNG file.

    Returns:
        Optional[str]: The path to the saved screenshot file if successful, None otherwise.
    """
    workspace = NSWorkspace.sharedWorkspace()
    active_app = workspace.frontmostApplication()
    if not active_app:
        print("Screenshot Error: No active application found.")
        return None

    active_app_pid = active_app.processIdentifier()
    window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements, kCGNullWindowID)

    active_window_id = None
    active_window_bounds = None

    # Heuristic: Find the most suitable window.
    # This might need refinement for apps with many windows or unusual windowing behavior.
    # We look for an on-screen window belonging to the active app, with a name, and ideally the main one.
    # Often, the first one that meets these criteria and is on layer 0 is a good candidate.
    
    # Screen dimensions, for sanity check on window bounds if needed
    main_display_id = CGMainDisplayID()
    display_width = CGDisplayPixelsWide(main_display_id)
    display_height = CGDisplayPixelsHigh(main_display_id)

    candidate_windows = []
    for window_info in window_list:
        owner_pid = window_info.get('kCGWindowOwnerPID')
        window_layer = window_info.get('kCGWindowLayer')
        window_name = window_info.get('kCGWindowName')
        window_id = window_info.get('kCGWindowNumber')
        bounds_dict = window_info.get('kCGWindowBounds')

        # Relaxed condition: window_name is no longer strictly required to be non-empty.
        # We still prefer named windows if available, but will accept unnamed ones if they fit other criteria.
        if owner_pid == active_app_pid and window_layer == 0 and window_id:
            # Basic check: window should have some visible area on screen
            if bounds_dict['Width'] > 50 and bounds_dict['Height'] > 50: # Arbitrary minimum size
                 # Check if window is within screen bounds (simple check)
                if bounds_dict['X'] < display_width and bounds_dict['Y'] < display_height:
                    candidate_windows.append({
                        'id': window_id,
                        'bounds': bounds_dict,
                        'name': window_name,
                        'area': bounds_dict['Width'] * bounds_dict['Height']
                    })
    
    if not candidate_windows:
        print(f"Screenshot Error: No suitable window found for app {active_app.localizedName()} (PID: {active_app_pid}). Dumping all windows for this PID:")
        for window_info_debug in window_list:
            owner_pid_debug = window_info_debug.get('kCGWindowOwnerPID')
            if owner_pid_debug == active_app_pid:
                window_layer_debug = window_info_debug.get('kCGWindowLayer')
                window_name_debug = window_info_debug.get('kCGWindowName')
                window_id_debug = window_info_debug.get('kCGWindowNumber')
                bounds_dict_debug = window_info_debug.get('kCGWindowBounds')
                print(f"  - Window ID: {window_id_debug}, Name: '{window_name_debug}', Layer: {window_layer_debug}, Bounds: {bounds_dict_debug}")
        return None

    # This is a heuristic and might not always be correct.
    # Prioritize named windows if any candidates have names.
    named_candidates = [w for w in candidate_windows if w.get('name')]
    if named_candidates:
        best_candidate = max(named_candidates, key=lambda w: w['area'])
    elif candidate_windows: # If no named windows, take the largest of any unnamed (but otherwise valid) ones
        best_candidate = max(candidate_windows, key=lambda w: w['area'])
    else:
        # This case should ideally not be reached if the previous check (if not candidate_windows) is comprehensive
        print(f"Screenshot Error: No candidates found after filtering for app {active_app.localizedName()} (PID: {active_app_pid}). This shouldn't happen.")
        return None
        
    active_window_id = best_candidate['id']
    # print(f"Selected window '{best_candidate.get('name', 'Unnamed')}' (ID: {active_window_id}) for screenshot.")


    if active_window_id is None:
        print(f"Screenshot Error: Could not identify the active window for PID {active_app_pid}.")
        return None

    try:
        # Capture the specific window
        # The bounds parameter (second arg) for CGWindowListCreateImage can be:
        # - CGRectNull: Capture the entire window, including parts off-screen.
        # - Screen bounds: Capture only the on-screen portion of the window.
        # - Window bounds relative to screen: Also captures on-screen portion.
        # For simplicity and to get the full window content, we use CGRectNull.
        # The second argument to CGWindowListCreateImage is windowOption, previously kCGWindowListOptionIncludingWindow
        # Let's try with 0 (kCGWindowListOptionAll) or kCGWindowListOptionIncludingWindow (1 << 0) if available.
        # kCGWindowListOptionIncludingWindow (1) seems to be what we want to ensure we get the target window, not just what's on top of it.
        image_ref = CGWindowListCreateImage(CGRectNull, kCGWindowListOptionIncludingWindow, active_window_id, kCGWindowImageDefault) 
        
        if not image_ref:
            print(f"Screenshot Error: CGWindowListCreateImage failed for window ID {active_window_id}.")
            return None

        # Create a unique filename
        temp_fd, temp_image_path = tempfile.mkstemp(suffix=".png", prefix="active_window_", dir=SCREENSHOT_TEMP_DIR)
        os.close(temp_fd) # Close the file descriptor, we'll write to the path

        # Convert CGImage to NSBitmapImageRep and save as PNG
        # This is a more direct way using AppKit if CGImage is valid
        bitmap_rep = NSBitmapImageRep.alloc().initWithCGImage_(image_ref)
        if not bitmap_rep:
            print("Screenshot Error: Failed to create NSBitmapImageRep from CGImage.")
            # CGImageRelease(image_ref) # Core Foundation objects might need manual release if not ARC-managed by pyobjc
            return None
            
        png_data = bitmap_rep.representationUsingType_properties_(NSPNGFileType, None)
        
        if not png_data:
            print("Screenshot Error: Failed to get PNG representation from NSBitmapImageRep.")
            return None

        success = png_data.writeToFile_atomically_(temp_image_path, True)

        # Alternative saving using Pillow (more steps, but good fallback or for other formats)
        # width = CGImageGetWidth(image_ref)
        # height = CGImageGetHeight(image_ref)
        # provider = CGImageGetDataProvider(image_ref)
        # data = CGDataProviderCopyData(provider)
        # img = Image.frombytes("RGBA", (width, height), data, "raw", "BGRA")
        # img.save(temp_image_path, "PNG")
        # CGImageRelease(image_ref) # Important if using direct CoreGraphics data access

        if success:
            print(f"Screenshot of window ID {active_window_id} saved to {temp_image_path}")
            return temp_image_path
        else:
            print(f"Screenshot Error: Failed to write PNG data to file {temp_image_path}.")
            if os.path.exists(temp_image_path):
                os.remove(temp_image_path) # Clean up empty file
            return None

    except Exception as e:
        print(f"Screenshot Exception: An error occurred: {e}")
        # Clean up temp file if it exists and an error occurred
        if 'temp_image_path' in locals() and os.path.exists(temp_image_path):
            try:
                os.remove(temp_image_path)
            except OSError:
                pass # Ignore if removal fails
        return None

if __name__ == '__main__':
    print("Attempting to capture active window in 5 seconds...")
    import time
    time.sleep(5)
    
    # Make sure you have an application window active and frontmost when this runs.
    # For example, a Finder window, TextEdit, or your browser.
    # Avoid running it directly from a terminal that might immediately lose focus to the script itself.
    
    filepath = capture_active_window_to_temp_file()
    if filepath:
        print(f"SUCCESS: Screenshot saved to {filepath}")
        # You can open the file to verify:
        # import subprocess
        # subprocess.run(['open', filepath])
    else:
        print("FAILURE: Screenshot could not be captured.") 