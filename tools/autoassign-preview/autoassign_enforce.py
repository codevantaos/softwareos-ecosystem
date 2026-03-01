import json, os, re, sys, time, uuid
from pathlib import Path
import urllib.request

import yaml

DEGRADED_MARK = "[AUTOASSIGN_DEGRADED]"
DONE_MARK = "[AUTOASSIGN_DONE]"
LABEL_RETRY = "autoassign-retry"
LABEL_DEGRADED = "autoassign-degraded"

def die(msg: str, code: int = 2):
  print(f"[autoassign-enforce] ERROR: {msg}", file=sys.stderr)
  raise SystemExit(code)

def log(msg: str):
  print(f"[autoassign-enforce] {msg}")

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

def github_api_json(url: str, token: str, method: str = "GET", payload: dict | None = None, retry: int = 3):
  data = None
  headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "User-Agent": "autoassign-enforce"
  }
  if payload is not None:
    data = json.dumps(payload).encode("utf-8")
    headers["Content-Type"] = "application/json"

  last_err = None
  for attempt in range(1, retry + 1):
    try:
      req = urllib.request.Request(url, data=data, headers=headers, method=method)
      with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body else {}
    except Exception as e:
      last_err = e
      time.sleep(1.5 * attempt)
  raise last_err

def fetch_pr_files(repo: str, pr_number: int, token: str) -> list[str]:
  files: list[str] = []
  page = 1
  per_page = 100
  while True:
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/files?per_page={per_page}&page={page}"
    items = github_api_json(url, token, "GET")
    if not isinstance(items, list):
      die("Unexpected PR files API response")
    if not items:
      break
    for it in items:
      fn = it.get("filename")
      if fn:
        files.append(fn)
    if len(items) < per_page:
      break
    page += 1
  return files

def safe_fetch_pr_files(repo: str, pr_number: int, token: str) -> tuple[list[str], dict]:
  try:
    files = fetch_pr_files(repo, pr_number, token)
    return files, {}
  except Exception as e:
    note = {
      "degraded": True,
      "reason": f"fetch_pr_files_failed: {type(e).__name__}: {e}",
      "strategy": "labels/keywords/default-only",
      "changed_files": []
    }
    return [], note

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

def build_evidence(maintainers: dict, ruleset: dict, codeowners_rules, ctx: dict, *, degrade_note: dict | None = None):
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
  evidence = {
    "version": 1,
    "trace_id": trace_id,
    "input": ctx,
    "matched_rules": [{"id": rule["id"], "priority": int(rule["priority"]), "why": why}],
    "ranked_candidates": [
      {
        "login": a,
        "score": 10.0 * float(ownership_hits > 0),
        "signals": {"ownership": float(ownership_hits > 0), "label": 0.0, "keyword": 0.0, "path": 0.0}
      } for a in assignees
    ],
    "decision": {"team_id": team_id, "assignees": assignees},
    "notes": {
      "preview_only": False,
      "ownership_hits": ownership_hits,
      "enforce_guard": "writes only when routing-rules.settings.mode == enforce",
      "degrade": degrade_note or {}
    }
  }
  return evidence

def apply_assignees(repo: str, number: int, token: str, assignees: list[str]):
  url = f"https://api.github.com/repos/{repo}/issues/{number}/assignees"
  return github_api_json(url, token, "POST", {"assignees": assignees})

def main():
  token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
  repo = os.environ.get("GITHUB_REPOSITORY")
  event_path = os.environ.get("GITHUB_EVENT_PATH")
  if not token:
    die("Missing GITHUB_TOKEN")
  if not repo:
    die("Missing GITHUB_REPOSITORY")
  if not event_path:
    die("Missing GITHUB_EVENT_PATH")

  maintainers_path = os.environ.get("MAINTAINERS_PATH", "MAINTAINERS.yaml")
  rules_path = os.environ.get("RULES_PATH", "routing-rules.yaml")
  codeowners_path = os.environ.get("CODEOWNERS_PATH", "CODEOWNERS")

  maintainers = load_yaml(maintainers_path)
  ruleset = load_yaml(rules_path)
  codeowners_rules = parse_codeowners(load_text(codeowners_path))
  verify_semantics(maintainers, ruleset)

  mode = (ruleset.get("settings") or {}).get("mode")
  if mode not in ["preview", "enforce"]:
    die("routing-rules.settings.mode must be preview|enforce")

  event = load_json(event_path)
  ctx = normalize_event(event)

  degrade_note = {}
  if ctx["event"] == "pull_request":
    files, degrade_note = safe_fetch_pr_files(repo, ctx["number"], token)
    ctx["changed_files"] = files

  evidence = build_evidence(maintainers, ruleset, codeowners_rules, ctx, degrade_note=degrade_note)
  Path("autoassign.evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
  log("wrote autoassign.evidence.json")

  if mode == "preview":
    log("mode=preview; skip apply")
    return

  from github_exec import add_labels, add_issue_comment, add_assignees, request_pr_reviewers, remove_label

  if mode == "enforce" and degrade_note.get("degraded") is True:
    try:
      add_labels(repo, ctx["number"], token, [LABEL_DEGRADED, LABEL_RETRY])
    except Exception:
      pass

    body = (
      f"{DEGRADED_MARK}\n"
      f"AutoAssign degraded (no apply)\n"
      f"- reason: {degrade_note.get('reason')}\n"
      f"- strategy: {degrade_note.get('strategy')}\n"
      f"- next: scheduled retry via label={LABEL_RETRY}\n"
      f"- trace_id: {evidence['trace_id']}\n"
    )
    try:
      add_issue_comment(repo, ctx["number"], token, body)
    except Exception:
      pass

    log("degraded=true; skip apply; scheduled retry label")
    return

  ignore_if_assigned = bool((ruleset.get("settings") or {}).get("ignore_if_assigned", True))
  if ignore_if_assigned and (ctx.get("assignees") or []):
    log("already has assignees; ignore_if_assigned=true; skip apply")
    return

  assignees = evidence["decision"]["assignees"]
  apply_assignees(repo, ctx["number"], token, assignees)
  log(f"applied assignees={assignees}")

  if ctx["event"] == "pull_request":
    try:
      request_pr_reviewers(repo, ctx["number"], token, assignees)
      log(f"requested reviewers={assignees}")
    except Exception as e:
      add_issue_comment(repo, ctx["number"], token, f"AutoAssign: request_reviewers failed, degraded to assignees only.\nerror: {e}")
      log("request_reviewers failed; degraded to comment")

  try:
    add_issue_comment(repo, ctx["number"], token, f"{DONE_MARK}\nAutoAssign done\n- trace_id: {evidence['trace_id']}\n")
  except Exception:
    pass

  for lb in [LABEL_RETRY, LABEL_DEGRADED]:
    try:
      remove_label(repo, ctx["number"], token, lb)
    except Exception:
      pass

if __name__ == "__main__":
  main()