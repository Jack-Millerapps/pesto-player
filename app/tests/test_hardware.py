import os
import subprocess

import config
from hardware import battery, system


def test_sysfs_battery_reads_battery_type_only(tmp_path):
    for name, typ, cap in (("ac", "Mains", "100"), ("bat0", "Battery", "42")):
        d = tmp_path / name
        d.mkdir()
        (d / "type").write_text(typ)
        (d / "capacity").write_text(cap)
    assert battery._read_sysfs_capacity(str(tmp_path)) == 42
    assert battery._read_sysfs_capacity(str(tmp_path / "missing")) is None


def test_battery_unknown_when_no_source(monkeypatch):
    monkeypatch.setattr(battery, "_read_sysfs_capacity", lambda *a: None)
    b = battery.BatteryMonitor()
    assert b.get_level() is None and not b.available
    assert not b.is_low() and not b.is_critical()


def test_display_power_without_backlight(tmp_path):
    d = system.DisplayPower(str(tmp_path))
    assert not d.has_backlight and d.get_brightness() is None
    d.sleep(); assert d.asleep
    d.wake(); assert not d.asleep


def test_display_power_with_backlight(tmp_path):
    n = tmp_path / "bl"
    n.mkdir()
    (n / "max_brightness").write_text("255")
    (n / "brightness").write_text("255")
    d = system.DisplayPower(str(tmp_path))
    d.sleep()
    assert (n / "brightness").read_text() == "0"
    d.wake()
    assert (n / "brightness").read_text() == "255"
    d.set_brightness(50)
    assert abs(int((n / "brightness").read_text()) - 128) <= 1


def test_shutdown_never_runs_in_test_mode(monkeypatch):
    called = []
    monkeypatch.setattr(config, "TEST_MODE", True)
    assert system.shutdown(runner=lambda *a, **k: called.append(a)) is False
    assert called == []


def test_shutdown_falls_back_to_sudo(monkeypatch):
    monkeypatch.setattr(config, "TEST_MODE", False)
    cmds = []

    def runner(cmd, **kw):
        cmds.append(cmd)
        return subprocess.CompletedProcess(cmd, 1 if cmd[0] == "systemctl" else 0)

    assert system.reboot(runner=runner) is True
    assert cmds == [["systemctl", "reboot"], ["sudo", "-n", "systemctl", "reboot"]]


def test_disk_info_walks_up_to_existing_parent(tmp_path):
    free, total = system.disk_info(str(tmp_path / "a" / "b"))
    assert free and total and free <= total
    assert system.human_bytes(1536) == "1.5 KB" and system.human_bytes(None) == "?"
