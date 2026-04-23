import os
import subprocess, json, time, threading, sys, math, random
from PIL import Image, ImageDraw, ImageFont

EXE = os.path.join(os.environ.get('LOCALAPPDATA', os.path.join(os.path.expanduser('~'), 'AppData', 'Local')), 'DynamicLightingDriver', 'DynamicLightingDriver.exe')
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

proc = subprocess.Popen([EXE], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
threading.Thread(target=lambda: [proc.stderr.readline() for _ in iter(int, 1)], daemon=True).start()

def send(cmd):
    proc.stdin.write((cmd + '\n').encode())
    proc.stdin.flush()
def recv():
    return proc.stdout.readline().decode().strip()

ready = recv()
assert ready == 'READY', f'Driver not ready: {ready}'

send("SET_EFFECT_NAME Water Droplets")
recv()

# === MONET WATER DROPLETS EFFECT ===
# A still pond surface in deep teals and moss greens, with raindrops
# landing and creating bright ripple rings that expand outward and fade.
# Inspired by Monet's Water Lilies — impressionist, dreamy, organic.

# 87-key TKL layout
rows = [15, 15, 15, 14, 13, 8, 7]
row_offsets = [0, 0, 0.075, 0.12, 0.15, 0, 0.85]
row_kw = [1, 1, 1, 1, 1, 1.5, 1]

key_labels = [
    "Esc","","F1","F2","F3","F4","","F5","F6","F7","F8","","F9","F10","F11",
    "`","1","2","3","4","5","6","7","8","9","0","-","=","Bks","Ins",
    "Tab","Q","W","E","R","T","Y","U","I","O","P","[","]","\\","Del",
    "Cap","A","S","D","F","G","H","J","K","L",";","'","Ent","PgU",
    "Shf","Z","X","C","V","B","N","M",",",".","/","Shf","Up",
    "Ctl","Win","Alt","Spc","Spc","Alt","Fn","Ctl",
    "","","Lft","Dn","Rt","",""
]

lamps = []
idx = 0
for ri, count in enumerate(rows):
    for ci in range(count):
        x = (row_offsets[ri] + ci * row_kw[ri]) / 15.0
        y = ri / 6.0
        lamps.append({"idx": idx, "x": x, "y": y, "label": key_labels[idx] if idx < len(key_labels) else "", "row": ri, "col": ci})
        idx += 1

# Pond colors — deep greens and teals like Monet's water
POND_DEEP    = (15, 50, 40)
POND_MID     = (30, 75, 55)
POND_LIGHT   = (45, 100, 75)
POND_TEAL    = (25, 85, 80)
LILY_PAD     = (40, 95, 45)
LILY_FLOWER  = (200, 140, 170)
RIPPLE_WHITE = (220, 235, 230)
SPLASH_WHITE = (255, 255, 245)

# Fixed lily pad positions (subtle color variation on the pond)
lily_pads = [(0.20, 0.20), (0.70, 0.35), (0.40, 0.80), (0.85, 0.70), (0.10, 0.60)]

def lerp(c1, c2, t):
    t = max(0, min(1, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


# Pre-generate droplet schedule so it's deterministic for viz + animation
def gen_droplet(seed):
    """Generate a droplet position from a seed."""
    rng = (seed * 73856093 + 19349663) & 0x7FFFFFFF
    x = ((rng >> 4) & 0xFFF) / 4095.0
    y = ((rng >> 16) & 0xFFF) / 4095.0
    return x, y


def render_frame(t):
    """Render one frame of the water droplet pond."""
    # Droplet timing
    droplet_interval = 0.85
    ripple_life = 3.2
    max_active = int(ripple_life / droplet_interval) + 2

    colors = {}
    for lamp in lamps:
        lx, ly = lamp['x'], lamp['y']

        # --- Pond water base with gentle movement ---
        wave1 = math.sin(lx * 6 + t * 0.4) * math.sin(ly * 5 + t * 0.3) * 0.5 + 0.5
        wave2 = math.sin(lx * 4 - t * 0.25 + ly * 3) * 0.5 + 0.5
        color = lerp(POND_DEEP, POND_MID, wave1 * 0.5)
        color = lerp(color, POND_TEAL, wave2 * 0.3)

        # Subtle light dappling (sunlight through water)
        dapple = math.sin(lx * 10 + t * 0.8) * math.sin(ly * 8 - t * 0.6) * 0.5 + 0.5
        color = lerp(color, POND_LIGHT, dapple * 0.2)

        # --- Lily pads ---
        for plx, ply in lily_pads:
            # Lily pads drift very slightly
            pad_x = plx + math.sin(t * 0.1 + plx * 5) * 0.02
            pad_y = ply + math.cos(t * 0.08 + ply * 4) * 0.015
            dist = math.sqrt((lx - pad_x) ** 2 + (ly - pad_y) ** 2)
            if dist < 0.08:
                pad_blend = 1.0 - dist / 0.08
                color = lerp(color, LILY_PAD, pad_blend * 0.7)
                # Small pink flower on some pads
                if dist < 0.03 and int((plx + ply) * 10) % 3 == 0:
                    color = lerp(color, LILY_FLOWER, (1.0 - dist / 0.03) * 0.8)

        # --- Water droplets and ripples ---
        ripple_max = 0.0
        splash_max = 0.0

        for i in range(max_active):
            drop_id = int(t / droplet_interval) - i
            birth = drop_id * droplet_interval
            age = t - birth
            if age < 0 or age > ripple_life:
                continue

            dx, dy = gen_droplet(drop_id)
            dist = math.sqrt((lx - dx) ** 2 + (ly - dy) ** 2)
            progress = age / ripple_life

            # Expanding ripple ring
            ripple_radius = progress * 0.8
            ring_dist = abs(dist - ripple_radius)
            ring_width = 0.06 + progress * 0.04

            if ring_dist < ring_width:
                fade = (1.0 - progress) ** 1.3
                intensity = (1.0 - ring_dist / ring_width) ** 0.8 * fade
                ripple_max = max(ripple_max, intensity)

            # Second ring trailing — fainter, wider
            if progress > 0.1:
                ring2_radius = max(0, ripple_radius - 0.10)
                ring2_dist = abs(dist - ring2_radius)
                ring2_width = ring_width * 1.3
                if ring2_dist < ring2_width:
                    fade2 = (1.0 - progress) ** 1.8
                    intensity2 = (1.0 - ring2_dist / ring2_width) ** 0.8 * fade2 * 0.3
                    ripple_max = max(ripple_max, intensity2)

            # Splash at impact — bright burst at center
            if age < 0.35:
                splash_radius = 0.10 * (1.0 - age / 0.35)
                if dist < splash_radius:
                    splash_intensity = (1.0 - age / 0.35) * (1.0 - dist / splash_radius)
                    splash_max = max(splash_max, splash_intensity)

        # Apply ripple glow
        if ripple_max > 0:
            color = lerp(color, RIPPLE_WHITE, ripple_max * 0.75)

        # Apply splash (brighter, on top)
        if splash_max > 0:
            color = lerp(color, SPLASH_WHITE, splash_max * 0.95)

        colors[str(lamp['idx'])] = '#{:02x}{:02x}{:02x}'.format(*color)

    return colors


# === GENERATE VISUALIZATION (4 snapshots) ===
key_w, key_h = 52, 42
gap = 4
margin = 25
label_h = 22
snapshots = [0.0, 1.5, 3.0, 5.0]

total_w = 15 * (key_w + gap) + margin * 2
single_h = len(rows) * (key_h + gap) + label_h + 8
total_h = len(snapshots) * single_h + margin * 2

img = Image.new('RGB', (total_w, total_h), (10, 30, 25))
draw = ImageDraw.Draw(img)

try:
    font = ImageFont.truetype("consola.ttf", 11)
    title_font = ImageFont.truetype("consola.ttf", 13)
except:
    font = ImageFont.load_default()
    title_font = font

draw.text((margin, 6), "Water Droplets  -  4 animation snapshots", fill=(180, 220, 210), font=title_font)

for si, snap_t in enumerate(snapshots):
    frame_colors = render_frame(snap_t)
    y_off = margin + 14 + si * single_h
    draw.text((margin, y_off), f"t = {snap_t:.1f}s", fill=(150, 200, 190), font=title_font)
    y_off += label_h

    idx = 0
    for ri, count in enumerate(rows):
        for ci in range(count):
            lamp = lamps[idx]
            hx = frame_colors[str(idx)]
            cr, cg, cb = int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)
            px = int(margin + (row_offsets[ri] + ci * row_kw[ri]) / 15.0 * (total_w - margin * 2))
            py = y_off + ri * (key_h + gap)
            draw.rounded_rectangle([px, py, px + key_w - 2, py + key_h - 2], radius=4, fill=(cr, cg, cb), outline=(30, 50, 45))
            label = lamp['label']
            if label:
                lum = cr * 0.299 + cg * 0.587 + cb * 0.114
                tc = (0, 0, 0) if lum > 128 else (150, 190, 180)
                bbox = draw.textbbox((0, 0), label, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                draw.text((px + (key_w - 2 - tw) // 2, py + (key_h - 2 - th) // 2), label, fill=tc, font=font)
            idx += 1

img_path = f"{OUT_DIR}\\_water_droplets_viz.png"
img.save(img_path)
print(f"Visualization saved to: {img_path}")

# === RUN ANIMATION LOOP ===
print("Starting water droplets animation (~8fps)...")
sys.stdout.flush()

PAUSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'rules', '.pause')

frame_num = 0
start = time.time()
while True:
    if os.path.exists(PAUSE_FILE):
        try:
            with open(PAUSE_FILE, 'r') as f:
                alert_data = f.read().strip()
            parts = alert_data.split('|')
            flash_color = parts[0] if parts[0].startswith('#') else '#FF69B4'
            flash_duration = float(parts[1]) if len(parts) > 1 else 3.0
            all_flash = {str(lamp['idx']): flash_color for lamp in lamps}
            flash_start = time.time()
            while time.time() - flash_start < flash_duration:
                send(f"SET_LAMPS {json.dumps(all_flash)}")
                recv()
                frame_num += 1
                time.sleep(0.125)
        except Exception as e:
            print(f"Alert flash error: {e}")
        finally:
            try:
                os.remove(PAUSE_FILE)
            except Exception:
                pass
        continue

    t = time.time() - start
    frame_colors = render_frame(t)
    send(f"SET_LAMPS {json.dumps(frame_colors)}")
    recv()
    frame_num += 1
    elapsed = time.time() - start
    target = frame_num / 8.0
    if target > elapsed:
        time.sleep(target - elapsed)
