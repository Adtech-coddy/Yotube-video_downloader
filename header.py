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
# Common yt-dlp options (B2)
# ---------------------------
def _common_ytdlp_opts(outtmpl=None):
    """
    Use player clients that typically expose HD formats.
    Do NOT skip dash/hls — we want DASH/HLS formats included.
    """
    opts = {
        "quiet": True,
        "noprogress": True,
        "nocheckcertificate": True,
        "retries": 5,
        "fragment_retries": 5,
        "http_headers": {
            # Android-like UA often returns richer format lists
            "User-Agent": "Mozilla/5.0 (Linux; Android 13)"
        },
        "extractor_args": {
            "youtube": {
                "player_client": [
                    "android",
                    "android_creator",
                    "ios",
                    "tv_embedded",
                    "mobile"
                ],
                # Ensure we do not skip DASH/HLS
                "skip": []
            }
        },
        # Make JSON parsing robust
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
        combined = []   # formats that already have video+audio (height + acodec not none)
        video_only = [] # formats with vcodec != none and (acodec none or height present but acodec none) - usually DASH
        audio_only = [] # formats with no height and have acodec

        # Track highest resolution found
        max_height = 0

        for f in raw_formats:
            fmt_id = f.get("format_id")
            ext = f.get("ext") or ""
            height = f.get("height")  # may be None
            vcodec = f.get("vcodec")
            acodec = f.get("acodec")
            filesize = f.get("filesize") or f.get("filesize_approx")
            fps = f.get("fps")
            tbr = f.get("tbr") or f.get("abr")  # bitrate

            # Combined (video+audio) - some formats come with both
            if height and acodec not in (None, "none") and vcodec not in (None, "none"):
                item = {
                    "format_id": fmt_id,
                    "ext": ext,
                    "resolution": f"{height}p",
                    "height": height,
                    "fps": fps,
                    "bitrate": tbr,
                    "filesize": human_size(filesize),
                    "note": f.get("format_note")
                }
                combined.append(item)
                max_height = max(max_height, height)

            # Video-only (DASH) - has vcodec, has height, but audio missing/none
            elif height and vcodec not in (None, "none") and acodec in (None, "none"):
                item = {
                    "format_id": fmt_id,
                    "ext": ext,
                    "resolution": f"{height}p",
                    "height": height,
                    "fps": fps,
                    "bitrate": tbr,
                    "filesize": human_size(filesize),
                    "note": f.get("format_note")
                }
                video_only.append(item)
                max_height = max(max_height, height)

            # Audio-only
            elif not height and acodec not in (None, "none"):
                abr = f.get("abr") or 0
                item = {
                    "format_id": fmt_id,
                    "ext": ext,
                    "abr": abr,
                    "bitrate": tbr,
                    "filesize": human_size(filesize),
                    "note": f.get("format_note")
                }
                audio_only.append(item)

        # Deduplicate format ids across groups (keep combined separate)
        # Some formats may appear duplicated; ensuring uniqueness by format_id
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

        # Determine if formats are limited (only <=360p)
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
# Client must POST JSON:
# {
#   "url": "...",
#   "format_id": "251",           # the format id chosen from /api/info
#   "format_kind": "combined"     # one of "combined","video_only","audio_only"
# }
# ---------------------------
@app.route('/api/download', methods=['POST'])
def api_download():
    data = request.get_json() or {}
    video_url = data.get("url")
    format_id = data.get("format_id")
    format_kind = data.get("format_kind")  # combined | video_only | audio_only

    if not video_url or not format_id:
        return jsonify({"error": "Missing url or format_id"}), 400

    # output filename
    out_name = f"{uuid.uuid4()}.%(ext)s"
    filepath_template = os.path.join(DOWNLOAD_FOLDER, out_name)

    # build ytdlp options
    ydl_opts = _common_ytdlp_opts(outtmpl=filepath_template)

    # Decide actual format string to request from yt-dlp
    # - If combined: ask for that format id directly (it has audio+video)
    # - If video_only: request format_id + best audio and merge to mp4
    # - If audio_only: request that audio format (no merge)
    if format_kind == "video_only":
        # combine video-only with best audio (prefer m4a/mp4 compatible)
        requested_format = f"{format_id}+bestaudio[ext=m4a]/bestaudio/best"
        ydl_opts.update({
            "format": requested_format,
            "merge_output_format": "mp4"  # ensure final is mp4 when merging
        })
    elif format_kind == "audio_only":
        ydl_opts.update({
            "format": format_id  # should be an audio format id like 251 or similar
        })
    else:
        # default: treat as combined (video+audio present)
        ydl_opts.update({
            "format": format_id,
            "merge_output_format": "mp4"
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # download returns list of files created; yt-dlp names final extension based on chosen format
            ydl.download([video_url])

        # find the actual produced file in DOWNLOAD_FOLDER (newest)
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
# API: Download audio-only as MP3 (convenience)
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
    # debug on for now; set debug=False in production
    app.run(debug=True, host="0.0.0.0", port=8080)
