import asyncio
import os
from dataclasses import dataclass

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

TOKEN = os.getenv('BOT_TOKEN')
API_BASE_URL = os.getenv('API_BASE_URL', 'http://api:8000')
API_SECRET = os.getenv('API_SECRET', '')

if not TOKEN:
    raise RuntimeError('BOT_TOKEN is not set')


@dataclass
class ApiError(Exception):
    message: str


class AddListState(StatesGroup):
    waiting_name = State()
    waiting_entries = State()


class ManualConfigState(StatesGroup):
    waiting_ns = State()


class AddWordsState(StatesGroup):
    waiting_text = State()


class BotUI:
    def __init__(self):
        self.screen_messages: dict[int, int] = {}


ui = BotUI()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


def kb(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def api_request(method: str, path: str, payload: dict | None = None, params: dict | None = None):
    headers = {'X-BOT-TOKEN': API_SECRET}
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=20) as client:
        response = await client.request(method, path, json=payload, params=params, headers=headers)
    if response.status_code >= 400:
        detail = response.json().get('detail', response.text)
        raise ApiError(str(detail))
    return response.json()


async def get_active_game(chat_id: int):
    data = await api_request('GET', '/game/status', params={'chat_id': chat_id})
    return data.get('game')


def main_menu_kb(has_game: bool):
    rows = [
        [InlineKeyboardButton(text='Нова игра', callback_data='menu:new_game')],
        [InlineKeyboardButton(text='Списъци', callback_data='menu:lists')],
        [InlineKeyboardButton(text='Помощ', callback_data='menu:help')],
    ]
    if has_game:
        rows.extend(
            [
                [InlineKeyboardButton(text='Покажи', callback_data='game:reveal')],
                [InlineKeyboardButton(text='Скрий', callback_data='game:hide')],
                [InlineKeyboardButton(text='Следващ', callback_data='game:next')],
                [InlineKeyboardButton(text='Статус', callback_data='game:status')],
                [InlineKeyboardButton(text='Край', callback_data='game:end')],
            ]
        )
    return kb(rows)


def lists_menu_kb():
    return kb([
        [InlineKeyboardButton(text='Покажи списъци', callback_data='lists:show')],
        [InlineKeyboardButton(text='Добави списък', callback_data='lists:add')],
        [InlineKeyboardButton(text='Добави думи към списък', callback_data='lists:add_words')],
        [InlineKeyboardButton(text='Изтрий списък', callback_data='lists:delete')],
        [InlineKeyboardButton(text='Назад', callback_data='menu:home')],
    ])


def game_action_kb(game: dict):
    status = game['status']
    if status == 'ALL_SEEN':
        return kb([
            [InlineKeyboardButton(text='Статус', callback_data='game:status')],
            [InlineKeyboardButton(text='Край', callback_data='game:end')],
            [InlineKeyboardButton(text='Меню', callback_data='menu:home')],
        ])
    if game['is_revealed']:
        return kb([
            [InlineKeyboardButton(text='Скрий', callback_data='game:hide')],
            [InlineKeyboardButton(text='Край', callback_data='game:end')],
        ])
    if game.get('current_seen'):
        return kb([
            [InlineKeyboardButton(text='Следващ', callback_data='game:next')],
            [InlineKeyboardButton(text='Статус', callback_data='game:status')],
            [InlineKeyboardButton(text='Край', callback_data='game:end')],
        ])
    return kb([
        [InlineKeyboardButton(text='Покажи', callback_data='game:reveal')],
        [InlineKeyboardButton(text='Статус', callback_data='game:status')],
        [InlineKeyboardButton(text='Край', callback_data='game:end')],
    ])


async def render_screen(chat_id: int, text: str, keyboard: InlineKeyboardMarkup, message: Message | None = None):
    known_id = ui.screen_messages.get(chat_id)
    if message and known_id is None:
        known_id = message.message_id
        ui.screen_messages[chat_id] = known_id

    if known_id:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=known_id, text=text, reply_markup=keyboard)
            return
        except TelegramBadRequest:
            pass

    sent = await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)
    ui.screen_messages[chat_id] = sent.message_id


async def render_home(chat_id: int, message: Message | None = None):
    game = await get_active_game(chat_id)
    text = 'Spy Bot (one-phone)\nИзбери действие:'
    await render_screen(chat_id, text, main_menu_kb(bool(game)), message)


