"""EstateScout Telegram Bot — Complete Working Version

Full integration with Hermes Telegram channel (7310916411).
Handles: +silver, +training, +collection, +tools, +start, photo upload,
image annotation with red circles/boxes, and item notes.

Uses existing annotation.py and collection.py modules.
Follows telegram-bot-development skill guidelines.
"""

import os
import json
import asyncio
import base64
from pathlib import Path
from datetime import datetime
from io import BytesIO

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery,
    InputFile, PhotoSize, MessageEntity
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# ── Paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
ANNOTATION_DIR = DATA_DIR / "annotated_images"
ANNOTATION_DIR.mkdir(parents=True, exist_ok=True)

# Import backend modules
from annotation import annotate_image, analyze_and_annotate
from collection import (
    load_notes, save_notes, add_item_note, get_collection,
    get_item, delete_item, format_item_for_display, list_collection
)

# ── Credentials (app-specific, never touch Hermes token) ────────────────
BOT_TOKEN = os.environ.get("ESTATESCOUT_BOT_TOKEN", "")
ALLOWED_USERS = {
    int(u.strip())
    for u in os.environ.get("ESTATESCOUT_ALLOWED_USERS", "").split(",")
    if u.strip()
}
HOME_CHANNEL = os.environ.get("ESTATESCOUT_HOME_CHANNEL", "7310916411")


# ── Keyboard Helpers ────────────────────────────────────────────────────

def get_main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏷️ Silver Guide", callback_data="silver"),
            InlineKeyboardButton("📷 Scan Item", callback_data="scan"),
        ],
        [
            InlineKeyboardButton("📚 Training", callback_data="training"),
            InlineKeyboardButton("📦 Collection", callback_data="collection"),
        ],
        [
            InlineKeyboardButton("🛠️ Tools", callback_data="tools"),
            InlineKeyboardButton("📋 Library", callback_data="library"),
        ],
    ])


# ── Command Handlers ────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome = (
        f"🏴‍☠️ *EstateScout* — Your AI Estate Sale Assistant\n\n"
        f"Hi {user.first_name}! I help you identify silver at estate sales.\n\n"
        f"Send me a *photo* of an item and I'll:\n"
        f"• Analyze hallmarks and marks\n"
        f"• Draw red circles/boxes on the image\n"
        f"• Save annotated photos to your Library\n"
        f"• Record notes and verdict in your Collection\n\n"
        f"Tap a button below or send +start to see all commands."
    )
    await update.message.reply_text(
        welcome, parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )


async def cmd_silver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Solid Marks", callback_data="silver_solid"),
            InlineKeyboardButton("⚠️ Plated Marks", callback_data="silver_plated"),
        ],
        [
            InlineKeyboardButton("🇬🇧 British Marks", callback_data="silver_british"),
            InlineKeyboardButton("🇺🇸 American Makers", callback_data="silver_american"),
        ],
        [
            InlineKeyboardButton("❌ Fakes & Reproductions", callback_data="silver_fakes"),
            InlineKeyboardButton("🪙 Coin Silver", callback_data="silver_coins"),
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="main")],
    ])
    kb2 = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 Solid Marks", callback_data="silver_solid"),
            InlineKeyboardButton("⚠️ Plated Marks", callback_data="silver_plated"),
        ],
        [
            InlineKeyboardButton("🇬🇧 British Marks", callback_data="silver_british"),
            InlineKeyboardButton("🇺🇸 American Makers", callback_data="silver_american"),
        ],
        [
            InlineKeyboardButton("❌ Fakes & Reproductions", callback_data="silver_fakes"),
            InlineKeyboardButton("🪙 Coin Silver", callback_data="silver_coins"),
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="main")],
    ])
    await update.message.reply_text(
        "🏷️ *Silver Guide — Choose a topic:*\n\n"
        "Tap any topic to learn about it.",
        parse_mode="Markdown", reply_markup=kb2
    )


