import streamlit as st
import yt_dlp
import os
from io import BytesIO
import zipfile
import tempfile
import shutil
import ffmpeg
import time

def set_type(playlist: bool):
    if playlist:
        return '%(playlist_index)s - %(title)s.%(ext)s'
    else:
        return '%(title)s.%(ext)s'

def audio(playlist: bool):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': set_type(playlist=playlist),
        'noplaylist': not playlist,
    }
    return ydl_opts

def video(playlist: bool):
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': set_type(playlist=playlist),
        'noplaylist': not playlist,
    }
    return ydl_opts

def get_playlist_title(url):
    ydl_opts = {
        'quiet': True,
        'simulate': True,
        'extract_flat': True,
        'dump_single_json': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return info.get('title', 'Playlist')
    except Exception as e:
        st.error(f"Erro ao obter o título da playlist: {str(e)}")
        return 'Playlist'

def convert_to_mp3(input_file, output_file):
    ffmpeg.input(input_file).output(output_file).run()

def download_video_audio(playlist_url, codec, is_playlist):
    download_option = {"audio": audio, "video": video}
    
    playlist_title = "Downloads"
    ydl_opts = download_option.get(codec, audio)(playlist=is_playlist)
    temp_dir = tempfile.mkdtemp()
    ydl_opts['outtmpl'] = os.path.join(temp_dir, '%(title)s.%(ext)s')

    try:
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
            
            shutil.rmtree(temp_dir)  # Remove temporary directory and its contents
            zip_buffer.seek(0)
            return zip_buffer, f"{playlist_title}.zip"
        else:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
                file_ext = 'mp3' if codec == 'audio' else 'mp4'
                file_name = f"{info['title']}.{file_ext}"
                file_path = os.path.join(temp_dir, file_name)
                ydl.download([playlist_url])
                
                if codec == 'audio':
                    mp3_file_path = os.path.join(temp_dir, f"{info['title']}.mp3")
                    convert_to_mp3(file_path, mp3_file_path)
                    file_path = mp3_file_path
                
                with open(file_path, 'rb') as f:
                    file_data = BytesIO(f.read())
                os.remove(file_path)  # Remove local file after adding to file_data

            shutil.rmtree(temp_dir)  # Remove temporary directory and its contents
            file_data.seek(0)
            return file_data, file_name
    except Exception as e:
        st.error(f"Erro durante o download: {str(e)}")
        shutil.rmtree(temp_dir)  # Clean up in case of exception

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
        if file_buffer:
            st.download_button(label="Baixar", data=file_buffer, file_name=filename)
    else:
        st.error("Por favor, insira a URL da Playlist do YouTube.")
