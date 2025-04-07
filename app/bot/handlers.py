from aiogram import types, F
from aiogram.filters import Command, CommandObject
from aiogram.utils.markdown import hbold, hcode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import os
import tempfile
from loguru import logger
import re
import traceback
from typing import List, Dict, Any, Optional, Union, Set

# Заменяем импорт hbold на правильный импорт для aiogram 3.x
import aiogram.utils.formatting as fmt

from app.utils.filter_utils import FilterManager
from app.bot.product_parser import process_product_file, get_actual_price, request_stats, price_cache, CACHE_TTL
from app.utils.file_processor import parse_multiple_formats
from app.parser.ozon_parser import OzonParser, ProductInfo
import requests
from aiogram import Dispatcher
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ID администратора бота (можно получить из переменной окружения)
ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

# Создаем глобальный экземпляр улучшенного менеджера фильтров
filter_manager = FilterManager()

# Определяем состояния FSM для добавления товаров
class ProductList(StatesGroup):
    waiting_for_products = State()
    collecting_products = State()
    editing_product = State()
    viewing_list = State()
    choosing_method = State()

async def start_handler(message: types.Message):
    """
    Обработчик команды /start
    """
    await message.answer(
        "👋 Привет! Я бот для отслеживания цен на товары Ozon.\n\n"
        "🔍 Отправьте /new чтобы начать создание списка товаров для поиска.\n"
        "❓ Отправьте /help для получения справки по командам."
    )

async def help_handler(message: types.Message):
    """
    Обработчик команды /help
    """
    help_text = (
        "🤖 <b>Доступные команды:</b>\n\n"
        "/new - Создать новый список товаров\n"
        "/done - Завершить ввод товаров и начать поиск\n"
        "/cancel - Отменить текущую операцию\n"
        "/filters - Управление фильтрами\n"
        "/stopword - Управление стоп-словами\n"
        "/blacklist - Управление черным списком продавцов\n"
        "/dailyword - Ежедневное стоп-слово\n"
        "/article - Поиск товара по артикулу\n"
        "/version - Показать версию бота\n"
        "/improvements - Список улучшений\n"
        "/reset - Сбросить все настройки\n\n"
        "📝 <b>Форматы ввода товаров:</b>\n\n"
        "1. Простой формат:\n"
        "<code>название_товара артикул,цена[,валюта]</code>\n\n"
        "2. Структурированный формат:\n"
        "<code>ТОВАР 1\n"
        "ИМЯ: название\n"
        "АРТИКУЛ: артикул\n"
        "ЦЕНА: цена\n"
        "[ВАЛЮТА: валюта]</code>\n\n"
        "❗️ Артикул должен быть указан в названии товара или отдельным полем\n"
        "💰 Валюта по умолчанию: RUB"
    )
    await message.answer(help_text, parse_mode="HTML")

async def version_handler(message: types.Message):
    """
    Обработчик команды /version
    """
    version_info = (
        "🤖 <b>Ozon Parser Bot</b>\n\n"
        "Версия: 2.0.0\n"
        "Последнее обновление: 07.04.2024\n\n"
        "📝 <b>Изменения:</b>\n"
        "• Переход на aiogram 3.x\n"
        "• Улучшена обработка ошибок\n"
        "• Добавлена поддержка структурированного формата\n"
        "• Оптимизирована работа с браузером\n"
        "• Улучшена система фильтрации\n\n"
        "🔧 Используйте /improvements для просмотра всех возможностей"
    )
    await message.answer(version_info, parse_mode="HTML")

