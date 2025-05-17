import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, func, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.exc import SQLAlchemyError
import datetime
import os
import time
import sys # Import sys

# Define the database URL
DATABASE_FILE = "productivity_tracker.db"

# Determine PROJECT_ROOT based on whether the app is bundled by PyInstaller
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # Running in a PyInstaller bundle
    PROJECT_ROOT = sys._MEIPASS
else:
    # Normal execution (e.g., from source)
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA_DIR = os.path.join(PROJECT_ROOT, ".data") 
DATABASE_URL = f"sqlite:///{os.path.join(DATA_DIR, DATABASE_FILE)}"

Base = declarative_base()

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=func.now())
    is_archived = Column(Boolean, default=False)
    goals = relationship("Goal", back_populates="project", cascade="all, delete-orphan")
    activity_logs = relationship("ActivityLog", back_populates="project", cascade="all, delete-orphan")

class Goal(Base):
    __tablename__ = "goals"
    id = Column(Integer, primary_key=True, index=True)
    text = Column(String, nullable=False)
    created_at = Column(DateTime, default=func.now())
    is_active = Column(Boolean, default=False, index=True) # Default to False, explicitly set one active
    completed_at = Column(DateTime, nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    project = relationship("Project", back_populates="goals")
    activity_logs = relationship("ActivityLog", back_populates="goal", cascade="all, delete-orphan")

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=func.now(), index=True)
    application_name = Column(String)
    window_title = Column(Text) # Window titles can be long
    detailed_context = Column(Text, nullable=True) # New column for URL/doc path
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False) # Denormalized for easier queries
    goal = relationship("Goal", back_populates="activity_logs")
    project = relationship("Project", back_populates="activity_logs")

engine = None
SessionLocal = None

def init_db():
    global engine, SessionLocal
    if engine is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        print(f"Database will be initialized at: {DATABASE_URL}")
        engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        print("Database initialized and tables created.")
    return SessionLocal

def get_db():
    if SessionLocal is None:
        init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Project Functions ---
def add_project(name: str):
    if not name.strip():
        print("Project name cannot be empty.")
        return None
    db_session_gen = get_db()
    db = next(db_session_gen)
    try:
        existing_project = db.query(Project).filter(Project.name == name).first()
        if existing_project:
            print(f"Project '{name}' already exists.")
            return existing_project
        new_project = Project(name=name)
        db.add(new_project)
        db.commit()
        db.refresh(new_project)
        print(f"Added new project: '{name}', ID: {new_project.id}")
        return new_project
    except SQLAlchemyError as e:
        db.rollback()
        print(f"Error adding project: {e}")
        return None
    finally:
        next(db_session_gen, None)

def get_project_by_id(project_id: int):
    db_session_gen = get_db()
    db = next(db_session_gen)
    try:
        return db.query(Project).filter(Project.id == project_id).first()
    finally:
        next(db_session_gen, None)

def get_all_projects(include_archived: bool = False):
    db_session_gen = get_db()
    db = next(db_session_gen)
    try:
        query = db.query(Project)
        if not include_archived:
            query = query.filter(Project.is_archived == False)
        return query.order_by(Project.name).all()
    finally:
        next(db_session_gen, None)

# --- Goal Functions ---
def add_goal(goal_text: str, project_id: int):
    if not goal_text.strip():
        print("Goal text cannot be empty.")
        return None
    db_session_gen = get_db()
    db = next(db_session_gen)
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            print(f"Project with ID {project_id} not found. Cannot add goal.")
            return None
        if project.is_archived:
            print(f"Project '{project.name}' is archived. Cannot add goal.")
            return None

        new_goal = Goal(text=goal_text, project_id=project_id)
        db.add(new_goal)
        db.commit()
        db.refresh(new_goal)
        print(f"Added new goal '{goal_text}' to project '{project.name}'")
        return new_goal
    except SQLAlchemyError as e:
        db.rollback()
        print(f"Error adding goal: {e}")
        return None
    finally:
        next(db_session_gen, None)

