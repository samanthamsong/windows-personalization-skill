"""
Extract dominant colors from Spotify album art.

Uses Pillow k-means clustering to find the most prominent colors
in an album cover image.
"""

import io
import requests
from PIL import Image
from collections import Counter


def fetch_image(url):
    """Download an image from a URL and return a PIL Image."""
    resp = requests.get(url, timeout=5)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content))


def extract_colors(image, num_colors=5):
    """
    Extract dominant colors from a PIL Image using quantization.
    Returns list of (r, g, b) tuples sorted by frequency.
    """
    img = image.copy()
    img = img.resize((80, 80))
    img = img.convert('RGB')

    # Quantize to reduce to num_colors * 2 to get better candidates
    quantized = img.quantize(colors=num_colors * 2, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette()
    color_counts = Counter(quantized.getdata())

    # Build (count, color) pairs from palette
    colors = []
    for idx, count in color_counts.most_common():
        r, g, b = palette[idx * 3], palette[idx * 3 + 1], palette[idx * 3 + 2]
        # Skip very dark (near-black) and very light (near-white) colors
        brightness = (r + g + b) / 3
        if 20 < brightness < 240:
            colors.append(((r, g, b), count))

    # Sort by count descending
    colors.sort(key=lambda x: -x[1])

    # Return just the RGB tuples
    result = [c[0] for c in colors[:num_colors]]

    # Pad with fallback if we filtered too aggressively
    if len(result) < 2:
        result = [(r, g, b) for (r, g, b), _ in
                  sorted(Counter(quantized.getdata()).most_common(),
                         key=lambda x: -x[1])[:num_colors]]
        result = [(palette[idx * 3], palette[idx * 3 + 1], palette[idx * 3 + 2])
                  for idx in [c[0] for c in Counter(quantized.getdata()).most_common()[:num_colors]]]

    return result[:num_colors]


def colors_from_url(url, num_colors=5):
    """Download album art and extract dominant colors."""
    img = fetch_image(url)
    return extract_colors(img, num_colors)


def rgb_to_hex(r, g, b):
    """Convert RGB tuple to hex string."""
    return '#{:02x}{:02x}{:02x}'.format(r, g, b)


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        url = sys.argv[1]
        colors = colors_from_url(url)
        for c in colors:
            print(f"  {rgb_to_hex(*c)}  rgb{c}")
    else:
        print("Usage: python color_extract.py <album_art_url>")
