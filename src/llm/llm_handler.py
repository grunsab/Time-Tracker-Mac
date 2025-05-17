import threading
import os
import base64
from io import BytesIO
from PIL import Image
import ollama # Ollama Python client
import time # For tests
import sys # For modifying path for testing

# --- Configuration for Ollama Models --- 
# Ensure these models are pulled in your Ollama instance (e.g., `ollama pull gemma:latest`)
OLLAMA_TEXT_MODEL = "gemma3:4b" 
OLLAMA_MULTIMODAL_MODEL = "gemma3:4b" # LLaVA is a common multimodal model available in Ollama

# Configuration for image preprocessing (if needed by the multimodal model)
# LLaVA models are generally flexible, but consistent sizing can be good.
IMAGE_TARGET_SIZE = False

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
            
            print("Initializing LLMHandler for Ollama...")
            self.client = ollama.Client() # Default client connects to http://localhost:11434
            self.text_model_name = OLLAMA_TEXT_MODEL
            self.multimodal_model_name = OLLAMA_MULTIMODAL_MODEL
            self._initialized = True
            # Perform an initial check to see if Ollama is responsive and models are available
            self.check_ollama_status()
            print(f"LLMHandler initialized. Text model: {self.text_model_name}, Multimodal: {self.multimodal_model_name}")

    def check_ollama_status(self):
        """Checks if Ollama server is responsive and if the configured models are available."""
        try:
            print("Checking Ollama server status and model availability...")
            local_models = self.client.list() # Get list of local models
            available_model_names = [model['name'] for model in local_models['models']]
            print(f"Available Ollama models: {available_model_names}")

            text_model_found = any(self.text_model_name in name for name in available_model_names)
            multimodal_model_found = any(self.multimodal_model_name in name for name in available_model_names)

            if not text_model_found:
                print(f"Warning: Text model '{self.text_model_name}' not found in Ollama. Please pull it.")
                # You might want to raise an error or handle this more gracefully depending on app requirements
            else:
                print(f"Text model '{self.text_model_name}' is available in Ollama.")

            if not multimodal_model_found:
                print(f"Warning: Multimodal model '{self.multimodal_model_name}' not found in Ollama. Image description will fail. Please pull it.")
            else:
                print(f"Multimodal model '{self.multimodal_model_name}' is available in Ollama.")
            return True
            
        except Exception as e:
            print(f"Error connecting to Ollama or listing models: {e}")
            print("Please ensure Ollama server is running and accessible.")
            # Potentially raise this error to be caught by the UI for user feedback
            return False

    def analyze_screenshot_for_productivity(self, image_path: str, user_goal: str) -> str | None:
        if not os.path.exists(image_path):
            print(f"Screenshot Analysis Error: Original image file not found at {image_path}")
            return "Image file not found for analysis."

        try:
            print(f"Preprocessing image for Ollama multimodal analysis: {image_path}")
            img = Image.open(image_path)
            if IMAGE_TARGET_SIZE:
                img_resized = img.resize(IMAGE_TARGET_SIZE, Image.Resampling.LANCZOS)
                print(f"Image resized from {img.size} to {img_resized.size} for Ollama.")
            else:
                img_resized = img # Use original if no target size

            buffered = BytesIO()
            img_resized.save(buffered, format="PNG") # Save as PNG for consistency
            image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

            print(f"Sending image to Ollama model '{self.multimodal_model_name}' for productivity analysis.")
            
            analysis_prompt = f"""The user's stated goal is: '{user_goal}'.
This is a screenshot of the user's current screen.
Based *only* on the visual information in this screenshot and the user's goal, analyze if the user's current activity (as shown on screen) appears to be aligned with their stated goal.
- If aligned, briefly explain why and offer encouragement.
- If misaligned, gently point out the potential distraction or misalignment with the goal.
- If the screenshot provides insufficient information to make a determination (e.g., it's a desktop, a login screen, or too ambiguous), state that clearly.
Your analysis should be concise.
Analysis:"""
            
            response = self.client.generate(
                model=self.multimodal_model_name,
                prompt=analysis_prompt,
                images=[image_base64],
                stream=False 
            )
            analysis_result = response['response'].strip()
            print(f"Ollama Multimodal ('{self.multimodal_model_name}') Raw Analysis Response: {analysis_result}")
            return analysis_result

        except ollama.ResponseError as e:
            print(f"Ollama API Error during screenshot analysis: {e.error}")
            if "model not found" in e.error.lower():
                 return f"Ollama Error: Multimodal model '{self.multimodal_model_name}' not found. Please ensure it is pulled and available in Ollama."
            return f"Ollama API Error: {e.error}"
        except Exception as e:
            print(f"Error during screenshot analysis via Ollama: {e}")
            return f"Error generating screenshot analysis via Ollama: {e}"

    def generate_feedback(self, active_app_name: str, window_title: str, user_goal: str, 
                          feedback_type: str = "Normal", detailed_context: str = None, 
                          visual_analysis_context: str = None) -> str:
        
        instruction = ""
        # Max tokens for Ollama is often handled by the model's context or can be tuned; 
        # for `generate`, it's more about controlling output length via prompt or specific model params if available.
        # We will rely on good prompting for length control.

        if feedback_type == "Brief":
            instruction = "Provide very brief, one-sentence constructive feedback or a motivational comment."
        elif feedback_type == "Detailed":
            instruction = "Provide more detailed and expansive constructive feedback. If appropriate, include a follow-up question for the user to consider. Offer specific insights if possible."
        else: 
            instruction = "Provide brief, constructive feedback or a motivational comment."

        context_str = f"The user is currently using the application '{active_app_name}'.\nThe active window title is '{window_title}'."
        if detailed_context and detailed_context != "N/A":
            context_str += f"\nThe specific textual context (e.g., URL or document path) is: '{detailed_context}'."
        
        if visual_analysis_context:
            context_str += f"\nAn AI analysis of the user's screen based on their goal suggests: '{visual_analysis_context}'."
        
        # For Ollama, we typically send a single prompt or a structured list of messages for chat.
        # For `generate` with an instruct model like Gemma, a direct prompt is fine.
        full_prompt = f"""{context_str}
The user's stated goal for this task is: '{user_goal}'.

Based on all this information (application, window title, textual context, and screen description if provided), analyze if the user is likely working towards their goal.
{instruction}
If the activity seems aligned, encourage them.
If it seems misaligned, gently suggest how to refocus.
If there's not enough information, state that clearly.
Consider all provided context to make your assessment.
Feedback:"""
        # Note: Gemma instruct models often use specific turn tokens like <start_of_turn>user / <start_of_turn>model.
        # Depending on how Ollama serves the Gemma model, these might be handled automatically or you might need to add them.
        # For simplicity, we'll start without them and see Ollama's output. 
        # If needed, the prompt can be: f"<start_of_turn>user\n{full_prompt_content}<end_of_turn>\n<start_of_turn>model"

        try:
            print(f"Sending prompt to Ollama model '{self.text_model_name}' for feedback.")
            response = self.client.generate(
                model=self.text_model_name,
                prompt=full_prompt,
                stream=False
            )
            feedback = response['response'].strip()
            # print(f"Ollama Text ('{self.text_model_name}') Raw Response: {feedback}")
            return feedback
        except ollama.ResponseError as e:
            print(f"Ollama API Error during feedback generation: {e.error}")
            if "model not found" in e.error.lower():
                 return f"Ollama Error: Text model '{self.text_model_name}' not found. Please ensure it is pulled and available in Ollama."
            return f"Ollama API Error: {e.error}"
        except Exception as e:
            print(f"Error during Ollama feedback generation: {e}")
            return f"Error generating feedback from Ollama: {e}"

