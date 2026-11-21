import glob, json, os, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import validate_plans as v
import retime_plans as r
import align_drop as ad


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

class OffsetReport(unittest.TestCase):
    PLAN = {"video_adds": [{"durationInFrames": 30}, {"durationInFrames": 31}, {"durationInFrames": 30}]}

    def test_signed_offsets(self):
        # cuts at 1.000s and 2.0333s; beats at 1.0 and 2.0
        offs = v.cut_offsets_ms(self.PLAN, {"beats": [1.0, 2.0]})
        self.assertEqual(offs, [0.0, 33.3])

    def test_audio_offset_is_applied(self):
        plan = dict(self.PLAN, audio_add={"sourceStartFromInSeconds": 5.0})
        self.assertEqual(v.cut_offsets_ms(plan, {"beats": [6.0, 7.0]}), [0.0, 33.3])

    def test_no_beats_gives_empty(self):
        self.assertEqual(v.cut_offsets_ms(self.PLAN, {"beats": []}), [])

    def test_summarize(self):
        self.assertEqual(v.summarize_offsets([-10.0, 20.0]), (15.0, 20.0))
        self.assertEqual(v.summarize_offsets([]), (0.0, 0.0))

class DropAlignment(unittest.TestCase):
    PLAN = {"audio_add": {"sourceStartFromInSeconds": 1.0},
            "video_adds": [{"durationInFrames": 30}] * 4}   # cuts at 1s, 2s, 3s

    def test_cut_on_drop_is_zero(self):
        self.assertEqual(v.drop_alignment_ms(self.PLAN, {"drop_time": 3.0}), 0.0)  # 3.0-1.0=2.0s

    def test_signed_offset(self):
        # drop at plan-time 2.1s -> nearest cut 2.0s is 100 ms early
        self.assertEqual(v.drop_alignment_ms(self.PLAN, {"drop_time": 3.1}), -100.0)

    def test_missing_drop_or_cuts(self):
        self.assertIsNone(v.drop_alignment_ms(self.PLAN, {}))
        self.assertIsNone(v.drop_alignment_ms({"video_adds": [{"durationInFrames": 30}]}, {"drop_time": 1}))


class AlignDrop(unittest.TestCase):
    def _plan(self, durs):
        return {"phase": 0.0, "video_adds": [{"durationInFrames": d} for d in durs],
                "boundaries_s": [0.0] + [round(sum(durs[:i + 1]) / 30, 3) for i in range(len(durs) - 1)] + [round(sum(durs) / 30, 3)]}

    def test_moves_nearest_cut_onto_drop_beat_preserving_total(self):
        plan = self._plan([30, 30, 30, 30])           # cuts at frames 30, 60, 90
        beats = {"beats": [1.0, 2.0, 2.4, 3.0], "drop_time": 2.4}   # beat @ frame 72
        new, info = ad.align(plan, beats)
        self.assertEqual(info["to"], 72)
        self.assertEqual(sum(new), 120)
        self.assertEqual(new, [30, 42, 18, 30])
        ad.apply(plan, new)
        self.assertEqual(plan["boundaries_s"][2], 2.4)

    def test_noop_when_already_on_drop_or_too_far(self):
        plan = self._plan([30, 30, 30, 30])
        self.assertIsNone(ad.align(plan, {"beats": [2.0], "drop_time": 2.0}))
        self.assertIsNone(ad.align(plan, {"beats": [3.9], "drop_time": 3.9}, max_shift=5))
        self.assertIsNone(ad.align(plan, {"beats": [2.0]}))

    def test_refuses_to_create_flicker_clip(self):
        plan = self._plan([30, 5, 30])                # cuts at 30, 35
        beat = 32 / 30.0                              # moving cut 1 -> 32 leaves a 3-frame clip
        self.assertIsNone(ad.align(plan, {"beats": [beat], "drop_time": beat}))


if __name__ == "__main__":
    unittest.main()


class Pacing(unittest.TestCase):
    @staticmethod
    def plan(durs):
        return {"video_adds": [{"durationInFrames": d} for d in durs]}

    def test_accelerating(self):
        p = v.pacing(self.plan([30, 30, 20, 10, 8, 6]))
        self.assertTrue(p["accelerates"]); self.assertFalse(p["monotone"])
        self.assertEqual((p["clips"], p["min_s"], p["max_s"]), (6, 0.2, 1.0))

    def test_monotone_and_decelerating(self):
        p = v.pacing(self.plan([15, 15, 15, 15]))
        self.assertTrue(p["monotone"]); self.assertFalse(p["accelerates"])
        self.assertFalse(v.pacing(self.plan([6, 8, 20, 30]))["accelerates"])

    def test_too_few_clips(self):
        self.assertIsNone(v.pacing(self.plan([30])))
        self.assertIsNone(v.pacing({}))
