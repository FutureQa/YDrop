import sys
import threading
import time
from pathlib import Path
sys.path.append('e:/YDrop')

from core.downloader import DownloadQueue, DownloadItem

def run_test(name, url, format_type, format_key):
    print(f"\n{'='*50}\nStarting test: {name}\nFormat Key: {format_key}\n{'='*50}")
    
    out_folder = Path('e:/YDrop/test_out')
    out_folder.mkdir(exist_ok=True)
    
    parts = format_key.split('|')
    if format_type == 'video':
        qual = parts[1].lower() if len(parts) > 1 else 'best'
        fmt = parts[2].lower() if len(parts) > 2 else 'mp4'
        codec = parts[3].lower() if len(parts) > 3 and parts[3] else 'any'
        title = f"{fmt}-{qual}-{codec}"
    else:
        fmt = parts[1].lower() if len(parts) > 1 else 'mp3'
        qual = parts[2].lower() if len(parts) > 2 else 'best'
        # Convert "Best Quality" to "best" to avoid spaces in test file names
        qual = qual.replace(' ', '_')
        title = f"{fmt}-{qual}-any"

    item = DownloadItem(
        url=url, 
        title=title, 
        format_type=format_type, 
        format_key=format_key, 
        output_folder=str(out_folder),
        output_template=f"{title}.%(ext)s"
    )

    q = DownloadQueue()

    def on_update(item_id, item_obj):
        if item_obj.progress > 0:
            print(f"\rProgress: {item_obj.progress*100:.1f}% | Status: {item_obj.status} | ETA: {item_obj.eta}", end="")
        else:
            print(f"\nUpdate: Status: {item_obj.status}")

    q.set_update_callback(on_update)
    q.add(item)

    while item.status not in ('done', 'error', 'cancelled'):
        time.sleep(0.5)

    print(f'\n\nResult for {name}: {item.status}')
    if item.status == 'error':
        print(f"Error Message: {item.error_message}")

if __name__ == '__main__':
    url = 'https://youtu.be/RrESvSRNpeo?si=OXe8xn4DFVteg5Z1'
    
    tests = [
        # Video Tests (Container + Codec)
        ('Video_MP4_Any', 'video', 'video|1080p|MP4|'),
        ('Video_MKV_Any', 'video', 'video|1080p|MKV|'),
        ('Video_WEBM_Any', 'video', 'video|1080p|WEBM|'),
        ('Video_MP4_H264', 'video', 'video|1080p|MP4|avc1'),
        ('Video_MP4_AV1', 'video', 'video|1080p|MP4|av01'),
        ('Video_WEBM_VP9', 'video', 'video|1080p|WEBM|vp09'),
        
        # Audio Tests (Format)
        ('Audio_MP3', 'audio', 'audio|MP3|192k'),
        ('Audio_M4A', 'audio', 'audio|M4A|192k'),
        ('Audio_FLAC', 'audio', 'audio|FLAC|Best Quality'),
        ('Audio_WAV', 'audio', 'audio|WAV|Best Quality'),
        ('Audio_OGG', 'audio', 'audio|OGG|192k'),
        ('Audio_AAC', 'audio', 'audio|AAC|192k'),
        ('Audio_OPUS', 'audio', 'audio|OPUS|192k'),
    ]
    
    for name, ftype, fkey in tests:
        run_test(name, url, ftype, fkey)
        
    print("\nAll tests completed!")