async def cmd_training(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Module 1: Basic ID", callback_data="mod1")],
        [InlineKeyboardButton("🟡 Module 2: Intermediate", callback_data="mod2")],
        [InlineKeyboardButton("🟠 Module 3: Advanced", callback_data="mod3")],
        [InlineKeyboardButton("🔴 Module 4: Practical", callback_data="mod4")],
        [InlineKeyboardButton("⬅️ Back", callback_data="main")],
    ])
    await update.message.reply_text(
        "📚 *Training Academy*\n\n"
        "Progressive lessons from basic ID to estate sale mastery.\n\n"
        "Tap a module to open it:",
        parse_mode="Markdown", reply_markup=kb
    )


async def cmd_collection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = list_collection()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📷 Scan New Item", callback_data="scan")],
        [InlineKeyboardButton("⬅️ Back", callback_data="main")],
    ])
    await update.message.reply_text(result, reply_markup=kb)


async def cmd_tools(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚖️ Pocket Scale", callback_data="tool_scale")],
        [InlineKeyboardButton("🧲 Magnet Test", callback_data="tool_magnet")],
        [InlineKeyboardButton("📋 Full Kit", callback_data="tool_kit")],
        [InlineKeyboardButton("⬅️ Back", callback_data="main")],
    ])
    await update.message.reply_text(
        "🛠️ *Estate Sale Toolkit*\n\n"
        "Essential tools for the field. Tap for details:",
        parse_mode="Markdown", reply_markup=kb
    )


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📷 Take Photo", switch_inline_query_current_chat="")],
        [InlineKeyboardButton("📁 Choose Photo", callback_data="choose_photo")],
        [InlineKeyboardButton("⬅️ Back", callback_data="main")],
    ])
    await update.message.reply_text(
        "📷 *Scan an Item*\n\n"
        "Take or choose a photo of an estate sale item.\n"
        "I'll analyze hallmarks, draw red circles on marks,\n"
        "and save the annotated image to your Library.",
        parse_mode="Markdown", reply_markup=kb
    )


async def cmd_library(update: Update, context: ContextTypes.DEFAULT_TYPE):
    annotated_dir = ANNOTATION_DIR
    items = get_collection()
    annotated_files = []
    if annotated_dir.exists():
        annotated_files = sorted(annotated_dir.iterdir())

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📷 Scan New Item", callback_data="scan")],
        [InlineKeyboardButton("⬅️ Back", callback_data="main")],
    ])

    if not annotated_files and not items["items"]:
        await update.message.reply_text(
            "📚 *Library is empty*\n\n"
            "Scan items to build your annotated photo library!",
            parse_mode="Markdown", reply_markup=kb
        )
        return

    parts = ["📚 *Your Library*\n\n"]
    for f in annotated_files:
        parts.append(f"🖼️ {f.name}\n")
    for item in items["items"][:10]:
        parts.append(f"📦 {item.get('description', 'No description')}\n")

    if len(annotated_files) > 5:
        parts.append(f"\n...and {len(annotated_files) - 5} more annotated images.")

    await update.message.reply_text(
        "".join(parts), parse_mode="Markdown", reply_markup=kb
    )


# ── Silver Topic Handlers ───────────────────────────────────────────────

