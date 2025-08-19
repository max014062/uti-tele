import os
from telegram.ext import Updater, MessageHandler, Filters

def handle_photo(update, context):
    """Fungsi ini akan dipanggil setiap kali bot menerima foto."""
    update.message.reply_text("Foto diterima via GitHub deploy!")
    print("Menerima foto dan mengirim balasan.")

def main():
    """Fungsi utama untuk menjalankan bot."""
    # Mengambil token dari Secrets yang akan kita atur di Replit nanti
    TOKEN = os.environ.get('TOKEN_BOT', 'TokenBelumDiSet') # .get() biar aman
    
    if TOKEN == 'TokenBelumDiSet':
        print("ERROR: TOKEN_BOT belum diatur di Secrets!")
        return

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(MessageHandler(Filters.photo, handle_photo))

    updater.start_polling()
    print("Bot sedang berjalan, di-deploy dari GitHub...")
    updater.idle()

if __name__ == '__main__':
    main()
