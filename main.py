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

# --- Konfigurasi Awal ---
TOKEN = os.environ.get('TOKEN_BOT')
DRIVE_FOLDER_ID = os.environ.get('DRIVE_FOLDER_ID')
GOOGLE_OAUTH_CREDS_STR = os.environ.get('GOOGLE_OAUTH_CREDS')
SCOPES = ['https://www.googleapis.com/auth/drive']

# URL redirect harus SAMA PERSIS dengan yang di Google Cloud Console
REDIRECT_URI = f"https://{os.environ.get('REPL_ID', '')}.replit.dev/oauth2callback" if 'REPL_ID' in os.environ else "http://localhost:8080/oauth2callback"

drive_service = None
app = Flask(__name__)

# --- Fungsi Otentikasi & Server Web (BARU) ---
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
        return "<h1>Bot Telegram Aktif dan Terhubung ke Google Drive!</h1><p>Anda bisa menutup tab ini.</p>"

@app.route('/oauth2callback')
def oauth2callback():
    creds_info = json.loads(GOOGLE_OAUTH_CREDS_STR)
    flow = Flow.from_client_config(creds_info, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials
    token_json = creds.to_json()
    
    html_response = f"""
    <h1>Otorisasi Berhasil!</h1>
    <p>Sekarang, simpan teks di bawah ini sebagai secret baru di Replit:</p>
    <hr>
    <p><b>KEY:</b> <code>GOOGLE_TOKEN_JSON</code></p>
    <p><b>VALUE:</b></p>
    <textarea rows="10" cols="80" readonly>{token_json}</textarea>
    <hr>
    <p>Setelah menyimpan secret, hentikan dan jalankan ulang bot-nya.</p>
    """
    return html_response

# --- Fungsi-fungsi Bot (Sama seperti sebelumnya, tidak ada perubahan) ---
# ... (Semua fungsi handle_photo, process_photos_job, upload_to_drive tetap sama) ...
# (Untuk mempersingkat, saya tidak tampilkan lagi di sini, tapi pastikan semua fungsi itu masih ada di bawah bagian ini)

async def handle_photo(update, context):
    # ... (kode handle_photo sama)
    pass
async def process_photos_job(context):
    # ... (kode process_photos_job sama)
    pass
def upload_to_drive(file_stream, filename):
    # ... (kode upload_to_drive sama)
    pass

# --- Fungsi Utama untuk Menjalankan Bot ---
def run_bot():
    if not get_drive_service():
        print("Bot belum bisa dimulai. Selesaikan proses otorisasi Google terlebih dahulu melalui web.")
        return

    application = Application.builder().token(TOKEN).build()
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("Bot Telegram siap menerima foto...")
    application.run_polling()

# --- Titik Masuk Program ---
if __name__ == '__main__':
    # Pastikan semua fungsi lama masih ada di atas
    # (Kode di bawah ini adalah salinan dari kode sebelumnya, pastikan fungsi-fungsinya ada)
    async def handle_photo(update, context):
        if not drive_service: await update.effective_message.reply_text("Koneksi ke Google Drive belum siap."); return
        chat_id = update.effective_chat.id; photo_file = update.effective_message.photo[-1]
        if 'pending_photos' not in context.chat_data: context.chat_data['pending_photos'] = []
        context.chat_data['pending_photos'].append(photo_file)
        old_jobs = context.job_queue.get_jobs_by_name(f"job_{chat_id}");
        for job in old_jobs: job.schedule_removal()
        context.job_queue.run_once(process_photos_job, 2, chat_id=chat_id, name=f"job_{chat_id}")

    async def process_photos_job(context):
        job = context.job; chat_id = job.chat_id; photos_to_process = context.chat_data.pop('pending_photos', [])
        if not photos_to_process: return
        count = len(photos_to_process); await context.bot.send_message(chat_id, f"Menerima {count} foto. Mengupload...")
        successful_uploads = 0
        for photo in photos_to_process:
            try:
                file = await photo.get_file(); file_bytes = await file.download_as_bytearray()
                file_stream = io.BytesIO(file_bytes); filename = f"telegram_{chat_id}_{photo.file_unique_id}.jpg"
                if upload_to_drive(file_stream, filename): successful_uploads += 1
            except Exception as e: print(f"Gagal proses foto: {e}")
        await context.bot.send_message(chat_id, f"Selesai! {successful_uploads} dari {count} foto berhasil diupload.")

    def upload_to_drive(file_stream, filename):
        if not drive_service: return None
        try:
            media = MediaIoBaseUpload(file_stream, mimetype='image/jpeg', resumable=True)
            request = drive_service.files().create(media_body=media, body={'name': filename, 'parents': [DRIVE_FOLDER_ID]});
            response = request.execute(); print(f"File '{filename}' diupload, ID: {response.get('id')}"); return response
        except Exception as e: print(f"Gagal upload: {e}"); return None

    # Jalankan server web Flask di thread terpisah
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8080))
    flask_thread.daemon = True
    flask_thread.start()
    
    # Jalankan bot
    run_bot()