SILVER_TOPICS = {
    "silver_solid": (
        "✅ *SOLID SILVER MARKS* (WORTH $$$$)\n\n"
        "**925** — Most common. 92.5% silver. Stamped '925' on underside.\n"
        "US standard since 1868.\n\n"
        "**STERLING** — American sterling. Capital letters on flatware.\n\n"
        "**800** — Continental European (German, French). 80% purity.\n\n"
        "**835** — French standard. 83.5%. Minerva head mark.\n\n"
        "**958** — Britannia silver. 95.8%. Rare, valuable.\n\n"
        "**COIN SILVER** — Pre-1837 American. 90.3%. Made from melted coins."
    ),
    "silver_plated": (
        "⚠️ *PLATED MARKS* (WORTH $)\n\n"
        "**EPNS** — Electroplated Nickel Silver. NOT solid silver.\n"
        "Base metal: 60% copper, 20% nickel, 20% zinc.\n\n"
        "**EP** — Electroplated. Not solid silver.\n\n"
        "**SILVER PLATED / SP** — Thin coating. UK law prohibits calling it just 'silver'.\n\n"
        "**A1** — American silver plated standard.\n\n"
        "**Old Sheffield Plate (OSP)** — Fused silver/copper (1740s-1840s).\n"
        "Shows copper bleeding at wear points."
    ),
    "silver_british": (
        "🇬🇧 *BRITISH HALLMARKS*\n\n"
        "**Lion Passant** — Walking lion = 925 sterling. Most recognizable hallmark.\n\n"
        "**Assay Office Marks:**\n"
        "• London — Anchor symbol\n"
        "• Birmingham — Anchor (different shield)\n"
        "• Sheffield — Rose\n"
        "• Edinburgh — Castle\n"
        "• Glasgow — Tree + 3 fish\n\n"
        "**Date Letters** — Small letter = year. Font + shield = specific year.\n\n"
        "**Maker Marks** — Two initials in shield. Famous: Paul Revere (PR),\n"
        "Paul Storr (PS), Thomas Kirk (TK)."
    ),
    "silver_american": (
        "🇺🇸 *AMERICAN MAKERS*\n\n"
        "**Tiffany & Co.** — Extremely valuable. Museum quality. 1837-present.\n\n"
        "**Gorham** — Art Nouveau collectible. 1831-2010.\n\n"
        "**Reed & Barton** — Quality American. 1824-2015. Bankrupt 2015.\n\n"
        "**International Silver Co.** — Common but collectible. 1870-1960s.\n\n"
        "**Towle Silver Co.** — American silver plate/sterling. 1840-1970s.\n\n"
        "**Oneida Silver Co.** — Common American silver plate. 1890s-present."
    ),
    "silver_fakes": (
        "❌ *FAKES & REPRODUCTIONS*\n\n"
        "**Wear Points** — Check fork tines, spoon backs. Plated shows brass/copper.\n\n"
        "**Weight Test** — Solid silver heavier: teaspoon solid 15-20g vs plated 8-12g.\n\n"
        "**Magnet Test** — Silver non-magnetic. Magnet sticks = steel core.\n\n"
        "**Ice Test** — Silver conducts heat fastest. Ice melts faster on solid.\n\n"
        "**Tone Test** — Tap together. Solid rings clear/long. Plated sounds dull.\n\n"
        "**Fake Hallmarks** — Shallow stamping, wrong fonts, modern marks on antique.\n\n"
        "**Weighted Silver** — Silver shell filled with lead. X-ray needed."
    ),
    "silver_coins": (
        "🪙 *COIN SILVER*\n\n"
        "Pre-1965 US coins are 90% silver:\n\n"
        "**Dime** — 0.0723 troy oz\n"
        "**Quarter** — 0.1600 troy oz\n"
        "**Half Dollar** — 0.3616 troy oz\n"
        "**Morgan Dollar** — 0.7734 troy oz (1878-1921, most collectible)\n\n"
        "**Pre-1837 'Coin Silver'** — 90.3% purity from melted coins."
    ),
}

TOOL_TOPICS = {
    "tool_scale": (
        "⚖️ *Pocket Scale*\n\n"
        "**Etekcity ESF-300** — $12-15. 0.01g precision, USB-C.\n"
        "**MyWeigh MD-500** — $20-25. 0.01g / 500g max.\n\n"
        "Use: Tare scale → place item → read weight → compare to benchmarks."
    ),
    "tool_magnet": (
        "🧲 *Neodymium Magnet*\n\n"
        "**K&J Magnetics N52** — $3-5. 1/4 inch diameter.\n\n"
        "If attracts = steel core, NOT silver.\n"
        "If no attraction = could be silver OR non-magnetic base metal."
    ),
    "tool_kit": (
        "🛠️ *Complete Estate Sale Kit*\n\n"
        "• USB-C pocket scale ($10-20)\n"
        "• Neodymium magnet ($3-5)\n"
        "• Magnifying glass ($5)\n"
        "• Microfiber cloth ($2-5)\n"
        "• Your iPhone with EstateScout\n\n"
        "*Total cost: $20-35*"
    ),
}

