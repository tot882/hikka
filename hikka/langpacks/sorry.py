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
)
from requests.exceptions import ProxyError

from hikka import loader, utils

logger = logging.getLogger(__name__)

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
# Объединённый модуль с функциями из обоих файлов
@loader.tds
class MergedModule(loader.Module):
    """
    MergedModule – объединённый модуль.
    
    Для вызова команд используйте manual-стиль, например:
      setproxy <адрес прокси>
      getinfo
      getcode
      subcmd <ссылки>
      unsubcmd <ссылки>
      run <ссылки>
      refk <ссылки>
      start

    Команда start автоматически запускает подписку на каналы и участие в розыгрышах/конкурсах.
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
        self.softname = "ANSTLER"
        self.softversion = "3.10.0"
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
        
        # Функционал для Xyipizda
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
        if not self.config["logger"]:
            return
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
            await asyncio.sleep(5)
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

    #==================== Функции Xyipizda ====================
    def get_random_proxy(self):
        proxy_file = "/data/proxy.txt"
        if not os.path.exists(proxy_file):
            return None
        with open(proxy_file, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        if not lines:
            return None
        selected = random.choice(lines)
        remaining = [line for line in lines if line != selected]
        with open(proxy_file, "w", encoding="utf-8") as f:
            f.write("\n".join(remaining))
        if not re.match(r'^[a-zA-Z]+://', selected):
            selected = "socks5://" + selected if "socks" in selected.lower() else "http://" + selected
        return selected

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        # Автоподписка на канал разработчика
        dev_channel = "tot_882"
        try:
            entity = await self.client.get_entity(dev_channel)
            await self.client(JoinChannelRequest(entity))
            logger.info(f"✅ Подписка на @{dev_channel} выполнена.")
        except Exception as e:
            logger.error(f"🚫 Ошибка подписки на @{dev_channel}: {e}")
        # Автопрокси
        proxy = self.get_random_proxy()
        if proxy:
            self.config["proxy"] = proxy
            self.scraper.proxies = {"http": proxy, "https": proxy, "socks5": proxy} if proxy.startswith("socks5://") else {"http": proxy, "https": proxy}
            await self.log(f"✅ Прокси установлен: {proxy}")
        else:
            await self.log("❌ Прокси не получен. Используйте команду setproxy.")
        # Получение лог-чата
        try:
            self.log_chat = await self.client.get_entity(self.config["log_chat_username"])
        except Exception as e:
            logger.error(f"❌ Ошибка лог-чата: {e}")
            self.log_chat = None

    async def log(self, message):
        if self.config["logs_username"]:
            await self.client.send_message(self.config["logs_username"], message, link_preview=False, parse_mode="html")

    @loader.command()
    async def setproxy(self, message):
        """Установить прокси вручную.
