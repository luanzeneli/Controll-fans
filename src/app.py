"""Desktop GUI for controlling your PC's RGB (fans, RAM, cooler) via OpenRGB.

Run it with:   python -m src.app      (from the project root)
or:            python src/app.py

It needs OpenRGB running with its SDK server:   openrgb --server
"""

from __future__ import annotations

import sys
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QFrame, QGroupBox, QHBoxLayout, QInputDialog, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
    QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from .effects import EFFECTS, EffectEngine
from .monitors import AudioMonitor, TempMonitor
from .ram import RAMController
from .rgb_client import RGBClient
from . import profiles

FPS = 30


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My RGB Control")
        self.resize(620, 640)

        self.client = RGBClient()
        self.engine = EffectEngine(self.client)
        self.temp = TempMonitor()
        self.audio = AudioMonitor()
        self.ram = RAMController()
        self.current_color = (0, 200, 255)
        self.ram_color = (255, 0, 0)

        self._build_ui()

        # animation loop
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(int(1000 / FPS))
        self._last_t = time.monotonic()

        self._try_connect()

    # -- UI construction ----------------------------------------------------

    def _build_ui(self):
        root = QWidget()
        layout = QVBoxLayout(root)

        # connection bar
        conn = QHBoxLayout()
        self.status_label = QLabel("Not connected")
        self.status_label.setStyleSheet("font-weight: bold;")
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._try_connect)
        self.rescan_btn = QPushButton("Rescan devices")
        self.rescan_btn.clicked.connect(self._rescan)
        conn.addWidget(self.status_label, 1)
        conn.addWidget(self.connect_btn)
        conn.addWidget(self.rescan_btn)
        layout.addLayout(conn)

        layout.addWidget(self._hline())

        # device selection
        dev_box = QGroupBox("Devices  (tick the ones you want to control)")
        dev_layout = QVBoxLayout(dev_box)
        self.device_list = QListWidget()
        self.device_list.setSelectionMode(QListWidget.NoSelection)
        dev_layout.addWidget(self.device_list)
        sel_row = QHBoxLayout()
        all_btn = QPushButton("Select all")
        all_btn.clicked.connect(lambda: self._set_all_checks(True))
        none_btn = QPushButton("Select none")
        none_btn.clicked.connect(lambda: self._set_all_checks(False))
        setup_btn = QPushButton("Set up fan LED counts…")
        setup_btn.clicked.connect(self._open_led_setup)
        sel_row.addWidget(all_btn)
        sel_row.addWidget(none_btn)
        sel_row.addStretch(1)
        sel_row.addWidget(setup_btn)
        dev_layout.addLayout(sel_row)
        layout.addWidget(dev_box)

        # effect controls
        fx_box = QGroupBox("Effect")
        fx = QVBoxLayout(fx_box)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Type:"))
        self.effect_combo = QComboBox()
        self.effect_combo.addItems(EFFECTS.keys())
        row1.addWidget(self.effect_combo, 1)
        self.color_btn = QPushButton("Pick colour")
        self.color_btn.clicked.connect(self._pick_color)
        self._update_color_btn()
        row1.addWidget(self.color_btn)
        fx.addLayout(row1)

        self.speed_slider, speed_row = self._slider("Speed", 1, 100, 30)
        fx.addLayout(speed_row)
        self.bright_slider, bright_row = self._slider("Brightness", 1, 100, 100)
        fx.addLayout(bright_row)

        apply_row = QHBoxLayout()
        self.apply_btn = QPushButton("Apply effect")
        self.apply_btn.clicked.connect(self._apply_effect)
        self.stop_btn = QPushButton("Stop animation")
        self.stop_btn.clicked.connect(self.engine.clear)
        self.off_btn = QPushButton("All off")
        self.off_btn.clicked.connect(self._all_off)
        apply_row.addWidget(self.apply_btn, 1)
        apply_row.addWidget(self.stop_btn)
        apply_row.addWidget(self.off_btn)
        fx.addLayout(apply_row)

        self.reactive_label = QLabel("")
        self.reactive_label.setStyleSheet("color: #888;")
        fx.addWidget(self.reactive_label)

        layout.addWidget(fx_box)

        # RAM (Kingston Fury DDR5 — direct SMBus, separate from OpenRGB)
        ram_box = QGroupBox("RAM — Kingston Fury DDR5 (static colour)")
        ram_layout = QHBoxLayout(ram_box)
        self.ram_color_btn = QPushButton("Pick RAM colour")
        self.ram_color_btn.clicked.connect(self._pick_ram_color)
        self.ram_apply_btn = QPushButton("Apply to RAM")
        self.ram_apply_btn.clicked.connect(self._apply_ram)
        self.ram_off_btn = QPushButton("RAM off")
        self.ram_off_btn.clicked.connect(self._ram_off)
        ram_layout.addWidget(self.ram_color_btn)
        ram_layout.addWidget(self.ram_apply_btn)
        ram_layout.addWidget(self.ram_off_btn)
        layout.addWidget(ram_box)
        self.ram_box = ram_box
        self._update_ram_btn()
        self._refresh_ram_availability()

        # profiles
        prof_box = QGroupBox("Profiles")
        prof = QHBoxLayout(prof_box)
        self.profile_combo = QComboBox()
        self._reload_profiles()
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self._load_profile)
        save_btn = QPushButton("Save current…")
        save_btn.clicked.connect(self._save_profile)
        del_btn = QPushButton("Delete")
        del_btn.clicked.connect(self._delete_profile)
        prof.addWidget(self.profile_combo, 1)
        prof.addWidget(load_btn)
        prof.addWidget(save_btn)
        prof.addWidget(del_btn)
        layout.addWidget(prof_box)

        self.setCentralWidget(root)

    def _hline(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    def _slider(self, label, lo, hi, val):
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        s = QSlider(Qt.Horizontal)
        s.setRange(lo, hi)
        s.setValue(val)
        row.addWidget(s, 1)
        return s, row

    # -- connection ---------------------------------------------------------

    def _try_connect(self):
        try:
            self.client.connect()
        except RuntimeError as exc:
            self.status_label.setText("Not connected")
            QMessageBox.warning(self, "Can't connect to OpenRGB", str(exc))
            return
        self._refresh_devices()
        n = len(self.client.devices)
        self.status_label.setText(f"Connected — {n} device(s) found")

    def _rescan(self):
        if not self.client.connected:
            self._try_connect()
            return
        self.client.rescan()
        self._refresh_devices()

    def _refresh_devices(self):
        self.device_list.clear()
        for d in self.client.devices:
            item = QListWidgetItem(f"{d.name}  [{d.type}, {d.led_count} LEDs]")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            item.setData(Qt.UserRole, d.index)
            self.device_list.addItem(item)

    def _open_led_setup(self):
        """Dialog to set how many LEDs are on each (resizable) zone/header.

        ARGB fan headers (e.g. JRAINBOW1/2/3) report 0 LEDs until you tell
        OpenRGB how many fans are daisy-chained on them. Set a count here, hit
        OK, then apply a colour to see them light up. Bump the number until all
        the fans on that header are fully lit.
        """
        if not self.client.connected:
            QMessageBox.information(self, "Not connected",
                                    "Connect to OpenRGB first.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Fan / LED count setup")
        outer = QVBoxLayout(dialog)
        tip = QLabel(
            "Set the number of LEDs on each header. For ARGB fans, multiply\n"
            "fans-on-this-header × LEDs-per-fan. Not sure? Put a generous number\n"
            "(e.g. 60), apply a colour, and lower it until there's no dark tail.")
        tip.setStyleSheet("color:#888;")
        outer.addWidget(tip)

        form = QFormLayout()
        spinners = []  # (device_index, zone_index, spinbox)
        for dev in self.client.devices:
            for zi, (zname, zsize) in enumerate(dev.zones):
                spin = QSpinBox()
                spin.setRange(0, 300)
                spin.setValue(zsize)
                form.addRow(f"{dev.name} — {zname}", spin)
                spinners.append((dev.index, zi, spin))
        outer.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        outer.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return

        errors = []
        for dev_index, zone_index, spin in spinners:
            try:
                self.client.resize_zone(dev_index, zone_index, spin.value())
            except RuntimeError as exc:
                errors.append(str(exc))
        self._refresh_devices()
        if errors:
            QMessageBox.warning(self, "Some zones couldn't resize",
                                "\n".join(errors))
        else:
            QMessageBox.information(
                self, "Done",
                "LED counts updated. Pick an effect and click Apply to test.")

    def _set_all_checks(self, checked: bool):
        state = Qt.Checked if checked else Qt.Unchecked
        for i in range(self.device_list.count()):
            self.device_list.item(i).setCheckState(state)

    def _selected_targets(self):
        targets = []
        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            if item.checkState() == Qt.Checked:
                targets.append(item.data(Qt.UserRole))
        return targets

    # -- colour -------------------------------------------------------------

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(*self.current_color), self, "Pick colour")
        if c.isValid():
            self.current_color = (c.red(), c.green(), c.blue())
            self._update_color_btn()

    def _update_color_btn(self):
        r, g, b = self.current_color
        text_color = "#000" if (r + g + b) > 380 else "#fff"
        self.color_btn.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); color: {text_color};"
        )

    # -- RAM (direct SMBus) -------------------------------------------------

    def _refresh_ram_availability(self):
        """Enable RAM controls only if we can actually reach the SMBus."""
        ok = self.ram.available()
        for btn in (self.ram_color_btn, self.ram_apply_btn, self.ram_off_btn):
            btn.setEnabled(ok)
        if not ok:
            self.ram_box.setTitle(
                "RAM — Kingston Fury DDR5 (unavailable — see tooltip)")
            self.ram_box.setToolTip(self.ram.unavailable_reason())
        else:
            self.ram_box.setTitle("RAM — Kingston Fury DDR5 (static colour)")
            self.ram_box.setToolTip("")

    def _pick_ram_color(self):
        c = QColorDialog.getColor(QColor(*self.ram_color), self, "RAM colour")
        if c.isValid():
            self.ram_color = (c.red(), c.green(), c.blue())
            self._update_ram_btn()

    def _update_ram_btn(self):
        r, g, b = self.ram_color
        text_color = "#000" if (r + g + b) > 380 else "#fff"
        self.ram_color_btn.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); color: {text_color};"
        )

    def _apply_ram(self):
        try:
            self.ram.set_color(self.ram_color)
        except Exception as exc:
            QMessageBox.warning(self, "RAM control failed", str(exc))

    def _ram_off(self):
        try:
            self.ram.turn_off()
        except Exception as exc:
            QMessageBox.warning(self, "RAM control failed", str(exc))

    # -- applying effects ---------------------------------------------------

    def _apply_effect(self):
        if not self.client.connected:
            QMessageBox.information(self, "Not connected",
                                    "Connect to OpenRGB first.")
            return
        targets = self._selected_targets()
        if not targets:
            QMessageBox.information(self, "No devices",
                                    "Tick at least one device to control.")
            return

        name = self.effect_combo.currentText()
        effect_cls = EFFECTS[name]
        effect = effect_cls(
            color=self.current_color,
            speed=self.speed_slider.value() / 30.0,
            brightness=self.bright_slider.value() / 100.0,
        )

        # wire up reactive sources
        self.reactive_label.setText("")
        self.temp.stop()
        self.audio.stop()
        if name == "Temperature":
            if self.temp.available():
                self.temp.start()
                self.reactive_label.setText(
                    "Reacting to CPU temperature (blue=cool, red=hot).")
            else:
                self.reactive_label.setText(
                    "psutil temperature sensors unavailable on this system.")
        elif name == "Audio Reactive":
            if self.audio.available():
                self.audio.start()
                self.reactive_label.setText(
                    "Reacting to audio input. Tip: route speaker output to a "
                    "'monitor' input to react to music.")
            else:
                self.reactive_label.setText(
                    "sounddevice/numpy unavailable — install requirements.")

        self.engine.set_effect(effect, targets)

    def _all_off(self):
        self.engine.clear()
        self.temp.stop()
        self.audio.stop()
        if self.client.connected:
            self.client.turn_off()

    # -- animation loop -----------------------------------------------------

    def _on_tick(self):
        now = time.monotonic()
        dt = now - self._last_t
        self._last_t = now
        effect = self.engine.effect
        if effect is not None:
            # feed live values into reactive effects
            if hasattr(effect, "value"):
                effect.value = self.temp.value
            if hasattr(effect, "level"):
                effect.level = self.audio.level
        self.engine.tick(dt)

    # -- profiles -----------------------------------------------------------

    def _current_settings(self) -> dict:
        return {
            "effect": self.effect_combo.currentText(),
            "color": list(self.current_color),
            "speed": self.speed_slider.value(),
            "brightness": self.bright_slider.value(),
            "targets": self._selected_targets(),
        }

    def _reload_profiles(self):
        self.profile_combo.clear()
        self.profile_combo.addItems(profiles.list_profiles())

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Save profile", "Profile name:")
        if not ok or not name.strip():
            return
        profiles.save_profile(name.strip(), self._current_settings())
        self._reload_profiles()
        self.profile_combo.setCurrentText(name.strip())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        if not name:
            return
        try:
            data = profiles.load_profile(name)
        except FileNotFoundError:
            return
        self.effect_combo.setCurrentText(data.get("effect", "Static"))
        self.current_color = tuple(data.get("color", [0, 200, 255]))
        self._update_color_btn()
        self.speed_slider.setValue(int(data.get("speed", 30)))
        self.bright_slider.setValue(int(data.get("brightness", 100)))
        # restore device selection
        wanted = set(data.get("targets", []))
        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            checked = item.data(Qt.UserRole) in wanted
            item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self._apply_effect()

    def _delete_profile(self):
        name = self.profile_combo.currentText()
        if name:
            profiles.delete_profile(name)
            self._reload_profiles()

    # -- shutdown -----------------------------------------------------------

    def closeEvent(self, event):
        self.temp.stop()
        self.audio.stop()
        self.client.disconnect()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
