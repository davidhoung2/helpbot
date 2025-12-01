import os
import asyncio
import discord
from discord import app_commands
from typing import Optional
from datetime import datetime, timedelta

from src.aclient import discordClient
from src.providers import ProviderType
from src import log, personas
from src.log import logger
from src import dispatch_db, dispatch_parser


def run_discord_bot():
    @discordClient.event
    async def on_ready():
        dispatch_db.init_database()
        
        # Set bot status to DND with "正在玩工具人" activity
        await discordClient.change_presence(
            status=discord.Status.dnd,
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name="工具人"
            )
        )
        
        await discordClient.send_start_prompt()
        await discordClient.tree.sync()
        loop = asyncio.get_event_loop()
        loop.create_task(discordClient.process_messages())
        loop.create_task(dispatch_cleanup_task())
        logger.info(f'{discordClient.user} is now running!')
    
    async def dispatch_cleanup_task():
        """Background task to clean up expired dispatch records"""
        while True:
            try:
                deleted = dispatch_db.delete_expired_dispatches()
                if deleted > 0:
                    logger.info(f"Cleanup task: Deleted {deleted} expired dispatch records")
            except Exception as e:
                logger.error(f"Error in dispatch cleanup task: {e}")
            
            await asyncio.sleep(3600)


    @discordClient.tree.command(name="chat", description="聊天")
    async def chat(interaction: discord.Interaction, *, message: str):
        if len(message) > 2000:
            await interaction.response.send_message(
                "❌ 訊息太長 (最多 2000 字元)",
                ephemeral=True
            )
            return

        message = message.replace('\x00', '')
        message = message.strip()

        if not message:
            await interaction.response.send_message(
                "❌ 請提供訊息內容",
                ephemeral=True
            )
            return

        prompt_instruction = (
            "無論我問什麼請一律使用繁體中文回應 除非我有叫你更改語言"
        )
        message  = prompt_instruction + prompt_instruction
        
        if discordClient.is_replying_all:
            await interaction.response.defer(ephemeral=False)
            await interaction.followup.send(
                "> **警告：您已在 ReplyAll 模式。請先使用 `/replyall` 關閉此模式後，才能使用 Slash Command。**")
            logger.warning("\x1b[31mYou already on replyAll mode, can't use slash command!\x1b[0m")
            return
        if interaction.user == discordClient.user:
            return
        username = str(interaction.user)
        discordClient.current_channel = interaction.channel
        logger.info(
            f"\x1b[31m{username}\x1b[0m : /chat [{message}] in ({discordClient.current_channel})")

        await discordClient.enqueue_message(interaction, message)

    @discordClient.tree.command(name="reset", description="Clear conversation history")
    async def reset(interaction: discord.Interaction):
        discordClient.reset_conversation_history()
        await interaction.response.send_message(
            "🔄 Conversation history has been cleared. Starting fresh!",
            ephemeral=False
        )

    @discordClient.tree.command(name="dispatch", description="查看目前的派車表單")
    async def dispatch(interaction: discord.Interaction):
        """View all active dispatch records"""
        try:
            dispatches = dispatch_db.get_all_active_dispatches()
            formatted = dispatch_parser.format_dispatch_list(dispatches)
            
            if len(formatted) > 2000:
                chunks = [formatted[i:i+1900] for i in range(0, len(formatted), 1900)]
                await interaction.response.send_message(chunks[0], ephemeral=False)
                for chunk in chunks[1:]:
                    await interaction.followup.send(chunk)
            else:
                await interaction.response.send_message(formatted, ephemeral=False)
                
        except Exception as e:
            logger.error(f"Error fetching dispatch records: {e}")
            await interaction.response.send_message(
                f"❌ 取得派車資訊時發生錯誤：{e}",
                ephemeral=True
            )
    
    @discordClient.tree.command(name="dispatch_list", description="查詢派車列表")
    async def dispatch_list_cmd(interaction: discord.Interaction):
        """Show dispatch list"""
        try:
            dispatches = dispatch_db.get_all_active_dispatches()
            formatted = dispatch_parser.format_dispatch_list(dispatches)
            await interaction.response.send_message(formatted, ephemeral=False)
        except Exception as e:
            logger.error(f"Error getting dispatch list: {e}")
            await interaction.response.send_message(f"❌ 取得列表時發生錯誤：{e}", ephemeral=True)

    @discordClient.tree.command(name="dispatch_clear", description="清除所有已過期的派車記錄")
    async def dispatch_clear(interaction: discord.Interaction):
        """Manually clear expired dispatch records"""
        try:
            deleted = dispatch_db.delete_expired_dispatches()
            await interaction.response.send_message(
                f"🗑️ 已刪除 {deleted} 筆過期的派車記錄。",
                ephemeral=False
            )
        except Exception as e:
            logger.error(f"Error clearing dispatch records: {e}")
            await interaction.response.send_message(
                f"❌ 清除派車記錄時發生錯誤：{e}",
                ephemeral=True
            )

    @discordClient.tree.command(name="help", description="Show all available commands")
    async def help(interaction: discord.Interaction):
        embed = discord.Embed(
            title="🤖 AI Discord Bot - Help",
            description="Here are all available commands:",
            color=discord.Color.blue()
        )
        
        commands = [
            ("💬 **Chat Commands**", [
                ("/chat [message]", "Chat with the AI"),
                ("/reset", "Clear conversation history"),
                ("/replyall", "Toggle bot responding to all messages")
            ]),
            ("🤖 **Provider & Model**", [
                ("/provider", "Switch AI provider and model interactively")
            ]),
            ("🎨 **Image Generation**", [
                ("/draw [prompt]", "Generate an image from text")
            ]),
            ("🎭 **Personas**", [
                ("/switchpersona [name]", "Change AI personality"),
                ("Available", "standard, creative, technical, casual"),
                ("Admin Only", "jailbreak-v1, jailbreak-v2, jailbreak-v3 (restricted)")
            ]),
            ("🚗 **派車管理**", [
                ("/dispatch", "查看目前的派車表單"),
                ("/dispatch_clear", "手動清除過期記錄")
            ]),
            ("⚙️ **Settings**", [
                ("/private", "Toggle private/public responses"),
                ("/help", "Show this help message")
            ])
        ]
        
        for category, cmds in commands:
            value = "\n".join([f"`{cmd}` - {desc}" for cmd, desc in cmds])
            embed.add_field(name=category, value=value, inline=False)
        
        # Add provider info
        info = discordClient.get_current_provider_info()
        embed.add_field(
            name="📊 Current Settings",
            value=f"**Provider:** {info['provider']}\n**Model:** {info['current_model']}",
            inline=False
        )
        
        # Add dispatch count
        dispatch_count = dispatch_db.get_dispatch_count()
        embed.add_field(
            name="🚗 派車統計",
            value=f"**目前有效派車數:** {dispatch_count}",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def process_dispatch_message(message):
        """Process a message and check if it contains dispatch information"""
        content = message.content
        
        if not dispatch_parser.is_dispatch_message(content):
            return False
        
        # Check for cancellations first
        cancelled_info = dispatch_parser.extract_cancelled_info(content)
        if cancelled_info:
            deleted = dispatch_db.delete_dispatch_by_date(cancelled_info['date'], cancelled_info['task_name'])
            logger.info(f"Cancelled dispatch for {cancelled_info['date']}: deleted {deleted} records")
        
        # Then process new dispatches
        parsed_list = dispatch_parser.parse_dispatch_message(content)
        if not parsed_list:
            # If only cancellation, consider it handled
            return bool(cancelled_info)
        
        added_count = 0
        ai_issues = []  # Track AI issues to report to user
        
        # parsed_list is now a list of dispatch records
        for parsed in parsed_list:
            logger.info(f"[DEBUG] Processing record: date={parsed['date']}, vehicles={parsed['vehicles']}, commander={parsed['commander']}, driver={parsed['driver']}")
            for vehicle in parsed['vehicles']:
                logger.info(f"[DEBUG] Checking vehicle: {vehicle['vehicle_id']}")
                
                # AI validate task name only if both commander and driver are present
                task_name = vehicle.get('task_name', '')
                commander = parsed.get('commander', '')
                driver = parsed.get('driver', '')
                
                if task_name and commander and driver:
                    try:
                        is_valid_task = await dispatch_parser.validate_task_name_with_ai(task_name)
                        if not is_valid_task:
                            logger.info(f"[AI Validation] Task name '{task_name}' failed AI validation, but keeping it")
                            ai_issues.append(f"⚠️ 任務驗證失敗: {task_name}")
                        else:
                            logger.info(f"[AI Validation] Task name '{task_name}' passed AI validation")
                    except Exception as e:
                        logger.warning(f"[AI Validation] Error validating task name '{task_name}': {e}")
                        logger.info(f"[AI Validation] AI unavailable, keeping task name '{task_name}'")
                        ai_issues.append(f"⚠️ AI 驗證不可用，任務名稱: {task_name}")
                elif task_name:
                    logger.info(f"[AI Validation] Skipping AI validation for task name '{task_name}' - commander or driver missing")
                
                if not dispatch_db.check_duplicate(parsed['date'], vehicle['vehicle_id']):
                    logger.info(f"[DEBUG] Adding dispatch: {parsed['date']} - {vehicle['vehicle_id']} (plate: {vehicle.get('vehicle_plate', '')}, task: {vehicle.get('task_name', '')})")
                    dispatch_db.add_dispatch(
                        dispatch_date=parsed['date'],
                        day_of_week=parsed['day_of_week'],
                        vehicle_id=vehicle['vehicle_id'],
                        vehicle_status=vehicle['status'],
                        commander=parsed['commander'],
                        driver=parsed['driver'],
                        message_id=str(message.id),
                        channel_id=str(message.channel.id),
                        vehicle_plate=vehicle.get('vehicle_plate', ''),
                        task_name=vehicle.get('task_name', '')
                    )
                    added_count += 1
                else:
                    logger.info(f"[DEBUG] Duplicate found: {parsed['date']} - {vehicle['vehicle_id']}")
        
        if added_count > 0 or cancelled_info:
            if added_count > 0:
                logger.info(f"Added {added_count} dispatch records from message")
            try:
                await message.add_reaction('✅')
            except Exception as e:
                logger.warning(f"Could not add reaction: {e}")
            
            # Send AI issue notification if any
            if ai_issues:
                try:
                    issue_text = "\n".join(ai_issues)
                    await message.reply(f"✅ 派車紀錄已保存\n\n{issue_text}\n\n（任務仍然被保存，但建議檢查AI驗證結果）")
                except Exception as e:
                    logger.warning(f"Could not send AI issue notification: {e}")
            
            return True
        
        return False

    @discordClient.event
    async def on_message(message):
        logger.info(f"[DEBUG] Received message from {message.author}: {message.content[:50] if message.content else '(empty)'}...")
        
        if message.author == discordClient.user:
            logger.info("[DEBUG] Ignoring own message")
            return
        
        # Ignore direct messages (private chats)
        if message.guild is None:
            logger.info(f"[DEBUG] Ignoring private message from {message.author}")
            return
        
        # Ignore messages from blacklisted channels
        blacklist_channels = os.getenv("BLACKLIST_CHANNEL_IDS", "1332155696564928646").split(",")
        blacklist_channels = [ch.strip() for ch in blacklist_channels if ch.strip()]
        if str(message.channel.id) in blacklist_channels:
            logger.info(f"[DEBUG] Ignoring message from blacklisted channel: {message.channel.id}")
            return
        
        content = message.content.strip().lower()
        
        admin_ids = os.getenv("ADMIN_USER_IDS", "").split(",")
        admin_ids = [id.strip() for id in admin_ids if id.strip()]
        is_admin = str(message.author.id) in admin_ids
        
        if content == '!myid':
            await message.channel.send(f"你的 Discord 用戶 ID 是: `{message.author.id}`")
            return
        
        if content in ['!dispatch', '!派車', '!派車表', '派車表', '查派車']:
            try:
                dispatches = dispatch_db.get_all_active_dispatches()
                formatted = dispatch_parser.format_dispatch_list(dispatches)
                await message.channel.send(formatted)
                logger.info(f"Dispatch list sent to {message.author}")
            except Exception as e:
                logger.error(f"Error sending dispatch list: {e}")
                await message.channel.send(f"❌ 取得派車資訊時發生錯誤：{e}")
            return
        
        if content in ['!dispatch_clear', '!清除派車']:
            try:
                deleted = dispatch_db.delete_expired_dispatches()
                await message.channel.send(f"🗑️ 已刪除 {deleted} 筆過期的派車記錄。")
            except Exception as e:
                logger.error(f"Error clearing dispatch: {e}")
                await message.channel.send(f"❌ 清除派車記錄時發生錯誤：{e}")
            return
        
        if content in ['!清空所有派車', '!truncate_dispatch']:
            if not is_admin:
                await message.channel.send("❌ 只有管理員可以清空所有派車記錄。")
                return
            try:
                deleted = dispatch_db.clear_all_dispatches()
                await message.channel.send(f"🗑️ 已清空所有派車記錄，共刪除 {deleted} 筆。")
            except Exception as e:
                logger.error(f"Error clearing all dispatch: {e}")
                await message.channel.send(f"❌ 清空派車記錄時發生錯誤：{e}")
            return
        
        if content.startswith('!刪除 ') or content.startswith('!delete '):
            if not is_admin:
                await message.channel.send("❌ 只有管理員可以刪除記錄。")
                return
            try:
                parts = message.content.strip().split(' ', 1)
                if len(parts) < 2:
                    await message.channel.send("❌ 請提供要刪除的記錄 ID。用法: `!刪除 <ID>`")
                    return
                dispatch_id = int(parts[1])
                if dispatch_db.delete_dispatch(dispatch_id):
                    await message.channel.send(f"✅ 已刪除記錄 ID: {dispatch_id}")
                else:
                    await message.channel.send(f"❌ 找不到記錄 ID: {dispatch_id}")
            except ValueError:
                await message.channel.send("❌ ID 必須是數字。")
            except Exception as e:
                await message.channel.send(f"❌ 刪除時發生錯誤：{e}")
            return
        
        if content.startswith('!編輯 ') or content.startswith('!edit '):
            if not is_admin:
                await message.channel.send("❌ 只有管理員可以編輯記錄。")
                return
            try:
                parts = message.content.strip().split(' ')
                if len(parts) < 4:
                    await message.channel.send("❌ 用法: `!編輯 <ID> <欄位> <新值>`\n欄位: 車長, 駕駛")
                    return
                dispatch_id = int(parts[1])
                field = parts[2]
                new_value = ' '.join(parts[3:])
                
                if field in ['車長', 'commander']:
                    if dispatch_db.update_dispatch(dispatch_id, commander=new_value):
                        await message.channel.send(f"✅ 已更新記錄 ID {dispatch_id} 的車長為: {new_value}")
                    else:
                        await message.channel.send(f"❌ 找不到記錄 ID: {dispatch_id}")
                elif field in ['駕駛', 'driver']:
                    if dispatch_db.update_dispatch(dispatch_id, driver=new_value):
                        await message.channel.send(f"✅ 已更新記錄 ID {dispatch_id} 的駕駛為: {new_value}")
                    else:
                        await message.channel.send(f"❌ 找不到記錄 ID: {dispatch_id}")
                else:
                    await message.channel.send("❌ 不支援的欄位。可用欄位: 車長, 駕駛")
            except ValueError:
                await message.channel.send("❌ ID 必須是數字。")
            except Exception as e:
                await message.channel.send(f"❌ 編輯時發生錯誤：{e}")
            return
        
        if content in ['!dispatch_list', '!派車列表', '!詳細派車']:
            try:
                dispatches = dispatch_db.get_all_active_dispatches()
                if not dispatches:
                    await message.channel.send("目前沒有派車資訊。")
                    return
                lines = ["📋 **派車詳細列表** (含 ID)\n"]
                for d in dispatches:
                    lines.append(f"**ID: {d['id']}** | {d['dispatch_date']} | {d['vehicle_id']} | 車長: {d['commander'] or '(空)'} | 駕駛: {d['driver'] or '(空)'}")
                await message.channel.send('\n'.join(lines))
            except Exception as e:
                await message.channel.send(f"❌ 取得列表時發生錯誤：{e}")
            return
        
        if content == '!help' or content == '!指令':
            help_text = """📋 **派車管理指令**

**查詢指令 (所有人可用):**
`!派車` / `!dispatch` - 查看派車表單
`!派車列表` / `!詳細派車` - 查看含 ID 的詳細列表
`!myid` - 查看你的用戶 ID

**管理指令 (僅管理員):**
`!編輯 <ID> 車長 <名字>` - 修改車長
`!編輯 <ID> 駕駛 <名字>` - 修改駕駛
`!刪除 <ID>` - 刪除指定記錄
`!清除派車` / `!dispatch_clear` - 清除所有過期記錄
`!清空所有派車` / `!truncate_dispatch` - 清除所有派車記錄

**自動功能:**
✅ 自動偵測派車訊息 - 包含日期+車牌會自動儲存
✅ 支援格式:
```
12／17
軍K-20539 9A觀測所佈覽用車
車長：上士曾智偉
駕駛：上士周宗暘
```

✅ 自動偵測取消 - 包含日期+「取消」會自動刪除
  • 範例: `原定11/11三分隊線巡取消`"""
            await message.channel.send(help_text)
            return
        
        try:
            logger.info(f"[DEBUG] Checking if dispatch message: {message.content[:100] if message.content else '(empty)'}")
            dispatch_processed = await process_dispatch_message(message)
            if dispatch_processed:
                logger.info(f"Dispatch info saved from {message.author}")
            else:
                # Check if message has date but is not a valid dispatch format
                if dispatch_parser.has_date(message.content) and not dispatch_parser.is_dispatch_message(message.content):
                    await message.reply("❌ 偵測到日期，但格式不符合派車資訊。\n\n請使用正確的派車格式：\n```\n12/26(五) 任務用車\n車長:   \n駕駛:    \n```\n\n輸入 `!help` 查看完整格式說明。")
                logger.info(f"[DEBUG] Not a dispatch message or already exists")
        except Exception as e:
            logger.error(f"Error processing dispatch message: {e}")
        
        if discordClient.is_replying_all:
            if discordClient.replying_all_discord_channel_id:
                if message.channel.id != int(discordClient.replying_all_discord_channel_id):
                    return
            
            username = str(message.author)
            user_message = message.content
            discordClient.current_channel = message.channel
            
            logger.info(f"\x1b[31m{username}\x1b[0m : {user_message} in ({message.channel})")
            await discordClient.enqueue_message(message, user_message)

    # Run the bot
    discordClient.run(os.getenv("DISCORD_BOT_TOKEN"))