"""Regression checks for GNOME overview icon stacking (no running X server)."""

import importlib.util
import os
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location(
    "icon_stacking", Path(__file__).resolve().parent / "keep-desktop-icons.py")
icons = importlib.util.module_from_spec(spec)
spec.loader.exec_module(icons)


class StackingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.proc = self.root / "proc"
        self.proc.mkdir()
        self.renderer = self.root / "linux-wallpaperengine"
        self.renderer.touch()
        self.gjs = self.root / "gjs"
        self.gjs.touch()
        self.rows = []
        self.types = {}
        self.lower = Mock()

    def window(self, wid, pid, executable, title, kind="DESKTOP"):
        process = self.proc / str(pid)
        process.mkdir()
        (process / "exe").symlink_to(executable)
        self.rows.append(f"{wid} -1 {pid} hostname {title}")
        self.types[wid] = f"_NET_WM_WINDOW_TYPE(ATOM) = _NET_WM_WINDOW_TYPE_{kind}"

    def output(self, args, **kwargs):
        if args == ["wmctrl", "-lp"]:
            return "\n".join(self.rows)
        if args[0] == "xprop":
            return self.types[args[2]]
        raise AssertionError(f"Unexpected command: {args}")

    def restore(self, order, uid=None):
        with patch.object(icons.subprocess, "check_output", side_effect=self.output):
            return icons.restore_order(
                "_NET_CLIENT_LIST_STACKING(WINDOW): window id # " + order,
                self.renderer, lower=self.lower, proc_root=self.proc, uid=uid)

    def test_overview_restack_lowers_only_wallpaper_covering_icons(self):
        self.window("0x10", 10, self.renderer, "Wallpaper left")
        self.window("0x20", 20, self.gjs, "Desktop Icons 1")
        self.window("0x30", 30, self.renderer, "Wallpaper right")
        self.assertEqual(self.restore("0x10, 0x20, 0x30"), 1)
        self.lower.assert_called_once_with("0x30")

    def test_corrected_order_emits_no_restack_requests(self):
        self.window("0x10", 10, self.renderer, "Wallpaper left")
        self.window("0x20", 20, self.renderer, "Wallpaper right")
        self.window("0x30", 30, self.gjs, "Desktop Icons 1")
        self.assertEqual(self.restore("0x10, 0x20, 0x30"), 0)
        self.lower.assert_not_called()

    def test_normal_renderer_scan_window_is_not_lowered(self):
        self.window("0x10", 10, self.gjs, "Desktop Icons 1")
        self.window("0x20", 20, self.renderer, "Compatibility scan", "NORMAL")
        self.assertEqual(self.restore("0x10, 0x20"), 0)
        self.lower.assert_not_called()

    def test_other_executable_and_foreign_owner_are_ignored(self):
        other = self.root / "another-renderer"
        other.touch()
        self.window("0x10", 10, self.gjs, "Desktop Icons 1")
        self.window("0x20", 20, other, "Wallpaper")
        self.window("0x30", 30, self.renderer, "Foreign wallpaper")
        original = icons.process_executable

        def process(pid, uid, proc_root):
            if pid == "30":
                return original(pid, os.getuid() + 1, proc_root)
            return original(pid, uid, proc_root)

        with patch.object(icons, "process_executable", side_effect=process):
            self.assertEqual(self.restore("0x10, 0x20, 0x30"), 0)
        self.lower.assert_not_called()

    def test_gjs_console_desktop_icons_are_recognized(self):
        console = self.root / "gjs-console"
        console.touch()
        self.window("0x10", 10, console, "Desktop Icons 2")
        self.window("0x20", 20, self.renderer, "Wallpaper")
        self.assertEqual(self.restore("0x10, 0x20"), 1)
        self.lower.assert_called_once_with("0x20")

    def test_gjs_application_is_not_an_icon_surface(self):
        self.window("0x10", 10, self.gjs, "GNOME application")
        self.window("0x20", 20, self.renderer, "Wallpaper")
        self.assertEqual(self.restore("0x10, 0x20"), 0)
        self.lower.assert_not_called()

    def test_duplicate_property_events_do_not_rescan(self):
        watcher = Mock()
        watcher.stdout = Mock()
        line = "_NET_CLIENT_LIST_STACKING(WINDOW): window id # 0x10, 0x20\n"
        watcher.stdout.__iter__ = Mock(return_value=iter([line, line]))
        watcher.poll.return_value = 0
        with patch.object(icons.subprocess, "Popen", return_value=watcher), \
                patch.object(icons, "restore_order", return_value=0) as restore, \
                patch.object(icons.time, "sleep", side_effect=SystemExit):
            with self.assertRaises(SystemExit):
                icons.watch(self.renderer)
        restore.assert_called_once_with(line, self.renderer)

    def test_signal_exit_terminates_and_reaps_xprop(self):
        watcher = Mock()
        watcher.stdout = Mock()

        def interrupted():
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)

        watcher.stdout.__iter__ = Mock(side_effect=interrupted)
        watcher.poll.return_value = None
        original = signal.getsignal(signal.SIGTERM)
        with patch.object(icons.subprocess, "Popen", return_value=watcher), \
                patch.dict(os.environ, {"XDG_RUNTIME_DIR": str(self.root)}), \
                patch.object(icons, "backend_path", return_value=self.renderer):
            with self.assertRaises(SystemExit):
                icons.main([])
        watcher.terminate.assert_called_once_with()
        watcher.wait.assert_called_once_with(timeout=3)
        watcher.stdout.close.assert_called_once_with()
        self.assertEqual(signal.getsignal(signal.SIGTERM), original)

    def test_second_instance_exits_without_starting_watcher(self):
        with (self.root / "wallpaper-icon-stacking.lock").open("w") as lock:
            icons.fcntl.flock(lock, icons.fcntl.LOCK_EX | icons.fcntl.LOCK_NB)
            with patch.dict(os.environ, {"XDG_RUNTIME_DIR": str(self.root)}), \
                    patch.object(icons, "backend_path", return_value=self.renderer), \
                    patch.object(icons, "watch") as watch:
                icons.main([])
            watch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
