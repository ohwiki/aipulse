"""Product Hunt fetcher. Uses GraphQL API to get trending AI products."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import requests

try:
    from common import isoformat_z, normalize_whitespace, parse_datetime
except ModuleNotFoundError:
    from tools.common import isoformat_z, normalize_whitespace, parse_datetime

from . import (build_item, build_retry_session, source_matches_keywords,
               within_target_window)

GRAPHQL_URL = "https://api.producthunt.com/v2/api/graphql"

POSTS_QUERY = """
query FetchPosts($first: Int!, $after: String, $postedAfter: DateTime!, $postedBefore: DateTime!) {
  posts(first: $first, after: $after, order: VOTES, postedAfter: $postedAfter, postedBefore: $postedBefore) {
    nodes {
      id name tagline description votesCount createdAt featuredAt website url
      topics { edges { node { id name slug } } }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""


def _get_token() -> str:
    """Get Product Hunt API token (developer token or OAuth client credentials)."""
    developer_token = os.getenv("PRODUCTHUNT_DEVELOPER_TOKEN", "").strip()
    if developer_token:
        return developer_token

    client_id = os.getenv("PRODUCTHUNT_CLIENT_ID", "").strip()
    client_secret = os.getenv("PRODUCTHUNT_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError(
            "Product Hunt credentials missing. Set PRODUCTHUNT_DEVELOPER_TOKEN "
            "or PRODUCTHUNT_CLIENT_ID and PRODUCTHUNT_CLIENT_SECRET."
        )

    response = requests.post(
        "https://api.producthunt.com/v2/oauth/token",
        json={"client_id": client_id, "client_secret": client_secret, "grant_type": "client_credentials"},
        timeout=30,
    )
    response.raise_for_status()
    token = str(response.json().get("access_token", "")).strip()
    if not token:
        raise RuntimeError("Product Hunt OAuth response did not include access_token")
    return token


def _matches_keywords(post: dict, source: dict) -> bool:
    """Check if a Product Hunt post matches the source's keyword filter."""
    return source_matches_keywords(
        source,
        str(post.get("name", "")),
        str(post.get("tagline", "")),
        str(post.get("description", "")),
        str(post.get("topics_text", "")),
    )


def fetch(source: dict, now: datetime, start_at: datetime, end_at: datetime) -> list[dict]:
    """Fetch trending AI products from Product Hunt via GraphQL.

    Paginates through results, filters by keywords and time window.
    Returns items sorted by vote count descending.
    """
    token = _get_token()
    session = build_retry_session()
    max_results = int(source.get("max_results", 20))
    page_size = min(max_results, int(source.get("page_size", 20)))

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "aipulse/1.0",
    }

    items: list[dict] = []
    cursor: str | None = None
    has_next_page = True

    while has_next_page and len(items) < max_results:
        response = session.post(
            GRAPHQL_URL,
            headers=headers,
            json={
                "query": POSTS_QUERY,
                "variables": {
                    "first": page_size,
                    "after": cursor,
                    "postedAfter": isoformat_z(start_at),
                    "postedBefore": isoformat_z(end_at),
                },
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise RuntimeError(f"Product Hunt GraphQL error: {payload['errors']}")

        posts_payload = payload.get("data", {}).get("posts") or {}
        for post in posts_payload.get("nodes", []):
            published_at = parse_datetime(post.get("createdAt"))
            if not published_at or not within_target_window(published_at, start_at, end_at):
                continue

            # Build topics text for keyword matching
            topic_nodes = [
                edge.get("node", {})
                for edge in ((post.get("topics") or {}).get("edges") or [])
                if isinstance(edge, dict)
            ]
            post["topics_text"] = " ".join(
                normalize_whitespace(str(n.get("name", ""))) for n in topic_nodes if n.get("name")
            )
            if not _matches_keywords(post, source):
                continue

            url = str(post.get("url", "")).strip()
            if not url:
                continue

            summary = normalize_whitespace(" ".join(
                part for part in [post.get("tagline", ""), post.get("description", "")] if part
            ))
            items.append(build_item(
                title=normalize_whitespace(str(post.get("name", ""))),
                url=url,
                source_name=source["name"],
                category=source["category"],
                summary=summary,
                published_at=isoformat_z(published_at),
                votes_count=post.get("votesCount"),
                featured=bool(post.get("featuredAt")),
                website=post.get("website"),
                topics=[{"id": n.get("id"), "name": n.get("name"), "slug": n.get("slug")} for n in topic_nodes],
            ))
            if len(items) >= max_results:
                break

        page_info = posts_payload.get("pageInfo") or {}
        has_next_page = bool(page_info.get("hasNextPage")) and len(items) < max_results
        cursor = page_info.get("endCursor")

    items.sort(key=lambda item: (-int(item.get("votes_count") or 0), item.get("published_at", "")))
    return items[:max_results]
