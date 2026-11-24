import os, sys, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import preview_timeline as pt


class Timeline(unittest.TestCase):
    PLAN = {"video_adds": [{"durationInFrames": 30}, {"durationInFrames": 30}, {"durationInFrames": 30}]}
    BEATS = {"beats": [0.0, 1.0, 2.0, 3.0], "drop_time": 2.0}

    def test_model_offsets(self):
        m = pt.timeline_model(self.PLAN, self.BEATS)
        self.assertEqual(m["total"], 3.0)
        self.assertEqual([c["off_ms"] for c in m["cuts"]], [0.0, 0.0])
        self.assertEqual(m["drop"], 2.0)

    def test_build_renders_committed_plans(self):
        html = pt.build(os.path.join(ROOT, "plans"))
        self.assertIn("<svg", html)
        self.assertIn("zora", html)

    def test_main_writes_file(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "t.html")
            pt.main([os.path.join(ROOT, "plans"), "-o", out])
            self.assertTrue(os.path.getsize(out) > 500)


if __name__ == "__main__":
    unittest.main()
