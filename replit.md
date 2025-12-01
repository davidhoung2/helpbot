# ChatGPT Discord Bot

## Overview
This is a Discord bot that integrates with multiple AI providers (OpenAI, Claude, Gemini, Grok, and a free provider via g4f). Users can chat with AI assistants, generate images, switch between providers, and customize the bot's personality using different personas.

**Current State**: Bot is running and connected to Discord as "yang#0266". All dependencies installed and configured for Replit environment.

## Recent Changes
**December 1, 2025** (AI Task Name Validation + Task-Only Records):
- Added `validate_task_name_with_ai()` function to use AI providers for validating military task names
- AI validation only runs when BOTH commander AND driver are present (complete dispatch info)
- Task name extraction now supports format: `12/25-7 9A觀測所佈纜` (date + task name)
- System now creates dispatch records even without vehicle plates:
  - With vehicle plate: `vehicle_id = plate`, `task_name = extracted task`
  - Without vehicle plate but with task: `vehicle_id = task`, `task_name = task`
  - With neither: record not created
- AI validation results logged for debugging

**Previous Changes Summary**:
- Vehicle plate (車牌號碼) and task name (任務名稱) stored as separate fields
- Automatic dispatch message detection and database storage
- Support for multiple date formats and comma-separated dates
- Date range parsing (e.g., `11/19-20`, `11/19、20`)
- Smart validation prompting when date detected but invalid format
- Automatic cleanup of expired records (hourly)

## Project Architecture

### Core Components
- **main.py**: Entry point that validates environment and starts the bot
- **src/bot.py**: Discord bot commands and event handlers
- **src/aclient.py**: Discord client implementation with message queue system
- **src/providers.py**: AI provider abstraction layer supporting multiple backends
- **src/personas.py**: Personality presets for the AI assistant
- **src/log.py**: Logging configuration
- **src/dispatch_db.py**: SQLite database operations for dispatch records
- **src/dispatch_parser.py**: Message parser for extracting dispatch information
- **utils/message_utils.py**: Message processing utilities

### AI Providers Supported
1. **Free Provider** (g4f): No API key required, uses Blackbox, DuckDuckGo, and FreeChatGPT
2. **OpenAI**: Requires OPENAI_KEY secret
3. **Claude** (Anthropic): Requires CLAUDE_KEY secret
4. **Gemini** (Google): Requires GEMINI_KEY secret
5. **Grok** (xAI): Requires GROK_KEY secret

### Dependencies
- discord.py 2.4.0 - Discord API wrapper
- g4f 0.3.2.9 - Free GPT providers
- openai 1.66.2 - OpenAI API
- anthropic 0.42.0 - Claude API
- google-generativeai 0.8.3 - Gemini API
- python-dotenv 1.0.1 - Environment variable management
- selenium 4.28.1 - Browser automation (for some providers)
- aiohttp 3.11.11 - Async HTTP client

## Required Secrets
- **DISCORD_BOT_TOKEN** (required): Already configured in Replit Secrets

## Optional Secrets for Premium Providers
- **OPENAI_KEY**: For OpenAI GPT models and DALL-E 3 image generation
- **CLAUDE_KEY**: For Anthropic Claude models
- **GEMINI_KEY**: For Google Gemini models (including image generation)
- **GROK_KEY**: For xAI Grok models

## Discord Bot Commands

### AI Chat Commands
- `/chat [message]` - Chat with the current AI provider
- `/provider` - Switch between AI providers
- `/draw [prompt] [model]` - Generate images
- `/reset` - Clear conversation history
- `/switchpersona [persona]` - Switch AI personality
- `/private` - Bot replies only visible to command user
- `/public` - Bot replies visible to everyone (default)
- `/replyall` - Bot responds to all messages in channel (toggle)

### Dispatch Management Commands (Slash)
- `/dispatch` - View all active dispatch records (派車表單)
- `/dispatch_list` - View dispatch list (派車列表)
- `/dispatch_clear` - Manually clear expired dispatch records

### Text Commands (Legacy - still supported)
- `!派車` / `!dispatch` - View dispatch form
- `!派車列表` / `!詳細派車` - View detailed list
- `!編輯 <ID> <field> <value>` - Edit dispatch
- `!刪除 <ID>` - Delete dispatch
- `!清除派車` / `!dispatch_clear` - Clear expired records
- `!help` / `!指令` - Show help
- `!myid` - Show your Discord ID

## Dispatch Management
The bot automatically detects dispatch messages and stores them in a local SQLite database.

### Supported Message Formats:

**With Vehicle Plate (most common):**
```
12／17
軍K-20539 9A觀測所佈覽用車
車長：上士曾智偉
駕駛：上士周宗暘
```

**Without Vehicle Plate (task-only, also stored):**
```
12/25-7 9A觀測所佈纜
車長：上士曾智偉
駕駛：中士許皓珽
```

**Supported Date Formats:**
- Standard: `12/2(二)派車` (with weekday)
- Date range: `12/25-7派車` (12/25 to 12/27)
- Comma-separated: `11/19、20派車` or `11/19, 20派車`
- Fullwidth slash: `12／11派車`

### Features:
- Automatic detection: No command needed, just send the dispatch info
- Task name validation: AI validates task names when commander and driver both present
- Duplicate prevention: Won't add the same vehicle/task for the same date twice
- Auto-cleanup: Expired records (past dates) are deleted automatically every hour
- Confirmation: Bot adds ✅ reaction when dispatch info is saved
- Smart validation: Bot prompts with correct format when detecting invalid dispatch messages

## Environment Configuration
The bot uses a `.env` file for configuration. Key settings:
- `DISCORD_BOT_TOKEN`: Bot authentication (stored as Replit secret)
- `LOGGING`: Enable/disable logging (default: True)
- `DEFAULT_PROVIDER`: Default AI provider (default: free)
- `DEFAULT_MODEL`: Default model (default: auto)
- `ADMIN_USER_IDS`: Comma-separated Discord user IDs for admin access

## Deployment Notes
- Bot runs in console mode (no web frontend)
- Uses Python 3.11
- All dependencies managed via pip
- Workflow configured to run `python main.py`
- Bot automatically reconnects on disconnect

## User Preferences
None specified yet.