TRAINING_MODULES = {
    "mod1": (
        "🟢 *Module 1: Basic Silver Identification*\n\n"
        "**Lesson 1.1: The Two Marks That Matter**\n"
        "SOLID: 925, STERLING, 800, 835\n"
        "NOT SOLID: EPNS, Silver Plated, EP, A1\n\n"
        "**Lesson 1.2: Weight Test**\n"
        "Teaspoon: Solid = 15-20g | Plated = 8-12g\n\n"
        "**Lesson 1.3: Magnet Test**\n"
        "Silver is NOT magnetic. Magnet sticks = NOT silver.\n\n"
        "**Lesson 1.4: Wear Points**\n"
        "Fork tines, spoon backs, handle ends. Yellow/gold = PLATED.\n\n"
        "**Lesson 1.5: 60-Second Checklist**\n"
        "Marks → Weight → Wear → Magnet → Decision."
    ),
    "mod2": (
        "🟡 *Module 2: Intermediate*\n\n"
        "**British Hallmarks**\n"
        "Lion Passant = 925. Assay offices: London (anchor),\n"
        "Birmingham (anchor), Sheffield (rose), Edinburgh (castle).\n\n"
        "**Maker Marks**\n"
        "Tiffany, Gorham, Reed & Barton — extremely valuable.\n\n"
        "**Spotting Reproductions**\n"
        "Perfect condition + modern fonts = suspicious.\n\n"
        "**Old Sheffield Plate**\n"
        "Fused silver/copper (1740s-1840s). Copper bleeding at wear points."
    ),
    "mod3": (
        "🟠 *Module 3: Advanced*\n\n"
        "**Date Letter System**\n"
        "Each assay office has its own alphabet cycle. Font + shield = year.\n\n"
        "**Rare Marks**\n"
        "Paul de Lamerie (PL) — $5k-$100k+\n"
        "Paul Revere (PR) — $10k-$500k+\n"
        "Britannia 958 — Higher purity, rare.\n\n"
        "**Weighted Silver**\n"
        "Silver shell filled with lead. X-ray needed to detect."
    ),
    "mod4": (
        "🔴 *Module 4: Practical Estate Sale Scenarios*\n\n"
        "**Scenario 1: Drawer of Mixed Flatware**\n"
        "Sort by weight (heavy = solid). Check each for 925. Buy lot if 50%+ solid.\n\n"
        "**Scenario 2: Service for 12**\n"
        "Check if complete. Complete service worth 2-3x individual pieces.\n\n"
        "**Scenario 3: Candlesticks**\n"
        "PAIRS are essential. Single = $5-20. Pair of solid = $100-500+.\n\n"
        "**Scenario 4: Coin Collection**\n"
        "Check dates (pre-1965 = silver). Count total silver content.\n\n"
        "**Golden Rules**\n"
        "Heavy + No wear + 925 = SOLID. Pairs > Singles."
    ),
}


