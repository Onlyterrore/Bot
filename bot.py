import asyncio
import os
import json

from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode

from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardMarkup, KeyboardButton

API_TOKEN = "8189643318:AAEjvXhCyKd7uVsp9ZuGMpzKXtj7aqYaPKg"

# ===== Белый список пользователей (user_id) =====
ALLOWED_USERS = {
    324213868,  # ID пользователей с доступом
    155987540,
    58536654,
    110374107
}

# ==============================
#   ЧТЕНИЕ / ЗАПИСЬ JSON
# ==============================
def load_chat_ids() -> list:
    file_path = "chat_ids.json"
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "chat_ids" in data:
                return data["chat_ids"]
    except Exception as e:
        print(f"Ошибка при загрузке chat_ids.json: {e}")
    return []

def save_chat_ids(chat_list: list):
    data = {"chat_ids": chat_list}
    try:
        with open("chat_ids.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Ошибка при сохранении chat_ids.json: {e}")

# ==============================
#   ГЛОБАЛЬНЫЙ СПИСОК ГРУПП
# ==============================
CHAT_IDS = load_chat_ids()  # Загружаем при старте

WAITING_FOR_BROADCAST_TEXT = set()
WAITING_FOR_ADD_GROUP = set()
WAITING_FOR_REMOVE_GROUP = set()

BROADCAST_TEXTS = {}

class ConfirmBroadcast(CallbackData, prefix="confirm_broadcast"):
    decision: str  # "yes" / "no"

