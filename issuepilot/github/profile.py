from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from issuepilot.github.client import GitHubClient

_CALENDAR_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
  }
}
"""

_LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


class GitHubProfile(BaseModel):
    login: str
    name: str | None
    avatar_url: str
    html_url: str
    bio: str | None
    public_repos: int
    followers: int


class ContributionDay(BaseModel):
    date: date
    count: int
    level: int  # 0-4, GitHub's own quartiles


class ContributionCalendar(BaseModel):
    total: int
    weeks: list[list[ContributionDay]]


class PullRequestSummary(BaseModel):
    title: str
    repo: str
    number: int
    html_url: str
    state: Literal["open", "merged", "closed"]
    updated_at: datetime


class ProfileOverview(BaseModel):
    profile: GitHubProfile
    calendar: ContributionCalendar
    pull_requests: list[PullRequestSummary]


def load_profile_overview(client: GitHubClient, login: str, *, pr_limit: int = 30) -> ProfileOverview:
    """Profile, past-year contribution calendar and recent PRs for one user."""
    user = client.get_user(login)
    profile = GitHubProfile(
        login=user["login"],
        name=user.get("name"),
        avatar_url=user["avatar_url"],
        html_url=user["html_url"],
        bio=user.get("bio"),
        public_repos=user.get("public_repos", 0),
        followers=user.get("followers", 0),
    )

    raw_calendar = client.graphql(_CALENDAR_QUERY, {"login": login})["user"]["contributionsCollection"][
        "contributionCalendar"
    ]
    calendar = ContributionCalendar(
        total=raw_calendar["totalContributions"],
        weeks=[
            [
                ContributionDay(date=day["date"], count=day["contributionCount"], level=_LEVELS[day["contributionLevel"]])
                for day in week["contributionDays"]
            ]
            for week in raw_calendar["weeks"]
        ],
    )

    pull_requests = [
        PullRequestSummary(
            title=item["title"],
            repo=item["repository_url"].split("/repos/", 1)[1],
            number=item["number"],
            html_url=item["html_url"],
            state="merged" if (item.get("pull_request") or {}).get("merged_at") else item["state"],
            updated_at=item["updated_at"],
        )
        for item in client.search_issues(f"is:pr author:{login}", per_page=pr_limit)
    ]

    return ProfileOverview(profile=profile, calendar=calendar, pull_requests=pull_requests)