async def improvements_handler(message: types.Message):
    """
    Обработчик команды /improvements
    """
    improvements_text = (
        "🔧 <b>Доступные улучшения:</b>\n\n"
        "1. <b>Фильтрация товаров</b>\n"
        "• /stopword - добавление стоп-слов для фильтрации\n"
        "• /blacklist - блокировка нежелательных продавцов\n"
        "• /dailyword - автоматическая смена стоп-слова\n\n"
        "2. <b>Форматы ввода</b>\n"
        "• Поддержка структурированного формата\n"
        "• Автоматическое определение артикулов\n"
        "• Поддержка разных валют\n\n"
        "3. <b>Поиск товаров</b>\n"
        "• Кеширование результатов поиска\n"
        "• Умный поиск по артикулу\n"
        "• Обход защиты от ботов\n\n"
        "4. <b>Уведомления</b>\n"
        "• Мгновенные уведомления о снижении цен\n"
        "• Детальная информация о товарах\n"
        "• Ссылки на товары\n\n"
        "5. <b>Управление</b>\n"
        "• Простое добавление товаров\n"
        "• Редактирование списка\n"
        "• Сброс настроек\n\n"
        "❓ Используйте /help для получения справки по командам"
    )
    await message.answer(improvements_text, parse_mode="HTML")

async def filters_handler(message: types.Message):
    """
    Обработчик команды /filters
    """
    filters_text = (
        "🔧 <b>Управление фильтрами</b>\n\n"
        "1. <b>Стоп-слова</b>\n"
        "• /stopword add слово - добавить стоп-слово\n"
        "• /stopword remove слово - удалить стоп-слово\n"
        "• /stopword list - показать список стоп-слов\n"
        "• /stopword clear - очистить список\n\n"
        "2. <b>Черный список продавцов</b>\n"
        "• /blacklist add продавец - добавить в черный список\n"
        "• /blacklist remove продавец - удалить из черного списка\n"
        "• /blacklist list - показать черный список\n"
        "• /blacklist clear - очистить список\n\n"
        "3. <b>Ежедневное стоп-слово</b>\n"
        "• /dailyword - показать текущее стоп-слово\n"
        "• /dailyword set слово - установить стоп-слово\n"
        "• /dailyword clear - отключить ежедневное стоп-слово"
    )
    await message.answer(filters_text, parse_mode="HTML")

async def stopword_handler(message: types.Message, command: CommandObject):
    """
    Обработчик команды /stopword
    """
    if not command.args:
        await message.answer(
            "❓ Используйте:\n"
            "/stopword add слово - добавить стоп-слово\n"
            "/stopword remove слово - удалить стоп-слово\n"
            "/stopword list - показать список\n"
            "/stopword clear - очистить список"
        )
        return
        
    args = command.args.split()
    action = args[0].lower()
    
    if action == "list":
        words = filter_manager.get_stop_words()
        if words:
            await message.answer(
                "📋 Список стоп-слов:\n\n" + "\n".join(f"• {word}" for word in words)
            )
        else:
            await message.answer("📋 Список стоп-слов пуст")
            
    elif action == "clear":
        filter_manager.clear_stop_words()
        await message.answer("✅ Список стоп-слов очищен")
        
    elif action in ["add", "remove"] and len(args) > 1:
        word = " ".join(args[1:])
        if action == "add":
            filter_manager.add_stop_word(word)
            await message.answer(f"✅ Стоп-слово '{word}' добавлено")
        else:
            if filter_manager.remove_stop_word(word):
                await message.answer(f"✅ Стоп-слово '{word}' удалено")
            else:
                await message.answer(f"❌ Стоп-слово '{word}' не найдено")
    else:
        await message.answer("❌ Неверный формат команды")

async def blacklist_handler(message: types.Message, command: CommandObject):
    """
    Обработчик команды /blacklist
    """
    if not command.args:
        await message.answer(
            "❓ Используйте:\n"
            "/blacklist add продавец - добавить в черный список\n"
            "/blacklist remove продавец - удалить из черного списка\n"
            "/blacklist list - показать список\n"
            "/blacklist clear - очистить список"
        )
        return
        
    args = command.args.split()
    action = args[0].lower()
    
    if action == "list":
        sellers = filter_manager.get_blacklisted_sellers()
        if sellers:
            await message.answer(
                "📋 Черный список продавцов:\n\n" + "\n".join(f"• {seller}" for seller in sellers)
            )
        else:
            await message.answer("📋 Черный список пуст")
            
    elif action == "clear":
        filter_manager.clear_blacklisted_sellers()
        await message.answer("✅ Черный список очищен")
        
    elif action in ["add", "remove"] and len(args) > 1:
        seller = " ".join(args[1:])
        if action == "add":
            filter_manager.add_blacklisted_seller(seller)
            await message.answer(f"✅ Продавец '{seller}' добавлен в черный список")
        else:
            if filter_manager.remove_blacklisted_seller(seller):
                await message.answer(f"✅ Продавец '{seller}' удален из черного списка")
            else:
                await message.answer(f"❌ Продавец '{seller}' не найден в черном списке")
    else:
        await message.answer("❌ Неверный формат команды")

