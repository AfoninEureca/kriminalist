"""
CyberSherlock404bot — бот учебной игры «Центр „Контур“».

Что умеет:
  • открывает игру как мини-приложение Telegram (кнопка «🎮 Играть» под полем ввода);
  • принимает протоколы сыгранных сцен и начисляет баллы за звёзды;
  • принимает истории игроков для разбора, отправляет их модераторам;
  • начисляет баллы: +10 — история признана правдоподобной, +30 — по ней создан сценарий;
  • рейтинг, личный счёт, карточки сцен в PDF.

Настройки — в файле .env (см. .env.example). Токен бота в коде не хранится.
"""
import asyncio
import html
import json
import logging
import os
import re
import sqlite3
import time
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (BotCommand, CallbackQuery, FSInputFile, KeyboardButton, Message,
                           ReplyKeyboardMarkup, WebAppInfo)
from aiogram.utils.keyboard import InlineKeyboardBuilder

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name('.env'))
except ImportError:  # python-dotenv не обязателен, можно задать переменные окружения
    pass

BOT_TOKEN = os.getenv('BOT_TOKEN', '')
WEBAPP_URL = os.getenv('WEBAPP_URL', '').rstrip('/')
MOD_CHAT_ID = int(os.getenv('MOD_CHAT_ID', '0') or 0)
ADMIN_IDS = {int(x) for x in re.split(r'[,\s]+', os.getenv('ADMIN_IDS', '')) if x.strip().lstrip('-').isdigit()}
DB_PATH = os.getenv('DB_PATH', str(Path(__file__).with_name('kontur.db')))
CARDS_DIR = Path(__file__).with_name('cards')

PTS_PLAUSIBLE = 10      # история признана правдоподобной
PTS_SCENARIO = 30       # по истории создан сценарий
STORIES_PER_DAY = 3     # защита от потока сообщений
RANKS = [(0, 'Стажёр центра'), (10, 'Младший сыщик'), (30, 'Сыщик'), (60, 'Старший сыщик'), (120, 'Эксперт центра')]

SCENES = {
    2: 'Ноутбук без владельца', 3: 'Обновление, которое открыло дверь', 4: 'Телефон сотрудника',
    5: 'Гостевая сеть', 6: 'Двойник приложения', 7: 'Склеенные следы', 8: 'Свой среди своих',
    9: 'Срочный платёж', 10: 'Голос директора', 11: 'Поставщик поставщика',
    12: 'Помощник, который слушает чужих', 13: 'Двойное вымогательство', 14: 'Подброшенные улики',
    15: 'Данные клиента', 16: 'Последний счёт', 17: 'Покупатель',
    18: 'Тихий пакет', 19: 'Камера во дворе', 20: 'Машина без ключа', 21: 'Сорок уведомлений',
    22: 'Чужой ноутбук', 23: 'Идеальный кандидат', 24: 'Обмен',
    25: 'Письмо без ошибок', 26: 'Голос и лицо', 27: 'Помощник с ключами', 28: 'Чужая модель',
    29: 'Придуманный пакет', 30: 'Вставили в чат', 31: 'Бот обещал', 32: 'Человек в контуре',
    33: 'Помощь с возвратом', 34: 'Звонок в поддержку', 35: 'Терпеливый помощник', 36: 'Обновление для всех сразу',
    37: 'Ключ в сборке', 38: 'Резервная копия рядом', 39: 'Записано впрок', 40: 'Отравленный разбор',
    # Сезоны 6–10: штаб «Меридиан»
    41: 'Общая учётная запись',    42: 'Терминал без хозяина',    43: 'Регламент как щит',    44: 'Клиент всегда прав',
        45: 'Релиз по пятницам',    46: 'Схема, которой нет',    47: 'Слишком много «нет»',    48: 'Совет, которому поверили',
        49: 'Подрядчик с ключами',    50: 'Облако по умолчанию',    51: 'Обновление от поставщика',    52: 'Бухгалтерия на аутсорсе',
        53: 'Друг партнёра',    54: 'Договор, который никто не читал',    55: 'Один на всех',    56: 'Кто ещё держит ключи',
        57: 'Первый час',    58: 'Что мы знаем, а что нет',    59: 'Письмо клиентам',    60: 'Регулятор',
        61: 'Страховка',    62: 'Журналист звонит',    63: 'Сотрудник в центре внимания',    64: 'Публичный разбор',
        65: 'Голос директора',    66: 'Видеозвонок',    67: 'Помощник, который всё знает',    68: 'Вставили в чат',
        69: 'Подсказка из документа',    70: 'Умный отчёт',    71: 'Фото накладной',    72: 'Совет от машины',
        73: 'Первый день',    74: 'Последний день',    75: 'Школа',    76: 'Поликлиника',
        77: 'Семейная лавка',    78: 'Учения',    79: 'Садовник',    80: 'Передать ключи',
}
KINDS = {'me': 'Случилось со мной', 'org': 'Случилось в организации', 'news': 'Новость или публикация'}
STATUS = {'new': 'на проверке', 'clarify': 'нужно уточнение', 'plausible': 'правдоподобна',
          'scenario': 'по ней создан сценарий', 'rejected': 'не подошла'}

