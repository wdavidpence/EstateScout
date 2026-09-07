# EstateScout agent instructions

## Telegram integration boundary

EstateScout is intended to run inside the user's existing Hermes Telegram channel/chat `7310916411`.

- Do not create, start, or recommend a second Telegram polling process for EstateScout.
- Do not load `/Users/davidpence/.hermes/.env` or reuse Hermes's Telegram bot token.
- Implement EstateScout as Hermes-integrated functionality: a Hermes plugin, gateway handler, command, or other supported extension point.
- A standalone `python-telegram-bot` app is allowed only if the user explicitly requests a separate BotFather bot and supplies a separate token.
- Keep any standalone fallback fail-closed with app-specific variables such as `ESTATESCOUT_BOT_TOKEN`.

Before changing Telegram behavior, verify which single process owns long polling and preserve Hermes's existing Telegram connection.