async def daily_word_handler(message: types.Message, command: CommandObject):
    """
    Обработчик команды /dailyword
    """
    if not command.args:
        word = filter_manager.get_daily_stop_word()
        if word:
            await message.answer(f"📅 Текущее ежедневное стоп-слово: {word}")
        else:
            await message.answer("❌ Ежедневное стоп-слово не установлено")
        return
        
    args = command.args.split()
    action = args[0].lower()
    
    if action == "set" and len(args) > 1:
        word = " ".join(args[1:])
        filter_manager.set_daily_stop_word(word)
        await message.answer(f"✅ Установлено ежедневное стоп-слово: {word}")
        
    elif action == "clear":
        filter_manager.clear_daily_stop_word()
        await message.answer("✅ Ежедневное стоп-слово отключено")
        
    else:
        await message.answer(
            "❓ Используйте:\n"
            "/dailyword - показать текущее стоп-слово\n"
            "/dailyword set слово - установить стоп-слово\n"
            "/dailyword clear - отключить ежедневное стоп-слово"
        )

async def article_command_handler(message: types.Message, command: CommandObject):
    """
    Обработчик команды /article для поиска товара по артикулу
    """
    if not command.args:
        await message.answer(
            "❓ Используйте: /article АРТИКУЛ\n"
            "Например: /article 123456789"
        )
        return
        
    article = command.args.strip()
    
    # Отправляем сообщение о начале поиска
    status_message = await message.answer(f"🔍 Ищу товар с артикулом {article}...")
    
    try:
        # Создаем парсер
        parser = OzonParser()
        
        try:
            # Ищем товар
            result = await parser.search_by_article(article)
            
            if result:
                # Формируем сообщение с результатом
                response = (
                    f"✅ Товар найден!\n\n"
                    f"📦 {result.name}\n"
                    f"🔢 Артикул: {result.article}\n"
                    f"💰 Цена: {result.price} {result.currency}\n"
                    f"👤 Продавец: {result.seller}\n"
                    f"🔗 Ссылка: {result.url}"
                )
            else:
                response = f"❌ Товар с артикулом {article} не найден"
                
            # Обновляем сообщение
            await status_message.edit_text(response)
            
        except Exception as e:
            logger.error(f"Error searching article {article}: {e}")
            await status_message.edit_text(f"❌ Ошибка при поиске товара: {str(e)}")
            
        finally:
            # Закрываем парсер
            await parser.close()
            
    except Exception as e:
        logger.error(f"Error creating parser: {e}")
        await status_message.edit_text("❌ Ошибка при создании парсера")
        
async def reset_handler(message: types.Message):
    """
    Обработчик команды /reset для сброса всех настроек
    """
    # Очищаем все фильтры
    filter_manager.clear_stop_words()
    filter_manager.clear_blacklisted_sellers()
    filter_manager.clear_daily_stop_word()
    
    # Очищаем кеш цен
    price_cache.clear()
    
    # Сбрасываем статистику
    stats = request_stats()
    for key in stats:
        stats[key] = 0
        
    await message.answer(
        "✅ Все настройки сброшены:\n\n"
        "• Список стоп-слов очищен\n"
        "• Черный список продавцов очищен\n"
        "• Ежедневное стоп-слово отключено\n"
        "• Кеш цен очищен\n"
        "• Статистика сброшена"
    )

