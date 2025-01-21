import asyncio

from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode

# В актуальных версиях (например, aiogram 3.17+) CallbackData в таком модуле:
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

API_TOKEN = "8189643318:AAEjvXhCyKd7uVsp9ZuGMpzKXtj7aqYaPKg"

# Список чатов, куда бот будет рассылать:
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

# Создадим CallbackData для кнопок подтверждения
class ConfirmBroadcast(CallbackData, prefix="confirm_broadcast"):
    decision: str  # "yes" или "no"


def get_main_menu() -> ReplyKeyboardMarkup:
    """
    Возвращаем «Reply-клавиатуру» с кнопкой «Сделать рассылку».
    Можно добавить и другие кнопки в будущем.
    """
    keyboard = [
        [KeyboardButton(text="Сделать рассылку")],
        # Если нужны другие кнопки, добавьте новые строки/списки
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


async def cmd_start(message: Message):
    """
    Приветствие и показ основной меню-клавиатуры.
    """
    await message.answer(
        text="Нажмите «Сделать рассылку», после чего введите текст сообщения.",
        reply_markup=get_main_menu()  # прикрепляем нашу клавиатуру
    )


async def handle_make_broadcast(message: Message):
    """
    Когда пользователь нажимает кнопку «Сделать рассылку», в чат приходит текст "Сделать рассылку".
    Ловим это сообщение:
      1) Запоминаем user_id в WAITING_FOR_BROADCAST_TEXT
      2) Просим ввести текст для рассылки
    """
    WAITING_FOR_BROADCAST_TEXT.add(message.from_user.id)
    await message.answer("Напишите сообщение, которое хотите разослать всем.")


async def process_broadcast_text(message: Message):
    """
    Срабатывает, когда пользователь в WAITING_FOR_BROADCAST_TEXT.
    Запрашиваем подтверждение «Да / Нет» (Inline-кнопки).
    """
    user_id = message.from_user.id
    WAITING_FOR_BROADCAST_TEXT.remove(user_id)

    # Запоминаем текст (чтобы потом при «Да» разослать)
    BROADCAST_TEXTS[user_id] = message.text

    # Создаём inline-кнопки "Да" / "Нет"
    kb = InlineKeyboardBuilder()
    kb.button(text="Да", callback_data=ConfirmBroadcast(decision="yes"))
    kb.button(text="Нет", callback_data=ConfirmBroadcast(decision="no"))
    kb.adjust(2)

    # Спрашиваем подтверждение
    await message.answer(
        text=f"Вы точно хотите отправить это сообщение?\n\n{message.text}",
        reply_markup=kb.as_markup()
    )


async def confirm_broadcast_callback(call: CallbackQuery, callback_data: ConfirmBroadcast):
    """
    Срабатывает при нажатии Inline-кнопок «Да» / «Нет».
    Если «Да», рассылаем текст по CHAT_IDS. Если «Нет», отменяем.
    """
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
    # Ответ на колбэк — убирает «часики» в Telegram
    await call.answer()


async def main():
    # Инициализируем бота
    bot = Bot(
        token=API_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Хэндлер команды /start
    dp.message.register(cmd_start, lambda msg: msg.text == "/start")

    # Хэндлер нажатия кнопки «Сделать рассылку» (т.е. приходит текст "Сделать рассылку")
    dp.message.register(handle_make_broadcast, lambda msg: msg.text == "Сделать рассылку")

    # Хэндлер ввода текста для рассылки, если user_id в WAITING_FOR_BROADCAST_TEXT
    dp.message.register(
        process_broadcast_text,
        lambda msg: msg.from_user.id in WAITING_FOR_BROADCAST_TEXT
    )

    # Хэндлер inline-кнопок «Да / Нет»
    dp.callback_query.register(confirm_broadcast_callback, ConfirmBroadcast.filter())

    # Запускаем лонг-поллинг
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
