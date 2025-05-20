import threading
import os
import subprocess # Added for running llama-mtmd-cli
# import base64 # No longer needed for screenshots
# from io import BytesIO # No longer needed for screenshots
# from PIL import Image # No longer needed for screenshots
from llama_cpp import Llama, LlamaGrammar # Import Llama
import time # For tests
import sys # For modifying path for testing
from typing import Optional # Added import

# --- Import new macos_context module ---
from utils import macos_context # Assuming utils is in PYTHONPATH or relative

# --- Configuration for Llama CPP Model --- 
# IMPORTANT: User needs to download the GGUF model and place it here.
# Example: gemma-2b-it.gguf or similar
# Model path should be configurable or placed in a known location.
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "models", "gemma-3-1b-it-IQ4_NL.gguf")
# Create a dummy model file if it doesn't exist for placeholder purposes. 
# The user MUST replace this with a real model.
MODELS_DIR = os.path.dirname(MODEL_PATH)
if not os.path.exists(MODELS_DIR):
    os.makedirs(MODELS_DIR)
if not os.path.exists(MODEL_PATH):
    try:
        with open(MODEL_PATH, 'w') as f:
            f.write("This is a placeholder. Replace with a real GGUF model file.")
        print(f"Created a placeholder model file at {MODEL_PATH}. YOU MUST REPLACE IT WITH A REAL MODEL.")
    except IOError as e:
        print(f"Could not create placeholder model file at {MODEL_PATH}: {e}. YOU MUST PROVIDE THE MODEL MANUALLY.")

# OLLAMA_TEXT_MODEL = "gemma3:4b" # REMOVED
# OLLAMA_MULTIMODAL_MODEL = "gemma3:4b" # REMOVED

# IMAGE_TARGET_SIZE = False # No longer needed

