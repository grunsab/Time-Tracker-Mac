import sys
import os

# Add the src directory to the Python path
# This is necessary so that Python can find the modules in the src directory
# when running main.py from the root directory of the project.
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir) # This assumes main.py is in src/
sys.path.insert(0, project_root)

from src.ui.main_window import App
from src.database.database_handler import init_db #, get_active_goal, set_active_goal # Keep other imports if they were there
# from src.tracker.app_tracker import get_active_application_info # Assuming this was commented out or not present before minimal test
# from src.llm.llm_handler import get_llm_handler # Assuming this was commented out or not present before minimal test

def main():
    # Initialize database first
    try:
        init_db()
        print("Database initialized and tables created.")
    except Exception as e:
        print(f"Critical error initializing database: {e}")
        sys.exit(1) # Exit if DB can't be set up

    app = App()
    app.mainloop()

if __name__ == '__main__':
    main() 