import customtkinter as ctk
from tkinter import messagebox # For simple dialogs
import datetime # Added for date calculations
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from src.tracker.app_tracker import get_active_application_info
from src.llm.llm_handler import get_llm_handler
from src.database.database_handler import (
    init_db, add_project, get_all_projects, get_project_by_id,
    add_goal, get_goals_for_project, set_active_goal, get_active_goal, complete_goal, Goal, get_goal_by_id,
    add_activity_log, get_aggregated_activity_by_app # Import new function
)
from src.utils.screenshot_utils import capture_active_window_to_temp_file # Import for screenshot
import threading
import time
import os

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        try:
            init_db()
            print("Database initialized successfully from App.")
        except Exception as e:
            messagebox.showerror("Database Error", f"Database initialization failed: {e}\nApplication might not work correctly.")
            # Potentially exit or disable DB-dependent features

        self.title("Productivity Tracker")
        self.geometry("750x900") # Adjusted size for tabs and potentially more content

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        # --- Main Layout Frames ---
        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.pack(pady=10, padx=10, fill="x")

        # --- Top Frame: Active App Info ---
        self.active_app_label = ctk.CTkLabel(self.top_frame, text="App: Fetching...", font=ctk.CTkFont(size=14))
        self.active_app_label.pack(pady=(5,0))
        self.active_window_label = ctk.CTkLabel(self.top_frame, text="Window: ...", font=ctk.CTkFont(size=12))
        self.active_window_label.pack(pady=(0,0))
        self.detailed_context_label = ctk.CTkLabel(self.top_frame, text="Context: ...", font=ctk.CTkFont(size=10), wraplength=700) # Adjusted wraplength
        self.detailed_context_label.pack(pady=(0,5))

        # Screenshot Analysis Button
        self.analyze_window_button = ctk.CTkButton(self.top_frame, text="Analyze Window Content (Screenshot)", command=self.analyze_window_content_action)
        self.analyze_window_button.pack(pady=5)

        # --- Tab View ---
        # TabView will now hold Dashboard, Goals, and Feedback sections.
        # It should expand to fill most of the window.
        self.tab_view = ctk.CTkTabview(self) # Removed fixed height
        self.tab_view.pack(pady=10, padx=10, fill="both", expand=True) # expand=True now for tab_view

        self.dashboard_tab = self.tab_view.add("Dashboard")
        self.goals_tab = self.tab_view.add("Goals")
        self.feedback_tab = self.tab_view.add("Feedback") # New Feedback Tab
        self.visualizations_tab = self.tab_view.add("Visualizations") # New Visualizations Tab

        self.tab_view.set("Dashboard") # Default to Dashboard, or change to "Feedback"

        # self.bottom_frame is NO LONGER USED as a main packed frame.
        # Its content will move into self.feedback_tab.

        # --- Dashboard Tab Content ---
        self.dashboard_content_frame = ctk.CTkFrame(self.dashboard_tab) # Create a new frame for dashboard content
        self.dashboard_content_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.dashboard_content_frame.grid_columnconfigure(0, weight=1)
        self.dashboard_content_frame.grid_columnconfigure(1, weight=2) # Give more space to goals list

        # --- Dashboard: Left - Projects & New Goal ---
        self.project_controls_frame = ctk.CTkFrame(self.dashboard_content_frame) # Parent is now dashboard_content_frame
        self.project_controls_frame.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="nsew")

        ctk.CTkLabel(self.project_controls_frame, text="Projects", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        self.project_selector = ctk.CTkComboBox(self.project_controls_frame, values=["Loading..."], command=self.on_project_selected, width=200)
        self.project_selector.pack(pady=5)
        
        self.new_project_entry = ctk.CTkEntry(self.project_controls_frame, placeholder_text="New Project Name", width=200)
        self.new_project_entry.pack(pady=5)
        self.add_project_button = ctk.CTkButton(self.project_controls_frame, text="Create Project", command=self.create_project_action)
        self.add_project_button.pack(pady=5)

        ctk.CTkLabel(self.project_controls_frame, text="Add New Goal", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(20,5))
        self.new_goal_entry = ctk.CTkEntry(self.project_controls_frame, placeholder_text="New Goal for Selected Project", width=200)
        self.new_goal_entry.pack(pady=5)
        self.add_goal_button = ctk.CTkButton(self.project_controls_frame, text="Add Goal to Project", command=self.add_goal_action)
        self.add_goal_button.pack(pady=5)
        
        # --- Dashboard: Right - Goals List for Selected Project ---
        self.goals_display_frame = ctk.CTkFrame(self.dashboard_content_frame) # Parent is now dashboard_content_frame
        self.goals_display_frame.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="nsew")
        
        ctk.CTkLabel(self.goals_display_frame, text="Project Goals", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        self.current_project_label = ctk.CTkLabel(self.goals_display_frame, text="Selected Project: None", font=ctk.CTkFont(size=12))
        self.current_project_label.pack(pady=5)
        self.goals_list_frame = ctk.CTkScrollableFrame(self.goals_display_frame, height=350) # Consider adjusting height dynamically
        self.goals_list_frame.pack(pady=5, padx=5, fill="both", expand=True)

        # --- Goals Tab Content ---
        self.goals_tab_content_frame = ctk.CTkFrame(self.goals_tab)
        self.goals_tab_content_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.goals_tab_content_frame.grid_columnconfigure(0, weight=1) # For filter controls
        self.goals_tab_content_frame.grid_columnconfigure(1, weight=3) # For goal list

        # Filters for Goals Tab
        self.goals_tab_filter_frame = ctk.CTkFrame(self.goals_tab_content_frame)
        self.goals_tab_filter_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        
        ctk.CTkLabel(self.goals_tab_filter_frame, text="Filter by Project:").pack(side="left", padx=(5,2))
        self.goals_tab_project_filter_var = ctk.StringVar(value="All Projects")
        self.goals_tab_project_filter_combo = ctk.CTkComboBox(self.goals_tab_filter_frame, 
                                                              values=["All Projects"], 
                                                              variable=self.goals_tab_project_filter_var,
                                                              command=self.refresh_goals_tab_display)
        self.goals_tab_project_filter_combo.pack(side="left", padx=(0,10))

        ctk.CTkLabel(self.goals_tab_filter_frame, text="Filter by Status:").pack(side="left", padx=(10,2))
        self.goals_tab_status_options = ["All", "Pending", "Active", "Completed"]
        self.goals_tab_status_filter_var = ctk.StringVar(value="All")
        self.goals_tab_status_filter_combo = ctk.CTkComboBox(self.goals_tab_filter_frame, 
                                                             values=self.goals_tab_status_options, 
                                                             variable=self.goals_tab_status_filter_var,
                                                             command=self.refresh_goals_tab_display)
        self.goals_tab_status_filter_combo.pack(side="left", padx=(0,5))
        
        self.refresh_goals_tab_filters_button = ctk.CTkButton(self.goals_tab_filter_frame, text="Refresh Filters", command=self.populate_goals_tab_project_filter)
        self.refresh_goals_tab_filters_button.pack(side="left", padx=(10,5))


        # Scrollable list for all goals
        self.all_goals_list_scrollable_frame = ctk.CTkScrollableFrame(self.goals_tab_content_frame)
        self.all_goals_list_scrollable_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        self.goals_tab_content_frame.grid_rowconfigure(1, weight=1) # Ensure the list expands


        # --- Feedback Tab Content (Previously bottom_frame content) ---
        self.feedback_tab_content_frame = ctk.CTkFrame(self.feedback_tab, fg_color="transparent")
        self.feedback_tab_content_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.active_goal_display_label = ctk.CTkLabel(self.feedback_tab_content_frame, text="Active Goal for Feedback: None", font=ctk.CTkFont(size=12, weight="bold"), wraplength=730)
        self.active_goal_display_label.pack(pady=5, fill="x")

        self.feedback_controls_frame = ctk.CTkFrame(self.feedback_tab_content_frame)
        self.feedback_controls_frame.pack(pady=5, fill="x")

        ctk.CTkLabel(self.feedback_controls_frame, text="Freq:").pack(side="left", padx=(10,5))
        self.feedback_frequency_options = ["Off", "15s", "30s", "1m", "2m", "5m"]
        self.feedback_frequency_map = {"Off": 0, "15s": 15, "30s": 30, "1m": 60, "2m": 120, "5m": 300}
        self.feedback_frequency_var = ctk.StringVar(value="30s")
        self.feedback_frequency_menu = ctk.CTkOptionMenu(self.feedback_controls_frame, 
                                                       values=self.feedback_frequency_options, 
                                                       variable=self.feedback_frequency_var,
                                                       command=self.on_feedback_settings_changed)
        self.feedback_frequency_menu.pack(side="left", padx=5)

        ctk.CTkLabel(self.feedback_controls_frame, text="Type:").pack(side="left", padx=(20,5))
        self.feedback_type_options = ["Brief", "Normal", "Detailed"]
        self.feedback_type_var = ctk.StringVar(value="Normal")
        self.feedback_type_menu = ctk.CTkOptionMenu(self.feedback_controls_frame, 
                                                  values=self.feedback_type_options,
                                                  variable=self.feedback_type_var,
                                                  command=self.on_feedback_settings_changed)
        self.feedback_type_menu.pack(side="left", padx=5)

        self.llm_status_label = ctk.CTkLabel(self.feedback_tab_content_frame, text="LLM Status: Initializing...", font=ctk.CTkFont(size=10))
        self.llm_status_label.pack(pady=(5,0), fill="x")
        
        self.feedback_scrollable_frame = ctk.CTkScrollableFrame(self.feedback_tab_content_frame) # Removed fixed height
        self.feedback_scrollable_frame.pack(pady=10, padx=0, fill="both", expand=True)
        
        self.feedback_label = ctk.CTkLabel(self.feedback_scrollable_frame, text="AI Feedback: ...", 
                                          wraplength=700, 
                                          justify="left", font=ctk.CTkFont(size=12))
        self.feedback_label.pack(pady=5, padx=5, fill="both", expand=True)

        # --- Visualizations Tab Content ---
        self.visualizations_content_frame = ctk.CTkFrame(self.visualizations_tab, fg_color="transparent")
        self.visualizations_content_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # --- Visualizations Tab: Controls ---
        self.viz_controls_frame = ctk.CTkFrame(self.visualizations_content_frame)
        self.viz_controls_frame.pack(pady=10, padx=10, fill="x")

        ctk.CTkLabel(self.viz_controls_frame, text="Project:").pack(side="left", padx=(0,5))
        self.viz_project_selector = ctk.CTkComboBox(self.viz_controls_frame, values=["Loading..."], command=self.on_viz_controls_changed, width=180)
        self.viz_project_selector.pack(side="left", padx=(0,10))

        ctk.CTkLabel(self.viz_controls_frame, text="Period:").pack(side="left", padx=(0,5))
        self.viz_period_options = ["Last 7 Days", "Last 30 Days"] # Add more later if needed
        self.viz_period_var = ctk.StringVar(value=self.viz_period_options[0])
        self.viz_period_selector = ctk.CTkOptionMenu(self.viz_controls_frame, 
                                                     values=self.viz_period_options,
                                                     variable=self.viz_period_var,
                                                     command=self.on_viz_controls_changed)
        self.viz_period_selector.pack(side="left", padx=(0,10))
        
        self.viz_refresh_button = ctk.CTkButton(self.viz_controls_frame, text="Refresh Chart", command=self.refresh_visualizations_chart)
        self.viz_refresh_button.pack(side="left", padx=5)

        # --- Visualizations Tab: Chart Area ---
        self.viz_chart_frame = ctk.CTkFrame(self.visualizations_content_frame, fg_color="transparent")
        self.viz_chart_frame.pack(fill="both", expand=True, padx=10, pady=(0,10))
        
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.viz_chart_frame)
        # self.canvas.draw() # Initial draw can be empty or placeholder
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(side="top", fill="both", expand=True)
        self.ax.set_title("App Usage") # Placeholder title

        # --- Internal State ---
        self.projects_map = {} # name -> id
        self.current_project_id = None # For the dashboard tab's project selection
        self.globally_active_goal_id = None
        self.globally_active_goal_text = "None"
        self.globally_active_goal_project_id = None 

        self.llm_handler = None
        self.last_app_name_for_ui = ""
        self.last_window_title_for_ui = ""
        self.last_detailed_context_for_ui = "N/A"
        
        self.last_logged_app_name = ""
        self.last_logged_window_title = ""
        self.last_logged_detailed_context = ""
        self.last_logged_goal_id = None
        
        self.current_feedback_frequency_seconds = self.feedback_frequency_map[self.feedback_frequency_var.get()]
        self.current_feedback_type = self.feedback_type_var.get()
        self.last_screenshot_time = 0 # Initialize last screenshot time
        self.last_feedback_generation_time = 0 # For text-only feedback if screenshots are off
        
        self.load_initial_data() # This will also populate project filters
        self.populate_viz_project_selector() # New call

        self.tracking_active = True
        self.app_tracker_thread = threading.Thread(target=self.update_active_app_display_and_log_activity, daemon=True)
        self.app_tracker_thread.start()
        self.llm_thread = None # Will be initialized after LLM handler is ready
        self.initialize_llm_handler_and_loop()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Initial population of the goals tab
        self.refresh_goals_tab_display()

    def initialize_llm_handler_and_loop(self):
        """Initializes the LLM handler and starts the feedback loop in a separate thread."""
        try:
            self.llm_status_label.configure(text="LLM Status: Loading model & Connecting to Ollama...")
            self.llm_handler = get_llm_handler() # This initializes Ollama client and checks status
            
            # Check if handler initialized and Ollama server is responsive
            # The LLMHandler constructor now calls check_ollama_status, which prints warnings.
            # We rely on _initialized flag and that client exists.
            if self.llm_handler and self.llm_handler._initialized and self.llm_handler.client:
                # To be more robust, explicitly call check_ollama_status here if it returns a clear True/False for UI update
                # For now, we assume if _initialized is True, basic setup was ok.
                # A successful check_ollama_status call within __init__ should mean it's ready.
                # The llm_handler prints detailed status/warnings to console.
                self.llm_status_label.configure(text=f"LLM Status: Ready (Text: {self.llm_handler.text_model_name}, Vision: {self.llm_handler.multimodal_model_name})")
                if not self.llm_thread or not self.llm_thread.is_alive():
                    self.llm_thread = threading.Thread(target=self.llm_interaction_loop, daemon=True)
                    self.llm_thread.start()
            else:
                # This case might be hit if check_ollama_status fails severely in __init__ or client is not set
                self.llm_status_label.configure(text="LLM Status: Error - Ollama connection failed or models unavailable. Check console.")
        except Exception as e:
            full_error_msg = f"Failed to initialize LLM/Ollama: {e}"
            print(full_error_msg)
            # Display a more user-friendly part of the error in UI
            self.llm_status_label.configure(text=f"LLM Status: Error - {str(e)[:100]}")

    def analyze_window_content_action(self):
        """Captures a screenshot, gets its description from the LLM, and updates feedback. This is for MANUAL button press."""
        self.feedback_label.configure(text="AI Feedback: Capturing screenshot (manual)...")
        
        screenshot_path = capture_active_window_to_temp_file()
        if not screenshot_path:
            messagebox.showerror("Screenshot Error", "Could not capture the active window.")
            self.feedback_label.configure(text="AI Feedback: Screenshot capture failed.")
            return

        self.feedback_label.configure(text=f"AI Feedback: Screenshot captured ({os.path.basename(screenshot_path)}). Analyzing image...")
        self.update_idletasks() # Ensure UI updates

        if not self.llm_handler or not self.llm_handler._initialized:
            messagebox.showerror("LLM Error", "LLM Handler is not initialized or Ollama is not connected.")
            self.feedback_label.configure(text="AI Feedback: LLM not ready for image analysis.")
            return
        
        user_current_goal = self.globally_active_goal_text
        if not user_current_goal or user_current_goal == "None":
            messagebox.showinfo("Goal Needed", "Please set an active goal before analyzing a screenshot.")
            self.feedback_label.configure(text="AI Feedback: Set a goal to analyze screenshot.")
            return

        # Run the potentially long LLM call in a separate thread to keep UI responsive
        threading.Thread(target=self._process_screenshot_and_update_feedback, 
                         args=(screenshot_path, user_current_goal, True), daemon=True).start() # Added is_manual_request flag

    def _process_screenshot_and_update_feedback(self, screenshot_path: str, user_goal_for_analysis: str, is_manual_request: bool = False):
        try:
            visual_analysis = self.llm_handler.analyze_screenshot_for_productivity(screenshot_path, user_goal_for_analysis)
            
            # Prefix for UI message based on manual or auto
            ui_prefix = "Manual Screenshot Analysis" if is_manual_request else "Automated Screenshot Analysis"

            if not visual_analysis or visual_analysis.startswith("Error generating screenshot analysis") or \
               visual_analysis.startswith("LLM not available") or visual_analysis.startswith("Image file not found") or \
               "does not support processing image data" in visual_analysis or \
               "cannot process visual content" in visual_analysis or \
               visual_analysis.startswith("Ollama Error"):
                self.after(0, lambda: self.feedback_label.configure(text=f"AI Feedback ({ui_prefix}): Could not get visual analysis. Response: {visual_analysis}"))
                if "The current LLM setup does not support processing image data" in visual_analysis or \
                   "The current LLM indicated it cannot process visual content" in visual_analysis or \
                   "Multimodal model" in visual_analysis and "not found" in visual_analysis: 
                    messagebox.showwarning("Image Analysis Not Supported/Failed", 
                                          f"The LLM failed to analyze the image. Details: {visual_analysis[:200]}")
                return # Return None or error string if analysis failed, so llm_interaction_loop knows
            
            # If this was a manual request, update UI immediately with visual analysis and combined feedback
            if is_manual_request:
                interim_feedback_text = f"{ui_prefix} (vs Goal: '{user_goal_for_analysis}'):\n{visual_analysis}\n\n------\nGenerating overall feedback..."
                self.after(0, lambda: self.feedback_label.configure(text=interim_feedback_text))
                
                active_app = self.last_app_name_for_ui
                window_title = self.last_window_title_for_ui
                current_task_goal = self.globally_active_goal_text 
                detailed_context = self.last_detailed_context_for_ui
                feedback_type = self.current_feedback_type

                if current_task_goal == "None" or not current_task_goal.strip():
                    self.after(0, lambda: self.feedback_label.configure(text=f"AI Feedback ({ui_prefix}): Please set an active goal."))
                    return

                final_feedback = self.llm_handler.generate_feedback(
                    active_app, window_title, current_task_goal,
                    feedback_type=feedback_type,
                    detailed_context=detailed_context,
                    visual_analysis_context=visual_analysis
                )
                
                final_display_text = f"{ui_prefix} (vs Goal: '{user_goal_for_analysis}'):\n{visual_analysis}\n\n------\nAI Feedback (with Visuals):\n{final_feedback}"
                self.after(0, lambda: self.feedback_label.configure(text=final_display_text))
            else:
                # For automated calls, this function now primarily returns the analysis for llm_interaction_loop
                # The UI update for automated calls will be handled by llm_interaction_loop after generating combined feedback.
                # However, we might want a small log or status update here.
                print(f"Automated visual analysis successful: {visual_analysis[:100]}...")
                # No self.after UI update here for automated, it's handled in the main loop.

        except Exception as e:
            error_msg = f"Error during screenshot processing ({ui_prefix}): {str(e)[:200]}"
            print(error_msg)
            if is_manual_request: # Only show error in main feedback label if manual
                self.after(0, lambda: self.feedback_label.configure(text=f"AI Feedback: {error_msg}"))
            # For automated, error is logged. The main loop will continue.
        finally:
            if screenshot_path and os.path.exists(screenshot_path):
                try:
                    os.remove(screenshot_path)
                    print(f"Cleaned up screenshot: {screenshot_path}")
                except OSError as e_remove:
                    print(f"Error removing screenshot {screenshot_path}: {e_remove}")
            
            # This function, when called by automated process, should return the analysis or None/error
            if not is_manual_request:
                return visual_analysis # This is what the llm_interaction_loop will use

    def populate_goals_tab_project_filter(self, selected_project_name_for_filter = None):
        """Populates the project filter combobox on the Goals tab."""
        print("Populating Goals tab project filter...")
        projects = get_all_projects() # Assuming this returns Project objects
        project_names = ["All Projects"]
        if projects:
            project_names.extend([p.name for p in projects])
        
        current_filter_val = self.goals_tab_project_filter_var.get()
        self.goals_tab_project_filter_combo.configure(values=project_names)

        if selected_project_name_for_filter and selected_project_name_for_filter in project_names:
            self.goals_tab_project_filter_var.set(selected_project_name_for_filter)
        elif current_filter_val in project_names : # try to keep current selection
            self.goals_tab_project_filter_var.set(current_filter_val)
        elif project_names:
            self.goals_tab_project_filter_var.set(project_names[0])
        else: # Should not happen if "All Projects" is always there
             self.goals_tab_project_filter_var.set("All Projects")

    def refresh_goals_tab_display(self, event=None): # event is passed by combobox command
        """Clears and re-populates the scrollable list in the Goals tab based on filters."""
        for widget in self.all_goals_list_scrollable_frame.winfo_children():
            widget.destroy()

        selected_project_name_filter = self.goals_tab_project_filter_var.get()
        selected_status_filter = self.goals_tab_status_filter_var.get()

        print(f"Refreshing Goals Tab: Project Filter='{selected_project_name_filter}', Status Filter='{selected_status_filter}'")

        all_db_projects = get_all_projects(include_archived=True) # Get all projects for goal association
        project_id_to_name_map = {p.id: p.name for p in all_db_projects}
        
        target_project_id = None
        if selected_project_name_filter != "All Projects":
            # Find the ID for the selected project name filter
            for proj_id, proj_name in project_id_to_name_map.items():
                if proj_name == selected_project_name_filter:
                    target_project_id = proj_id
                    break
            if target_project_id is None:
                print(f"Warning: Project '{selected_project_name_filter}' not found for filtering.")
                # Display a message in the goals list?
                ctk.CTkLabel(self.all_goals_list_scrollable_frame, text=f"Project filter '{selected_project_name_filter}' not found.").pack()
                return


        # Fetch goals - potentially all if no project filter, or filtered by project_id
        # Then, client-side filter by status. More complex DB queries could do this server-side.
        
        goals_to_display = []
        if target_project_id:
            # Fetch goals only for the specific project
            project_goals = get_goals_for_project(target_project_id, include_completed=True)
            if project_goals:
                goals_to_display.extend(project_goals)
        else:
            # Fetch goals for all projects
            for p in all_db_projects:
                if not p.is_archived: # Typically, don't show goals from archived projects unless specified
                    project_goals = get_goals_for_project(p.id, include_completed=True)
                    if project_goals:
                        goals_to_display.extend(project_goals)
        
        # Now filter by status
        filtered_goals = []
        if selected_status_filter == "All":
            filtered_goals = goals_to_display
        else:
            for goal in goals_to_display:
                status = ""
                if goal.completed_at:
                    status = "Completed"
                elif goal.id == self.globally_active_goal_id: # Check if it's the global active goal
                    status = "Active"
                else:
                    status = "Pending"
                
                if selected_status_filter == status:
                    filtered_goals.append(goal)
        
        if not filtered_goals:
            ctk.CTkLabel(self.all_goals_list_scrollable_frame, text="No goals match the current filters.").pack(pady=10)
            return

        for goal_obj in sorted(filtered_goals, key=lambda g: (g.project_id, g.created_at), reverse=True):
            goal_item_frame = ctk.CTkFrame(self.all_goals_list_scrollable_frame, fg_color=("gray80", "gray25")) # Slightly different color for items
            goal_item_frame.pack(fill="x", pady=3, padx=3)

            project_name = project_id_to_name_map.get(goal_obj.project_id, "Unknown Project")
            
            status_text = "Pending"
            if goal_obj.completed_at:
                status_text = f"Completed ({goal_obj.completed_at.strftime('%Y-%m-%d')})"
            elif goal_obj.id == self.globally_active_goal_id:
                status_text = "Active for Feedback"

            info_text = f"Goal: {goal_obj.text}\nProject: {project_name}\nStatus: {status_text}\nCreated: {goal_obj.created_at.strftime('%Y-%m-%d %H:%M')}"
            
            ctk.CTkLabel(goal_item_frame, text=info_text, wraplength=650, justify="left").pack(side="left", padx=5, pady=5, expand=True, fill="x")

            # Add action buttons (Set Active, Complete) to the Goals tab as well
            action_button_frame = ctk.CTkFrame(goal_item_frame, fg_color="transparent")
            action_button_frame.pack(side="right", padx=5, pady=5)

            if not goal_obj.completed_at:
                if goal_obj.id != self.globally_active_goal_id:
                    set_active_btn = ctk.CTkButton(action_button_frame, text="Set Active", width=70,
                                                     command=lambda g_id=goal_obj.id: self.set_globally_active_goal_action_from_goals_tab(g_id))
                    set_active_btn.pack(pady=2)
                
                complete_btn = ctk.CTkButton(action_button_frame, text="Complete", width=70,
                                               command=lambda g_id=goal_obj.id: self.complete_goal_action_from_goals_tab(g_id))
                complete_btn.pack(pady=2)
            # Add more actions if needed: e.g., Edit, Delete

    def set_globally_active_goal_action_from_goals_tab(self, goal_id: int):
        self.set_globally_active_goal_action(goal_id) # Use the existing method
        self.refresh_goals_tab_display() # Refresh this tab
        # Also refresh dashboard if the project of this goal is selected there
        active_goal_obj = get_goal_by_id(goal_id) # Need a get_goal_by_id or fetch it
        if active_goal_obj and active_goal_obj.project_id == self.current_project_id:
            self.load_goals_for_project(self.current_project_id)

    def complete_goal_action_from_goals_tab(self, goal_id: int):
        self.complete_goal_action(goal_id) # Use the existing method
        self.refresh_goals_tab_display() # Refresh this tab
         # Also refresh dashboard if the project of this goal is selected there
        # To do this robustly, we'd need to know the project_id of the completed goal.
        # For now, a simpler refresh or rely on user to switch projects if needed.
        # A better way: complete_goal_action should return the goal_obj or its project_id
        # completed_goal = complete_goal(goal_id)
        # if completed_goal and completed_goal.project_id == self.current_project_id:
        if self.current_project_id: # For now, just refresh if a project is selected
            self.load_goals_for_project(self.current_project_id)

    def load_initial_data(self):
        self.load_projects() # This is for the dashboard project selector
        self.populate_goals_tab_project_filter() # This is for the Goals tab project filter
        self.load_and_display_globally_active_goal()
        
        if self.projects_map and self.project_selector.get() != "No Projects Yet":
            # self.on_project_selected will be called if project_selector.set triggers command
            # but to be sure, call it if values were set without triggering command initially.
             if self.project_selector.get() in self.projects_map:
                self.on_project_selected(self.project_selector.get())
             else: # If default selection isn't a valid project name
                self.current_project_label.configure(text="Selected Project: No projects available")
                self.clear_goals_list() # Dashboard goals list
        else:
            self.current_project_label.configure(text="Selected Project: No projects available")
            self.clear_goals_list()

        self.refresh_goals_tab_display() # Initial load for goals tab

    def load_projects(self):
        """Loads projects for the Dashboard's project selector."""
        print("Loading projects for Dashboard selector...")
        projects = get_all_projects()
        self.projects_map.clear() # name -> id map for dashboard
        project_names_for_dashboard_selector = []
        if projects:
            for p in projects:
                if not p.is_archived: # Dashboard usually for active work
                    self.projects_map[p.name] = p.id
                    project_names_for_dashboard_selector.append(p.name)
            
            self.project_selector.configure(values=project_names_for_dashboard_selector if project_names_for_dashboard_selector else ["No Active Projects"])
            if project_names_for_dashboard_selector:
                current_selection = self.project_selector.get()
                if current_selection not in project_names_for_dashboard_selector:
                     self.project_selector.set(project_names_for_dashboard_selector[0])
                # self.on_project_selected should be triggered by .set() if command is configured
            else:
                self.project_selector.set("No Active Projects")
                self.current_project_id = None
        else:
            self.project_selector.configure(values=["No Projects Yet"])
            self.project_selector.set("No Projects Yet")
            self.current_project_id = None
        # print(f"Loaded projects for dashboard selector: {project_names_for_dashboard_selector}")

    def create_project_action(self):
        project_name = self.new_project_entry.get()
        if not project_name.strip():
            messagebox.showwarning("Input Error", "Project name cannot be empty.")
            return
        new_proj = add_project(project_name)
        if new_proj:
            self.new_project_entry.delete(0, ctk.END)
            self.load_projects() # Reload dashboard projects
            self.populate_goals_tab_project_filter(selected_project_name_for_filter=new_proj.name) # Reload goals tab filter and try to select new one
            
            if new_proj.name in self.projects_map: # Check if it made it to the dashboard selector
                 self.project_selector.set(new_proj.name)
                 self.on_project_selected(new_proj.name) # Trigger dashboard view update
            
            self.refresh_goals_tab_display() # Refresh the goals list in the Goals tab
            messagebox.showinfo("Success", f"Project '{new_proj.name}' created.")
        else:
            messagebox.showerror("Error", f"Failed to create project '{project_name}'. It might already exist or DB error.")

    def set_globally_active_goal_action(self, goal_id: int):
        print(f"Attempting to set global active goal ID: {goal_id}")
        updated_goal = set_active_goal(goal_id)
        if updated_goal:
            self.load_and_display_globally_active_goal()
            # Refresh the goals list for the current project on dashboard tab
            if self.current_project_id and self.current_project_id == updated_goal.project_id: # only if the active goal belongs to current project
                self.load_goals_for_project(self.current_project_id)
            elif self.current_project_id: # if it belongs to another project, just refresh current one to remove old [ACTIVE] tag
                self.load_goals_for_project(self.current_project_id)

            self.refresh_goals_tab_display() # Refresh the goals tab display
        else:
            messagebox.showerror("Error", "Could not set active goal. It might be completed or an error occurred.")

    def complete_goal_action(self, goal_id: int):
        # Need to get project_id of goal being completed to refresh dashboard if it's the current one
        
        # This is tricky because get_goal_by_id is not yet defined.
        # For now, assume complete_goal in DB handler sets is_active to false.
        # The UI will refresh the active goal display and the lists.
        
        # Simplification: fetch the goal's project ID before completing, if possible
        # Or, the complete_goal function in DB could return the object including project_id
        # temp_goal_obj = get_goal_by_id(goal_id) # Assuming this function exists

        completed = complete_goal(goal_id) # This is from database_handler
        
        if completed: # `completed` here is the goal object from DB
            project_id_of_completed_goal = completed.project_id

            if self.globally_active_goal_id == goal_id:
                self.load_and_display_globally_active_goal() 
            
            if self.current_project_id == project_id_of_completed_goal:
                self.load_goals_for_project(self.current_project_id) # Refresh dashboard list
            
            self.refresh_goals_tab_display() # Refresh goals tab
        else:
            messagebox.showerror("Error", "Failed to complete goal.")

    def on_project_selected(self, selected_project_name: str): # For Dashboard
        if selected_project_name == "No Projects Yet" or selected_project_name == "Loading..." or selected_project_name == "No Active Projects":
            self.current_project_id = None
            self.current_project_label.configure(text="Selected Project: None")
            self.clear_goals_list()
            return

        self.current_project_id = self.projects_map.get(selected_project_name)
        if self.current_project_id:
            print(f"Dashboard Project selected: {selected_project_name} (ID: {self.current_project_id})")
            self.current_project_label.configure(text=f"Selected Project: {selected_project_name}")
            self.load_goals_for_project(self.current_project_id)
        else:
            print(f"Error: Could not find ID for dashboard project {selected_project_name}")
            self.current_project_label.configure(text="Selected Project: Error")
            self.clear_goals_list()

    def clear_goals_list(self): # For Dashboard
        for widget in self.goals_list_frame.winfo_children():
            widget.destroy()

    def load_goals_for_project(self, project_id: int): # For Dashboard
        self.clear_goals_list()
        if project_id is None:
            ctk.CTkLabel(self.goals_list_frame, text="Select a project to see its goals.").pack(pady=5)
            return
        
        project = get_project_by_id(project_id)
        if project and project.is_archived:
            ctk.CTkLabel(self.goals_list_frame, text=f"Project '{project.name}' is archived.\nNo goals shown here.").pack(pady=5)
            return

        goals = get_goals_for_project(project_id, include_completed=True)
        if not goals:
            ctk.CTkLabel(self.goals_list_frame, text="No goals yet for this project.").pack(pady=5)
            return

        for goal_obj in goals:
            goal_frame = ctk.CTkFrame(self.goals_list_frame)
            goal_frame.pack(fill="x", pady=2, padx=2)

            status = "Completed" if goal_obj.completed_at else "Pending"
            goal_text_display = f"{goal_obj.text} (Status: {status})"
            if goal_obj.id == self.globally_active_goal_id:
                goal_text_display += " [ACTIVE FEEDBACK]"
            
            ctk.CTkLabel(goal_frame, text=goal_text_display, wraplength=280, justify="left").pack(side="left", padx=5, pady=5, expand=True, fill="x")

            button_frame = ctk.CTkFrame(goal_frame, fg_color="transparent") # fg_color="transparent"
            button_frame.pack(side="right", padx=5)

            if not goal_obj.completed_at:
                if goal_obj.id != self.globally_active_goal_id:
                    set_active_btn = ctk.CTkButton(button_frame, text="Set Active", width=80,
                                                 command=lambda g_id=goal_obj.id: self.set_globally_active_goal_action(g_id))
                    set_active_btn.pack(side="left", padx=2)
                else: # If it IS the active goal, maybe show a "Deactivate" or it's implicitly handled by setting another
                    pass

                complete_btn = ctk.CTkButton(button_frame, text="Complete", width=80,
                                               command=lambda g_id=goal_obj.id: self.complete_goal_action(g_id))
                complete_btn.pack(side="left", padx=2)

    def add_goal_action(self): # For Dashboard
        goal_text = self.new_goal_entry.get()
        if not goal_text.strip():
            messagebox.showwarning("Input Error", "Goal text cannot be empty.")
            return
        if self.current_project_id is None:
            messagebox.showwarning("Project Error", "Please select or create a project first (on Dashboard).")
            return
        
        project = get_project_by_id(self.current_project_id)
        if project and project.is_archived:
            messagebox.showwarning("Project Archived", f"Project '{project.name}' is archived. Cannot add new goals.")
            return

        new_g = add_goal(goal_text, self.current_project_id)
        if new_g:
            self.new_goal_entry.delete(0, ctk.END)
            self.load_goals_for_project(self.current_project_id) # Refresh dashboard list
            self.refresh_goals_tab_display() # Refresh goals tab as well
            messagebox.showinfo("Success", f"Goal '{new_g.text}' added to current project.")
        else:
            messagebox.showerror("Error", "Failed to add goal. Check logs.")

    def load_and_display_globally_active_goal(self):
        active_goal_obj = get_active_goal()
        if active_goal_obj:
            self.globally_active_goal_id = active_goal_obj.id
            self.globally_active_goal_text = active_goal_obj.text
            self.globally_active_goal_project_id = active_goal_obj.project_id 
            self.active_goal_display_label.configure(text=f"Active Goal for Feedback: {active_goal_obj.text}")
            print(f"Loaded globally active goal: '{active_goal_obj.text}' (Project ID: {self.globally_active_goal_project_id})")
            
            if self.last_logged_goal_id != self.globally_active_goal_id:
                self.last_logged_app_name = ""
                self.last_logged_window_title = ""
                self.last_logged_detailed_context = ""
                self.last_logged_goal_id = self.globally_active_goal_id
        else:
            self.globally_active_goal_id = None
            self.globally_active_goal_text = "None"
            self.globally_active_goal_project_id = None
            self.active_goal_display_label.configure(text="Active Goal for Feedback: None")
            print("No globally active goal found.")
            self.last_logged_app_name = ""
            self.last_logged_window_title = ""
            self.last_logged_detailed_context = ""
            self.last_logged_goal_id = None
        
        # After loading active goal, all goal lists should refresh to reflect new status
        if hasattr(self, 'goals_list_frame') and self.current_project_id: # If dashboard is initialized
             self.load_goals_for_project(self.current_project_id)
        if hasattr(self, 'all_goals_list_scrollable_frame'): # If goals tab is initialized
            self.refresh_goals_tab_display()

    def update_active_app_display_and_log_activity(self):
        while self.tracking_active:
            app_info = get_active_application_info()
            current_app_name = "None"
            current_window_title = "N/A"
            current_detailed_context = "N/A"

            if app_info:
                current_app_name = app_info.get('name', 'N/A')
                current_window_title = app_info.get('window_title', 'N/A')
                current_detailed_context = app_info.get('detailed_context', 'N/A')
            
            # Update UI labels
            if hasattr(self, 'active_app_label'): # Check if UI element exists before configuring
                self.active_app_label.configure(text=f"App: {current_app_name}")
                self.active_window_label.configure(text=f"Window: {current_window_title}")
                self.detailed_context_label.configure(text=f"Context: {current_detailed_context if current_detailed_context not in [None, 'N/A'] else '...'}")
            
            self.last_app_name_for_ui = current_app_name 
            self.last_window_title_for_ui = current_window_title 
            self.last_detailed_context_for_ui = current_detailed_context

            # Activity Logging Logic
            if self.globally_active_goal_id and self.globally_active_goal_project_id:
                if self.last_logged_goal_id != self.globally_active_goal_id:
                    self.last_logged_app_name = "" 
                    self.last_logged_window_title = ""
                    self.last_logged_detailed_context = "" # Reset this too
                    self.last_logged_goal_id = self.globally_active_goal_id

                if (current_app_name != self.last_logged_app_name or \
                    current_window_title != self.last_logged_window_title or \
                    current_detailed_context != self.last_logged_detailed_context): # Added context check
                    
                    is_meaningful_change = not (
                        (self.last_logged_app_name == "N/A" and current_app_name == "None") or 
                        (self.last_logged_app_name == "None" and current_app_name == "N/A")
                    )
                    if not (current_app_name == "None" or current_app_name == "N/A") and is_meaningful_change:
                        print(f"Logging activity: App: {current_app_name}, Win: {current_window_title}, Ctx: {current_detailed_context} for Goal ID {self.globally_active_goal_id}")
                        add_activity_log(
                            goal_id=self.globally_active_goal_id,
                            project_id=self.globally_active_goal_project_id,
                            app_name=current_app_name,
                            window_title=current_window_title,
                            detailed_context=current_detailed_context
                        )
                        self.last_logged_app_name = current_app_name
                        self.last_logged_window_title = current_window_title
                        self.last_logged_detailed_context = current_detailed_context
            else:
                if self.last_logged_goal_id is not None:
                    self.last_logged_app_name = ""
                    self.last_logged_window_title = ""
                    self.last_logged_detailed_context = ""
                    self.last_logged_goal_id = None
            
            time.sleep(2) 

    def llm_interaction_loop(self):
        # Initial status update
        try:
            if not self.llm_handler or not self.llm_handler._initialized or not self.llm_handler.client:
                self.after(0, lambda: self.llm_status_label.configure(text="LLM Status: Initializing..."))
                self.initialize_llm_handler_and_loop() # Attempt to re-initialize if not ready
                return # Exit this iteration, will be recalled by initialize_llm_handler_and_loop
            else:
                # Update status if handler is now ready (might have been initialized by the above call)
                 self.after(0, lambda: self.llm_status_label.configure(text=f"LLM Status: Ready (Text: {self.llm_handler.text_model_name}, Vision: {self.llm_handler.multimodal_model_name})"))
        except Exception as e:
            self.after(0, lambda: self.llm_status_label.configure(text=f"LLM Status: Error - {str(e)[:100]}"))
            print(f"LLM handler check failed in loop: {e}")
            # Optionally, schedule a retry for initialization after a delay
            # self.after(10000, self.initialize_llm_handler_and_loop) # Retry after 10s
            time.sleep(5) # Wait before next check if LLM init fails
            if self.tracking_active: # Reschedule this loop
                self.llm_thread = threading.Thread(target=self.llm_interaction_loop, daemon=True)
                self.llm_thread.start()
            return


        loop_interval = 2 # seconds - how often this loop runs to check conditions
        time_since_last_feedback_or_screenshot = time.time() - max(self.last_feedback_generation_time, self.last_screenshot_time)

        while self.tracking_active:
            if not self.llm_handler or not self.llm_handler._initialized:
                print("LLM Handler not ready in main loop, attempting re-init and skipping cycle.")
                # Attempt to re-initialize. This might happen if Ollama server stops/starts.
                # The initialize_llm_handler_and_loop method itself should be robust.
                # self.initialize_llm_handler_and_loop() # This will also restart the loop if successful.
                # For now, simply wait and let the main app structure handle re-init if needed via status checks.
                time.sleep(loop_interval * 2) # Wait a bit longer if LLM is not ready
                continue

            visual_analysis_for_this_iteration = None
            user_goal_for_feedback = self.globally_active_goal_text
            active_goal_id = self.globally_active_goal_id
            
            # Check if feedback generation is globally turned off
            if self.current_feedback_frequency_seconds == 0:
                if self.feedback_label.cget("text") != "AI Feedback: Turned off (Set a frequency).":
                    self.after(0, lambda: self.feedback_label.configure(text="AI Feedback: Turned off (Set a frequency)."))
                self.last_feedback_generation_time = time.time() # Keep updating to prevent immediate run if turned back on
                self.last_screenshot_time = time.time()
                time.sleep(loop_interval)
                continue

            if not active_goal_id or user_goal_for_feedback == "None":
                if self.feedback_label.cget("text") != "AI Feedback: Set an active goal for feedback.":
                     self.after(0, lambda: self.feedback_label.configure(text="AI Feedback: Set an active goal for feedback."))
                self.last_feedback_generation_time = time.time()
                self.last_screenshot_time = time.time()
                time.sleep(loop_interval)
                continue
            
            current_time = time.time()
            ready_for_action = (current_time - self.last_feedback_generation_time) >= self.current_feedback_frequency_seconds

            if ready_for_action:
                print(f"LLM Loop: Ready for action. Freq: {self.current_feedback_frequency_seconds}s. Goal: {user_goal_for_feedback}")
                
                # Attempt screenshot and visual analysis if multimodal model is available
                if self.llm_handler.multimodal_model_name and self.llm_handler.multimodal_model_name != "None": # Check if a multimodal model is configured
                    print("LLM Loop: Attempting automated screenshot and analysis.")
                    self.after(0, lambda: self.feedback_label.configure(text="AI Feedback: Capturing screenshot (auto)..."))
                    
                    screenshot_path = capture_active_window_to_temp_file()
                    if screenshot_path:
                        try:
                            # Call _process_screenshot_and_update_feedback in a way that it returns the analysis
                            # This needs to be blocking or handled with care if threaded
                            # For simplicity, let's make it blocking here as the loop itself is in a thread.
                            visual_analysis_for_this_iteration = self._process_screenshot_and_update_feedback(screenshot_path, user_goal_for_feedback, is_manual_request=False)
                            
                            if visual_analysis_for_this_iteration and not visual_analysis_for_this_iteration.startswith("Error"):
                                 self.after(0, lambda: self.feedback_label.configure(text=f"AI Feedback: Screenshot analyzed (auto). Visuals: {visual_analysis_for_this_iteration[:60]}..."))
                            elif visual_analysis_for_this_iteration: # Contains an error message
                                self.after(0, lambda: self.feedback_label.configure(text=f"AI Feedback: Screenshot analysis failed (auto). {visual_analysis_for_this_iteration[:100]}..."))
                            else: # Path existed, but analysis returned None (should be an error string per current logic)
                                self.after(0, lambda: self.feedback_label.configure(text="AI Feedback: Screenshot analysis failed (auto). Unknown error."))
                        except Exception as e_ss:
                            print(f"Error in automated screenshot processing call: {e_ss}")
                            self.after(0, lambda: self.feedback_label.configure(text=f"AI Feedback: Error during auto screenshot: {str(e_ss)[:60]}"))
                        finally:
                            self.last_screenshot_time = current_time # Update time even if it failed, to avoid rapid retries
                    else:
                        print("LLM Loop: Failed to capture screenshot (auto).")
                        self.after(0, lambda: self.feedback_label.configure(text="AI Feedback: Screenshot capture failed (auto)."))
                        self.last_screenshot_time = current_time # Update time to avoid rapid retries on capture failure

                # Proceed to generate feedback (with or without visual analysis)
                self.after(0, lambda: self.feedback_label.configure(text=f"AI Feedback: Generating feedback for '{user_goal_for_feedback}'..."))
                
                try:
                    final_feedback_text = self.llm_handler.generate_feedback(
                        active_app_name=self.last_app_name_for_ui,
                        window_title=self.last_window_title_for_ui,
                        user_goal=user_goal_for_feedback,
                        feedback_type=self.current_feedback_type,
                        detailed_context=self.last_detailed_context_for_ui,
                        visual_analysis_context=visual_analysis_for_this_iteration # Pass it here
                    )

                    display_text = ""
                    if visual_analysis_for_this_iteration and not visual_analysis_for_this_iteration.startswith("Error"):
                        display_text = f"Automated Visual Analysis (vs Goal: '{user_goal_for_feedback}'):\n{visual_analysis_for_this_iteration}\n\n------\n"
                    display_text += f"AI Feedback (Goal: '{user_goal_for_feedback}'):\n{final_feedback_text}"
                    
                    self.after(0, lambda text_to_display=display_text: self.feedback_label.configure(text=text_to_display))
                    self.last_feedback_generation_time = current_time # Mark that feedback was generated

                except Exception as e_feedback:
                    print(f"Error during feedback generation in LLM loop: {e_feedback}")
                    self.after(0, lambda: self.feedback_label.configure(text=f"AI Feedback: Error generating feedback - {str(e_feedback)[:60]}"))
                    self.last_feedback_generation_time = current_time # Still update time to avoid rapid retry on error

            time.sleep(loop_interval) # Wait for the next check

    def on_feedback_settings_changed(self, choice=None): 
        new_freq_seconds = self.feedback_frequency_map[self.feedback_frequency_var.get()]
        new_type = self.feedback_type_var.get()
        
        # Reset LLM loop's timer if frequency changes to force re-evaluation
        if new_freq_seconds != self.current_feedback_frequency_seconds:
             # This reset is handled internally in the loop by time_since_last_feedback potentially becoming >= new_freq_seconds
             pass

        self.current_feedback_frequency_seconds = new_freq_seconds
        self.current_feedback_type = new_type
        print(f"Feedback settings changed: Frequency: {self.current_feedback_frequency_seconds}s, Type: {self.current_feedback_type}")
        # The LLM loop will pick this up. If frequency changed to "Off", it will show "Turned off".
        # If changed from "Off" to a value, it will resume.
        # An immediate feedback generation on change could be added if desired.

    def on_closing(self):
        print("Closing application...")
        self.tracking_active = False
        # Give threads a moment to finish their current loop iteration
        if hasattr(self, 'app_tracker_thread') and self.app_tracker_thread.is_alive():
            self.app_tracker_thread.join(timeout=2.5) # Increased timeout slightly
        if hasattr(self, 'llm_thread') and self.llm_thread.is_alive():
            self.llm_thread.join(timeout=2.0)
        self.destroy()

    def populate_viz_project_selector(self):
        projects = get_all_projects()
        project_names = [p.name for p in projects]
        self.projects_map_viz = {p.name: p.id for p in projects} # Similar to dashboard's projects_map
        if not project_names:
            project_names = ["No Projects Yet"]
            self.viz_project_selector.set("No Projects Yet")
            self.viz_project_selector.configure(state="disabled")
        else:
            self.viz_project_selector.configure(values=project_names, state="normal")
            if self.viz_project_selector.get() not in project_names and len(project_names) > 0:
                 self.viz_project_selector.set(project_names[0])
        self.refresh_visualizations_chart() # Initial chart load

    def on_viz_controls_changed(self, event=None):
        self.refresh_visualizations_chart()

    def refresh_visualizations_chart(self):
        selected_project_name = self.viz_project_selector.get()
        if not selected_project_name or selected_project_name == "Loading..." or selected_project_name == "No Projects Yet":
            self.ax.clear()
            self.ax.text(0.5, 0.5, "Please select a project.", horizontalalignment='center', verticalalignment='center')
            self.canvas.draw()
            return

        project_id = self.projects_map_viz.get(selected_project_name)
        if project_id is None:
            self.ax.clear()
            self.ax.text(0.5, 0.5, "Invalid project selected.", horizontalalignment='center', verticalalignment='center')
            self.canvas.draw()
            return

        selected_period = self.viz_period_var.get()
        end_date = datetime.datetime.now()
        if selected_period == "Last 7 Days":
            start_date = end_date - datetime.timedelta(days=7)
        elif selected_period == "Last 30 Days":
            start_date = end_date - datetime.timedelta(days=30)
        else:
            # Should not happen with OptionMenu, but good practice
            self.ax.clear()
            self.ax.text(0.5, 0.5, "Invalid period selected.", horizontalalignment='center', verticalalignment='center')
            self.canvas.draw()
            return

        # Fetch aggregated data
        try:
            app_usage_data = get_aggregated_activity_by_app(project_id, start_date, end_date)
        except Exception as e:
            print(f"Error fetching or processing visualization data: {e}")
            self.ax.clear()
            self.ax.text(0.5, 0.5, f"Error loading data: {e}", horizontalalignment='center', verticalalignment='center',  wrap=True)
            self.canvas.draw()
            return

        self.ax.clear()
        if not app_usage_data:
            self.ax.text(0.5, 0.5, "No activity data found for the selected period.", horizontalalignment='center', verticalalignment='center', wrap=True)
        else:
            apps = list(app_usage_data.keys())
            durations_seconds = list(app_usage_data.values())
            durations_hours = [d / 3600 for d in durations_seconds] # Convert to hours

            self.ax.barh(apps, durations_hours, color='skyblue') # Horizontal bar chart
            self.ax.set_xlabel("Time Spent (hours)")
            self.ax.set_ylabel("Application")
            self.ax.set_title(f"App Usage for {selected_project_name} ({selected_period})")
            self.fig.tight_layout() # Adjust layout to prevent labels from being cut off
        
        self.canvas.draw()

if __name__ == '__main__':
    app = App()
    app.mainloop() 