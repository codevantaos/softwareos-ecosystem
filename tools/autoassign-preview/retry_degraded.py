import os, re, time
from github_exec import github_api_json, add_issue_comment, add_labels, remove_label, list_issue_comments

LABEL_RETRY = "autoassign-retry"
LABEL_DEGRADED = "autoassign-degraded"
DONE_MARK = "[AUTOASSIGN_DONE]"
DEGRADED_MARK = "[AUTOASSIGN_DEGRADED]"

MAX_RETRIES = 12
RETRY_BACKOFF_MIN = [10, 10, 20, 20, 40, 40, 60, 60, 120, 120, 180, 180]

def list_open_items(repo: str, token: str, per_page: int = 50, pages: int = 4):
  out = []
  for page in range(1, pages + 1):
    url = f"https://api.github.com/repos/{repo}/issues?state=open&per_page={per_page}&page={page}"
    items = github_api_json(url, token, "GET")
    if not items:
      break
    out.extend(items)
  return out

def has_done(comments: list[dict]) -> bool:
  return any(DONE_MARK in (c.get("body") or "") for c in comments)

def parse_retry_state(comments: list[dict]) -> tuple[int, int]:
  retry_count = 0
  last_epoch = 0
  for c in comments:
    body = c.get("body") or ""
    if DEGRADED_MARK not in body:
      continue
    m1 = re.search(r"retry_count=(\d+)", body)
    m2 = re.search(r"last_retry_epoch=(\d+)", body)
    if m1:
      retry_count = max(retry_count, int(m1.group(1)))
    if m2:
      last_epoch = max(last_epoch, int(m2.group(1)))
  return retry_count, last_epoch

def main():
  token = os.environ["GITHUB_TOKEN"]
  repo = os.environ["GITHUB_REPOSITORY"]

  items = list_open_items(repo, token)
  now = int(time.time())

  for it in items:
    if "pull_request" not in it:
      continue

    num = int(it["number"])
    labels = [x.get("name","") for x in (it.get("labels") or []) if isinstance(x, dict)]

    if LABEL_DEGRADED not in labels:
      continue

    comments = list_issue_comments(repo, num, token)
    if has_done(comments):
      for lb in [LABEL_RETRY, LABEL_DEGRADED]:
        try: remove_label(repo, num, token, lb)
        except Exception: pass
      continue

    retry_count, last_epoch = parse_retry_state(comments)

    if retry_count >= MAX_RETRIES:
      try:
        add_issue_comment(
          repo, num, token,
          f"{DEGRADED_MARK}\nretry_count={retry_count}\nlast_retry_epoch={last_epoch}\n"
          f"AutoAssign retry circuit-open (max retries reached={MAX_RETRIES}).\n"
          f"- action: stop scheduling retries\n"
        )
      except Exception:
        pass
      try:
        remove_label(repo, num, token, LABEL_RETRY)
      except Exception:
        pass
      continue

    backoff_min = RETRY_BACKOFF_MIN[min(retry_count, len(RETRY_BACKOFF_MIN)-1)]
    if last_epoch and (now - last_epoch) < backoff_min * 60:
      continue

    try:
      add_labels(repo, num, token, [LABEL_RETRY])
    except Exception:
      pass

    next_count = retry_count + 1
    try:
      add_issue_comment(
        repo, num, token,
        f"{DEGRADED_MARK}\nretry_count={next_count}\nlast_retry_epoch={now}\n"
        f"AutoAssign retry scheduled.\n"
        f"- backoff_min={backoff_min}\n"
      )
    except Exception:
      pass

if __name__ == "__main__":
  main()