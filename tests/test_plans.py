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


class ValidatorNegatives(unittest.TestCase):
    BEATS = {"beats": [0.0, 0.5, 1.0, 1.5]}

    def plan(self, durs, **kw):
        p = {"video_adds": [{"durationInFrames": d} for d in durs],
             "total_frames": sum(durs), "cut_count": len(durs), "phase": 0.0}
        p.update(kw)
        return p

    def test_good_plan_passes(self):
        self.assertEqual(v.check_plan(self.plan([15, 15, 15]), self.BEATS), [])

    def test_off_beat_cut_is_reported(self):
        errs = v.check_plan(self.plan([20, 10, 15]), self.BEATS)
        self.assertTrue(any("off the nearest beat" in e for e in errs))

    def test_flicker_clip_is_reported(self):
        errs = v.check_plan(self.plan([15, 2, 13, 15]), self.BEATS)
        self.assertTrue(any("flicker" in e for e in errs))

    def test_total_and_count_mismatch(self):
        errs = v.check_plan(self.plan([15, 15], total_frames=99, cut_count=5), self.BEATS)
        self.assertEqual(len([e for e in errs if "!=" in e]), 2)

    def test_empty_beat_map(self):
        self.assertIn("beat map has no beats", v.check_plan(self.plan([15, 15]), {"beats": []}))


if __name__ == "__main__":
    unittest.main()
