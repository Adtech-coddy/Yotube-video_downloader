from flask import Flask, request, jsonify, send_from_directory, send_file
import yt_dlp
import os
import uuid
import math

app = Flask(__name__)
DOWNLOAD_FOLDER = 'downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)


@app.route('/')
def serve_homepage():
    return send_from_directory('.', 'header.html')


@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)


# ---------------------------
# Common yt-dlp options (UPDATED)
# ---------------------------
def _common_ytdlp_opts(outtmpl=None):
    """
    Cleaner, more reliable config for better format exposure.
    """
    opts = {
        "quiet": True,
        "noprogress": True,
        "nocheckcertificate": True,
        "retries": 5,
        "fragment_retries": 5,
        "format_sort": ["res", "fps", "br"],  # prioritize higher resolution
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13)"
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["android"],  # IMPORTANT FIX
                "skip": []
            }
        },
        "forcejson": False,
    }

    if outtmpl:
        opts["outtmpl"] = outtmpl

    return opts


# ---------------------------
# Utility helpers
# ---------------------------
def human_size(bytes_val):
    if not bytes_val:
        return None
    try:
        bytes_val = int(bytes_val)
    except Exception:
        return None
    if bytes_val <= 0:
        return None
    sizes = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(bytes_val, 1024)))
    p = math.pow(1024, i)
    s = round(bytes_val / p, 2)
    return f"{s} {sizes[i]}"


# ---------------------------
# API: GET video + audio info (grouped)
# ---------------------------
@app.route('/api/info', methods=['POST'])
def api_info():
    data = request.get_json() or {}
    video_url = data.get('url')
    if not video_url:
        return jsonify({'error': 'No URL provided'}), 400

    ydl_opts = _common_ytdlp_opts()
    ydl_opts["skip_download"] = True

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

        # pick best thumbnail
        thumbnail = info.get("thumbnail")
        if not thumbnail and "thumbnails" in info:
            thumbs = sorted(info["thumbnails"], key=lambda t: (t.get("width") or 0) * (t.get("height") or 0), reverse=True)
            if thumbs:
                thumbnail = thumbs[0].get("url")

        raw_formats = info.get("formats") or []

        # Build grouped format lists (cleaned)
        combined = []   # formats that already have video+audio
        video_only = [] # video without audio
        audio_only = [] # audio only

        max_height = 0

        for f in raw_formats:
            fmt_id = f.get("format_id")
            ext = f.get("ext") or ""
            height = f.get("height")
            vcodec = f.get("vcodec")
            acodec = f.get("acodec")
            filesize = f.get("filesize") or f.get("filesize_approx")
            fps = f.get("fps")
            tbr = f.get("tbr") or f.get("abr")

            if height and acodec not in (None, "none") and vcodec not in (None, "none"):
                combined.append({
                    "format_id": fmt_id,
                    "ext": ext,
                    "resolution": f"{height}p",
                    "height": height,
                    "fps": fps,
                    "bitrate": tbr,
                    "filesize": human_size(filesize),
                    "note": f.get("format_note")
                })
                max_height = max(max_height, height)
            elif height and vcodec not in (None, "none") and acodec in (None, "none"):
                video_only.append({
                    "format_id": fmt_id,
                    "ext": ext,
                    "resolution": f"{height}p",
                    "height": height,
                    "fps": fps,
                    "bitrate": tbr,
                    "filesize": human_size(filesize),
                    "note": f.get("format_note")
                })
                max_height = max(max_height, height)
            elif not height and acodec not in (None, "none"):
                audio_only.append({
                    "format_id": fmt_id,
                    "ext": ext,
                    "abr": f.get("abr") or 0,
                    "bitrate": tbr,
                    "filesize": human_size(filesize),
                    "note": f.get("format_note")
                })

        def uniq_by_id(lst):
            seen = set()
            out = []
            for x in lst:
                if x["format_id"] not in seen:
                    out.append(x)
                    seen.add(x["format_id"])
            return out

        combined = sorted(uniq_by_id(combined), key=lambda x: (x.get("height") or 0), reverse=True)
        video_only = sorted(uniq_by_id(video_only), key=lambda x: (x.get("height") or 0), reverse=True)
        audio_only = sorted(uniq_by_id(audio_only), key=lambda x: (x.get("abr") or 0), reverse=True)

        limited = True
        if max_height and max_height > 360:
            limited = False

        return jsonify({
            "title": info.get("title", "No Title"),
            "uploader": info.get("uploader"),
            "duration": info.get("duration"),
            "thumbnail": thumbnail or "https://via.placeholder.com/300x169?text=No+Thumbnail",
            "site": info.get("extractor_key", info.get("extractor", "Unknown")),
            "limited_formats": limited,
            "formats": {
                "combined": combined,
                "video_only": video_only,
                "audio_only": audio_only
            }
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------
# API: DOWNLOAD selected format
# ---------------------------
@app.route('/api/download', methods=['POST'])
def api_download():
    data = request.get_json() or {}
    video_url = data.get("url")
    format_id = data.get("format_id")
    format_kind = data.get("format_kind")  # combined | video_only | audio_only

    if not video_url or not format_id:
        return jsonify({"error": "Missing url or format_id"}), 400

    # First, get video info to fetch the title
    try:
        with yt_dlp.YoutubeDL(_common_ytdlp_opts()) as ydl:
            info = ydl.extract_info(video_url, download=False)
        video_title = sanitize_filename(info.get("title", "video"))
    except Exception as e:
        video_title = "video"  # fallback title

    # output filename template
    filepath_template = os.path.join(DOWNLOAD_FOLDER, video_title + ".%(ext)s")

    # build yt-dlp options
    ydl_opts = _common_ytdlp_opts(outtmpl=filepath_template)

    if format_kind == "video_only":
        requested_format = f"{format_id}+bestaudio[ext=m4a]/bestaudio/best"
        ydl_opts.update({
            "format": requested_format,
            "merge_output_format": "mp4",   # force merged filename to match outtmpl
        })
    elif format_kind == "audio_only":
        ydl_opts.update({
            "format": format_id
        })
    else:
        # combined format
        ydl_opts.update({
            "format": format_id,
            "merge_output_format": "mp4"  # optional, ensures mp4
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # find produced file
        files = sorted(
            (os.path.join(DOWNLOAD_FOLDER, f) for f in os.listdir(DOWNLOAD_FOLDER)),
            key=lambda p: os.path.getmtime(p),
            reverse=True
        )
        if files:
            produced = files[0]
            produced_name = os.path.basename(produced)
            return jsonify({"message": "Download completed", "file": f"/download_file/{produced_name}"})
        else:
            return jsonify({"error": "Download finished but no file found"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------
# API: Download audio-only as MP3
# ---------------------------
@app.route('/api/download_audio', methods=['POST'])
def api_download_audio():
    data = request.get_json() or {}
    video_url = data.get("url")
    if not video_url:
        return jsonify({"error": "Missing url"}), 400

    filename = f"{uuid.uuid4()}.mp3"
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)

    ydl_opts = _common_ytdlp_opts(outtmpl=filepath)
    ydl_opts.update({
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192"
        }]
    })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        return jsonify({"message": "Audio download completed", "file": f"/download_file/{filename}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------
# Serve downloaded files
# ---------------------------
@app.route('/download_file/<filename>')
def serve_file(filename):
    path = os.path.join(DOWNLOAD_FOLDER, filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return jsonify({"error": "File not found"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))