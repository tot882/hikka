import asyncio
import base64
import contextlib
import difflib
import inspect
import io
import logging
import random
import re
import typing

import requests
import rsa
from hikkatl.tl.types import Message
from hikkatl.utils import resolve_inline_message_id

from .. import loader, main, utils
from ..types import InlineCall, InlineQuery
from ..version import __version__

logger = logging.getLogger(__name__)

@loader.tds
class ToThosT(loader.Module):
    """Chat ToThosT"""

    strings = {"name": "ToThosT"}

    async def client_ready(self):
        await self.request_join(
            "@tothosting",
            (
                "Это чат твоего хостинга"
                " Пожалуйста зайди в него'"
            ),
        )
