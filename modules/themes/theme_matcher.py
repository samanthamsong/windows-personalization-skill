"""
Theme matcher — semantic matching of user prompts against the MSIX theme library.

Scores each catalog theme by keyword overlap with the user's prompt/theme spec,
returns the best match with a confidence score. Falls back to custom generation
if confidence is below threshold.
"""

import json
import math
import os
import re


CATALOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "library", "catalog.json")

# Minimum confidence to consider a library match (0–1)
DEFAULT_THRESHOLD = 0.3


def _load_catalog() -> list:
    """Load the theme catalog from disk."""
    if not os.path.exists(CATALOG_PATH):
        return []
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("themes", [])


def _tokenize(text: str) -> set:
    """Split text into lowercase keyword tokens."""
    return set(re.findall(r'[a-z0-9]+', text.lower()))


def _color_distance(hex1: str, hex2: str) -> float:
    """Euclidean distance between two hex colors, normalized to 0–1."""
    def parse(h):
        h = h.lstrip('#')
        if len(h) != 6:
            return (0, 0, 0)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    r1, g1, b1 = parse(hex1)
    r2, g2, b2 = parse(hex2)
    max_dist = math.sqrt(255**2 * 3)
    dist = math.sqrt((r1-r2)**2 + (g1-g2)**2 + (b1-b2)**2)
    return dist / max_dist


def score_theme(theme: dict, prompt_tokens: set,
                spec_color: str = None, spec_mode: str = None) -> float:
    """Score a catalog theme against user intent. Returns 0–1."""
    score = 0.0
    max_score = 0.0

    # --- Tag overlap (weight: 5) ---
    tags = set(t.lower() for t in theme.get("tags", []))
    name_tokens = _tokenize(theme.get("name", ""))
    all_theme_tokens = tags | name_tokens

    if all_theme_tokens:
        overlap = len(prompt_tokens & all_theme_tokens)
        tag_score = overlap / max(1, min(len(prompt_tokens), len(all_theme_tokens)))
        score += tag_score * 5.0
    max_score += 5.0

    # --- Name substring match (weight: 3) ---
    theme_name_lower = theme.get("name", "").lower()
    # Check if any multi-word sequence from the prompt appears in the name
    prompt_text = " ".join(sorted(prompt_tokens))
    name_match = 0.0
    for token in prompt_tokens:
        if token in theme_name_lower:
            name_match += 1.0
    if prompt_tokens:
        name_match /= len(prompt_tokens)
    score += name_match * 3.0
    max_score += 3.0

    # --- Color proximity (weight: 2, only if user specified a color) ---
    if spec_color and theme.get("accent_color"):
        color_sim = 1.0 - _color_distance(spec_color, theme["accent_color"])
        score += color_sim * 2.0
        max_score += 2.0

    # --- Mode match (weight: 1, only if user specified a mode) ---
    if spec_mode and theme.get("mode"):
        if spec_mode.lower() == theme["mode"].lower():
            score += 1.0
        max_score += 1.0

    return score / max_score if max_score > 0 else 0.0


def find_match(prompt: str = None, spec: dict = None,
               threshold: float = DEFAULT_THRESHOLD) -> dict | None:
    """Find the best matching theme from the library.

    Args:
        prompt: Natural language prompt (e.g. "spring flowers")
        spec: Theme spec dict (may contain name, accent_color, mode)
        threshold: Minimum confidence to return a match

    Returns:
        dict with 'theme' (catalog entry), 'confidence' (0–1), and 'reason'
        or None if no match above threshold.
    """
    catalog = _load_catalog()
    if not catalog:
        return None

    # Build tokens from prompt and/or spec name
    tokens = set()
    if prompt:
        tokens |= _tokenize(prompt)
    if spec:
        if spec.get("name"):
            tokens |= _tokenize(spec["name"])

    if not tokens:
        return None

    spec_color = spec.get("accent_color") if spec else None
    spec_mode = spec.get("mode") if spec else None

    best_theme = None
    best_score = 0.0

    for theme in catalog:
        s = score_theme(theme, tokens, spec_color, spec_mode)
        if s > best_score:
            best_score = s
            best_theme = theme

    if best_theme and best_score >= threshold:
        return {
            "theme": best_theme,
            "confidence": round(best_score, 3),
            "reason": f"Matched '{best_theme['name']}' with confidence {best_score:.1%}"
        }

    return None


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python theme_matcher.py <prompt>")
        print("  e.g. python theme_matcher.py 'spring flowers'")
        sys.exit(1)

    prompt = " ".join(sys.argv[1:])
    result = find_match(prompt=prompt)
    if result:
        print(f"✅ {result['reason']}")
        print(json.dumps(result["theme"], indent=2))
    else:
        print(f"❌ No library match for: {prompt}")
        print("   Would fall back to custom theme generation.")
