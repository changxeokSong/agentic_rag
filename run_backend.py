import os
import subprocess
import sys


def main():
    # Ensure LM Studio endpoint is reachable info printed (optional)
    base_url = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
    print(f"[Backend] Using LM Studio at: {base_url}")

    # Prefer running automation dashboard and/or services if needed.
    # For now, run nothing long-lived other than a simple status tail to keep container healthy.
    # The frontend service runs Streamlit UI.
    # If you need a backend API server, replace below with e.g., `uvicorn api:app`.
    print("[Backend] Ready. No persistent backend server defined; container kept alive.")
    try:
        # Keep process alive while allowing logs to stream if needed
        subprocess.call([sys.executable, "-c", "import time;\nprint('Backend idle...');\nwhile True: time.sleep(3600)"])
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()