def get_main_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="Сделать рассылку")],
        [
            KeyboardButton(text="Добавить группу"),
            KeyboardButton(text="Удалить группу"),
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# ==============================
#   Хэндлер /start
# ==============================
async def cmd_start(message: Message):
    if message.from_user.id not in ALLOWED_USERS:
        await message.answer("У вас нет доступа к этому боту.")
        return
    
    await message.answer(
        text="Привет! Используйте кнопки для рассылки и управления группами.",
        reply_markup=get_main_menu()
    )

# ==============================
#   Сделать рассылку
# ==============================
async def handle_make_broadcast(message: Message):
    if message.from_user.id not in ALLOWED_USERS:
        await message.answer("У вас нет доступа к этому боту.")
        return

    WAITING_FOR_BROADCAST_TEXT.add(message.from_user.id)
    
    # Формируем список групп для вывода
    if not CHAT_IDS:
        group_list = "Список групп пуст."
    else:
        group_list = "Актуальный список групп:\n\n" + "\n".join(
            [f"{i+1}. {group['name']} (ID: {group['id']})" for i, group in enumerate(CHAT_IDS)]
        )
    
    await message.answer(f"{group_list}\n\nНапишите сообщение, которое хотите разослать во все группы.")

async def process_broadcast_text(message: Message):
    if message.from_user.id not in ALLOWED_USERS:
        await message.answer("У вас нет доступа к этому боту.")
        return

    if message.from_user.id not in WAITING_FOR_BROADCAST_TEXT:
        await message.answer("Вы не начали процесс рассылки. Нажмите 'Сделать рассылку', чтобы начать.")
        return

    WAITING_FOR_BROADCAST_TEXT.remove(message.from_user.id)
    BROADCAST_TEXTS[message.from_user.id] = message.html_text  # Используем html_text для сохранения ссылок

    kb = InlineKeyboardBuilder()
    kb.button(text="Да", callback_data=ConfirmBroadcast(decision="yes"))
    kb.button(text="Нет", callback_data=ConfirmBroadcast(decision="no"))
    kb.adjust(2)

    await message.answer(
        f"Вы хотите отправить это сообщение во все группы?\n\n{message.text}",
        reply_markup=kb.as_markup()
    )

async def confirm_broadcast_callback(call: CallbackQuery, callback_data: ConfirmBroadcast):
    if call.from_user.id not in ALLOWED_USERS:
        await call.message.answer("У вас нет доступа к этому боту.")
        await call.message.edit_reply_markup(None)
        await call.answer()
        return

    text_for_broadcast = BROADCAST_TEXTS.pop(call.from_user.id, None)
    if callback_data.decision == "yes" and text_for_broadcast:
        bot = call.bot
        success_count = 0

        # Отправляем сообщение с parse_mode="HTML" для сохранения ссылок
        for group in CHAT_IDS:
            try:
                await bot.send_message(
                    chat_id=group["id"],
                    text=text_for_broadcast,  # Используем текст с HTML-разметкой
                    parse_mode="HTML"  # Включаем HTML-разметку
                )
                success_count += 1
            except Exception as e:
                print(f"Ошибка при отправке в чат {group['id']}: {e}")

        await call.message.answer(f"Сообщение разослано в {success_count} чатов.")
    else:
        await call.message.answer("Рассылка отменена.")

    await call.message.edit_reply_markup(None)
    await call.answer()

# ==============================
#   Добавление группы
# ==============================
async def handle_add_group(message: Message):
    if message.from_user.id not in ALLOWED_USERS:
        await message.answer("У вас нет доступа к этому боту.")
        return

    WAITING_FOR_ADD_GROUP.add(message.from_user.id)
    await message.answer("Введите ID группы (chat_id).")

async def process_add_group(message: Message):
    if message.from_user.id not in ALLOWED_USERS:
        await message.answer("У вас нет доступа к этому боту.")
        return

    if message.from_user.id not in WAITING_FOR_ADD_GROUP:
        await message.answer("Вы не начали процесс добавления группы. Нажмите 'Добавить группу', чтобы начать.")
        return

    WAITING_FOR_ADD_GROUP.remove(message.from_user.id)

    try:
        chat_id = int(message.text)  # Преобразуем ID в число
    except ValueError:
        await message.answer("Некорректный формат. Введите числовой ID группы.")
        return

    # Проверяем, есть ли группа уже в списке
    if any(group["id"] == chat_id for group in CHAT_IDS):
        await message.answer("Группа с таким ID уже существует.")
        return

    # Получаем информацию о группе через API Telegram
    bot = message.bot
    try:
        chat_info = await bot.get_chat(chat_id)
        group_name = chat_info.title  # Получаем название группы
    except Exception as e:
        await message.answer(f"Не удалось получить информацию о группе. Убедитесь, что бот добавлен в группу и имеет доступ. Ошибка: {e}")
        return

    # Добавляем группу в список
    CHAT_IDS.append({"id": chat_id, "name": group_name})
    save_chat_ids(CHAT_IDS)  # Сохраняем в JSON

    await message.answer(f"Группа '{group_name}' (ID: {chat_id}) успешно добавлена.")

# ==============================
#   Удаление группы
# ==============================
async def handle_remove_group(message: Message):
    if message.from_user.id not in ALLOWED_USERS:
        await message.answer("У вас нет доступа к этому боту.")
        return

    if not CHAT_IDS:
        await message.answer("Список групп пуст.")
        return

    WAITING_FOR_REMOVE_GROUP.add(message.from_user.id)

    # Формируем список групп для вывода
    group_list = "Выберите группу для удаления:\n\n" + "\n".join(
        [f"{i+1}. {group['name']} (ID: {group['id']})" for i, group in enumerate(CHAT_IDS)]
    )

    await message.answer(group_list)

async def process_remove_group(message: Message):
    if message.from_user.id not in ALLOWED_USERS:
        await message.answer("У вас нет доступа к этому боту.")
        return

    if message.from_user.id not in WAITING_FOR_REMOVE_GROUP:
        await message.answer("Вы не начали процесс удаления группы. Нажмите 'Удалить группу', чтобы начать.")
        return

    WAITING_FOR_REMOVE_GROUP.remove(message.from_user.id)

    try:
        group_number = int(message.text)  # Номер группы для удаления
        if group_number < 1 or group_number > len(CHAT_IDS):
            await message.answer("Некорректный номер группы.")
            return
    except ValueError:
        await message.answer("Введите номер группы для удаления.")
        return

    # Удаляем группу из списка
    removed_group = CHAT_IDS.pop(group_number - 1)
    save_chat_ids(CHAT_IDS)  # Сохраняем в JSON

    await message.answer(f"Группа '{removed_group['name']}' (ID: {removed_group['id']}) успешно удалена.")

# ==============================
#   MAIN
# ==============================
async def main():
    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.message.register(cmd_start, lambda msg: msg.text == "/start")
    dp.message.register(handle_make_broadcast, lambda msg: msg.text == "Сделать рассылку")
    dp.message.register(process_broadcast_text, lambda msg: msg.from_user.id in WAITING_FOR_BROADCAST_TEXT)
    dp.message.register(handle_add_group, lambda msg: msg.text == "Добавить группу")
    dp.message.register(process_add_group, lambda msg: msg.from_user.id in WAITING_FOR_ADD_GROUP)
    dp.message.register(handle_remove_group, lambda msg: msg.text == "Удалить группу")
    dp.message.register(process_remove_group, lambda msg: msg.from_user.id in WAITING_FOR_REMOVE_GROUP)
    dp.callback_query.register(confirm_broadcast_callback, ConfirmBroadcast.filter())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())