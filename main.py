import random
from telebot import types, TeleBot
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup
import sqlalchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from models import create_tables_models, Dictionary, WordsUser, WordsDel
import json
import os
from dotenv import load_dotenv

load_dotenv()
token_bot = os.getenv('TOKEN_BOT')
drive = os.getenv('DB_DRIVER')
user = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')
connect_name = os.getenv('DB_CONNECT_NAME')
port = os.getenv('DB_PORT')
database = os.getenv('DB_DATABASE')

state_storage = StateMemoryStorage()
bot = TeleBot(token_bot, state_storage=state_storage)
buttons = []


class OperationsDictionary:
    """

    Class for working with the Dictionary database
    after initializing the class, you need to call
    method connect() then create_tables(), then open_session()
    and after that you can call methods to process the data and
    after finishing working with the class, call method close_session()

    """
    def __init__(self, drive, database, connect_name, port, user, password):
        self.drive = drive
        self.database = database
        self.connect_name = connect_name
        self.port = port
        self.user = user
        self.password = password
        self.engine = None
        self.session = None

    def connect(self):
        dsn = (f'{self.drive}://{self.user}:{self.password}@'
               f'{self.connect_name}:{self.port}/{self.database}')
        self.engine = sqlalchemy.create_engine(dsn, pool_pre_ping=True)

    def create_tables(self):
        create_tables_models(self.engine)

    def open_session(self):
        session = sessionmaker(bind=self.engine)
        self.session = session()

    def close_session(self):
        self.session.close()

    def load_data(self, file):
        """

        Use this method to populate the Dictionary database from file JSON

        :param file: file name including path
        :type file: :obj:'str'

        """
        with open(file, encoding="utf-8") as f:
            json_data = json.load(f)
        for record in json_data:
            word_dict = Dictionary(**record)
            self.session.add(word_dict)
            self.session.commit()
            self.session.add(WordsUser(user_id=0, word_id=word_dict.id))
            self.session.commit()

    def get_data(self):
        """

        Use this method to debug and monitor data in the database

        """
        sql_query = self.session.query(Dictionary).all()
        for sqls in sql_query:
            print(sqls)
        sql_query = self.session.query(WordsUser).all()
        for sqls in sql_query:
            print(sqls)
        sql_query = self.session.query(WordsDel).all()
        for sqls in sql_query:
            print(sqls)

    def amount_data(self, table_name):
        """

        Use this method to determine the number of records in a particular table

        :param table_name: name of the desired table
        :type table_name: :obj:'str'

        :return: number of records in a particular table

        """
        model = {
            'dictionary': Dictionary,
            'words_user': WordsUser,
            'words_del': WordsDel
        }.get(table_name)
        number_records = self.session.query(model).count()
        return number_records

    def get_words(self, user_id=0, flag_count=False):
        """

        Use this method to get up-to-date data from the database
        for a specific user if flag_count=False then the method
        returns data in the form of a list of tuples if flag_count=True
        then the method returns the number of
        tuples (words from the Dictionary)

        :param user_id: Telegram user ID
        :type user_id: :obj:'int'

        :param flag_count: method use flag
        :type flag_count: :obj:'str'

        :return: list of tuples (current dictionary data
            for a specific user) or a number of
            tuples (words from the Dictionary)

        """
        sql_query = self.session.query(Dictionary) \
            .with_entities(Dictionary.id, Dictionary.target_word,
                           Dictionary.translate) \
            .join(WordsUser, WordsUser.word_id == Dictionary.id) \
            .outerjoin(WordsDel, WordsDel.word_id == WordsUser.word_id) \
            .filter((WordsDel.user_id.is_(None)) |
                    (WordsDel.user_id != user_id)) \
            .filter((WordsUser.user_id == 0) |
                    (WordsUser.user_id == user_id))
        if flag_count:
            result = sql_query.count()
        else:
            result = sql_query.all()
            random.shuffle(result)
            result = result[0:4]
        return result

    def add_word(self, user_id, target_word, translate):
        """

        Use this method to add a new word to the
        Dictionary for a specific user

        :param user_id: Telegram user ID
        :type user_id: :obj:'int'

        :param target_word: word in English
        :type target_word: :obj:'str'

        :param translate: word in Russian
        :type translate: :obj:'str'

        """
        word_dict = Dictionary(target_word=target_word, translate=translate)
        self.session.add(word_dict)
        self.session.commit()
        self.session.add(WordsUser(user_id=user_id, word_id=word_dict.id))
        self.session.commit()

    def del_word(self, user_id, word_id):
        """
        Use this method to remove a word for a specific user

        :param user_id: Telegram user ID
        :type user_id: :obj:'int'

        :param word_id: ID of the word in the dictionary
        :type word_id: :obj:'int'

        """
        sql_query = self.session.query(WordsUser) \
            .filter(WordsUser.user_id == user_id) \
            .filter(WordsUser.word_id == word_id)
        if len(sql_query.all()) > 0:
            sql_query.delete()
            self.session.query(Dictionary).filter(
                Dictionary.id == word_id).delete()
            self.session.commit()
        else:
            self.session.add(WordsDel(user_id=user_id, word_id=word_id))
            try:
                self.session.commit()
            except IntegrityError:
                self.session.rollback()

    def reset_db(self, user_id):
        """

        Use this method to reset all changes to
        the database for a specific user

        :param user_id: Telegram user ID
        :type user_id: :obj:'int'

        """
        sql_query = self.session.query(Dictionary) \
            .join(WordsUser, WordsUser.word_id == Dictionary.id) \
            .filter(WordsUser.user_id == user_id).all()
        for sqls in sql_query:
            self.session.delete(sqls)
        sql_query = self.session.query(WordsDel) \
            .filter(WordsDel.user_id == user_id).all()
        for sqls in sql_query:
            self.session.delete(sqls)
        self.session.commit()


