import asyncio

from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode

# В актуальных версиях (например, aiogram 3.17+) CallbackData в таком модуле:
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

API_TOKEN = "8189643318:AAEjvXhCyKd7uVsp9ZuGMpzKXtj7aqYaPKg"

# ===== Белый список пользователей (user_id) =====
ALLOWED_USERS = {
    324213868,  # <-- впишите реальные ID людей, которым разрешён доступ
    155987540,
    110374107,
    58536654,
    # ... добавляйте нужные ID
}

# Список чатов, куда бот будет рассылать
CHAT_IDS = [
    -4725970015,
    -4606527215,
    -1001684876104,
    -1001821795786,
    -1002213297288,
    -1002004317785,
    -1001837008670,
    # Дополняйте при необходимости
]

# Набор пользователей, от которых ждём текст
WAITING_FOR_BROADCAST_TEXT = set()

# Словарь: user_id -> текст, который они хотят разослать
BROADCAST_TEXTS = {}

# CallbackData для инлайн-кнопок «Да/Нет»
class ConfirmBroadcast(CallbackData, prefix="confirm_broadcast"):
    decision: str  # "yes" или "no"

def get_main_menu() -> ReplyKeyboardMarkup:
    """
    Возвращаем «Reply-клавиатуру» с кнопкой «Сделать рассылку».
    """
    keyboard = [
        [KeyboardButton(text="Сделать рассылку")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

async def cmd_start(message: Message):
    """
    Приветствие и показ основной меню-клавиатуры.
    """
    # Проверяем, есть ли user_id в белом списке
    if message.from_user.id not in ALLOWED_USERS:
        await message.answer("У вас нет доступа к этому боту.")
        return

    await message.answer(
        text="Нажмите «Сделать рассылку», после чего введите текст сообщения.",
        reply_markup=get_main_menu()
    )

async def handle_make_broadcast(message: Message):
    """
    Когда пользователь нажимает кнопку «Сделать рассылку».
    """
    # Проверка доступа
    if message.from_user.id not in ALLOWED_USERS:
        await message.answer("У вас нет доступа к этому боту.")
        return

    WAITING_FOR_BROADCAST_TEXT.add(message.from_user.id)
    await message.answer("Напишите сообщение, которое хотите разослать всем.")

async def process_broadcast_text(message: Message):
    """
    Срабатывает, когда пользователь в WAITING_FOR_BROADCAST_TEXT:
    запрашиваем подтверждение «Да / Нет».
    """
    # Проверка доступа
    if message.from_user.id not in ALLOWED_USERS:
        await message.answer("У вас нет доступа к этому боту.")
        return

    user_id = message.from_user.id
    # Убираем из "ожидающих"
    WAITING_FOR_BROADCAST_TEXT.remove(user_id)

    # Запоминаем текст
    BROADCAST_TEXTS[user_id] = message.text

    # Инлайн-кнопки
    kb = InlineKeyboardBuilder()
    kb.button(text="Да", callback_data=ConfirmBroadcast(decision="yes"))
    kb.button(text="Нет", callback_data=ConfirmBroadcast(decision="no"))
    kb.adjust(2)

    await message.answer(
        text=f"Вы точно хотите отправить это сообщение?\n\n{message.text}",
        reply_markup=kb.as_markup()
    )

async def confirm_broadcast_callback(call: CallbackQuery, callback_data: ConfirmBroadcast):
    """
    Обработка нажатия «Да» / «Нет».
    """
    # Проверка доступа
    if call.from_user.id not in ALLOWED_USERS:
        await call.message.answer("У вас нет доступа к этому боту.")
        # Уберём кнопки и ответим, чтобы не зависало
        await call.message.edit_reply_markup(None)
        await call.answer()
        return

    user_id = call.from_user.id
    broadcast_text = BROADCAST_TEXTS.pop(user_id, None)

    if callback_data.decision == "yes" and broadcast_text:
        bot = call.bot
        success_count = 0
        for cid in CHAT_IDS:
            try:
                await bot.send_message(chat_id=cid, text=broadcast_text)
                success_count += 1
            except Exception as e:
                print(f"Ошибка при отправке в чат {cid}: {e}")

        await call.message.answer(f"Сообщение разослано в {success_count} чатов(а).")
    else:
        await call.message.answer("Рассылка отменена.")

    # Убираем inline-кнопки, чтобы нельзя было нажимать повторно
    await call.message.edit_reply_markup(None)
    # Ответ на коллбэк — убирает «часики»
    await call.answer()

async def main():
    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Хэндлер команды /start
    dp.message.register(cmd_start, lambda msg: msg.text == "/start")

    # Хэндлер нажатия «Сделать рассылку»
    dp.message.register(handle_make_broadcast, lambda msg: msg.text == "Сделать рассылку")

    # Хэндлер ввода текста для рассылки
    dp.message.register(
        process_broadcast_text,
        lambda msg: msg.from_user.id in WAITING_FOR_BROADCAST_TEXT
    )

    # Хэндлер инлайн-кнопок «Да / Нет»
    dp.callback_query.register(confirm_broadcast_callback, ConfirmBroadcast.filter())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())