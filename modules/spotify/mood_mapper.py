"""
Map Spotify audio features to lighting effect parameters.

Spotify provides these features per track:
  - energy (0-1): intensity/activity
  - valence (0-1): musical positivity (happy vs sad)
  - tempo (BPM): beats per minute
  - danceability (0-1): how suitable for dancing
  - acousticness (0-1): confidence the track is acoustic
  - instrumentalness (0-1): predicts if track has no vocals
"""

import math


def classify_mood(features):
    """
    Classify track mood from audio features.
    Returns a mood string and parameters dict.
    """
    energy = features.get('energy', 0.5)
    valence = features.get('valence', 0.5)
    tempo = features.get('tempo', 120)
    danceability = features.get('danceability', 0.5)
    instrumentalness = features.get('instrumentalness', 0.0)

    # Mood classification
    if energy > 0.7 and valence > 0.6:
        mood = 'energetic'
    elif energy > 0.7 and valence <= 0.6:
        mood = 'intense'
    elif energy <= 0.4 and valence <= 0.4:
        mood = 'melancholy'
    elif energy <= 0.4 and valence > 0.6:
        mood = 'peaceful'
    elif instrumentalness > 0.7:
        mood = 'ambient'
    elif danceability > 0.7:
        mood = 'groovy'
    else:
        mood = 'neutral'

    return mood


def mood_to_effect_params(mood, tempo, album_colors):
    """
    Convert mood + tempo + album colors into effect parameters.
    Returns a dict with pattern, speed, brightness, color strategy.
    """
    # Normalize tempo to a speed multiplier (60bpm=0.5x, 120bpm=1x, 180bpm=1.5x)
    speed = max(0.3, min(2.0, tempo / 120.0))

    params = {
        'mood': mood,
        'tempo': tempo,
        'speed': speed,
        'colors': album_colors,
        'brightness': 1.0,
    }

    if mood == 'energetic':
        params['pattern'] = 'wave'
        params['speed'] = speed * 1.2
        params['brightness'] = 1.0
        params['overlay'] = 'twinkle'

    elif mood == 'intense':
        params['pattern'] = 'wave'
        params['speed'] = speed * 1.5
        params['brightness'] = 1.0
        params['color_shift'] = 'cool'

    elif mood == 'melancholy':
        params['pattern'] = 'breathe'
        params['speed'] = speed * 0.6
        params['brightness'] = 0.7
        params['color_shift'] = 'cool'

    elif mood == 'peaceful':
        params['pattern'] = 'breathe'
        params['speed'] = speed * 0.5
        params['brightness'] = 0.8

    elif mood == 'ambient':
        params['pattern'] = 'breathe'
        params['speed'] = speed * 0.4
        params['brightness'] = 0.6
        params['overlay'] = 'twinkle'

    elif mood == 'groovy':
        params['pattern'] = 'wave'
        params['speed'] = speed
        params['brightness'] = 0.9
        params['overlay'] = 'twinkle'

    else:  # neutral
        params['pattern'] = 'wave'
        params['speed'] = max(speed * 0.8, 1.0)
        params['brightness'] = 1.0

    return params


def shift_color_temperature(rgb, direction='cool'):
    """Shift an RGB color warmer or cooler."""
    r, g, b = rgb
    if direction == 'cool':
        r = max(0, int(r * 0.8))
        b = min(255, int(b * 1.2))
    elif direction == 'warm':
        r = min(255, int(r * 1.2))
        b = max(0, int(b * 0.8))
    return (r, g, b)


def apply_brightness(rgb, brightness):
    """Scale an RGB color by a brightness factor."""
    return tuple(min(255, int(c * brightness)) for c in rgb)


def blend_colors(c1, c2, t):
    """Linearly interpolate between two RGB colors."""
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
