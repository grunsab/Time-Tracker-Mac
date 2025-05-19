import customtkinter as ctk
from tkinter import messagebox # For simple dialogs
import datetime # Added for date calculations
from datetime import date as dt_date, timedelta, datetime as dt_datetime # For specific date/time operations
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates # For formatting time on axis
from src.tracker.app_tracker import get_active_application_info
from src.llm.llm_handler import get_llm_handler
from src.database.database_handler import (
    init_db, add_project, get_all_projects, get_project_by_id,
    add_goal, get_goals_for_project, set_active_goal, get_active_goal, complete_goal, Goal, get_goal_by_id,
    add_activity_log, get_aggregated_activity_by_app, get_activity_logs_for_day # Import new function
)
from src.utils.screenshot_utils import capture_active_window_to_temp_file # Import for screenshot
import threading
import time
import os

class NudgePopup(ctk.CTkToplevel):
    def __init__(self, parent, message: str, on_snooze=None, on_dismiss=None):
        super().__init__(parent)
        
        # Configure popup window
        self.title("Productivity Nudge")
        self.geometry("600x300")
        self.resizable(False, False)
        
        # Make it stay on top
        self.attributes('-topmost', True)
        
        # Center the popup on screen
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        
        # Create main frame
        self.frame = ctk.CTkFrame(self)
        self.frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Message label
        self.message_label = ctk.CTkLabel(
            self.frame,
            text=message,
            wraplength=540,
            justify="left",
            font=ctk.CTkFont(size=14)
        )
        self.message_label.pack(pady=20, padx=20, fill="both", expand=True)
        
        # Buttons frame
        self.button_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.button_frame.pack(pady=10, padx=20, fill="x")
        
        # Snooze button
        self.snooze_button = ctk.CTkButton(
            self.button_frame,
            text="Snooze 30m",
            command=lambda: self._handle_snooze(on_snooze),
            width=120
        )
        self.snooze_button.pack(side="right", padx=5)
        
        # Dismiss button
        self.dismiss_button = ctk.CTkButton(
            self.button_frame,
            text="Dismiss",
            command=lambda: self._handle_dismiss(on_dismiss),
            width=120
        )
        self.dismiss_button.pack(side="right", padx=5)
        
        # Bind escape key to dismiss
        self.bind('<Escape>', lambda e: self._handle_dismiss(on_dismiss))
        
        # Ensure the popup is visible
        self.deiconify()
        self.lift()
        self.focus_force()
        
    def _handle_snooze(self, callback):
        if callback:
            callback()
        self.destroy()
        
    def _handle_dismiss(self, callback):
        if callback:
            callback()
        self.destroy()

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Constants for Modern UI ---
        self.CORNER_RADIUS = 8
        self.PAD_X = 10
        self.PAD_Y = 10
        self.FRAME_BORDER_WIDTH = 0 # Set to 1 or 2 for subtle borders if desired

        # --- Theme and Appearance ---
        ctk.set_appearance_mode("System") # Options: "System", "Light", "Dark"
        ctk.set_default_color_theme("dark-blue") # Options: "blue", "dark-blue", "green"

        try:
            init_db()
            print("Database initialized successfully from App.")
        except Exception as e:
            messagebox.showerror("Database Error", f"Database initialization failed: {e}\nApplication might not work correctly.")
            # Potentially exit or disable DB-dependent features

        self.title("Productivity Tracker")
        self.geometry("800x950") # Slightly increased size for better spacing

        # --- Main Layout Frames ---
        self.top_frame = ctk.CTkFrame(self, corner_radius=self.CORNER_RADIUS, border_width=self.FRAME_BORDER_WIDTH)
        self.top_frame.pack(pady=self.PAD_Y, padx=self.PAD_X, fill="x")

        # --- Top Frame: Active App Info ---
        self.active_app_label = ctk.CTkLabel(self.top_frame, text="App: Fetching...", font=ctk.CTkFont(size=15, weight="bold")) # Increased size
        self.active_app_label.pack(pady=(self.PAD_Y/2, 0))
        self.active_window_label = ctk.CTkLabel(self.top_frame, text="Window: ...", font=ctk.CTkFont(size=13)) # Increased size
        self.active_window_label.pack(pady=(0,0))
        self.detailed_context_label = ctk.CTkLabel(self.top_frame, text="Context: ...", font=ctk.CTkFont(size=11), wraplength=750) # Adjusted wraplength for new geometry
        self.detailed_context_label.pack(pady=(0,self.PAD_Y/2))

        # Screenshot Analysis Button
        self.analyze_window_button = ctk.CTkButton(self.top_frame, text="Analyze Window Content (Screenshot)", command=lambda: self.analyze_window_content_action_mtmd())
        self.analyze_window_button.pack(pady=5)

        # --- Tab View ---
        # TabView will now hold Dashboard, Goals, and Feedback sections.
        # It should expand to fill most of the window.
        self.tab_view = ctk.CTkTabview(self, corner_radius=self.CORNER_RADIUS) # Added corner_radius
        self.tab_view.pack(pady=self.PAD_Y, padx=self.PAD_X, fill="both", expand=True) # expand=True now for tab_view

        self.dashboard_tab = self.tab_view.add("Dashboard")
        self.goals_tab = self.tab_view.add("Goals")
        self.feedback_tab = self.tab_view.add("Feedback") # New Feedback Tab
        self.visualizations_tab = self.tab_view.add("Visualizations") # New Visualizations Tab

        self.tab_view.set("Dashboard") # Default to Dashboard, or change to "Feedback"

        # self.bottom_frame is NO LONGER USED as a main packed frame.
        # Its content will move into self.feedback_tab.

        # --- Dashboard Tab Content ---
        self.dashboard_content_frame = ctk.CTkFrame(self.dashboard_tab, fg_color="transparent") # Transparent if tabview has color
        self.dashboard_content_frame.pack(fill="both", expand=True, padx=self.PAD_X/2, pady=self.PAD_Y/2)
        self.dashboard_content_frame.grid_columnconfigure(0, weight=1)
        self.dashboard_content_frame.grid_columnconfigure(1, weight=2) # Give more space to goals list
        self.dashboard_content_frame.grid_rowconfigure(0, weight=1) # Allow vertical expansion

        # --- Dashboard: Left - Projects & New Goal ---
        self.project_controls_frame = ctk.CTkFrame(self.dashboard_content_frame, corner_radius=self.CORNER_RADIUS, border_width=self.FRAME_BORDER_WIDTH)
        self.project_controls_frame.grid(row=0, column=0, padx=(0, self.PAD_X/2), pady=self.PAD_Y/2, sticky="nsew")

        ctk.CTkLabel(self.project_controls_frame, text="Projects", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=self.PAD_Y)
        self.project_selector = ctk.CTkComboBox(self.project_controls_frame, values=["Loading..."], command=self.on_project_selected, width=220, corner_radius=self.CORNER_RADIUS) # Increased width
        self.project_selector.pack(pady=self.PAD_Y/2, padx=self.PAD_X)
        
        self.new_project_entry = ctk.CTkEntry(self.project_controls_frame, placeholder_text="New Project Name", width=220, corner_radius=self.CORNER_RADIUS)
        self.new_project_entry.pack(pady=self.PAD_Y/2, padx=self.PAD_X)
        self.add_project_button = ctk.CTkButton(self.project_controls_frame, text="Create Project", command=self.create_project_action, corner_radius=self.CORNER_RADIUS, font=ctk.CTkFont(weight="bold")) # Bold text
        self.add_project_button.pack(pady=self.PAD_Y, padx=self.PAD_X, ipady=self.PAD_Y/4) # Added Y padding for button height

        ctk.CTkLabel(self.project_controls_frame, text="Add New Goal", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(self.PAD_Y*1.5, self.PAD_Y/2))
        self.new_goal_entry = ctk.CTkEntry(self.project_controls_frame, placeholder_text="New Goal for Selected Project", width=220, corner_radius=self.CORNER_RADIUS)
        self.new_goal_entry.pack(pady=self.PAD_Y/2, padx=self.PAD_X)
        self.add_goal_button = ctk.CTkButton(self.project_controls_frame, text="Add Goal to Project", command=self.add_goal_action, corner_radius=self.CORNER_RADIUS, font=ctk.CTkFont(weight="bold")) # Bold text
        self.add_goal_button.pack(pady=self.PAD_Y, padx=self.PAD_X, ipady=self.PAD_Y/4) # Added Y padding
        
        # --- Dashboard: Right - Goals List for Selected Project ---
        self.goals_display_frame = ctk.CTkFrame(self.dashboard_content_frame, corner_radius=self.CORNER_RADIUS, border_width=self.FRAME_BORDER_WIDTH)
        self.goals_display_frame.grid(row=0, column=1, padx=(self.PAD_X/2, 0), pady=self.PAD_Y/2, sticky="nsew")
        
        ctk.CTkLabel(self.goals_display_frame, text="Project Goals", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=self.PAD_Y)
        self.current_project_label = ctk.CTkLabel(self.goals_display_frame, text="Selected Project: None", font=ctk.CTkFont(size=13))
        self.current_project_label.pack(pady=self.PAD_Y/2)
        self.goals_list_frame = ctk.CTkScrollableFrame(self.goals_display_frame, corner_radius=self.CORNER_RADIUS, fg_color="transparent") # Removed fixed height, fg_color transparent
        self.goals_list_frame.pack(pady=self.PAD_Y/2, padx=self.PAD_X/2, fill="both", expand=True)

        # --- Goals Tab Content ---
        self.goals_tab_content_frame = ctk.CTkFrame(self.goals_tab, fg_color="transparent")
        self.goals_tab_content_frame.pack(fill="both", expand=True, padx=self.PAD_X/2, pady=self.PAD_Y/2)
        self.goals_tab_content_frame.grid_columnconfigure(0, weight=1) # For filter controls
        self.goals_tab_content_frame.grid_columnconfigure(1, weight=3) # For goal list

        # Filters for Goals Tab
        self.goals_tab_filter_frame = ctk.CTkFrame(self.goals_tab_content_frame, corner_radius=self.CORNER_RADIUS, border_width=self.FRAME_BORDER_WIDTH)
        self.goals_tab_filter_frame.grid(row=0, column=0, columnspan=2, padx=self.PAD_X/2, pady=self.PAD_Y/2, sticky="ew")
        
        ctk.CTkLabel(self.goals_tab_filter_frame, text="Filter by Project:").pack(side="left", padx=(self.PAD_X, self.PAD_X/4))
        self.goals_tab_project_filter_var = ctk.StringVar(value="All Projects")
        self.goals_tab_project_filter_combo = ctk.CTkComboBox(self.goals_tab_filter_frame, 
                                                              values=["All Projects"], 
                                                              variable=self.goals_tab_project_filter_var,
                                                              command=self.refresh_goals_tab_display,
                                                              corner_radius=self.CORNER_RADIUS)
        self.goals_tab_project_filter_combo.pack(side="left", padx=(0,self.PAD_X))

        ctk.CTkLabel(self.goals_tab_filter_frame, text="Filter by Status:").pack(side="left", padx=(self.PAD_X, self.PAD_X/4))
        self.goals_tab_status_options = ["All", "Pending", "Active", "Completed"]
        self.goals_tab_status_filter_var = ctk.StringVar(value="All")
        self.goals_tab_status_filter_combo = ctk.CTkComboBox(self.goals_tab_filter_frame, 
                                                             values=self.goals_tab_status_options, 
                                                             variable=self.goals_tab_status_filter_var,
                                                             command=self.refresh_goals_tab_display,
                                                             corner_radius=self.CORNER_RADIUS)
        self.goals_tab_status_filter_combo.pack(side="left", padx=(0,self.PAD_X/2))
        
        self.refresh_goals_tab_filters_button = ctk.CTkButton(self.goals_tab_filter_frame, text="Refresh Filters", command=self.populate_goals_tab_project_filter, corner_radius=self.CORNER_RADIUS, font=ctk.CTkFont(weight="bold")) # Bold text
        self.refresh_goals_tab_filters_button.pack(side="left", padx=(self.PAD_X,self.PAD_X/2), pady=self.PAD_Y/2) # Added Y padding for button


        # Scrollable list for all goals
        self.all_goals_list_scrollable_frame = ctk.CTkScrollableFrame(self.goals_tab_content_frame, corner_radius=self.CORNER_RADIUS, fg_color="transparent")
        self.all_goals_list_scrollable_frame.grid(row=1, column=0, columnspan=2, padx=self.PAD_X/2, pady=self.PAD_Y/2, sticky="nsew")
        self.goals_tab_content_frame.grid_rowconfigure(1, weight=1) # Ensure the list expands

        # Define a common style for goal item list entries (fg_color for light/dark)
        self.goal_item_fg_color = ("#F0F0F0", "#2C2F33") # Light gray for light, dark slate for dark
        self.goal_item_hover_color = ("#E0E0E0", "#3C3F43")
        self.button_in_list_fg_color = ("#606060", "#A0A0A0") # Darker gray for light, lighter gray for dark
        self.button_in_list_hover_color = ("#707070", "#B0B0B0")
        self.button_in_list_text_color = ("#FFFFFF", "#1E1E1E")

        # --- Feedback Tab Content (Previously bottom_frame content) ---
        self.feedback_tab_content_frame = ctk.CTkFrame(self.feedback_tab, fg_color="transparent")
        self.feedback_tab_content_frame.pack(fill="both", expand=True, padx=self.PAD_X/2, pady=self.PAD_Y/2)

        self.active_goal_display_label = ctk.CTkLabel(self.feedback_tab_content_frame, text="Active Goal for Feedback: None", font=ctk.CTkFont(size=14, weight="bold"), wraplength=730) # Increased size
        self.active_goal_display_label.pack(pady=self.PAD_Y, fill="x")

        self.feedback_controls_frame = ctk.CTkFrame(self.feedback_tab_content_frame, corner_radius=self.CORNER_RADIUS, border_width=self.FRAME_BORDER_WIDTH)
        self.feedback_controls_frame.pack(pady=self.PAD_Y/2, fill="x")

        ctk.CTkLabel(self.feedback_controls_frame, text="Freq:").pack(side="left", padx=(self.PAD_X,self.PAD_X/4))
        self.feedback_frequency_options = ["Off", "15s", "30s", "1m", "2m", "5m"]
        self.feedback_frequency_map = {"Off": 0, "15s": 15, "30s": 30, "1m": 60, "2m": 120, "5m": 300}
        self.feedback_frequency_var = ctk.StringVar(value="30s")
        self.feedback_frequency_menu = ctk.CTkOptionMenu(self.feedback_controls_frame, 
                                                       values=self.feedback_frequency_options, 
                                                       variable=self.feedback_frequency_var,
                                                       corner_radius=self.CORNER_RADIUS)
        self.feedback_frequency_menu.pack(side="left", padx=self.PAD_X/2)
        self.feedback_frequency_var.trace_add("write", self._app_handle_feedback_settings_update) # Trace added

        ctk.CTkLabel(self.feedback_controls_frame, text="Type:").pack(side="left", padx=(self.PAD_X*1.5, self.PAD_X/4))
        self.feedback_type_options = ["Brief", "Normal", "Detailed"]
        self.feedback_type_var = ctk.StringVar(value="Normal")
        self.feedback_type_menu = ctk.CTkOptionMenu(self.feedback_controls_frame, 
                                                  values=self.feedback_type_options,
                                                  variable=self.feedback_type_var,
                                                  corner_radius=self.CORNER_RADIUS)
        self.feedback_type_menu.pack(side="left", padx=self.PAD_X/2)
        self.feedback_type_var.trace_add("write", self._app_handle_feedback_settings_update) # Trace added

        # Screenshot Analysis Toggle
        self.screenshot_analysis_enabled_var = ctk.BooleanVar(value=False) # Default to False
        self.current_screenshot_analysis_enabled = False # Initial state
        self.screenshot_analysis_toggle_checkbox = ctk.CTkCheckBox(self.feedback_controls_frame,
                                                                  text="Enable Screenshot Analysis",
                                                                  variable=self.screenshot_analysis_enabled_var,
                                                                  command=self._app_handle_screenshot_toggle,
                                                                  corner_radius=self.CORNER_RADIUS)
        self.screenshot_analysis_toggle_checkbox.pack(side="left", padx=(self.PAD_X*1.5, self.PAD_X/2))


        self.llm_status_label = ctk.CTkLabel(self.feedback_tab_content_frame, text="LLM Status: Initializing...", font=ctk.CTkFont(size=11))
        self.llm_status_label.pack(pady=(self.PAD_Y/2,0), fill="x")
        
        # Screenshot Analysis Status Label (moved from llm_interaction_loop)
        self.screenshot_analysis_status_label = ctk.CTkLabel(self.feedback_tab_content_frame, 
                                                             text="Screenshot Analysis: Idle", 
                                                             font=ctk.CTkFont(size=11), 
                                                             wraplength=730)
        self.screenshot_analysis_status_label.pack(pady=(0, self.PAD_Y/2), fill="x")

        self.feedback_scrollable_frame = ctk.CTkScrollableFrame(self.feedback_tab_content_frame, corner_radius=self.CORNER_RADIUS, fg_color="transparent")
        self.feedback_scrollable_frame.pack(pady=self.PAD_Y, padx=0, fill="both", expand=True)
        
        self.feedback_label = ctk.CTkLabel(self.feedback_scrollable_frame, text="AI Feedback: ...", 
                                          wraplength=700, 
                                          justify="left", font=ctk.CTkFont(size=13)) # Increased size
        self.feedback_label.pack(pady=self.PAD_X/2, padx=self.PAD_X/2, fill="both", expand=True)

        # --- Visualizations Tab Content ---
        self.visualizations_content_frame = ctk.CTkFrame(self.visualizations_tab, fg_color="transparent")
        self.visualizations_content_frame.pack(fill="both", expand=True, padx=self.PAD_X/2, pady=self.PAD_Y/2)

        # --- Visualizations Tab: Controls ---
        self.viz_controls_frame = ctk.CTkFrame(self.visualizations_content_frame, corner_radius=self.CORNER_RADIUS, border_width=self.FRAME_BORDER_WIDTH)
        self.viz_controls_frame.pack(pady=self.PAD_Y, padx=self.PAD_X/2, fill="x")

        ctk.CTkLabel(self.viz_controls_frame, text="Project:").pack(side="left", padx=(self.PAD_X, self.PAD_X/4))
        self.viz_project_selector = ctk.CTkComboBox(self.viz_controls_frame, values=["Loading...", "All Projects"], command=self.on_viz_controls_changed, width=180, corner_radius=self.CORNER_RADIUS)
        self.viz_project_selector.pack(side="left", padx=(0,self.PAD_X))
        self.viz_project_selector.set("All Projects") # Default to all projects

        ctk.CTkLabel(self.viz_controls_frame, text="Period:").pack(side="left", padx=(self.PAD_X, self.PAD_X/4))
        self.viz_period_options = ["Specific Day", "Last 7 Days", "Last 30 Days"] # Add more later if needed
        self.viz_period_var = ctk.StringVar(value=self.viz_period_options[0])
        self.viz_period_selector = ctk.CTkOptionMenu(self.viz_controls_frame, 
                                                     values=self.viz_period_options,
                                                     variable=self.viz_period_var,
                                                     command=lambda event: self.on_viz_controls_changed(event),
                                                     corner_radius=self.CORNER_RADIUS)
        self.viz_period_selector.pack(side="left", padx=(0,self.PAD_X))
        
        # Date entry for "Specific Day"
        self.viz_date_label = ctk.CTkLabel(self.viz_controls_frame, text="Date (YYYY-MM-DD):")
        self.viz_date_label.pack(side="left", padx=(self.PAD_X, self.PAD_X/4))
        
        self.viz_date_entry = ctk.CTkEntry(self.viz_controls_frame, placeholder_text="YYYY-MM-DD", width=120, corner_radius=self.CORNER_RADIUS)
        self.viz_date_entry.insert(0, dt_date.today().strftime("%Y-%m-%d"))
        self.viz_date_entry.pack(side="left", padx=(0, self.PAD_X/2))

        self.viz_today_button = ctk.CTkButton(self.viz_controls_frame, text="Today", command=self.set_viz_date_to_today, width=60, corner_radius=self.CORNER_RADIUS)
        self.viz_today_button.pack(side="left", padx=(0, self.PAD_X))
        
        self.viz_refresh_button = ctk.CTkButton(self.viz_controls_frame, text="Refresh Chart", command=self.refresh_visualizations_chart, corner_radius=self.CORNER_RADIUS, font=ctk.CTkFont(weight="bold")) # Bold text
        self.viz_refresh_button.pack(side="left", padx=(self.PAD_X, self.PAD_X/2), pady=self.PAD_Y/2, ipady=self.PAD_Y/4) # Added Y padding

        # --- Visualizations Tab: Chart Area ---
        self.viz_chart_frame = ctk.CTkFrame(self.visualizations_content_frame, fg_color="transparent", corner_radius=self.CORNER_RADIUS)
        self.viz_chart_frame.pack(fill="both", expand=True, padx=self.PAD_X/2, pady=(0,self.PAD_Y/2))
        
        # Update Matplotlib chart style for better theme integration
        # Determine colors based on appearance mode for chart
        current_appearance = ctk.get_appearance_mode().lower()
        if current_appearance == "dark":
            chart_bg_color = "#2B2B2B" # A common dark background
            text_color = "#DCE4EE"    # A light text color for dark background
            grid_color = "#4A4A4A"    # A subtle grid color
        else: # Light mode or system (assuming light)
            chart_bg_color = "#E0E0E0" # A light gray background
            text_color = "#1F1F1F"    # A dark text color for light background
            grid_color = "#C0C0C0"    # A subtle grid color for light

        self.fig = Figure(figsize=(5, 4), dpi=100, facecolor=chart_bg_color)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor(chart_bg_color)
        
        self.ax.set_xlabel("Application", color=text_color)
        self.ax.set_ylabel("Time (seconds)", color=text_color)
        
        self.ax.tick_params(axis='x', colors=text_color, labelrotation=45) # Rotate labels for readability
        self.ax.tick_params(axis='y', colors=text_color)
        
        self.ax.title.set_color(text_color)
        # self.ax.set_title("App Usage") # Title is set in refresh_visualizations_chart

        # Set color for spines (the box around the chart)
        self.ax.spines['bottom'].set_color(grid_color)
        self.ax.spines['top'].set_color(grid_color) 
        self.ax.spines['right'].set_color(grid_color)
        self.ax.spines['left'].set_color(grid_color)
        
        # Add a grid for better readability
        self.ax.grid(True, color=grid_color, linestyle='--', linewidth=0.5)
        self.fig.tight_layout() # Adjust layout to prevent labels from being cut off

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.viz_chart_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(side="top", fill="both", expand="True")
        # self.canvas.draw() # Initial draw can be empty or placeholder - will be drawn by refresh_visualizations_chart

        # --- Internal State ---
        self.last_feedback_generation_time = 0 # Moved here for early initialization

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
        # self.last_feedback_generation_time = 0 # For text-only feedback # MOVED EARLIER
        
        self.load_initial_data() # This will also populate project filters
        self.populate_viz_project_selector() # New call
        self.on_viz_controls_changed() # Call to set initial visibility of date entry

        self.tracking_active = True
        # self.app_tracker_thread = threading.Thread(target=self.update_active_app_display_and_log_activity, daemon=True) # REMOVED
        # self.app_tracker_thread.start() # REMOVED
        self.after(1000, self.update_active_app_display_and_log_activity) # ADDED - Start the loop in the main thread

        self.llm_thread = None # Will be initialized after LLM handler is ready
        self.initialize_llm_handler_and_loop()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Initial population of the goals tab
        self.refresh_goals_tab_display()
        self._app_handle_screenshot_toggle() # Call to set initial button state

        # --- Nudge System Components ---
        self.nudge_enabled = True
        self.last_nudge_times = {}  # app_name -> last nudge timestamp
        self.nudge_cooldown = 60  # 1 minutes in seconds
        self.nudge_snooze_until = None
        self.nudge_snooze_duration = 180  # 5 minutes in seconds
        self.unproductive_apps = set()  # Track apps marked as unproductive
        self.nudge_history = []  # Track nudge effectiveness
        self.current_nudge_popup = None  # Track current popup
        self.last_nudge_check_time = 0  # Track last nudge check
        self.nudge_check_interval = 15  # Check for nudges every 15 seconds

        # --- Nudge UI Elements ---
        self.nudge_frame = ctk.CTkFrame(self, corner_radius=self.CORNER_RADIUS, border_width=self.FRAME_BORDER_WIDTH)
        self.nudge_frame.pack(pady=self.PAD_Y, padx=self.PAD_X, fill="x")
        
        self.nudge_status_label = ctk.CTkLabel(self.nudge_frame, text="Nudge System: Active", font=ctk.CTkFont(size=12))
        self.nudge_status_label.pack(side="left", padx=self.PAD_X)
        
        self.nudge_toggle = ctk.CTkSwitch(self.nudge_frame, text="Enable Nudges", command=self._toggle_nudge_system)
        self.nudge_toggle.select()  # Default to enabled
        self.nudge_toggle.pack(side="right", padx=self.PAD_X)
        
        self.nudge_message_label = ctk.CTkLabel(self.nudge_frame, text="", wraplength=700, justify="left")
        self.nudge_message_label.pack(fill="x", padx=self.PAD_X, pady=self.PAD_Y/2)
        
        self.nudge_controls_frame = ctk.CTkFrame(self.nudge_frame, fg_color="transparent")
        self.nudge_controls_frame.pack(fill="x", padx=self.PAD_X)
        
        self.snooze_button = ctk.CTkButton(self.nudge_controls_frame, text="Snooze 30m", 
                                          command=self._snooze_nudge,
                                          width=100,
                                          corner_radius=self.CORNER_RADIUS)
        self.snooze_button.pack(side="right", padx=self.PAD_X)
        
        self.dismiss_button = ctk.CTkButton(self.nudge_controls_frame, text="Dismiss", 
                                           command=self._dismiss_nudge,
                                           width=100,
                                           corner_radius=self.CORNER_RADIUS)
        self.dismiss_button.pack(side="right", padx=self.PAD_X)

    def set_viz_date_to_today(self):
        today_str = dt_date.today().strftime("%Y-%m-%d")
        self.viz_date_entry.delete(0, ctk.END)
        self.viz_date_entry.insert(0, today_str)
        self.refresh_visualizations_chart()

    def initialize_llm_handler_and_loop(self):
        """Initializes the LLM handler and starts the feedback loop in a separate thread."""
        try:
            # self.llm_status_label.configure(text="LLM Status: Loading model & Connecting to Ollama...")
            self.llm_status_label.configure(text="LLM Status: Loading local model...")
            self.llm_handler = get_llm_handler() # This initializes Llama CPP client and checks status
            
            # Check if handler initialized 
            # The LLMHandler constructor now attempts to load the model.
            # We rely on _initialized flag and that llm object exists.
            if self.llm_handler and self.llm_handler._initialized and self.llm_handler.llm:
                # The llm_handler prints detailed status/warnings to console.
                self.llm_status_label.configure(text=f"LLM Status: Ready (Model: {self.llm_handler.text_model_name})")
                if not self.llm_thread or not self.llm_thread.is_alive():
                    self.llm_thread = threading.Thread(target=self.llm_interaction_loop, daemon=True)
                    self.llm_thread.start()
            else:
                # This case might be hit if model loading fails in __init__
                self.llm_status_label.configure(text="LLM Status: Error - Model not loaded. Check model path & console.")
                messagebox.showerror("LLM Error", f"The LLM (model: {self.llm_handler.text_model_name if self.llm_handler else 'Unknown'}) failed to load. Please ensure the model file is correctly placed in the 'models' directory and is not a placeholder. Check console for more details.")

        except Exception as e:
            # full_error_msg = f"Failed to initialize LLM/Ollama: {e}"
            full_error_msg = f"Failed to initialize LLM (Llama CPP): {e}"
            print(full_error_msg)
            # Display a more user-friendly part of the error in UI
            self.llm_status_label.configure(text=f"LLM Status: Error - {str(e)[:100]}")

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
            goal_item_frame = ctk.CTkFrame(self.all_goals_list_scrollable_frame, 
                                             corner_radius=self.CORNER_RADIUS-2, # Slightly less radius for inner items
                                             fg_color=self.goal_item_fg_color, 
                                             border_width=1, 
                                             border_color=("#D0D0D0", "#3A3A3A")) 
            goal_item_frame.pack(fill="x", pady=(self.PAD_Y/3, 0), padx=self.PAD_X/3) # Reduced Y padding between items

            project_name = project_id_to_name_map.get(goal_obj.project_id, "Unknown Project")
            
            status_text = "Pending"
            if goal_obj.completed_at:
                status_text = f"Completed ({goal_obj.completed_at.strftime('%Y-%m-%d')})"
            elif goal_obj.id == self.globally_active_goal_id:
                status_text = "Active for Feedback"

            info_text = f"Goal: {goal_obj.text}\nProject: {project_name}\nStatus: {status_text}\nCreated: {goal_obj.created_at.strftime('%Y-%m-%d %H:%M')}"
            
            info_label = ctk.CTkLabel(goal_item_frame, text=info_text, wraplength=550, justify="left") # Adjusted wraplength
            info_label.pack(side="left", padx=self.PAD_X, pady=self.PAD_Y, expand=True, fill="x")

            # Add action buttons (Set Active, Complete) to the Goals tab as well
            action_button_frame = ctk.CTkFrame(goal_item_frame, fg_color="transparent")
            action_button_frame.pack(side="right", padx=self.PAD_X/2, pady=self.PAD_Y/2, fill="y") # Fill Y to center buttons

            button_width = 90 # Standardized button width
            if not goal_obj.completed_at:
                if goal_obj.id != self.globally_active_goal_id:
                    set_active_btn = ctk.CTkButton(action_button_frame, text="Set Active", 
                                                     width=button_width, 
                                                     corner_radius=self.CORNER_RADIUS-2,
                                                     # fg_color=self.button_in_list_fg_color, 
                                                     # hover_color=self.button_in_list_hover_color,
                                                     # text_color=self.button_in_list_text_color,
                                                     fg_color="transparent", 
                                                     border_width=1,
                                                     border_color=self.button_in_list_fg_color, # Use the defined color for border
                                                     hover_color=self.button_in_list_hover_color, # Use defined for hover
                                                     text_color=self.button_in_list_fg_color, # Use defined for text
                                                     font=ctk.CTkFont(size=12), # Explicit font for list buttons
                                                     command=lambda g_id=goal_obj.id: self.set_globally_active_goal_action_from_goals_tab(g_id))
                    set_active_btn.pack(pady=self.PAD_Y/3, padx=self.PAD_X/3)
                
                complete_btn = ctk.CTkButton(action_button_frame, text="Complete", 
                                               width=button_width,
                                               corner_radius=self.CORNER_RADIUS-2,
                                               # fg_color=self.button_in_list_fg_color,
                                               # hover_color=self.button_in_list_hover_color,
                                               # text_color=self.button_in_list_text_color,
                                               fg_color="transparent", 
                                               border_width=1,
                                               border_color=self.button_in_list_fg_color,
                                               hover_color=self.button_in_list_hover_color,
                                               text_color=self.button_in_list_fg_color,
                                               font=ctk.CTkFont(size=12),
                                               command=lambda g_id=goal_obj.id: self.complete_goal_action_from_goals_tab(g_id))
                complete_btn.pack(pady=self.PAD_Y/3, padx=self.PAD_X/3)
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
            goal_frame = ctk.CTkFrame(self.goals_list_frame, 
                                      corner_radius=self.CORNER_RADIUS-2, 
                                      fg_color=self.goal_item_fg_color,
                                      border_width=1,
                                      border_color=("#D0D0D0", "#3A3A3A"))
            goal_frame.pack(fill="x", pady=(self.PAD_Y/3,0), padx=self.PAD_X/3)

            status = "Completed" if goal_obj.completed_at else "Pending"
            goal_text_display = f"{goal_obj.text} (Status: {status})"
            if goal_obj.id == self.globally_active_goal_id:
                goal_text_display += " [ACTIVE FEEDBACK]"
            
            label_width = 280 # Default from before
            if self.goals_list_frame.winfo_width() > 350: # basic attempt to make it wider if space
                label_width = self.goals_list_frame.winfo_width() - 100 # Subtract button/padding approx

            ctk.CTkLabel(goal_frame, text=goal_text_display, wraplength=label_width, justify="left").pack(side="left", padx=self.PAD_X, pady=self.PAD_Y, expand=True, fill="x")

            button_frame = ctk.CTkFrame(goal_frame, fg_color="transparent") # fg_color="transparent"
            button_frame.pack(side="right", padx=self.PAD_X/2, pady=self.PAD_Y/2, fill="y") # Fill Y

            button_width = 90 # Standardized width
            if not goal_obj.completed_at:
                if goal_obj.id != self.globally_active_goal_id:
                    set_active_btn = ctk.CTkButton(button_frame, text="Set Active", 
                                                 width=button_width,
                                                 corner_radius=self.CORNER_RADIUS-2,
                                                 # fg_color=self.button_in_list_fg_color, 
                                                 # hover_color=self.button_in_list_hover_color,
                                                 # text_color=self.button_in_list_text_color,
                                                 fg_color="transparent", 
                                                 border_width=1,
                                                 border_color=self.button_in_list_fg_color, # Use the defined color for border
                                                 hover_color=self.button_in_list_hover_color, # Use defined for hover
                                                 text_color=self.button_in_list_fg_color, # Use defined for text
                                                 font=ctk.CTkFont(size=12), # Explicit font
                                                 command=lambda g_id=goal_obj.id: self.set_globally_active_goal_action(g_id))
                    set_active_btn.pack(pady=self.PAD_Y/3, padx=self.PAD_X/3)
                else: # If it IS the active goal, maybe show a "Deactivate" or it's implicitly handled by setting another
                    pass

                complete_btn = ctk.CTkButton(button_frame, text="Complete", 
                                               width=button_width,
                                               corner_radius=self.CORNER_RADIUS-2,
                                               # fg_color=self.button_in_list_fg_color,
                                               # hover_color=self.button_in_list_hover_color,
                                               # text_color=self.button_in_list_text_color,
                                               fg_color="transparent", 
                                               border_width=1,
                                               border_color=self.button_in_list_fg_color,
                                               hover_color=self.button_in_list_hover_color,
                                               text_color=self.button_in_list_fg_color,
                                               font=ctk.CTkFont(size=12),
                                               command=lambda g_id=goal_obj.id: self.complete_goal_action(g_id))
                complete_btn.pack(pady=self.PAD_Y/3, padx=self.PAD_X/3)

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
        if not self.tracking_active:
            return

        active_info = get_active_application_info()

        if active_info:
            app_name = active_info.get("name", "Unknown App")
            window_title = active_info.get("window_title", "Unknown Window")
            detailed_context = active_info.get("detailed_context", "N/A") 
        else:
            app_name = "N/A"
            window_title = "N/A"
            detailed_context = "N/A"

        # --- Update UI Labels ---
        self.last_app_name_for_ui = app_name
        self.last_window_title_for_ui = window_title
        self.last_detailed_context_for_ui = detailed_context

        if hasattr(self, 'active_app_label'):
            self.active_app_label.configure(text=f"App: {app_name}")
            self.active_window_label.configure(text=f"Window: {window_title}")
            self.detailed_context_label.configure(text=f"Context: {detailed_context if detailed_context not in [None, 'N/A'] else '...'}")
        
        # Check if we should show a nudge (only every 15 seconds)
        current_time = time.time()
        if current_time - self.last_nudge_check_time >= self.nudge_check_interval:
            if self._should_nudge(app_name, window_title, detailed_context):
                print(f"Should show nudge for app: {app_name}")
                self._show_nudge(app_name, window_title, detailed_context)
            self.last_nudge_check_time = current_time
        
        # --- Activity Logging Logic ---
        goal_id_to_log = self.globally_active_goal_id
        
        # Determine if a log should occur
        should_log = False
        if goal_id_to_log is not None:
            if (app_name != self.last_logged_app_name or
                window_title != self.last_logged_window_title or
                detailed_context != self.last_logged_detailed_context or
                goal_id_to_log != self.last_logged_goal_id):
                
                if not (app_name in ["None", "N/A"] and self.last_logged_app_name in ["None", "N/A"]):
                    should_log = True
        
        if should_log:
            project_id_to_log = self.globally_active_goal_project_id

            if goal_id_to_log and project_id_to_log is None:
                active_goal_obj = get_goal_by_id(goal_id_to_log)
                if active_goal_obj:
                    project_id_to_log = active_goal_obj.project_id
            
            if goal_id_to_log and project_id_to_log:
                add_activity_log(
                    goal_id=goal_id_to_log,
                    project_id=project_id_to_log,
                    app_name=app_name,
                    window_title=window_title,
                    detailed_context=detailed_context
                )
                print(f"Logging activity: App: {app_name}, Win: {window_title}, Ctx: {detailed_context} for Goal ID {goal_id_to_log} (Project ID: {project_id_to_log})")
            else:
                print(f"Skipping log: App: {app_name}, Win: {window_title}. Active Goal ID: {goal_id_to_log}, Project ID for Goal: {project_id_to_log} (might be missing).")

            self.last_logged_app_name = app_name
            self.last_logged_window_title = window_title
            self.last_logged_detailed_context = detailed_context
            self.last_logged_goal_id = goal_id_to_log
        
        # Reschedule this method to run again
        self.after(1000, self.update_active_app_display_and_log_activity)

    def llm_interaction_loop(self):
        # Initial status update
        try:
            if not self.llm_handler or not self.llm_handler._initialized or not self.llm_handler.llm:
                self.after(0, lambda: self.llm_status_label.configure(text="LLM Status: Initializing..."))
                self.initialize_llm_handler_and_loop()
                return
            else:
                self.after(0, lambda: self.llm_status_label.configure(text=f"LLM Status: Ready (Model: {self.llm_handler.text_model_name})"))
        except Exception as e:
            self.after(0, lambda: self.llm_status_label.configure(text=f"LLM Status: Error - {str(e)[:100]}"))
            print(f"LLM handler check failed in loop: {e}")
            time.sleep(5)
            if self.tracking_active:
                self.llm_thread = threading.Thread(target=self.llm_interaction_loop, daemon=True)
                self.llm_thread.start()
            return

        loop_interval = 1

        while self.tracking_active:
            current_time = time.time()
            time_since_last_feedback = current_time - self.last_feedback_generation_time

            if not self.llm_handler or not self.llm_handler._initialized:
                print("LLM Handler not ready in main loop, attempting re-init and skipping cycle.")
                self.after(0, lambda: self.llm_status_label.configure(text="LLM Status: Model not loaded. Waiting..."))
                time.sleep(loop_interval * 2)
                continue
            else:
                current_status = self.llm_status_label.cget("text")
                expected_status = f"LLM Status: Ready (Model: {self.llm_handler.text_model_name})"
                if current_status != expected_status and "Error" not in current_status:
                    if self.llm_handler.llm:
                        self.after(0, lambda: self.llm_status_label.configure(text=expected_status))
                    elif "Error" not in current_status:
                        self.after(0, lambda: self.llm_status_label.configure(text="LLM Status: Model not loaded. Check logs."))

            user_goal_for_feedback = self.globally_active_goal_text
            active_goal_id = self.globally_active_goal_id

            if self.current_feedback_frequency_seconds == 0:
                if self.feedback_label.cget("text") != "AI Feedback: Turned off (Set a frequency).":
                    self.after(0, lambda: self.feedback_label.configure(text="AI Feedback: Turned off (Set a frequency)."))
                if self.screenshot_analysis_status_label.cget("text") != "Screenshot Analysis: Disabled by user.":
                    self.after(0, lambda: self.screenshot_analysis_status_label.configure(text="Screenshot Analysis: Disabled by user."))
                self.last_feedback_generation_time = current_time
                time.sleep(loop_interval)
                continue

            if not active_goal_id or user_goal_for_feedback == "None":
                if self.feedback_label.cget("text") != "AI Feedback: Set an active goal for feedback.":
                    self.after(0, lambda: self.feedback_label.configure(text="AI Feedback: Set an active goal for feedback."))
                if self.screenshot_analysis_status_label.cget("text") != "Screenshot Analysis: Disabled by user.":
                    self.after(0, lambda: self.screenshot_analysis_status_label.configure(text="Screenshot Analysis: Disabled by user."))
                self.last_feedback_generation_time = current_time
                time.sleep(loop_interval)
                continue

            # Skip LLM processing if both context and window title are empty/N/A
            if (not self.last_detailed_context_for_ui or self.last_detailed_context_for_ui == "N/A") and \
               (not self.last_window_title_for_ui or self.last_window_title_for_ui == "N/A"):
                if self.feedback_label.cget("text") != "AI Feedback: Waiting for active window content...":
                    self.after(0, lambda: self.feedback_label.configure(text="AI Feedback: Waiting for active window content..."))
                self.last_feedback_generation_time = current_time
                time.sleep(loop_interval)
                continue

            ready_for_action = (current_time - self.last_feedback_generation_time) >= self.current_feedback_frequency_seconds

            if ready_for_action:
                print(f"LLM Loop: Ready for feedback cycle. Goal: {user_goal_for_feedback}")
                self.after(0, lambda: self.feedback_label.configure(text=f"AI Feedback: Preparing feedback for '{user_goal_for_feedback}'..."))

                current_visual_analysis_result = None
                processed_manual_screenshot = False

                if self.current_screenshot_analysis_enabled:
                    if hasattr(self, 'last_screenshot_analysis_result') and self.last_screenshot_analysis_result is not None:
                        print("LLM Loop: Using manually triggered screenshot analysis result.")
                        current_visual_analysis_result = self.last_screenshot_analysis_result
                        self.last_screenshot_analysis_result = None
                        processed_manual_screenshot = True
                        status_text = f"Screenshot Analysis: Used manual result ({current_visual_analysis_result[:60]}{'...' if len(current_visual_analysis_result) > 60 else ''})."
                        self.after(0, lambda text=status_text: self.screenshot_analysis_status_label.configure(text=text))
                    elif self.current_feedback_frequency_seconds > 0:
                        self.after(0, lambda: self.screenshot_analysis_status_label.configure(text="Screenshot Analysis (Auto): Capturing..."))
                        screenshot_path_auto = None
                        try:
                            screenshot_path_auto = capture_active_window_to_temp_file()
                            if screenshot_path_auto:
                                self.after(0, lambda: self.screenshot_analysis_status_label.configure(text=f"Screenshot Analysis (Auto): Analyzing '{os.path.basename(screenshot_path_auto)}'..."))
                                analysis_result_auto = self.llm_handler.analyze_screenshot_with_mtmd(screenshot_path_auto, user_goal_for_feedback)
                                current_visual_analysis_result = analysis_result_auto
                                display_text_auto = "Screenshot Analysis (Auto): Failed or no result."
                                if analysis_result_auto:
                                    display_text_auto = f"Screenshot Analysis (Auto): {analysis_result_auto[:70]}{'...' if len(analysis_result_auto) > 70 else ''}"
                                self.after(0, lambda text=display_text_auto: self.screenshot_analysis_status_label.configure(text=text))
                            else:
                                self.after(0, lambda: self.screenshot_analysis_status_label.configure(text="Screenshot Analysis (Auto): Capture failed."))
                        except Exception as e_ss_auto:
                            print(f"Error during automatic screenshot capture/analysis: {e_ss_auto}")
                            error_text = f"Screenshot Analysis Error (Auto): {str(e_ss_auto)[:60]}..."
                            self.after(0, lambda text=error_text: self.screenshot_analysis_status_label.configure(text=text))
                        finally:
                            if screenshot_path_auto and os.path.exists(screenshot_path_auto):
                                try:
                                    os.remove(screenshot_path_auto)
                                    print(f"Cleaned up auto temp screenshot: {screenshot_path_auto}")
                                except OSError as e_del_auto:
                                    print(f"Error deleting auto temp screenshot {screenshot_path_auto}: {e_del_auto}")
                else:
                    if not processed_manual_screenshot:
                        current_status = self.screenshot_analysis_status_label.cget("text")
                        if current_status != "Screenshot Analysis: Disabled by user.":
                             self.after(0, lambda: self.screenshot_analysis_status_label.configure(text="Screenshot Analysis: Disabled by user."))
                    current_visual_analysis_result = None
                
                try:
                    final_feedback_text = self.llm_handler.generate_feedback(
                        active_app_name=self.last_app_name_for_ui,
                        window_title=self.last_window_title_for_ui,
                        user_goal=user_goal_for_feedback,
                        feedback_type=self.current_feedback_type,
                        detailed_context=self.last_detailed_context_for_ui,
                        visual_analysis_result=current_visual_analysis_result
                    )
                    display_text_feedback = f"AI Feedback (Goal: '{user_goal_for_feedback}'):\n{final_feedback_text}"
                    self.after(0, lambda text=display_text_feedback: self.feedback_label.configure(text=text))
                    self.last_feedback_generation_time = current_time
                except Exception as e_feedback:
                    print(f"Error during feedback generation in LLM loop: {e_feedback}")
                    error_feedback_text = f"AI Feedback: Error generating feedback - {str(e_feedback)[:60]}"
                    self.after(0, lambda text=error_feedback_text: self.feedback_label.configure(text=text))
                    self.last_feedback_generation_time = current_time

            time.sleep(loop_interval)

    def _app_handle_feedback_settings_update(self, *args): # Renamed and accepts *args for trace
        self.current_feedback_frequency_seconds = self.feedback_frequency_map.get(self.feedback_frequency_var.get(), 30)
        self.current_feedback_type = self.feedback_type_var.get()
        print(f"Feedback settings updated: Frequency: {self.current_feedback_frequency_seconds}s, Type: {self.current_feedback_type}")
        # Reset timer to apply new frequency immediately for next feedback
        self.last_feedback_generation_time = 0 

    def _app_handle_screenshot_toggle(self, *args):
        self.current_screenshot_analysis_enabled = self.screenshot_analysis_enabled_var.get()
        print(f"Screenshot analysis enabled: {self.current_screenshot_analysis_enabled}")

        # Guard access to analyze_window_button as it's created before this might be called by checkbox init
        if hasattr(self, 'analyze_window_button'):
            if self.current_screenshot_analysis_enabled:
                self.analyze_window_button.configure(state="normal")
            else:
                self.analyze_window_button.configure(state="disabled")

        # Guard access to screenshot_analysis_status_label, as it might not exist if command fires early
        if hasattr(self, 'screenshot_analysis_status_label'):
            if self.current_screenshot_analysis_enabled:
                current_status = self.screenshot_analysis_status_label.cget("text")
                if current_status == "Screenshot Analysis: Disabled by user." or \
                   current_status == "Screenshot Analysis: Idle (feedback off)." or \
                   current_status == "Screenshot Analysis: Idle (no active goal)." :
                    self.screenshot_analysis_status_label.configure(text="Screenshot Analysis: Idle (Feature Enabled).")
            else:
                self.screenshot_analysis_status_label.configure(text="Screenshot Analysis: Disabled by user.")
        else:
            # This case would typically only be hit if the command fires *very* early during __init__
            # before the label is created. The explicit call at the end of __init__ will set it correctly.
            print("Warning: _app_handle_screenshot_toggle called before screenshot_analysis_status_label was created.")

        # Clear any pending manual screenshot result if user disables feature
        if not self.current_screenshot_analysis_enabled:
            if hasattr(self, 'last_screenshot_analysis_result'):
                self.last_screenshot_analysis_result = None
        
        # Reset timer to apply new settings immediately for next feedback cycle check.
        self.last_feedback_generation_time = 0

    def analyze_window_content_action_mtmd(self):
        if not self.current_screenshot_analysis_enabled:
            messagebox.showinfo("Feature Disabled", "Screenshot analysis is currently disabled. You can enable it in the Feedback tab.")
            return

        if not self.llm_handler or not self.llm_handler.vision_model_name: # Or specific check for MTMD model if vision_model_name is generic
            messagebox.showerror("LLM Error", "Visual analysis model is not available or not configured for manual analysis.")
            self.screenshot_analysis_status_label.configure(text="Screenshot Analysis: Vision model error.")
            return

        active_goal_text_for_prompt = self.globally_active_goal_text
        if not self.globally_active_goal_id or active_goal_text_for_prompt == "None":
            messagebox.showwarning("No Active Goal", "Please set an active goal before analyzing window content.")
            self.screenshot_analysis_status_label.configure(text="Screenshot Analysis: Manual trigger - No active goal.")
            return

        self.screenshot_analysis_status_label.configure(text="Screenshot Analysis (Manual): Capturing...")
        screenshot_path = None # Initialize before try block
        try:
            screenshot_path = capture_active_window_to_temp_file()
            if screenshot_path:
                self.screenshot_analysis_status_label.configure(text=f"Screenshot Analysis (Manual): Analyzing '{os.path.basename(screenshot_path)}' for goal '{active_goal_text_for_prompt}'...")
                
                # Run in a separate thread to avoid freezing UI
                def _analyze_in_thread():
                    try:
                        analysis_result = self.llm_handler.analyze_screenshot_with_mtmd(screenshot_path, active_goal_text_for_prompt)
                        if analysis_result:
                            # Store the result for the LLM loop to pick up
                            self.last_screenshot_analysis_result = analysis_result 
                            status_update_text = f"Screenshot Analysis (Manual): Ready - {analysis_result[:60]}{'...' if len(analysis_result) > 60 else ''}"
                            self.after(0, lambda: self.screenshot_analysis_status_label.configure(text=status_update_text))
                            # Trigger LLM loop to process immediately by resetting its timer
                            self.last_feedback_generation_time = 0 
                        else:
                            self.after(0, lambda: self.screenshot_analysis_status_label.configure(text="Screenshot Analysis (Manual): No result from analysis."))
                    except Exception as e_analyze:
                        print(f"Error during manual screenshot analysis thread: {e_analyze}")
                        error_text_analyze = f"Screenshot Analysis Error (Manual): {str(e_analyze)[:60]}..."
                        self.after(0, lambda: self.screenshot_analysis_status_label.configure(text=error_text_analyze))
                    finally:
                        if screenshot_path and os.path.exists(screenshot_path):
                            try:
                                os.remove(screenshot_path)
                                print(f"Cleaned up manual temp screenshot: {screenshot_path}")
                            except OSError as e_del:
                                print(f"Error deleting manual temp screenshot {screenshot_path}: {e_del}")
                
                analysis_thread = threading.Thread(target=_analyze_in_thread, daemon=True)
                analysis_thread.start()

            else:
                self.screenshot_analysis_status_label.configure(text="Screenshot Analysis (Manual): Capture failed.")
        except Exception as e:
            print(f"Error during manual screenshot capture: {e}")
            error_text = f"Screenshot Analysis Error (Manual): {str(e)[:60]}..."
            self.screenshot_analysis_status_label.configure(text=error_text)
            if screenshot_path and os.path.exists(screenshot_path): # Ensure cleanup even if analysis part not reached
                try:
                    os.remove(screenshot_path)
                except OSError as e_del_outer:
                    print(f"Error deleting temp screenshot on outer error {screenshot_path}: {e_del_outer}")

    def on_closing(self):
        print("Application closing...")
        self.tracking_active = False
        # Give threads a moment to finish their current loop iteration
        if hasattr(self, 'llm_thread') and self.llm_thread.is_alive():
            self.llm_thread.join(timeout=2.0)
        self.destroy()

    def populate_viz_project_selector(self):
        projects = get_all_projects()
        # Ensure "All Projects" is always an option
        project_names = ["All Projects"] + [p.name for p in projects if not p.is_archived] 
        # self.projects_map_viz = {p.name: p.id for p in projects if not p.is_archived} # Store IDs too

        current_val = self.viz_project_selector.get()
        self.viz_project_selector.configure(values=project_names)
        if current_val in project_names:
            self.viz_project_selector.set(current_val)
        elif project_names:
            self.viz_project_selector.set(project_names[0])
        else: # Should not happen with "All Projects"
            self.viz_project_selector.set("No Projects Yet")
        
        # self.refresh_visualizations_chart() # Refresh chart when project list updates if needed

    def on_viz_controls_changed(self, event=None):
        # This method is called when project or period selectors change.
        # We might want to refresh the chart automatically, or wait for refresh button.
        # For now, let's just print the change.
        selected_period = self.viz_period_var.get()
        if selected_period == "Specific Day":
            self.viz_date_label.pack(side="left", padx=(self.PAD_X, self.PAD_X/4), before=self.viz_refresh_button)
            self.viz_date_entry.pack(side="left", padx=(0, self.PAD_X/2), before=self.viz_refresh_button)
            self.viz_today_button.pack(side="left", padx=(0, self.PAD_X), before=self.viz_refresh_button)
        else:
            self.viz_date_label.pack_forget()
            self.viz_date_entry.pack_forget()
            self.viz_today_button.pack_forget()
            
        print(f"Viz controls changed: Project: {self.viz_project_selector.get()}, Period: {self.viz_period_var.get()}")
        # self.refresh_visualizations_chart() # Uncomment to auto-refresh

    def refresh_visualizations_chart(self):
        self.ax.clear() # Clear previous plot
        current_appearance = ctk.get_appearance_mode().lower()
        if current_appearance == "dark":
            chart_bg_color = "#2B2B2B"
            text_color = "#DCE4EE"
            grid_color = "#4A4A4A"
            bar_color = "#5699D3" # A pleasant blue for dark mode bars
        else:
            chart_bg_color = "#E0E0E0"
            text_color = "#1F1F1F"
            grid_color = "#C0C0C0"
            bar_color = "#4A88C4" # A slightly different blue for light mode bars

        self.fig.patch.set_facecolor(chart_bg_color)
        self.ax.set_facecolor(chart_bg_color)
        self.ax.tick_params(axis='x', colors=text_color)
        self.ax.tick_params(axis='y', colors=text_color)
        self.ax.title.set_color(text_color)
        self.ax.xaxis.label.set_color(text_color)
        self.ax.yaxis.label.set_color(text_color)
        self.ax.spines['bottom'].set_color(grid_color)
        self.ax.spines['top'].set_color(grid_color)
        self.ax.spines['right'].set_color(grid_color)
        self.ax.spines['left'].set_color(grid_color)
        self.ax.grid(True, color=grid_color, linestyle='--', linewidth=0.5)

        selected_period = self.viz_period_var.get()
        selected_project_name = self.viz_project_selector.get()
        
        project_id_to_viz = None
        if selected_project_name != "All Projects" and selected_project_name != "No Projects Yet" and selected_project_name != "Loading...":
            # Need to get project_id from project_name. Assuming projects_map is populated.
            # For simplicity, re-fetch all projects to create a temporary map if projects_map_viz is not robustly maintained.
            # A better approach would be to ensure self.projects_map_viz is always up-to-date.
            projects = get_all_projects()
            temp_projects_map = {p.name: p.id for p in projects}
            project_id_to_viz = temp_projects_map.get(selected_project_name)
            if not project_id_to_viz:
                messagebox.showerror("Error", f"Could not find project ID for: {selected_project_name}")
                self.ax.set_title(f"Error: Project '{selected_project_name}' not found", color=text_color)
                self.canvas.draw()
                return

        if selected_period == "Specific Day":
            try:
                date_str = self.viz_date_entry.get()
                target_date = dt_datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                messagebox.showerror("Input Error", "Invalid date format. Please use YYYY-MM-DD.")
                self.ax.set_title("Invalid Date Format", color=text_color)
                self.canvas.draw()
                return

            logs = get_activity_logs_for_day(target_date=target_date, project_id=project_id_to_viz)

            if not logs:
                self.ax.set_title(f"No activity logged for {target_date.strftime('%Y-%m-%d')}", color=text_color)
                self.ax.set_xlabel("Time of Day", color=text_color)
                self.ax.set_yticks([]) # No apps to show
                 # Set x-axis limits from 00:00 to 23:59 for an empty chart too
                start_of_day = dt_datetime.combine(target_date, dt_datetime.min.time())
                end_of_day = dt_datetime.combine(target_date, dt_datetime.max.time())
                self.ax.set_xlim(start_of_day, end_of_day)
                self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                self.ax.tick_params(axis='x', labelrotation=45)
                self.canvas.draw()
                return

            # Process logs for timeline view
            app_activity_blocks = []
            for i in range(len(logs)):
                current_log = logs[i]
                start_time = current_log.timestamp
                # Determine end time
                if i < len(logs) - 1:
                    end_time = logs[i+1].timestamp
                else:
                    # For the last log, assume it lasts until the next log would have been, or a fixed small duration.
                    # For a daily timeline, it could extend to the end of its logged minute, or a default duration if too short.
                    # A simple way: extend to end of the day, or if too long, cap it.
                    # For now, let's assume activity duration is until the next log. The last log's duration isn't explicitly defined by this model.
                    # A better approach: Each log represents a *change* of activity. So current log is active until next log.
                    # End of day for the last activity for that day.
                    end_time = dt_datetime.combine(target_date, dt_datetime.max.time())
                    # Cap duration if next log is on a different day (should not happen with get_activity_logs_for_day)
                    if end_time.date() > target_date:
                         end_time = dt_datetime.combine(target_date, dt_datetime.max.time())
                
                # If current_log and next log are too close, they might represent the same continuous activity block that was just re-logged.
                # For a simple timeline, each distinct log entry is a block. Refinements can merge these later.
                duration_seconds = (end_time - start_time).total_seconds()
                if duration_seconds <= 0 and i < len(logs) -1 : # if not the last log
                    # if a log has 0 duration and it's not the last one, likely it's a quick switch.
                    # give it a minimum visual duration, e.g. 1 minute, so it's visible
                    end_time = start_time + timedelta(seconds=60)
                elif duration_seconds <=0 and i == len(logs) -1: # last log of the day with zero/negative duration from EOD calc
                    end_time = start_time + timedelta(seconds=60) # give it min 1 min duration


                app_activity_blocks.append({
                    "app": current_log.application_name,
                    "start": start_time,
                    "end": end_time,
                    "title": current_log.window_title
                })

            # Create the timeline plot (Gantt-like)
            app_names = sorted(list(set(block["app"] for block in app_activity_blocks)))
            app_y_pos = {name: i for i, name in enumerate(app_names)}

            for block in app_activity_blocks:
                y = app_y_pos[block["app"]]
                start_dt = block["start"]
                end_dt = block["end"]
                # barh needs (y, width, left)
                self.ax.barh(y, (end_dt - start_dt), left=start_dt, height=0.6, color=bar_color, edgecolor=grid_color)
                # Optionally, add window title text to bars if space/desired
                # self.ax.text(start_dt + (end_dt - start_dt)/2, y, block["title"][:30], ha='center', va='center', fontsize=7, color=text_color_on_bar)

            self.ax.set_yticks(range(len(app_names)))
            self.ax.set_yticklabels(app_names)
            self.ax.set_xlabel("Time of Day", color=text_color)
            self.ax.set_ylabel("Application", color=text_color)
            self.ax.set_title(f"Application Timeline for {target_date.strftime('%Y-%m-%d')}", color=text_color)

            # Format X-axis for time
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            # self.ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
            self.ax.tick_params(axis='x', labelrotation=45)
            
            # Set x-axis limits from 00:00 to 23:59
            start_of_day = dt_datetime.combine(target_date, dt_datetime.min.time())
            end_of_day = dt_datetime.combine(target_date, dt_datetime.max.time())
            self.ax.set_xlim(start_of_day, end_of_day)

        else: # Existing logic for "Last 7 Days" / "Last 30 Days"
            today = dt_date.today()
            if selected_period == "Last 7 Days":
                start_date_param = today - timedelta(days=6)
                end_date_param = today + timedelta(days=1) #timedelta to include whole of today
                title = f"App Usage Last 7 Days"
            elif selected_period == "Last 30 Days":
                start_date_param = today - timedelta(days=29)
                end_date_param = today + timedelta(days=1)
                title = f"App Usage Last 30 Days"
            else:
                # Should not happen with current options
                self.ax.set_title("Invalid Period Selected", color=text_color)
                self.canvas.draw()
                return
            
            if project_id_to_viz is None and selected_project_name != "All Projects":
                messagebox.showwarning("Project Error", f"Project '{selected_project_name}' not found for aggregated view. Showing for all projects.")
            
            # Convert date objects to datetime objects for the database function call
            start_datetime_param = dt_datetime.combine(start_date_param, dt_datetime.min.time())
            end_datetime_param = dt_datetime.combine(end_date_param, dt_datetime.min.time()) # end_date is exclusive in some queries, or inclusive for others. get_aggregated expects inclusive start, exclusive end.
                                                                                          # For simplicity let's use end of selected day.
            end_datetime_param = dt_datetime.combine(today, dt_datetime.max.time()) # ensure it covers the entirety of the last day included in the period.

            if selected_project_name == "All Projects":
                # Aggregate across all projects
                all_projects_data = get_all_projects()
                aggregated_data = {}
                for p in all_projects_data:
                    if not p.is_archived:
                        project_data = get_aggregated_activity_by_app(p.id, start_datetime_param, end_datetime_param)
                        for app, duration in project_data.items():
                            aggregated_data[app] = aggregated_data.get(app, 0) + duration
                app_durations = aggregated_data
                title += " (All Projects)"
            elif project_id_to_viz:
                app_durations = get_aggregated_activity_by_app(project_id_to_viz, start_datetime_param, end_datetime_param)
                title += f" ({selected_project_name})"
            else: # Fallback or should not happen if UI is correct
                self.ax.set_title("Error determining project for aggregated view", color=text_color)
                self.canvas.draw()
                return

            if not app_durations:
                self.ax.set_title(f"No activity data for {title}", color=text_color)
            else:
                apps = list(app_durations.keys())
                times = list(app_durations.values())
                self.ax.bar(apps, times, color=bar_color)
                self.ax.set_xlabel("Application", color=text_color)
                self.ax.set_ylabel("Total Time (seconds)", color=text_color)
                self.ax.set_title(title, color=text_color)
                self.ax.tick_params(axis='x', labelrotation=45, ha="right")
        
        self.fig.tight_layout() # Adjust layout to prevent labels from being cut off
        self.canvas.draw()

    def _toggle_nudge_system(self):
        """Toggle the nudge system on/off."""
        self.nudge_enabled = self.nudge_toggle.get()
        status_text = "Active" if self.nudge_enabled else "Disabled"
        self.nudge_status_label.configure(text=f"Nudge System: {status_text}")
        if not self.nudge_enabled and self.current_nudge_popup:
            self.current_nudge_popup.destroy()
            self.current_nudge_popup = None

    def _snooze_nudge(self):
        """Snooze the current nudge for 30 minutes."""
        self.nudge_snooze_until = time.time() + self.nudge_snooze_duration
        if self.current_nudge_popup:
            self.current_nudge_popup.destroy()
            self.current_nudge_popup = None
        self.nudge_status_label.configure(text=f"Nudge System: Snoozed until {time.strftime('%H:%M', time.localtime(self.nudge_snooze_until))}")

    def _dismiss_nudge(self):
        """Dismiss the current nudge."""
        if self.current_nudge_popup:
            self.current_nudge_popup.destroy()
            self.current_nudge_popup = None
        self.nudge_status_label.configure(text="Nudge System: Active")

    def _clear_nudge_message(self):
        """Clear the current nudge message."""
        self.nudge_message_label.configure(text="")
        self.snooze_button.pack_forget()
        self.dismiss_button.pack_forget()

    def _should_nudge(self, app_name: str, window_title: str, detailed_context: str) -> bool:
        """Determine if a nudge should be shown for the current activity."""
        # Skip if both context and window title are empty/N/A
        if (not detailed_context or detailed_context == "N/A") and (not window_title or window_title == "N/A"):
            print("Skipping nudge check - empty context and window title")
            return False

        if not self.nudge_enabled:
            print("Nudge system is disabled")
            return False
            
        if self.nudge_snooze_until and time.time() < self.nudge_snooze_until:
            print(f"Nudge is snoozed until {time.strftime('%H:%M', time.localtime(self.nudge_snooze_until))}")
            return False
            
        # Check cooldown for this app
        last_nudge = self.last_nudge_times.get(app_name, 0)
        if time.time() - last_nudge < self.nudge_cooldown:
            print(f"App {app_name} is in cooldown period")
            return False
            
        # Use LLM to analyze if the activity is unproductive
        try:
            if self.llm_handler and self.llm_handler._initialized:
                print(f"Analyzing productivity for app: {app_name}, window: {window_title}")
                is_unproductive = self.llm_handler.analyze_productivity(
                    app_name=app_name,
                    window_title=window_title,
                    detailed_context=detailed_context,
                    active_goal=self.globally_active_goal_text
                )
                print(f"Productivity analysis result: {is_unproductive}")
                return is_unproductive
        except Exception as e:
            print(f"Error analyzing productivity: {e}")
            import traceback
            traceback.print_exc()
            
        return False

    def _show_nudge(self, app_name: str, window_title: str, detailed_context: str):
        """Show a nudge message for unproductive activity."""
        try:
            if self.llm_handler and self.llm_handler._initialized:
                print(f"Generating nudge message for app: {app_name}, window: {window_title}")
                nudge_message = self.llm_handler.generate_nudge_message(
                    app_name=app_name,
                    window_title=window_title,
                    detailed_context=detailed_context,
                    active_goal=self.globally_active_goal_text
                )
                
                if nudge_message:
                    print(f"Generated nudge message: {nudge_message}")
                    # Close any existing popup
                    if self.current_nudge_popup:
                        print("Closing existing popup")
                        self.current_nudge_popup.destroy()
                    
                    # Create and show new popup
                    print("Creating new nudge popup")
                    self.current_nudge_popup = NudgePopup(
                        self,
                        nudge_message,
                        on_snooze=self._snooze_nudge,
                        on_dismiss=self._dismiss_nudge
                    )
                    # Ensure the popup is visible and on top
                    self.current_nudge_popup.lift()
                    self.current_nudge_popup.focus_force()
                    
                    self.last_nudge_times[app_name] = time.time()
                    
                    # Log nudge for analytics
                    self.nudge_history.append({
                        'timestamp': time.time(),
                        'app_name': app_name,
                        'window_title': window_title,
                        'message': nudge_message,
                        'goal': self.globally_active_goal_text
                    })
                else:
                    print("No nudge message generated")
        except Exception as e:
            print(f"Error generating nudge message: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    app = App()
    app.mainloop() 