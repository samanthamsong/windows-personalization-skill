import os
import subprocess, json, time, threading, sys, math, colorsys
from PIL import Image, ImageDraw, ImageFont

EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'DynamicLightingMcp', 'bin', 'Debug', 'net9.0-windows10.0.26100.0', 'DynamicLightingMcp.exe')
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

proc = subprocess.Popen([EXE], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
threading.Thread(target=lambda: [proc.stderr.readline() for _ in iter(int,1)], daemon=True).start()

def send(obj):
    proc.stdin.write((json.dumps(obj)+'\n').encode())
    proc.stdin.flush()
def recv():
    return json.loads(proc.stdout.readline())

send({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'test','version':'1.0'}}})
recv()
send({'jsonrpc':'2.0','method':'notifications/initialized'})
time.sleep(3)

# === ASTROLOGY THEME DESIGN ===
# Gemini Sun (core) - Air sign, duality/twins, golden/amber with mirror symmetry
# Pisces Moon (emotion) - Water sign, dreamy, deep indigo to seafoam, mystical
# Virgo Rising (presentation) - Earth sign, grounded, sage/forest greens

# Layout: 87 keys across 7 rows
rows = [15, 15, 15, 14, 13, 8, 7]
row_offsets_x = [0, 0, 0.075, 0.12, 0.15, 0, 0.85]
row_key_widths = [1, 1, 1, 1, 1, 1.5, 1]
key_labels = [
    "Esc","","F1","F2","F3","F4","","F5","F6","F7","F8","","F9","F10","F11",
    "`","1","2","3","4","5","6","7","8","9","0","-","=","Bks","Ins",
    "Tab","Q","W","E","R","T","Y","U","I","O","P","[","]","\\","Del",
    "Cap","A","S","D","F","G","H","J","K","L",";","'","Ent","PgU",
    "Shf","Z","X","C","V","B","N","M",",",".","/","Shf","Up",
    "Ctl","Win","Alt","Spc","Spc","Alt","Fn","Ctl",
    "","","Lft","Dn","Rt","",""
]

# Build lamp positions
lamps = []
idx = 0
for ri, count in enumerate(rows):
    for ci in range(count):
        kw = row_key_widths[ri]
        x = (row_offsets_x[ri] + ci * kw) / 15.0
        y = ri / (len(rows) - 1)
        label = key_labels[idx] if idx < len(key_labels) else ""
        lamps.append({"idx": idx, "x": x, "y": y, "label": label, "row": ri, "col": ci})
        idx += 1

