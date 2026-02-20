from flask import Flask, request, jsonify, send_from_directory, send_file
import yt_dlp
import os
import uuid
import threading

app = Flask(__name__)
DOWNLOAD_FOLDER = 'downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

@app.route('/')
def serve_homepage():
    return send_from_directory('.', 'header.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

# API: Get Video Info
@app.route('/api/info', methods=['POST'])
def video_info():
    data = request.get_json()
    video_url = data.get('url')

    if not video_url:
        return jsonify({'error': 'No URL provided'}), 400

    ydl_opts = {
        'quiet': True,
        'skip_download': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
        
        # Select the highest-quality thumbnail
        thumbnail = info.get('thumbnail')
        if not thumbnail and 'thumbnails' in info:
            thumbnails = sorted(
                info.get('thumbnails', []),
                key=lambda x: x.get('width', 0) * x.get('height', 0),
                reverse=True
            )
            thumbnail = thumbnails[0].get('url') if thumbnails else ''

        # Filter and format video quality options
        formats = []
        for f in info.get('formats', []):
            if f.get('ext') in ['mp4', 'webm'] and f.get('format_id') and f.get('height'):
                resolution = f"{f.get('height')}p"
                formats.append({
                    'format_id': f['format_id'],
                    'ext': f['ext'],
                    'quality': f"{resolution} - {f['ext']}",
                    'resolution': resolution
                })

        # Sort formats by resolution (highest to lowest)
        formats = sorted(formats, key=lambda x: int(x['resolution'][:-1]), reverse=True)

        return jsonify({
            'title': info.get('title', 'No Title'),
            'thumbnail': thumbnail or 'https://via.placeholder.com/300x169?text=No+Thumbnail',
            'formats': formats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Download Video by Format
@app.route('/api/download', methods=['POST'])
def api_download():
    data = request.get_json()
    video_url = data.get('url')
    format_id = data.get('format_id')

    if not video_url or not format_id:
        return jsonify({'error': 'Missing URL or format_id'}), 400

    filename = f"{uuid.uuid4()}.mp4"
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)

    ydl_opts = {
        'format': format_id,
        'outtmpl': filepath,
        'merge_output_format': 'mp4'
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        print(f"✅ Download finished: {filepath}")
        return jsonify({'message': 'Download completed', 'file': f'/download_file/{filename}'})
    except Exception as e:
        print(f"❌ Download error: {e}")
        return jsonify({'error': str(e)}), 500

# Serve the downloaded file
@app.route('/download_file/<filename>')
def serve_downloaded_file(filename):
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({'error': 'File not found'}), 404

# Keep your old endpoint (for legacy support)
@app.route('/download', methods=['POST'])
def legacy_download():
    data = request.get_json()
    video_url = data.get('url')

    if not video_url:
        return jsonify({'error': 'No URL provided'}), 400

    filename = f"{uuid.uuid4()}.mp4"
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)

    threading.Thread(target=run_yt_dlp, args=(video_url, filepath)).start()

    return jsonify({'message': 'Download started', 'filename': filename})

def run_yt_dlp(video_url, filepath):
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': filepath,
        'merge_output_format': 'mp4'
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        print(f"✅ Download completed: {filepath}")
    except Exception as e:
        print(f"❌ Download error: {e}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
