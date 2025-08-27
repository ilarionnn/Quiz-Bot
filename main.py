import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.filters.command import Command

from question import quiz_data
from config import API_TOKEN, DB_NAME
from database import get_quiz_index, get_user_score, update_quiz_index, update_user_score, create_table, get_all_users_scores

# Объект бота
bot = Bot(token=API_TOKEN)
# Диспетчер
dp = Dispatcher()

def generate_options_keyboard(answer_options, right_answer_index):
    builder = InlineKeyboardBuilder()

    for i, option in enumerate(answer_options):
        # Создаем callback_data с индексом варианта
        callback_data = f"answer_{i}"
        builder.add(types.InlineKeyboardButton(
            text=option,
            callback_data=callback_data)
        )

    builder.adjust(1)
    return builder.as_markup()

@dp.callback_query(F.data.startswith("answer_"))
async def handle_answer(callback: types.CallbackQuery):
    # Получаем индекс выбранного ответа
    selected_index = int(callback.data.split("_")[1])
    
    # Получаем текущий вопрос
    current_question_index = await get_quiz_index(callback.from_user.id)
    current_question = quiz_data[current_question_index]
    
    # Получаем текст выбранного ответа
    selected_answer = current_question['options'][selected_index]
    
    # Удаляем кнопки
    await callback.bot.edit_message_reply_markup(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        reply_markup=None
    )

    # Отправляем ответ пользователя в чат
    await callback.message.answer(f"Ваш ответ: {selected_answer}")
    
    # Проверяем правильность ответа
    if selected_index == current_question['correct_option']:
        await callback.message.answer("✅ Верно!")
        current_score = await get_user_score(callback.from_user.id)
        current_score += 1
        await update_user_score(callback.from_user.id, current_score)
    else:
        correct_answer = current_question['options'][current_question['correct_option']]
        await callback.message.answer(f"❌ Неправильно. Правильный ответ: {correct_answer}")
    
    # Переходим к следующему вопросу
    current_question_index += 1
    await update_quiz_index(callback.from_user.id, current_question_index)
    
    current_score = await get_user_score(callback.from_user.id)
    
    if current_question_index < len(quiz_data):
        await get_question(callback.message, callback.from_user.id)
    else:
        await callback.message.answer(f"Это был последний вопрос. Квиз завершен! \nВаш результат: {current_score} правильных ответов.")



async def cmd_stats(message: types.Message):
    #Показать статистику всех пользователей
    all_stats = await get_all_users_scores()
    
    if not all_stats:
        await message.answer("📊 Пока никто не играл в квиз!")
        return
    
    stats_text = "Статистика игроков:\n\n"
    
    for i, (user_id, score) in enumerate(all_stats, 1):
        stats_text += f"{i}. ID {user_id} - {score} правильных ответов\n"
        
        # Ограничиваем вывод чтобы не получить огромный список
        if i >= 10:
            stats_text += "\n... и другие"
            break
    
    await message.answer(stats_text)

# Хэндлер на команду /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="Начать игру"))
    builder.add(types.KeyboardButton(text="Статистика"))
    builder.adjust(2)
    
    await message.answer(
        "Добро пожаловать в квиз!\n\n"
        "Доступные команды:\n"
        "/quiz - Начать квиз\n"
        "/stats - Статистика игроков\n"
        "/help - Помощь",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

dp.message.register(cmd_stats, Command("stats"))
dp.message.register(cmd_stats, F.text == "Статистика")

async def get_question(message, user_id):
    # Получение текущего вопроса из словаря состояний пользователя
    current_question_index = await get_quiz_index(user_id)
    correct_index = quiz_data[current_question_index]['correct_option']
    opts = quiz_data[current_question_index]['options']
    kb = generate_options_keyboard(opts, opts[correct_index])
    await message.answer(f"{quiz_data[current_question_index]['question']}", reply_markup=kb)


async def new_quiz(message):
    user_id = message.from_user.id
    current_question_index = 0
    new_score=0
    await update_quiz_index(user_id, current_question_index)
    await update_user_score(user_id, new_score)
    await get_question(message, user_id)

# Хэндлер на команду /quiz
@dp.message(F.text=="Начать игру")
@dp.message(Command("quiz"))
async def cmd_quiz(message: types.Message):

    await message.answer(f"Давайте начнем квиз!")
    await new_quiz(message)

# Хэндлер на команду /help
@dp.message(Command("help"))
async def cmd_start(message: types.Message):
    await message.answer("Команды бота:\n/start - начать взаимодействие с ботом\n/help - открыть помощь\n/quiz - начать игру")

async def delete_webhook():
    ###!!!Удаляет активный вебхук
    bot = Bot(token=API_TOKEN)
    await bot.delete_webhook()
    await bot.session.close()

# Запуск процесса поллинга новых апдейтов
async def main():
    await delete_webhook()
    # Запускаем создание таблицы базы данных
    await create_table()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())