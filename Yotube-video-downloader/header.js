async function download() {
  const input = document.querySelector('.Link-Search');
  const url = input.value.trim();

  if (!url) {
    alert("Please enter a video URL.");
    return;
  }

  const status = document.getElementById('status');
  const thumbnail = document.getElementById('thumbnail');
  const thumbImg = document.getElementById('thumb-img');

  status.innerHTML = "⏳ Analyzing link...";
  if (thumbnail) {
    thumbnail.style.display = 'none'; // Hide thumbnail initially
    thumbImg.src = ''; // Clear previous thumbnail
  }

  // Remove old elements (ask permission?)
  const existingContainer = document.getElementById('quality-options');
  if (existingContainer) existingContainer.remove();
  const existingTextGroup = document.querySelector('.text-group');
  if (existingTextGroup) existingTextGroup.remove();

  try {
    const infoResponse = await fetch('/api/info', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });

    const infoResult = await infoResponse.json();

    if (!infoResponse.ok || infoResult.error) {
      throw new Error(infoResult.error || "Video info fetch failed.");
    }

    // ✅ NEW: Tell user analyzing is done
    status.innerHTML = "✅ Link analyzed successfully! Please choose a quality to download.";

    // Display the thumbnail
    if (thumbnail && thumbImg) {
      thumbImg.src = infoResult.thumbnail;
      thumbnail.style.display = 'block';
    }

    // Create quality selection container
    const qualityContainer = document.createElement('div');
    qualityContainer.id = 'quality-options';
    qualityContainer.style.textAlign = 'center';

    const select = document.createElement('select');
    select.style.width = '100%';
    select.style.maxWidth = '300px';
    select.style.padding = '0.5rem';
    select.style.fontSize = '0.9rem';
    select.style.border = '6px solid dodgerblue';
    select.style.borderRadius = '6px';
    select.style.backgroundColor = 'white';

    // Default option
    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = 'Select Quality';
    defaultOption.disabled = true;
    defaultOption.selected = true;
    select.appendChild(defaultOption);

    // Populate quality options
    infoResult.formats.forEach(f => {
      const option = document.createElement('option');
      option.value = f.format_id;
      option.textContent = f.quality;
      select.appendChild(option);
    });

    qualityContainer.appendChild(select);
    thumbnail.after(qualityContainer);

    // Handle quality selection change
    select.onchange = async () => {
      if (select.value) {
        status.innerHTML = "Downloading...";
        try {
          const downloadResponse = await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, format_id: select.value })
          });
          const downloadResult = await downloadResponse.json();

          if (!downloadResponse.ok || downloadResult.error) {
            throw new Error(downloadResult.error || "Download failed.");
          }

          // Create a link to download the file
          const link = document.createElement('a');
          link.href = downloadResult.file;
          link.download = '';
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);

          status.innerHTML = "✅ Download finished";
        } catch (error) {
          status.innerHTML = "❌ Download Error: " + error.message;
        }
      }
    };

    // Display video title and instructions
    const textGroup = document.createElement('div');
    textGroup.className = 'text-group';

    const titleText = document.createElement('p');
    titleText.textContent = `Video: ${infoResult.title}`;
    const qualityPrompt = document.createElement('p');
    qualityPrompt.textContent = 'Select Video Quality:';
    const instructions = document.createElement('p');
    instructions.textContent = 'Choose a quality to download';

    textGroup.appendChild(titleText);
    textGroup.appendChild(qualityPrompt);
    textGroup.appendChild(instructions);

    qualityContainer.after(textGroup);

  } catch (error) {
    status.innerHTML = "❌ Error: " + error.message;
  }
}



  const mobileMenu = document.getElementById('mobile-menu');
  const navMenu = document.getElementById('navbar-menu');

  mobileMenu.addEventListener('click', () => {
    navMenu.classList.toggle('active');
  });



