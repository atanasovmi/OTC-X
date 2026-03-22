"""Helper script to launch the Streamlit frontend."""

from pathlib import Path
import subprocess


def main() -> None:
    app_path = Path(__file__).resolve().parent / "frontend" / "app.py"
    subprocess.run(["streamlit", "run", str(app_path)], check=True)


if __name__ == "__main__":
    main()

