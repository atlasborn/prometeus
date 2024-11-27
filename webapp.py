import streamlit as st
import yt_dlp
import os
from io import BytesIO
import zipfile
import tempfile

def set_type(playlist: bool):
    if playlist:
        return '%(playlist_index)s - %(title)s.%(ext)s'
    else:
        return '%(title)s.%(ext)s'

def audio(playlist: bool):
    ydl_opts = {
        'format': 'bestvideo[ext=mp4][vcodec=h264]+bestaudio/best',
        'outtmpl': set_type(playlist=playlist),
        'noplaylist': not playlist,
        'merge_output_format': 'mp4',
        'postprocessors': [{'key': 'FFmpegVideoConvertor', 'format': 'mp4'}]
    }
    return ydl_opts

def video(playlist: bool):
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': set_type(playlist=playlist),
        'noplaylist': not playlist,
        'merge_output_format': 'mp4'
        }
    return ydl_opts

def get_playlist_title(url):
    ydl_opts = {
        'quiet': True,
        'simulate': True,
        'extract_flat': True,
        'dump_single_json': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return info.get('title', 'Playlist')

def download_video_audio(playlist_url, codec, is_playlist):
    download_option = {"audio": audio, "video": video}
    
    playlist_title = "Downloads"
    ydl_opts = download_option.get(codec, audio)(playlist=is_playlist)
    temp_dir = tempfile.mkdtemp()
    ydl_opts['outtmpl'] = os.path.join(temp_dir, '%(title)s.%(ext)s')

    if is_playlist:
        playlist_title = get_playlist_title(playlist_url)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([playlist_url])
        
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith('.mp3') or file.endswith('.mp4'):
                        file_path = os.path.join(root, file)
                        with open(file_path, 'rb') as f:
                            zip_file.writestr(file, f.read())
                        os.remove(file_path)  # Remove local file after adding to zip_buffer
        
        os.rmdir(temp_dir)  # Remove temporary directory
        zip_buffer.seek(0)
        return zip_buffer, f"{playlist_title}.zip"
    else:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)
            file_ext = 'mp3' if codec == 'audio' else 'mp4'
            file_name = f"{info['title']}.{file_ext}"
            file_path = os.path.join(temp_dir, file_name)
            ydl.download([playlist_url])
            with open(file_path, 'rb') as f:
                file_data = BytesIO(f.read())
            os.remove(file_path)  # Remove local file after adding to file_data

        os.rmdir(temp_dir)  # Remove temporary directory
        file_data.seek(0)
        return file_data, file_name

st.title("Prometeus Downloader - Youtube Converter [ MP3 MP4]")

# URL da Playlist
playlist_url = st.text_input("Youtube URL")

# Codec
codec = st.radio("Select Output Format:", ('audio', 'video'))

# Playlist
is_playlist = st.checkbox("Playlist")

if st.button("Baixar"):
    if playlist_url:
        file_buffer, filename = download_video_audio(playlist_url, codec, is_playlist)
        st.download_button(label="Baixar", data=file_buffer, file_name=filename)
    else:
        st.error("Por favor, insira a URL da Playlist do YouTube.")
