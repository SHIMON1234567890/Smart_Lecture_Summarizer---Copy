import os
import sys
import subprocess

# Auto-detect and switch to the virtual environment if running with global/un-activated Python
script_dir = os.path.dirname(os.path.abspath(__file__))
candidate_venvs = [
    os.path.join(script_dir, "venv", "Scripts", "python.exe"),
    r"C:\Users\Shimon\OneDrive\Desktop\Smart_Lecture_Summarizer - Copy\venv\Scripts\python.exe",
]
target_python = next((p for p in candidate_venvs if os.path.exists(p)), None)

if target_python and os.path.normcase(sys.executable) != os.path.normcase(target_python):
    print(f"[*] Switching to virtual environment Python: {target_python}")
    script_file = os.path.abspath(__file__)
    sys.exit(subprocess.call([target_python, script_file] + sys.argv[1:]))

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