class Command:
    """

    Class for typing requests to the bot

    """
    ADD_WORD = 'Добавить слово'
    DELETE_WORD = 'Удалить слово'
    NEXT = 'Дальше ⏭'
    BEGIN = 'Начать изучение'
    RESET = 'Сбросить изменения'


class MyStates(StatesGroup):
    """

    Class for saving the state of the
    bot for working out different scenarios

    """
    standby_mode = State()
    target_word = State()
    add_words_step1 = State()
    add_words_step2 = State()


def show_hint(*lines):
    return '\n'.join(lines)


def show_target(data):
    return f"{data['target_word']} -> {data['translate_word']}"


def standby_mode(message):
    """

    This method is needed to return parameters
    to wait for the user to select an action

    :param message: types.Message from user
    :type message: :obj:'telebot.types.Message'

    """
    cid = message.chat.id
    bot.set_state(message.from_user.id, MyStates.standby_mode, cid)
    with bot.retrieve_data(message.from_user.id, cid) as data:
        data['id_word'] = None
        data['target_word'] = ''
        data['translate_word'] = ''
        data['other_words'] = []
    markup = types.ReplyKeyboardMarkup(row_width=2)
    buttons_star = []
    begin_btn = types.KeyboardButton(Command.BEGIN)
    add_word_btn = types.KeyboardButton(Command.ADD_WORD)
    reset_btn = types.KeyboardButton(Command.RESET)
    buttons_star.extend([begin_btn, add_word_btn, reset_btn])
    markup.add(*buttons_star)
    str_message = show_hint(f"Вам доступно для изучения "
                            f"{words_db.get_words(cid, True)} слов(а)",
                            "Выберите дальнейшие действие:")
    bot.send_message(cid, str_message, reply_markup=markup)


@bot.message_handler(commands=['start'])
def start_bot(message):
    """

    The method called when the user commands /start
    is needed for greeting and switching to the mode
    of waiting for the user to select an action

    :param message: types.Message from user
    :type message: :obj:'telebot.types.Message'

    """
    cid = message.chat.id
    bot.send_message(cid, "Привет я бот - Учитель Английского языка!")
    standby_mode(message)


@bot.message_handler(commands=['cards'])
def create_cards(message):
    """

    The method called with the command "/cards" or as a
    result of the request "Next" or "Start learning"
    request is needed for the process of learning words,
    the bot displays the words to the user and asks them
    to select a translation for it

    :param message: types.Message from user
    :type message: :obj:'telebot.types.Message'

    """
    cid = message.chat.id
    markup = types.ReplyKeyboardMarkup(row_width=2)
    global buttons
    buttons = []
    data_words = words_db.get_words(cid)
    id_word = data_words[0][0]
    target_word = data_words[0][1]
    translate = data_words[0][2]
    others = [y for x, y, z in data_words[0:4]]
    other_words_btns = [types.KeyboardButton(word) for word in others]
    buttons.extend(other_words_btns)
    random.shuffle(buttons)
    next_btn = types.KeyboardButton(Command.NEXT)
    add_word_btn = types.KeyboardButton(Command.ADD_WORD)
    delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
    reset_btn = types.KeyboardButton(Command.RESET)
    buttons.extend([next_btn, add_word_btn, delete_word_btn, reset_btn])
    markup.add(*buttons)
    greeting = show_hint("Выбери перевод слова:", f"🇷🇺 {translate}")
    bot.send_message(message.chat.id, greeting, reply_markup=markup)
    bot.set_state(message.from_user.id, MyStates.target_word, cid)
    with bot.retrieve_data(message.from_user.id, cid) as data:
        data['id_word'] = id_word
        data['target_word'] = target_word
        data['translate_word'] = translate
        data['other_words'] = others


