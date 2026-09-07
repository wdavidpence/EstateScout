"""EstateScout Image Annotation System

When user sends a photo, this module:
1. Analyzes the image for hallmarks, marks, wear points
2. Creates an annotated version with red circles/boxes/arrows
3. Returns the annotated image + text notes

Uses PIL/Pillow for image annotation.
"""

import os
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
NOTES_FILE = DATA_DIR / "items.json"

# Colors
RED = (255, 0, 0)
YELLOW = (255, 255, 0)
GREEN = (0, 255, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


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
    item_data["date_added"] = notes.get("last_updated", "Unknown")
    
    notes["items"].append(item_data)
    notes["total"] = len(notes["items"])
    notes["last_updated"] = item_data.get("date_seen", "Unknown")
    
    save_notes(notes)
    return item_id


def get_collection():
    """Get all saved items."""
    notes = load_notes()
    return notes


def annotate_image(image_path, annotations):
    """
    Annotate an image with red circles/boxes/arrows.
    
    Args:
        image_path: Path to the original image
        annotations: List of annotation dicts with:
            - type: 'circle', 'box', 'arrow'
            - coordinates: (x1, y1, x2, y2) or center + radius
            - label: Text to display
            - color: (R, G, B) tuple
    
    Returns:
        Path to annotated image
    """
    # Open original image
    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)
    
    # Try to load a font (use default if not available)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
    except:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        except:
            font = ImageFont.load_default()
    
    for annotation in annotations:
        ann_type = annotation.get("type", "circle")
        color = annotation.get("color", RED)
        label = annotation.get("label", "")
        
        if ann_type == "circle":
            # Draw circle around hallmark/marks
            x1, y1, x2, y2 = annotation["coordinates"]
            draw.ellipse([x1, y1, x2, y2], outline=color, width=3)
            
            # Add label if provided
            if label:
                bbox = draw.textbbox((x1, y2 + 5), label, font=font)
                draw.rectangle(bbox, fill=color)
                draw.text((x1 + 2, y2 + 7), label, fill=WHITE, font=font)
        
        elif ann_type == "box":
            # Draw box around wear points
            x1, y1, x2, y2 = annotation["coordinates"]
            draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
            
            # Add label if provided
            if label:
                bbox = draw.textbbox((x1, y1 - 25), label, font=font)
                draw.rectangle(bbox, fill=color)
                draw.text((x1 + 2, y1 - 23), label, fill=WHITE, font=font)
        
        elif ann_type == "arrow":
            # Draw arrow from label to mark
            x1, y1 = annotation["start"]
            x2, y2 = annotation["end"]
            
            # Draw line (arrow shaft)
            draw.line([(x1, y1), (x2, y2)], fill=color, width=3)
            
            # Draw arrowhead
            arrow_size = 10
            angle = 30  # degrees
            
            import math
            rad = math.radians(angle)
            
            # Calculate arrowhead points
            dx, dy = x2 - x1, y2 - y1
            length = math.sqrt(dx*dx + dy*dy)
            if length > 0:
                ux, uy = dx/length, dy/length
                
                # Perpendicular vector
                px, py = -uy, ux
                
                # Arrowhead points
                p1 = (x2 - ux * arrow_size + px * arrow_size, 
                      y2 - uy * arrow_size + py * arrow_size)
                p2 = (x2 - ux * arrow_size - px * arrow_size, 
                      y2 - uy * arrow_size - py * arrow_size)
                
                draw.polygon([(x2, y2), p1, p2], fill=color)
            
            # Add label at start point
            if label:
                bbox = draw.textbbox((x1 - 50, y1 - 20), label, font=font, fill=color)
                draw.rectangle(bbox, fill=color)
                draw.text((x1 - 48, y1 - 18), label, fill=WHITE, font=font)
    
    # Save annotated image
    output_path = DATA_DIR / "annotated_images" / f"annotated_{os.path.basename(image_path)}"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    img.save(output_path)
    return str(output_path)


def analyze_and_annotate(image_path, user_description=None):
    """
    Analyze an image and create annotations.
    
    This is a placeholder - in production, this would use computer vision
    to detect hallmarks, marks, wear points automatically.
    
    For now, we'll create annotations based on user description or
    manual specification.
    
    Args:
        image_path: Path to the image
        user_description: Optional description from user
    
    Returns:
        Dict with annotation info and path to annotated image
    """
    # Load image to get dimensions for coordinate calculations
    img = Image.open(image_path)
    width, height = img.size
    
    # Default annotations (placeholder - would be AI-detected in production)
    annotations = []
    
    # Example: If user mentions a hallmark, we'd annotate it
    # For now, create a generic annotation structure
    
    if user_description:
        # Parse user description to identify what to annotate
        desc_lower = user_description.lower()
        
        if "925" in desc_lower or "sterling" in desc_lower:
            # Annotate area where hallmark would be (bottom center)
            annotations.append({
                "type": "circle",
                "coordinates": (width//2 - 50, height - 100, width//2 + 50, height - 30),
                "label": "Hallmark: 925/Sterling",
                "color": RED
            })
        
        if "epns" in desc_lower or "plated" in desc_lower:
            annotations.append({
                "type": "circle",
                "coordinates": (width//2 - 60, height - 150, width//2 + 60, height - 80),
                "label": "Mark: EPNS/Plated",
                "color": YELLOW
            })
        
        if "wear" in desc_lower or "yellow" in desc_lower:
            # Annotate wear points (tips of fork/spoon)
            annotations.append({
                "type": "box",
                "coordinates": (width//4, height//4, width//4 + 100, height//4 + 80),
                "label": "Wear Point",
                "color": RED
            })
    
    # If no specific annotations, create a generic one
    if not annotations:
        annotations.append({
            "type": "circle",
            "coordinates": (width//2 - 50, height//2 - 30, width//2 + 50, height//2 + 30),
            "label": "Item Analyzed",
            "color": GREEN
        })
    
    # Create annotated image
    annotated_path = annotate_image(image_path, annotations)
    
    return {
        "annotated_image": annotated_path,
        "annotations": annotations,
        "image_size": f"{width}x{height}",
        "note": "Image annotated with red circles/boxes around identified features"
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
