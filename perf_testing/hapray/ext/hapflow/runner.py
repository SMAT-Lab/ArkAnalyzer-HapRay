# -*- coding: utf-8 -*-
import os, sys, json, shutil, subprocess, logging, datetime
from collections import defaultdict
from pathlib import Path
LOG = logging.getLogger(__name__)

def _run(cmd, cwd=None, env=None):
    LOG.info("Run: %s", " ".join(cmd))
    res = subprocess.run(cmd, cwd=cwd, env=env, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if res.returncode != 0:
        LOG.error(res.stdout)
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    if res.stdout:
        LOG.debug(res.stdout)
    return res

def _ensure_dir(p):
    os.makedirs(p, exist_ok=True); return p

def _write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def run_homecheck(homecheck_root: str, out_dir: str):
    tmp_dir = _ensure_dir(os.path.join(out_dir, "homecheck_tmp"))
    tool = os.path.join(homecheck_root, "node_modules", "homecheck", "lib", "tools", "toolRun.js")
    proj_cfg = os.path.join(homecheck_root, "config", "projectConfig.json")
    _run([
        "node", "--max-old-space-size=16384",
        tool,
        f"--projectConfigPath={proj_cfg}",
        f"--depGraphOutputDir={tmp_dir}"
    ], cwd=homecheck_root)

    for name in ("fileDepGraph.json", "moduleDepGraph.json"):
        src = os.path.join(tmp_dir, name); dst = os.path.join(out_dir, name)
        if not os.path.exists(src):
            raise FileNotFoundError(f"Homecheck missing {name}")
        shutil.copy(src, dst)
        LOG.info("Homecheck -> %s", dst)
def _has_ts_subdirs(p: Path) -> bool:
    if not p.is_dir():
        return False
    for d in p.iterdir():
        if d.is_dir() and d.name.isdigit() and len(d.name) == 14:
            return True
    return False

def resolve_reports_root(reports_root: str | None) -> str:
    candidates = []

    if reports_root:
        candidates.append(Path(reports_root))

    here = Path(__file__).resolve()
    candidates.append(here.parents[3] / "reports")
    candidates.append(Path.cwd() / "reports")
    candidates.append(here.parents[2] / "reports") 

    for p in candidates:
        try:
            if _has_ts_subdirs(p):
                LOG.info("Resolved reports_root -> %s", p)
                return str(p)
        except Exception:
            pass

    raise FileNotFoundError(
        "No timestamp folder in reports/ (tried: %s)" %
        "; ".join(str(c) for c in candidates)
    )


def pick_latest_case_dirs(reports_root: str):
    ts_list = [d for d in os.listdir(reports_root)
               if d.isdigit() and len(d) == 14 and os.path.isdir(os.path.join(reports_root, d))]
    if not ts_list:
        raise FileNotFoundError("No timestamp folder in reports/")
    ts_list.sort(reverse=True)
    latest = os.path.join(reports_root, ts_list[0])
    cases = [os.path.join(latest, d) for d in os.listdir(latest)
             if os.path.isdir(os.path.join(latest, d)) and "_round" not in d]
    if not cases:
        raise FileNotFoundError("No case folder found in latest reports/")
    return latest, cases

def extract_hapray_outputs(reports_root: str, out_dir: str):
    latest_ts, cases = pick_latest_case_dirs(reports_root)

    chosen = None
    for c in cases:
        p = os.path.join(c, "report", "hapray_report.json")
        if os.path.exists(p):
            chosen = p
    if not chosen:
        raise FileNotFoundError("hapray_report.json not found in cases")
    shutil.copy(chosen, os.path.join(out_dir, "hapray_report.json"))
    LOG.info("Copied hapray_report.json from %s", chosen)

    har_items = []
    for c in cases:
        info = os.path.join(c, "hiperf", "hiperf_info.json")
        if not os.path.exists(info): 
            continue
        try:
            with open(info, "r", encoding="utf-8") as f:
                obj = json.load(f)
        except Exception:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("har"), list):
            har_items += obj["har"]
        elif isinstance(obj, list):
            for blk in obj:
                if isinstance(blk, dict) and isinstance(blk.get("har"), list):
                    har_items += blk["har"]
    if not har_items:
        LOG.warning("No HAR items from hiperf_info.json; write empty list.")
    har_items.sort(key=lambda x: x.get("count", 0), reverse=True)
    _write_json(os.path.join(out_dir, "component_timings.json"), har_items)
    LOG.info("Wrote component_timings.json (%d items)", len(har_items))

def get_hapray_data_list(data: dict):
    try:
        return data["perf"]["steps"][0]["data"]
    except (KeyError, IndexError):
        LOG.warning("hapray_report missing perf.steps[0].data")
        return []

