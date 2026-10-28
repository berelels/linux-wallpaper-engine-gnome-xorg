import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('bridge',str(Path(__file__).resolve().parent / 'gnome-backend.py'))
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
class PlacementTests(unittest.TestCase):
 def test_monitor_coordinates(self):
  layout='HDMI-0 connected primary 1920x1080+1920+0 (normal)\nHDMI-1-2 connected 1920x1080+0+0 (normal)\nDP-0 disconnected\n'
  with patch.object(bridge.subprocess,'check_output',return_value=layout):
   self.assertEqual(bridge.monitors(),{'HDMI-0':('1920','0','1920','1080'),'HDMI-1-2':('0','0','1920','1080')})
 def test_negative_monitor_coordinates(self):
  layout='DP-0 connected primary 1920x1080-1920+0 (normal)\nHDMI-0 connected 1080x1920+0-540 (normal)\n'
  with patch.object(bridge.subprocess,'check_output',return_value=layout):
   self.assertEqual(bridge.monitors(),{'DP-0':('-1920','0','1920','1080'),'HDMI-0':('0','-540','1080','1920')})
 def test_desktop_type_precedes_position_and_below(self):
  with patch.object(bridge.subprocess,'run') as run, patch.object(bridge,'lower_desktop') as lower:
   bridge.pin('0x123',('1920','0','1920','1080'))
  lower.assert_called_once_with('0x123')
  commands=[c.args[0] for c in run.call_args_list]
  self.assertEqual(commands[0][-1], '_NET_WM_WINDOW_TYPE_DESKTOP')
  self.assertIn(['wmctrl','-i','-r','0x123','-b','remove,above,below'],commands)
  self.assertIn(['wmctrl','-i','-r','0x123','-b','add,sticky'],commands)
  self.assertEqual(commands[-1][-1],'0,1920,0,1920,1080')
 def test_parent_death_kills_even_a_suspended_renderer(self):
  from unittest.mock import MagicMock
  libc=MagicMock();libc.prctl.return_value=0
  with patch.object(bridge.ctypes,'CDLL',return_value=libc),patch.object(bridge.os,'getppid',return_value=123):
   bridge.renderer_lifetime()
  libc.prctl.assert_called_once_with(1,bridge.signal.SIGKILL,0,0,0)
 def test_disconnected_monitor_does_not_block_an_active_monitor(self):
  from unittest.mock import MagicMock
  child=MagicMock();child.pid=321;child.poll.side_effect=[None,0,0]
  geometry=('0','0','1920','1080')
  with patch.object(bridge.sys,'argv',['bridge','/backend','--screen-root','missing','--screen-root','main']),patch.object(bridge,'monitors',return_value={'main':geometry}),patch.object(bridge.subprocess,'Popen',return_value=child) as spawn,patch.object(bridge.subprocess,'check_output',return_value='0x123 0 321 host wallpaper'),patch.object(bridge,'pin') as pin:
   bridge.main()
  self.assertEqual(spawn.call_count,1)
  pin.assert_called_once_with('0x123',geometry)
 def test_invalid_monitor_does_not_launch(self):
  with patch.object(bridge.sys,'argv',['bridge','/backend','--screen-root','missing']),patch.object(bridge,'monitors',return_value={}),patch.object(bridge.subprocess,'Popen') as spawn:
   with self.assertRaises(ValueError): bridge.main()
   spawn.assert_not_called()
if __name__ == '__main__':
 unittest.main()
