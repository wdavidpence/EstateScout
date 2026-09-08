"""EstateScout Collection Manager

Manages saving and retrieving notes about items user shows me.
"""

import json
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent / "data"
NOTES_FILE = DATA_DIR / "items.json"


def load_notes():
    """Load existing notes from JSON file."""
    if NOTES_FILE.exists():
        with open(NOTES_FILE) as f:
            return json.load(f)
    return {"items": [], "total": 0}


def save_notes(notes):
    """Save notes to JSON file."""
    NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(NOTES_FILE, 'w') as f:
        json.dump(notes, f, indent=2)


def add_item_note(item_data):
    """Add a new item note to the collection."""
    notes = load_notes()
    
    # Generate unique ID
    item_id = f"item_{len(notes['items']) + 1:04d}"
    item_data["id"] = item_id
    item_data["date_added"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    notes["items"].append(item_data)
    notes["total"] = len(notes["items"])
    notes["last_updated"] = item_data.get("date_seen", datetime.now().strftime("%Y-%m-%d"))
    
    save_notes(notes)
    return item_id


def get_collection():
    """Get all saved items."""
    notes = load_notes()
    return notes


def get_item(item_id):
    """Get a specific item by ID."""
    notes = load_notes()
    for item in notes["items"]:
        if item.get("id") == item_id:
            return item
    return None


def delete_item(item_id):
    """Delete an item from collection."""
    notes = load_notes()
    original_count = len(notes["items"])
    notes["items"] = [item for item in notes["items"] if item.get("id") != item_id]
    notes["total"] = len(notes["items"])
    
    if len(notes["items"]) < original_count:
        save_notes(notes)
        return True
    return False


def format_item_for_display(item):
    """Format an item for Telegram display."""
    lines = []
    lines.append(f"📦 **{item.get('type', 'Unknown').title()}**")
    lines.append(f"ID: {item.get('id', 'N/A')}")
    
    if item.get("description"):
        lines.append(f"📝 {item['description']}")
    
    if item.get("marks_found"):
        lines.append(f"🏷️ Marks: {item['marks_found']}")
    
    if item.get("weight_grams"):
        lines.append(f"⚖️ Weight: {item['weight_grams']}g")
    
    if item.get("magnet_test"):
        lines.append(f"🧲 Magnet: {item['magnet_test']}")
    
    if item.get("visual_condition"):
        lines.append(f"✨ Condition: {item['visual_condition']}")
    
    if item.get("wear_points"):
        lines.append(f"⚠️ Wear: {item['wear_points']}")
    
    if item.get("verdict"):
        verdict_emoji = {"solid silver": "✅", "plated": "⚠️", "fake": "❌", "unknown": "❓"}
        emoji = verdict_emoji.get(item["verdict"], "🔍")
        lines.append(f"{emoji} Verdict: {item['verdict'].title()}")
    
    if item.get("confidence"):
        lines.append(f"🎯 Confidence: {item['confidence']}")
    
    if item.get("estimated_value_range"):
        lines.append(f"💰 Value: {item['estimated_value_range']}")
    
    if item.get("date_seen"):
        lines.append(f"📅 Seen: {item['date_seen']}")
    
    if item.get("location"):
        lines.append(f"📍 Location: {item['location']}")
    
    return "\n".join(lines)


def list_collection():
    """List all items in collection with summary."""
    notes = load_notes()
    
    if not notes["items"]:
        return "📭 Your collection is empty.\n\nSend me a photo of an item and I'll analyze it and save notes!"
    
    lines = []
    lines.append(f"📚 **Your Collection ({notes['total']} items)**\n")
    
    for item in notes["items"]:
        verdict = item.get("verdict", "unknown")
        emoji = {"solid silver": "✅", "plated": "⚠️", "fake": "❌", "unknown": "❓"}.get(verdict, "🔍")
        
        desc = item.get("description", "No description")[:50]
        lines.append(f"{emoji} #{item.get('id', '?')} {desc}")
    
    lines.append("\n💡 Send me a photo to add more items!")
    
    return "\n".join(lines)


def save_item_from_analysis(image_path, analysis_result, user_notes=None):
    """Save item notes from image analysis."""
    item_data = {
        "type": "photo_analysis",
        "image_path": str(image_path),
        "annotated_image": analysis_result.get("annotated_image"),
        "notes": user_notes or "",
        "verdict": "pending_analysis",
        "confidence": "medium"
    }
    
    item_id = add_item_note(item_data)
    return item_id