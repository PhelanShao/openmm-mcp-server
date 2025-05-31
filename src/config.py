# src/config.py
# Project configuration management

import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

class AppConfig:
    """Application configuration settings."""

    # Server settings
    SERVER_HOST: str = os.getenv("MCP_SERVER_HOST", "127.0.0.1")
    SERVER_PORT: int = int(os.getenv("MCP_SERVER_PORT", "8000"))
    SERVER_TRANSPORT: str = os.getenv("MCP_SERVER_TRANSPORT", "sse") # "stdio" or "sse"

    # Logging settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_FILE: str | None = os.getenv("LOG_FILE") # e.g., "mcp_server.log"

    # OpenMM Engine settings
    DEFAULT_OPENMM_PLATFORM: str | None = os.getenv("DEFAULT_OPENMM_PLATFORM") # e.g., "CUDA", "OpenCL", "CPU"
    # Example: Platform properties could be a JSON string in env var
    # DEFAULT_OPENMM_PLATFORM_PROPERTIES: Dict[str, str] = json.loads(os.getenv("DEFAULT_OPENMM_PLATFORM_PROPERTIES", "{}"))

    # Task Management settings
    TASK_DATA_DIR: str = os.getenv("TASK_DATA_DIR", "task_data") # Directory to store task-related files
    MAX_CONCURRENT_TASKS: int = int(os.getenv("MAX_CONCURRENT_TASKS", "2"))

    # Abacus Engine (Placeholder settings for future use)
    ABACUS_EXECUTABLE_PATH: str | None = os.getenv("ABACUS_EXECUTABLE_PATH")

    # Add other configurations as needed

# Instantiate the config object for easy import elsewhere
config = AppConfig()

# Example of how to use:
# from src.config import config
# print(f"Server will run on {config.SERVER_HOST}:{config.SERVER_PORT}")

if __name__ == "__main__":
    print("Configuration Settings:")
    for key, value in AppConfig.__dict__.items():
        if not key.startswith("__") and not callable(value):
            # For class variables, access them via `config` instance
            actual_value = getattr(config, key, "N/A")
            print(f"  {key}: {actual_value}")
    print(f"\nTask data will be stored in: {os.path.abspath(config.TASK_DATA_DIR)}")