def integrate_four(in_dir: str, out_path: str):
    fileDepGraph_data   = json.load(open(os.path.join(in_dir, "fileDepGraph.json"), "r", encoding="utf-8"))
    moduleDepGraph_data = json.load(open(os.path.join(in_dir, "moduleDepGraph.json"), "r", encoding="utf-8"))
    hapray_report_data  = json.load(open(os.path.join(in_dir, "hapray_report.json"), "r", encoding="utf-8"))
    component_timings   = json.load(open(os.path.join(in_dir, "component_timings.json"), "r", encoding="utf-8"))

    har_timing = {}
    for it in component_timings:
        if "name" in it:
            name = it["name"]
            if name.startswith("@ohos/"):
                name = name.split("/")[1]
            har_timing[name] = it.get("count", 0)

    hap_data = get_hapray_data_list(hapray_report_data)
    file_timing_by_name = {
        os.path.basename(it["file"]): it.get("fileEvents", 0)
        for it in hap_data if "file" in it
    }

    har_short_names = {os.path.basename(n["name"]) for n in moduleDepGraph_data.get("nodes", [])}
    file_to_har = {}
    for n in fileDepGraph_data.get("nodes", []):
        fpath = n["name"]; chosen = "无法推断"
        for part in reversed(os.path.normpath(fpath).split(os.sep)):
            part = part.split('.')[0]
            if part in har_short_names:
                chosen = part; break
        file_to_har[fpath] = chosen

    full_file_timing = {}
    for n in fileDepGraph_data.get("nodes", []):
        fname = os.path.basename(n["name"])
        full_file_timing[n["name"]] = file_timing_by_name.get(fname, 0)

    out = {
        "harGraph": {"nodes": [], "edges": moduleDepGraph_data.get("edges", [])},
        "fileGraphs": defaultdict(lambda: {"nodes": [], "edges": []}),
        "crossHarDependencies": []
    }

    har_nodes_map = {}
    for n in moduleDepGraph_data.get("nodes", []):
        short = os.path.basename(n["name"]); n["name"] = short
        n["timing_cycles"] = har_timing.get(short, 0)
        out["harGraph"]["nodes"].append(n)
        har_nodes_map[n["id"]] = short

    file_id_to_har = {}
    for n in fileDepGraph_data.get("nodes", []):
        f = n["name"]; har = file_to_har.get(f)
        if har and har != "无法推断":
            n["timing_cycles"] = full_file_timing.get(f, 0)
            out["fileGraphs"][har]["nodes"].append(n)
            file_id_to_har[n["id"]] = har

    cross_tmp = defaultdict(lambda: defaultdict(int))
    for e in fileDepGraph_data.get("edges", []):
        s, t = e["source"], e["target"]
        hs, ht = file_id_to_har.get(s), file_id_to_har.get(t)
        if not hs or not ht: 
            continue
        if hs == ht:
            out["fileGraphs"][hs]["edges"].append(e)
        else:
            cross_tmp[s][ht] += 1

    for sid, tgts in cross_tmp.items():
        for har_t, cnt in tgts.items():
            out["crossHarDependencies"].append({"sourceId": sid, "targetHarId": har_t, "count": cnt})

    final = {
        "harGraph": out["harGraph"],
        "fileGraphs": dict(out["fileGraphs"]),
        "crossHarDependencies": out["crossHarDependencies"]
    }
    _write_json(out_path, final)
    LOG.info("Wrote %s", out_path)




def run_hapflow_pipeline(reports_root: str, homecheck_root: str):
    reports_root = resolve_reports_root(reports_root)

    latest_ts, _ = pick_latest_case_dirs(reports_root)
    out_dir = _ensure_dir(os.path.join(latest_ts, "hapflow"))

    tool = os.path.join(homecheck_root, "node_modules", "homecheck", "lib", "tools", "toolRun.js")
    proj_cfg = os.path.join(homecheck_root, "config", "projectConfig.json")
    do_homecheck = os.path.isfile(tool) and os.path.isfile(proj_cfg)

    if do_homecheck:
        LOG.info("[Homecheck] RUN (tool: %s)", tool)
        LOG.info("=== HapFlow: run Homecheck ===")
        run_homecheck(homecheck_root, out_dir)
    else:
        LOG.info("[Homecheck] SKIP (missing tool/config under %s)", homecheck_root)

    LOG.info("=== HapFlow: extract HapRay outputs ===")
    extract_hapray_outputs(reports_root, out_dir)

    LOG.info("=== HapFlow: integrate four files ===")
    integrate_four(out_dir, os.path.join(out_dir, "hierarchical_integrated_data.json"))

    LOG.info("=== HapFlow: prepare viewer ===")

    LOG.info("HapFlow is ready: %s", out_dir)

