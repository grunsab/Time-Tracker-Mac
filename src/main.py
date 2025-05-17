import sys
import os

# Add the src directory to the Python path
# This is necessary so that Python can find the modules in the src directory
# when running main.py from the root directory of the project.
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir) # This assumes main.py is in src/
sys.path.insert(0, project_root)

from src.ui.main_window import App

def main():
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main() 