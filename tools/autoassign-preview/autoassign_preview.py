import json, os, re, sys, uuid
from pathlib import Path

import yaml

def die(msg: str, code: int = 2):
  print(f"[autoassign-preview] ERROR: {msg}", file=sys.stderr)
  raise SystemExit(code)

def load_yaml(path: str):
  return yaml.safe_load(Path(path).read_text(encoding="utf-8"))

def load_json(path: str):
  return json.loads(Path(path).read_text(encoding="utf-8"))

def load_text(path: str):
  return Path(path).read_text(encoding="utf-8")

def parse_codeowners(text: str):
  rules = []
  for raw in text.splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
      continue
    parts = line.split()
    if len(parts) < 2:
      continue
    rules.append((parts[0], parts[1:]))
  return rules

def match_glob(path: str, pattern: str) -> bool:
  pat = re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
  return re.fullmatch(pat, path) is not None

def codeowners_for_file(rules, file_path: str):
  owners = []
  for pat, os_ in rules:
    if match_glob("/" + file_path.lstrip("/"), pat) or match_glob(file_path, pat):
      owners = os_
  return owners

def normalize_event(event: dict):
  if "issue" in event:
    obj = event["issue"]
    labels = [x.get("name","") for x in (obj.get("labels") or []) if isinstance(x, dict)]
    return {
      "event": "issue",
      "number": int(obj["number"]),
      "title": obj.get("title",""),
      "body": obj.get("body",""),
      "labels": labels,
      "changed_files": [],
      "assignees": [x.get("login","") for x in (obj.get("assignees") or []) if isinstance(x, dict)]
    }
  if "pull_request" in event:
    pr = event["pull_request"]
    labels = [x.get("name","") for x in (pr.get("labels") or []) if isinstance(x, dict)]
    return {
      "event": "pull_request",
      "number": int(pr["number"]),
      "title": pr.get("title",""),
      "body": pr.get("body",""),
      "labels": labels,
      "changed_files": [],
      "assignees": [x.get("login","") for x in (pr.get("assignees") or []) if isinstance(x, dict)]
    }
  die("Unsupported event payload (need issue or pull_request)")

def verify_semantics(maintainers: dict, ruleset: dict):
  teams = {t["id"] for t in maintainers.get("teams", [])}
  if maintainers.get("repo", {}).get("default_team") not in teams:
    die("MAINTAINERS.repo.default_team must exist in teams")

  rules = ruleset.get("rules") or []
  if not rules:
    die("routing-rules.yaml rules must not be empty")

  defaults = [i for i, r in enumerate(rules) if (r.get("when") or {}).get("always") is True]
  if len(defaults) != 1:
    die("Must have exactly one default rule: when.always=true")
  if defaults[0] != len(rules) - 1:
    die("Default rule must be last")

  prios = [int(r["priority"]) for r in rules]
  if prios != sorted(prios):
    die("Rules priority must be sorted ascending")

  for r in rules:
    tid = (r.get("route") or {}).get("team_id")
    if tid not in teams:
      die(f"routing-rules.yaml references unknown team_id: {tid}")

def pick_rule(ruleset: dict, ctx: dict):
  text = (ctx.get("title","") + "\n" + ctx.get("body","")).lower()
  labels = set(ctx.get("labels") or [])
  files = ctx.get("changed_files") or []

  for r in ruleset["rules"]:
    w = r.get("when") or {}

    ev = w.get("event")
    if ev and ev != ctx["event"]:
      continue

    if w.get("always") is True:
      return r, "default"

    any_labels = w.get("any_labels") or []
    if any_labels and not any(l in labels for l in any_labels):
      continue

    any_keywords = w.get("any_keywords") or []
    if any_keywords and not any(k.lower() in text for k in any_keywords):
      continue

    any_files = w.get("any_files") or []
    if any_files:
      if ctx["event"] != "pull_request":
        continue
      ok = any(any(match_glob(f, p) for p in any_files) for f in files)
      if not ok:
        continue

    return r, "matched"

  die("No rule matched (missing default?)")

def build_evidence(maintainers: dict, ruleset: dict, codeowners_rules, ctx: dict):
  teams_by_id = {t["id"]: t for t in maintainers["teams"]}
  rule, why = pick_rule(ruleset, ctx)

  team_id = rule["route"]["team_id"]
  team = teams_by_id[team_id]
  strategy = rule["route"].get("strategy", "team_members")

  ownership_hits = 0
  if ctx["event"] == "pull_request":
    for f in (ctx["changed_files"] or []):
      owners = codeowners_for_file(codeowners_rules, f)
      if any(f"@codevantaeco/{team_id}" == o for o in owners):
        ownership_hits += 1

  max_assignees = int(ruleset["settings"]["max_assignees"])
  if strategy == "oncall_only":
    assignees = team["escalation"]["oncall"][:max_assignees]
  else:
    assignees = sorted(team["members"])[:max_assignees]

  trace_id = uuid.uuid4().hex[:12]
  return {
    "version": 1,
    "trace_id": trace_id,
    "input": ctx,
    "matched_rules": [
      {"id": rule["id"], "priority": int(rule["priority"]), "why": why}
    ],
    "ranked_candidates": [
      {
        "login": a,
        "score": 10.0 * float(ownership_hits > 0),
        "signals": {"ownership": float(ownership_hits > 0), "label": 0.0, "keyword": 0.0, "path": 0.0}
      } for a in assignees
    ],
    "decision": {"team_id": team_id, "assignees": assignees},
    "notes": {
      "preview_only": True,
      "changed_files_in_preview": "empty unless provided by caller; enforce phase will fetch files via GitHub API"
    }
  }

def main():
  maintainers_path = os.environ.get("MAINTAINERS_PATH", "MAINTAINERS.yaml")
  rules_path = os.environ.get("RULES_PATH", "routing-rules.yaml")
  codeowners_path = os.environ.get("CODEOWNERS_PATH", "CODEOWNERS")
  event_path = os.environ.get("GITHUB_EVENT_PATH")

  if not event_path:
    die("GITHUB_EVENT_PATH is missing")

  maintainers = load_yaml(maintainers_path)
  ruleset = load_yaml(rules_path)
  codeowners_rules = parse_codeowners(load_text(codeowners_path))
  event = load_json(event_path)

  verify_semantics(maintainers, ruleset)

  ctx = normalize_event(event)
  evidence = build_evidence(maintainers, ruleset, codeowners_rules, ctx)

  out = Path("autoassign.evidence.json")
  out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
  print(f"[autoassign-preview] wrote {out}")

if __name__ == "__main__":
  main()