from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Comment(BaseModel):
    id: int
    author: str
    body: str
    created_at: datetime

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Comment":
        return cls(
            id=data["id"],
            author=data["user"]["login"],
            body=data.get("body") or "",
            created_at=data["created_at"],
        )


class Issue(BaseModel):
    number: int
    title: str
    body: str
    state: str
    labels: list[str]
    author: str
    comment_count: int
    created_at: datetime
    updated_at: datetime
    html_url: str
    comments: list[Comment] = Field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict[str, Any], comments: list[dict[str, Any]] | None = None) -> "Issue":
        return cls(
            number=data["number"],
            title=data["title"],
            body=data.get("body") or "",
            state=data["state"],
            labels=[label["name"] for label in data.get("labels", [])],
            author=data["user"]["login"],
            comment_count=data["comments"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            html_url=data["html_url"],
            comments=[Comment.from_api(c) for c in (comments or [])],
        )
