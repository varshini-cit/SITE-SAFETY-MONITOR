"""
Beginner-friendly entry point for running PPE detection on a video.

Usage (from the project root):

    .venv\\Scripts\\python run_detection.py
    .venv\\Scripts\\python run_detection.py --input data/my_video.mp4 --model models/ppe_model.pt

Defaults come from src/config.py so there is one place to edit.
"""

from src.detect import main

if __name__ == "__main__":
    main()
