# KODE FINAL UNTUK DEPLOY DI RENDER
import os
import json
import io
import threading
from flask import Flask, request, redirect
from telegram.ext import Application, MessageHandler, filters

# Import library Google
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# --- Konfigurasi Awal dari Environment Variables/Secrets ---
TOKEN = os.environ.get('TOKEN_BOT')
DRIVE_FOLDER_ID = os.environ.get('DRIVE_FOLDER_ID')
GOOGLE_OAUTH_CREDS_STR = os.environ.get('GOOGLE_OAUTH_CREDS')
SCOPES = ['https://www.googleapis.com/auth/drive']

# URL redirect harus SAMA PERSIS dengan yang di Google Cloud Console
# Render.com secara otomatis memberikan URL, kita hanya perlu menambahkan /oauth2callback
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')
REDIRECT_URI = f"{RENDER_EXTERNAL_URL}/oauth2callback" if RENDER_EXTERNAL_URL else "http://localhost:8080/oauth2callback"

drive_service = None
app = Flask(__name__)

# --- Fungsi Otentikasi & Server Web ---
def get_drive_service():
    global drive_service
    creds = None
    if 'GOOGLE_TOKEN_JSON' in os.environ:
        try:
            token_info = json.loads(os.environ['GOOGLE_TOKEN_JSON'])
            creds = Credentials.from_authorized_user_info(token_info, SCOPES)
            drive_service = build('drive', 'v3', credentials=creds)
            print("Berhasil terhubung ke Google Drive dengan token yang ada.")
            return True
        except Exception as e:
            print(f"Gagal memuat token: {e}")
            return False
    return False

@app.route('/')
def home():
    if not get_drive_service():
        creds_info = json.loads(GOOGLE_OAUTH_CREDS_STR)
        flow = Flow.from_client_config(creds_info, scopes=SCOPES, redirect_uri=REDIRECT_URI)
        authorization_url, _ = flow.authorization_url(prompt='consent')
        return f'<h1>Otorisasi Google Diperlukan</h1><p>Silakan klik link berikut untuk memberi izin:</p><p><a href="{authorization_url}">Beri Izin Akses Google Drive</a></p>'
    else:
        return "<h1>Bot Telegram Aktif dan Terhubung ke Google Drive!</h1><p>Anda bisa menutup tab ini. UptimeRobot akan menjaga bot tetap online.</p>"

@app.route('/oauth2callback')
def oauth2callback():
    creds_info = json.loads(GOOGLE_OAUTH_CREDS_STR)
    flow = Flow.from_client_config(creds_info, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials
    token_json = creds.to_json()
    
    html_response = f"""
    <h1>Otorisasi Berhasil!</h1>
    <p>Sekarang, simpan teks di bawah ini sebagai Environment Variable baru di Render:</p>
    <hr>
    <p><b>KEY:</b> <code>GOOGLE_TOKEN_JSON</code></p>
    <p><b>VALUE:</b></p>
    <textarea rows="10" cols="80" readonly>{token_json}</textarea>
    <hr>
    <p>Setelah menyimpan, restart layanan Anda di Render.</p>
    """
    return html_response

# --- Fungsi-fungsi Bot ---
async def handle_photo(update, context):
    if not drive_service:
        await update.effective_message.reply_text("Koneksi ke Google Drive belum siap. Selesaikan proses otorisasi terlebih dahulu.")
        return
        
    chat_id = update.effective_chat.id
    photo_file = update.effective_message.photo[-1]

    if 'pending_photos' not in context.chat_data:
        context.chat_data['pending_photos'] = []
    context.chat_data['pending_photos'].append(photo_file)

    old_jobs = context.job_queue.get_jobs_by_name(f"job_{chat_id}")
    for job in old_jobs:
        job.schedule_removal()
    
    context.job_queue.run_once(process_photos_job, 2, chat_id=chat_id, name=f"job_{chat_id}")

async def process_photos_job(context):
    job = context.job
    chat_id = job.chat_id
    photos_to_process = context.chat_data.pop('pending_photos', [])
    
    if not photos_to_process:
        return

    count = len(photos_to_process)
    await context.bot.send_message(chat_id, f"Menerima {count} foto. Sedang mengupload ke Google Drive...")

    successful_uploads = 0
    for photo in photos_to_process:
        try:
            file = await photo.get_file()
            file_bytes = await file.download_as_bytearray()
            file_stream = io.BytesIO(file_bytes)
            filename = f"telegram_{chat_id}_{photo.file_unique_id}.jpg"
            if upload_to_drive(file_stream, filename):
                successful_uploads += 1
        except Exception as e:
            print(f"Gagal memproses foto: {e}")

    await context.bot.send_message(chat_id, f"Selesai! {successful_uploads} dari {count} foto berhasil diupload ke Google Drive.")

def upload_to_drive(file_stream, filename):
    if not drive_service:
        print("Upload dibatalkan: Drive service tidak terkonfigurasi.")
        return None
    try:
        media = MediaIoBaseUpload(file_stream, mimetype='image/jpeg', resumable=True)
        request = drive_service.files().create(
            media_body=media,
            body={'name': filename, 'parents': [DRIVE_FOLDER_ID]}
        )
        response = request.execute()
        print(f"File '{filename}' berhasil diupload dengan ID: {response.get('id')}")
        return response
    except Exception as e:
        print(f"Gagal mengupload file: {e}")
        return None

# --- Fungsi Utama untuk Menjalankan Bot ---
def run_bot():
    if not get_drive_service():
        print("Bot belum bisa dimulai karena token Google Drive tidak ditemukan. Buka URL utama untuk memulai proses otorisasi.")
        # Kita tidak menghentikan program, agar server web tetap jalan untuk otorisasi
        return

    application = Application.builder().token(TOKEN).build()
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("Bot Telegram siap menerima foto...")
    application.run_polling()

# --- Titik Masuk Program ---
if __name__ == '__main__':
    # Jalankan bot di thread terpisah agar tidak memblokir server web
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    # Jalankan server web Flask sebagai proses utama
    # gunicorn akan menjalankan 'app' ini
    # app.run(host='0.0.0.0', port=8080)
