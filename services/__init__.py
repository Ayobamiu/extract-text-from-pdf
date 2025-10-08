import os
import sys

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Create __init__.py files for proper package structure
init_files = ["services/__init__.py", "utils/__init__.py"]

for init_file in init_files:
    file_path = os.path.join(project_root, init_file)
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            f.write("")
