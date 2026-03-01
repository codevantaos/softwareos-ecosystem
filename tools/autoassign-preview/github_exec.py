import json, time, urllib.request

class GitHubAPIError(RuntimeError):
  pass

def _req(url: str, token: str, method: str, payload: dict | None = None):
  data = None
  headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "User-Agent": "autoassign-exec"
  }
  if payload is not None:
    data = json.dumps(payload).encode("utf-8")
    headers["Content-Type"] = "application/json"
  req = urllib.request.Request(url, data=data, headers=headers, method=method)
  with urllib.request.urlopen(req, timeout=30) as resp:
    body = resp.read().decode("utf-8")
    return json.loads(body) if body else {}

def github_api_json(url: str, token: str, method: str = "GET", payload: dict | None = None, retry: int = 4):
  last = None
  for attempt in range(1, retry + 1):
    try:
      return _req(url, token, method, payload)
    except Exception as e:
      last = e
      time.sleep(1.5 * attempt)
  raise GitHubAPIError(str(last))

def add_issue_comment(repo: str, number: int, token: str, body: str):
  url = f"https://api.github.com/repos/{repo}/issues/{number}/comments"
  return github_api_json(url, token, "POST", {"body": body})

def add_assignees(repo: str, number: int, token: str, assignees: list[str]):
  url = f"https://api.github.com/repos/{repo}/issues/{number}/assignees"
  return github_api_json(url, token, "POST", {"assignees": assignees})

def request_pr_reviewers(repo: str, number: int, token: str, reviewers: list[str]):
  url = f"https://api.github.com/repos/{repo}/pulls/{number}/requested_reviewers"
  return github_api_json(url, token, "POST", {"reviewers": reviewers})

def add_labels(repo: str, number: int, token: str, labels: list[str]):
  url = f"https://api.github.com/repos/{repo}/issues/{number}/labels"
  return github_api_json(url, token, "POST", {"labels": labels})

def remove_label(repo: str, number: int, token: str, label: str):
  url = f"https://api.github.com/repos/{repo}/issues/{number}/labels/{label}"
  return github_api_json(url, token, "DELETE")

def list_issue_comments(repo: str, number: int, token: str, per_page: int = 50, pages: int = 3):
  out = []
  for page in range(1, pages + 1):
    url = f"https://api.github.com/repos/{repo}/issues/{number}/comments?per_page={per_page}&page={page}"
    items = github_api_json(url, token, "GET")
    if not items:
      break
    out.extend(items)
  return out