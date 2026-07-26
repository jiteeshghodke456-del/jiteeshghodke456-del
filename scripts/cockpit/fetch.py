"""Pull the numbers the cards render.

Every fetch degrades to an empty result rather than raising, so a GitHub or
Codeforces outage produces a card with honest zeroes instead of a failed
workflow and a broken image in the README.
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser

USER_AGENT = "jiteesh-profile-asset-generator"


def http_json(url: str, token: str | None = None, payload: dict | None = None) -> object:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"

    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, headers=headers, data=data)
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def safe_json(url: str, token: str | None = None) -> object | None:
    try:
        return http_json(url, token)
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        json.JSONDecodeError,
    ) as exc:
        print(f"warning: could not fetch {url}: {exc}", file=sys.stderr)
        return None


# --- contribution calendar ------------------------------------------------


class ContributionHTMLParser(HTMLParser):
    """Scrapes the public calendar when no token is available."""

    def __init__(self) -> None:
        super().__init__()
        self.days: list[dict] = []
        self.days_by_id: dict[str, dict] = {}
        self.tooltip_day: dict | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "tool-tip":
            self.tooltip_day = self.days_by_id.get(values.get("for") or "")
            return
        if tag not in {"td", "rect"}:
            return
        date = values.get("data-date")
        level = values.get("data-level")
        if not date or level is None:
            return
        day = {
            "date": date,
            "count": int(values.get("data-count") or 0),
            "level": int(level or 0),
        }
        self.days.append(day)
        if values.get("id"):
            self.days_by_id[str(values["id"])] = day

    def handle_data(self, data: str) -> None:
        if self.tooltip_day is None:
            return
        match = re.search(r"([\d,]+)\s+contributions?", data)
        if match:
            self.tooltip_day["count"] = int(match.group(1).replace(",", ""))

    def handle_endtag(self, tag: str) -> None:
        if tag == "tool-tip":
            self.tooltip_day = None


def fetch_contributions(username: str, token: str | None) -> list[dict]:
    today = dt.datetime.now(dt.UTC).date()
    start = today - dt.timedelta(days=364)

    if token:
        query = """
        query($login: String!, $from: DateTime!, $to: DateTime!) {
          user(login: $login) {
            contributionsCollection(from: $from, to: $to) {
              contributionCalendar {
                weeks { contributionDays { date contributionCount contributionLevel } }
              }
            }
          }
        }
        """
        try:
            data = http_json(
                "https://api.github.com/graphql",
                token,
                {
                    "query": query,
                    "variables": {
                        "login": username,
                        "from": f"{start.isoformat()}T00:00:00Z",
                        "to": f"{today.isoformat()}T23:59:59Z",
                    },
                },
            )
            weeks = data["data"]["user"]["contributionsCollection"][
                "contributionCalendar"
            ]["weeks"]
            return [
                {
                    "date": day["date"],
                    "count": int(day["contributionCount"]),
                    "level": day["contributionLevel"],
                }
                for week in weeks
                for day in week["contributionDays"]
            ]
        except (
            KeyError,
            TypeError,
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
        ) as exc:
            print(f"warning: contribution calendar via API failed: {exc}", file=sys.stderr)

    url = (
        f"https://github.com/users/{username}/contributions"
        f"?from={start.isoformat()}&to={today.isoformat()}"
    )
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"}
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            parser = ContributionHTMLParser()
            parser.feed(response.read().decode("utf-8"))
            return parser.days
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        print(f"warning: could not fetch {url}: {exc}", file=sys.stderr)
        return []


# --- GitHub ---------------------------------------------------------------


def fetch_github(
    username: str, token: str | None
) -> tuple[dict, list[dict], collections.Counter]:
    user = safe_json(f"https://api.github.com/users/{username}", token)
    if not isinstance(user, dict):
        user = {"login": username, "public_repos": 0, "followers": 0, "created_at": ""}

    repos: list[dict] = []
    for page in range(1, 6):
        data = safe_json(
            f"https://api.github.com/users/{username}/repos"
            f"?per_page=100&page={page}&sort=updated",
            token,
        )
        if not isinstance(data, list):
            break
        repos.extend(repo for repo in data if isinstance(repo, dict))
        if len(data) < 100:
            break

    languages: collections.Counter = collections.Counter()
    for repo in repos:
        if repo.get("fork") or not repo.get("name"):
            continue
        lang_data = safe_json(
            f"https://api.github.com/repos/{username}/{repo['name']}/languages", token
        )
        if isinstance(lang_data, dict):
            for language, byte_count in lang_data.items():
                if isinstance(byte_count, int):
                    languages[str(language)] += byte_count
        elif repo.get("language"):
            languages[str(repo["language"])] += 1

    return user, repos, languages


def account_age_days(user: dict) -> int:
    created = str(user.get("created_at") or "")
    if not created:
        return 0
    try:
        born = dt.datetime.fromisoformat(created.replace("Z", "+00:00")).date()
    except ValueError:
        return 0
    return max(0, (dt.datetime.now(dt.UTC).date() - born).days)


def streaks(contributions: list[dict]) -> dict:
    """Current streak, longest streak, active days, busiest single day."""
    ordered = sorted(contributions, key=lambda day: day["date"])
    longest = current = running = 0
    active = 0
    busiest = 0
    for day in ordered:
        count = int(day.get("count") or 0)
        busiest = max(busiest, count)
        if count > 0:
            active += 1
            running += 1
            longest = max(longest, running)
        else:
            running = 0
    # The streak still counts if today has not been committed to yet.
    for day in reversed(ordered):
        if int(day.get("count") or 0) > 0:
            current += 1
        elif current or day is not ordered[-1]:
            break
    return {
        "current": current,
        "longest": longest,
        "active_days": active,
        "busiest_day": busiest,
        "total": sum(int(day.get("count") or 0) for day in ordered),
        "tracked_days": len(ordered),
    }


# --- Codeforces -----------------------------------------------------------


def fetch_codeforces(handle: str) -> list[dict]:
    data = safe_json(
        f"https://codeforces.com/api/user.status?handle={handle}&from=1&count=10000"
    )
    if (
        isinstance(data, dict)
        and data.get("status") == "OK"
        and isinstance(data.get("result"), list)
    ):
        return [row for row in data["result"] if isinstance(row, dict)]
    return []


def codeforces_stats(submissions: list[dict]) -> dict:
    verdicts: collections.Counter = collections.Counter()
    solved: set[str] = set()
    attempted: set[str] = set()
    ratings: list[int] = []
    languages: collections.Counter = collections.Counter()

    for submission in submissions:
        verdict = str(submission.get("verdict") or "OTHER")
        verdicts[verdict] += 1
        problem = submission.get("problem") or {}
        key = f"{problem.get('contestId')}-{problem.get('index')}"
        attempted.add(key)
        languages[str(submission.get("programmingLanguage") or "unknown")] += 1
        if verdict == "OK":
            solved.add(key)
            if isinstance(problem.get("rating"), int):
                ratings.append(problem["rating"])

    total = len(submissions)
    accepted = verdicts.get("OK", 0)
    return {
        "total": total,
        "accepted": accepted,
        "solved": len(solved),
        "attempted": len(attempted),
        "accept_rate": (accepted / total * 100) if total else 0.0,
        "verdicts": verdicts,
        "max_rating": max(ratings) if ratings else 0,
        "languages": languages,
    }
