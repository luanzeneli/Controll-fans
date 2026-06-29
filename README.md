# My RGB Control

A personalized desktop app to control the RGB on your PC's **fans, RAM, and
cooler** — running on Pop!_OS (Linux).

It sits on top of [OpenRGB](https://openrgb.org), which is the engine that
actually talks to the lighting hardware. Our app talks to OpenRGB over its
local network SDK and adds a friendly GUI with:

- 🎨 **Static colours + presets** — pick any colour per device, save/load profiles
- 🌈 **Animated effects** — Breathing, Rainbow, Wave, Colour Cycle
- 🌡️ **Temperature reactive** — colours shift blue→red with your CPU temp
- 🎵 **Audio reactive** — lights pulse to whatever is playing

---

## One-time setup (on your Pop!_OS PC)

### 1. Install OpenRGB (the hardware engine)

```bash
sudo apt update
sudo apt install -y openrgb
```

If `apt` can't find it, grab the `.deb` from <https://openrgb.org/releases.html>
and install with `sudo dpkg -i openrgb_*.deb`.

> **Permissions:** OpenRGB needs access to your hardware. Install its udev rules
> (the package usually does this automatically) and **reboot once** after
> installing. If devices don't show up, run OpenRGB once with `sudo openrgb`
> to confirm they're detected, then fix permissions per the OpenRGB docs.

### 2. Let OpenRGB detect your hardware

Open the OpenRGB app once (`openrgb`) and check the **Devices** tab — you should
see your motherboard, RAM, fans, and cooler listed. This is also how we find out
what hardware you have. If something's missing, that device may need a different
connection or isn't yet supported — tell me which and we'll work around it.

### 3. Install this app's dependencies

```bash
cd controll-fans
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Running it

The easy way:

```bash
./run.sh
```

This starts the OpenRGB SDK server (if it isn't already running) and launches
the GUI.

Doing it manually instead:

```bash
# terminal 1 — start the engine's network server
openrgb --server

# terminal 2 — start the app
source .venv/bin/activate
python -m src.app
```

---

## How to use the GUI

1. Click **Connect** (it auto-connects on launch). You'll see your devices.
2. **Tick** the devices you want to control.
3. Choose an **effect**, pick a **colour**, set **speed/brightness**.
4. Click **Apply effect**.
5. Save the look as a **Profile** to switch between setups instantly.

- **Temperature** effect → colours follow your CPU temperature.
- **Audio Reactive** → lights pulse to sound. To react to *music* (not your mic),
  route your speaker output into an input "monitor" source in your sound settings
  (PipeWire/PulseAudio), then select that as the default input.

---

## Project layout

```
controll-fans/
├── run.sh              # one-command launcher
├── requirements.txt
├── src/
│   ├── app.py          # the GUI (PySide6)
│   ├── rgb_client.py   # wrapper around the OpenRGB SDK
│   ├── effects.py      # animation + reactive effect engine
│   ├── monitors.py     # CPU-temp and audio level sources
│   └── profiles.py     # save/load JSON profiles
└── profiles/           # your saved looks live here
```

## Troubleshooting

- **"Couldn't reach the OpenRGB SDK server"** — OpenRGB isn't running with
  `--server`. Run `openrgb --server` or use `./run.sh`.
- **No devices listed** — see the permissions note in step 1; reboot after
  installing OpenRGB, and confirm devices appear in the OpenRGB app itself.
- **Effects look choppy** — lower the number of selected devices or reduce speed.