def set_active_goal(goal_id: int):
    db_session_gen = get_db()
    db = next(db_session_gen)
    try:
        db.query(Goal).filter(Goal.is_active == True).update({"is_active": False}, synchronize_session=False)
        goal_to_activate = db.query(Goal).filter(Goal.id == goal_id).first()
        if goal_to_activate:
            if goal_to_activate.completed_at:
                print(f"Goal '{goal_to_activate.text}' is completed. Cannot set as active.")
                db.rollback()
                return None
            goal_to_activate.is_active = True
            db.commit()
            db.refresh(goal_to_activate)
            print(f"Set goal '{goal_to_activate.text}' (ID: {goal_id}) as active.")
            return goal_to_activate
        else:
            print(f"Goal with ID {goal_id} not found.")
            db.rollback()
            return None
    except SQLAlchemyError as e:
        db.rollback()
        print(f"Error setting active goal: {e}")
        return None
    finally:
        next(db_session_gen, None)

def complete_goal(goal_id: int):
    db_session_gen = get_db()
    db = next(db_session_gen)
    try:
        goal = db.query(Goal).filter(Goal.id == goal_id).first()
        if goal:
            goal.completed_at = func.now()
            goal.is_active = False # A completed goal cannot be the active one
            db.commit()
            db.refresh(goal)
            print(f"Goal '{goal.text}' marked as completed.")
            return goal
        return None
    except SQLAlchemyError as e:
        db.rollback()
        print(f"Error completing goal: {e}")
        return None
    finally:
        next(db_session_gen, None)

def get_active_goal():
    db_session_gen = get_db()
    db = next(db_session_gen)
    try:
        return db.query(Goal).filter(Goal.is_active == True).order_by(Goal.created_at.desc()).first()
    finally:
        next(db_session_gen, None)

def get_goals_for_project(project_id: int, include_completed: bool = False):
    db_session_gen = get_db()
    db = next(db_session_gen)
    try:
        query = db.query(Goal).filter(Goal.project_id == project_id)
        if not include_completed:
            query = query.filter(Goal.completed_at == None)
        return query.order_by(Goal.created_at.desc()).all()
    finally:
        next(db_session_gen, None)

def get_goal_by_id(goal_id: int):
    db_session_gen = get_db()
    db = next(db_session_gen)
    try:
        return db.query(Goal).filter(Goal.id == goal_id).first()
    finally:
        next(db_session_gen, None)

