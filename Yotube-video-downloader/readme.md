from pathlib import Path

# Define the contents of the README and .gitignore files
readme_content = """# YouTube Video Downloader 🎥📥

This project is a fast, easy-to-use YouTube video downloader built with Python and Flask. It allows users to download videos in MP3 and MP4 formats with quality options and basic progress tracking.

## Features ✅
- 🎬 Download videos in MP4 or MP3 format. Mp3 format coming soon!
- 📶 Choose video quality (360p, 720p, etc.)
- 💾 Save download history (locally)
- ⏳ Show basic download progress
- 📁 Downloads saved to a specific folder

## Requirements
- Python 3.7+
- Flask
- yt-dlp
- FFmpeg

## How to Run Locally 🚀
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Start the Flask server: `python app.py`
4. Visit `http://localhost:5000`

## Notes
- Make sure `ffmpeg` is available in the system path or properly linked in `yt-dlp` config.
- The frontend UI is simple, but responsive features are coming soon.
- No login or account required—just paste, choose, and download.

## License
This project is licensed under the MIT License.

---

**Built for educational and personal use. Do not use for copyright-infringing purposes.**
"""

gitignore_content = """# Ignore Python cache files
__pycache__/
*.pyc
*.pyo
*.pyd

# Ignore virtual environments
env/
venv/
ENV/
.VENV/
.venv/

# Ignore VS Code settings
.vscode/

# Ignore system files
.DS_Store
Thumbs.db

# Ignore downloaded videos (your output folder)
downloads/

# Ignore Python environment variables
.env

# Ignore Flask server logs
*.log

# Ignore FFmpeg and yt-dlp binaries/folders
ffmpeg-7.1.1-full_build/
yt-dlp/
"""

# Combine into a single file
combined_content = f"README.md\n{'='*9}\n{readme_content}\n\n.gitignore\n{'='*10}\n{gitignore_content}"

# Save the combined file
output_path = Path("/mnt/data/video_downloader_commit_info.txt")
output_path.write_text(combined_content)

output_path.name
