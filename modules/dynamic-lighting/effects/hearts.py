import os
import subprocess, json, time, threading, sys

EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'DynamicLightingMcp', 'bin', 'Debug', 'net9.0-windows10.0.26100.0', 'DynamicLightingMcp.exe')
proc = subprocess.Popen([EXE], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)

def send(obj):
    proc.stdin.write((json.dumps(obj)+'\n').encode())
    proc.stdin.flush()
def recv():
    return json.loads(proc.stdout.readline())

threading.Thread(target=lambda: [proc.stderr.readline() for _ in iter(int,1)], daemon=True).start()

send({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'test','version':'1.0'}}})
recv()
send({'jsonrpc':'2.0','method':'notifications/initialized'})
time.sleep(3)

# === PHYSICAL KEYBOARD MAPPING ===
# Standard ANSI TKL 87-key: key labels + approximate physical X position (in key-widths)
keyboard = [
    # Row 0 (F-keys): 15 lamps, indices 0-14
    # Esc, gap, F1-F4, gap, F5-F8, gap, F9-F11 (+F12/PrtSc as 14)
    [("Esc",0), ("  ",1.5), ("F1",2), ("F2",3), ("F3",4), ("F4",5),
     ("  ",6), ("F5",6.5), ("F6",7.5), ("F7",8.5), ("F8",9.5),
     ("  ",10.5), ("F9",11), ("F10",12), ("F11",13)],

    # Row 1 (Number): 15 lamps, indices 15-29
    [("` ",0), ("1 ",1), ("2 ",2), ("3 ",3), ("4 ",4), ("5 ",5),
     ("6 ",6), ("7 ",7), ("8 ",8), ("9 ",9), ("0 ",10), ("- ",11),
     ("= ",12), ("Bk",13.5), ("In",15.5)],

    # Row 2 (QWERTY): 15 lamps, indices 30-44
    [("Tb",0), ("Q ",1.5), ("W ",2.5), ("E ",3.5), ("R ",4.5), ("T ",5.5),
     ("Y ",6.5), ("U ",7.5), ("I ",8.5), ("O ",9.5), ("P ",10.5), ("[ ",11.5),
     ("] ",12.5), ("\\ ",13.5), ("De",15.5)],

    # Row 3 (Home): 14 lamps, indices 45-58
    [("Cp",0), ("A ",1.75), ("S ",2.75), ("D ",3.75), ("F ",4.75), ("G ",5.75),
     ("H ",6.75), ("J ",7.75), ("K ",8.75), ("L ",9.75), ("; ",10.75), ("' ",11.75),
     ("En",13), ("Pu",15.5)],

    # Row 4 (Shift): 13 lamps, indices 59-71
    [("Sh",0), ("Z ",2.25), ("X ",3.25), ("C ",4.25), ("V ",5.25), ("B ",6.25),
     ("N ",7.25), ("M ",8.25), (", ",9.25), (". ",10.25), ("/ ",11.25),
     ("Sh",13), ("Up",14.5)],

    # Row 5 (Bottom): 8 lamps, indices 72-79
    [("Ct",0), ("Wn",1.25), ("Al",2.5), ("Sp",4), ("Sp",6), ("Al",9.5),
     ("Fn",10.75), ("Ct",12)],

    # Row 6 (Arrows): 7 lamps, indices 80-86
    [("  ",11), ("  ",12), ("Lf",13.5), ("Dn",14.5), ("Rt",15.5), ("  ",16), ("  ",17)],
]

rows = [15, 15, 15, 14, 13, 8, 7]

# Build lamp index -> physical x,y mapping
lamp_phys = {}
idx = 0
for ri, row in enumerate(keyboard):
    for ci, (label, px) in enumerate(row):
        lamp_phys[idx] = {"label": label, "px": px, "py": ri, "row": ri, "col": ci}
        idx += 1

# === HEART DESIGN USING PHYSICAL X POSITIONS ===
# Heart test: is lamp physically inside heart shape?
# Heart centered at (cx, cy) with half-width hw
# Account for the fact that Y spacing (row height) ~= 1 key-width
def in_heart_phys(px, py, cx, cy, size):
    x = (px - cx) / size
    y = -(py - cy) / size * 1.5  # stretch vertically since rows are close together
    return (x*x + y*y - 1)**3 - x*x * y*y*y < 0

# Place 2 hearts at specific physical positions
hearts = [
    (4.0, 2.0, 2.5),   # left heart: centered around R/F area, rows 1-3
    (9.0, 2.0, 2.5),   # right heart: centered around O/L area, rows 1-3
]

# Build color map
colors = {}
for i in range(87):
    colors[str(i)] = '#080002'

RED   = '#FF0000'
PINK  = '#FF3355'

for cx, cy, sz in hearts:
    for i, info in lamp_phys.items():
        if in_heart_phys(info['px'], info['py'], cx, cy, sz):
            # Brighter toward center
            dx = abs(info['px'] - cx) / sz
            dy = abs(info['py'] - cy) / sz
            if dx < 0.3 and dy < 0.3:
                colors[str(i)] = PINK
            else:
                colors[str(i)] = RED

# === VISUALIZATION ===
def show_keyboard(colors, lamp_phys, keyboard, rows):
    RESET = "\033[0m"
    def rgb_bg(hex_col):
        r, g, b = int(hex_col[1:3],16), int(hex_col[3:5],16), int(hex_col[5:7],16)
        fg = "30" if (r*0.299 + g*0.587 + b*0.114) > 128 else "97"
        return f"\033[{fg};48;2;{r};{g};{b}m"

    row_names = ['F-keys ', 'Numbers', 'QWERTY ', 'Home   ', 'Shift  ', 'Mods   ', 'Arrows ']

    print("=== KEYBOARD VISUALIZATION ===")
    idx = 0
    for ri, row in enumerate(keyboard):
        parts = []
        for ci, (label, px) in enumerate(row):
            col = colors.get(str(idx), '#000000')
            parts.append(f"{rgb_bg(col)} {label} {RESET}")
            idx += 1
        print(f"{row_names[ri]}| {''.join(parts)}")

    # Text-only version
    print()
    print("=== KEY LABELS (R=RED heart, .=dark) ===")
    idx = 0
    for ri, row in enumerate(keyboard):
        parts = []
        for ci, (label, px) in enumerate(row):
            col = colors.get(str(idx), '#000000')
            r_val = int(col[1:3], 16)
            if r_val > 200:
                parts.append(f"[{label}]")
            elif r_val > 100:
                parts.append(f"({label})")
            else:
                parts.append(f" {label} ")
            idx += 1
        print(f"{row_names[ri]}| {''.join(parts)}")
    print()

show_keyboard(colors, lamp_phys, keyboard, rows)

# Apply
send({'jsonrpc':'2.0','id':3,'method':'tools/call','params':{
    'name':'set_per_lamp_colors',
    'arguments':{'lamp_colors': json.dumps(colors)}
}})
r = recv()
print(r['result']['content'][0]['text'])
print("Hearts theme active!")
sys.stdout.flush()

try:
    proc.wait()
except KeyboardInterrupt:
    proc.terminate()
