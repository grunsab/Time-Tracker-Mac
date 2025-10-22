# Time Tracker Mac OS Application

A macOS application designed to help users track their productivity, understand their work patterns, and align their activities with their stated goals using a locally run Gemma3 language model.

## Features

-   **Application Tracking:** Monitors active applications and user activity within them.
-   **Goal Setting:** Allows users to define and manage their productivity goals.
-   **AI-Powered Analysis:** Utilizes a local Gemma3 model to analyze time usage against goals.
-   **Active Feedback:** Provides real-time feedback and suggestions to the user.
-   **Data Visualization:** (Future) Offers insights into work patterns through charts and summaries.

## Project Structure (Initial Thoughts)

-   `src/`: Main application source code.
    -   `main.py`: Application entry point.
    -   `tracker/`: Modules for tracking application and window activity.
    -   `ui/`: Modules for the user interface (e.g., using PyQt, Tkinter, or SwiftUI via Python bridges).
    -   `llm/`: Modules for interacting with the local Gemma3 model.
    -   `database/`: Modules for data storage (e.g., SQLite).
-   `models/`: Directory for storing the local Gemma3 model (or configuration for it).
-   `requirements.txt`: Python dependencies.
-   `run.sh`: (Optional) Script to easily run the application.

## Technology Stack (Proposed)

-   **Language:** Python
-   **GUI:** PyQt6, CustomTkinter, or another Python GUI framework.
-   **LLM:** Gemma3 (via Hugging Face Transformers, Ollama, or similar)
-   **macOS Integration:** `pyobjc` or AppleScript for application tracking.
-   **Database:** SQLite

## Development Setup

(To be detailed later)

```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Further instructions for running the app
python src/main.py
```

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).
