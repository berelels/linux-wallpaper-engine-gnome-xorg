import json
from pathlib import Path
import tempfile
import unittest
from wallpaper_content import resolve_background, prepare_arguments

class PresetTests(unittest.TestCase):
    def test_preset_resolves_and_preserves_override_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, data in {'1': {'type':'scene','file':'scene.json','general':{'properties':{'color':{},'clock':{}}}},
                               '2': {'dependency':'1','preset':{'color':'1 0 0','clock':False,'unknown':2}}}.items():
                (root/name).mkdir(); (root/name/'project.json').write_text(json.dumps(data))
            path, flags = resolve_background(str(root/'2'))
            self.assertEqual(path, str(root/'1'))
            self.assertEqual(flags, ['--set-property','color=1 0 0','--set-property','clock=false'])
            args = prepare_arguments(['--bg',str(root/'2'),'--set-property','clock=true'])
            self.assertEqual(args[-1], 'clock=true')
            self.assertEqual(json.loads((root/'2/project.json').read_text())['dependency'],'1')
    def test_missing_dependency_reports_workshop_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'1';p.mkdir();(p/'project.json').write_text('{"dependency":"123"}')
            with self.assertRaisesRegex(ValueError,'123'):resolve_background(str(p))
    def test_cycles_and_path_traversal_are_rejected(self):
        for dependency in ('1','../other'):
            with tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/'1';p.mkdir();(p/'project.json').write_text(json.dumps({'dependency':dependency}))
                with self.assertRaises(ValueError):resolve_background(str(p))
    def test_background_without_manifest_is_unchanged(self):
        self.assertEqual(resolve_background('123456789'),('123456789',[]))