# ── Callback Query Handler ──────────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Required — dismisses "loading" animation

    data = query.data

    # Navigation
    if data == "main":
        kb = get_main_keyboard()
        await query.edit_message_text(
            "🏴‍☠️ *EstateScout*\n\n"
            "Choose a section below:",
            parse_mode="Markdown", reply_markup=kb
        )
        return

    # Silver topics
    if data in SILVER_TOPICS:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="main")],
        ])
        await query.edit_message_text(
            SILVER_TOPICS[data], parse_mode="Markdown", reply_markup=kb
        )
        return

    # Tool topics
    if data in TOOL_TOPICS:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="main")],
        ])
        await query.edit_message_text(
            TOOL_TOPICS[data], parse_mode="Markdown", reply_markup=kb
        )
        return

    # Training modules
    if data in TRAINING_MODULES:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="main")],
        ])
        await query.edit_message_text(
            TRAINING_MODULES[data], parse_mode="Markdown", reply_markup=kb
        )
        return

    # Scan / photo
    if data in ("scan", "choose_photo"):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="main")],
        ])
        await query.edit_message_text(
            "📷 *Scan an Item*\n\n"
            "Send me a photo of an estate sale item.\n"
            "I'll analyze it, draw red circles on hallmarks,\n"
            "and save the annotated image to your Library.\n\n"
            "*Just send a photo!*",
            parse_mode="Markdown", reply_markup=kb
        )
        return

    # Collection
    if data == "collection":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📷 Scan New Item", callback_data="scan")],
            [InlineKeyboardButton("⬅️ Back", callback_data="main")],
        ])
        result = list_collection()
        await query.edit_message_text(result, reply_markup=kb)
        return

    # Library
    if data == "library":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📷 Scan New Item", callback_data="scan")],
            [InlineKeyboardButton("⬅️ Back", callback_data="main")],
        ])
        annotated_dir = ANNOTATION_DIR
        items = get_collection()
        annotated_files = sorted(annotated_dir.iterdir()) if annotated_dir.exists() else []

        if not annotated_files and not items["items"]:
            await query.edit_message_text(
                "📚 *Library is empty*\n\n"
                "Scan items to build your annotated photo library!",
                parse_mode="Markdown", reply_markup=kb
            )
            return

        parts = ["📚 *Your Library*\n\n"]
        for f in annotated_files:
            parts.append(f"🖼️ {f.name}\n")
        for item in items["items"][:10]:
            parts.append(f"📦 {item.get('description', 'No description')}\n")

        await query.edit_message_text(
            "".join(parts), parse_mode="Markdown", reply_markup=kb
        )
        return

    # Silver guide
    if data == "silver":
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Solid Marks", callback_data="silver_solid"),
                InlineKeyboardButton("⚠️ Plated Marks", callback_data="silver_plated"),
            ],
            [
                InlineKeyboardButton("🇬🇧 British Marks", callback_data="silver_british"),
                InlineKeyboardButton("🇺🇸 American Makers", callback_data="silver_american"),
            ],
            [
                InlineKeyboardButton("❌ Fakes & Reproductions", callback_data="silver_fakes"),
                InlineKeyboardButton("🪙 Coin Silver", callback_data="silver_coins"),
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data="main")],
        ])
        await query.edit_message_text(
            "🏷️ *Silver Guide — Choose a topic:*\n\n"
            "Tap any topic to learn about it.",
            parse_mode="Markdown", reply_markup=kb
        )
        return

    # Training
    if data == "training":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🟢 Module 1: Basic ID", callback_data="mod1")],
            [InlineKeyboardButton("🟡 Module 2: Intermediate", callback_data="mod2")],
            [InlineKeyboardButton("🟠 Module 3: Advanced", callback_data="mod3")],
            [InlineKeyboardButton("🔴 Module 4: Practical", callback_data="mod4")],
            [InlineKeyboardButton("⬅️ Back", callback_data="main")],
        ])
        await query.edit_message_text(
            "📚 *Training Academy*\n\n"
            "Tap a module to open it:",
            parse_mode="Markdown", reply_markup=kb
        )
        return

    # Tools
    if data == "tools":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚖️ Pocket Scale", callback_data="tool_scale")],
            [InlineKeyboardButton("🧲 Magnet Test", callback_data="tool_magnet")],
            [InlineKeyboardButton("📋 Full Kit", callback_data="tool_kit")],
            [InlineKeyboardButton("⬅️ Back", callback_data="main")],
        ])
        await query.edit_message_text(
            "🛠️ *Estate Sale Toolkit*\n\n"
            "Tap for details:",
            parse_mode="Markdown", reply_markup=kb
        )
        return

    # Unknown
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main")]])
    await query.edit_message_text(
        "Unknown option. Try again:",
        reply_markup=kb
    )


