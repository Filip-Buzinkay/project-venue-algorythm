import subprocess
import sys
import os
import time

# Path to the markX foler
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PYTHON = sys.executable

def main():
    print("Launching Project Venus...")

    # Start robots first — they bind their PUB sockets
    walle = subprocess.Popen(
        [PYTHON, os.path.join(ROOT, "mark6_5", "WallE.py")],
        cwd=os.path.join(ROOT, "mark6_5")
    )
    print("WallE is ON")

    time.sleep(0.2)

    r2 = subprocess.Popen(
        [PYTHON, os.path.join(ROOT, "mark6_5", "R2.py")],
        cwd=os.path.join(ROOT, "mark6_5")
    )
    print("R2 is ON")

    # time to initiallize comms
    time.sleep(1.0)

    # Start venus simulation — it connects to robot PUBs and binds sensor PUBs
    tatooine = subprocess.Popen(
        [PYTHON, os.path.join(ROOT, "mark6_5", "venus.py")],
        cwd=os.path.join(ROOT, "mark6_5")
    )
    print("The mission is ON")

    print("\nAll systems engaged\n")

    # Wait for tatooine (simulation) to close
    tatooine.wait()

    # When window closes, kill the robots too
    print("Abort mission!!")
    walle.terminate()
    r2.terminate()

    # Give them a moment to clean up
    time.sleep(0.3)
    walle.kill()
    r2.kill()

    print("We are done here")

if __name__ == "__main__":
    main()