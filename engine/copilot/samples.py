"""Sample manager: searches and downloads clean, studio-quality royalty-free instruments."""

import os
import requests

SAMPLES_DIR = os.path.expanduser("~/Desktop/AI-to-Music/samples")

def get_api_key():
    key = os.environ.get("FREESOUND_API_KEY")
    if not key:
        raise ValueError("FREESOUND_API_KEY is not set. Run: export FREESOUND_API_KEY='your_key'")
    return key

def ensure_samples_dir():
    os.makedirs(SAMPLES_DIR, exist_ok=True)
    return SAMPLES_DIR

def search_and_download_sample(query, sample_type="oneshot", filename=None):
    """Search FreeSound with strict duration and quality filters.
    
    sample_type: 'oneshot' (0.1 - 3.0s) or 'loop' (2.0 - 15.0s)
    """
    api_key = get_api_key()
    ensure_samples_dir()
    
    # Strict duration filters: One-shots must be under 3.5 seconds!
    duration_filter = "duration:[0.1 TO 3.5]" if sample_type == "oneshot" else "duration:[2.0 TO 16.0]"
    
    # Enhance query with production keywords
    enhanced_query = f"{query} one shot" if sample_type == "oneshot" and "shot" not in query else query
    
    print(f"🌐 [Web] Searching FreeSound for clean {sample_type}: '{enhanced_query}'...")
    url = "https://freesound.org/apiv2/search/text/"
    params = {
        "query": enhanced_query,
        "filter": duration_filter,
        "token": api_key,
        "fields": "id,name,previews,duration,num_downloads,rating",
        "page_size": 10,
        "sort": "downloads_desc"  # Most downloaded by real producers!
    }
    
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise ValueError(f"FreeSound API error ({response.status_code}): {response.text}")
        
    results = response.json().get("results", [])
    if not results:
        # Fallback without 'one shot' keyword if too strict
        params["query"] = query
        response = requests.get(url, params=params)
        results = response.json().get("results", [])
        if not results:
            raise ValueError(f"No clean samples found on FreeSound for: '{query}'")
        
    # Pick the most downloaded/highest rated isolated hit
    top_sound = results[0]
    sound_name = top_sound["name"]
    sound_id = top_sound["id"]
    duration = top_sound.get("duration", 0)
    preview_url = top_sound.get("previews", {}).get("preview-hq-mp3")
    
    if not preview_url:
        raise ValueError(f"Sound {sound_id} has no preview URL.")
        
    print(f"🎵 [Web] Found: '{sound_name}' ({duration:.2f}s, ID: {sound_id})")
    print(f"⬇️  [Web] Downloading studio sample...")
    
    if not filename:
        clean_name = "".join(c for c in query if c.isalnum() or c in (" ", "_")).rstrip()
        filename = f"{clean_name.replace(' ', '_')}.mp3"
    elif not filename.endswith((".mp3", ".wav")):
        filename += ".mp3"
        
    file_path = os.path.join(SAMPLES_DIR, filename)
    
    audio_data = requests.get(preview_url)
    with open(file_path, "wb") as f:
        f.write(audio_data.content)
        
    print(f"✅ [Web] Saved clean sample to: {file_path}")
    return file_path
