import os
import subprocess, json, time, threading, sys, math
from PIL import Image, ImageDraw, ImageFont

EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'DynamicLightingDriver', 'bin', 'Debug', 'net9.0-windows10.0.26100.0', 'DynamicLightingDriver.exe')
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

send("SET_EFFECT_NAME Magical Fireworks")
recv()

# === MAGICAL FIREWORKS EFFECT ===
# Night sky with fireworks launching upward, exploding into colorful
# particle bursts that rain down with sparkle trails and fade out.

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

# Night sky colors
SKY_DARK   = (5, 5, 20)
SKY_DEEP   = (10, 8, 35)
STAR_WHITE = (180, 180, 200)

# Firework explosion colors — each firework picks one
FIREWORK_COLORS = [
    ((255, 50, 80),   (255, 150, 180)),  # red → pink
    ((50, 120, 255),  (150, 200, 255)),  # blue → light blue
    ((255, 200, 30),  (255, 255, 150)),  # gold → pale yellow
    ((200, 50, 255),  (255, 150, 255)),  # purple → lavender
    ((50, 255, 120),  (150, 255, 200)),  # green → mint
    ((255, 100, 30),  (255, 200, 100)),  # orange → peach
    ((0, 220, 255),   (150, 240, 255)),  # cyan → ice
    ((255, 50, 200),  (255, 180, 240)),  # magenta → pink
]

