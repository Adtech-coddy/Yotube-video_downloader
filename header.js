async function download() {
  const input = document.querySelector('.Link-Search');
  const url = input.value.trim();
  if (!url) {
    alert("Please enter a media URL.");
    return;
  }

  const status = document.getElementById('status');
  const thumbnail = document.getElementById('thumbnail');
  const thumbImg = document.getElementById('thumb-img');

  status.innerHTML = `
    <div class="spinner-container">
      <span class="emoji-spinner">⏳</span>
      <p>Analyzing link...</p>
    </div>`;
  status.style.textAlign = "center";

  // Clear old UI
  if (thumbnail) {
    thumbnail.style.display = 'none';
    thumbImg.src = '';
  }
  document.querySelector('#quality-options')?.remove();
  document.querySelector('.text-group')?.remove();
  document.querySelector('#audio-group')?.remove();

  try {
    const r = await fetch('/api/info', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ url })
    });
    const info = await r.json();
    if (!r.ok || info.error) throw new Error(info.error || 'Info fetch failed.');

    status.innerHTML = "✅ Link analyzed successfully!";

    // Thumbnail
    if (thumbnail && thumbImg) {
      thumbImg.src = info.thumbnail;
      thumbnail.style.display = 'block';
    }

    // Title + Site
    const textGroup = document.createElement('div');
    textGroup.className = 'text-group';
    textGroup.style.textAlign = 'center';
    textGroup.style.marginTop = '20px';

    textGroup.innerHTML = `
      <p style="font-weight:bold;">Title: ${info.title}</p>
      <p style="color:gray;">Source: ${info.site}</p>
      ${info.limited_formats ? "<p style='color:red;'>⚠ Limited formats available (SABR)</p>" : ""}
    `;

    thumbnail.after(textGroup);

    // -------------------------
    // AUDIO DOWNLOAD BUTTON
    // -------------------------
    const audioFormats = info.formats.audio_only || [];
    if (audioFormats.length > 0) {
      const audioGroup = document.createElement('div');
      audioGroup.id = 'audio-group';
      audioGroup.style.textAlign = 'center';
      audioGroup.style.marginTop = '20px';

      const bestAudio = audioFormats[0]; // Already sorted best-first

      audioGroup.innerHTML = `
        <button id="mp3-btn"
          style="padding:10px 15px;font-size:1rem;border-radius:5px;background:dodgerblue;color:white;border:none;cursor:pointer;">
          🎵 Download MP3
        </button>
      `;

      textGroup.after(audioGroup);

      document.getElementById('mp3-btn').onclick = async () => {
        status.innerHTML = "🎵 Downloading audio...";
        try {
          const dr = await fetch('/api/download_audio', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
          });
          const dj = await dr.json();
          if (!dr.ok || dj.error) throw new Error(dj.error);

          const a = document.createElement('a');
          a.href = dj.file;
          a.download = '';
          document.body.appendChild(a);
          a.click();
          a.remove();

          status.innerHTML = "✅ Audio download complete!";
        } catch (e) {
          status.innerHTML = "❌ " + e.message;
        }
      };
    }

    // -------------------------
    // VIDEO QUALITY DROPDOWN
    // -------------------------
    const combined = info.formats.combined || [];
    const videoOnly = info.formats.video_only || [];

    const allVideo = [
      ...combined.map(x => ({ ...x, kind: "combined" })),
      ...videoOnly.map(x => ({ ...x, kind: "video_only" }))
    ];

    if (allVideo.length === 0) return;

    const qualityContainer = document.createElement('div');
    qualityContainer.id = 'quality-options';
    qualityContainer.style.textAlign = 'center';
    qualityContainer.style.marginTop = '16px';

    const select = document.createElement('select');
    select.style.width = '100%';
    select.style.maxWidth = '320px';
    select.style.padding = '0.5rem';
    select.style.fontSize = '0.95rem';
    select.style.border = '2px solid dodgerblue';
    select.style.borderRadius = '6px';
    select.style.backgroundColor = 'white';

    select.innerHTML = `
      <option value="" disabled selected>Select Video Quality</option>
    `;

    allVideo.forEach(f => {
      const opt = document.createElement('option');
      opt.value = `${f.format_id}||${f.kind}`;
      opt.textContent = `${f.resolution} (${f.ext}) ${f.filesize ? " - " + f.filesize : ""}`;
      select.appendChild(opt);
    });

    qualityContainer.appendChild(select);

    (document.getElementById('audio-group') || textGroup).after(qualityContainer);

    select.onchange = async () => {
      const value = select.value;
      if (!value) return;

      const [format_id, format_kind] = value.split("||");

      status.innerHTML = "📥 Downloading video...";

      try {
        const dr = await fetch('/api/download', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url, format_id, format_kind })
        });

        const dj = await dr.json();
        if (!dr.ok || dj.error) throw new Error(dj.error);

        const a = document.createElement('a');
        a.href = dj.file;
        a.download = '';
        document.body.appendChild(a);
        a.click();
        a.remove();

        status.innerHTML = "✅ Video download finished!";
      } catch (e) {
        status.innerHTML = "❌ " + e.message;
      }
    };

  } catch (err) {
    status.innerHTML = "❌ Error: " + err.message;
  }
}
