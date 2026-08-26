#!/usr/bin/env python3
"""pipeline/worker.py — one entry point to feed text through the stage
pipeline (所有文本处理是一道流水线).

    python3 pipeline/worker.py <workId> [moreIds...] [options]

Reads pipeline/works/<workId>.json manifests, then runs the enabled stages
in numeric order:

    10-fetch -> 20-normalize -> 30-tokenize -> 40-align -> 50-analyze
             -> 60-gloss -> 70-emit -> 90-qa

Each stage is a subprocess `stages/<NN>/stage.py --in <path> --out <path>
--work <id> --config <manifest>`; artifacts chain through a per-work run
dir (.pipeline-run/<workId>/). Failure policy per stage comes from the
manifest ("on_fail": "abort" default | "skip") — see pipeline/ERRORS.md.

Options:
  --apply            copy run-dir outputs into --out-root (default dry-run;
                     QA gates must pass first either way)
  --out-root DIR     publish root (default public/data)
  --run-root DIR     artifact root (default .pipeline-run)
  --stages a,b,c     run only these sections (names without NN- prefix)
  --record-checksums pass through to 10-fetch (bootstrap sidecars)
  --allow-fetch       pass through to 10-fetch (execute fetch commands)
  --log PATH         structured JSON log (default qa-report/logs/<id>.json)

Structured log record:
  {workId, started, finished, status,
   stages: [{stage, status, duration_ms, errors[], warnings[], artifacts[]}]}
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STAGE_RE = re.compile(r"^(\d+)-([a-z]+)$")


def discover_stages() -> list:
    out = []
    for d in sorted(os.listdir(os.path.join(HERE, "stages"))):
        m = STAGE_RE.match(d)
        if m and os.path.exists(os.path.join(HERE, "stages", d, "stage.py")):
            out.append((int(m.group(1)), d, m.group(2)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("works", nargs="+", help="workIds under pipeline/works/")
    ap.add_argument("--manifests", default=os.path.join(REPO, "pipeline",
                                                        "works"))
    ap.add_argument("--out-root", default=os.path.join(REPO, "public",
                                                       "data"))
    ap.add_argument("--run-root", default=os.path.join(REPO,
                                                       ".pipeline-run"))
    ap.add_argument("--stages", help="comma list of section names")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--record-checksums", action="store_true")
    ap.add_argument("--allow-fetch", action="store_true")
    ap.add_argument("--log")
    args = ap.parse_args()

    stages = discover_stages()
    only = set(args.stages.split(",")) if args.stages else None
    any_failed = False

    for work_id in args.works:
        t0 = time.time()
        manifest_path = os.path.join(args.manifests, f"{work_id}.json")
        if not os.path.exists(manifest_path):
            print(f"[worker] no manifest {manifest_path}", file=sys.stderr)
            return 1
        manifest = json.load(open(manifest_path, encoding="utf-8"))
        run_dir = os.path.join(args.run_root, work_id)
        out_dir = os.path.join(run_dir, "out")
        shutil.rmtree(run_dir, ignore_errors=True)
        os.makedirs(out_dir, exist_ok=True)

        record = {"workId": work_id, "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
                  "status": "ok", "stages": [], "manifest": manifest_path}
        prev_artifact, artifacts_idx = None, {}
        failed_at = None

        for _, dirname, section in stages:
            if only and section not in only:
                continue
            sec = manifest.get(section) or {}
            entry = {"stage": dirname, "status": "ok", "duration_ms": 0,
                     "errors": [], "warnings": [], "artifacts": []}
            st = time.time()
            if not sec.get("enabled"):
                entry.update(status="skipped",
                             reason=sec.get("reason",
                                            "not enabled in manifest"))
                record["stages"].append(entry)
                continue
            if failed_at:
                entry.update(status="skipped", reason=f"aborted after "
                             f"{failed_at} (on_fail=abort)")
                record["stages"].append(entry)
                continue

            stage_py = os.path.join(HERE, "stages", dirname, "stage.py")
            artifact = os.path.join(run_dir, f"{dirname}.json")
            stage_in = (os.path.join(run_dir, "artifacts.json")
                        if section == "qa"
                        else prev_artifact or manifest_path)
            cmd = [sys.executable, stage_py,
                   "--in", stage_in,
                   "--out", out_dir if section == "emit" else artifact,
                   "--work", work_id, "--config", manifest_path]
            if section == "fetch":
                if args.record_checksums:
                    cmd.append("--record-checksums")
                if args.allow_fetch:
                    cmd.append("--allow-fetch")
            if section == "qa":
                # gate input: index of everything produced so far
                json.dump(artifacts_idx,
                          open(os.path.join(run_dir, "artifacts.json"), "w"))
            proc = subprocess.run(cmd, cwd=REPO, capture_output=True,
                                  text=True)
            entry["duration_ms"] = int((time.time() - st) * 1000)
            if proc.returncode != 0:
                entry["status"] = "failed"
                tail = [ln for ln in proc.stderr.strip().splitlines() if ln]
                entry["errors"] = tail[-3:] or [f"exit {proc.returncode}"]
                record["stages"].append(entry)
                if sec.get("on_fail", "abort") == "skip":
                    entry["status"] = "failed-skipped"
                    continue          # keep chaining on the LAST good output
                failed_at = dirname
                record["status"] = "failed"
                break
            if section == "tokenize":
                # QA gate: GRETIL ref-marker / apparatus leakage into
                # units[].words[] must abort the chain before align/gloss
                # ever see it (fail-loud; see stages/90-qa/check_words_clean.py).
                chk = subprocess.run(
                    [sys.executable,
                     os.path.join(HERE, "stages", "90-qa",
                                  "check_words_clean.py"),
                     "--in", artifact, "--max-show", "10"],
                    cwd=REPO, capture_output=True, text=True)
                entry["duration_ms"] = int((time.time() - st) * 1000)
                if chk.returncode != 0:
                    entry["status"] = "failed"
                    tail = ([ln for ln in chk.stderr.strip().splitlines()
                             if ln]
                            + [ln for ln in chk.stdout.strip().splitlines()
                               if "VIOLATION" in ln or "FAIL" in ln])
                    entry["errors"] = tail[-3:] or \
                        ["dirty tokens in words[]"]
                    record["stages"].append(entry)
                    failed_at = dirname
                    record["status"] = "failed"
                    break
            if section == "emit":
                entry["artifacts"] = sorted(
                    os.path.relpath(os.path.join(dp, f), run_dir)
                    for dp, _, fs in os.walk(out_dir) for f in fs)
                artifacts_idx["emit"] = out_dir
            else:
                entry["artifacts"] = [os.path.relpath(artifact, run_dir)]
                artifacts_idx[section] = artifact
                prev_artifact = artifact
            record["stages"].append(entry)

        # publish only when the whole chain incl. qa passed
        ran_qa = any(s["stage"].endswith("-qa") and s["status"] == "ok"
                     for s in record["stages"])
        emitted = bool(artifacts_idx.get("emit"))
        if args.apply and not failed_at and ran_qa and emitted:
            published = []
            for dp, _, fs in os.walk(out_dir):
                for f in fs:
                    src = os.path.join(dp, f)
                    relp = os.path.relpath(src, out_dir)
                    if relp.startswith("_artifacts"):
                        continue
                    dst = os.path.join(args.out_root, relp)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copyfile(src, dst)
                    published.append(relp)
            record["published"] = sorted(published)
            record["publish_root"] = os.path.relpath(args.out_root, REPO)

        record["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        record["duration_ms"] = int((time.time() - t0) * 1000)
        if failed_at:
            any_failed = True
        log_path = args.log or os.path.join(REPO, "qa-report", "logs",
                                            f"{work_id}.json")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False, indent=2)
        for e in record["stages"]:
            mark = {"ok": "+", "skipped": "-", "failed": "X",
                    "failed-skipped": "!"}[e["status"]]
            print(f" [{mark}] {e['stage']:<14} {e['status']:<14} "
                  f"{e.get('reason','')}{e.get('errors', [''])[0] if e['status'].startswith('failed') else ''}")
        print(f"[worker] {work_id}: {record['status']} in "
              f"{record['duration_ms']}ms"
              + (f" -> published {len(record.get('published', []))} files"
                 if record.get("published") else ""))

    # corpus-wide home-search gate: after ANY publish, the committed
    # search index must still cover every catalog work and answer the
    # dual-script spot queries (stages/90-qa/check_search_index.py)
    if args.apply:
        gate = subprocess.run(
            [sys.executable,
             os.path.join(HERE, "stages", "90-qa", "check_search_index.py"),
             "--data-root", args.out_root],
            cwd=REPO, capture_output=True, text=True)
        sys.stdout.write(gate.stdout)
        sys.stderr.write(gate.stderr)
        if gate.returncode != 0:
            print("[worker] search-index gate FAILED after publish",
                  file=sys.stderr)
            return 1
        # Pali DPD morphology gate (stages/90-qa/check_morph_pali.py):
        # shard shape + per-work sampled coverage + ṁ/ṃ fold sanity.
        # Self-skips when public/data/morph-pali has not been built.
        pali = subprocess.run(
            [sys.executable,
             os.path.join(HERE, "stages", "90-qa", "check_morph_pali.py"),
             "--data-root", args.out_root],
            cwd=REPO, capture_output=True, text=True)
        sys.stdout.write(pali.stdout)
        sys.stderr.write(pali.stderr)
        if pali.returncode != 0:
            print("[worker] morph-pali gate FAILED after publish",
                  file=sys.stderr)
            return 1
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