@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_cards(message):
    """

    The method is called upon request "Next" is
    needed to go to method create_cards()

    :param message: types.Message from user
    :type message: :obj:'telebot.types.Message'

    """
    create_cards(message)


@bot.message_handler(func=lambda message: message.text == Command.BEGIN)
def begin_cards(message):
    """

    The method is called upon request "Start studying"
    is needed to go to method create_cards()

    :param message: types.Message from user
    :type message: :obj:'telebot.types.Message'

    """
    create_cards(message)


@bot.message_handler(func=lambda message: message.text == Command.RESET)
def reset_bot(message):
    """

    The method called when the user requesting "Reset changes"
    is needed to reset database changes by the user

    :param message: types.Message from user
    :type message: :obj:'telebot.types.Message'

    """
    cid = message.chat.id
    words_db.reset_db(cid)
    bot.send_message(cid, "Изменения сброшены!")
    standby_mode(message)


@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def delete_word(message):
    """

    The method is called when the user requests "Delete word"
    and is needed to remove a specific word from the user data

    :param message: types.Message from user
    :type message: :obj:'telebot.types.Message'

    """
    cid = message.chat.id
    with bot.retrieve_data(message.from_user.id, cid) as data:
        words_db.del_word(cid, data['id_word'])
        bot.send_message(cid, show_hint("Слово удалено", show_target(data)))
    standby_mode(message)


@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word(message):
    """

    The method is called when the user requests "Add a word"
    and is needed to add a specific word to the user data,
    at this stage, the user is asked for a word in English

    :param message: types.Message from user
    :type message: :obj:'telebot.types.Message'

    """
    cid = message.chat.id
    bot.send_message(cid, "Введите слова на английском:")
    bot.set_state(message.from_user.id, MyStates.add_words_step1, cid)


@bot.message_handler(func=lambda message: True, content_types=['text'])
def message_reply(message):
    """

    The method is called when the user responds and is
    needed to process user responses in different scenarios,
    namely when giving an answer based on the translation
    of a word, as well as to continue filling
    in data for entering a new word

    :param message: types.Message from user
    :type message: :obj:'telebot.types.Message'

    """
    cid = message.chat.id
    state = bot.get_state(message.from_user.id, cid)
    if state == 'MyStates:target_word':
        text = message.text
        markup = types.ReplyKeyboardMarkup(row_width=2)
        with bot.retrieve_data(message.from_user.id, cid) as data:
            target_word = data['target_word']
            if text == target_word:
                global buttons
                buttons = []
                hint = show_target(data)
                hint_text = ["Отлично!❤", hint]
                next_btn = types.KeyboardButton(Command.NEXT)
                add_word_btn = types.KeyboardButton(Command.ADD_WORD)
                delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
                reset_btn = types.KeyboardButton(Command.RESET)
                buttons.extend([next_btn, add_word_btn,
                                delete_word_btn, reset_btn])
                hint = show_hint(*hint_text)
            else:
                for btn in buttons:
                    if btn.text == text:
                        btn.text = text + '❌'
                        break
                hint = show_hint("Допущена ошибка!",
                                 "Попробуй ещё раз вспомнить слово:",
                                 f"🇷🇺{data['translate_word']}")
        markup.add(*buttons)
        bot.send_message(cid, hint, reply_markup=markup)
    elif state == 'MyStates:add_words_step1':
        with bot.retrieve_data(message.from_user.id, cid) as data:
            data['id_word'] = None
            data['target_word'] = message.text
            data['translate_word'] = ''
            data['other_words'] = []
        bot.send_message(cid, "Введите слова на русском:")
        bot.set_state(message.from_user.id, MyStates.add_words_step2, cid)
    elif state == 'MyStates:add_words_step2':
        with bot.retrieve_data(message.from_user.id, cid) as data:
            data['translate_word'] = message.text
            words_db.add_word(cid, data['target_word'], data['translate_word'])
            bot.send_message(cid, show_hint("Слово добавлено",
                                            show_target(data)))
        standby_mode(message)


if __name__ == '__main__':
    words_db = OperationsDictionary(drive, database, connect_name, port, user,
                                    password)
    words_db.connect()
    words_db.create_tables()
    words_db.open_session()
    if words_db.amount_data('dictionary') == 0:
        words_db.load_data('tests_data.json')
    # words_db.get_data()
    print('Бот запущен...')
    bot.infinity_polling(skip_pending=True)
    words_db.close_session()