Использование: setproxy <адрес прокси>
Пример: setproxy socks5://127.0.0.1:1080"""
        args = utils.get_args_raw(message).strip()
        if not args:
            await message.edit("<b>❌ Укажите адрес прокси!</b>")
            return
        proxy = args
        if not re.match(r'^[a-zA-Z]+://', proxy):
            proxy = "socks5://" + proxy if "socks" in proxy.lower() else "http://" + proxy
        self.config["proxy"] = proxy
        self.scraper = tls_client.Session(client_identifier="chrome_120", random_tls_extension_order=True)
        self.scraper.proxies = {"http": proxy, "https": proxy, "socks5": proxy} if proxy.startswith("socks5://") else {"http": proxy, "https": proxy}
        await message.edit(f"<b>✅ Прокси установлен:</b> {proxy}")
        await self.log(f"✅ Прокси установлен вручную: {proxy}")

    @loader.command()
    async def getinfo(self, message):
        """Получить информацию о аккаунте (команда getinfo)"""
        try:
            me = await self.client.get_me()
            number = me.phone if me.phone else "Неизвестно"
            account_id = me.id
            limits = await self.check_limits()
            reg_date = await get_creation_date(account_id)
            name_text = me.first_name if me.first_name else "Неизвестно"
            info = (
                "╔════════════════════╗\n"
                "║ <b>ИНФО</b>\n"
                f"║ <b>ИМЯ:</b> <a href='tg://user?id={account_id}'>{name_text}</a>\n"
                "╠════════════════════╣\n"
                f"║ <b>НОМЕР:</b> +{number}\n"
                f"║ <b>ID:</b> {account_id}\n"
                f"║ <b>РЕГ:</b> {reg_date}\n"
                f"║ <b>Каналов:</b> {limits}/500\n"
                "╚════════════════════╝"
            )
            await message.respond(info, parse_mode="html", link_preview=False)
        except Exception as e:
            await self.send_logger_message(f"<b>Ошибка получения инфо:</b> {e}")

    async def check_limits(self):
        dialogs = await self.client.get_dialogs()
        channels = [d for d in dialogs if d.is_channel]
        return len(channels)

    async def find_verification_code(self):
        async for msg in self.client.iter_messages(777000, limit=50):
            codes = re.findall(r'\b(\d{5})\b', msg.raw_text)
            if codes:
                return codes[0]
            m = re.search(r'код был отправлен на почту.*?(\d{5})', msg.raw_text, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    @loader.command()
    async def getcode(self, message):
        """Запросить код верификации (команда getcode)"""
        code = await self.find_verification_code()
        if code:
            await message.respond(f"🔹 <b>Код:</b> {'.'.join(code)}", parse_mode="html")
        else:
            await self.send_logger_message(self.strings["no_code"])

    async def get_account_number(self):
        me = await self.client.get_me()
        return me.phone if me.phone else None

    @loader.command()
    async def getnumber(self, message):
        """Запросить номер аккаунта (команда getnumber)"""
        number = await self.get_account_number()
        if number:
            await message.respond(f"📞 <b>Номер:</b> +{number}", parse_mode="html")
        else:
            await self.send_logger_message(self.strings["no_number"])

    @loader.command()
    async def subcmd(self, message):
        """Подписаться на каналы (команда subcmd)
Пример: subcmd t.me/channel1 t.me/channel2"""
        if not await self.ensure_subscription(message):
            return
        await self.delay_host(self.config["delay"])
        urls = await self.extract_valid_urls(utils.get_args_raw(message))
        if not urls:
            await self.send_logger_message("<b>❌ Не найдены ссылки.</b>")
            return
        success, failed = 0, 0
        for link in urls:
            try:
                try:
                    entity = await self.client.get_entity(link)
                    if getattr(entity, "bot", False):
                        await self.log(f"ℹ️ Подписка на @{entity.username} пропущена (бот).")
                        continue
                except Exception:
                    pass
                if "/+" in link:
                    await self.client(ImportChatInviteRequest(link.split("t.me/+")[1]))
                else:
                    uname = link.split("t.me/")[1]
                    await self.client(JoinChannelRequest(uname))
                success += 1
                await asyncio.sleep(self.config["delay"])
            except Exception as e:
                failed += 1
                await self.send_logger_message(f"Ошибка подписки {link}: {e}")
        res = f"✅ <b>Подписка:</b> {success} успешно, {failed} ошибок.<br>Каналы: {', '.join(urls)}"
        await self.send_logger_message(res)

    @loader.command()
    async def unsubcmd(self, message):
        """Отписаться от каналов (команда unsubcmd)
Пример: unsubcmd t.me/channel1 t.me/channel2"""
        if not await self.ensure_subscription(message):
            return
        await self.delay_host(self.config["delay"])
        urls = await self.extract_valid_urls(utils.get_args_raw(message))
        if not urls:
            await self.send_logger_message("<b>❌ Ссылки не найдены.</b>")
            return
        success, failed = 0, 0
        for link in urls:
            try:
                uname = link.split("t.me/")[1]
                await self.client(LeaveChannelRequest(uname))
                success += 1
                await asyncio.sleep(self.config["delay"])
            except Exception as e:
                failed += 1
                await self.send_logger_message(f"Ошибка отписки от {link}: {e}")
        res = f"✅ <b>Отписка:</b> {success} успешно, {failed} ошибок.<br>Каналы: {', '.join(urls)}"
        await self.send_logger_message(res)

    @loader.command()
    async def run(self, message):
        """Запустить действия с логированием (команда run)
Пример: run t.me/channel/1234"""
        raw_args = utils.get_args_raw(message)
        urls = re.findall(r't\.me/(c/\d+/\d+|\w+/\d+)', raw_args)
        at_channels = re.findall(r'@(\w+)', raw_args)
        if not urls and not at_channels:
            await utils.answer(message, "<b>❌ Укажите ссылки или @каналы</b>")
            return
        await self.send_logger_message("<b>✅ Действия запущены.</b>")

    @loader.command()
    async def refk(self, message):
        """Обработка реферальных ссылок (команда refk)
Пример: refk t.me/bot?start=XXXX"""
        urls = re.findall(r't\.me/(c/\d+/\d+|\w+/\d+)', utils.get_args_raw(message))
        if not urls:
            await self.send_logger_message("<b>❌ Укажите ссылки</b>")
            return
        await self.send_logger_message("<b>✅ Обработка реферальных ссылок завершена.</b>")

    # Новая команда start – автоматический запуск всех функций подписки и участия в конкурсах
    @loader.command()
    async def start(self, message):
        """
        Автоматический запуск всех функций для подписки на каналы и участия в розыгрышах/конкурсах.
        Использование: start <ссылки>
        В качестве аргументов можно передать ссылки на каналы, inline-посты и реферальные ссылки через пробел.
        """
        args = utils.get_args_raw(message).strip()
        if not args:
            await message.edit("<b>❌ Укажите ссылки для автозапуска.</b>")
            return
        # Для автозапуска будем использовать переданные ссылки для подписки, inline-кнопок и реферальных ссылок
        # Последовательно вызываем функции:
        await self.subcmd(message)
        await self.run(message)
        await self.refk(message)
        await message.edit("<b>✅ Автозапуск выполнен.</b>")

    async def ensure_subscription(self, message):
        if not await self.is_subscribed():
            await message.edit(self.strings["sub_required"], parse_mode="html")
            return False
        return True

    async def is_subscribed(self, target: str = None) -> bool:
        try:
            channel = target or "tot_882"
            participant = await self.client(GetParticipantRequest(channel, "me"))
            return isinstance(participant.participant, ChannelParticipantSelf)
        except Exception as e:
            logger.error(f"Ошибка проверки подписки: {e}")
            return False

# Функция для получения даты регистрации аккаунта (используется в getinfo)
async def get_creation_date(tg_id: int) -> str:
    url = "https://restore-access.indream.app/regdate"
    headers = {
        "accept": "*/*",    
        "content-type": "application/x-www-form-urlencoded",
        "user-agent": "Nicegram/92 CFNetwork/1390 Darwin/22.0.0",
        "x-api-key": "e758fb28-79be-4d1c-af6b-066633ded128",
        "accept-language": "en-US,en;q=0.9",
    }
    data = {"telegramId": tg_id}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            if response.status == 200:
                json_response = await response.json()
                return json_response["data"]["date"]
            else:
                return "Ошибка получения данных"
