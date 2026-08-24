"""DigitalTwin.ai prototype launcher."""
import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent
    cmd = [sys.executable, "-m", "streamlit", "run", str(root / "app" / "dashboard.py")]
    print("Starting DigitalTwin.ai dashboard...")
    print("  $ " + " ".join(cmd))
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
