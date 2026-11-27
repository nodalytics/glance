
import importlib.metadata
import importlib.util
import json
import os
import platform
import shutil
import struct
import subprocess
import sys
import time

from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = (
    PROJECT_ROOT
    / "test_output"
    / "performance"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "hardware_diagnostics.json"
)


def run_command(command, timeout=30):
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )

        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }


def powershell_json(command):
    result = run_command(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            command + " | ConvertTo-Json -Depth 5",
        ]
    )

    if not result.get("success"):
        return result

    try:
        return json.loads(
            result["stdout"]
        )

    except json.JSONDecodeError:
        return result


def get_system_information():
    return {
        "operating_system": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "logical_cpu_count": os.cpu_count(),
        "python_version": platform.python_version(),
        "python_bits": struct.calcsize("P") * 8,
        "virtual_environment_active": (
            sys.prefix != sys.base_prefix
        ),
    }


def get_cpu_information():
    return powershell_json(
        "Get-CimInstance Win32_Processor | "
        "Select-Object Name, Manufacturer, "
        "NumberOfCores, NumberOfLogicalProcessors, "
        "MaxClockSpeed, L2CacheSize, L3CacheSize"
    )


def get_memory_information():
    return powershell_json(
        "Get-CimInstance Win32_ComputerSystem | "
        "Select-Object TotalPhysicalMemory"
    )


def get_gpu_information():
    return powershell_json(
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name, AdapterRAM, "
        "DriverVersion, VideoProcessor"
    )


def get_nvidia_information():
    executable = shutil.which("nvidia-smi")

    if executable is None:
        return {
            "available": False,
            "message": "nvidia-smi not found in PATH",
        }

    result = run_command(
        [
            executable,
            "--query-gpu=name,memory.total,"
            "memory.free,driver_version,"
            "utilization.gpu",
            "--format=csv,noheader,nounits",
        ]
    )

    return {
        "available": result.get("success", False),
        "result": result,
    }


def get_package_information():
    packages = [
        "paddlepaddle",
        "paddlepaddle-gpu",
        "paddleocr",
        "opencv-python",
        "opencv-contrib-python",
        "opencv-python-headless",
        "numpy",
        "Pillow",
        "onnx",
        "onnxruntime",
        "onnxruntime-gpu",
        "openvino",
        "torch",
        "torchvision",
        "numba",
        "psutil",
        "fastapi",
        "uvicorn",
    ]

    information = {}

    for package in packages:
        try:
            version = importlib.metadata.version(
                package
            )

            information[package] = {
                "installed": True,
                "version": version,
            }

        except importlib.metadata.PackageNotFoundError:
            information[package] = {
                "installed": False,
                "version": None,
            }

    return information


def probe_python_module(module_name, code):
    try:
        available = (
            importlib.util.find_spec(module_name)
            is not None
        )

    except Exception as error:
        return {
            "available": False,
            "error": str(error),
        }

    if not available:
        return {
            "available": False,
        }

    started = time.perf_counter()

    result = run_command(
        [
            sys.executable,
            "-c",
            code,
        ],
        timeout=120,
    )

    elapsed = time.perf_counter() - started

    result["available"] = True
    result["probe_duration_ms"] = round(
        elapsed * 1000,
        3,
    )

    return result


def get_paddle_information():
    code = """
import json
import paddle

compiled_with_cuda = paddle.is_compiled_with_cuda()

result = {
    "version": paddle.__version__,
    "compiled_with_cuda": compiled_with_cuda,
    "current_device": paddle.device.get_device(),
}

try:
    result["cuda_device_count"] = (
        paddle.device.cuda.device_count()
        if compiled_with_cuda
        else 0
    )
except Exception as error:
    result["cuda_error"] = str(error)

print(json.dumps(result))
"""

    return probe_python_module(
        "paddle",
        code,
    )


def get_opencv_information():
    code = """
import cv2
import json

result = {
    "version": cv2.__version__,
    "thread_count": cv2.getNumThreads(),
    "cpu_count": cv2.getNumberOfCPUs(),
    "optimized": cv2.useOptimized(),
    "opencl_available": cv2.ocl.haveOpenCL(),
    "opencl_enabled": cv2.ocl.useOpenCL(),
}

try:
    result["cuda_device_count"] = (
        cv2.cuda.getCudaEnabledDeviceCount()
    )
except Exception as error:
    result["cuda_error"] = str(error)

print(json.dumps(result))
"""

    return probe_python_module(
        "cv2",
        code,
    )


def get_onnx_information():
    code = """
import json
import onnxruntime as ort

print(json.dumps({
    "version": ort.__version__,
    "device": ort.get_device(),
    "available_providers": (
        ort.get_available_providers()
    ),
}))
"""

    return probe_python_module(
        "onnxruntime",
        code,
    )


def get_torch_information():
    code = """
import json
import torch

available = torch.cuda.is_available()

result = {
    "version": torch.__version__,
    "cuda_available": available,
    "cuda_version": torch.version.cuda,
    "cpu_threads": torch.get_num_threads(),
    "cuda_device_count": torch.cuda.device_count(),
}

if available:
    result["cuda_device_name"] = (
        torch.cuda.get_device_name(0)
    )

print(json.dumps(result))
"""

    return probe_python_module(
        "torch",
        code,
    )


def get_environment_information():
    variables = [
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "CUDA_VISIBLE_DEVICES",
        "FLAGS_use_mkldnn",
        "FLAGS_enable_pir_api",
    ]

    return {
        name: os.environ.get(name)
        for name in variables
    }


def get_disk_information():
    usage = shutil.disk_usage(PROJECT_ROOT)

    return {
        "total_gib": round(
            usage.total / (1024 ** 3),
            2,
        ),
        "used_gib": round(
            usage.used / (1024 ** 3),
            2,
        ),
        "free_gib": round(
            usage.free / (1024 ** 3),
            2,
        ),
    }


def main():
    started = time.perf_counter()

    print("=" * 65)
    print("PHASE 7.1 - HARDWARE DIAGNOSTICS")
    print("=" * 65)

    report = {
        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    checks = [
        (
            "system",
            get_system_information,
        ),
        (
            "cpu",
            get_cpu_information,
        ),
        (
            "memory",
            get_memory_information,
        ),
        (
            "gpu",
            get_gpu_information,
        ),
        (
            "nvidia",
            get_nvidia_information,
        ),
        (
            "packages",
            get_package_information,
        ),
        (
            "paddle",
            get_paddle_information,
        ),
        (
            "opencv",
            get_opencv_information,
        ),
        (
            "onnxruntime",
            get_onnx_information,
        ),
        (
            "torch",
            get_torch_information,
        ),
        (
            "environment",
            get_environment_information,
        ),
        (
            "disk",
            get_disk_information,
        ),
    ]

    for name, function in checks:
        print(
            f"\nChecking {name}...",
            flush=True,
        )

        try:
            report[name] = function()

        except Exception as error:
            report[name] = {
                "success": False,
                "error": str(error),
            }

    report["diagnostic_duration_seconds"] = round(
        time.perf_counter() - started,
        3,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            report,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\n" + "=" * 65)
    print("DIAGNOSTIC RESULTS")
    print("=" * 65)

    print(
        json.dumps(
            report,
            indent=4,
            ensure_ascii=False,
        )
    )

    print("\n" + "=" * 65)
    print("DIAGNOSTICS COMPLETED")
    print(f"Report saved: {OUTPUT_FILE}")
    print("=" * 65)


if __name__ == "__main__":
    main()
