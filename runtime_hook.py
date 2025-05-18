import os
import sys

# sys.executable is .../YourApp.app/Contents/MacOS/YourApp
exe_dir = os.path.dirname(sys.executable)

# Path to the dylib, now expected in Contents/MacOS
dylib_path = os.path.join(exe_dir, 'libpython3.9.dylib')

# Path to the Frameworks directory
# exe_dir is Contents/MacOS, so .. takes us to Contents/
frameworks_dir = os.path.join(exe_dir, '..', 'Frameworks')

# Desired symlink path within Frameworks
symlink_path = os.path.join(frameworks_dir, 'Python3')

# Relative path from Frameworks/Python3 to MacOS/libpython3.9.dylib
# This should resolve to '../MacOS/libpython3.9.dylib'
symlink_target = os.path.relpath(dylib_path, frameworks_dir)


# Ensure Frameworks directory exists
if not os.path.exists(frameworks_dir):
    try:
        os.makedirs(frameworks_dir)
        print(f"[Runtime Hook] Created directory: {frameworks_dir}")
    except Exception as e:
        print(f"[Runtime Hook] Error creating directory {frameworks_dir}: {e}")
        # If we can't create Frameworks dir, we probably can't make the symlink
        sys.exit(1) # Or handle error appropriately

# Create the symlink if the dylib exists and the symlink doesn't
if os.path.exists(dylib_path):
    if not os.path.lexists(symlink_path):
        try:
            os.symlink(symlink_target, symlink_path)
            print(f"[Runtime Hook] Created symlink: {symlink_path} -> {symlink_target}")
        except Exception as e:
            print(f"[Runtime Hook] Error creating symlink {symlink_path}: {e}")
    else:
        print(f"[Runtime Hook] Info: Symlink already exists at {symlink_path}")
else:
    print(f"[Runtime Hook] Error: Dylib not found at {dylib_path}") 