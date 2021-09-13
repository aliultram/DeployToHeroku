import asyncio
import io
import re
import urllib.parse
from typing import ClassVar, Optional

import aiohttp
import telethon as tg

from .. import command, module, util

LOGIN_CODE_REGEX = r"[Ll]ogin code: (\d+)"


class NetworkModule(module.Module):
    name: ClassVar[str] = "Network"

    @command.desc("Pong")
    async def cmd_ping(self, ctx: command.Context):
        before = util.time.msec()
        await ctx.respond("Calculating response time...")
        after = util.time.msec()

        return f"Request response time: {after - before:.0f} ms"

    async def on_message(self, msg: tg.events.NewMessage.Event) -> None:
        # Only check Telegram service messages
        if msg.sender_id != 777000:
            return

        # Print login code if present
        match = re.search(LOGIN_CODE_REGEX, msg.raw_text)
        if match is not None:
            self.log.info(f"Received Telegram login code: {match.group(1)}")

    @command.desc("Upload given file to file.io")
    @command.usage("[expiry time?]", optional=True)
    async def cmd_fileio(self, ctx: command.Context) -> str:
        expires = ctx.input

        if not ctx.msg.is_reply:
            return "__Reply to a file to upload it.__"

        if expires == "help":
            return "__Expiry format: 1y/12m/52w/365d__"
        if expires:
            if expires[-1] not in ["y", "m", "w", "d"]:
                return "__Unknown unit. Expiry format: 1y/12m/52w/365d__"

            try:
                int(expires[:-1])
            except ValueError:
                return "__Invalid number. Expiry format: 1y/12m/52w/365d__"
        else:
            expires = "2d"

        reply_msg = await ctx.msg.get_reply_message()
        if not reply_msg.file:
            return "__That message doesn't contain a file.__"

        data = await util.tg.download_file(ctx, reply_msg)
        buf = io.BytesIO(data)
        buf.name = reply_msg.file.name

        await ctx.respond("Uploading file to [file.io](https://file.io/)...")

        async with self.bot.http.post(
            f"https://file.io/?expires={expires}", data={"file": buf}
        ) as resp:
            resp_data = await resp.json()

            if not resp_data["success"]:
                return f"__Error uploading file — status code {resp.status}__"

            return str(resp_data["link"])

    @command.desc("Update the embed for a link")
    @command.usage("[link?, or reply]", optional=True)
    @command.alias("upde", "updl", "updatelink", "ul", "ulink")
    async def cmd_update_link(self, ctx: command.Context) -> Optional[str]:
        link = ctx.input

        if not (link or ctx.msg.is_reply):
            return "__Provide or reply to a link to update it.__"

        if not link:
            reply_msg = await ctx.msg.get_reply_message()

            for entity, text in reply_msg.get_entities_text():
                if isinstance(
                    entity,
                    (tg.tl.types.MessageEntityUrl, tg.tl.types.MessageEntityTextUrl),
                ):
                    link = text

        if not link:
            return "__That message doesn't contain any links."

        await ctx.respond(f"Updating embed for [link]({link})...")

        async with self.bot.client.conversation("WebpageBot") as conv:
            await conv.send_message(link)

            response = await conv.get_response()
            await conv.mark_read()

            if "Link previews was updated successfully" in response.raw_text:
                # Provide a status update
                await ctx.respond("Waiting for embed update to propagate...")

                # Give Telegram some time to propagate the update
                await asyncio.sleep(1)

                # Send the new preview
                await ctx.respond(f"Updated embed for link: {link}", link_preview=True)
            else:
                # Failed for some reason, send the error
                await ctx.respond(
                    f"Error updating embed for [link]({link}): `{response.raw_text}`"
                )

        return None

    @command.desc("Generate a LMGTFY link (Let Me Google That For You)")
    @command.usage("[search query]")
    async def cmd_lmgtfy(self, ctx: command.Context) -> str:
        query = ctx.input
        params = urllib.parse.urlencode({"q": query})

        return f"https://lmgtfy.com/?{params}"