class LLMHandler:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(LLMHandler, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            
            print("Initializing LLMHandler with Llama CPP...")
            self.model_path = MODEL_PATH
            self.llm = None
            self.text_model_name = os.path.basename(self.model_path) # Use file name as model name
            
            try:
                if not os.path.exists(self.model_path) or os.path.getsize(self.model_path) < 1000: # Basic check for placeholder
                    print(f"ERROR: Model file not found or is a placeholder at {self.model_path}. Please download and place the correct GGUF model file.")
                    self._initialized = False # Mark as not properly initialized
                    # Optional: raise an error to be caught by UI if critical
                    # raise FileNotFoundError(f"Model file not found or is a placeholder: {self.model_path}")
                    return # Stop initialization if model isn't there

                self.llm = Llama(
                    model_path=self.model_path,
                    n_ctx=2048,  # Context window size (can be adjusted)
                    n_gpu_layers=-1, # Offload all possible layers to GPU, set to 0 for CPU only
                    verbose=True # Enable verbose logging from llama.cpp
                )
                self._initialized = True
                print(f"LLMHandler initialized with Llama CPP. Model: {self.text_model_name}")
            except Exception as e:
                print(f"Error initializing Llama CPP model: {e}")
                self._initialized = False
                # Optional: raise an error
                # raise RuntimeError(f"Failed to initialize Llama CPP model: {e}")

    def get_detailed_context_from_os(self, active_app_name: str) -> Optional[str]:
        """Attempts to get detailed context (URL, file path) from the active macOS application."""
        context = None
        app_name_lower = active_app_name.lower()

        # Make sure macos_context is available
        # This check might be redundant if imports are handled well, but good for safety
        if not macos_context:
            print("macos_context module not available.")
            return None

        try:
            if "safari" in app_name_lower:
                context = macos_context.get_safari_url()
            elif "chrome" in app_name_lower: # Covers "Google Chrome", "Chrome", etc.
                context = macos_context.get_chrome_url()
            elif "preview" in app_name_lower:
                context = macos_context.get_preview_document_path()
            elif "textedit" in app_name_lower:
                context = macos_context.get_textedit_document_path()
            # Add more app handlers here as needed
            # e.g., elif "microsoft word" in app_name_lower: context = macos_context.get_word_document_path()
        except Exception as e:
            print(f"Error getting detailed context for {active_app_name}: {e}")
        
        if context:
            print(f"Automatically fetched context for {active_app_name}: {context}")
        return context

    def check_ollama_status(self): # This method is no longer relevant, can be removed or adapted
        """Checks if the Llama CPP model was loaded successfully."""
        if self.llm and self._initialized:
            print(f"Llama CPP model '{self.text_model_name}' loaded successfully.")
            return True
        else:
            print(f"Llama CPP model '{self.text_model_name}' failed to load. Check model path and logs.")
            return False

    # def analyze_screenshot_for_productivity(self, image_path: str, user_goal: str) -> str | None: # Removed

    def analyze_screenshot_with_mtmd(self, image_path: str, user_goal: str) -> Optional[str]:
        """
        Analyzes a screenshot using llama-mtmd-cli to determine if the content
        is productive towards the user_goal.

        Args:
            image_path (str): Path to the screenshot image file.
            user_goal (str): The user's current goal.

        Returns:
            str | None: Analysis result string if successful, None otherwise.
        """
        if not self._initialized: # Check if main LLM is initialized, though this is a separate tool
            print("LLMHandler not fully initialized. Screenshot analysis might be affected if it relied on shared state (it doesn't here).")
            # We can proceed as llama-mtmd-cli is external

        if not os.path.exists(image_path):
            print(f"Screenshot Error: Image path does not exist: {image_path}")
            return None

        # --- Determine absolute paths for models ---
        # MODELS_DIR is already defined at the module level, pointing to the project's "models" directory.
        # If MODELS_DIR is not defined or accessible here, redefine it:
        # current_script_dir = os.path.dirname(os.path.abspath(__file__))
        # project_root_dir = os.path.dirname(os.path.dirname(current_script_dir))
        # models_base_dir = os.path.join(project_root_dir, "models")
        # For this case, MODELS_DIR (derived from MODEL_PATH) should be sufficient.

        llama_mtmd_cmd = "llama-mtmd-cli"
        
        # Use absolute paths for model files, assuming they are in MODELS_DIR
        # User provided model names:
        model_filename = "gemma-3-4b-it-q4_0.gguf"
        mmproj_filename = "mmproj-model-f16-4B.gguf"

        abs_model_path = os.path.join(MODELS_DIR, model_filename)
        abs_mmproj_path = os.path.join(MODELS_DIR, mmproj_filename)

        # Check if the model files exist at these absolute paths
        if not os.path.exists(abs_model_path):
            print(f"Error: Multimodal model file not found at {abs_model_path}")
            return "Error: Multimodal model file not found."
        if not os.path.exists(abs_mmproj_path):
            print(f"Error: Multimodal projection file not found at {abs_mmproj_path}")
            return "Error: Multimodal projection file not found."


        # Construct the prompt for llama-mtmd-cli.
        # This prompt format is a guess and may need adjustment based on how llama-mtmd-cli expects it.
        # It should instruct the model to analyze the image in the context of the user's goal.
        prompt = f"USER: Analyze the attached image. The user's current goal is: '{user_goal}'. Is the content of this image relevant and productive for achieving this goal? Provide a brief analysis. ASSISTANT:"

        command = [
            llama_mtmd_cmd,
            "-m", abs_model_path, # Use absolute path
            "--mmproj", abs_mmproj_path, # Use absolute path
            "--image", image_path,
            "-p", prompt 
            # Add other necessary llama-mtmd-cli parameters if any (e.g., --temp, --n-predict)
            # For example, to control output length: --n-predict 100
        ]

        try:
            print(f"Executing llama-mtmd-cli: {' '.join(command)}")
            process = subprocess.run(command, capture_output=True, text=True, check=True, timeout=60) # 60s timeout
            
            # The output parsing will depend heavily on llama-mtmd-cli's actual stdout.
            # This is a common way to get the main text output, but it might need refinement.
            # Typically, the command output includes the prompt and then the model's response.
            # We need to extract just the model's response.
            # If the command prints the prompt then the answer, we might need to split or parse.
            # Assuming the last non-empty part of the output after "ASSISTANT:" is the response.
            output = process.stdout.strip()
            # print(f"llama-mtmd-cli raw output: {output}") # For debugging

            # A simple way to get text after the prompt's "ASSISTANT:"
            assistant_marker = "ASSISTANT:"
            if assistant_marker in output:
                analysis_result = output.split(assistant_marker, 1)[-1].strip()
            else: # Fallback if marker is not found, take the whole output (might include prompt)
                analysis_result = output
            
            if not analysis_result: # If the result is empty after stripping
                print("llama-mtmd-cli produced empty output after prompt marker.")
                return "Visual analysis completed, but no specific feedback was generated."


            print(f"Screenshot analysis result: {analysis_result}")
            return analysis_result

        except subprocess.CalledProcessError as e:
            print(f"Error executing llama-mtmd-cli: {e}")
            print(f"Stderr: {e.stderr}")
            return "Error during visual analysis (execution failed)."
        except subprocess.TimeoutExpired:
            print("llama-mtmd-cli command timed out.")
            return "Error during visual analysis (command timed out)."
        except FileNotFoundError:
            print(f"Error: '{llama_mtmd_cmd}' not found. Make sure llama.cpp is installed and llama-mtmd-cli is in your PATH.")
            return "Error: Visual analysis tool not found."
        except Exception as e:
            print(f"An unexpected error occurred with llama-mtmd-cli: {e}")
            return "An unexpected error occurred during visual analysis."

    def generate_feedback(self, active_app_name: str, window_title: str, user_goal: str, 
                          feedback_type: str = "Normal", detailed_context: str = None, visual_analysis_result: Optional[str] = None) -> str:
        if not self.llm or not self._initialized:
            return "Error: LLM model not initialized. Please check model path and logs."
        
        # --- Automatically fetch detailed context if not provided ---
        if not detailed_context or detailed_context == "N/A":
            print(f"No detailed context provided for {active_app_name}. Attempting to fetch automatically.")
            auto_detailed_context = self.get_detailed_context_from_os(active_app_name)
            if auto_detailed_context:
                detailed_context = auto_detailed_context
            else:
                print(f"Could not automatically fetch detailed context for {active_app_name}.")
                detailed_context = None # Ensure it's None if not found, rather than "N/A"
        # --- End of new context fetching logic ---

        instruction = ""
        if feedback_type == "Brief":
            instruction = "Provide very brief, one-sentence constructive feedback or a motivational comment."
        elif feedback_type == "Detailed":
            instruction = "Provide more detailed and expansive constructive feedback. If appropriate, include a follow-up question for the user to consider. Offer specific insights if possible."
        else: 
            instruction = "Provide brief, constructive feedback or a motivational comment."

        context_str = f"The user is currently using the application '{active_app_name}'.\nThe active window title is '{window_title}'."
        if detailed_context and detailed_context != "N/A":
            context_str += f"\nThe specific textual context (e.g., URL or document path) is: '{detailed_context}'."
        
        if visual_analysis_result: # Add visual analysis to context if available
            context_str += f"\nVisual analysis of the current screen content: '{visual_analysis_result}'."

        # Gemma instruction format (example - adjust if your model needs a different one)
        # See: https://ai.google.dev/gemma/docs/formatting
        # Using a simplified prompt structure here, assuming the GGUF model is instruct-tuned
        # and llama-cpp handles specific tokenization needs for Gemma.

        full_prompt = f"<start_of_turn>user\n{context_str}\nThe user's stated goal for this task is: '{user_goal}'.\n\nBased on all this information (application, window title, textual context), analyze if the user is likely working towards their goal.\n{instruction}\nIf the activity seems aligned, encourage them.\nIf it seems misaligned, gently suggest how to refocus.\nIf there's not enough information, state that clearly.\nFeedback:<end_of_turn>\n<start_of_turn>model\n"

        try:
            print(f"Sending prompt to Llama CPP model '{self.text_model_name}' for feedback.")
            # print(f"Full prompt:\n{full_prompt}") # For debugging

            response = self.llm(
                full_prompt,
                max_tokens=250, # Adjust as needed
                stop=["<end_of_turn>", "<start_of_turn>user"], # Stop generation at these tokens
                echo=False # Do not echo the prompt in the output
            )
            
            feedback = response['choices'][0]['text'].strip()
            # print(f"Llama CPP Raw Response: {feedback}")
            return feedback
        # except llama_cpp.LlamaError as e: # Specific error for llama_cpp if available
        #     print(f"Llama CPP Error during feedback generation: {e}")
        #     return f"Error generating feedback from Llama CPP: {e}"
        except Exception as e:
            print(f"Error during Llama CPP feedback generation: {e}")
            return f"Error generating feedback from Llama CPP: {e}"

    def analyze_productivity(self, app_name: str, window_title: str, detailed_context: str, active_goal: str) -> bool:
        """
        Analyzes if the current activity is productive towards the user's goal.
        
        Args:
            app_name (str): Name of the active application
            window_title (str): Title of the active window
            detailed_context (str): Additional context (URL, file path, etc.)
            active_goal (str): The user's current goal
            
        Returns:
            bool: True if the activity is unproductive, False if productive or cannot determine
        """
        if not self.llm or not self._initialized:
            return False
            
        context_str = f"The user is currently using the application '{app_name}'.\nThe active window title is '{window_title}'."
        if detailed_context and detailed_context != "N/A":
            context_str += f"\nThe specific context is: '{detailed_context}'."
            
        prompt = f"<start_of_turn>user\n{context_str}\nThe user's current goal is: '{active_goal}'.\n\nBased on this information, determine if the user's current activity is productive towards their goal. Consider:\n1. Is the application typically used for work/productivity?\n2. Does the window title/content suggest productive work?\n3. Is the activity aligned with the stated goal?\n\nRespond with ONLY 'UNPRODUCTIVE' if the activity is clearly not helping achieve the goal, or 'PRODUCTIVE' if it is. If uncertain, respond with 'UNCERTAIN'.<end_of_turn>\n<start_of_turn>model\n"
        
        try:
            response = self.llm(
                prompt,
                max_tokens=50,
                stop=["<end_of_turn>", "<start_of_turn>user"],
                echo=False
            )
            
            result = response['choices'][0]['text'].strip().upper()
            return "UNPRODUCTIVE" in result
            
        except Exception as e:
            print(f"Error analyzing productivity: {e}")
            return False

    def generate_nudge_message(self, app_name: str, window_title: str, detailed_context: str, active_goal: str) -> str:
        """
        Generates a personalized nudge message to help the user refocus on their goal.
        
        Args:
            app_name (str): Name of the active application
            window_title (str): Title of the active window
            detailed_context (str): Additional context (URL, file path, etc.)
            active_goal (str): The user's current goal
            
        Returns:
            str: A personalized nudge message
        """
        if not self.llm or not self._initialized:
            return "Unable to generate nudge message - LLM not initialized."
            
        context_str = f"The user is currently using the application '{app_name}'.\nThe active window title is '{window_title}'."
        if detailed_context and detailed_context != "N/A":
            context_str += f"\nThe specific context is: '{detailed_context}'."
            
        prompt = f"<start_of_turn>user\n{context_str}\nThe user's current goal is: '{active_goal}'.\n\nGenerate a brief, encouraging message to help the user refocus on their goal. The message should:\n1. Be gentle and non-judgmental\n2. Acknowledge the current activity\n3. Remind them of their goal\n4. Suggest a specific action to get back on track\n5. Be concise (2-3 sentences maximum)\n\nFormat the response as a friendly, supportive message.<end_of_turn>\n<start_of_turn>model\n"
        
        try:
            response = self.llm(
                prompt,
                max_tokens=150,
                stop=["<end_of_turn>", "<start_of_turn>user"],
                echo=False
            )
            
            return response['choices'][0]['text'].strip()
            
        except Exception as e:
            print(f"Error generating nudge message: {e}")
            return "I notice you might be getting distracted. Would you like to take a moment to refocus on your goal?"

# Singleton instance getter
def get_llm_handler():
    return LLMHandler()

if __name__ == '__main__':
    print("Attempting to initialize LLMHandler for Llama CPP and test functionality...")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_for_test = os.path.dirname(current_dir) 
    project_root_for_test = os.path.dirname(project_root_for_test) 
    if project_root_for_test not in sys.path:
        sys.path.insert(0, project_root_for_test)
        sys.path.insert(0, os.path.join(project_root_for_test, "src")) # Add src to path for utils.macos_context

    # IMPORTANT: Ensure MODEL_PATH in this file points to a valid GGUF model for this test to run.
    if not os.path.exists(MODEL_PATH) or "placeholder" in MODEL_PATH.lower() or os.path.getsize(MODEL_PATH) < 1000:
        print(f"SKIPPING LLMHandler test: Model file at {MODEL_PATH} is missing, a placeholder, or too small.")
        print("Please download a Gemma GGUF model (e.g., gemma-3-4b-it-qat-q4_0-gguf) and update MODEL_PATH.")
    else:
        try:
            handler = get_llm_handler()
            if not handler._initialized or not handler.llm:
                 print("LLM Handler failed to initialize properly. Skipping tests.")
                 raise SystemExit("LLM Init Failed") # Exit if handler is not good

            print("\n--- Test Llama CPP Text-Only Feedback Generation ---")
            base_args = {
                "active_app_name": "VS Code", 
                "window_title": "llm_handler.py - Time Tracker Mac", 
                "user_goal": "Refactor LLMHandler to use Llama CPP.",
                "detailed_context": "Editing the generate_feedback method."
            }
            feedback_text_only = handler.generate_feedback(**base_args, feedback_type="Normal")
            print(f"Llama CPP Text-Only Feedback: {feedback_text_only}")

            print("\n--- Test Llama CPP with auto-context (Safari example) ---")
            # To test this, open Safari to a specific page before running
            safari_args = {
                "active_app_name": "Safari", 
                "window_title": "Some Webpage - Safari", 
                "user_goal": "Researching web APIs for project.",
                "detailed_context": None # Let it auto-fetch
            }
            feedback_safari = handler.generate_feedback(**safari_args, feedback_type="Brief")
            print(f"Llama CPP Safari Feedback (auto-context): {feedback_safari}")

            print("\n--- Test Llama CPP with auto-context (Preview example) ---")
            # To test this, open a PDF in Preview before running
            preview_args = {
                "active_app_name": "Preview", 
                "window_title": "MyDocument.pdf", 
                "user_goal": "Reviewing project specification.",
                "detailed_context": None # Let it auto-fetch
            }
            feedback_preview = handler.generate_feedback(**preview_args, feedback_type="Detailed")
            print(f"Llama CPP Preview Feedback (auto-context): {feedback_preview}")

            print("\n--- Test Llama CPP Screenshot Analysis (Placeholder) ---")
            # This test requires a placeholder image and llama-mtmd-cli to be functional
            # Create a dummy image file for testing
            dummy_image_path = "dummy_screenshot.png"
            try:
                from PIL import Image as PImage # Use a different alias to avoid conflict if any
                img = PImage.new('RGB', (600, 400), color = 'red')
                img.save(dummy_image_path)
                
                # Test the new screenshot analysis method
                # Ensure llama-mtmd-cli is in PATH and models are accessible
                # You might need to adjust model paths in analyze_screenshot_with_mtmd
                # or ensure they are in the current working directory / a known model dir.
                print(f"Attempting screenshot analysis with '{dummy_image_path}'...")
                screenshot_goal = "Develop a new feature for a Python application."
                analysis_result = handler.analyze_screenshot_with_mtmd(dummy_image_path, screenshot_goal)
                print(f"Screenshot Analysis Result: {analysis_result}")

                # Test feedback generation with screenshot analysis
                if analysis_result and "error" not in analysis_result.lower():
                     feedback_with_visual = handler.generate_feedback(
                        active_app_name="VS Code",
                        window_title="new_feature.py - MyProject",
                        user_goal=screenshot_goal,
                        detailed_context="Working on the core logic.",
                        visual_analysis_result=analysis_result
                    )
                     print(f"Feedback with Visual Analysis: {feedback_with_visual}")
                else:
                    print("Skipping feedback generation with visual due to analysis error/missing result.")

            except ImportError:
                print("Pillow (PIL) is not installed. Cannot create dummy image for screenshot analysis test.")
                print("Please install Pillow: pip install Pillow")
            except Exception as e:
                print(f"Error during screenshot analysis test: {e}")
            finally:
                if os.path.exists(dummy_image_path):
                    os.remove(dummy_image_path)
                
        except Exception as e:
            print(f"An error occurred during the LLMHandler (Llama CPP) test: {e}")
            import traceback
            traceback.print_exc() 