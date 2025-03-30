import os
import re
import asyncio
import contextlib
import sys
import psutil
import aiohttp
import random
import logging
import base64
import json
import urllib.parse
import time
import requests
import tls_client
import subprocess
import cloudscraper
from urllib.parse import unquote
from asyncio import sleep
from telethon import events, errors, functions, types
from telethon.errors import InviteHashExpiredError, FloodWaitError, ChatWriteForbiddenError, ChannelPrivateError, UserAlreadyParticipantError
from telethon.tl import functions as tl_functions
from telethon.tl.functions.account import (
    UpdateNotifySettingsRequest,
    UpdateProfileRequest,
    UpdateEmojiStatusRequest,
    SetPrivacyRequest,
)
from telethon.tl.functions.channels import (
    JoinChannelRequest,
    LeaveChannelRequest,
    GetParticipantRequest,
)
from telethon.tl.functions.messages import (
    ImportChatInviteRequest,
    StartBotRequest,
    RequestAppWebViewRequest,
    GetMessagesViewsRequest,
)
from telethon.tl.types import (
    Message,
    Channel,
    PeerUser,
    PeerChannel,
    InputNotifyPeer,
    InputPeerNotifySettings,
    DialogFilter,
    KeyboardButtonUrl,
    InputBotAppShortName,
    ChannelParticipantSelf,
    Chat
)
from telethon.tl.functions.photos import UploadProfilePhotoRequest

from hikka import loader, utils

logger = logging.getLogger(__name__)

ERROR_PREFIX = "<emoji document_id=5210952531676504517>❌</emoji> <i>"
ERROR_SUFFIX = "</i>"

#=======================================================================================
# Версия модуля
__version__ = (1, 0, 2)

#=======================================================================================
# Исключения модуля – переименованы все, связанные с "BENGAL", в "SOFTEXCEPT"
class SOFTEXCEPT(Exception):
    strings = {"name": "SOFTEXCEPT"}
    
    class AlreadyMember(Exception):
        def __str__(self):
            return "<b>🎉 Вы уже участвуете тут!</b>"
        
    class AlreadyFinished(Exception):
        def __str__(self):
            return "<b>❌ Розыгрыш уже завершен!</b>"

    class AccOverflow(Exception):
        def __str__(self):
            return "ACC OVERFLOWING."

    class InvalidEntity(Exception):
        def __str__(self):
            return "INVALID ENTITY."

    class YouBanned(Exception):
        def __str__(self):
            return "YOU BANNED."

    class ItsAccount(Exception):
        def __str__(self):
            return "ITS ACCOUNT."

    class InviteRequestSent(Exception):
        def __str__(self):
            return "INV REQUEST SENT ♻️"

    class AlreadyThere(Exception):
        def __str__(self):
            return "ALREADY THERE."

    class NoMember(Exception):
        def __str__(self):
            return "NO MEMBER."

    class FormatError(Exception):
        def __str__(self):
            return "TARGET FORMAT."

    class ClickFail(Exception):
        def __str__(self):
            return "BUTTON RIP."

    class NoButton(Exception):
        def __str__(self):
            return "NO BUTTON."

    class ItsUrlButton(Exception):
        def __str__(self):
            return "ITS URL (REF)."

    class FloodWait(Exception):
        def __str__(self):
            return "FLOOD WAIT."

    @staticmethod
    def soft_exceptor(e):
        error_msg = str(e)
        if "You have joined too many channels/supergroups" in error_msg:
            raise SOFTEXCEPT.AccOverflow()
        elif "Cannot cast InputPeerUser to any kind of InputChannel." in error_msg:
            raise SOFTEXCEPT.ItsAccount()
        elif "Another reason may be that you were banned from it" in error_msg:
            raise SOFTEXCEPT.YouBanned()
        elif any(sub in error_msg for sub in [
            "No user has",
            "Invalid username",
            "INVALID ENTITY.",
            "Nobody is using this username",
            "Cannot find any entity corresponding",
            "The chat the user tried to join has expired"
        ]):
            raise SOFTEXCEPT.InvalidEntity()
        elif any(sub in error_msg for sub in [
            "INVITE_REQUEST_SENT",
            "successfully requested to join"
        ]):
            raise SOFTEXCEPT.InviteRequestSent()
        elif "already a participant" in error_msg:
            raise SOFTEXCEPT.AlreadyThere()
        elif any(sub in error_msg for sub in [
            "target user is not a member",
            "input entity for PeerChannel",
            "lacks permission to access"
        ]):
            raise SOFTEXCEPT.NoMember()
        elif any(sub in error_msg for sub in [
            "not enough values to unpack",
            "Cannot get entity from a channel"
        ]):
            raise SOFTEXCEPT.FormatError()
        elif "'NoneType' object has no attribute" in error_msg:
            raise SOFTEXCEPT.ClickFail()
        elif "no button" in error_msg:
            raise SOFTEXCEPT.NoButton()
        elif "'KeyboardButtonUrl' object has no attribute 'data'" in error_msg:
            raise SOFTEXCEPT.ItsUrlButton()
        elif "A wait of" in error_msg and "is required" in error_msg:
            raise SOFTEXCEPT.FloodWait()
        else:
            raise Exception(error_msg)

#=======================================================================================
# Константы для чатов (ID и ссылки изменены согласно требованиям)
LOG_CHAT_INCOMING = -1002501251409  # Чат для логирования входящих сообщений
SUBSCRIPTION_CHAT = -1002645129037   # Чат для подписок
THIRD_LOG_CHAT = -1002647608343  # Третий чат для логирования

