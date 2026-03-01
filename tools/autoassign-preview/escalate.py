import os, json, time
from datetime import datetime, timezone

import yaml
from pathlib import Path

from github_exec import github_api_json, add_issue_comment, add_assignees, request_pr_reviewers

ESCALATION_MARK = "[AUTOASSIGN_ESCALATED]"

def iso_to_dt(s: str) -> datetime:
  return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)

def now_utc() -> datetime:
  return datetime.now(timezone.utc)

def load_yaml(path: str):
  return yaml.safe_load(Path(path).read_text(encoding="utf-8"))

def list_open_issues_and_prs(repo: str, token: str, per_page: int = 50, pages: int = 4):
  out = []
  for page in range(1, pages + 1):
    url = f"https://api.github.com/repos/{repo}/issues?state=open&sort=updated&direction=desc&per_page={per_page}&page={page}"
    items = github_api_json(url, token, "GET")
    if not items:
      break
    out.extend(items)
  return out

def already_escalated(comments: list[dict]) -> bool:
  for c in comments:
    if ESCALATION_MARK in (c.get("body") or ""):
      return True
  return False

def list_comments(repo: str, number: int, token: str, per_page: int = 50, pages: int = 2):
  out=[]
  for page in range(1, pages+1):
    url=f"https://api.github.com/repos/{repo}/issues/{number}/comments?per_page={per_page}&page={page}"
    items=github_api_json(url, token, "GET")
    if not items: break
    out.extend(items)
  return out

def main():
  token = os.environ["GITHUB_TOKEN"]
  repo = os.environ["GITHUB_REPOSITORY"]

  m = load_yaml("MAINTAINERS.yaml")
  teams = {t["id"]: t for t in m["teams"]}

  items = list_open_issues_and_prs(repo, token)

  for it in items:
    number = int(it["number"])
    is_pr = "pull_request" in it
    title = it.get("title","")
    labels = [x.get("name","") for x in (it.get("labels") or []) if isinstance(x, dict)]
    assignees = [x.get("login","") for x in (it.get("assignees") or []) if isinstance(x, dict)]
    created_at = iso_to_dt(it["created_at"])
    updated_at = iso_to_dt(it["updated_at"])

    team_id = "triage"
    for tid, t in teams.items():
      if any(l in set(labels) for l in (t.get("routing",{}).get("labels") or [])):
        team_id = tid
        break

    team = teams[team_id]
    fr = int(team["sla"]["first_response_hours"])
    rv = int(team["sla"]["review_hours"])

    age_h = (now_utc() - created_at).total_seconds() / 3600.0
    idle_h = (now_utc() - updated_at).total_seconds() / 3600.0

    need = False
    reason = ""

    if not assignees and age_h >= fr:
      need = True
      reason = f"no assignees after {fr}h (age={age_h:.1f}h)"
    elif assignees and idle_h >= rv:
      need = True
      reason = f"stale after {rv}h (idle={idle_h:.1f}h)"

    if not need:
      continue

    comments = list_comments(repo, number, token)
    if already_escalated(comments):
      continue

    oncall = team["escalation"]["oncall"]
    body = f"""{ESCALATION_MARK}
AutoAssign Escalation
- team: {team_id}
- reason: {reason}
- oncall: {", ".join(oncall)}
- title: {title}
"""
    add_issue_comment(repo, number, token, body)

    try:
      add_assignees(repo, number, token, oncall)
    except Exception:
      pass

    if is_pr:
      try:
        request_pr_reviewers(repo, number, token, oncall)
      except Exception:
        pass

if __name__ == "__main__":
  main()