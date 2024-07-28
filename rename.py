import os
import requests
import json
import time
import subprocess
import base64
import hmac
import hashlib
import shutil

# Настройка ACRCloud
config = {
    'host': 'your host',
    'access_key': 'your key',
    'access_secret': 'your secret',
    'timeout': 60,  # seconds
    'data_type': 'audio',
    'signature_version': '1'
}

# Получение пути к директории, в которой находится скрипт
script_dir = os.path.dirname(os.path.abspath(__file__))

# Укажите путь к ffmpeg (если он находится в папке рядом со скриптом)
ffmpeg_path = os.path.join(script_dir, 'ffmpeg/bin/ffmpeg.exe')

# Укажите папку назначения (папка рядом со скриптом)
destination_folder = os.path.join(script_dir, 'out')

# Недопустимые символы для названий файлов в Windows
invalid_chars = '<>:"/\\|?*'

# Функция для замены недопустимых символов в имени файла
def sanitize_filename(filename):
    return ''.join(c if c not in invalid_chars else '_' for c in filename)

# Функция для извлечения 30 секунд из середины трека
def extract_middle_segment(file_path, duration=30):
    temp_file = os.path.join(script_dir, "temp_segment.mp3")
    total_duration = get_audio_duration(file_path)
    start_time = (total_duration - duration) / 2
    command = [
        ffmpeg_path,
        '-i', file_path,
        '-ss', str(start_time),
        '-t', str(duration),
        '-acodec', 'copy',
        temp_file
    ]
    subprocess.run(command, check=True)
    return temp_file

# Функция для получения длительности аудиофайла
def get_audio_duration(file_path):
    command = [
        ffmpeg_path,
        '-i', file_path
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = result.stderr.decode('utf-8', errors='ignore')
    duration_line = [line for line in output.split('\n') if 'Duration' in line]
    
    if not duration_line:
        raise ValueError(f"Could not determine duration of file: {file_path}")
    
    duration = duration_line[0].split(',')[0].split(' ')[-1]
    hours, minutes, seconds = map(float, duration.split(':'))
    total_duration = hours * 3600 + minutes * 60 + seconds
    return total_duration

# Функция для создания подписи
def create_signature(string_to_sign, access_secret):
    return base64.b64encode(hmac.new(access_secret.encode(), string_to_sign.encode(), hashlib.sha1).digest()).decode()

# Функция для идентификации трека
def identify_track(file_path):
    url = f"https://{config['host']}/v1/identify"
    try:
        with open(file_path, 'rb') as f:
            sample = f.read()
            timestamp = str(int(time.time()))
            string_to_sign = f"POST\n/v1/identify\n{config['access_key']}\naudio\n{config['signature_version']}\n{timestamp}"
            signature = create_signature(string_to_sign, config['access_secret'])
            
            files = {'sample': sample}
            data = {
                'access_key': config['access_key'],
                'data_type': config['data_type'],
                'signature_version': config['signature_version'],
                'signature': signature,
                'timestamp': timestamp,
                'sample_bytes': len(sample)
            }
            
            response = requests.post(url, files=files, data=data)
            result = response.json()
            
            print(f"Response: {result}")  # Отладочная информация
            
            return result
    except Exception as e:
        print(f"Error identifying segment: {e}")
        return None

# Функция для переименования и перемещения файла
def rename_and_move_file(file_path, title, artist, destination_folder):
    base_name = os.path.basename(file_path)
    new_name = f"{sanitize_filename(title)} - {sanitize_filename(artist)}.mp3"
    new_path = os.path.join(destination_folder, new_name)
    
    # Переименование и перемещение файла с явным указанием кодировки UTF-8
    try:
        if not os.path.exists(destination_folder):
            os.makedirs(destination_folder)
        shutil.move(file_path, new_path)
        print(f"Renamed and moved {base_name} to {new_path}")
    except Exception as e:
        print(f"Error moving file: {e}")

# Сканирование директории с MP3 файлами
def scan_directory(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.mp3'):
                file_path = os.path.join(root, file)
                try:
                    segment_path = extract_middle_segment(file_path)
                    result = identify_track(segment_path)
                    os.remove(segment_path)  # Удаляем временный сегмент
                    if result and 'metadata' in result and 'music' in result['metadata']:
                        music = result['metadata']['music'][0]
                        title = music['title']
                        artist = music['artists'][0]['name']
                        rename_and_move_file(file_path, title, artist, destination_folder)
                    else:
                        print(f"Could not identify {file_path}. Result: {result}")
                except Exception as e:
                    print(f"Error processing file {file_path}: {e}")

# Создание папки назначения, если она не существует
if not os.path.exists(destination_folder):
    os.makedirs(destination_folder)

# Укажите директорию с MP3 файлами (папка рядом со скриптом)
directory = os.path.join(script_dir, 'put')
scan_directory(directory)