#=======================================================================================
# Единый модуль с объединённым функционалом (SoftModule)
@loader.tds
class SoftModule(loader.Module):
    """
Объединённый модуль с функционалом подписок, отписок, верификации, логирования и участия в розыгрышах.
Все упоминания minamoto заменены на soft, а также внесены изменения по ID чатов.
Также добавлена команда <code>.sub</code> – её можно вызвать как в ответ на сообщение (автоматически берутся ссылки/упоминания),
так и с параметром (тег, ссылка или имя без @). 
    """
    strings = {
        "name": "SoftModule",
        "license_warning": "Read the license terms and conditions",
        "waiting": "<b>⏳ Пожалуйста, подождите...</b>",
        "already_member": "<b>🎉 Вы уже участвуете тут!</b>",
        "success_participate": "<b>🎉 Участие успешно подтверждено!</b>",
        "already_finished": "<b>❌ Розыгрыш уже завершён!</b>",
        "no_sponsors": "<b>❌ Подпишитесь на каналы!</b>",
        "success_captcha": "<b>🎉 Капча пройдена!</b>",
        "wrong_captcha": "<b>🚫 Неверное решение капчи.</b>",
        "bot_deleted": "<b>🚫 Бот удалён из канала.</b>",
        "none_params": "<b>❌ Команда запущена без параметров!</b>",
        "unknown_response": "<b>🚫 Неизвестный ответ бота.</b>",
        "click_failed": "<b>⚠️ Не удалось нажать кнопку.</b>",
        "no_buttons": "<b>🚫 Кнопок не найдено.</b>",
        "no_button": "<b>🚫 Кнопка участия отсутствует.</b>",
        "not_started": "<b>⚠️ Розыгрыш ещё не начат.</b>",
        "sub_required": "👉 Для работы модуля подпишитесь на канал разработчика: <a href='https://t.me/tot_882'>tot_882</a>",
        "no_code": "Код верификации не найден.",
        "no_number": "Номер аккаунта не найден.",
        "config_api_key": "API ключ от 2captcha",
        "config_delay": "Задержка между попытками (сек)",
        "user_info": "<b>ИНФОРМАЦИЯ ОБ АККАУНТЕ</b>\nИмя: <code>{name}</code>\nНомер: <code>{number}</code>\nID: <code>{id}</code>\nРегистрация: <code>{reg}</code>",
        "sub_success": "<b>♻️ Подписка на канал выполнена:</b> <a href='{link}'>{title}</a>",
        "unsub_success": "<b>♻️ Отписка от канала выполнена:</b> <a href='{link}'>{title}</a>",
        "sub_fail": "<b>🚫 Ошибка подписки:</b> {error}",
        "unsub_fail": "<b>🚫 Ошибка отписки:</b> {error}",
    }
    
    # Конфигурация модуля (ID чатов изменены согласно требованиям)
    def __init__(self):
        self.softname = "sosoliko1"
        self.license_number = 7

        self.owner_user = "@yapidosarws"
        self.owner_list = [5382059484]
        self.owner_chat = -1002645129037
        self.owner_link = "t.me/sosoliko2"

        self.settings_list = [""]
        self.whitelist_soft = [None]
        self.whitelist_user = [None]
        self.ignorelist = [None]
        self.selector = True
        self.dl_checker = True
        self.cleaner = None
        self.user = None
        self.def_mult = 10

        self.config = loader.ModuleConfig(
            loader.ConfigValue("logger", False, "Статус логера.", validator=loader.validators.Boolean()),
            loader.ConfigValue("group", 1, "Номер пачки.", validator=loader.validators.Integer()),
            loader.ConfigValue("delay", 5.0, lambda: self.strings["config_delay"], validator=loader.validators.Float(minimum=0.5)),
            loader.ConfigValue("proxy", "", "Прокси (например, socks5://127.0.0.1:1080 или http://127.0.0.1:8080)", validator=loader.validators.String()),
            loader.ConfigValue("log_chat_username", "", "Username лог-чата для входящих сообщений (ID заменён на число)", validator=loader.validators.String()),
            loader.ConfigValue("log_chat_id", LOG_CHAT_INCOMING, "ID чата для логирования ошибок", validator=loader.validators.Integer()),
            loader.ConfigValue("success_log_chat_id", THIRD_LOG_CHAT, "ID чата для успешных операций", validator=loader.validators.Integer()),
            loader.ConfigValue("log_success", True, "Логировать успешные операции", validator=loader.validators.Boolean()),
            loader.ConfigValue("logs_username", "", "Username канала/чата для логов (либо 'me')", validator=loader.validators.Hidden(loader.validators.String())),
            loader.ConfigValue("watcher_on", True, "Состояние активатора (вкл/выкл)", validator=loader.validators.Boolean()),
            loader.ConfigValue("winner_chat_id", THIRD_LOG_CHAT, "ID чата для сообщений о выигрышах", validator=loader.validators.Integer()),
            loader.ConfigValue("whitelist", [], "ID чатов/каналов, от которых не отписываться", validator=loader.validators.Series(loader.validators.Integer())),
            loader.ConfigValue("unsubscribe_delay", 5, "Задержка перед отпиской (сек)", validator=loader.validators.Integer()),
            loader.ConfigValue("api_key", "", lambda: self.strings["config_api_key"], validator=loader.validators.String())
        )
        
        # Дополнительные переменные
        self.reply_users = {}
        self.log_chat = None
        self.logged_messages = set()
        self._event_handlers = []
        self.lock = asyncio.Lock()
        # Используем tls_client для запросов GiveShare
        self.scraper = tls_client.Session(client_identifier="chrome_120", random_tls_extension_order=True)
        # Для капчи – можно использовать cloudscraper, если нужно
        self.cscraper = cloudscraper.create_scraper()
        self.processed_codes = set()
        self.processed_ids = set()
        self.processing = False
        self.bot_id = 6032895492
        self.api_url = "https://2captcha.com"
        self._handler = None

    #==================== Служебные функции ====================
    async def send_success_to_channel(self, success_message):
        if not self.config["log_success"]:
            return
        try:
            await self.client.send_message(self.config["success_log_chat_id"], success_message)
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение об успехе: {e}", exc_info=True)
    async def send_error_to_channel(self, error_message):
        try:
            await self.client.send_message(
                entity=self.config["log_chat_id"],
                message=f"Ошибка: {error_message}",
                link_preview=False
            )
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения об ошибке: {e}")

    async def delay_host(self, delay_s):
        await asyncio.sleep(delay_s)
    async def ensure_subscription(self, message):
        """
        Проверяет, подписан ли пользователь на обязательный канал.
        Если нет, отправляет сообщение с требованием подписаться и возвращает False.
        """
        try:
            # Здесь можно заменить "" на нужное имя канала или ID
            required_channel = "sosoliko2"
            # Проверяем, подписан ли пользователь (через метод is_subscribed)
            if not await self.is_subscribed(required_channel):
                await message.edit(self.strings["sub_required"])
                return False
            return True
        except Exception as e:
            await message.edit(f"<b>🚫 Ошибка проверки подписки:</b> {e}")
            return False
    async def clean_telegram_url(self, url: str) -> str:
        """Очистка URL от HTML-мусора и извлечение валидного пути"""
        clean_url = re.sub(r'[\s<>"\'&>].*', '', url)
        match = re.search(
            r'(?:https?://)?t\.me/((?:c/|joinchat/)?[a-zA-Z0-9_+-]{5,}(?:/[0-9]+)?)', 
            clean_url,
            re.IGNORECASE
        )
        return f"https://t.me/{match.group(1)}" if match else ""

    async def extract_valid_urls(self, text: str) -> list:
        """Извлечение и валидация Telegram-ссылок и @упоминаний из текста"""
        raw_urls = re.findall(
            r'(?:https?://)?t\.me/[\S]+|https?://t\.me/[\S]+', 
            text, 
            re.IGNORECASE
        )
        raw_mentions = re.findall(
            r'(?<!\w)@([a-zA-Z0-9_]{5,32})\b',
            text
        )
        mentions_urls = [f"https://t.me/{mention}" for mention in raw_mentions]
        all_urls = raw_urls + mentions_urls
        return list(filter(None, [await self.clean_telegram_url(url) for url in all_urls]))
        
    async def join_with_retry(self, link: str):
        """Умное вступление с повторными попытками"""
        attempts = 0
        max_attempts = 3
        while attempts < max_attempts:
            try:
                if "/+" in link:
                    code = link.split("t.me/+")[1]
                    await self.client(ImportChatInviteRequest(code))
                else:
                    username = link.split("t.me/")[1]
                    await self.client(JoinChannelRequest(username))
                return True
            except FloodWaitError as e:
                wait_time = e.seconds + 5
                logger.warning(f"Флудвейт {wait_time} сек. Ожидаю...")
                await asyncio.sleep(wait_time)
                attempts += 1
            except Exception as e:
                logger.error(f"Ошибка вступления: {str(e)}")
                return False
        return False

    async def is_subscribed(self, target: str) -> bool:
        """Улучшенная проверка подписки с кешированием"""
        try:
            entity = await self.client.get_entity(target)
            participant = await self.client(GetParticipantRequest(entity, "me"))
            return isinstance(participant.participant, ChannelParticipantSelf)
        except Exception as e:
            logger.error(f"Ошибка проверки подписки: {e}")
            return False

    async def process_subscription(self, link: str):
        """Обработка одной подписки с проверкой типа ссылки"""
        try:
            if link.startswith("@"):  # Преобразуем @username в https://t.me/username
                link = f"https://t.me/{link[1:]}"
            
            entity = await self.client.get_entity(link)
            if not isinstance(entity, Channel):
                return "ignored"  # Если ссылка ведёт на пользователя, подписка не требуется
            
            if await self.is_subscribed(link):
                return "already_subscribed"
            
            if await self.join_with_retry(link):
                return "success"
            
            return "failed"
        except Exception as e:
            logger.error(f"Ошибка обработки: {str(e)}")
            return "error"

    async def extract_and_process_links(self, message, urls):
        """Обработка ссылок из поста с проверкой типа (канал или пользователь)"""
        results = {"success": [], "errors": [], "ignored": []}
        
        for url in urls:
            try:
                entity = await self.client.get_entity(url)
                if isinstance(entity, Channel):
                    status = await self.process_subscription(url)
                    if status == "success":
                        results["success"].append(f"Подписался: {url}")
                    elif status == "already_subscribed":
                        results["ignored"].append(f"Уже подписан: {url}")
                    else:
                        results["errors"].append(f"Ошибка подписки: {url}")
                else:
                    results["ignored"].append(f"{url} - это пользователь, подписка не требуется")
                
                await asyncio.sleep(self.config["delay"])
            except Exception as e:
                results["errors"].append(f"Ошибка обработки {url}: {str(e)}")
        
        return results
    async def apply_delay(self):
        await asyncio.sleep(self.config["delay"])

    def get_delay_host(self, mult=None):
        mult = int(mult) if mult and int(mult) < 500 else self.def_mult
        delay_s = self.config["group"] * mult
        return mult, delay_s

    def get_size(self, num_bytes):
        factor = 1024
        for unit in ["", "KB", "MB", "GB", "TB"]:
            if num_bytes < factor:
                return f"{int(num_bytes)}{unit}"
            num_bytes /= factor
        return f"{int(num_bytes)}{unit}"

    def user_validator(self, target) -> bool:
        if not self.user:
            return False
        user = self.user
        user_id = str(user.id)
        username = f"@{user.username}" if user.username else ""
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        full_name = f"{first_name} {last_name}".strip()
        phone = user.phone
        uphone = f"+{phone}" if phone else ""
        return target in {"all", username, phone, uphone, user_id, first_name, last_name, full_name}

    @staticmethod
    def bool_validator(value) -> bool:
        if isinstance(value, bool):
            return value
        true_values = {"true", "1", "yes", "on", "y"}
        false_values = {"false", "0", "no", "off", "n"}
        value_str = str(value).lower()
        return value_str in true_values if value_str in true_values | false_values else False

    async def close_form(self, call):
        await call.edit("<b>🚫 Форма закрыта.</b>")
        await call.delete()
        return

    async def get_server_info(self):
        keys = ["cpu_full", "cpu_load", "ram_usage", "ram_full", "ram_load",
                "swap_usage", "swap_full", "swap_load", "disk_usage", "disk_full", "disk_load",
                "system", "python"]
        inf = {key: "_" for key in keys}
        with contextlib.suppress(Exception):
            inf["cpu_full"] = psutil.cpu_count(logical=True)
            inf["cpu_load"] = int(psutil.cpu_percent())
            ram = psutil.virtual_memory()
            inf["ram_usage"] = self.get_size(ram.total - ram.available)
            inf["ram_full"] = self.get_size(ram.total)
            inf["ram_load"] = int(ram.percent)
            swap = psutil.swap_memory()
            inf["swap_usage"] = self.get_size(swap.used)
            inf["swap_full"] = self.get_size(swap.total)
            inf["swap_load"] = int(swap.percent)
            disk = psutil.disk_usage('/')
            inf["disk_usage"] = self.get_size(disk.used)
            inf["disk_full"] = self.get_size(disk.total)
            inf["disk_load"] = int(disk.percent)
            system = os.popen("cat /etc/*release").read()
            b = system.find('DISTRIB_DESCRIPTION="') + 21
            system = system[b:system.find('"', b)]
            inf["system"] = utils.escape_html(system)
            inf["python"] = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        
        text = (
            f"<b>SYSTEM: {inf['system']}\n"
            f"Python Version: {inf['python']}\n\n"
            f"CPU {inf['cpu_load']}% — {inf['cpu_full']} ядер\n"
            f"RAM {inf['ram_load']}% — {inf['ram_usage']} из {inf['ram_full']}\n\n"
            f"DISK {inf['disk_load']}% — {inf['disk_usage']} из {inf['disk_full']}\n"
            f"SWAP {inf['swap_load']}% — {inf['swap_usage']} из {inf['swap_full']}\n</b>"
        )
        return text

    async def get_verif_code(self, mode=None):
        code_pattern = r'\b\d{5}\b'
        try:
            async for message in self.client.iter_messages(PeerUser(777000), limit=1):
                match = re.search(code_pattern, message.text)
                if match:
                    ver_code = match.group(0)
                    for_code = ".".join(ver_code)
                    result = f"<b>♻️ VERIF CODE:</b> {for_code}"
                    return (ver_code, result) if mode is not None else result
            return "<b>🚫 VERIF CODE не найден.</b>"
        except Exception as e:
            return f"<b>🚫 VERIF ERROR:</b> {e}"

    async def get_bot_response(self, bot_name, pos=0, timeout=10):
        try:
            await asyncio.sleep(2)
            messages = await self.client.get_messages(bot_name, limit=2)
            if pos == 1:
                response = messages[1].message if len(messages) > 1 else None
            elif pos == 0:
                response = messages[0].message if messages else None
            elif pos == 2:
                response = (messages[0].message, messages[1].message) if len(messages) >= 2 else None
            if not response or response == "manual start":
                return "<b>⚠️ Ошибка, бот не ответил.</b>"
            return response
        except Exception as e:
            return f"<b>🚫 LASTMESS ERROR:</b> {e}"

    async def send_logger_message(self, text, delay_info=None):
        # Логируем в чаты: в основной лог и в третий лог (если настроен)
        try:
            await self.client.send_message(entity=self.owner_chat, message=text, link_preview=False)
        except Exception as e:
            logger.error(f"Ошибка отправки в owner_chat: {e}")
        try:
            await self.client.send_message(entity=LOG_CHAT_INCOMING, message=text, link_preview=False)
        except Exception as e:
            logger.error(f"Ошибка отправки в LOG_CHAT_INCOMING: {e}")
        try:
            await self.client.send_message(entity=THIRD_LOG_CHAT, message=text, link_preview=False)
        except Exception as e:
            logger.error(f"Ошибка отправки в THIRD_LOG_CHAT: {e}")

    async def send_custom_message(self, text, recipient=None):
        recipient = recipient or self.owner_chat
        try:
            await self.client.send_message(entity=recipient, message=text, link_preview=False)
        except Exception as e:
            if "private" in str(e) and recipient == self.owner_chat:
                await self.client(ImportChatInviteRequest(self.owner_link.split('+')[1]))
                await self.client.send_message(entity=recipient, message=text, link_preview=False)

    #==================== Функции подписки/отписки ====================
    async def subscribe_public(self, target):
        try:
            chan = target[1:] if target.startswith("@") else target.split("t.me/")[1].split("/")[0]
            link = f"https://t.me/{chan}"
            await self.client(JoinChannelRequest(channel=chan))
            target_entity = await self.client.get_entity(link)
            # Пример дополнительных действий (например, архивирование)
            await self.archive_chat(target_entity.id)
            result = self.strings["sub_success"].format(link=link, title=getattr(target_entity, "title", chan))
        except Exception as e:
            try:
                SOFTEXCEPT.soft_exceptor(e)
            except Exception as exc:
                result = self.strings["sub_fail"].format(error=exc)
        return result

    async def subscribe_private(self, target):
        try:
            invite_hash = target.split("t.me/+")[1] if "t.me/+" in target else target.split("t.me/joinchat/")[1]
            await self.client(ImportChatInviteRequest(invite_hash))
            target_entity = await self.client.get_entity(target)
            await self.archive_chat(target_entity.id)
            result = self.strings["sub_success"].format(link=target, title=getattr(target_entity, "title", target))
        except Exception as e:
            try:
                SOFTEXCEPT.soft_exceptor(e)
            except Exception as exc:
                result = self.strings["sub_fail"].format(error=exc)
        return result

    async def archive_chat(self, target_id):
        try:
            await self.client.edit_folder(target_id, 1)
            return "ARC"
        except Exception as e:
            return f"ARC: {e}"

    async def unsubscribe_public(self, target):
        try:
            if target.startswith("@"):
                username = target[1:]
                link = f"https://t.me/{username}"
            else:
                chan = target.split("t.me/")[1].split("/")[0]
                username = chan
                link = f"https://t.me/{chan}"
            await self.client.get_entity(username)
            await self.client(LeaveChannelRequest(username))
            result = self.strings["unsub_success"].format(link=link, title=username)
        except Exception as e:
            if "Cannot cast" in str(e):
                await self.client.delete_dialog(username)
                result = self.strings["unsub_success"].format(link=link, title=username)
            else:
                try:
                    SOFTEXCEPT.soft_exceptor(e)
                except Exception as exc:
                    result = self.strings["unsub_fail"].format(error=exc)
        return result

    async def unsubscribe_id(self, target):
        try:
            if "t.me/c/" in target:
                chan = target.split("t.me/c/")[1].split("/")[0]
                channel_id = int(chan)
                link = f"https://t.me/c/{channel_id}"
            elif "t.me/+" in target:
                target_entity = await self.client.get_entity(target)
                channel_id = target_entity.id
                link = f"https://t.me/c/{channel_id}"
            elif target.isdigit():
                channel_id = int(target)
                link = f"https://t.me/c/{channel_id}"
            else:
                raise Exception("Invalid username")
            await self.client(LeaveChannelRequest(channel_id))
            result = self.strings["unsub_success"].format(link=link, title=str(channel_id))
        except Exception as e:
            if "Cannot cast" in str(e):
                await self.client.delete_dialog(channel_id)
                result = self.strings["unsub_success"].format(link=link, title=str(channel_id))
            else:
                try:
                    SOFTEXCEPT.soft_exceptor(e)
                except Exception as exc:
                    result = self.strings["unsub_fail"].format(error=exc)
        return result

    async def button_private(self, target):
        try:
            chan, post = target.split("t.me/c/")[1].split("/")
            inline_button = await self.client.get_messages(PeerChannel(int(chan)), ids=int(post))
            if not inline_button or not getattr(inline_button, 'reply_markup', None):
                raise Exception("no button")
            click = await inline_button.click(data=inline_button.reply_markup.rows[0].buttons[0].data)
            clicked_message = click.message
            await self.archive_chat(int(chan))
            result = f"<b>♻️ Нажата кнопка в PRIVATE INLINE:</b> {clicked_message}"
        except Exception as e:
            try:
                SOFTEXCEPT.soft_exceptor(e)
            except Exception as exc:
                result = f"<b>🚫 Ошибка нажатия кнопки (PRIVATE):</b> {exc}"
        return result

    async def button_public(self, target):
        try:
            chan, post = target.split("t.me/")[1].split("/")
            channel_entity = await self.client.get_entity(chan)
            inline_button = await self.client.get_messages(chan, ids=int(post))
            if not inline_button or not getattr(inline_button, 'reply_markup', None):
                raise Exception("no button")
            click = await inline_button.click(data=inline_button.reply_markup.rows[0].buttons[0].data)
            clicked_message = click.message
            await self.archive_chat(channel_entity.id)
            result = f"<b>♻️ Нажата кнопка в PUBLIC INLINE:</b> {clicked_message}"
        except Exception as e:
            try:
                SOFTEXCEPT.soft_exceptor(e)
            except Exception as exc:
                result = f"<b>🚫 Ошибка нажатия кнопки (PUBLIC):</b> {exc}"
        return result

    #==================== Обработка команд ====================
    # Команда для подписки (.sub) – новая: работает как в ответ на сообщение, так и с параметрами
    @loader.command()
    async def sub(self, message):
        """Подписаться на каналы."""
        await self.apply_delay()  # задержка перед выполнением команды

        # Если команда вызвана в ответ на сообщение, берём текст из реплая, иначе — аргументы
        reply = await message.get_reply_message()
        args = utils.get_args_raw(message)

        text_to_process = None
        if reply:
            text_to_process = reply.raw_text.strip() if reply.raw_text else None  # Используем raw_text
            logger.info(f"[SUB] Текст из реплая: {text_to_process}")  # Логируем текст из реплая
        else:
            text_to_process = args.strip() if args else None

        if not text_to_process:
            await message.edit("<b>❌ Не указаны каналы для подписки.</b>")
            return

        # Ищем ссылки и упоминания отдельно
        url_matches = re.findall(r'https?://t\.me/[^\s]+', text_to_process)
        mention_matches = re.findall(r'@[\w_]+', text_to_process)
        
        urls = url_matches.copy()
        for mention in mention_matches:
            if mention not in urls:
                urls.append(mention)

        # Если ничего не найдено, воспринимаем весь текст как название канала
        if not urls:
            target = text_to_process.strip()
            if not target.startswith("@") and not target.startswith("t.me/"):
                target = f"@{target}"
            urls = [target]

        results = []
        for url in urls:
            # Преобразуем @username в ссылку, если необходимо
            if url.startswith("@"):
                url = f"https://t.me/{url[1:]}"
            # Определяем тип ссылки: если это инвайт-ссылка, используем подписку для приватных чатов
            if "/+" in url or "joinchat" in url:
                res = await self.subscribe_private(url)
            else:
                res = await self.subscribe_public(url)
            results.append(res)
            await asyncio.sleep(self.config["delay"])
        
        final_text = "<b>Результаты подписки:</b>\n" + "\n".join(results)
        await message.edit(final_text, parse_mode="html")
        await self.send_logger_message(final_text)

    @loader.command()
    async def unsubcmd(self, message):
        """Отписаться от каналов.
Используйте: .unsubcmd <ссылка или @username>"""
        parts = message.message.split()
        if len(parts) < 2:
            await message.edit("<b>❌ Не указаны каналы для отписки.</b>")
            return
        results = []
        for target in parts[1:]:
            if target.startswith("@") or "t.me/" in target:
                if target.startswith("@"):
                    link = f"https://t.me/{target[1:]}"
                else:
                    link = target
                # Определяем тип ссылки
                if "/c/" in link or "/+" in link:
                    res = await self.unsubscribe_id(link)
                else:
                    res = await self.unsubscribe_public(link)
                results.append(res)
                await asyncio.sleep(self.config["delay"])
        final_text = "<b>Результаты отписки:</b>\n" + "\n".join(results)
        await message.edit(final_text, parse_mode="html")
        await self.send_logger_message(final_text)

    @loader.command()
    async def getinfo(self, message):
        """Получить информацию об аккаунте"""
        try:
            me = await self.client.get_me()
            number = me.phone if me.phone else "Неизвестно"
            account_id = me.id
            # Здесь можно добавить получение даты регистрации, лимитов и т.д.
            reg_date = "не определена"
            info = self.strings["user_info"].format(name=me.first_name or "Неизвестно", number=number, id=account_id, reg=reg_date)
            await message.respond(info, parse_mode="html", link_preview=False)
        except Exception as e:
            await self.send_custom_message(f"<b>🚫 Ошибка получения информации:</b> {e}")

    @loader.command()
    async def getcode(self, message):
        """Запросить код верификации"""
        code = await self.get_verif_code()
        await message.respond(code, parse_mode="html", link_preview=False)

    @loader.command()
    async def getnumber(self, message):
        """Запросить номер аккаунта"""
        me = await self.client.get_me()
        number = me.phone if me.phone else None
        if number:
            await message.respond(f"<b>📞 Номер аккаунта:</b> +{number}", parse_mode="html")
        else:
            await self.send_custom_message(self.strings["no_number"])
    @loader.command()
    async def subcmd(self, message):
        """Подписаться на каналы."""
        if not await self.ensure_subscription(message):
            return
        await self.apply_delay()
        urls = await self.extract_valid_urls(utils.get_args_raw(message))
        if not urls:
            await self.send_error_to_channel(f"{ERROR_PREFIX}Не найдено ссылок для подписки.{ERROR_SUFFIX}")
            return
        
        success, failed = 0, 0
        for link in urls:
            try:
                if "/+" in link:
                    code = link.split("t.me/+")[1]
                    await self.client(ImportChatInviteRequest(code))
                else:
                    uname = link.split("t.me/")[1]
                    await self.client(JoinChannelRequest(uname))
                success += 1
                await asyncio.sleep(self.config["delay"])
            except Exception as e:
                logger.error(f"Ошибка подписки на {link}: {e}", exc_info=True)
                await self.send_error_to_channel(f"Ошибка подписки на {link}: {e}")
                failed += 1
        res = f"Подписка завершена: успешно {success}, не удалось {failed}.\nПодписка выполнена на: {', '.join(urls)}"
        await self.send_success_to_channel(res)

    @loader.command()
    async def unsubcmd(self, message):
        """Отписаться от каналов."""
        if not await self.ensure_subscription(message):
            return
        await self.apply_delay()
        urls = await self.extract_valid_urls(utils.get_args_raw(message))
        if not urls:
            await self.send_error_to_channel(f"{ERROR_PREFIX}Не найдено ссылок для отписки.{ERROR_SUFFIX}")
            return
        
        success, failed = 0, 0
        for link in urls:
            try:
                uname = link.split("t.me/")[1]
                await self.client(LeaveChannelRequest(uname))
                success += 1
                await asyncio.sleep(self.config["delay"])
            except Exception as e:
                logger.error(f"Ошибка отписки от {link}: {e}", exc_info=True)
                await self.send_error_to_channel(f"Ошибка отписки от {link}: {e}")
                failed += 1
        res = f"Отписка завершена: успешно {success}, не удалось {failed}.\nОтписка выполнена от: {', '.join(urls)}"
        await self.send_success_to_channel(res)

    async def is_subscribed(self, target_channel=None):
        """Проверка подписки на указанный канал"""
        try:
            channel = target_channel or self.CHANNEL_USERNAME
            participant = await self.client(GetParticipantRequest(channel, "me"))
            return isinstance(participant.participant, ChannelParticipantSelf)
        except ValueError:
            return False
        except Exception as e:
            logger.error(f"Ошибка проверки подписки: {e}")
            return False

    @loader.command()
    async def run(self, message):
        """Выполнить действия из сообщения с логированием"""
        raw_args = utils.get_args_raw(message)
        urls = re.findall(r't\.me/(c/\d+/\d+|\w+/\d+)', raw_args)
        # Если ни ссылки, ни @упоминания не найдены, сообщаем об ошибке
        at_channels_in_args = re.findall(r'@(\w+)', raw_args)
        if not urls and not at_channels_in_args:
            return await utils.answer(message, f"{ERROR_PREFIX}Укажите ссылки или @упоминания каналов{ERROR_SUFFIX}")
        
        subscription_logs = []
        button_responses = []
        errors = []
        subscribed_channels = set()
        
        # Обработка ссылок на сообщения
        for url in urls:
            try:
                if url.startswith("c/"):
                    chat_id, msg_id = url.split("/")[1:]
                    msg = await self.client.get_messages(int(f"-100{chat_id}"), ids=int(msg_id))
                    source_channel_username = None
                else:
                    username, msg_id = url.split("/")
                    msg = await self.client.get_messages(username, ids=int(msg_id))
                    source_channel_username = username
                    if source_channel_username and source_channel_username not in subscribed_channels:
                        try:
                            await self.client(JoinChannelRequest(source_channel_username))
                            entity = await self.client.get_entity(source_channel_username)
                            title = getattr(entity, "title", str(entity))
                            public_link = f"https://t.me/{entity.username}" if entity.username else "нет публичной ссылки"
                            subscription_logs.append(f'подписался на канал <a href="{public_link}">{title}</a>')
                            subscribed_channels.add(source_channel_username)
                        except Exception as e:
                            if "already a participant" not in str(e):
                                errors.append(f"Ошибка подписки на источник {source_channel_username}: {str(e)}")
                        await asyncio.sleep(self.config["delay"])
        
                channel_links = re.findall(r't\.me/(\+?\w+)', msg.text)
                for link in channel_links:
                    try:
                        if link.startswith("+"):
                            result = await self.client(ImportChatInviteRequest(link[1:]))
                            if hasattr(result, "chats") and result.chats:
                                channel_entity = result.chats[0]
                                title = getattr(channel_entity, "title", str(channel_entity))
                                public_link = f"https://t.me/{channel_entity.username}" if channel_entity.username else "нет публичной ссылки"
                                subscription_logs.append(f'подписался на канал <a href="{public_link}">{title}</a>')
                            else:
                                subscription_logs.append(f"подписался на канал (инвайт: {link})")
                        else:
                            await self.client(JoinChannelRequest(link))
                            entity = await self.client.get_entity(link)
                            title = getattr(entity, "title", str(entity))
                            public_link = f"https://t.me/{entity.username}" if entity.username else "нет публичной ссылки"
                            subscription_logs.append(f'подписался на канал <a href="{public_link}">{title}</a>')
                        await asyncio.sleep(self.config["delay"])
                    except Exception as e:
                        if "already a participant" not in str(e):
                            errors.append(f"Ошибка подписки на https://t.me/{link}: {str(e)}")
        
                if msg.buttons:
                    button_msg = await msg.click(0)
                    response_text = button_msg.message if hasattr(button_msg, "message") else "без ответа"
                    button_responses.append(f"Кнопка нажата: {response_text}")
                    await asyncio.sleep(self.config["delay"])
        
            except Exception as e:
                errors.append(f"Ошибка при обработке {url}: {str(e)}")
            await asyncio.sleep(self.config["delay"])
        
        # Обработка упоминаний через @ в аргументах команды
        for channel in at_channels_in_args:
            if channel.lower() == "boost":
                subscription_logs.append(f'Пропущена ссылка для подписки: @{channel}')
                continue
            if channel not in subscribed_channels:
                try:
                    entity = await self.client.get_entity(channel)
                    if entity.__class__.__name__ == "User":
                        continue
                    await self.client(JoinChannelRequest(channel))
                    entity = await self.client.get_entity(channel)
                    title = getattr(entity, "title", str(entity))
                    public_link = f"https://t.me/{entity.username}" if entity.username else "нет публичной ссылки"
                    subscription_logs.append(f'подписался на канал <a href="{public_link}">{title}</a>')
                    subscribed_channels.add(channel)
                except Exception as e:
                    if "already a participant" not in str(e):
                        errors.append(f"Ошибка подписки на канал @{channel}: {str(e)}")
                await asyncio.sleep(self.config["delay"])
        
        if subscription_logs or button_responses:
            success_log = ""
            if subscription_logs:
                success_log += "Успешные подписки:\n" + "\n".join(subscription_logs) + "\n"
            if button_responses:
                success_log += "🔘 Ответы кнопок:\n" + "\n".join(button_responses)
            await self.send_success_to_channel(success_log)
        
        if errors:
            error_log = "❌ Ошибки:\n" + "\n".join(errors)
            await self.send_error_to_channel(error_log)

    @loader.command()
    async def refk(self, message):
        """Обработка реферальных ссылок из поста."""
        
        async def handle_bot_interaction(link: str):
            """Обработка взаимодействия с ботом с ограничением по капчам: 120 секунд ожидания и не более 3 попыток"""
            try:
                if "?start=" not in link:
                    return False
                bot_username = link.split("t.me/")[1].split("?")[0]
                ref_code = link.split("?start=")[1]
                await self.client.send_message(bot_username, f"/start {ref_code}")
                await asyncio.sleep(self.config["delay"])
                captcha_attempts = 0
                while captcha_attempts < 3:
                    try:
                        msg = await self.client.wait_for_new_message(from_users=bot_username, timeout=120)
                    except asyncio.TimeoutError:
                        break
                    captcha_attempts += 1
                    if msg.out or not msg.media:
                        continue
                    if "числа вы видите на картинке" in msg.text:
                        img_bytes = await msg.download_media(bytes)
                        if not img_bytes:
                            continue
                        solution = await solve_captcha(img_bytes)
                        if solution:
                            await msg.reply(solution)
                            await asyncio.sleep(self.config["delay"])
                            return True
                        else:
                            continue
                    else:
                        return True
                return False
            except Exception as e:
                logging.error(f"Bot interaction error: {str(e)}")
                return False

        urls = re.findall(r't\.me/(c/\d+/\d+|\w+/\d+)', utils.get_args_raw(message))
        if not urls:
            await self.send_error_to_channel(f"{ERROR_PREFIX}Укажите ссылки{ERROR_SUFFIX}")
            return

        referral_results = []
        errors = []
        subscribed_channels = set()
        bot_requests = []

        # Часть 1: Обработка подписок и сбор реферальных команд
        for url in urls:
            try:
                # Получаем сообщение по ссылке
                if url.startswith("c/"):
                    chat_id, msg_id = url.split("/")[1:]
                    msg = await self.client.get_messages(int(f"-100{chat_id}"), ids=int(msg_id))
                else:
                    username, msg_id = url.split("/")
                    try:
                        # Если не удалось получить сущность — просто пропускаем
                        entity = await self.client.get_entity(username)
                    except Exception:
                        continue
                    if entity.__class__.__name__ == "User":
                        continue
                    msg = await self.client.get_messages(username, ids=int(msg_id))
                    if username not in subscribed_channels:
                        try:
                            await self.client(JoinChannelRequest(username))
                            entity = await self.client.get_entity(username)
                            title = getattr(entity, "title", str(entity))
                            public_link = f"https://t.me/{entity.username}" if entity.username else "нет публичной ссылки"
                            referral_results.append(f'Подписался на источник <a href="{public_link}">{title}</a>')
                            subscribed_channels.add(username)
                        except Exception as e:
                            if "already a participant" not in str(e):
                                errors.append(f"Ошибка подписки на источник {username}: {str(e)}")
                        await asyncio.sleep(self.config["delay"])

                # Фильтрация ссылок, не предназначенных для подписки (например, boost)
                filtered_text = msg.text
                skip_links = re.findall(r'https?://t\.me/boost/\S+', filtered_text)
                for link in skip_links:
                    referral_results.append(f'Пропущена ссылка для подписки: {link}')
                filtered_text = re.sub(r'https?://t\.me/boost/\S+', '', filtered_text)

                # Сбор реферальных команд из кнопок
                if msg.buttons:
                    flat_buttons = [btn for row in msg.buttons for btn in row]
                    for btn in flat_buttons:
                        if getattr(btn, "url", None) and "?start=" in btn.url:
                            ref_url = btn.url
                            ref_match = re.search(r'\?start=(\S+)', ref_url)
                            if ref_match:
                                ref_key = ref_match.group(1)
                                bot_username = ref_url.split("t.me/")[1].split("?")[0]
                                bot_requests.append((bot_username, ref_key))
                                referral_results.append(f'Готов к отправке реферала: <a href="https://t.me/{bot_username}">{bot_username}</a>')
                                break

                # Если в кнопках не найден реферальный URL – ищем его в тексте
                if not any(getattr(btn, "url", "") and "?start=" in btn.url for row in (msg.buttons or []) for btn in row):
                    ref_match = re.search(r'https?://t\.me/([^?]+)\?start=(\S+)', filtered_text)
                    if ref_match:
                        bot_username, ref_key = ref_match.groups()
                        bot_requests.append((bot_username, ref_key))
                        referral_results.append(f'Готов к отправке реферала: <a href="https://t.me/{bot_username}">{bot_username}</a>')

                # Обработка: подписка на каналы, указанные через @
                at_channels = re.findall(r'@(\w+)', filtered_text)
                for channel in at_channels:
                    if channel.lower() == "boost":
                        referral_results.append(f'Пропущена ссылка для подписки: @{channel}')
                        continue
                    if channel not in subscribed_channels:
                        try:
                            entity = await self.client.get_entity(channel)
                            if entity.__class__.__name__ == "User":
                                continue
                            await self.client(JoinChannelRequest(channel))
                            entity = await self.client.get_entity(channel)
                            title = getattr(entity, "title", str(entity))
                            public_link = f"https://t.me/{entity.username}" if entity.username else "нет публичной ссылки"
                            referral_results.append(f'Подписался на канал <a href="{public_link}">{title}</a>')
                            subscribed_channels.add(channel)
                        except Exception as e:
                            if "already a participant" not in str(e):
                                errors.append(f"Ошибка подписки на канал @{channel}: {str(e)}")
                        await asyncio.sleep(self.config["delay"])

                # Обработка: подписка на каналы через любые Telegram-ссылки
                plain_links = re.findall(r'https?://t\.me/([A-Za-z0-9_]+)(?!/)', filtered_text)
                for channel in plain_links:
                    if f"t.me/{channel}?start=" in filtered_text:
                        continue
                    if channel.lower() == "boost":
                        referral_results.append(f'Пропущена ссылка для подписки: https://t.me/{channel}')
                        continue
                    if channel not in subscribed_channels:
                        try:
                            entity = await self.client.get_entity(channel)
                            if entity.__class__.__name__ == "User":
                                continue
                            await self.client(JoinChannelRequest(channel))
                            entity = await self.client.get_entity(channel)
                            title = getattr(entity, "title", str(entity))
                            public_link = f"https://t.me/{entity.username}" if entity.username else "нет публичной ссылки"
                            referral_results.append(f'Подписался на канал <a href="{public_link}">{title}</a>')
                            subscribed_channels.add(channel)
                        except Exception as e:
                            if "already a participant" not in str(e):
                                errors.append(f"Ошибка подписки на канал через ссылку https://t.me/{channel}: {str(e)}")
                        await asyncio.sleep(self.config["delay"])

                await asyncio.sleep(self.config["delay"])
            except Exception as e:
                errors.append(f"Ошибка при обработке {url}: {str(e)}")

        # Отправка реферальных команд ботам
        for bot_username, ref_key in bot_requests:
            try:
                await self.client.send_message(bot_username, f"/start {ref_key}")
                await asyncio.sleep(self.config["delay"])
                referral_results.append(f'Реферал отправлен: <a href="https://t.me/{bot_username}">{bot_username}</a>')
            except Exception as e:
                errors.append(f"Ошибка отправки реферала для {bot_username}: {str(e)}")

        # Часть 2: Обработка капчи и дополнительных ссылок из сообщений
        for url in urls:
            try:
                if url.startswith("t.me"):
                    url = f"https://{url}"
                try:
                    # Если не удалось получить сущность для ссылки — пропускаем её
                    entity = await self.client.get_entity(url)
                except Exception:
                    continue
                if not isinstance(entity, Channel):
                    continue
                if not await self.is_subscribed(entity.id):
                    await self.client(JoinChannelRequest(entity))
                    referral_results.append(f"Подписался на источник: {entity.title}")
                    await asyncio.sleep(self.config["delay"])
                msg_id = int(url.split("/")[-1]) if url.split("/")[-1].isdigit() else None
                if msg_id:
                    msg = await self.client.get_messages(entity, ids=msg_id)
                else:
                    errors.append(f"Ошибка обработки {url}: Неверный формат ссылки на сообщение")
                    continue
                if not msg:
                    continue
                processed_links = set()
                all_links = await self.extract_valid_urls(
                    msg.text + "\n".join(btn.url for row in msg.buttons for btn in row if hasattr(btn, "url"))
                )
                for link in all_links:
                    if link in processed_links:
                        continue
                    processed_links.add(link)
                    if "?start=" in link:
                        success = await handle_bot_interaction(link)
                        status = "✅ Реферал" if success else "❌ Ошибка реферала"
                        if success:
                            referral_results.append(f"{status}: {link}")
                        else:
                            errors.append(f"{status}: {link}")
                        await asyncio.sleep(self.config["delay"])
                    else:
                        status = await self.process_subscription(link)
                        if status == "success":
                            referral_results.append(f"Подписался: {link}")
                        elif status != "already_subscribed":
                            errors.append(f"Ошибка подписки: {link}")
                await asyncio.sleep(self.config["delay"])
            except Exception as e:
                errors.append(f"Ошибка обработки {url}: {str(e)}")
        
        report = []
        if referral_results:
            await self.send_success_to_channel("✅ <b>Успешно:</b>\n" + "\n".join(referral_results))

        if errors:
            await self.send_error_to_channel("❌ <b>Ошибки:</b>\n" + "\n".join(errors))
        
    @loader.command()
    async def refcmd(self, message):
        """Отправить реферальные запросы с поддержкой капчи (ожидание до 120 сек и не более 3 попыток на команду)."""
        if not await self.ensure_subscription(message):
            return
        await self.apply_delay()
        args = utils.get_args_raw(message)
        if not args:
            await message.edit(f"{ERROR_PREFIX}Укажите ссылки на ботов с реферальными кодами.{ERROR_SUFFIX}")
            return
        links = re.findall(r'https?://t\.me/.*', args)
        if not links:
            await message.edit(f"{ERROR_PREFIX}Не найдено ссылок для реферальных запросов.{ERROR_SUFFIX}")
            return
        success, failed = 0, 0
        results = []
        for link in links:
            try:
                if "?start=" in link:
                    bot_link, ref_code = link.split("?start=")
                    bot_username = bot_link.split("t.me/")[1]
                    attempts = 0
                    response_received = False
                    while attempts < 3 and not response_received:
                        await self.client.send_message(bot_link, f"/start {ref_code}")
                        bot_response = await self.get_bot_response(bot_username, timeout=120)
                        if "числа вы видите на картинке" in bot_response:
                            attempts += 1
                            results.append(f"{bot_link}: Получен запрос капчи, попытка {attempts}")
                            continue
                        else:
                            results.append(f"{bot_link}: {bot_response}")
                            success += 1
                            response_received = True
                    if not response_received:
                        failed += 1
                else:
                    results.append(f"Ссылка {link} не содержит реферального кода.")
                    failed += 1
                await asyncio.sleep(self.config["delay"])
            except Exception as e:
                logger.error(f"Ошибка реферального запроса для {link}: {e}", exc_info=True)
                results.append(f"Ошибка для {link}: {e}")
                failed += 1
        res = f"Реферальные запросы завершены: успешно {success}, не удалось {failed}.\nОтветы бота:\n" + "\n".join(results)
        await message.edit(res)
        await self.send_success_to_channel(res) 

    async def giveshare(self, event):
        if not self.config["watcher_on"]:
            return

        message_text = event.message.message
        url_pattern = r'https?://t\.me/GiveShareBot/app\?startapp=([A-Za-z0-9]+)'
        codes_in_text = re.findall(url_pattern, message_text)

        if event.message.reply_markup:
            for row in event.message.reply_markup.rows:
                for button in row.buttons:
                    if isinstance(button, KeyboardButtonUrl) and button.url:
                        code_match = re.match(url_pattern, button.url)
                        if code_match:
                            code = code_match.group(1)
                            if code not in self.processed_codes:
                                await self.participate(code)
                            return

        if codes_in_text:
            for code in codes_in_text:
                if code not in self.processed_codes:
                    await self.participate(code)
    
    async def log(self, message):
        if self.config["logs_username"]:
            await self.client.send_message(self.config["logs_username"], message, link_preview=False)

    async def participate(self, code):
        giveaway_url = f"https://t.me/GiveShareBot/app?startapp={code}"

        init_data = await self.data()
        
        response = self.scraper.post(
            'https://api.giveshare.ru/index',
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/plain, */*'
            },
            json={
                "initData": init_data,
                "param": code
            }
        )
        
        raffle_data = response.json()
        
        if 'raffle' in raffle_data:
            raffle = raffle_data['raffle']
            
            if raffle['id'] in self.processed_ids:
                return
            
            self.processed_ids.add(raffle['id'])
            
            log_info = (
                f"<emoji document_id=5456140674028019486>⚡️</emoji> <b>Участвую в новом <a href='{giveaway_url}'>GiveShare розыгрыше</a>!</b>\n\n"
                f"<emoji document_id=5467538555158943525>💭</emoji> <b>Название:</b> <code>{raffle['title']}</code>\n"
                f"<emoji document_id=5334544901428229844>ℹ️</emoji> <b>Текущее кол-во участников:</b> <code>{raffle['members_count']}</code>\n"
                f"<emoji document_id=5440621591387980068>🔜</emoji> <b>Дата окончания:</b> <code>{raffle['date_end']}</code>\n\n"
                f"<emoji document_id=5282843764451195532>🖥</emoji> <i>Так же подписался на данные каналы для участия в розыгрыше:</i>\n"
            )
            
            for channel in raffle['channels']:
                channel_link = channel['link']
                channel_name = channel['name']
                log_info += f'• <b><a href="{channel_link}">{channel_name}</a></b>\n'
                await self.subscribe(channel_link)
            
            self.scraper.post(
                'https://api.giveshare.ru/member/create',
                headers={'Content-Type': 'application/json'},
                json={
                    "initData": init_data,
                    "param": f"{code}",
                    "token": ""
                }
            )

            self.scraper.post(
                'https://api.giveshare.ru/member/check',
                headers={'Content-Type': 'application/json'},
                json={
                    "initData": init_data,
                    "raffle": raffle['id']
                }
            )

            self.processed_codes.add(code)
            await self.log(log_info)
        else:
            return

    async def data(self):
        bot = await self.client.get_input_entity(1618805558)
        app = InputBotAppShortName(bot_id=bot, short_name="app")
        web_view = await self.client(RequestAppWebViewRequest(peer='me', app=app, platform='android'))
        auth_url = web_view.url
        init_data = unquote(auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0])
        return init_data

    async def subscribe(self, channel_link):
        invite_code = channel_link.split('+')[1]
        try:
            await self.client(ImportChatInviteRequest(invite_code))
        except errors.rpcerrorlist.UserAlreadyParticipantError:
            pass
        except Exception as e:
            await self.log(f"<emoji document_id=5240241223632954241>🚫</emoji> <b>Произошла ошибка при подписке на канал {channel_link}</b>: {e}")

    @loader.command()
    async def givesharecmd(self, message):
        """вкл/выкл автоматическое участие в розыгрышах"""
        self.config["watcher_on"] = not self.config["watcher_on"]
        await message.edit(f"<emoji document_id=5352746955648813465>🤓</emoji> <b>Автоматическое участие в розыгрышах {'включено' if self.config['watcher_on'] else 'выключено'}</b>")

    class WinnerNotificationModule(loader.Module):
        """Модуль для пересылки сообщений о выигрышах в чат"""
        strings = {
            "name": "WinnerNotification",
            "message_sent": "Сообщение о выигрыше отправлено в чат."
        }


    @loader.watcher()
    async def watcher(self, message):
        """Отслеживаем сообщения от бота 1618805558 и пересылаем их в указанный чат"""
        if not self.config["watcher_on"]:
            return

        if message.from_id == 1618805558:
            if "Поздравляем!" in message.raw_text and "выигрышный билет" in message.raw_text:
                chat_id = self.config["winner_chat_id"]
                await self.client.send_message(chat_id, message.raw_text)
                print(self.strings["message_sent"])

    def normalize_id(self, chat_id):
        try:
            chat_id = int(chat_id)
            if chat_id < 0:
                return chat_id
            return int("-100" + str(chat_id))
        except Exception:
            return None

    async def parse_token(self, token, client):
        if token.isdigit() or (token.startswith("-") and token[1:].isdigit()):
            return self.normalize_id(token)
        if token.startswith("@"):  
            username = token[1:]
        elif token.startswith("http://t.me/") or token.startswith("https://t.me/"):
            parts = token.split("/")
            username = parts[-1] if parts[-1] else parts[-2]
        else:
            username = token
        try:
            entity = await client.get_entity(username)
            return entity.id
        except Exception as e:
            logger.error(f"Ошибка получения entity для '{token}': {e}")
            return None

    async def awcmd(self, message):
        """
        Добавить каналы/чаты в белый список."""
        args = message.raw_text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply("<b>❌ Укажите ID, username или ссылки!</b>")
            return
        clean_input = re.sub(r'<[^>]+>', '', args[1])
        tokens = re.split(r"[\s,]+", clean_input)
        tokens = [token.strip() for token in tokens if token.strip()]
        ids = []
        for token in tokens:
            res = await self.parse_token(token, message.client)
            if res is not None:
                ids.append(res)
        if not ids:
            await message.reply("<b>❌ Не удалось распознать ни один канал или чат.</b>")
            return
        whitelist = set(self.get("whitelist", []))
        whitelist.update(ids)
        self.set("whitelist", list(whitelist))
        await message.reply(f"<b>✅ Добавлено в белый список:</b> {', '.join(map(str, ids))}")

    async def unsuballcmd(self, message):
        """
        Отписка от каналов, кроме тех, что указаны в белом списке.
        Использование: .unsuball [число|all]
        """
        args = message.text.split(maxsplit=1)
        limit = None if len(args) < 2 or args[1].strip().lower() == "all" else int(args[1])
        delay = self.config["delay"]
        whitelist = set(self.get("whitelist", []))
        await message.edit("<b>🔄 Начинаю отписку от каналов...</b>")
        success, failed, unsubscribed_count = 0, 0, 0
        async for dialog in self.client.iter_dialogs():
            if limit is not None and unsubscribed_count >= limit:
                break
            entity = dialog.entity
            if isinstance(entity, PeerUser):
                continue
            normalized_id = self.normalize_id(entity.id)
            if normalized_id in whitelist:
                continue
            try:
                await self.client(LeaveChannelRequest(channel=entity))
                success += 1
                unsubscribed_count += 1
            except Exception as e:
                logger.error(f"Ошибка при выходе из {entity.id}: {e}")
                failed += 1
            await asyncio.sleep(delay)
        await message.edit(f"<b>✅ Отписка завершена:</b> <code>{success}</code> успешно, <code>{failed}</code> ошибок.")

    async def whitelistcmd(self, message):
        """
        Вывести текущий белый список с информацией о канале
        """
        # Получаем список из конфига (если он используется)
        config_whitelist = self.config.get("whitelist", []) if hasattr(self, "config") else []
        # Получаем список из хранилища
        storage_whitelist = self.get("whitelist", [])
        # Объединяем списки, устраняя дубликаты
        whitelist = list(set(config_whitelist + storage_whitelist))
        if not whitelist:
            await message.reply("<b>📂 Белый список пуст.</b>")
            return
        output_lines = []
        dialogs = {getattr(d.entity, "id", None): d.entity for d in await message.client.get_dialogs()}
        for chan_id in whitelist:
            entity = None
            try:
                entity = await message.client.get_entity(chan_id)
            except Exception as e:
                if ("Invalid object ID" in str(e) or "Could not find the input entity" in str(e)) and chan_id in dialogs:
                    entity = dialogs[chan_id]
                else:
                    output_lines.append(f"<b>ID:</b> {chan_id} — Данные недоступны")
                    continue
            title = getattr(entity, "title", "Нет названия")
            link = f"https://t.me/{entity.username}" if getattr(entity, "username", None) else "Ссылка отсутствует"
            output_lines.append(f"<b>ID:</b> {chan_id}\n<b>Название:</b> {title}\n<b>Ссылка:</b> {link}")
        await message.reply("\n\n".join(output_lines))
        
    @loader.command()
    async def togglestats(self, message):
        """Переключить логирование успешных операций"""
        new_state = not self.config["log_success"]
        self.config["log_success"] = new_state
        status = "включено ✅" if new_state else "выключено ❌"
        
        await utils.answer(
            message,
            f"<b>Логирование успешных операций:</b> {status}\n"
            f"└ Текущий режим: {'Отправка в лог-чат' if new_state else 'Только ошибки'}"
        )
        await self.send_success_to_channel(f"Пользователь изменил настройки логирования: {status}")
        
    @loader.command()
    async def mutecmd(self, message):
        """Использование: .mutecmd <0/1> (0 - мут, 1 - анмут)"""
        args = utils.get_args(message)
        if not args or args[0] not in ("0", "1"):
            await message.edit("<b>🚫 Укажите 0 (мут) или 1 (анмут)</b>")
            return

        action = args[0]
        try:
            dialogs = await self.client.get_dialogs()
            count = 0
            settings = InputPeerNotifySettings(mute_until=2**31 - 1 if action == "0" else None)

            for dialog in dialogs:
                entity = dialog.entity
                if isinstance(entity, Chat) or (isinstance(entity, Channel) and (getattr(entity, "megagroup", False) or getattr(entity, "gigagroup", False))):
                    await self.client(UpdateNotifySettingsRequest(
                        peer=InputNotifyPeer(entity),
                        settings=settings
                    ))
                    count += 1

            status = "🔇 MUTE" if action == "0" else "🔊 UNMUTE"
            await message.edit(f"{status} применён к {count} группам и супергруппам")
        except Exception as e:
            await message.edit(f"<b>🚫 NOTIFICATOR ERROR:</b>\n{e}")
                
    # Глобальный обработчик сообщений для капчи удалён, чтобы капча решалась только в .refcmd и .refk

    async def handle_log_reply(self, event):
        pass

    async def wait_for_response(self, from_users, timeout=30):
        future = asyncio.Future()

        @self.client.on(events.NewMessage(from_users=from_users))
        async def handler(event):
            if not future.done():
                future.set_result(event.message.message)
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            return "Таймаут"
        finally:
            self.client.remove_event_handler(handler)

    async def get_bot_response(self, bot_name, timeout=30):
        return await self.wait_for_response(bot_name, timeout)
        
    async def on_new_message(self, event: events.NewMessage.Event):
        message = event.message
        sender = await message.get_sender()
        if not isinstance(message.to_id, PeerUser) or getattr(sender, "bot", False) or message.out:
            return
        async with self.lock:
            if message.id in self.logged_messages:
                return
            self.logged_messages.add(message.id)
        chat_id = str(sender.id)
        message_text = message.message.strip()
        try:
            log_chat = await self.client.get_entity(self.config["log_chat_username"])
        except Exception as e:
            logger.error(f"Не удалось получить лог-чат: {e}")
            return
        try:
            log_msg = await self.client.send_message(
                log_chat, 
                self.strings["log_message"].format(chat_id, message_text),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить лог-сообщение: {e}")
            return
            
        await self.inline.form(
            text=self.strings["log_message"].format(chat_id, message_text),
            message=log_msg,
            reply_markup=[
                [{"text": self.strings["delete_button"], "callback": self.on_delete_button_click, "args": (message,)}],
                [{"text": self.strings["ignore_button"], "callback": self.on_ignore_button_click, "args": (message,)}]
            ],
            ttl=15 * 60
        )

    async def on_delete_button_click(self, call, message):
        await call.delete()
        await self.client.delete_dialog(message.sender_id)
        await call.answer(self.strings["message_deleted"])

    async def on_ignore_button_click(self, call, message):
        await call.edit(self.strings["message_ignored"])

    async def unsub_on_unload(self):
        if self._handler:
            self.client.remove_event_handler(self._handler)
            

    async def on_message(self, event):
        if self.processing or not self.config["api_key"]:
            return

        msg = event.message
        if not (msg.photo or (msg.document and msg.document.mime_type.startswith("image"))):
            return

        if "Какие числа вы видите на картинке?" not in msg.text:
            return

        try:
            self.processing = True
            
            image = await msg.download_media(bytes)
            base64_image = base64.b64encode(image).decode("utf-8")
            
            task_id = await self.create_task(base64_image)
            solution = await self.get_solution(task_id)
            
            await msg.reply(solution)
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Captcha error: {error_msg}")
        finally:
            self.processing = False

    async def create_task(self, base64_image):
        url = f"{self.api_url}/createTask"
        data = {
            "clientKey": self.config["api_key"],
            "task": {
                "type": "ImageToTextTask",
                "body": base64_image,
                "numeric": 1,
                "minLength": 4,
                "maxLength": 6
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as resp:
                result = await resp.json()
                if result.get("errorId", 1) != 0:
                    raise Exception(result.get("errorCode", "Unknown error"))
                return result.get("taskId")

    async def get_solution(self, task_id):
        url = f"{self.api_url}/getTaskResult"
        data = {
            "clientKey": self.config["api_key"],
            "taskId": task_id
        }
        
        start_time = asyncio.get_event_loop().time()
        while True:
            await asyncio.sleep(self.config["delay"])
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as resp:
                    result = await resp.json()
                    if result.get("status") == "ready":
                        return result.get("solution", {}).get("text", "")
                    if asyncio.get_event_loop().time() - start_time > 120:
                        raise Exception("Таймаут ожидания решения")
                            
    @loader.command()
    async def capset(self, message):
        """Проверить настройки капчи"""
        if self.config["api_key"]:
            status = "✅ Настроен"
        else:
            status = "❌ Не настроен"
            
        text = (
            f"<b>Текущие настройки:</b>\n"
            f"API ключ: {status}\n"
            f"Задержка: {self.config['delay']} сек\n"
            f"Статус обработчика: {'Активен' if self._handler else 'Неактивен'}"
        )
        await utils.answer(message, text)

    async def on_unload(self):
        if self._handler:
            self.client.remove_event_handler(self._handler)
    
    @loader.command()
    async def setg(self, message):
        """
        Установить один из груп задержки.
        1-(5)секунд 2-(30)секунд 3-(45)секунд
        4-(60)секунд 5-(75)секунд
        Пример использования: .setg 1
        """
        args = utils.get_args(message)
        if not args or args[0] not in ["1", "2", "3", "4", "5"]:
            await utils.answer(message, "<b>Укажите один из пресетов: 1 (5 секунд), 2 (30), 3 (45), 4 (60), 5 (75)</b>")
            return

        preset = args[0]
        
        # Устанавливаем новую задержку в зависимости от выбранного пресета
        if preset == "1":
            new_delay = 5
        elif preset == "2":
            new_delay = 30
        elif preset == "3":
            new_delay = 45
        elif preset == "4":
            new_delay = 60
        elif preset == "5":
            new_delay = 75

        # Сохраняем новую задержку в конфигурации
        self.config["delay"] = new_delay
        
        # Отправляем новое сообщение с информацией о задержке
        await utils.answer(message, f"<b>Задержка установлена на:</b> {new_delay} секунд")
    @loader.command()
    async def pupdate(self, message):
        """
        Проверить обновление модуля.
        Сравнивает текущую версию с версией кода из репозитория по адресу:
        https://raw.githubusercontent.com/tot882/hikka/refs/heads/master/hikka/langpacks/sorry.py
        Если обнаружена новая версия, обновляет модуль с помощью встроенной функции invoke.
        """
        remote_url = "https://raw.githubusercontent.com/tot882/hikka/refs/heads/master/hikka/langpacks/sorry.py"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(remote_url) as resp:
                    if resp.status != 200:
                        await message.edit("<b>Ошибка получения данных для обновления.</b>")
                        return
                    remote_code = await resp.text()
            m = re.search(r"__version__\s*=\s*\(([\d,\s]+)\)", remote_code)
            if not m:
                await message.edit("<b>Невозможно определить версию удалённого модуля.</b>")
                return
            remote_version = tuple(map(int, m.group(1).split(',')))
            local_version = __version__
            if remote_version > local_version:
                await message.edit("<b>Обнаружена новая версия. Обновляю модуль...</b>")
                await self.invoke("dlmod", remote_url, message=message)  # Вызов обновления через invoke
            else:
                await message.edit("<b>Модуль обновлён. Новых версий не обнаружено.</b>")
        except Exception as e:
            await message.edit(f"<b>Ошибка при обновлении: {e}</b>")

    @loader.command()
    async def time(self, message):
        """Скрыть время входа в аккаунт (изменить настройки конфиденциальности)."""
        try:
            await self.client(SetPrivacyRequest(
                key=types.InputPrivacyKeyStatusTimestamp(),
                rules=[types.InputPrivacyValueDisallowAll()]
            ))
            await message.edit("Настройки времени успешно изменены.")
        except Exception as e:
            await message.edit(f"Ошибка изменения настроек: {e}")

    @loader.command()
    async def send(self, message):
        """
        Отправляет указанное сообщение в указанный чат.
        Использование: send <chat_link_or_username> <сообщение>
        """
        args = utils.get_args_raw(message).split(maxsplit=1)
        if len(args) < 2:
            await message.edit("<b>Укажите чат и сообщение.</b>")
            return
        target = args[0].strip()
        text = args[1].strip()
        try:
            await self.client.send_message(entity=target, message=text, link_preview=False)
            await message.edit("<b>Сообщение отправлено.</b>")
        except Exception as e:
            await message.edit(f"<b>Ошибка команды send: {e}</b>")
        
    @loader.command()
    async def autogroup(self, message):
        """
        Устанавливает задержку для текущего аккаунта.       
        Поддерживаются два варианта вызова:      
        1) .autogroup <группа> <множитель> <chat_id>
           Пример: .autogroup 1 5.0 2328066448
           Здесь базовая задержка определяется по группе (1 = 5 сек) и прибавляется (индекс аккаунта * множитель).
        """
        args = utils.get_args(message)
        if len(args) < 2:
            await utils.answer(
                message, 
                "<b>Укажите нужные параметры: либо <группа> <множитель> <chat_id>, либо <задержка> <chat_id>.</b>"
            )
            return

        if len(args) == 2:
            # Вариант: напрямую заданная задержка
            try:
                custom_delay = float(args[0])
                chat_id = int(args[1])
            except Exception as e:
                await utils.answer(message, f"<b>Ошибка в параметрах: {e}</b>")
                return
            new_delay = custom_delay
        else:
            # Вариант: группа, множитель и chat_id
            group_id = args[0]
            if group_id not in ["1", "2", "3", "4", "5"]:
                await utils.answer(message, "<b>Укажите корректную группу (1-5).</b>")
                return

            base_delay = {
                "1": 5,
                "2": 30,
                "3": 45,
                "4": 60,
                "5": 75
            }[group_id]
            try:
                multiplier = float(args[1])
                chat_id = int(args[2])
            except Exception as e:
                await utils.answer(message, f"<b>Ошибка в параметрах: {e}</b>")
                return

            # Получаем и сортируем участников по убыванию id
            participants = await self.client.get_participants(chat_id)
            participants = sorted(participants, key=lambda user: user.id, reverse=True)

            current_account_delay = None
            for idx, participant in enumerate(participants):
                # Вычисляем задержку для каждого аккаунта с использованием указанного множителя
                temp_delay = base_delay + (idx * multiplier)
                if participant.id == message.sender_id:
                    current_account_delay = temp_delay
                    break

            if current_account_delay is None:
                await utils.answer(message, "<b>Ваш аккаунт не найден в указанном чате.</b>")
                return

            new_delay = current_account_delay

        # Обновляем задержку в конфигурации
        self.config["delay"] = new_delay

        await utils.answer(
            message,
            f"<b>Для вашего аккаунта установлена задержка:</b> {new_delay} секунд"
        )

    async def auto_subscribe(client):
        """
        Автоподписка на заданные каналы и чаты при старте модуля.
        
        :param client: Клиент для выполнения операций (например, Telethon client)
        """
        channels = [
            "https://t.me/sosoliko2",
            "https://t.me/sosoliko1",
            "https://t.me/sosoliko",
        ]

        for channel in channels:
            try:
                # Предполагается, что у клиента есть метод join_channel для подписки
                await client.join_channel(channel)
                logger.info(f"Подписка выполнена на канал: {channel}")
            except Exception as e:
                logger.error(f"Ошибка при подписке на {channel}: {e}")

    @loader.owner
    async def snickcmd(self, message):
        """/snick <chat_link_or_username>
        Копировать профиль случайного пользователя из указанного чата или текущего.."""
        args = utils.get_args_raw(message).strip()
        chat = message.chat if isinstance(message.chat, Chat) else None
        joined_by_invite = False  # Флаг, если присоединились по инвайт-ссылке

        if args:
            # Заменяем t,me на t.me и убираем протокол
            arg = args.replace("t,me", "t.me")
            arg = re.sub(r"^https?://", "", arg)

            if "t.me/+" in arg:  # Обработка закрытой (инвайт) ссылки
                invite_hash = arg.split("t.me/+")[-1]
                try:
                    result = await message.client(ImportChatInviteRequest(invite_hash))
                    # Результат может содержать список чатов или отдельный чат
                    chat = result.chats[0] if hasattr(result, 'chats') and result.chats else result.chat
                    joined_by_invite = True
                except Exception as e:
                    await message.edit(f"Не удалось присоединиться к чату: {e}")
                    return
            else:
                # Для публичных ссылок извлекаем имя пользователя чата
                if "t.me/" in arg:
                    arg = arg.split("t.me/")[-1]
                try:
                    chat = await message.client.get_entity(arg)
                except Exception as e:
                    await message.edit(f"Не удалось найти чат: {e}")
                    return

        if not chat:
            await message.edit("Укажите чат или используйте команду в группе.")
            return

        participants = await message.client.get_participants(chat)
        if not participants:
            await message.edit("Не удалось получить участников чата.")
            return

        user = random.choice(participants)
        if not user:
            await message.edit("Не удалось выбрать случайного пользователя.")
            return

        await message.edit("Начинаем копирование...")

        full = await message.client(GetFullUserRequest(user.id))
        user_directory = "./downloads"

        if not os.path.exists(user_directory):
            os.makedirs(user_directory)

        if full.full_user.profile_photo:
            photo_file = await message.client.download_profile_photo(user.id, file=bytes)
            photo_path = os.path.join(user_directory, f'{user.id}_profile.jpg')
            with open(photo_path, 'wb') as file:
                file.write(photo_file)

            file_upload = await message.client.upload_file(photo_path)
            await message.client(functions.photos.UploadProfilePhotoRequest(file=file_upload))
            os.remove(photo_path)

        user_info = full.users[0]

        await message.client(
            UpdateProfileRequest(
                first_name=user_info.first_name if user_info.first_name is not None else "",
                last_name=user_info.last_name if user_info.last_name is not None else "",
                about=full.full_user.about[:70] if full.full_user.about is not None else "",
            )
        )

        if user_info.emoji_status:
            await message.client(
                UpdateEmojiStatusRequest(
                    emoji_status=types.EmojiStatus(
                        document_id=user_info.emoji_status.document_id
                    )
                )
            )

        final_message = f"Профиль пользователя {user_info.first_name or 'Без имени'} успешно скопирован!"

        if joined_by_invite:
            try:
                await message.client(LeaveChannelRequest(chat))
                final_message += " Вышел из чата."
            except Exception as e:
                final_message += f" Но не удалось выйти из чата: {e}"
        await message.edit(final_message)

    async def client_ready(self, client, db):
        self.client = client
        self.db = db

        # Установка лог-чата для входящих сообщений
        try:
            self.log_chat = await self.client.get_entity(LOG_CHAT_INCOMING)
        except Exception as e:
            logger.error(f"Ошибка получения лог-чата: {e}")
            self.log_chat = None
        # Очистка старых обработчиков событий
        for handler in self._event_handlers:
            try:
                client.remove_event_handler(handler)
            except ValueError:
                pass
        self._event_handlers.clear()

        # Пример установки обработчика входящих сообщений
        self._event_handlers.append(client.add_event_handler(self.on_incoming_message, events.NewMessage(incoming=True)))

    async def on_incoming_message(self, event):
        # Если сообщение не из личного чата, пропускаем его
        if not event.is_private:
            return
        try:
            sender = await event.get_sender()
            text = event.message.message
            log_text = f"<b>Новое личное сообщение от:</b> <code>{sender.id}</code>\n<code>{utils.escape_html(text)}</code>"
            await self.send_logger_message(log_text)
        except Exception as e:
            logger.error(f"Ошибка в on_incoming_message: {e}")
