"""Optional OpenVINO fallback never blocks a CPU video worker."""
import sys
import types
import unittest
from unittest.mock import patch
from model_runtime import load_detector


class OpenVinoTests(unittest.TestCase):
    def test_torch_remains_default_without_export(self):
        module=types.ModuleType("ultralytics")
        class FakeYOLO:
            def __init__(self,p):self.path=p
            def export(self,*a,**k):raise AssertionError("Export unexpectedly used")
        module.YOLO=FakeYOLO
        with patch.dict(sys.modules,{"ultralytics":module}):
            model,label=load_detector("yolo26n.pt",640,use_openvino=False)
        self.assertEqual(model.path,"yolo26n.pt")
        self.assertEqual(label,"PyTorch")

    def test_graceful_fallback_if_openvino_missing(self):
        module=types.ModuleType("ultralytics")
        class FakeYOLO:
            def __init__(self,p):self.path=p
            def export(self,*a,**k):raise AssertionError("Export unexpectedly used")
        module.YOLO=FakeYOLO
        with patch.dict(sys.modules,{"ultralytics":module}), patch(
                "model_runtime.importlib.util.find_spec",return_value=None):
            model,label=load_detector("yolo26n.pt",640,use_openvino=True)
        self.assertEqual(model.path,"yolo26n.pt")
        self.assertIn("not installed",label)


if __name__=="__main__":unittest.main()
