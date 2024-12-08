import streamlit as st
import pafy
import os
from io import BytesIO
import zipfile
import tempfile
import shutil
import ffmpeg
import logging

logging.basicConfig(level=logging.INFO)

def set_type(playlist: bool):
    if playlist:
        return '%(playlist_index)s - %(title)s.%(ext)s'
    else:
        return '%(title)s.%(ext)s'

def get_playlist_title(url):
    ydl_opts = {
        'quiet': True,
        'simulate': True,
        'extract_flat': True,
        'dump_single_json': True,
    }
    try:
        playlist = pafy.get_playlist(url)
        return playlist['title']
    except Exception as e:
        logging.error(f"Erro ao obter o título da playlist: {str(e)}")
        st.error(f"Erro ao obter o título da playlist: {str(e)}")
        return 'Playlist'

def convert_to_mp3(input_file, output_file):
    try:
        ffmpeg.input(input_file).output(output_file).run()
    except Exception as e:
        logging.error(f"Erro na conversão para MP3: {str(e)}")
        st.error(f"Erro na conversão para MP3: {str(e)}")

def download_video_audio(playlist_url, codec, is_playlist):
    temp_dir = tempfile.mkdtemp()

    try:
        if is_playlist:
            playlist = pafy.get_playlist(playlist_url)
            playlist_title = playlist['title']
            
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                for item in playlist['items']:
                    p = item['pafy']
                    bestaudio = p.getbestaudio()
                    file_name = f"{p.title}.{bestaudio.extension}"
                    file_path = os.path.join(temp_dir, file_name)
                    bestaudio.download(filepath=file_path)
                    
                    if codec == 'audio':
                        mp3_file_path = os.path.join(temp_dir, f"{p.title}.mp3")
                        convert_to_mp3(file_path, mp3_file_path)
                        file_path = mp3_file_path

                    with open(file_path, 'rb') as f:
                        zip_file.writestr(file_name, f.read())
                    os.remove(file_path)

            shutil.rmtree(temp_dir)
            zip_buffer.seek(0)
            if zip_buffer.getbuffer().nbytes == 0:
                st.warning("O arquivo ZIP está vazio. Verifique se os vídeos foram baixados corretamente.")
            return zip_buffer, f"{playlist_title}.zip"
        else:
            p = pafy.new(playlist_url)
            bestaudio = p.getbestaudio()
            file_name = f"{p.title}.{bestaudio.extension}"
            file_path = os.path.join(temp_dir, file_name)
            bestaudio.download(filepath=file_path)
            
            if codec == 'audio':
                mp3_file_path = os.path.join(temp_dir, f"{p.title}.mp3")
                convert_to_mp3(file_path, mp3_file_path)
                file_path = mp3_file_path
            
            with open(file_path, 'rb') as f:
                file_data = BytesIO(f.read())
            os.remove(file_path)

            shutil.rmtree(temp_dir)
            file_data.seek(0)
            return file_data, file_name
    except Exception as e:
        logging.error(f"Erro durante o download: {str(e)}")
        st.error(f"Erro durante o download: {str(e)}")
        shutil.rmtree(temp_dir)

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
