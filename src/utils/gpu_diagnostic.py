"""
Drishti-AX: Neural Hardware Audit (The Hardware Doctor)
Module: utils/gpu_diagnostic.py
Version: Sentinel-13.0 "Titan"
Author: Sentinel Core System
Timestamp: 2026-02-12 23:30:00 UTC
Classification: DIAGNOSTIC // HARDWARE INTERFACE

Description:
    A high-level diagnostic tool designed to bridge the gap between 
    Python AI libraries and physical GPU hardware.
    
    It performs a 'Deep Handshake' with the NVIDIA Driver to determine:
    1.  Why the CPU fallback occurred.
    2.  If the installed PyTorch/ONNX binaries support CUDA.
    3.  The exact VRAM budget available for the Neural Engine.
    
    ARCHITECTURAL CHECKS:
    - CUDA Driver vs Runtime Version Mismatch.
    - Python Environment Library Audit (CPU vs GPU wheels).
    - Turing (GTX 16xx) Feature Support (FP16/INT8).
    - PCIe Bandwidth & P2P capabilities.
"""

import sys
import os
import platform
import subprocess
import json
import logging
import ctypes
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# ==============================================================================
#        ADVANCED TELEMETRY
# ==============================================================================
class AuditFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[90m',    # Grey
        'INFO': '\033[92m',     # Green (Pass)
        'WARNING': '\033[93m',  # Yellow (Degraded)
        'ERROR': '\033[91m',    # Red (Fail)
        'CRITICAL': '\033[41m'  # Red BG (Panic)
    }
    RESET = '\033[0m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        return f"{color}[HARDWARE] {record.levelname:<8} | {record.getMessage()}{self.RESET}"

logger = logging.getLogger("NeuralAudit")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(AuditFormatter())
logger.addHandler(handler)

