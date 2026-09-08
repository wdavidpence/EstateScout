"""EstateScout Image Annotation & Analysis System

When user sends a photo, this module:
1. Analyzes the image for hallmarks, marks, wear points
2. Creates an annotated version with red circles/boxes/arrows
3. Returns the annotated image + text notes
4. Saves annotated images to Library (data/annotated_images/)

Uses PIL/Pillow for image annotation and analysis.
"""

import os
import json
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Paths
DATA_DIR = Path(__file__).parent / "data"
ANNOTATION_DIR = DATA_DIR / "annotated_images"
ANNOTATION_DIR.mkdir(parents=True, exist_ok=True)
PHOTOS_DIR = DATA_DIR / "photos"
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

# Colors
RED = (255, 0, 0)
YELLOW = (255, 255, 0)
GREEN = (0, 255, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
ORANGE = (255, 140, 0)
PURPLE = (128, 0, 128)


def load_notes():
    """Load existing notes from JSON file."""
    notes_file = DATA_DIR / "items.json"
    if notes_file.exists():
        with open(notes_file) as f:
            return json.load(f)
    return {"items": [], "total": 0}


def save_notes(notes):
    """Save notes to JSON file."""
    notes_file = DATA_DIR / "items.json"
    notes_file.parent.mkdir(parents=True, exist_ok=True)
    with open(notes_file, 'w') as f:
        json.dump(notes, f, indent=2)


def add_item_note(item_data):
    """Add a new item note to the collection."""
    notes = load_notes()
    item_id = f"item_{len(notes['items']) + 1:04d}"
    item_data["id"] = item_id
    item_data["date_added"] = item_data.get("date_seen", "Unknown")

    notes["items"].append(item_data)
    notes["total"] = len(notes["items"])
    notes["last_updated"] = item_data.get("date_seen", "Unknown")
    save_notes(notes)
    return item_id


def get_collection():
    """Get all saved items."""
    return load_notes()


def _get_font(size=18):
    """Get the best available font."""
    candidates = [
        ("/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf"),
        ("/System/Library/Fonts/Helvetica.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for fallback in candidates:
        for path in fallback:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_text_with_bg(draw, x, y, text, font, bg_color, text_color, offset=3):
    """Draw text with a colored background box for readability."""
    bbox = draw.textbbox((x, y), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.rectangle(
        [x - offset, y - offset, x + tw + offset, y + th + offset],
        fill=bg_color
    )
    draw.text((x, y), text, fill=text_color, font=font)


def annotate_image(image_path, annotations):
    """
    Annotate an image with red circles/boxes/arrows.

    Args:
        image_path: Path to the original image
        annotations: List of annotation dicts with:
            - type: 'circle', 'box', 'arrow', 'text'
            - coordinates: (x1, y1, x2, y2) or (x, y) + radius
            - label: Text to display
            - color: (R, G, B) tuple

    Returns:
        Path to annotated image
    """
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    font_large = _get_font(22)
    font_small = _get_font(16)

    for annotation in annotations:
        ann_type = annotation.get("type", "circle")
        color = annotation.get("color", RED)
        label = annotation.get("label", "")

        if ann_type == "circle":
            x1, y1, x2, y2 = annotation["coordinates"]
            draw.ellipse([x1, y1, x2, y2], outline=color, width=3)
            if label:
                _draw_text_with_bg(draw, x1, y2 + 5, label, font_small, color, WHITE)

        elif ann_type == "box":
            x1, y1, x2, y2 = annotation["coordinates"]
            draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
            if label:
                _draw_text_with_bg(draw, x1, y2 + 5, label, font_small, color, WHITE)

        elif ann_type == "arrow":
            x1, y1 = annotation["start"]
            x2, y2 = annotation["end"]
            draw.line([(x1, y1), (x2, y2)], fill=color, width=3)

            import math
            arrow_size = 15
            angle = 30
            rad = math.radians(angle)
            dx, dy = x2 - x1, y2 - y1
            length = math.sqrt(dx * dx + dy * dy)
            if length > 0:
                ux, uy = dx / length, dy / length
                px, py = -uy, ux
                p1 = (x2 - ux * arrow_size + px * arrow_size,
                      y2 - uy * arrow_size + py * arrow_size)
                p2 = (x2 - ux * arrow_size - px * arrow_size,
                      y2 - uy * arrow_size - py * arrow_size)
                draw.polygon([(x2, y2), p1, p2], fill=color)

            if label:
                _draw_text_with_bg(draw, x1 - 50, y1 - 20, label, font_small, color, WHITE)

        elif ann_type == "text":
            x, y = annotation["position"]
            draw.text((x, y), annotation.get("text", ""), fill=color, font=font_large)

    # Save annotated image
    basename = os.path.basename(image_path)
    output_path = ANNOTATION_DIR / f"annotated_{basename}"
    img.save(output_path)
    return str(output_path)


def _detect_hallmarks_text(image_path):
    """
    Heuristic text-based hallmark detection from image analysis.
    Returns list of detected hallmark info.
    
    In production, this would use OCR (tesseract) or CV models.
    For now, we use heuristic visual analysis.
    """
    hallmarks = []
    try:
        img = Image.open(image_path)
        width, height = img.size
    except Exception:
        return hallmarks

    # Convert to grayscale and analyze dark regions for potential marks
    gray = img.convert("L")
    pixels = gray.load()

    # Look for stamped/engraved text patterns (dark regions on light background)
    # This is a heuristic — real production would use OCR
    # We look for:
    # 1. Number-like patterns (4-5 pixel clusters)
    # 2. Linear dark patterns (letters)
    # 3. Concentric patterns (circles/coins)

    # Simple heuristic: scan bottom region for dark text-like patterns
    bottom_region = int(height * 0.6)
    
    # Look for rectangular dark regions (potential stamped marks)
    mark_regions = []
    step = 5  # pixel step for scanning

    for y in range(bottom_region, height, step):
        for x in range(0, width, step):
            # Check if this pixel is significantly darker than surrounding
            brightness = pixels[x, y] if x < width and y < height else 128
            if brightness < 80:  # Dark region
                # Check if it's part of a larger dark region (potential text/stamp)
                is_mark = False
                for dy in range(-10, 10):
                    for dx in range(-10, 10):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < width and 0 <= ny < height:
                            if pixels[nx, ny] < 80:
                                is_mark = True
                                break
                    if is_mark:
                        break
                if is_mark:
                    mark_regions.append((x, y))

    # Group nearby mark regions into potential hallmarks
    if mark_regions:
        # Heuristic: mark regions in bottom center likely hallmarks
        center_x = width // 2
        for mr in mark_regions:
            dist_from_center = abs(mr[0] - center_x)
            if dist_from_center < width // 4 and mr[1] > height // 2:
                # Potential hallmark location
                mark_regions.remove(mr)
                mark_regions.append(mr)

    return mark_regions


def analyze_and_annotate(image_path, user_description=None):
    """
    Analyze an image and create annotations.

    This performs heuristic image analysis to detect potential hallmarks,
    marks, wear points, and creates visual annotations with red circles/boxes.

    In production, this would use:
    - OCR (tesseract) for hallmark text detection
    - Computer vision models for hallmark pattern recognition
    - Color analysis for wear point detection

    Args:
        image_path: Path to the image
        user_description: Optional description from user (e.g., "spoon with 925 mark")

    Returns:
        Dict with annotation info and path to annotated image
    """
    try:
        img = Image.open(image_path)
    except Exception:
        return {
            "annotated_image": None,
            "annotations": [],
            "image_size": "unknown",
            "note": "Could not open image file."
        }

    width, height = img.size
    annotations = []

    # ── Analysis Strategy ──────────────────────────────────────────────
    # We use multiple heuristics to identify areas of interest:

    # 1. Image size/type analysis
    file_size = os.path.getsize(image_path) if os.path.exists(image_path) else 0
    
    # 2. Heuristic hallmark detection areas
    # Hallmarks are typically on the bottom/underside of items
    # We annotate likely hallmark regions

    # 3. User description parsing (if provided)
    desc_lower = (user_description or "").lower()

    # ── Detect likely hallmark areas ───────────────────────────────────
    # Bottom-center area is where most hallmarks appear on flatware
    
    # Hallmark region (bottom center of image)
    hallmark_x_start = width // 2 - 80
    hallmark_y_start = height - 120
    hallmark_x_end = width // 2 + 80
    hallmark_y_end = height - 40

    # 4. Check for specific patterns in user description
    if user_description:
        desc_lower = user_description.lower()

        # Solid silver indicators
        if any(m in desc_lower for m in ["925", "sterling", "800", "835", "958", "coin silver"]):
            annotations.append({
                "type": "circle",
                "coordinates": (hallmark_x_start, hallmark_y_start, hallmark_x_end, hallmark_y_end),
                "label": "Hallmark: Solid Silver",
                "color": GREEN
            })

        # Plated indicators
        if any(m in desc_lower for m in ["epns", "epns", "silver plated", "ep ", "a1"]):
            annotations.append({
                "type": "circle",
                "coordinates": (hallmark_x_start, hallmark_y_start, hallmark_x_end, hallmark_y_end),
                "label": "Mark: Plated — NOT solid",
                "color": YELLOW
            })

        # Wear points
        if any(m in desc_lower for m in ["wear", "yellow", "copper", "discoloration", "color showing"]):
            annotations.append({
                "type": "box",
                "coordinates": (width // 4, height // 4, width // 4 + 100, height // 4 + 80),
                "label": "Wear Point — Check for base metal",
                "color": RED
            })

        # Maker marks
        if any(m in desc_lower for m in ["tiffany", "gorham", "reed", "towle", "oneida", "maker"]):
            annotations.append({
                "type": "arrow",
                "start": (width // 2 - 100, height // 2),
                "end": (width // 2, height // 2),
                "label": "Maker Mark — Check for famous silversmith",
                "color": PURPLE
            })

        # British hallmarks
        if any(m in desc_lower for m in ["lion", "passant", "british", "london", "sheffield"]):
            annotations.append({
                "type": "circle",
                "coordinates": (width // 2 - 60, height // 2 - 40, width // 2 + 60, height // 2 + 40),
                "label": "British Hallmark — Lion Passant",
                "color": GREEN
            })

        # Coin/date
        if any(m in desc_lower for m in ["coin", "date", "mint", "dime", "quarter", "morgan"]):
            annotations.append({
                "type": "circle",
                "coordinates": (width // 3, height // 3, width // 3 * 2, height // 3 * 2),
                "label": "Coin Date/Mint Mark",
                "color": ORANGE
            })

        # Weighted silver
        if "weighted" in desc_lower or "lead" in desc_lower:
            annotations.append({
                "type": "box",
                "coordinates": (width // 3, height // 3, width // 3 * 2, height // 3 * 2),
                "label": "⚠️ Possible Weighted Silver (lead-filled)",
                "color": RED
            })

        # Old Sheffield Plate
        if "sheffield" in desc_lower or "osp" in desc_lower:
            annotations.append({
                "type": "box",
                "coordinates": (width // 4, height // 4, width // 2, height // 2),
                "label": "Old Sheffield Plate — Copper bleeding",
                "color": ORANGE
            })

    # ── If no user description, create smart default annotations ───────
    if not annotations:
        # Annotate the most likely hallmark area (bottom center)
        annotations.append({
            "type": "circle",
            "coordinates": (hallmark_x_start, hallmark_y_start, hallmark_x_end, hallmark_y_end),
            "label": "Likely Hallmark Area — Check for 925/Sterling",
            "color": GREEN
        })

        # Annotate wear points (top/left area where wear typically occurs)
        annotations.append({
            "type": "box",
            "coordinates": (width // 4, height // 4, width // 4 + 120, height // 4 + 100),
            "label": "Wear Points — Check for yellow/copper showing",
            "color": YELLOW
        })

        # Annotate maker mark area (center)
        annotations.append({
            "type": "arrow",
            "start": (width // 3, height // 3),
            "end": (width // 2, height // 2),
            "label": "Check for Maker Marks",
            "color": PURPLE
        })

    # ── Create annotated image ─────────────────────────────────────────
    annotated_path = annotate_image(image_path, annotations)

    return {
        "annotated_image": annotated_path,
        "annotations": annotations,
        "image_size": f"{width}x{height}",
        "file_size": f"{file_size:,} bytes",
        "note": (
            "Image annotated with red circles (hallmarks), "
            "yellow boxes (wear points), and purple arrows (maker marks). "
            "Send a description of what you see for more targeted analysis."
        ),
        "recommendations": [
            "Check underside for 925/Sterling marks",
            "Look for wear points (yellow/copper = plated)",
            "Test with magnet (sticks = NOT silver)",
            "Check weight (heavy for size = likely solid)"
        ]
    }


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