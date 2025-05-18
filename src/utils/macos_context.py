import ScriptingBridge
import os

def get_safari_url():
    """Gets the URL of the frontmost tab in Safari."""
    try:
        safari = ScriptingBridge.SBApplication.applicationWithBundleIdentifier_("com.apple.Safari")
        if safari.isRunning() and safari.windows() and len(safari.windows()) > 0:
            # Ensure there's a window and it has a current tab with a URL
            if safari.windows()[0].currentTab() and safari.windows()[0].currentTab().URL():
                return safari.windows()[0].currentTab().URL()
    except Exception as e:
        print(f"Error getting Safari URL: {e}")
    return None

def get_chrome_url():
    """Gets the URL of the frontmost tab in Google Chrome."""
    try:
        chrome = ScriptingBridge.SBApplication.applicationWithBundleIdentifier_("com.google.Chrome")
        if chrome.isRunning() and chrome.windows() and len(chrome.windows()) > 0:
            # Ensure there's a window and it has an active tab with a URL
            active_tab = chrome.windows()[0].activeTab()
            if active_tab and active_tab.URL():
                return active_tab.URL()
    except Exception as e:
        print(f"Error getting Chrome URL: {e}")
    return None

def get_preview_document_path():
    """Gets the path of the frontmost document in Preview."""
    try:
        preview = ScriptingBridge.SBApplication.applicationWithBundleIdentifier_("com.apple.Preview")
        if preview.isRunning() and preview.documents() and len(preview.documents()) > 0:
            # Documents in Preview have a 'path' attribute
            doc_path = preview.documents()[0].path()
            if doc_path:
                return os.path.normpath(doc_path) # Normalize to clean up 'file://localhost'
    except Exception as e:
        # Preview might use 'file' instead of 'path' for some versions/docs, or other errors
        print(f"Error getting Preview document path (attempt 1): {e}")
        # Fallback or alternative method if needed based on AppleScript dictionary for Preview
        # For now, we just print the error. A more robust solution might try alternative AppleScript commands.
    return None

def get_textedit_document_path():
    """Gets the path of the frontmost document in TextEdit."""
    try:
        textedit = ScriptingBridge.SBApplication.applicationWithBundleIdentifier_("com.apple.TextEdit")
        if textedit.isRunning() and textedit.documents() and len(textedit.documents()) > 0:
            # TextEdit documents usually have a 'path' attribute
            doc_path = textedit.documents()[0].path()
            if doc_path:
                 return os.path.normpath(doc_path)
    except Exception as e:
        print(f"Error getting TextEdit document path: {e}")
    return None

# Example usage (for testing this module directly)
if __name__ == '__main__':
    print("Attempting to get context from active applications...")
    
    safari_url = get_safari_url()
    if safari_url:
        print(f"Current Safari URL: {safari_url}")
    else:
        print("Safari not running or no URL found.")

    chrome_url = get_chrome_url()
    if chrome_url:
        print(f"Current Chrome URL: {chrome_url}")
    else:
        print("Chrome not running or no URL found.")

    preview_path = get_preview_document_path()
    if preview_path:
        print(f"Current Preview document: {preview_path}")
    else:
        print("Preview not running or no document found.")

    textedit_path = get_textedit_document_path()
    if textedit_path:
        print(f"Current TextEdit document: {textedit_path}")
    else:
        print("TextEdit not running or no document found.") 