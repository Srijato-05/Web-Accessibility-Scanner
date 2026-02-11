import os
import sys
import logging
import threading
import time
import json
import requests
from typing import List, Union, Optional, Dict, Any

# Third-Party AI Libraries
try:
    import torch
    from sentence_transformers import SentenceTransformer, util
    from langchain_ollama import ChatOllama
    import ollama
except ImportError as e:
    print(f"[CRITICAL] Missing Dependency: {e}")
    print("Run: uv pip install torch sentence-transformers langchain-ollama ollama")
    sys.exit(1)

# ==========================================
#        LOGGING CONFIGURATION
# ==========================================
# Setup a dedicated logger for the AI Engine
logger = logging.getLogger("AI_ENGINE")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - [AI_ENGINE] - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# ==========================================
#        LOCAL AI MANAGER (SINGLETON)
# ==========================================
class LocalAI:
    """
    The Central Nervous System for Drishti-AX.
    Manages connections to:
    1. Local Inference Server (Ollama) -> Llama-3 (Reasoning) & Moondream (Vision)
    2. Embedding Engine (Sentence-Transformers) -> MPNet (Semantic Search)
    
    Implements:
    - Lazy Loading (Save RAM until needed)
    - Automatic Retry Logic (For Ollama cold-starts)
    - Thread-Safe Singleton Pattern (For Swarm access)
    - Hardware Acceleration Detection (CUDA/MPS/CPU)
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(LocalAI, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        logger.info("Initializing Local AI Neural Engine (Lazy Mode)...")
        
        # 1. Hardware Detection
        if torch.cuda.is_available():
            self.device = "cuda"
            logger.info("Hardware Acceleration: NVIDIA CUDA Detected 🟢")
        elif torch.backends.mps.is_available():
            self.device = "mps" # For Mac M1/M2/M3
            logger.info("Hardware Acceleration: Apple Metal (MPS) Detected 🟢")
        else:
            self.device = "cpu"
            logger.warning("Hardware Acceleration: NONE (Running on CPU) 🟡")

        # 2. Configuration
        self.ollama_base_url = "http://localhost:11434"
        self.reasoning_model_name = "llama3:8b"
        self.vision_model_name = "moondream"
        self.embedding_model_name = "sentence-transformers/all-mpnet-base-v2"
        
        # 3. State Flags (Lazy Load)
        self._mpnet = None
        self._llm_reasoning = None
        self._vision_client = None
        
        self._initialized = True

    # ==========================================
    #        COMPONENT 1: SEMANTIC SEARCH
    # ==========================================
    @property
    def mpnet(self):
        """
        Lazy-loads the Sentence Transformer model.
        Used for finding buttons by meaning (e.g., 'Submit' ~= 'Send').
        """
        if self._mpnet is None:
            with self._lock:
                if self._mpnet is None:
                    try:
                        logger.info(f"Loading Embedding Model ({self.embedding_model_name}) on {self.device}...")
                        self._mpnet = SentenceTransformer(self.embedding_model_name, device=self.device)
                        logger.info("Embedding Model Loaded Successfully.")
                    except Exception as e:
                        logger.critical(f"FATAL: Failed to load MPNet: {e}")
                        # Fallback to prevent crash, though functionality is crippled
                        self._mpnet = None
        return self._mpnet

    def get_embedding(self, text: Union[str, List[str]]) -> torch.Tensor:
        """
        Generates vector embeddings for a string or list of strings.
        Returns a PyTorch Tensor.
        """
        model = self.mpnet
        if not model:
            logger.error("Embedding Engine unavailable.")
            return torch.zeros((1, 768), device=self.device)
            
        try:
            # Generate embeddings
            embeddings = model.encode(text, convert_to_tensor=True, device=self.device, show_progress_bar=False)
            return embeddings
        except Exception as e:
            logger.error(f"Embedding Generation Failed: {e}")
            # Return zero tensor to prevent downstream crash
            return torch.zeros((1, 768), device=self.device)

    def compute_similarity(self, query_emb, corpus_embs):
        """
        Calculates Cosine Similarity between a query and a list of targets.
        Used by the Semantic Sensor to rank buttons.
        """
        try:
            return util.cos_sim(query_emb, corpus_embs)
        except Exception as e:
            logger.error(f"Similarity Computation Failed: {e}")
            return torch.tensor([0.0])

    # ==========================================
    #        COMPONENT 2: REASONING (LLM)
    # ==========================================
    @property
    def llm_reasoning(self):
        """
        Lazy-loads the LangChain Ollama wrapper.
        Used for Planning (Architect) and Coding (Surgeon).
        """
        if self._llm_reasoning is None:
            with self._lock:
                if self._llm_reasoning is None:
                    # Health Check Loop
                    if not self._wait_for_ollama():
                        return None
                    
                    logger.info(f"Connecting to Ollama ({self.reasoning_model_name})...")
                    try:
                        self._llm_reasoning = ChatOllama(
                            model=self.reasoning_model_name,
                            base_url=self.ollama_base_url,
                            temperature=0.1,  # Strict logic (Low Creativity)
                            num_ctx=8192,     # Large context window for DOM analysis
                            keep_alive="1h"   # Keep model loaded in VRAM
                        )
                        logger.info("Reasoning Engine Connected.")
                    except Exception as e:
                        logger.error(f"Failed to connect to LangChain Ollama: {e}")
                        return None
        return self._llm_reasoning

    def _wait_for_ollama(self, retries=5, delay=3) -> bool:
        """
        Pings the Ollama API to ensure it's up and running.
        Retries automatically if the service is starting.
        """
        url = f"{self.ollama_base_url}/api/tags"
        for i in range(retries):
            try:
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    return True
            except requests.exceptions.ConnectionError:
                logger.warning(f"Ollama Unreachable (Attempt {i+1}/{retries}). Is 'ollama serve' running?")
                time.sleep(delay)
            except Exception as e:
                logger.error(f"Ollama Health Check Error: {e}")
                return False
        
        logger.critical("FATAL: Ollama Service is OFFLINE. Start it via terminal or app.")
        return False

    def generate_code(self, prompt: str, system_role: str = "You are a WCAG Expert.") -> str:
        """
        Robust wrapper for LLM Code Generation.
        Handles errors and creates a properly formatted prompt structure.
        """
        llm = self.llm_reasoning
        if not llm:
            return "/* Error: AI Engine Offline */"

        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            
            messages = [
                SystemMessage(content=f"{system_role} Output ONLY valid code/JSON. No markdown."),
                HumanMessage(content=prompt)
            ]
            
            response = llm.invoke(messages)
            return response.content.strip()
        except Exception as e:
            logger.error(f"LLM Generation Failed: {e}")
            return "/* Error: Generation Exception */"

    # ==========================================
    #        COMPONENT 3: VISION (VLM)
    # ==========================================
    def analyze_image(self, image_path: str, prompt: str = "Describe this UI element for accessibility.") -> str:
        """
        Uses Moondream (via Ollama raw API) to describe images.
        Crucial for Pillar 3 (Alt-Text Generation).
        """
        if not os.path.exists(image_path):
            logger.error(f"Image not found at path: {image_path}")
            return "Error: Image Missing"

        if not self._wait_for_ollama(retries=2):
            return "Error: AI Vision Offline"

        try:
            # We use the raw 'ollama' lib here because LangChain's vision support varies
            response = ollama.generate(
                model=self.vision_model_name,
                prompt=prompt,
                images=[image_path],
                stream=False
            )
            description = response.get('response', '').strip()
            logger.info(f"Vision Analysis Complete ({len(description)} chars)")
            return description
        except Exception as e:
            logger.error(f"Vision Model Failed: {e}")
            return "Error: Vision Analysis Exception"

# Global Singleton Instance
# Import 'ai_engine' from anywhere in the project to access these features
ai_engine = LocalAI()

if __name__ == "__main__":
    # Self-Test when running this file directly
    print("--- Running AI Engine Diagnostics ---")
    
    # Test 1: Embedding
    print("1. Testing MPNet...")
    emb = ai_engine.get_embedding("Hello World")
    print(f"   -> Embedding Shape: {emb.shape}")
    
    # Test 2: Ollama Connection
    print("2. Testing Ollama Connection...")
    status = ai_engine._wait_for_ollama(retries=1)
    print(f"   -> Ollama Status: {'ONLINE' if status else 'OFFLINE'}")
    
    if status:
        # Test 3: Generation
        print("3. Testing Llama-3 Generation...")
        res = ai_engine.generate_code("Return the JSON object {'status': 'ok'}")
        print(f"   -> Response: {res}")