async def stats_handler(message: types.Message):
    """
    Обработчик команды /stats для просмотра статистики
    """
    stats = request_stats()
    cache_size = len(price_cache)
    
    stats_text = (
        "📊 <b>Статистика запросов:</b>\n\n"
        f"Всего запросов: {stats['total']}\n"
        f"Попадания в кеш: {stats['cache_hits']}\n"
        f"Запуски браузера: {stats['browser_launches']}\n"
        f"Успешные API запросы: {stats['api_successes']}\n"
        f"Ошибки: {stats['failures']}\n\n"
        f"📦 Размер кеша: {cache_size} товаров\n"
        f"⌛️ Время жизни кеша: {CACHE_TTL//60} минут"
    )
    
    await message.answer(stats_text, parse_mode="HTML")

async def new_product_list_handler(message: types.Message, state: FSMContext):
    """
    Обработчик команды /new - создает новый список товаров
    """
    user_id = message.from_user.id
    user_name = message.from_user.full_name
    logger.info(f"Пользователь {user_id} ({user_name}) начал создание нового списка товаров")
    
    # Создаем клавиатуру с кнопками выбора способа добавления товаров в формате aiogram 3.x
    buttons = [
        [
            InlineKeyboardButton(text="Добавить текстом", callback_data="add_text"),
            InlineKeyboardButton(text="Загрузить файл", callback_data="add_file")
        ]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await message.answer(
        "Выберите способ добавления товаров для поиска:",
        reply_markup=markup
    )
    
    # Устанавливаем состояние, ожидаем выбор пользователя
    await state.set_state(ProductList.choosing_method)

async def done_handler(message: types.Message, state: FSMContext):
    """
    Обработчик команды /done для завершения ввода товаров
    """
    current_state = await state.get_state()
    if current_state not in [ProductList.collecting_products.state, ProductList.viewing_list.state]:
        await message.answer("Нет активного создания списка товаров.")
        return
    
    # Получаем список товаров
    user_data = await state.get_data()
    products = user_data.get("products", [])
    
    if not products:
        await message.answer("Вы не добавили ни одного товара. Операция отменена.")
        await state.clear()
        return
    
    # Создаем временный файл со списком товаров
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='w', encoding='utf-8') as temp_file:
        temp_path = temp_file.name
        for product in products:
            name = product.get("name", "")
            article = product.get("article", "")
            price = product.get("price", 0)
            currency = product.get("currency", "RUB")
            
            # Если артикул уже указан в товаре, используем его
            if article:
                temp_file.write(f"{name} {article},{price},{currency}\n")
            else:
                # Иначе предполагаем, что артикул указан в конце названия
                temp_file.write(f"{name},{price},{currency}\n")
    
    # Отправляем сообщение о начале поиска
    daily_word = filter_manager.get_daily_stop_word()
    await message.answer(
        f"🔍 Начинаю поиск {len(products)} товаров...\n\n"
        f"🔑 Ежедневное стоп-слово: {fmt.Bold(daily_word).as_html()}",
        parse_mode="HTML"
    )
    
    # Сбрасываем состояние
    await state.clear()
    
    try:
        # Запускаем поиск товаров
        await process_product_file(message.chat.id, temp_path, filter_manager)
    finally:
        # Удаляем временный файл
        os.unlink(temp_path)

async def cancel_handler(message: types.Message, state: FSMContext):
    """
    Обработчик команды /cancel
    """
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активной операции для отмены.")
        return
        
    await state.clear()
    await message.answer("✅ Операция отменена.")

async def handle_dailyword_without_slash(message: types.Message):
    """Обработчик для команды dailyword без слеша"""
    empty_command = CommandObject(command="dailyword", args="")
    await daily_word_handler(message, empty_command)

async def handle_stopword_without_slash(message: types.Message):
    """Обработчик для команды stopword без слеша"""
    empty_command = CommandObject(command="stopword", args="")
    await stopword_handler(message, empty_command)

async def handle_blacklist_without_slash(message: types.Message):
    """Обработчик для команды blacklist без слеша"""
    empty_command = CommandObject(command="blacklist", args="")
    await blacklist_handler(message, empty_command)

