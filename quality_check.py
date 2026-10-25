"""Real GPU comparison, using public sample speech instead of your microphone."""
from runtime import ROOT, configure
configure(offline=True)
import json
import sys
from studio import run_job

def main():
    report_path = ROOT / "work" / "quality-check.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {"note":"Signal checks and timings only. Listen before accepting audio quality.", "runs":[]}
    cases = [("convert","Male demo voice"), ("convert","Female demo voice")]
    if "--with-tts" in sys.argv:
        cases.append(("tts","Female demo voice"))
    if "--first-only" in sys.argv:
        cases = cases[:1]
    for mode, voice in cases:
        if any(r["mode"]==mode and r["voice"]==voice and (ROOT/r["folder"]/"result.json").exists() for r in report["runs"]):
            print("Already complete:", mode, voice, flush=True)
            continue
        print("Running:", mode, voice, flush=True)
        job, result = run_job(mode, str(ROOT / "inputs" / "demo-source.wav"), voice, None,
            text="Control, this is Ranger Two. The northern route is clear. We are returning to base.",
            preset="Radio", static=0.3, seed=42)
        report["runs"].append({"mode":mode,"voice":voice,"folder":str(job.relative_to(ROOT)),**result})
        print("Saved:", job.name, result, flush=True)
        (ROOT / "work" / "quality-check.json").write_text(json.dumps(report,indent=2))
    print("Comparisons ready for listening.",flush=True)

if __name__ == "__main__":
    main()