# --- Activity Log Functions ---
def add_activity_log(goal_id: int, project_id: int, app_name: str, window_title: str, detailed_context: str = None):
    if not app_name and not window_title: # Don't log empty entries
        return None
    db_session_gen = get_db()
    db = next(db_session_gen)
    try:
        log_entry = ActivityLog(
            goal_id=goal_id,
            project_id=project_id,
            application_name=app_name or "N/A",
            window_title=window_title or "N/A",
            detailed_context=detailed_context # Store new context
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        # print(f"Logged activity: App: {app_name}, Window: {window_title} for goal ID {goal_id}") # Can be very verbose
        return log_entry
    except SQLAlchemyError as e:
        db.rollback()
        print(f"Error adding activity log: {e}")
        return None
    finally:
        next(db_session_gen, None)

def get_activity_logs_for_goal(goal_id: int, limit: int = 100):
    db_session_gen = get_db()
    db = next(db_session_gen)
    try:
        return db.query(ActivityLog).filter(ActivityLog.goal_id == goal_id).order_by(ActivityLog.timestamp.desc()).limit(limit).all()
    finally:
        next(db_session_gen, None)

def get_activity_logs_for_project(project_id: int, limit: int = 200):
    db_session_gen = get_db()
    db = next(db_session_gen)
    try:
        return db.query(ActivityLog).filter(ActivityLog.project_id == project_id).order_by(ActivityLog.timestamp.desc()).limit(limit).all()
    finally:
        next(db_session_gen, None)

def get_aggregated_activity_by_app(project_id: int, start_date: datetime.datetime, end_date: datetime.datetime):
    db_session_gen = get_db()
    db = next(db_session_gen)
    try:
        logs = db.query(ActivityLog).filter(
            ActivityLog.project_id == project_id,
            ActivityLog.timestamp >= start_date,
            ActivityLog.timestamp < end_date
        ).order_by(ActivityLog.timestamp.asc()).all()

        if not logs:
            return {}

        app_durations = {}
        for i in range(len(logs)):
            current_log = logs[i]
            # Determine the end time for the current_log's duration
            if i < len(logs) - 1:
                next_log_timestamp = logs[i+1].timestamp
            else:
                # For the last log in the period, its duration extends to end_date
                next_log_timestamp = end_date
            
            # Ensure duration is not negative if timestamps are unusual (e.g. next_log_timestamp is before current_log.timestamp)
            # Though order_by should prevent this for logs from DB.
            # Also, cap duration at end_date, so if next_log is past end_date, only count till end_date.
            effective_end_timestamp = min(next_log_timestamp, end_date)
            duration = (effective_end_timestamp - current_log.timestamp).total_seconds()

            if duration > 0: # Only add if duration is positive
                app_name = current_log.application_name
                app_durations[app_name] = app_durations.get(app_name, 0) + duration
        
        return app_durations
    except SQLAlchemyError as e:
        print(f"Error aggregating activity by app: {e}")
        return {}
    finally:
        next(db_session_gen, None)

# Example usage (for testing this module directly)
if __name__ == "__main__":
    print("Initializing DB for direct test...")
    init_db()

    print("\n--- Testing Project, Goal, and Detailed Activity Log Persistence ---")
    proj1 = add_project("Detailed Context Test Project")
    if not proj1:
        print("Failed to create test project. Exiting.")
        exit()

    goal1 = add_goal("Testing URL and Doc Path Logging", proj1.id)
    if not goal1:
        print("Failed to create test goal. Exiting.")
        exit()

    set_active_goal(goal1.id)
    active_g = get_active_goal()
    if not active_g or active_g.id != goal1.id:
        print("Failed to set active goal for logging test. Exiting.")
        exit()
    
    print(f"Active goal for logging: '{active_g.text}' (ID: {active_g.id}) in project '{active_g.project.name}' (ID: {active_g.project_id})")

    # Test logging activities
    log1 = add_activity_log(active_g.id, active_g.project_id, "Google Chrome", "Research - Main Page - research.com", "http://research.com")
    time.sleep(0.1) # Ensure different timestamps for testing ordering
    log2 = add_activity_log(active_g.id, active_g.project_id, "Microsoft Word", "Report_Chapter1.docx", "/Users/test/Documents/Report_Chapter1.docx")
    time.sleep(0.1)
    log3 = add_activity_log(active_g.id, active_g.project_id, "Preview", "Diagram.pdf", "/Users/test/Downloads/Diagram.pdf")
    time.sleep(0.1)
    log4 = add_activity_log(active_g.id, active_g.project_id, "Finder", "Downloads", None) # No specific detailed context

    if not all([log1, log2, log3, log4]):
        print("Failed to add all activity logs during test.")
    else:
        print("\nSuccessfully added test activity logs.")

    print(f"\n--- Activity Logs for Goal '{goal1.text}' (with detailed context) ---")
    logs_for_goal = get_activity_logs_for_goal(goal1.id, limit=10)
    if logs_for_goal:
        for log in reversed(logs_for_goal):
            print(f"  - [{log.timestamp.strftime('%H:%M:%S')}] App: {log.application_name}, Win: {log.window_title}, Context: {log.detailed_context}")
    else:
        print("No logs found for this goal.")

    print(f"\n--- Activity Logs for Project '{proj1.name}' (first 10) ---")
    logs_for_project = get_activity_logs_for_project(proj1.id, limit=10)
    if logs_for_project:
        for log in reversed(logs_for_project):
            print(f"  - [{log.timestamp.strftime('%H:%M:%S')}] GoalID:{log.goal_id}, App: {log.application_name}, Win: {log.window_title}")
    else:
        print("No logs found for this project.")

    # Cleanup: To avoid issues with subsequent tests or app runs, you might delete the test project and its related data.
    # For simplicity in this example, we are not deleting. Consider this for robust test suites.
    # To delete: db.delete(proj1); db.commit() 