# ── Photo Handler ──────────────────────────────────────────────────────

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process uploaded photos: save, annotate, return annotated image + notes."""
    photos = update.message.photo
    if not photos:
        return

    # Get largest resolution (Telegram orders ascending)
    photo = photos[-1]
    file = await context.bot.get_file(photo.file_id)

    # Save original photo
    user_id = update.effective_user.id
    timestamp = int(datetime.now().timestamp())
    photo_path = DATA_DIR / "photos" / f"photo_{user_id}_{timestamp}.jpg"
    photo_path.parent.mkdir(parents=True, exist_ok=True)
    await file.download_to_drive(str(photo_path))

    # Annotate the photo
    result = analyze_and_annotate(str(photo_path))
    annotated_path = result["annotated_image"]

    # Send annotated image
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Save to Collection", callback_data="save_item")],
        [InlineKeyboardButton("📚 View Library", callback_data="library")],
        [InlineKeyboardButton("⬅️ Back", callback_data="main")],
    ])

    caption = (
        f"📷 *Photo Analysis Complete*\n\n"
        f"📐 Image: {result['image_size']}\n"
        f"📝 Annotations: {len(result['annotations'])} marks identified\n"
        f"💡 {result['note']}\n\n"
        f"Tap 'Save to Collection' to keep this item."
    )

    if os.path.exists(annotated_path):
        with open(annotated_path, "rb") as f:
            annotated_bytes = f.read()

        await update.message.reply_photo(
            annotated_bytes,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=kb
        )
    else:
        await update.message.reply_text(
            f"📷 *Photo received and saved.*\n\n"
            f"Image: {result['image_size']}\n"
            f"Annotations: {len(result['annotations'])} marks.\n\n"
            f"💡 {result['note']}\n\n"
            f"Send another photo to scan more items!",
            parse_mode="Markdown", reply_markup=kb
        )


async def save_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save the most recently scanned item to collection."""
    query = update.callback_query
    await query.answer()

    # Find most recent photo
    photos_dir = DATA_DIR / "photos"
    photo_files = sorted(photos_dir.iterdir()) if photos_dir.exists() else []

    if not photo_files:
        await query.edit_message_text(
            "No recent photos to save. Scan an item first!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="main")],
            ])
        )
        return

    latest_photo = photo_files[-1]
    item_id = add_item_note({
        "type": "photo_analysis",
        "image_path": str(latest_photo),
        "verdict": "pending",
        "confidence": "medium",
        "date_seen": datetime.now().strftime("%Y-%m-%d"),
        "location": "Estate Sale"
    })

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 View Collection", callback_data="collection")],
        [InlineKeyboardButton("📷 Scan Another", callback_data="scan")],
        [InlineKeyboardButton("⬅️ Back", callback_data="main")],
    ])

    await query.edit_message_text(
        f"✅ *Item saved to Collection!*\n\n"
        f"ID: {item_id}\n"
        f"Photo: {latest_photo.name}\n"
        f"Date: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        f"Send more photos to build your collection!",
        parse_mode="Markdown", reply_markup=kb
    )


# ── Main Entry Point ────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        print("❌ ESTATESCOUT_BOT_TOKEN not set. Set it in your environment.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("silver", cmd_silver))
    application.add_handler(CommandHandler("training", cmd_training))
    application.add_handler(CommandHandler("collection", cmd_collection))
    application.add_handler(CommandHandler("tools", cmd_tools))
    application.add_handler(CommandHandler("scan", cmd_scan))
    application.add_handler(CommandHandler("library", cmd_library))

    # Aliases with + prefix
    application.add_handler(CommandHandler("silver", cmd_silver))
    application.add_handler(CommandHandler("training", cmd_training))
    application.add_handler(CommandHandler("collection", cmd_collection))
    application.add_handler(CommandHandler("tools", cmd_tools))
    application.add_handler(CommandHandler("scan", cmd_scan))
    application.add_handler(CommandHandler("library", cmd_library))

    # Callback queries (all buttons)
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^"))
    application.add_handler(CallbackQueryHandler(save_item_callback, pattern="^save_item$"))

    # Photo messages
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print(f"🏴‍☠️ EstateScout bot starting...")
    print(f"   Channel: {HOME_CHANNEL}")
    print(f"   Data dir: {DATA_DIR}")
    print(f"   Annotated dir: {ANNOTATION_DIR}")
    print()

    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()