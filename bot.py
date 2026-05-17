import asyncio
import os
import logging
import asyncpg
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile
from dotenv import load_dotenv

#Загрузка данных с .env файла
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")#Токен телеграм бота
CHANNEL_ID = os.getenv("CHANNEL_ID")#Имя/ID канала 

# Параметры БД
DB_CONFIG = {
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

bot = Bot(token=TOKEN)
dp = Dispatcher()
db_pool = None 



async def init_db():#Функция инициализации БД
   
    global db_pool
    db_pool = await asyncpg.create_pool(**DB_CONFIG)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users_bot (
                id BIGINT PRIMARY KEY,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
                           CREATE TABLE IF NOT EXISTS video_cache (
                tt_url TEXT PRIMARY KEY,
                tg_file_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        

async def check_subscription(user_id: int):#Функция проверки подписки
    
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        
        return member.status in ["member", "creator", "administrator"]
    except Exception as e:
        logging.error(f"Ошибка проверки подписки: {e}")
        return False

async def download_tiktok_video_async(url):
    import yt_dlp
    ydl_opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'format': 'bestvideo+bestaudio/best',
        'noplaylist': True,
        'quiet': True
    }
    loop = asyncio.get_event_loop()
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        
        info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
        return ydl.prepare_filename(info)



@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
  
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users_bot (id, username) 
            VALUES ($1, $2) 
            ON CONFLICT (id) DO UPDATE SET username = EXCLUDED.username;
        """, user_id, username)

   
    is_subbed = await check_subscription(user_id)
    
   
    
    
    
    if not is_subbed:
        await message.answer(f"⚠️ Для использования бота подпишитесь на канал: {CHANNEL_ID}")
    else:
        await message.answer(f"Привет, {message.from_user.full_name}! Пришли ссылку на TikTok.")

@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    
    
    if not await check_subscription(user_id):
        await message.answer(f"❌ Доступ ограничен. Подпишитесь на канал: {CHANNEL_ID}")
        return

    text = message.text
    if text and "tiktok.com" in text:
        status_msg = await message.answer("⏳ Начинаю скачивание...")
        try:
            video_path = await download_tiktok_video_async(text)
            if video_path and os.path.exists(video_path):
                await message.answer_video(FSInputFile(video_path), caption="Готово!")
                os.remove(video_path)
                await status_msg.delete()
            else:
                await status_msg.edit_text("❌ Ошибка при скачивании.")
        except Exception as e:
            logging.error(f"Ошибка: {e}")
            await status_msg.edit_text("⚠️ Ошибка при обработке ссылки.")
    else:
        await message.answer("Пришли корректную ссылку на TikTok 🔗")



async def main():
    
    logging.basicConfig(level=logging.INFO)
    
    
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    await init_db()

    print("Бот запущен...")
    try:
        await dp.start_polling(bot)
    finally:
        await db_pool.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")