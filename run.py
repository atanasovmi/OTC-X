#!/usr/bin/env python3
"""
OTC-X Task Runner
Professional command-line interface for the OTC-X platform

Usage:
    python run.py backend    # Run the data pipeline
    python run.py frontend   # Launch the Streamlit dashboard
    python run.py test       # Run the test suite
    python run.py help       # Show this help message
"""

import sys
import subprocess
from pathlib import Path


def print_banner():
    """Print the OTC-X banner"""
    print("=" * 80)
    print(" OTC-X Market Intelligence Platform")
    print(" Swiss OTC Analytics & Data Pipeline")
    print("=" * 80)


def run_backend():
    """Execute the backend data pipeline"""
    print("\n🔧 Starting backend data pipeline...\n")
    backend_script = Path(__file__).parent / "backend" / "run_backend.py"
    result = subprocess.run([sys.executable, str(backend_script)])
    return result.returncode


def run_frontend():
    """Launch the Streamlit frontend"""
    print("\n🌐 Launching Streamlit dashboard...\n")
    print("Dashboard will open in your browser at http://localhost:8501")
    print("Press Ctrl+C to stop the server\n")

    app_path = Path(__file__).parent / "app.py"
    result = subprocess.run(["streamlit", "run", str(app_path)])
    return result.returncode


def run_tests():
    """Execute the test suite"""
    print("\n🧪 Running test suite...\n")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v"])
    return result.returncode


def show_help():
    """Display help information"""
    print(__doc__)
    return 0


def main():
    """Main entry point"""
    print_banner()

    if len(sys.argv) < 2:
        print("\n❌ Error: No command specified")
        show_help()
        return 1

    command = sys.argv[1].lower()

    commands = {
        "backend": run_backend,
        "frontend": run_frontend,
        "test": run_tests,
        "help": show_help,
    }

    if command not in commands:
        print(f"\n❌ Error: Unknown command '{command}'")
        show_help()
        return 1

    return commands[command]()


if __name__ == "__main__":
    sys.exit(main())
