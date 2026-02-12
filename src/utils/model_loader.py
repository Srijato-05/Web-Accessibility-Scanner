"""
Drishti-AX: Neural Nexus (The Titan Bridge)
Module: src.utils.model_loader
Version: Sentinel-15.1 "Titan Bridge"
Author: Sentinel Core System
Timestamp: 2026-02-12 23:15:00 UTC

Description:
    The interface between the Python Agents and the C++ Llama Engine.
    
    [CRITICAL FIX] Added 'generate_code' adapter method to prevent AttributeError.
    [OPTIMIZATION] Tuned for GTX 1650 (4GB VRAM) using Qwen-2.5-3B.
"""

import os
import sys
import logging
import torch

# ==============================================================================
#        WINDOWS CUDA 13.0 DLL INJECTION
# ==============================================================================
# Forces Python to look in the standard CUDA installation path for DLLs
cuda_path = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0\bin"
if os.path.exists(cuda_path):
    os.add_dll_directory(cuda_path)
    os.environ["PATH"] = cuda_path + os.pathsep + os.environ["PATH"]

try:
    from llama_cpp import Llama
except ImportError:
    print("FATAL: llama-cpp-python not installed. Run 'uv pip install...'")
    sys.exit(1)

logger = logging.getLogger("NeuralNexus")
logger.setLevel(logging.INFO)

class NeuralNexus:
    def __init__(self):
        self.model_path = os.path.join("models", "Qwen2.5-3B-Instruct-Q4_K_M.gguf")
        self.gpu_layers = -1  # -1 = Offload EVERYTHING to GPU
        self.context_window = 4096
        self.llm = None
        
        # Ignition Sequence
        self._ignite()

    def _ignite(self):
        """
        Bootstraps the Llama C++ Engine.
        """
        if not os.path.exists(self.model_path):
            logger.error(f"BRAIN MISSING: Could not find model at {self.model_path}")
            logger.error("Please run: uvx hf download bartowski/Qwen2.5-3B-Instruct-GGUF --include 'Qwen2.5-3B-Instruct-Q4_K_M.gguf' --local-dir ./models")
            return

        try:
            logger.info(f"Igniting Neural Nexus on GTX 1650...")
            self.llm = Llama(
                model_path=self.model_path,
                n_gpu_layers=self.gpu_layers,
                n_ctx=self.context_window,
                n_batch=512,          # Optimized for 4GB VRAM
                f16_kv=True,          # High-speed VRAM usage
                flash_attn=True,      # CUDA 13.0 Optimization
                verbose=False         # Keep console clean
            )
            logger.info("Neural Nexus Online. Ready for Inference.")
        except Exception as e:
            logger.critical(f"Ignition Failed: {e}")
            self.llm = None

    def generate_code(self, prompt: str, system_role: str = "Assistant") -> str:
        """
        The Adapter Method.
        Translates agent requests into Qwen-2.5 ChatML format.
        """
        if not self.llm:
            logger.error("Engine is offline. Returning empty thought.")
            return "[]"

        # Qwen-2.5 Strict ChatML Format
        # <|im_start|>system
        # {system_role}<|im_end|>
        # <|im_start|>user
        # {prompt}<|im_end|>
        # <|im_start|>assistant
        
        formatted_prompt = (
            f"<|im_start|>system\n{system_role}<|im_end|>\n"
            f"<|im_start|>user\n{prompt}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        try:
            output = self.llm(
                formatted_prompt,
                max_tokens=1024,      # Allow long responses
                stop=["<|im_end|>", "###"],
                temperature=0.7,      # Creativity balance
                echo=False
            )
            return output['choices'][0]['text'].strip()
        except Exception as e:
            logger.error(f"Inference Error: {e}")
            return "[]"

# Singleton Instance (This is what main_agent_runner imports)
ai_engine = NeuralNexus()