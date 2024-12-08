import streamlit as st
from pytube import YouTube
import os
from io import BytesIO
import zipfile
import tempfile
import shutil
import logging

logging.basicConfig(level=logging.INFO)

def download_video_audio(url, codec, is_playlist):
    temp_dir = tempfile.mkdtemp()

    try:
        if is_playlist:
            st.error("A funcionalidade de playlist ainda não está disponível para `pytube`.")
            return None, None
        else:
            yt = YouTube(url)
            if codec == 'audio':
                stream = yt.streams.filter(only_audio=True).first()
            else:
                stream = yt.streams.get_highest_resolution()

            file_name = f"{yt.title}.{stream.subtype}"
            file_path = os.path.join(temp_dir, file_name)
            stream.download(output_path=temp_dir, filename=file_name)
            
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
        return None, None

st.title("Prometeus Downloader - Youtube Converter [ MP3 MP4]")

# URL da Playlist
url = st.text_input("Youtube URL")

# Codec
codec = st.radio("Select Output Format:", ('audio', 'video'))

# Playlist
is_playlist = st.checkbox("Playlist")

if st.button("Baixar"):
    if url:
        file_buffer, filename = download_video_audio(url, codec, is_playlist)
        if file_buffer:
            st.download_button(label="Baixar", data=file_buffer, file_name=filename)
        else:
            st.error("Erro ao baixar o vídeo. Por favor, verifique a URL e tente novamente.")
    else:
        st.error("Por favor, insira a URL da Playlist do YouTube.")
