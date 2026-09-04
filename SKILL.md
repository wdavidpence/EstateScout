---
name: estate-scout
description: "Estate auction assistant — authenticate items, identify hallmarks, calculate max bids. Send photos or descriptions."
version: 1.0.0
---

# EstateScout

Estate auction floor assistant. Authenticate items, identify hallmarks, calculate max bids.

## Trigger
User sends photos of items, descriptions of items, or asks about authentication/bidding at estate sales/auctions.

## Quick Reference

### Silver Hallmarks (US & UK)
- **Sterling Silver (US):** 925 stamp, "STERLING", "925", "925/1000" — 92.5% pure silver
- **Britannia Silver (UK):** 958 stamp — 95.8% pure silver
- **Coin Silver (US):** 835 stamp — 83.5% pure silver (older US, pre-1868)
- **Silver Plate (EPNS):** "EPNS", "EP", "A1", "ALP" — thin silver over base metal
- **Silver Plate (no stamp):** Heavy, magnetic (base is nickel silver or copper)
- **Solid Silver Tests:**
  - Magnet: solid silver is NON-magnetic
  - Ice test: silver conducts heat fast — ice melts quickly on surface
  - Sound: solid silver rings with long clear tone; plated is dull thud
  - Acid test kit: nitric acid turns green = base metal, milky = silver plate, cream = sterling

### Gold Hallmarks
- **24K:** 999, "24K" — pure gold (soft, usually not wearable)
- **18K:** 750 stamp — 75% gold
- **14K:** 585 stamp — 58.5% gold (most common US)
- **10K:** 417 stamp — 41.7% gold (minimum US "gold")
- **9K:** 375 stamp — 37.5% gold (UK minimum)
- **Gold Filled:** "1/20 14K GF" — thick gold layer over base metal
- **Gold Plated:** "GP", "HGP", "RGP" — thin gold over base metal
- **Tests:** magnet (gold is non-magnetic), density test, acid test

### Jewelry Markers to Know
- **Platinum:** "PT", "PLAT", "950", "900" — very heavy for size
- **Palladium:** "PD", "950" — light for a platinum, similar color
- **Copper/Brass:** magnetic test fails, green patina on skin, reddish color
- **Stainless Steel:** magnetic (usually), very heavy, "SS" stamp
- **Base Metal Alloys:** magnetic, light weight, cheap appearance

### Coin Grading Quick Reference
- **MS-65+** (Mint State): Uncirculated, brilliant luster, no contact marks
- **AU-55** (About Uncirculated): Slight wear on highest points
- **VF-30** (Very Fine): Moderate wear, details clear
- **F-12** (Fine): Significant wear, all major details present
- **VG-8** (Very Good): Heavy wear, some details flat
- **G-4** (Good): Very worn, date/legend only clear
- **AG-3** (About Good): Barely recognizable, heavily worn

### Furniture Styles
- **Chippendale (1733-1790):** Cabriole legs, ball & claw feet, ornate carving
- **Hepplewhite (1765-1785):** Shield backs, tapered legs, feather motifs
- **Sheraton (1790-1810):** Straight legs, rectangular forms, inlay work
- **Federal (1780-1825):** Neoclassical, fan motifs, urn shapes
- **Victorian (1837-1901):** Heavy, ornate, dark wood, carved details
- **Arts & Crafts (1880-1920):** Simple, exposed joinery, mission style
- **Mid-Century Modern (1950-1965):** Clean lines, teak/walnut, organic curves

### Art Authentication Clues
- **Signature:** Compare to known examples, check for consistency
- **Canvas:** Hand-stretched vs machine-stretched (vintage = hand)
- **Frame:** Original frame adds value; check for period-appropriate styles
- **Patina:** Natural aging vs artificial distressing
- **Back of canvas:** Labels, stamps, exhibition history
- **Medium:** Oil on canvas, watercolor, print — know the differences

## Bidding Calculator

When user provides:
- Item description
- Comparable sold price (or I search for it)
- Condition assessment

Output:
- **Max Bid** (10-20% below comp for profit margin)
- **Target Buy Price** (20-30% below comp for good deal)
- **Walk Away Price** (30-40% below comp)
- Risk assessment (high/medium/low)

## Workflow

1. **Receive item** — photo or description from user
2. **Identify** — hallmarks, stamps, materials, style
3. **Authenticate** — real vs fake indicators
4. **Research comps** — search sold listings for value
5. **Advise** — max bid, target price, confidence level
6. **Log** — save item photo + data for future reference

## Photo Analysis

When user sends a photo:
1. Describe what you see in the photo
2. Identify any stamps, hallmarks, markings
3. Assess condition from visual clues
4. Provide authentication guidance
5. Suggest comparable searches

## Memory

Save important items, learned patterns, and user preferences:
- Items user has bought/sold
- Common fakes in their area
- Their bidding style and budget range
- Specific collectors' marks they encounter