# Singleton instance getter
def get_llm_handler():
    return LLMHandler()

if __name__ == '__main__':
    print("Attempting to initialize LLMHandler for Ollama and test functionality...")
    
    # This import needs to be handled carefully if utils is not in sys.path when run directly
    # For testing, we may need to create a dummy image directly or ensure path setup.
    # For now, assume if screenshot_utils fails, we create a dummy path and expect image processing to fail gracefully.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_for_test = os.path.dirname(current_dir) # Moves up one level from src/llm to src/
    project_root_for_test = os.path.dirname(project_root_for_test) # Moves up one level from src/ to project root
    if project_root_for_test not in sys.path:
        sys.path.insert(0, project_root_for_test)

    try:
        handler = get_llm_handler()
        
        print("\n--- Test Ollama Text-Only Feedback Generation ---")
        base_args = {
            "active_app_name": "VS Code", 
            "window_title": "llm_handler.py - Time Tracker Mac", 
            "user_goal": "Refactor LLMHandler to use Ollama.",
            "detailed_context": "Editing the generate_feedback method."
        }
        feedback_text_only = handler.generate_feedback(**base_args, feedback_type="Normal")
        print(f"Ollama Text-Only Feedback: {feedback_text_only}")

        print("\n--- Test Ollama Screenshot Productivity Analysis ---")
        test_image_path = None
        current_user_goal_for_test = base_args["user_goal"] # Use the same goal for screenshot analysis test

        try:
            from src.utils.screenshot_utils import capture_active_window_to_temp_file
            print("Attempting to capture a real screenshot for Ollama screenshot analysis test...")
            print("Please ensure an application window is active in the next 5 seconds.")
            time.sleep(5)
            real_screenshot_path = capture_active_window_to_temp_file()
            if real_screenshot_path:
                test_image_path = real_screenshot_path
                print(f"Using real screenshot for Ollama test: {test_image_path}")
            else:
                print("Failed to capture real screenshot for Ollama test.")
        except ImportError:
            print("screenshot_utils not found, skipping real screenshot for Ollama test.")
        except Exception as e:
            print(f"Error during screenshot capture for Ollama test: {e}")

        if test_image_path:
            visual_analysis = handler.analyze_screenshot_for_productivity(test_image_path, current_user_goal_for_test)
            print(f"Ollama Screenshot Analysis Result: {visual_analysis}")

            if visual_analysis and "Ollama Error" not in visual_analysis and "Image file not found" not in visual_analysis:
                print("\n--- Test Ollama Feedback Generation with Visual Context (Analysis) ---")
                feedback_with_visual = handler.generate_feedback(
                    **base_args,
                    feedback_type="Detailed",
                    visual_analysis_context=visual_analysis
                )
                print(f"Ollama Feedback with Visual Context (Analysis): {feedback_with_visual}")
            else:
                print("\nSkipping Ollama feedback generation with visual context due to issues in screenshot analysis.")
            
            if test_image_path and os.path.exists(test_image_path):
                 try: os.remove(test_image_path); print(f"Cleaned up test screenshot: {test_image_path}")
                 except: pass # ignore cleanup error for test
        else:
            print("\nSkipping Ollama screenshot analysis and visual feedback test as no image was captured/provided.")
            
    except Exception as e:
        print(f"An error occurred during the LLMHandler (Ollama) test: {e}")
        import traceback
        traceback.print_exc() 