async def handle_article_without_slash(message: types.Message):
    """Обработчик для команды article без слеша"""
    empty_command = CommandObject(command="article", args="")
    await article_command_handler(message, empty_command)

async def handle_done_without_slash(message: types.Message, state: FSMContext):
    """Обработчик для команды done без слеша"""
    current_state = await state.get_state()
    if current_state in [ProductList.collecting_products.state, ProductList.viewing_list.state]:
        await done_handler(message, state)
    else:
        await message.answer("Сначала создайте список товаров с помощью команды /new")

async def handle_cancel_without_slash(message: types.Message, state: FSMContext):
    """Обработчик для команды cancel без слеша"""
    await cancel_handler(message, state)

async def process_method_selection(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обработчик выбора метода добавления товаров
    """
    await callback_query.answer()
    
    if callback_query.data == "add_text":
        await callback_query.message.edit_text(
            "Отправьте список товаров в одном из форматов:\n\n"
            "1. Простой формат (каждый товар с новой строки):\n"
            "<code>название_товара артикул,цена[,валюта]</code>\n\n"
            "2. Структурированный формат:\n"
            "<code>ТОВАР 1\n"
            "ИМЯ: название\n"
            "АРТИКУЛ: артикул\n"
            "ЦЕНА: цена\n"
            "[ВАЛЮТА: валюта]</code>\n\n"
            "После ввода всех товаров нажмите /done",
            parse_mode="HTML"
        )
        await state.set_state(ProductList.collecting_products)
        
    elif callback_query.data == "add_file":
        await callback_query.message.edit_text(
            "Отправьте текстовый файл (.txt) со списком товаров в одном из форматов:\n\n"
            "1. Простой формат (каждый товар с новой строки):\n"
            "<code>название_товара артикул,цена[,валюта]</code>\n\n"
            "2. Структурированный формат:\n"
            "<code>ТОВАР 1\n"
            "ИМЯ: название\n"
            "АРТИКУЛ: артикул\n"
            "ЦЕНА: цена\n"
            "[ВАЛЮТА: валюта]</code>\n\n"
            "После загрузки файла нажмите /done",
            parse_mode="HTML"
        )
        await state.set_state(ProductList.collecting_products)
        
    elif callback_query.data == "search_products":
        # Получаем сохраненный текст с товарами
        user_data = await state.get_data()
        product_text = user_data.get("product_text", "")
        
        if not product_text:
            await callback_query.message.edit_text("Ошибка: текст с товарами не найден. Попробуйте отправить список товаров снова.")
            await state.clear()
            return
            
        # Создаем временный файл со списком товаров
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='w', encoding='utf-8') as temp_file:
            temp_path = temp_file.name
            temp_file.write(product_text)
        
        # Отправляем сообщение о начале поиска
        daily_word = filter_manager.get_daily_stop_word()
        await callback_query.message.edit_text(
            f"🔍 Начинаю поиск товаров...\n\n"
            f"🔑 Ежедневное стоп-слово: {fmt.Bold(daily_word).as_html()}",
            parse_mode="HTML"
        )
        
        # Сбрасываем состояние
        await state.clear()
        
        try:
            # Запускаем поиск товаров
            await process_product_file(callback_query.message.chat.id, temp_path, filter_manager)
        finally:
            # Удаляем временный файл
            os.unlink(temp_path)
            
    elif callback_query.data == "not_products":
        await callback_query.message.edit_text("Хорошо, игнорирую это сообщение. Используйте /new для создания нового списка товаров.")
        await state.clear()

async def text_handler(message: types.Message, state: FSMContext):
    """
    Обработчик обычных текстовых сообщений
    """
    # Проверяем на команды без слеша
    text = message.text.strip().lower()
    command_mapping = {
        "dailyword": handle_dailyword_without_slash,
        "blacklist": handle_blacklist_without_slash,
        "stopword": handle_stopword_without_slash,
        "filters": filters_handler,
        "help": help_handler,
        "start": start_handler,
        "article": handle_article_without_slash,
        "version": version_handler,
        "new": new_product_list_handler,
        "done": lambda msg: handle_done_without_slash(msg, state),
        "cancel": lambda msg: handle_cancel_without_slash(msg, state)
    }
    
    if text in command_mapping:
        # Вызываем соответствующий обработчик команды
        await command_mapping[text](message)
        return
    
    # Если сообщение начинается с "/", проверяем, не является ли оно командой
    if message.text.startswith('/'):
        command_part = message.text.split()[0].lower()
        # Пропускаем известные команды, которые обрабатываются другими обработчиками
        known_commands = ['/start', '/help', '/article', '/filters', '/blacklist', '/stopword', 
                          '/dailyword', '/version', '/new', '/done', '/cancel']
        if command_part in known_commands:
            # Это известная команда, пропускаем обработку
            return
    
    # Если мы ожидаем ввод товаров, то это сообщение обрабатывается в другом месте
    current_state = await state.get_state()
    if current_state == ProductList.collecting_products.state:
        await collect_products_handler(message, state)
        return
    
    # Проверяем, похоже ли сообщение на список товаров
    if check_if_product_message(message.text):
        logger.info(f"Обнаружено текстовое сообщение с товарами от пользователя {message.from_user.id}")
        # Спрашиваем пользователя, хочет ли он начать поиск по этому списку товаров
        buttons = [
            [
                InlineKeyboardButton(text="Да, искать товары", callback_data="search_products"),
                InlineKeyboardButton(text="Нет, это не список", callback_data="not_products")
            ]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        # Анализируем формат ввода для более точного ответа
        has_comma_format = "," in message.text
        has_compact_format = any(re.search(r'[а-яА-Яa-zA-Z]+\d{5,}', line) for line in message.text.strip().split('\n'))
        
        if has_compact_format:
            format_message = "Обнаружен компактный формат ввода: названиетовараартикул,цена"
        elif has_comma_format:
            format_message = "Обнаружен простой формат ввода: название товара,цена"
        else:
            format_message = "Обнаружен список товаров"
        
        await message.reply(
            f"👀 {format_message}. Начать поиск по этому списку?",
            reply_markup=keyboard
        )
        
        # Сохраняем текст сообщения в состоянии
        await state.update_data(product_text=message.text)
        await state.set_state(ProductList.waiting_for_products)

def register_handlers_common(dp: Dispatcher):
    """
    Регистрация обработчиков команд и сообщений
    """
    # Регистрируем обработчики команд, которые работают в любых состояниях
    dp.message.register(start_handler, Command(commands=["start"]))
    dp.message.register(help_handler, Command(commands=["help"]))
    dp.message.register(version_handler, Command(commands=["version"]))
    dp.message.register(improvements_handler, Command(commands=["improvements"]))
    dp.message.register(article_command_handler, Command(commands=["article"]))
    dp.message.register(new_product_list_handler, Command(commands=["new"]))
    dp.message.register(reset_handler, Command(commands=["reset"]))
    dp.message.register(stats_handler, Command(commands=["stats"]))
    
    # Обработчики фильтров должны работать в любых состояниях
    dp.message.register(filters_handler, Command(commands=["filters"]))
    dp.message.register(blacklist_handler, Command(commands=["blacklist"]))
    dp.message.register(stopword_handler, Command(commands=["stopword"]))
    dp.message.register(daily_word_handler, Command(commands=["dailyword"]))
    
    # Регистрируем обработчик для callback-кнопок
    dp.callback_query.register(process_method_selection)
    
    # Регистрируем обработчики для команд внутри FSM
    dp.message.register(done_handler, Command(commands=["done"]), ProductList.collecting_products)
    dp.message.register(done_handler, Command(commands=["done"]), ProductList.viewing_list)
    dp.message.register(cancel_handler, Command(commands=["cancel"]), ProductList.collecting_products)
    
    # Регистрируем обработчик текстовых сообщений
    dp.message.register(text_handler) 