def lerp(c1, c2, t):
    t = max(0, min(1, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def hash_int(n):
    """Simple deterministic hash for pseudo-random values."""
    n = ((n >> 16) ^ n) * 0x45D9F3B
    n = ((n >> 16) ^ n) * 0x45D9F3B
    n = (n >> 16) ^ n
    return n & 0x7FFFFFFF


def gen_firework(fw_id):
    """Generate firework properties from its ID."""
    h = hash_int(fw_id)
    # Position: x spread across keyboard, y in upper half (explodes high)
    cx = 0.1 + ((h >> 0) & 0xFF) / 255.0 * 0.8
    cy = 0.05 + ((h >> 8) & 0xFF) / 255.0 * 0.8
    # Color pair
    color_idx = ((h >> 16) & 0xFF) % len(FIREWORK_COLORS)
    # Number of particles (8-16)
    n_particles = 8 + ((h >> 20) & 0x7) 
    # Explosion size
    size = 0.25 + ((h >> 24) & 0x3F) / 63.0 * 0.35
    return cx, cy, color_idx, n_particles, size


def render_frame(t):
    """Render one frame of fireworks at time t."""
    # Firework timing
    fw_interval = 1.4       # new firework every 1.4s
    fw_launch_time = 0.5    # time to rise
    fw_explode_time = 2.5   # explosion + fade duration
    fw_total = fw_launch_time + fw_explode_time
    max_active = int(fw_total / fw_interval) + 2

    colors = {}
    for lamp in lamps:
        lx, ly = lamp['x'], lamp['y']

        # --- Night sky base with twinkling stars ---
        star_seed = hash_int(lamp['idx'] * 31337)
        star_phase = math.sin(t * (1.5 + (star_seed & 0xFF) / 200.0) + (star_seed >> 8)) * 0.5 + 0.5

        # Dark sky gradient (darker at top)
        sky = lerp(SKY_DARK, SKY_DEEP, ly * 0.5 + math.sin(lx * 3 + t * 0.2) * 0.1)

        # Sparse star twinkle
        if (star_seed & 0xF) < 2 and star_phase > 0.85:
            twinkle = (star_phase - 0.85) / 0.15
            sky = lerp(sky, STAR_WHITE, twinkle * 0.4)

        color = sky

        # --- Fireworks ---
        best_brightness = 0.0
        best_color = color

        for i in range(max_active):
            fw_id = int(t / fw_interval) - i
            birth = fw_id * fw_interval
            age = t - birth
            if age < 0 or age > fw_total:
                continue

            cx, cy, color_idx, n_particles, size = gen_firework(fw_id)
            core_color, trail_color = FIREWORK_COLORS[color_idx]

            # Phase 1: Launch trail (rising from bottom)
            if age < fw_launch_time:
                progress = age / fw_launch_time
                # Trail rises from bottom center to explosion point
                trail_x = cx
                trail_y = 1.0 - progress * (1.0 - cy)
                dist = math.sqrt((lx - trail_x) ** 2 + (ly - trail_y) ** 2)

                # Bright head
                if dist < 0.06:
                    intensity = (1.0 - dist / 0.06) * progress
                    if intensity > best_brightness:
                        best_brightness = intensity
                        best_color = lerp(core_color, (255, 255, 220), 0.5)

                # Fading tail below
                tail_len = 0.15 * progress
                if ly > trail_y and ly < trail_y + tail_len and abs(lx - trail_x) < 0.04:
                    tail_fade = (ly - trail_y) / tail_len
                    intensity = (1.0 - tail_fade) * progress * 0.5
                    if intensity > best_brightness:
                        best_brightness = intensity
                        best_color = trail_color

            # Phase 2: Explosion
            else:
                explode_age = age - fw_launch_time
                explode_progress = explode_age / fw_explode_time

                # Initial flash at detonation
                if explode_age < 0.15:
                    dist = math.sqrt((lx - cx) ** 2 + (ly - cy) ** 2)
                    if dist < 0.2:
                        flash = (1.0 - explode_age / 0.15) * (1.0 - dist / 0.2)
                        if flash > best_brightness:
                            best_brightness = flash
                            best_color = (255, 255, 240)

                # Particles radiating outward
                for p in range(n_particles):
                    angle = (p / n_particles) * math.pi * 2
                    # Slight angle variation per firework
                    angle += hash_int(fw_id * 100 + p) / 2147483647.0 * 0.3

                    # Particle position: radiates out then falls with gravity
                    speed = size * (0.7 + (hash_int(fw_id * 200 + p) & 0xFF) / 255.0 * 0.6)
                    px = cx + math.cos(angle) * speed * explode_progress
                    py = cy + math.sin(angle) * speed * explode_progress
                    # Gravity pulls particles down over time
                    py += 0.3 * explode_progress ** 2

                    dist = math.sqrt((lx - px) ** 2 + (ly - py) ** 2)

                    # Particle glow radius shrinks as it fades
                    glow_radius = 0.08 * (1.0 - explode_progress * 0.6)

                    if dist < glow_radius:
                        fade = (1.0 - explode_progress) ** 1.5
                        intensity = (1.0 - dist / glow_radius) * fade
                        if intensity > best_brightness:
                            best_brightness = intensity
                            # Color shifts from core to trail as particles age
                            particle_color = lerp(core_color, trail_color, explode_progress)
                            best_color = particle_color

                    # Sparkle trail behind each particle
                    if explode_progress > 0.2 and explode_progress < 0.85:
                        trail_px = cx + math.cos(angle) * speed * (explode_progress - 0.08)
                        trail_py = cy + math.sin(angle) * speed * (explode_progress - 0.08)
                        trail_py += 0.3 * (explode_progress - 0.08) ** 2
                        trail_dist = math.sqrt((lx - trail_px) ** 2 + (ly - trail_py) ** 2)
                        if trail_dist < 0.05:
                            sparkle_seed = hash_int(fw_id * 300 + p + int(t * 8))
                            if (sparkle_seed & 0x3) == 0:
                                sparkle = (1.0 - trail_dist / 0.05) * (1.0 - explode_progress) * 0.4
                                if sparkle > best_brightness:
                                    best_brightness = sparkle
                                    best_color = lerp(trail_color, (255, 255, 255), 0.5)

        # Apply firework color over sky
        if best_brightness > 0.02:
            color = lerp(color, best_color, min(best_brightness, 1.0))

            # Ambient glow — nearby sky gets lit up
        for i in range(max_active):
            fw_id = int(t / fw_interval) - i
            birth = fw_id * fw_interval
            age = t - birth
            if age < fw_launch_time or age > fw_total:
                continue
            explode_age = age - fw_launch_time
            if explode_age > fw_explode_time:
                continue
            cx, cy, color_idx, _, size = gen_firework(fw_id)
            core_color, _ = FIREWORK_COLORS[color_idx]
            dist = math.sqrt((lx - cx) ** 2 + (ly - cy) ** 2)
            if dist < 0.6:
                glow_fade = (1.0 - explode_age / fw_explode_time) ** 2
                glow = (1.0 - dist / 0.6) * glow_fade * 0.15
                color = lerp(color, core_color, glow)

        colors[str(lamp['idx'])] = '#{:02x}{:02x}{:02x}'.format(*color)

    return colors


# === GENERATE VISUALIZATION (4 snapshots) ===
key_w, key_h = 52, 42
gap = 4
margin = 25
label_h = 22
snapshots = [0.3, 1.0, 2.0, 3.5]

total_w = 15 * (key_w + gap) + margin * 2
single_h = len(rows) * (key_h + gap) + label_h + 8
total_h = len(snapshots) * single_h + margin * 2

img = Image.new('RGB', (total_w, total_h), (5, 5, 20))
draw = ImageDraw.Draw(img)

try:
    font = ImageFont.truetype("consola.ttf", 11)
    title_font = ImageFont.truetype("consola.ttf", 13)
except:
    font = ImageFont.load_default()
    title_font = font

draw.text((margin, 6), "Magical Fireworks  -  4 animation snapshots", fill=(200, 180, 220), font=title_font)

for si, snap_t in enumerate(snapshots):
    frame_colors = render_frame(snap_t)
    y_off = margin + 14 + si * single_h
    draw.text((margin, y_off), f"t = {snap_t:.1f}s", fill=(170, 150, 200), font=title_font)
    y_off += label_h

    idx = 0
    for ri, count in enumerate(rows):
        for ci in range(count):
            lamp = lamps[idx]
            hx = frame_colors[str(idx)]
            cr, cg, cb = int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)
            px = int(margin + (row_offsets[ri] + ci * row_kw[ri]) / 15.0 * (total_w - margin * 2))
            py = y_off + ri * (key_h + gap)
            draw.rounded_rectangle([px, py, px + key_w - 2, py + key_h - 2], radius=4, fill=(cr, cg, cb), outline=(30, 20, 50))
            label = lamp['label']
            if label:
                lum = cr * 0.299 + cg * 0.587 + cb * 0.114
                tc = (0, 0, 0) if lum > 128 else (140, 130, 170)
                bbox = draw.textbbox((0, 0), label, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                draw.text((px + (key_w - 2 - tw) // 2, py + (key_h - 2 - th) // 2), label, fill=tc, font=font)
            idx += 1

img_path = f"{OUT_DIR}\\_fireworks_viz.png"
img.save(img_path)
print(f"Visualization saved to: {img_path}")

# === RUN ANIMATION LOOP ===
print("Starting magical fireworks animation (~8fps)...")
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
