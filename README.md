# My RGB Control

A personalized desktop app to control the RGB on my PC's **fans, cooler, and
RAM** on Pop!_OS (Linux). Built on top of [OpenRGB](https://openrgb.org) for the
motherboard/fans, plus direct SMBus control for the DDR5 RAM that OpenRGB can't
see.

## What it controls

| Hardware | How | Status |
|----------|-----|--------|
| **9 ARGB fans + AIO** (MSI JRAINBOW headers) | OpenRGB SDK, Direct mode | ✅ full effects |
| **Kingston Fury Beast DDR5 RAM** | Direct SMBus writes (0x61/0x63) | ✅ static colour |
| RGB strip (JRGB1) | OpenRGB | ✅ if connected |

**Effects:** Static, Breathing, Rainbow, Wave, Colour Cycle, Temperature-reactive,
Audio-reactive, plus saveable profiles.

## My hardware (this build is tuned for it)

- **Motherboard:** MSI MAG Z790 Tomahawk WiFi (MS-7D91)
- **RAM:** Kingston Fury Beast DDR5-6000 CL36 (2 sticks, RGB at SMBus 0x61/0x63)
- **Case/fans:** Darkflash, 9 ARGB fans across JRAINBOW1/2/3 (60 LEDs each)
- **OS:** Pop!_OS 22.04 (noble base), Python 3.12

> ⚠️ **Important quirk:** on Linux this board only works in **Direct mode** —
> OpenRGB can't save hardware modes ("saving not supported"). So the app must be
> *running* to keep the fans lit. When it's closed the fans go dark; a reboot
> resets them to the BIOS default. That's why we autostart it. The RAM is
> different — its colour persists on its own until changed or rebooted.

---

# Full setup on a fresh Pop!_OS install

Do these in order. This is everything needed to reproduce the working setup on
the same hardware.

## 1. Install OpenRGB (the fan/cooler engine)

`apt install openrgb` does **not** work on Pop!_OS — get the official `.deb`:

```bash
cd ~/Downloads
wget https://codeberg.org/OpenRGB/OpenRGB/releases/download/release_candidate_1.0rc3/openrgb_1.0rc3_amd64_bookworm_6fbcf62.deb
sudo apt install -y ./openrgb_1.0rc3_amd64_bookworm_6fbcf62.deb
```
(Check <https://openrgb.org/releases.html> for a newer build; pick the **bookworm amd64** one.)

## 2. Enable RAM SMBus access (i2c)

```bash
# load the SMBus driver now and on every boot
sudo modprobe i2c-dev
echo "i2c-dev" | sudo tee /etc/modules-load.d/i2c-dev.conf

# let your user (and the app) reach the RAM without sudo
sudo apt install -y i2c-tools
sudo groupadd -f i2c
sudo usermod -aG i2c $USER
echo 'KERNEL=="i2c-[0-9]*", GROUP="i2c", MODE="0660"' | sudo tee /etc/udev/rules.d/99-i2c.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

## 3. Reboot

Needed for OpenRGB's hardware permissions and the i2c group to take effect.

```bash
sudo reboot
```

## 4. Get this app and install its dependencies

```bash
git clone https://github.com/luanzeneli/Controll-fans.git
cd Controll-fans
sudo apt install -y python3-venv python3-pip libportaudio2
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## 5. Run it

```bash
chmod +x run.sh
./run.sh          # starts the OpenRGB server + the GUI
```
> Close the OpenRGB GUI window if it's open — only one program can drive the
> lights at a time. `run.sh` starts its own headless server.

## 6. Configure the fans (one time)

The ARGB headers report 0 LEDs until told otherwise (this isn't saved in the
repo — it lives in OpenRGB's config). In the app:

1. Click **"Set up fan LED counts…"**
2. Set **JRAINBOW1 / 2 / 3** to **60** each → OK.
3. Pick an effect → **Apply**. Adjust counts down if any fan has a dark tail.

## 7. (Optional) Desktop launcher

```bash
./install-shortcut.sh      # adds "My RGB Control" to your apps menu
```

---

# Using the app

- **Fans/cooler:** tick devices → choose effect → pick colour/speed/brightness →
  **Apply effect**. Save looks as **Profiles**.
- **RAM:** in the "RAM — Kingston Fury DDR5" box → **Pick RAM colour** →
  **Apply to RAM**. (Greyed out? Log out/in so the i2c group applies.)
- **Temperature** effect → fans follow CPU temp. **Audio Reactive** → pulses to
  sound (route speaker output to a 'monitor' input to react to music).

---

# Project layout

```
Controll-fans/
├── run.sh                # launcher: OpenRGB server + GUI
├── install-shortcut.sh   # adds an app-menu/desktop launcher
├── requirements.txt
├── assets/icon.svg
├── src/
│   ├── app.py            # the GUI (PySide6)
│   ├── rgb_client.py     # OpenRGB SDK wrapper (fans/cooler)
│   ├── ram.py            # direct SMBus control for DDR5 RAM
│   ├── effects.py        # animation + reactive effect engine
│   ├── monitors.py       # CPU-temp + audio sources
│   └── profiles.py       # save/load JSON profiles
└── profiles/             # saved looks
```

# Troubleshooting

- **"Couldn't reach the OpenRGB SDK server"** → run `./run.sh` (it starts it), or
  `openrgb --server`.
- **Fans dark after closing the app** → expected (Direct-mode-only board). Relaunch
  the app, or reboot for the default red.
- **RAM box greyed out** → log out/in (i2c group), or check `ls -l /dev/i2c-0`
  shows group `i2c` and mode `660`.
- **No devices in OpenRGB** → reboot after installing OpenRGB; confirm they show
  in the OpenRGB app's Devices tab.
