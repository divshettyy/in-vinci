import glob, json, os, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import validate_plans as v
import retime_plans as r


class CommittedPlans(unittest.TestCase):
    def test_every_plan_is_beat_synced(self):
        for p in glob.glob(os.path.join(ROOT, "plans", "*.json")):
            if p.endswith("_beats.json"):
                continue
            plan = json.load(open(p)); beats = json.load(open(p[:-5] + "_beats.json"))
            self.assertEqual(v.check_plan(plan, beats), [], os.path.basename(p))


class Retime(unittest.TestCase):
    def test_drift_is_removed_and_total_preserved(self):
        # 0.4s = 12 frames per clip is exact; naive rounding of 0.43s gives drift
        bounds = [0.0, 0.43, 0.86, 1.29, 1.72]
        plan = {"boundaries_s": bounds, "total_frames": 52,
                "video_adds": [{"durationInFrames": 13}] * 4}
        d = r.retime(plan)
        self.assertEqual(sum(d), 52)
        acc = 0
        for i, x in enumerate(d[:-1]):
            acc += x
            self.assertLessEqual(abs(acc / 30 - bounds[i + 1]), 0.5 / 30 + 1e-9)

    def test_missing_boundaries_returns_none(self):
        self.assertIsNone(r.retime({"video_adds": [{"durationInFrames": 5}]}))


if __name__ == "__main__":
    unittest.main()
