import threading
import os
import subprocess # Added for running llama-mtmd-cli
# import base64 # No longer needed for screenshots
# from io import BytesIO # No longer needed for screenshots
# from PIL import Image # No longer needed for screenshots
from transformers import AutoProcessor, Gemma3nForConditionalGeneration, pipeline
import torch
import time # For tests
import sys # For modifying path for testing
from typing import Optional # Added import

# --- Import new macos_context module ---
try:
    from utils import macos_context # Assuming utils is in PYTHONPATH or relative
except ImportError:
    from src.utils import macos_context # Alternative import path

# --- Configuration for Gemma 3N E4B Model --- 
# Using Hugging Face Transformers instead of GGUF format
MODEL_ID = "google/gemma-3n-e4b-it"
# Support MPS (Metal Performance Shaders) for Apple Silicon
if torch.backends.mps.is_available():
    DEVICE = "mps"
    TORCH_DTYPE = torch.float32  # MPS doesn't support bfloat16
elif torch.cuda.is_available():
    DEVICE = "cuda"
    TORCH_DTYPE = torch.bfloat16
else:
    DEVICE = "cpu"
    TORCH_DTYPE = torch.float32

# Create models directory for caching
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "models")
if not os.path.exists(MODELS_DIR):
    os.makedirs(MODELS_DIR)

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
            
            print("Initializing LLMHandler with Gemma 3N E4B...")
            self.model_id = MODEL_ID
            self.device = DEVICE
            self.torch_dtype = TORCH_DTYPE
            self.model = None
            self.processor = None
            self.text_pipeline = None
            
            try:
                print(f"Loading model {self.model_id} on {self.device} with dtype {self.torch_dtype}")
                
                # Initialize model and processor
                self.model = Gemma3nForConditionalGeneration.from_pretrained(
                    self.model_id,
                    device_map="auto" if self.device == "cuda" else None,
                    torch_dtype=self.torch_dtype,
                    cache_dir=MODELS_DIR
                ).eval()
                
                self.processor = AutoProcessor.from_pretrained(
                    self.model_id,
                    cache_dir=MODELS_DIR
                )
                
                # Create text generation pipeline for simpler text-only tasks
                self.text_pipeline = pipeline(
                    "text-generation",
                    model=self.model,
                    tokenizer=self.processor.tokenizer,
                    device=self.device,
                    torch_dtype=self.torch_dtype
                )
                
                self._initialized = True
                print(f"LLMHandler initialized with Gemma 3N E4B. Model: {self.model_id}")
            except Exception as e:
                print(f"Error initializing Gemma 3N E4B model: {e}")
                self._initialized = False
                # Optional: raise an error
                # raise RuntimeError(f"Failed to initialize Gemma 3N E4B model: {e}")

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

    def check_model_status(self):
        """Checks if the Gemma 3N E4B model was loaded successfully."""
        if self.model and self._initialized:
            print(f"Gemma 3N E4B model '{self.model_id}' loaded successfully.")
            return True
        else:
            print(f"Gemma 3N E4B model '{self.model_id}' failed to load. Check initialization logs.")
            return False

    # def analyze_screenshot_for_productivity(self, image_path: str, user_goal: str) -> str | None: # Removed

    def analyze_screenshot_with_gemma(self, image_path: str, user_goal: str) -> Optional[str]:
        """
        Analyzes a screenshot using Gemma 3N E4B to determine if the content
        is productive towards the user_goal.

        Args:
            image_path (str): Path to the screenshot image file.
            user_goal (str): The user's current goal.

        Returns:
            str | None: Analysis result string if successful, None otherwise.
        """
        if not self._initialized or not self.model or not self.processor:
            print("LLMHandler not fully initialized. Screenshot analysis unavailable.")
            return None

        if not os.path.exists(image_path):
            print(f"Screenshot Error: Image path does not exist: {image_path}")
            return None

        try:
            from PIL import Image
            image = Image.open(image_path)
            
            # Prepare the conversation for the instruction-tuned model
            messages = [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": "You are a helpful assistant that analyzes screenshots to help users stay productive."}]
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": image},
                        {"type": "text", "text": f"Analyze this screenshot. The user's current goal is: '{user_goal}'. Is the content of this image relevant and productive for achieving this goal? Provide a brief analysis (2-3 sentences)."}
                    ]
                }
            ]
            
            # Apply chat template and process inputs
            inputs = self.processor.apply_chat_template(
                messages,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
            ).to(self.device)
            
            input_len = inputs["input_ids"].shape[-1]
            
            with torch.inference_mode():
                generation = self.model.generate(
                    **inputs,
                    max_new_tokens=150,
                    do_sample=False,
                    temperature=0.7,
                    pad_token_id=self.processor.tokenizer.eos_token_id
                )
                generation = generation[0][input_len:]
                analysis_result = self.processor.decode(generation, skip_special_tokens=True)
            
            print(f"Screenshot analysis result: {analysis_result}")
            return analysis_result.strip()
            
        except ImportError:
            print("PIL (Pillow) not available. Cannot analyze screenshots.")
            return "Error: PIL not available for image processing."
        except Exception as e:
            print(f"Error during screenshot analysis: {e}")
            return f"Error during visual analysis: {str(e)}"

    def generate_feedback(self, active_app_name: str, window_title: str, user_goal: str, 
                          feedback_type: str = "Normal", detailed_context: str = None, visual_analysis_result: Optional[str] = None) -> str:
        if not self.model or not self._initialized:
            return "Error: LLM model not initialized. Please check model initialization logs."
        
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

        # Prepare the conversation for the instruction-tuned model
        messages = [
            {
                "role": "system",
                "content": [{"type": "text", "text": "You are a helpful assistant that provides productivity feedback to help users stay focused on their goals."}]
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{context_str}\nThe user's stated goal for this task is: '{user_goal}'.\n\nBased on all this information (application, window title, textual context), analyze if the user is likely working towards their goal.\n{instruction}\nIf the activity seems aligned, encourage them.\nIf it seems misaligned, gently suggest how to refocus.\nIf there's not enough information, state that clearly.\nProvide feedback:"}
                ]
            }
        ]

        try:
            print(f"Sending prompt to Gemma 3N E4B model '{self.model_id}' for feedback.")
            
            # Apply chat template and process inputs
            inputs = self.processor.apply_chat_template(
                messages,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
            ).to(self.device)
            
            input_len = inputs["input_ids"].shape[-1]
            
            with torch.inference_mode():
                generation = self.model.generate(
                    **inputs,
                    max_new_tokens=250,
                    do_sample=True,
                    temperature=0.7,
                    pad_token_id=self.processor.tokenizer.eos_token_id
                )
                generation = generation[0][input_len:]
                feedback = self.processor.decode(generation, skip_special_tokens=True)
            
            return feedback.strip()
            
        except Exception as e:
            print(f"Error during Gemma 3N E4B feedback generation: {e}")
            return f"Error generating feedback from Gemma 3N E4B: {e}"

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
        if not self.model or not self._initialized:
            return False
            
        context_str = f"The user is currently using the application '{app_name}'.\nThe active window title is '{window_title}'."
        if detailed_context and detailed_context != "N/A":
            context_str += f"\nThe specific context is: '{detailed_context}'."
            
        messages = [
            {
                "role": "system",
                "content": [{"type": "text", "text": "You are a helpful assistant that analyzes user activities for productivity."}]
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{context_str}\nThe user's current goal is: '{active_goal}'.\n\nBased on this information, determine if the user's current activity is productive towards their goal. Consider:\n1. Is the application typically used for work/productivity?\n2. Does the window title/content suggest productive work?\n3. Is the activity aligned with the stated goal?\n\nRespond with ONLY 'UNPRODUCTIVE' if the activity is clearly not helping achieve the goal, or 'PRODUCTIVE' if it is. If uncertain, respond with 'UNCERTAIN'."}
                ]
            }
        ]
        
        try:
            inputs = self.processor.apply_chat_template(
                messages,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
            ).to(self.device)
            
            input_len = inputs["input_ids"].shape[-1]
            
            with torch.inference_mode():
                generation = self.model.generate(
                    **inputs,
                    max_new_tokens=50,
                    do_sample=False,
                    temperature=0.1,
                    pad_token_id=self.processor.tokenizer.eos_token_id
                )
                generation = generation[0][input_len:]
                result = self.processor.decode(generation, skip_special_tokens=True)
            
            return "UNPRODUCTIVE" in result.upper()
            
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
        if not self.model or not self._initialized:
            return "Unable to generate nudge message - LLM not initialized."
            
        context_str = f"The user is currently using the application '{app_name}'.\nThe active window title is '{window_title}'."
        if detailed_context and detailed_context != "N/A":
            context_str += f"\nThe specific context is: '{detailed_context}'."
            
        messages = [
            {
                "role": "system",
                "content": [{"type": "text", "text": "You are a helpful assistant that generates gentle, encouraging nudge messages to help users stay focused on their goals."}]
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{context_str}\nThe user's current goal is: '{active_goal}'.\n\nGenerate a brief, encouraging message to help the user refocus on their goal. The message should:\n1. Be gentle and non-judgmental\n2. Acknowledge the current activity\n3. Remind them of their goal\n4. Suggest a specific action to get back on track\n5. Be concise (2-3 sentences maximum)\n\nFormat the response as a friendly, supportive message."}
                ]
            }
        ]
        
        try:
            inputs = self.processor.apply_chat_template(
                messages,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
            ).to(self.device)
            
            input_len = inputs["input_ids"].shape[-1]
            
            with torch.inference_mode():
                generation = self.model.generate(
                    **inputs,
                    max_new_tokens=150,
                    do_sample=True,
                    temperature=0.7,
                    pad_token_id=self.processor.tokenizer.eos_token_id
                )
                generation = generation[0][input_len:]
                nudge_message = self.processor.decode(generation, skip_special_tokens=True)
            
            return nudge_message.strip()
            
        except Exception as e:
            print(f"Error generating nudge message: {e}")
            return "I notice you might be getting distracted. Would you like to take a moment to refocus on your goal?"