def lerp_color(c1, c2, t):
    t = max(0, min(1, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

def blend3(c1, c2, c3, t):
    """Blend across 3 colors: t=0->c1, t=0.5->c2, t=1->c3"""
    if t <= 0.5:
        return lerp_color(c1, c2, t * 2)
    else:
        return lerp_color(c2, c3, (t - 0.5) * 2)

# === COLOR PALETTES ===
# Pisces Moon (top) - mystical ocean depths
pisces_deep    = (15, 5, 50)      # deep indigo
pisces_mid     = (75, 0, 130)     # rich purple
pisces_light   = (100, 149, 237)  # cornflower blue
pisces_shimmer = (72, 209, 204)   # medium turquoise

# Gemini Sun (middle) - golden duality
gemini_warm    = (255, 191, 0)    # amber gold
gemini_hot     = (255, 140, 0)    # dark orange
gemini_cool    = (218, 165, 32)   # goldenrod
gemini_pale    = (255, 228, 181)  # moccasin

# Virgo Rising (bottom) - grounded earth
virgo_deep     = (34, 60, 34)     # dark forest
virgo_mid      = (85, 107, 47)    # dark olive
virgo_light    = (107, 142, 35)   # olive drab
virgo_sage     = (143, 188, 143)  # dark sea green

# === COMPUTE LAMP COLORS ===
colors = {}

for lamp in lamps:
    x, y = lamp['x'], lamp['y']
    ri = lamp['row']
    
    # Vertical zone blending (smooth transitions between signs)
    # Rows 0-1: Pisces Moon (top, ethereal, emotional world)
    # Rows 2-3: Gemini Sun (middle, core identity)  
    # Rows 4-6: Virgo Rising (bottom, how you present to world)
    
    if ri <= 1:
        # === PISCES MOON ZONE ===
        # Flowing water gradient with shimmer points
        # Deep indigo on edges, lighter blue/turquoise toward center
        center_dist = abs(x - 0.5) * 2  # 0 at center, 1 at edges
        
        if ri == 0:
            # Top row: deep indigo with purple accents
            base = lerp_color(pisces_mid, pisces_deep, center_dist)
            # Add shimmer at constellation-like points
            shimmer = math.sin(x * math.pi * 6) * 0.5 + 0.5
            color = lerp_color(base, pisces_shimmer, shimmer * 0.25)
        else:
            # Row 1: lighter, more flowing - seafoam meeting purple
            wave = math.sin(x * math.pi * 3 + 0.5) * 0.5 + 0.5
            color = lerp_color(pisces_light, pisces_shimmer, wave * 0.6)
            # Deepen edges
            color = lerp_color(color, pisces_mid, center_dist * 0.3)
    
    elif ri <= 3:
        # === GEMINI SUN ZONE ===
        # Duality: warm amber on left, cooler gold on right
        # Mirror symmetry representing the twins
        mirror_x = abs(x - 0.5) * 2  # distance from center
        
        if x < 0.5:
            # Left twin: warm/hot amber
            twin_color = lerp_color(gemini_hot, gemini_warm, mirror_x)
        else:
            # Right twin: cooler goldenrod
            twin_color = lerp_color(gemini_cool, gemini_pale, mirror_x * 0.7)
        
        # Center meeting point: bright radiant gold (where twins meet)
        if mirror_x < 0.15:
            radiance = 1.0 - mirror_x / 0.15
            twin_color = lerp_color(twin_color, (255, 255, 220), radiance * 0.6)
        
        # Row 2 is the transition from Pisces, add slight purple tint
        if ri == 2:
            color = lerp_color(pisces_light, twin_color, 0.7)
        else:
            color = twin_color
    
    else:
        # === VIRGO RISING ZONE ===
        # Grounded earth tones, structured and clean
        # Gradient from sage (lighter, inner) to deep forest (outer edges)
        center_dist = abs(x - 0.5) * 2
        
        if ri == 4:
            # Transition from Gemini - olive with golden hints
            earth = lerp_color(virgo_light, virgo_mid, center_dist)
            color = lerp_color(gemini_cool, earth, 0.75)
        elif ri == 5:
            # Deep grounded green
            color = lerp_color(virgo_sage, virgo_deep, center_dist * 0.7)
        else:
            # Bottom arrows: darkest earth
            color = lerp_color(virgo_mid, virgo_deep, 0.5)
    
    colors[str(lamp['idx'])] = '#{:02x}{:02x}{:02x}'.format(*color)

# Apply to keyboard
send({'jsonrpc':'2.0','id':3,'method':'tools/call','params':{
    'name':'set_per_lamp_colors',
    'arguments':{'lamp_colors': json.dumps(colors)}
}})
r = recv()
print(r['result']['content'][0]['text'])

# === RENDER VISUALIZATION ===
key_w, key_h = 52, 42
gap = 4
margin = 30
total_w = 15 * (key_w + gap) + margin * 2
kb_h = len(rows) * (key_h + gap)
legend_h = 130
total_h = kb_h + legend_h + margin * 3

img = Image.new('RGB', (total_w, total_h), (15, 12, 20))
draw = ImageDraw.Draw(img)

try:
    font = ImageFont.truetype("consola.ttf", 11)
    title_font = ImageFont.truetype("consola.ttf", 14)
    legend_font = ImageFont.truetype("consola.ttf", 12)
except:
    font = ImageFont.load_default()
    title_font = font
    legend_font = font

# Title
draw.text((margin, 10), "Gemini Sun  |  Pisces Moon  |  Virgo Rising", fill=(220, 200, 240), font=title_font)

y_start = margin + 15

# Draw keyboard
idx = 0
for ri, count in enumerate(rows):
    for ci in range(count):
        lamp = lamps[idx]
        hex_col = colors[str(idx)]
        r_val = int(hex_col[1:3], 16)
        g_val = int(hex_col[3:5], 16)
        b_val = int(hex_col[5:7], 16)
        color = (r_val, g_val, b_val)
        
        px = int(margin + (row_offsets_x[ri] + ci * row_key_widths[ri]) / 15.0 * (total_w - margin*2))
        py = y_start + ri * (key_h + gap)
        
        draw.rounded_rectangle([px, py, px+key_w-2, py+key_h-2], radius=4, fill=color, outline=(50,50,60))
        
        label = lamp['label']
        if label:
            lum = color[0]*0.299 + color[1]*0.587 + color[2]*0.114
            text_color = (0,0,0) if lum > 128 else (200,200,210)
            bbox = draw.textbbox((0,0), label, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((px + (key_w-2-tw)//2, py + (key_h-2-th)//2), label, fill=text_color, font=font)
        
        idx += 1

# Legend
ly = y_start + kb_h + 20

# Pisces Moon
draw.rounded_rectangle([margin, ly, margin+18, ly+18], radius=3, fill=pisces_mid)
draw.text((margin+24, ly+1), "Pisces Moon (top) - mystical ocean, deep indigo to seafoam", fill=(180,180,200), font=legend_font)

# Gemini Sun  
draw.rounded_rectangle([margin, ly+26, margin+18, ly+44], radius=3, fill=gemini_warm)
draw.text((margin+24, ly+27), "Gemini Sun (middle) - golden duality, warm/cool twins meeting at center", fill=(180,180,200), font=legend_font)

# Virgo Rising
draw.rounded_rectangle([margin, ly+52, margin+18, ly+70], radius=3, fill=virgo_mid)
draw.text((margin+24, ly+53), "Virgo Rising (bottom) - grounded earth, sage to deep forest", fill=(180,180,200), font=legend_font)

# Symbolism note
draw.text((margin, ly+82), "Rising = foundation (bottom)  |  Sun = core identity (center)  |  Moon = inner world (top)", 
          fill=(130,120,150), font=legend_font)

img_path = f"{OUT_DIR}\\_astrology_viz.png"
img.save(img_path)
print(f"\nVisualization saved to: {img_path}")
print("Astrology theme active!")
sys.stdout.flush()

try:
    proc.wait()
except KeyboardInterrupt:
    proc.terminate()
