from AppKit import NSWorkspace, NSRunningApplication
from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID, kCGWindowName
import time
import subprocess
import shlex # For safely formatting commands

# Bundle Identifiers for common applications
BUNDLE_ID_SAFARI = "com.apple.Safari"
BUNDLE_ID_CHROME = "com.google.Chrome"
BUNDLE_ID_FIREFOX = "org.mozilla.firefox"
BUNDLE_ID_EDGE = "com.microsoft.Edge"
BUNDLE_ID_TEXTEDIT = "com.apple.TextEdit"
BUNDLE_ID_PREVIEW = "com.apple.Preview"
BUNDLE_ID_VSCODE = "com.microsoft.VSCode"
# Add more as needed: Keynote, Pages, Numbers, Word, Excel, PowerPoint, etc.

def run_applescript(script: str):
    """Executes an AppleScript string and returns its output or None on error."""
    try:
        # Using osascript -e for direct execution
        # Ensure script is properly escaped if it contains complex quotes, though shlex helps.
        # For multiline scripts, passing as separate args to osascript might be better or using a temp file.
        # Here, we assume simple, one-line equivalent commands passed via -e.
        process = subprocess.Popen(['osascript', '-e', script], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE,
                                   text=True)
        stdout, stderr = process.communicate(timeout=2) # 2-second timeout
        if process.returncode == 0 and stdout:
            return stdout.strip()
        elif stderr:
            # print(f"AppleScript Error for script '{script[:50]}...': {stderr.strip()}") # Can be noisy
            pass
        return None
    except subprocess.TimeoutExpired:
        # print(f"AppleScript timed out for script '{script[:50]}...'")
        return None
    except Exception as e:
        # print(f"Exception running AppleScript '{script[:50]}...': {e}")
        return None

def get_safari_url():
    script = 'tell application "Safari" to get URL of front document'
    return run_applescript(script)

def get_chrome_url():
    script = 'tell application "Google Chrome" to get URL of active tab of front window'
    return run_applescript(script)

def get_firefox_url(): # Firefox can be tricky, often needs accessibility or command line flags
    # A common AppleScript that might work if Firefox is receptive:
    script = 'tell application "Firefox" to activate tell application "System Events" to keystroke "l" using command down tell application "System Events" to keystroke "c" using command down delay 0.5 end tell tell application "Firefox" to get the clipboard'
    # This is highly unreliable and invasive (uses clipboard). A better method would be browser extensions or specific command-line tools if Firefox supports them.
    # For now, returning None as a placeholder for a more robust solution.
    # print("Firefox URL retrieval is complex and not reliably implemented via basic AppleScript.")
    return None # Placeholder

def get_edge_url():
    script = 'tell application "Microsoft Edge" to get URL of active tab of front window'
    return run_applescript(script)

def get_document_path_generic(app_name: str):
    """Attempts to get the document path for common document-based apps."""
    # This script works for many apps that follow standard AppleScript document handling
    script = f'tell application "{app_name}" to get path of front document'
    return run_applescript(script)

def get_vscode_document_path():
    # VSCode has more complex window/document handling for AppleScript
    # This might get the path of the workspace or the frontmost file, results can vary.
    # A more robust solution might involve VSCode-specific commands or extensions.
    script = 'tell application "Visual Studio Code" to get path of active text editor of front window'
    # Fallback or alternative if the above doesn't work well:
    # script = 'tell application "Visual Studio Code" to get path of front document' 
    return run_applescript(script)

def get_active_window_title():
    """
    Attempts to get the window title of the frontmost application.
    Note: This might require accessibility permissions for the application.
    """
    try:
        window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
        for window in window_list:
            # Check if the window belongs to the frontmost application
            # This is a heuristic: check if the window is the frontmost one with a name and owned by an active app.
            # NSWorkspace.sharedWorkspace().frontmostApplication() can give the PID.
            # window.get('kCGWindowOwnerPID') can be compared.
            
            # A simpler heuristic for now: find the first window with a name that is likely on top.
            # More robust checking would involve matching PID of frontmost app.
            if window.get('kCGWindowLayer') == 0: # Main window layer
                owner_pid = window.get('kCGWindowOwnerPID')
                front_app_pid = NSWorkspace.sharedWorkspace().frontmostApplication().processIdentifier()
                if owner_pid == front_app_pid:
                    window_title = window.get('kCGWindowName', None)
                    if window_title:
                        return str(window_title)
        return None
    except Exception as e:
        # print(f"Error getting window title: {e}") # Can be noisy
        return None

def get_active_application_info():
    """
    Gets information about the currently active application on macOS,
    including window title and specific context like URL or document path if available.
    """
    workspace = NSWorkspace.sharedWorkspace()
    active_app_ns = workspace.frontmostApplication()

    if active_app_ns:
        app_name = active_app_ns.localizedName()
        bundle_id = active_app_ns.bundleIdentifier()
        window_title = get_active_window_title() or "N/A"
        detailed_context = None # URL or document path

        if bundle_id == BUNDLE_ID_SAFARI:
            detailed_context = get_safari_url()
        elif bundle_id == BUNDLE_ID_CHROME:
            detailed_context = get_chrome_url()
        elif bundle_id == BUNDLE_ID_EDGE:
            detailed_context = get_edge_url()
        elif bundle_id == BUNDLE_ID_FIREFOX:
            detailed_context = get_firefox_url() # Placeholder, likely returns None
        elif bundle_id == BUNDLE_ID_VSCODE:
            detailed_context = get_vscode_document_path()
            if not detailed_context: # Fallback for VSCode if specific editor path fails
                 detailed_context = get_document_path_generic(app_name)
        elif bundle_id in [BUNDLE_ID_TEXTEDIT, BUNDLE_ID_PREVIEW]:
            # For Preview and TextEdit, and potentially other simple document apps
            detailed_context = get_document_path_generic(app_name)
        # Add more app-specific handlers here if needed
        # e.g., for Microsoft Office, Adobe suite, etc., if standard AppleScript works.
        
        return {
            "name": app_name,
            "bundle_identifier": bundle_id,
            "window_title": window_title,
            "detailed_context": detailed_context or "N/A" # Ensure it's not None for dictionary
        }
    return None

def get_running_applications_info():
    """
    Gets information about all currently running applications on macOS.

    Returns:
        list: A list of dictionaries, where each dictionary contains
              the name and bundle identifier of a running application.
    """
    workspace = NSWorkspace.sharedWorkspace()
    running_apps = workspace.runningApplications()
    apps_info = []
    for app in running_apps:
        if app.activationPolicy() == 0: # Regular application
            apps_info.append({
                "name": app.localizedName(),
                "bundle_identifier": app.bundleIdentifier(),
            })
    return apps_info

if __name__ == "__main__":
    print("Tracking active application, window, and detailed context (updates every 5 secs). Ctrl+C to stop.")
    try:
        while True:
            active_app_info = get_active_application_info()
            if active_app_info:
                print(f"Active App: {active_app_info['name']} ({active_app_info['bundle_identifier']})\n  Window: {active_app_info['window_title']}\n  Context: {active_app_info['detailed_context']}")
            else:
                print("No active application found.")
            print("---")
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nTracker stopped.") 