log = logging.getLogger('kontur')
router = Router()


# ───────────────────────── база данных ─────────────────────────
def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with db() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, username TEXT, created INTEGER);
        CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, scene INTEGER,
            win INTEGER, stars INTEGER, protocol TEXT, ts INTEGER);
        CREATE TABLE IF NOT EXISTS stories (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, kind TEXT,
            title TEXT, body TEXT, vuln TEXT, source TEXT, files TEXT, status TEXT DEFAULT 'new',
            scene INTEGER, mod_id INTEGER, mod_note TEXT, created INTEGER, updated INTEGER);
        CREATE TABLE IF NOT EXISTS points (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER,
            reason TEXT, ref TEXT, ts INTEGER);
        ''')


def touch_user(u) -> None:
    with db() as con:
        con.execute('INSERT INTO users(id, name, username, created) VALUES(?,?,?,?) '
                    'ON CONFLICT(id) DO UPDATE SET name=excluded.name, username=excluded.username',
                    (u.id, u.first_name or 'Игрок', u.username, int(time.time())))


def add_points(uid: int, amount: int, reason: str, ref: str = '') -> None:
    with db() as con:
        con.execute('INSERT INTO points(user_id, amount, reason, ref, ts) VALUES(?,?,?,?,?)',
                    (uid, amount, reason, ref, int(time.time())))


def total(uid: int) -> int:
    with db() as con:
        return con.execute('SELECT COALESCE(SUM(amount),0) FROM points WHERE user_id=?', (uid,)).fetchone()[0]


def rank(p: int) -> str:
    return [n for lim, n in RANKS if p >= lim][-1]


def next_rank(p: int) -> str:
    for lim, n in RANKS:
        if lim > p:
            return f'До звания «{n}» — {lim - p} б.'
    return 'Высшее звание центра.'


def get_story(sid: int):
    with db() as con:
        return con.execute('SELECT * FROM stories WHERE id=?', (sid,)).fetchone()


# ───────────────────────── проверка на личные данные ─────────────────────────
SENSITIVE = [
    (re.compile(r'(?:\d[ -]?){13,19}'), 'номер карты или счёта'),
    (re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+'), 'адрес почты'),
    (re.compile(r'(?:\+7|\b8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}'), 'номер телефона'),
    (re.compile(r'(?i)(пароль|password|pin|пин-?код)\s*[:=]\s*\S+'), 'пароль или код'),
]


def find_sensitive(text: str) -> list:
    return [name for rx, name in SENSITIVE if rx.search(text or '')]


# Рабочее содержимое атак в историях не принимаем: код, команды, дампы, пошаговые инструкции.
OPERATIONAL = [
    (re.compile(r'```|~~~'), 'блок кода'),
    (re.compile(r'(?im)^\s*(?:\$|#|>)\s*\S+.*$'), 'строка команды'),
    (re.compile(r'(?i)\b(?:curl|wget|powershell|cmd\.exe|bash\s+-c|nc\s+-e|chmod|sudo|nmap|sqlmap|msfconsole|mimikatz|hashcat|metasploit)\b'), 'команда или инструмент атаки'),
    (re.compile(r'(?i)\b(?:0x[0-9a-f]{2}[\s,]+){6,}|\b(?:[0-9a-f]{2}[\s:]){12,}'), 'шестнадцатеричный дамп'),
    (re.compile(r'(?i)(?:шаг|step)\s*\d+\s*[:.)-].{0,80}(?:обойти|взломать|подобрать|внедрить|эксплуат|bypass|inject)'), 'пошаговая инструкция атаки'),
    (re.compile(r'(?i)\b(?:CVE-\d{4}-\d{4,7})\b.{0,60}(?:эксплойт|exploit|poc|proof of concept)'), 'рабочий эксплойт'),
]


def find_operational(text: str) -> list:
    return [name for rx, name in OPERATIONAL if rx.search(text or '')]


# ───────────────────────── клавиатуры ─────────────────────────
def main_kb() -> ReplyKeyboardMarkup:
    first = [KeyboardButton(text='🎮 Играть', web_app=WebAppInfo(url=WEBAPP_URL + '/index.html'))] if WEBAPP_URL \
        else [KeyboardButton(text='📚 Сцены')]
    return ReplyKeyboardMarkup(resize_keyboard=True, is_persistent=True, keyboard=[
        first,
        [KeyboardButton(text='✍️ Прислать историю'), KeyboardButton(text='🏆 Мои баллы')],
        [KeyboardButton(text='📄 Карточки'), KeyboardButton(text='❓ Правила')],
    ])


def mod_kb(sid: int, status: str):
    b = InlineKeyboardBuilder()
    if status in ('new', 'clarify'):
        b.button(text=f'✅ Правдоподобно +{PTS_PLAUSIBLE}', callback_data=f'mod:ok:{sid}')
    if status in ('new', 'clarify', 'plausible'):
        b.button(text=f'🎬 Создан сценарий +{PTS_SCENARIO}', callback_data=f'mod:scn:{sid}')
    if status in ('new', 'clarify'):
        b.button(text='❓ Уточнить', callback_data=f'mod:ask:{sid}')
        b.button(text='❌ Отклонить', callback_data=f'mod:no:{sid}')
    b.adjust(1)
    return b.as_markup()


# ───────────────────────── состояния ─────────────────────────
class Story(StatesGroup):
    kind = State()
    title = State()
    body = State()
    vuln = State()
    source = State()
    confirm = State()


class Clarify(StatesGroup):
    question = State()   # модератор пишет вопрос
    answer = State()     # автор отвечает


RULES_TEXT = (
    '<b>Как устроен центр «Контур»</b>\n\n'
    '🎮 <b>Игра.</b> Нажмите «🎮 Играть» под полем ввода, выберите сцену, запустите таймер. '
    'Когда дело закрыто, нажмите внизу «Сдать протокол в бот». Баллы за игру — по лучшему результату '
    'каждой сцены: 1 звезда = 1 балл.\n\n'
    '✍️ <b>Ваша история.</b> Расскажите случай, который видели сами, в своей организации или в новостях: '
    'что произошло, какие устройства, как заметили. Модератор проверит её.\n'
    f'• правдоподобная история — <b>+{PTS_PLAUSIBLE}</b> б.;\n'
    f'• по истории создан новый сценарий — ещё <b>+{PTS_SCENARIO}</b> б.\n'
    f'Не больше {STORIES_PER_DAY} историй в день.\n\n'
    '🔒 <b>Без личных данных.</b> Не пишите имена, телефоны, почту, пароли, номера карт и адреса. '
    'Названия компаний меняйте на «банк», «магазин», «завод». Истории используются обезличенно и только '
    'для учебных сценариев. Мы не публикуем способы атак — только как их заметить и как защититься. '
    'Не присылайте код, команды, дампы и пошаговые инструкции: бот такие тексты не примет, а модератор отклонит.\n\n'
    '🏅 <b>Звания:</b> ' + ' → '.join(f'{n} ({lim})' for lim, n in RANKS)
)


# ───────────────────────── общие команды ─────────────────────────
@router.message(CommandStart())
async def start(m: Message, state: FSMContext):
    await state.clear()
    touch_user(m.from_user)
    await m.answer(
        f'Здравствуйте, {html.escape(m.from_user.first_name or "коллега")}! Это центр «Контур» — '
        'учебная игра про цифровую криминалистику.\n\n'
        '🎮 Играйте сцены (сезоны 1–5) и эпизоды штаба «Меридиан» (сезоны 6–10) и сдавайте протоколы.\n✍️ Присылайте свои истории для разбора — за них начисляются баллы.\n\n'
        'Подробности — «❓ Правила».', reply_markup=main_kb())


@router.message(Command('help'))
@router.message(Command('rules'))
@router.message(F.text == '❓ Правила')
async def rules(m: Message):
    await m.answer(RULES_TEXT, reply_markup=main_kb())


@router.message(Command('cancel'))
async def cancel(m: Message, state: FSMContext):
    await state.clear()
    await m.answer('Отменено.', reply_markup=main_kb())


@router.message(Command('scenes'))
@router.message(F.text == '📚 Сцены')
async def scenes(m: Message):
    lines = ['<b>Сезон 1</b>'] + [f'{n}. {t}' for n, t in SCENES.items() if n <= 8] + \
            ['', '<b>Сезон 2</b>'] + [f'{n}. {t}' for n, t in SCENES.items() if 9 <= n <= 16] + \
            ['', '<b>Сезон 3</b>'] + [f'{n}. {t}' for n, t in SCENES.items() if 17 <= n <= 24] + \
            ['', '<b>Сезон 4</b>'] + [f'{n}. {t}' for n, t in SCENES.items() if 25 <= n <= 32] + \
            ['', '<b>Сезон 5</b>'] + [f'{n}. {t}' for n, t in SCENES.items() if 33 <= n <= 40] + \
            ['', '<b>Сезон 6</b>'] + [f'{n}. {t}' for n, t in SCENES.items() if 41 <= n <= 48] + \
            ['', '<b>Сезон 7</b>'] + [f'{n}. {t}' for n, t in SCENES.items() if 49 <= n <= 56] + \
            ['', '<b>Сезон 8</b>'] + [f'{n}. {t}' for n, t in SCENES.items() if 57 <= n <= 64] + \
            ['', '<b>Сезон 9</b>'] + [f'{n}. {t}' for n, t in SCENES.items() if 65 <= n <= 72] + \
            ['', '<b>Сезон 10</b>'] + [f'{n}. {t}' for n, t in SCENES.items() if 73 <= n <= 80]
    tail = '\n\nОткройте игру кнопкой «🎮 Играть» под полем ввода.' if WEBAPP_URL else \
        '\n\nИгра ещё не подключена: администратор должен указать WEBAPP_URL.'
    await m.answer('\n'.join(lines) + tail)


# ───────────────────────── протоколы из мини-приложения ─────────────────────────
@router.message(F.web_app_data)
async def web_app_data(m: Message):
    touch_user(m.from_user)
    try:
        d = json.loads(m.web_app_data.data)
        scene, win, stars = int(d.get('s', 0)), int(bool(d.get('w'))), max(0, min(3, int(d.get('st', 0))))
        prot = str(d.get('p', ''))[:3500]
    except (ValueError, TypeError):
        await m.answer('Не удалось прочитать протокол. Попробуйте ещё раз.')
        return
    if scene not in SCENES:
        await m.answer('Неизвестная сцена.')
        return
    uid = m.from_user.id
    with db() as con:
        best = con.execute('SELECT COALESCE(MAX(stars),0) FROM runs WHERE user_id=? AND scene=?', (uid, scene)).fetchone()[0]
        con.execute('INSERT INTO runs(user_id, scene, win, stars, protocol, ts) VALUES(?,?,?,?,?,?)',
                    (uid, scene, win, stars, prot, int(time.time())))
    gain = max(0, stars - best)
    if gain:
        add_points(uid, gain, f'Сцена {scene}: лучший результат {stars}★', f'scene:{scene}')
    head = f'Сцена {scene} «{SCENES[scene]}»: ' + (f'закрыто, {"★" * stars}{"☆" * (3 - stars)}' if win else 'дело не закрыто')
    more = f'\nНовый рекорд по сцене: +{gain} б.' if gain else ('\nРекорд по сцене не побит.' if win else '\nПопробуйте ещё раз: протокол сохранён.')
    await m.answer(f'{head}{more}\nВсего баллов: <b>{total(uid)}</b>.', reply_markup=main_kb())


# ───────────────────────── баллы и рейтинг ─────────────────────────
@router.message(Command('points'))
@router.message(F.text == '🏆 Мои баллы')
async def my_points(m: Message):
    touch_user(m.from_user)
    uid = m.from_user.id
    p = total(uid)
    with db() as con:
        runs = con.execute('SELECT scene, MAX(stars) s FROM runs WHERE user_id=? GROUP BY scene ORDER BY scene', (uid,)).fetchall()
        st = con.execute('SELECT status, COUNT(*) c FROM stories WHERE user_id=? GROUP BY status', (uid,)).fetchall()
        hist = con.execute('SELECT amount, reason FROM points WHERE user_id=? ORDER BY id DESC LIMIT 5', (uid,)).fetchall()
    sc = ', '.join(f'{r["scene"]}: {"★" * r["s"] or "—"}' for r in runs) or 'пока нет'
    ss = ', '.join(f'{STATUS.get(r["status"], r["status"])}: {r["c"]}' for r in st) or 'пока нет'
    hh = '\n'.join(f'  +{r["amount"]} — {html.escape(r["reason"])}' for r in hist) or '  пока нет'
    await m.answer(f'🏆 <b>{p} б.</b> · {rank(p)}\n{next_rank(p)}\n\n<b>Сцены:</b> {sc}\n<b>Истории:</b> {ss}\n'
                   f'<b>Последние начисления:</b>\n{hh}\n\nРейтинг — /top, мои истории — /mystories.')


@router.message(Command('top'))
async def top(m: Message):
    with db() as con:
        rows = con.execute('SELECT u.name, SUM(p.amount) t FROM points p JOIN users u ON u.id=p.user_id '
                           'GROUP BY p.user_id ORDER BY t DESC LIMIT 10').fetchall()
    if not rows:
        await m.answer('Рейтинг пока пуст. Сыграйте сцену или пришлите историю.')
        return
    medal = ['🥇', '🥈', '🥉']
    await m.answer('<b>Рейтинг центра «Контур»</b>\n' + '\n'.join(
        f'{medal[i] if i < 3 else str(i + 1) + "."} {html.escape(r["name"] or "Игрок")} — {r["t"]} б. · {rank(r["t"])}'
        for i, r in enumerate(rows)))


@router.message(Command('mystories'))
async def my_stories(m: Message):
    with db() as con:
        rows = con.execute('SELECT id, title, status FROM stories WHERE user_id=? ORDER BY id DESC LIMIT 15',
                           (m.from_user.id,)).fetchall()
    if not rows:
        await m.answer('Историй пока нет. Нажмите «✍️ Прислать историю».')
        return
    await m.answer('<b>Мои истории</b>\n' + '\n'.join(
        f'№{r["id"]} «{html.escape(r["title"])}» — {STATUS.get(r["status"], r["status"])}' for r in rows))


# ───────────────────────── карточки ─────────────────────────
def card_files() -> list:
    return sorted(CARDS_DIR.glob('*.pdf'), key=lambda p: [int(x) for x in re.findall(r'\d+', p.stem)] or [0])


@router.message(Command('cards'))
@router.message(F.text == '📄 Карточки')
async def cards(m: Message):
    files = card_files()
    if not files:
        await m.answer('Карточек пока нет.')
        return
    b = InlineKeyboardBuilder()
    for i, f in enumerate(files):
        nums = re.findall(r'\d+', f.stem)
        b.button(text='Сцены ' + '–'.join(nums) if len(nums) > 1 else f'Сцена {nums[0]}' if nums else f.stem,
                 callback_data=f'card:{i}')
    b.adjust(3)
    await m.answer('Карточки для печати. Печатайте с двусторонней печатью по длинному краю.', reply_markup=b.as_markup())


@router.callback_query(F.data.startswith('card:'))
async def send_card(c: CallbackQuery):
    files = card_files()
    i = int(c.data.split(':')[1])
    if 0 <= i < len(files):
        await c.message.answer_document(FSInputFile(files[i]))
    await c.answer()


# ───────────────────────── приём истории ─────────────────────────
@router.message(Command('story'))
@router.message(F.text == '✍️ Прислать историю')
async def story_start(m: Message, state: FSMContext):
    touch_user(m.from_user)
    with db() as con:
        n = con.execute('SELECT COUNT(*) FROM stories WHERE user_id=? AND created>?',
                        (m.from_user.id, int(time.time()) - 86400)).fetchone()[0]
    if n >= STORIES_PER_DAY:
        await m.answer(f'Сегодня уже отправлено {n} истории. Продолжим завтра — так модераторы успеют прочитать каждую.')
        return
    await state.clear()
    await state.set_state(Story.kind)
    b = InlineKeyboardBuilder()
    for k, t in KINDS.items():
        b.button(text=t, callback_data=f'kind:{k}')
    b.adjust(1)
    await m.answer('✍️ <b>История для разбора</b> — шаг 1 из 5.\nОткуда история?\n\n'
                   '🔒 Без имён, телефонов, почты, паролей, номеров карт и адресов. Отменить — /cancel.',
                   reply_markup=b.as_markup())


@router.callback_query(Story.kind, F.data.startswith('kind:'))
async def story_kind(c: CallbackQuery, state: FSMContext):
    k = c.data.split(':')[1]
    if k not in KINDS:
        await c.answer()
        return
    await state.update_data(kind=k)
    await state.set_state(Story.title)
    await c.message.edit_text(f'Шаг 1 из 5: {KINDS[k]} ✓')
    await c.message.answer('Шаг 2 из 5. Назовите историю коротко, до 80 знаков.\nНапример: «Письмо от бухгалтерии с новым счётом».')
    await c.answer()


async def guard(m: Message) -> bool:
    """True, если в тексте есть личные данные и шаг нужно повторить."""
    found = find_sensitive(m.text or '')
    if found:
        await m.answer('🔒 Похоже, в тексте есть: ' + ', '.join(found) +
                       '. Замените это словами («номер карты», «телефон бухгалтера») и пришлите шаг заново.')
        return True
    ops = find_operational(m.text or '')
    if ops:
        await m.answer('🛡 В тексте есть: ' + ', '.join(ops) + '. Мы не публикуем способы атак и не принимаем код, '
                       'команды и пошаговые действия. Опишите словами, что вы заметили и как защититься, '
                       'и пришлите шаг заново.')
        return True
    return False


@router.message(Story.title, F.text)
async def story_title(m: Message, state: FSMContext):
    if await guard(m):
        return
    t = m.text.strip()
    if not 5 <= len(t) <= 80:
        await m.answer('Название — от 5 до 80 знаков.')
        return
    await state.update_data(title=t)
    await state.set_state(Story.body)
    await m.answer('Шаг 3 из 5. Что произошло?\n• какие устройства и сервисы участвовали;\n• что заметили первым и когда;\n'
                   '• что сделали и чем кончилось.\nОт 150 до 3000 знаков.')


@router.message(Story.body, F.text)
async def story_body(m: Message, state: FSMContext):
    if await guard(m):
        return
    t = m.text.strip()
    if len(t) < 150:
        await m.answer(f'Пока {len(t)} знаков. Добавьте подробностей: устройства, порядок событий, как заметили.')
        return
    await state.update_data(body=t[:3000])
    await state.set_state(Story.vuln)
    await m.answer('Шаг 4 из 5. Какое слабое место или приём здесь, по-вашему? Можно ответить «не знаю».')


@router.message(Story.vuln, F.text)
async def story_vuln(m: Message, state: FSMContext):
    if await guard(m):
        return
    await state.update_data(vuln=m.text.strip()[:500], source='', files=[])
    await state.set_state(Story.source)
    b = InlineKeyboardBuilder()
    b.button(text='Готово, к проверке', callback_data='src:done')
    await m.answer('Шаг 5 из 5. Пришлите ссылку на источник, скриншот или документ (до 5 файлов). '
                   'Закройте на скриншотах имена и номера. Если нечего прислать — нажмите «Готово».',
                   reply_markup=b.as_markup())


@router.message(Story.source)
async def story_source(m: Message, state: FSMContext):
    d = await state.get_data()
    files = d.get('files', [])
    if m.photo or m.document:
        if len(files) >= 5:
            await m.answer('Уже 5 файлов. Нажмите «Готово».')
            return
        files.append(['photo', m.photo[-1].file_id] if m.photo else ['doc', m.document.file_id])
        await state.update_data(files=files)
        await m.answer(f'Файл добавлен ({len(files)} из 5). Можно прислать ещё или нажать «Готово».')
    elif m.text:
        if await guard(m):
            return
        await state.update_data(source=(d.get('source', '') + '\n' + m.text.strip())[:800].strip())
        await m.answer('Источник добавлен. Можно прислать ещё или нажать «Готово».')


@router.callback_query(Story.source, F.data == 'src:done')
async def story_preview(c: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    await state.set_state(Story.confirm)
    b = InlineKeyboardBuilder()
    b.button(text='📨 Отправить на проверку', callback_data='st:send')
    b.button(text='Отменить', callback_data='st:cancel')
    b.adjust(1)
    await c.message.answer(
        f'<b>Проверьте историю</b>\n\n<b>{html.escape(d["title"])}</b> · {KINDS[d["kind"]]}\n\n{html.escape(d["body"])}\n\n'
        f'<b>Слабое место:</b> {html.escape(d["vuln"])}\n<b>Источник:</b> {html.escape(d.get("source") or "—")}\n'
        f'<b>Файлов:</b> {len(d.get("files", []))}\n\n'
        'Отправляя, вы подтверждаете: в истории нет личных данных и паролей; центр может использовать её '
        'обезличенно для учебных сценариев.', reply_markup=b.as_markup())
    await c.answer()


@router.callback_query(Story.confirm, F.data == 'st:cancel')
async def story_cancel(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.edit_text('История не отправлена.')
    await c.answer()


def mod_text(s) -> str:
    with db() as con:
        u = con.execute('SELECT name, username FROM users WHERE id=?', (s['user_id'],)).fetchone()
    who = (html.escape(u['name']) + (f' @{u["username"]}' if u and u['username'] else '')) if u else str(s['user_id'])
    return (f'📥 <b>История №{s["id"]}</b> · {STATUS[s["status"]]}\nОт: {who} (id {s["user_id"]}) · {KINDS.get(s["kind"], "")}\n\n'
            f'<b>{html.escape(s["title"])}</b>\n{html.escape(s["body"])}\n\n<b>Слабое место:</b> {html.escape(s["vuln"] or "—")}\n'
            f'<b>Источник:</b> {html.escape(s["source"] or "—")}'
            + (f'\n<b>Заметка модератора:</b> {html.escape(s["mod_note"])}' if s['mod_note'] else ''))[:4000]


async def send_to_mods(bot: Bot, s) -> None:
    if not MOD_CHAT_ID:
        log.warning('MOD_CHAT_ID не задан: история №%s ждёт в /queue', s['id'])
        return
    await bot.send_message(MOD_CHAT_ID, mod_text(s), reply_markup=mod_kb(s['id'], s['status']))
    for kind, fid in json.loads(s['files'] or '[]'):
        if kind == 'photo':
            await bot.send_photo(MOD_CHAT_ID, fid, caption=f'К истории №{s["id"]}')
        else:
            await bot.send_document(MOD_CHAT_ID, fid, caption=f'К истории №{s["id"]}')


@router.callback_query(Story.confirm, F.data == 'st:send')
async def story_send(c: CallbackQuery, state: FSMContext, bot: Bot):
    d = await state.get_data()
    await state.clear()
    now = int(time.time())
    with db() as con:
        cur = con.execute('INSERT INTO stories(user_id, kind, title, body, vuln, source, files, created, updated) '
                          'VALUES(?,?,?,?,?,?,?,?,?)', (c.from_user.id, d['kind'], d['title'], d['body'], d['vuln'],
                                                        d.get('source', ''), json.dumps(d.get('files', [])), now, now))
        sid = cur.lastrowid
    await c.message.edit_text(f'📨 История №{sid} отправлена модераторам. Мы напишем, когда её прочитают.\n'
                              f'Правдоподобная история — +{PTS_PLAUSIBLE} б., сценарий по ней — ещё +{PTS_SCENARIO} б.')
    await send_to_mods(bot, get_story(sid))
    await c.answer('Отправлено')


# ───────────────────────── модерация ─────────────────────────
def is_mod(uid: int) -> bool:
    return uid in ADMIN_IDS


def set_status(sid: int, status: str, mod_id: int, note: str | None = None, scene: int | None = None) -> None:
    with db() as con:
        con.execute('UPDATE stories SET status=?, mod_id=?, updated=?, mod_note=COALESCE(?, mod_note), '
                    'scene=COALESCE(?, scene) WHERE id=?', (status, mod_id, int(time.time()), note, scene, sid))


async def notify(bot: Bot, uid: int, text: str) -> None:
    try:
        await bot.send_message(uid, text)
    except Exception as e:  # пользователь мог остановить бота
        log.info('Не удалось написать %s: %s', uid, e)


async def approve(bot: Bot, sid: int, mod_id: int) -> str:
    s = get_story(sid)
    if not s or s['status'] not in ('new', 'clarify'):
        return 'Уже решено.'
    set_status(sid, 'plausible', mod_id)
    add_points(s['user_id'], PTS_PLAUSIBLE, f'История №{sid} правдоподобна', f'story:{sid}')
    await notify(bot, s['user_id'], f'✅ История №{sid} «{html.escape(s["title"])}» признана правдоподобной: '
                                    f'+{PTS_PLAUSIBLE} б. Всего: {total(s["user_id"])} б.')
    return f'+{PTS_PLAUSIBLE} б. начислено.'


async def to_scenario(bot: Bot, sid: int, mod_id: int, scene: int | None = None) -> str:
    s = get_story(sid)
    if not s or s['status'] in ('scenario', 'rejected'):
        return 'Уже решено.'
    gained = 0
    if s['status'] in ('new', 'clarify'):
        add_points(s['user_id'], PTS_PLAUSIBLE, f'История №{sid} правдоподобна', f'story:{sid}')
        gained += PTS_PLAUSIBLE
    set_status(sid, 'scenario', mod_id, scene=scene)
    add_points(s['user_id'], PTS_SCENARIO, f'По истории №{sid} создан сценарий', f'scenario:{sid}')
    gained += PTS_SCENARIO
    where = f' — сцена {scene}' if scene else ''
    await notify(bot, s['user_id'], f'🎬 По вашей истории №{sid} «{html.escape(s["title"])}» создан новый сценарий{where}! '
                                    f'+{gained} б. Всего: {total(s["user_id"])} б. · {rank(total(s["user_id"]))}')
    return f'+{gained} б. начислено.'


@router.callback_query(F.data.startswith('mod:'))
async def mod_action(c: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_mod(c.from_user.id):
        await c.answer('Только для модераторов.', show_alert=True)
        return
    _, act, sid = c.data.split(':')
    sid = int(sid)
    if act == 'ok':
        res = await approve(bot, sid, c.from_user.id)
    elif act == 'scn':
        res = await to_scenario(bot, sid, c.from_user.id)
    elif act == 'no':
        s = get_story(sid)
        if s and s['status'] in ('new', 'clarify'):
            set_status(sid, 'rejected', c.from_user.id)
            await notify(bot, s['user_id'], f'Спасибо за историю №{sid}. В этот раз она не подошла для сценария: '
                                            'не хватило подробностей или похожий случай уже есть в игре. Присылайте новые!')
            res = 'Отклонено.'
        else:
            res = 'Уже решено.'
    elif act == 'ask':
        await state.set_state(Clarify.question)
        await state.update_data(sid=sid)
        await c.message.answer(f'Напишите вопрос автору истории №{sid} одним сообщением. Отмена — /cancel.')
        await c.answer()
        return
    else:
        res = '?'
    s = get_story(sid)
    if s:
        try:
            await c.message.edit_text(mod_text(s), reply_markup=mod_kb(sid, s['status']))
        except Exception:  # текст не изменился
            pass
    await c.answer(res)


@router.message(Clarify.question, F.text)
async def mod_question(m: Message, state: FSMContext, bot: Bot):
    sid = (await state.get_data())['sid']
    await state.clear()
    s = get_story(sid)
    if not s:
        await m.answer('История не найдена.')
        return
    set_status(sid, 'clarify', m.from_user.id, note='Вопрос: ' + m.text[:500])
    author = FSMContext(storage=state.storage, key=StorageKey(bot_id=bot.id, chat_id=s['user_id'], user_id=s['user_id']))
    await author.set_state(Clarify.answer)
    await author.update_data(sid=sid)
    await notify(bot, s['user_id'], f'❓ Модератор уточняет по истории №{sid} «{html.escape(s["title"])}»:\n\n'
                                    f'{html.escape(m.text)}\n\nОтветьте одним сообщением.')
    await m.answer('Вопрос отправлен автору.')


@router.message(Clarify.answer, F.text)
async def author_answer(m: Message, state: FSMContext, bot: Bot):
    if await guard(m):
        return
    sid = (await state.get_data())['sid']
    await state.clear()
    s = get_story(sid)
    if not s:
        return
    with db() as con:
        con.execute('UPDATE stories SET body=body || ?, updated=? WHERE id=?',
                    ('\n\n[Уточнение] ' + m.text[:1500], int(time.time()), sid))
    await m.answer('Спасибо! Ответ передан модератору.', reply_markup=main_kb())
    await send_to_mods(bot, get_story(sid))


@router.message(Command('queue'))
async def queue(m: Message):
    if not is_mod(m.from_user.id):
        return
    with db() as con:
        rows = con.execute("SELECT id, title, status FROM stories WHERE status IN ('new','clarify','plausible') "
                           'ORDER BY id LIMIT 30').fetchall()
    if not rows:
        await m.answer('Очередь пуста.')
        return
    await m.answer('<b>Очередь историй</b>\n' + '\n'.join(
        f'№{r["id"]} «{html.escape(r["title"])}» — {STATUS[r["status"]]} · /show {r["id"]}' for r in rows))


@router.message(Command('show'))
async def show(m: Message, command: CommandObject):
    if not is_mod(m.from_user.id) or not (command.args or '').strip().isdigit():
        return
    s = get_story(int(command.args))
    if not s:
        await m.answer('Не найдено.')
        return
    await m.answer(mod_text(s), reply_markup=mod_kb(s['id'], s['status']))


@router.message(Command('scenario'))
async def scenario_cmd(m: Message, command: CommandObject, bot: Bot):
    """/scenario 12 17 — по истории №12 создана сцена 17."""
    if not is_mod(m.from_user.id):
        return
    a = (command.args or '').split()
    if not a or not a[0].isdigit():
        await m.answer('Формат: /scenario НОМЕР_ИСТОРИИ [НОМЕР_СЦЕНЫ]')
        return
    await m.answer(await to_scenario(bot, int(a[0]), m.from_user.id, int(a[1]) if len(a) > 1 and a[1].isdigit() else None))


@router.message(Command('award'))
async def award(m: Message, command: CommandObject, bot: Bot):
    """/award USER_ID БАЛЛЫ причина — ручная поправка."""
    if not is_mod(m.from_user.id):
        return
    a = (command.args or '').split(maxsplit=2)
    if len(a) < 2 or not a[0].isdigit() or not a[1].lstrip('-').isdigit():
        await m.answer('Формат: /award USER_ID БАЛЛЫ причина')
        return
    uid, amount, why = int(a[0]), int(a[1]), (a[2] if len(a) > 2 else 'решение модератора')
    add_points(uid, amount, why, 'manual')
    await notify(bot, uid, f'Модератор начислил {amount:+d} б.: {html.escape(why)}. Всего: {total(uid)} б.')
    await m.answer('Готово.')


@router.message(Command('stats'))
async def stats(m: Message):
    if not is_mod(m.from_user.id):
        return
    with db() as con:
        u = con.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        r = con.execute('SELECT COUNT(*) FROM runs').fetchone()[0]
        s = con.execute('SELECT status, COUNT(*) c FROM stories GROUP BY status').fetchall()
    await m.answer(f'Игроков: {u}\nПротоколов: {r}\nИстории: ' +
                   (', '.join(f'{STATUS.get(x["status"], x["status"])} — {x["c"]}' for x in s) or 'нет'))


@router.message(Command('myid'))
async def myid(m: Message):
    await m.answer(f'Ваш id: <code>{m.from_user.id}</code>\nid этого чата: <code>{m.chat.id}</code>')


# ───────────────────────── запуск ─────────────────────────
def build() -> tuple[Bot, Dispatcher]:
    init_db()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    return bot, dp


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if not BOT_TOKEN:
        raise SystemExit('Нет BOT_TOKEN. Скопируйте .env.example в .env и впишите токен от @BotFather.')
    if not WEBAPP_URL:
        log.warning('WEBAPP_URL не задан: кнопка «🎮 Играть» не появится.')
    bot, dp = build()
    await bot.set_my_commands([
        BotCommand(command='start', description='Главное меню'),
        BotCommand(command='story', description='Прислать историю для разбора'),
        BotCommand(command='points', description='Мои баллы и звание'),
        BotCommand(command='top', description='Рейтинг'),
        BotCommand(command='mystories', description='Мои истории'),
        BotCommand(command='cards', description='Карточки для печати'),
        BotCommand(command='scenes', description='Список сцен'),
        BotCommand(command='rules', description='Правила и баллы'),
        BotCommand(command='cancel', description='Отменить'),
    ])
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
