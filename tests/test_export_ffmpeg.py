import glob
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import export_ffmpeg as ef


class Export(unittest.TestCase):
    def test_asset_map_has_all_clips(self):
        m = ef.asset_map()
        self.assertEqual(len(m), 17)
        self.assertEqual(m["f8fa989cdb"], "d_chase_vert.mp4")

    def test_every_plan_resolves_and_cuts_match(self):
        m = ef.asset_map()
        for p in glob.glob(os.path.join(ROOT, "plans", "*.json")):
            plan = json.load(open(p))
            if "video_adds" not in plan:
                continue
            cmd = ef.build_command(plan, "clips", "o.mp4", assets=m)
            fc = cmd[cmd.index("-filter_complex") + 1]
            self.assertIn("concat=n=%d" % len(plan["video_adds"]), fc, p)

    def test_crop_and_trim(self):
        f = ef.video_filter({"durationInFrames": 30, "sourceStartFromInSeconds": 2.0,
                             "width": 1166, "height": 2074, "left": -43, "top": -77}, 0, 30)
        self.assertIn("trim=start=2.000:duration=1.000", f)
        self.assertIn("scale=1166:2074,crop=1080:1920:43:77", f)

    def test_unknown_asset(self):
        plan = {"video_adds": [{"assetId": "zzzz", "durationInFrames": 3}], "total_frames": 3,
                "length_s": 0.1, "window": "w.mp3"}
        with self.assertRaises(KeyError):
            ef.build_command(plan, "clips", "o.mp4", assets={})


if __name__ == "__main__":
    unittest.main()