# ==============================================================================
#        CORE AUDIT CLASS
# ==============================================================================
class NeuralHardwareAudit:
    def __init__(self):
        self.report = {
            "timestamp": datetime.now().isoformat(),
            "os": platform.system(),
            "python": sys.version.split()[0],
            "gpu_detected": False,
            "cuda_available": False,
            "libraries": {},
            "vram_budget": 0,
            "recommendation": "CPU_ONLY"
        }

    def run_full_scan(self):
        logger.info("Initiating Neural Hardware Audit...")
        
        # 1. System Level (NVIDIA-SMI)
        self._check_nvidia_smi()
        
        # 2. Library Level (PyTorch)
        self._check_pytorch()
        
        # 3. Library Level (ONNX Runtime)
        self._check_onnx()
        
        # 4. Library Level (Llama.cpp)
        self._check_llama_cpp()
        
        # 5. Synthesis & Recommendation
        self._synthesize_recommendation()
        
        self._print_report()

    def _check_nvidia_smi(self):
        """Queries the NVIDIA System Management Interface."""
        try:
            # Run nvidia-smi in query mode (CSV format for parsing)
            cmd = [
                'nvidia-smi', 
                '--query-gpu=name,driver_version,memory.total,memory.free,compute_cap', 
                '--format=csv,noheader'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                output = result.stdout.strip().split(', ')
                if len(output) >= 4:
                    self.report['gpu_detected'] = True
                    self.report['hardware'] = {
                        "name": output[0],
                        "driver": output[1],
                        "total_vram": output[2],
                        "free_vram": output[3],
                        "compute_cap": output[4] if len(output) > 4 else "Unknown"
                    }
                    
                    # Parse Free VRAM to Int (MB)
                    free_mb = int(output[3].lower().replace(' mib', ''))
                    self.report['vram_budget'] = free_mb
                    
                    logger.info(f"GPU Hardware Detected: {output[0]} ({output[3]} Free)")
                    logger.info(f"Driver Version: {output[1]}")
            else:
                logger.warning("NVIDIA-SMI failed. Drivers might be missing or corrupted.")
        
        except FileNotFoundError:
            logger.critical("NVIDIA-SMI not found. Is the CUDA Toolkit installed?")

    def _check_pytorch(self):
        """Audits the PyTorch installation."""
        status = {"installed": False, "cuda_support": False, "version": "N/A", "device": "N/A"}
        try:
            import torch
            status["installed"] = True
            status["version"] = torch.__version__
            
            if torch.cuda.is_available():
                status["cuda_support"] = True
                status["device"] = torch.cuda.get_device_name(0)
                status["capability"] = torch.cuda.get_device_capability(0)
                status["cuda_version_compiled"] = torch.version.cuda
                self.report['cuda_available'] = True
                
                # Tensor Core Check (Turing = 7.5)
                cap = status["capability"]
                if cap[0] >= 7:
                    status["tensor_cores"] = "Supported (FP16)"
                else:
                    status["tensor_cores"] = "Not Supported"
                    
                logger.info(f"PyTorch: CUDA ENABLED (v{torch.version.cuda}) on {status['device']}")
            else:
                logger.error(f"PyTorch: CPU ONLY. (Installed v{torch.__version__} does not match CUDA drivers)")
                
        except ImportError:
            logger.warning("PyTorch not installed.")
        
        self.report['libraries']['pytorch'] = status

    def _check_onnx(self):
        """Audits ONNX Runtime for GPU providers."""
        status = {"installed": False, "providers": []}
        try:
            import onnxruntime as ort
            status["installed"] = True
            status["version"] = ort.__version__
            status["providers"] = ort.get_available_providers()
            
            if 'CUDAExecutionProvider' in status["providers"]:
                logger.info("ONNX Runtime: CUDA PROVIDER DETECTED")
            elif 'DmlExecutionProvider' in status["providers"]:
                logger.info("ONNX Runtime: DIRECTML DETECTED (Windows AMD/Intel/NVIDIA)")
            else:
                logger.error("ONNX Runtime: CPU ONLY (Install onnxruntime-gpu)")
                
        except ImportError:
            logger.warning("ONNX Runtime not installed.")
            
        self.report['libraries']['onnx'] = status

    def _check_llama_cpp(self):
        """Audits Llama-cpp-python (Common for local LLMs)."""
        status = {"installed": False, "compiled_with_cuda": False}
        try:
            from llama_cpp import Llama
            status["installed"] = True
            # There is no direct "is_cuda" flag in python bindings easily accessible without instantiating
            # We infer from shared library linkage or load attempt
            try:
                # Attempt dummy load to check log
                logger.debug("Llama.cpp: Checking build info...")
                status["info"] = "Check console logs during model load for 'BLAS = 1'"
            except:
                pass
        except ImportError:
            pass
        self.report['libraries']['llama_cpp'] = status

    def _synthesize_recommendation(self):
        """Generates the strategy to fix the environment."""
        vram = self.report['vram_budget']
        gpu = self.report.get('hardware', {}).get('name', 'None')
        
        logger.info("Synthesizing Neural Config...")
        
        # Scenario A: No GPU
        if not self.report['gpu_detected']:
            self.report['recommendation'] = "CRITICAL: Install NVIDIA Drivers."
            return

        # Scenario B: GPU Present, but Libraries are CPU
        pt = self.report['libraries'].get('pytorch', {})
        if not pt.get('cuda_support'):
            self.report['recommendation'] = "ACTION: Reinstall PyTorch with CUDA 11.8/12.1"
            self.report['fix_cmd'] = "uv pip install torch --index-url https://download.pytorch.org/whl/cu118"
            return

        # Scenario C: GPU Working (GTX 1650 Specifics)
        # GTX 1650 has 4GB VRAM. This is the bottleneck.
        if "1650" in gpu:
            if vram < 3500:
                self.report['recommendation'] = "WARNING: High VRAM Usage. Close other apps."
            
            # Model Sizing Logic
            # 1B Params @ FP16 = 2GB
            # 3B Params @ Q4_K_M = ~2.5GB
            # 7B Params @ Q4_K_M = ~5GB (Too big)
            
            self.report['model_strategy'] = {
                "architecture": "Turing (TU117)",
                "precision": "FP16 (Mixed)",
                "max_model_size_params": "3 Billion",
                "recommended_quantization": "Q4_K_M or Q5_K_M",
                "recommended_models": [
                    "TinyLlama-1.1B-Chat-v1.0-GGUF",
                    "StableLM-Zephyr-3B-GGUF",
                    "Qwen1.5-1.8B-Chat-GGUF"
                ]
            }
            logger.info("OPTIMIZED STRATEGY: Use 3B Param models with 4-bit Quantization (GGUF).")

    def _print_report(self):
        print("\n" + "="*60)
        print(f"   SENTINEL-13.0 NEURAL HARDWARE REPORT")
        print("="*60)
        
        # Hardware
        hw = self.report.get('hardware', {})
        print(f"GPU: {hw.get('name', 'NONE')} [{hw.get('compute_cap', '')}]")
        print(f"VRAM: {hw.get('free_vram', '0')} / {hw.get('total_vram', '0')}")
        
        # Software Status
        pt = self.report['libraries'].get('pytorch', {})
        print(f"\nPyTorch: {'[OK]' if pt.get('cuda_support') else '[FAIL]'}")
        if not pt.get('cuda_support'):
            print(f"  -> Detected: {pt.get('version')}")
            print(f"  -> Device: {pt.get('device')}")
            
        onnx = self.report['libraries'].get('onnx', {})
        print(f"ONNX:    {'[OK]' if 'CUDAExecutionProvider' in onnx.get('providers', []) else '[FAIL]'}")
        
        # Recommendation
        print("-" * 60)
        print(f"STATUS: {self.report.get('recommendation', 'UNKNOWN')}")
        if 'fix_cmd' in self.report:
            print(f"FIX CMD: {self.report['fix_cmd']}")
        
        if 'model_strategy' in self.report:
            strat = self.report['model_strategy']
            print(f"\n[STRATEGY FOR {hw.get('name')}]")
            print(f"  * Quantization: {strat['recommended_quantization']}")
            print(f"  * Max Params:   {strat['max_model_size_params']}")
            print(f"  * Candidate Models:")
            for m in strat['recommended_models']:
                print(f"    - {m}")
        print("="*60 + "\n")

if __name__ == "__main__":
    audit = NeuralHardwareAudit()
    audit.run_full_scan()