@dp.message(CommandStart())
async def start(message: Message):
    await render_home(message.chat.id, message)


@dp.callback_query(F.data == 'menu:home')
async def menu_home(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await render_home(callback.message.chat.id, callback.message)
    await callback.answer()


@dp.callback_query(F.data == 'menu:help')
async def menu_help(callback: CallbackQuery):
    text = (
        'Помощ:\n'
        '1) Създай списък със думи/фрази.\n'
        '2) Натисни „Нова игра“ и избери конфигурация.\n'
        '3) Всеки играч натиска „Покажи“ -> „Скрий“ -> „Следващ“.\n'
        '4) В края натисни „Край“ за резултат.'
    )
    await render_screen(callback.message.chat.id, text, kb([[InlineKeyboardButton(text='Назад', callback_data='menu:home')]]), callback.message)
    await callback.answer()


@dp.callback_query(F.data == 'menu:lists')
async def menu_lists(callback: CallbackQuery):
    await render_screen(callback.message.chat.id, 'Управление на списъци:', lists_menu_kb(), callback.message)
    await callback.answer()


@dp.callback_query(F.data == 'lists:show')
async def lists_show(callback: CallbackQuery):
    try:
        data = await api_request('GET', '/lists')
    except ApiError as err:
        await callback.answer(err.message, show_alert=True)
        return
    items = data['items']
    if not items:
        text = 'Няма списъци. Добави нов списък.'
    else:
        text = 'Списъци:\n' + '\n'.join([f"• {i['name']} ({i['entries_count']})" for i in items])
    await render_screen(callback.message.chat.id, text, lists_menu_kb(), callback.message)
    await callback.answer()


@dp.callback_query(F.data == 'lists:add')
async def lists_add(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddListState.waiting_name)
    await render_screen(callback.message.chat.id, 'Изпрати име на списъка.', kb([[InlineKeyboardButton(text='Отказ', callback_data='menu:home')]]), callback.message)
    await callback.answer()


@dp.message(AddListState.waiting_name)
async def add_list_name(message: Message, state: FSMContext):
    await state.update_data(list_name=message.text.strip())
    await state.set_state(AddListState.waiting_entries)
    await render_screen(message.chat.id, 'Сега изпрати думи/фрази (редове или запетаи).', kb([[InlineKeyboardButton(text='Отказ', callback_data='menu:home')]]))


@dp.message(AddListState.waiting_entries)
async def add_list_entries(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        created = await api_request('POST', '/lists', {'name': data['list_name']})
        stats = await api_request('POST', f"/lists/{created['id']}/entries/import", {'raw_text': message.text})
        text = f"Списъкът е създаден.\nНамерени: {stats['found']}, Добавени: {stats['added']}, Дубликати: {stats['duplicates']}"
    except ApiError as err:
        text = f'Грешка: {err.message}'
    await state.clear()
    await render_screen(message.chat.id, text, lists_menu_kb())


@dp.callback_query(F.data == 'lists:add_words')
async def lists_add_words(callback: CallbackQuery, state: FSMContext):
    data = await api_request('GET', '/lists')
    items = data['items']
    if not items:
        await render_screen(callback.message.chat.id, 'Няма списъци. Добави списък първо.', lists_menu_kb(), callback.message)
        await callback.answer()
        return
    buttons = [[InlineKeyboardButton(text=f"{i['name']} ({i['entries_count']})", callback_data=f"lists:add_words:{i['id']}")] for i in items]
    buttons.append([InlineKeyboardButton(text='Назад', callback_data='menu:lists')])
    await state.clear()
    await render_screen(callback.message.chat.id, 'Избери списък:', kb(buttons), callback.message)
    await callback.answer()


@dp.callback_query(F.data.startswith('lists:add_words:'))
async def lists_add_words_pick(callback: CallbackQuery, state: FSMContext):
    list_id = int(callback.data.split(':')[-1])
    await state.set_state(AddWordsState.waiting_text)
    await state.update_data(list_id=list_id)
    await render_screen(callback.message.chat.id, 'Изпрати думи/фрази за добавяне (редове или запетаи).', kb([[InlineKeyboardButton(text='Отказ', callback_data='menu:lists')]]), callback.message)
    await callback.answer()


@dp.message(AddWordsState.waiting_text)
async def lists_add_words_text(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        stats = await api_request('POST', f"/lists/{data['list_id']}/entries/import", {'raw_text': message.text})
        text = f"Готово. Намерени: {stats['found']}, Добавени: {stats['added']}, Дубликати: {stats['duplicates']}"
    except ApiError as err:
        text = f'Грешка: {err.message}'
    await state.clear()
    await render_screen(message.chat.id, text, lists_menu_kb())


@dp.callback_query(F.data == 'lists:delete')
async def lists_delete(callback: CallbackQuery):
    data = await api_request('GET', '/lists')
    items = data['items']
    if not items:
        await render_screen(callback.message.chat.id, 'Няма списъци за изтриване.', lists_menu_kb(), callback.message)
        await callback.answer()
        return
    buttons = [[InlineKeyboardButton(text=f"🗑 {i['name']}", callback_data=f"lists:del_confirm:{i['id']}")] for i in items]
    buttons.append([InlineKeyboardButton(text='Назад', callback_data='menu:lists')])
    await render_screen(callback.message.chat.id, 'Избери списък за изтриване:', kb(buttons), callback.message)
    await callback.answer()


@dp.callback_query(F.data.startswith('lists:del_confirm:'))
async def lists_delete_confirm(callback: CallbackQuery):
    list_id = int(callback.data.split(':')[-1])
    await render_screen(
        callback.message.chat.id,
        'Сигурни ли сте?',
        kb([
            [InlineKeyboardButton(text='Да, изтрий', callback_data=f'lists:del:{list_id}')],
            [InlineKeyboardButton(text='Отказ', callback_data='menu:lists')],
        ]),
        callback.message,
    )
    await callback.answer()


@dp.callback_query(F.data.startswith('lists:del:'))
async def lists_delete_done(callback: CallbackQuery):
    list_id = int(callback.data.split(':')[-1])
    try:
        await api_request('DELETE', f'/lists/{list_id}')
        text = 'Списъкът е изтрит.'
    except ApiError as err:
        text = f'Грешка: {err.message}'
    await render_screen(callback.message.chat.id, text, lists_menu_kb(), callback.message)
    await callback.answer()


@dp.callback_query(F.data == 'menu:new_game')
async def new_game(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    data = await api_request('GET', '/lists')
    items = [i for i in data['items'] if i['entries_count'] > 0]
    if not items:
        await render_screen(
            callback.message.chat.id,
            'Няма активни списъци със думи. Добави списък.',
            kb([
                [InlineKeyboardButton(text='Добави списък', callback_data='lists:add')],
                [InlineKeyboardButton(text='Назад', callback_data='menu:home')],
            ]),
            callback.message,
        )
        await callback.answer()
        return

    buttons = [[InlineKeyboardButton(text=f"{i['name']} ({i['entries_count']})", callback_data=f"new:list:{i['id']}")] for i in items]
    buttons.append([InlineKeyboardButton(text='Назад', callback_data='menu:home')])
    await render_screen(callback.message.chat.id, 'Избери списък:', kb(buttons), callback.message)
    await callback.answer()


@dp.callback_query(F.data.startswith('new:list:'))
async def new_game_list_pick(callback: CallbackQuery, state: FSMContext):
    list_id = int(callback.data.split(':')[-1])
    await state.update_data(list_id=list_id)
    presets = [(4, 1), (5, 1), (6, 1), (7, 2), (8, 2), (10, 2), (12, 3)]
    rows = [[InlineKeyboardButton(text=f'{n}/{s}', callback_data=f'new:cfg:{n}:{s}')] for n, s in presets]
    rows.append([InlineKeyboardButton(text='Ръчно', callback_data='new:manual')])
    rows.append([InlineKeyboardButton(text='Назад', callback_data='menu:new_game')])
    await render_screen(callback.message.chat.id, 'Избери играчи/шпиони:', kb(rows), callback.message)
    await callback.answer()


async def render_confirm(chat_id: int, state: FSMContext, message: Message | None = None):
    data = await state.get_data()
    lists_data = await api_request('GET', '/lists')
    list_name = next((i['name'] for i in lists_data['items'] if i['id'] == data['list_id']), f"#{data['list_id']}")
    text = f"Потвърди игра:\nСписък: {list_name}\nИграчИ: {data['players_count']}\nШпиони: {data['spies_count']}"
    await render_screen(
        chat_id,
        text,
        kb([
            [InlineKeyboardButton(text='Старт', callback_data='new:start')],
            [InlineKeyboardButton(text='Назад', callback_data='menu:new_game')],
        ]),
        message,
    )


@dp.callback_query(F.data.startswith('new:cfg:'))
async def new_game_cfg(callback: CallbackQuery, state: FSMContext):
    _, _, n, s = callback.data.split(':')
    await state.update_data(players_count=int(n), spies_count=int(s))
    await render_confirm(callback.message.chat.id, state, callback.message)
    await callback.answer()


@dp.callback_query(F.data == 'new:manual')
async def new_manual(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ManualConfigState.waiting_ns)
    await render_screen(callback.message.chat.id, 'Въведи формат: N S (пример: 5 1)', kb([[InlineKeyboardButton(text='Отказ', callback_data='menu:new_game')]]), callback.message)
    await callback.answer()


@dp.message(ManualConfigState.waiting_ns)
async def new_manual_text(message: Message, state: FSMContext):
    parts = message.text.split()
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        await message.answer('Формат: N S (пример: 5 1)')
        return
    n, s = int(parts[0]), int(parts[1])
    if s >= n or n < 3:
        await message.answer('Грешка: шпионите трябва да са по-малко от играчите.')
        return
    await state.update_data(players_count=n, spies_count=s)
    await state.set_state(None)
    await render_confirm(message.chat.id, state)


@dp.callback_query(F.data == 'new:start')
async def new_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    try:
        game = await api_request(
            'POST',
            '/game/start',
            {
                'chat_id': callback.message.chat.id,
                'list_id': data['list_id'],
                'players_count': data['players_count'],
                'spies_count': data['spies_count'],
            },
        )
    except ApiError as err:
        await callback.answer(err.message, show_alert=True)
        return
    await state.clear()
    await render_game_screen(callback.message.chat.id, game, callback.message)
    await callback.answer()


async def render_game_screen(chat_id: int, game: dict, message: Message | None = None, reveal_text: str | None = None):
    if game['status'] == 'ALL_SEEN':
        text = 'Всички видяха ролята си. Започнете обсъждане.'
    elif reveal_text:
        text = f"Играч {game['current_player']} от {game['players_count']}\n\n{reveal_text}"
    else:
        text = f"Играч {game['current_player']} от {game['players_count']}"
    await render_screen(chat_id, text, game_action_kb(game), message)


@dp.callback_query(F.data == 'game:status')
async def game_status(callback: CallbackQuery):
    try:
        game = await get_active_game(callback.message.chat.id)
    except ApiError as err:
        await callback.answer(err.message, show_alert=True)
        return
    if not game:
        await render_home(callback.message.chat.id, callback.message)
        await callback.answer()
        return
    marks = ' '.join([f"{p['player_index']}:{'✅' if p['seen'] else '⏳'}" for p in game['seen']])
    text = f"Статус: {game['seen_count']} / {game['players_count']}\n{marks}"
    await render_screen(callback.message.chat.id, text, game_action_kb(game), callback.message)
    await callback.answer()


async def call_game_action(callback: CallbackQuery, action: str):
    try:
        game = await api_request('POST', f'/game/{action}', {'chat_id': callback.message.chat.id})
    except ApiError as err:
        await callback.answer(err.message, show_alert=True)
        return
    reveal_text = game.get('reveal_text')
    await render_game_screen(callback.message.chat.id, game, callback.message, reveal_text=reveal_text)
    await callback.answer()


@dp.callback_query(F.data == 'game:reveal')
async def game_reveal(callback: CallbackQuery):
    await call_game_action(callback, 'reveal')


@dp.callback_query(F.data == 'game:hide')
async def game_hide(callback: CallbackQuery):
    await call_game_action(callback, 'hide')


@dp.callback_query(F.data == 'game:next')
async def game_next(callback: CallbackQuery):
    await call_game_action(callback, 'next')


@dp.callback_query(F.data == 'game:end')
async def game_end(callback: CallbackQuery):
    try:
        game = await api_request('POST', '/game/end', {'chat_id': callback.message.chat.id})
    except ApiError as err:
        await callback.answer(err.message, show_alert=True)
        return
    text = f"Играта приключи. Думата беше: {game['entry_text']}. Шпиони: {', '.join(map(str, game['spy_indices']))}"
    await render_screen(callback.message.chat.id, text, kb([[InlineKeyboardButton(text='Меню', callback_data='menu:home')]]), callback.message)
    await callback.answer()


@dp.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP, ChatType.PRIVATE}))
async def ignore_messages(_: Message):
    return


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