# Singleton instance getter
def get_llm_handler():
    return LLMHandler()

if __name__ == '__main__':
    print("Attempting to initialize LLMHandler for Gemma 3N E4B and test functionality...")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_for_test = os.path.dirname(current_dir) 
    project_root_for_test = os.path.dirname(project_root_for_test) 
    if project_root_for_test not in sys.path:
        sys.path.insert(0, project_root_for_test)
        sys.path.insert(0, os.path.join(project_root_for_test, "src")) # Add src to path for utils.macos_context

    try:
        handler = get_llm_handler()
        if not handler._initialized or not handler.model:
             print("LLM Handler failed to initialize properly. Skipping tests.")
             raise SystemExit("LLM Init Failed") # Exit if handler is not good

        print("\n--- Test Gemma 3N E4B Text-Only Feedback Generation ---")
        base_args = {
            "active_app_name": "VS Code", 
            "window_title": "llm_handler.py - Time Tracker Mac", 
            "user_goal": "Refactor LLMHandler to use Gemma 3N E4B.",
            "detailed_context": "Editing the generate_feedback method."
        }
        feedback_text_only = handler.generate_feedback(**base_args, feedback_type="Normal")
        print(f"Gemma 3N E4B Text-Only Feedback: {feedback_text_only}")

        print("\n--- Test Gemma 3N E4B with auto-context (Safari example) ---")
        # To test this, open Safari to a specific page before running
        safari_args = {
            "active_app_name": "Safari", 
            "window_title": "Some Webpage - Safari", 
            "user_goal": "Researching web APIs for project.",
            "detailed_context": None # Let it auto-fetch
        }
        feedback_safari = handler.generate_feedback(**safari_args, feedback_type="Brief")
        print(f"Gemma 3N E4B Safari Feedback (auto-context): {feedback_safari}")

        print("\n--- Test Gemma 3N E4B with auto-context (Preview example) ---")
        # To test this, open a PDF in Preview before running
        preview_args = {
            "active_app_name": "Preview", 
            "window_title": "MyDocument.pdf", 
            "user_goal": "Reviewing project specification.",
            "detailed_context": None # Let it auto-fetch
        }
        feedback_preview = handler.generate_feedback(**preview_args, feedback_type="Detailed")
        print(f"Gemma 3N E4B Preview Feedback (auto-context): {feedback_preview}")

        print("\n--- Test Gemma 3N E4B Screenshot Analysis ---")
        # This test requires a placeholder image
        # Create a dummy image file for testing
        dummy_image_path = "dummy_screenshot.png"
        try:
            from PIL import Image as PImage # Use a different alias to avoid conflict if any
            img = PImage.new('RGB', (600, 400), color = 'red')
            img.save(dummy_image_path)
            
            # Test the new screenshot analysis method
            print(f"Attempting screenshot analysis with '{dummy_image_path}'...")
            screenshot_goal = "Develop a new feature for a Python application."
            analysis_result = handler.analyze_screenshot_with_gemma(dummy_image_path, screenshot_goal)
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
        print(f"An error occurred during the LLMHandler (Gemma 3N E4B) test: {e}")
        import traceback
        traceback.print_exc() 