"""AI channel analysis: strategy, content ideas, scripts, growth blueprint.

Ported from the companion research web tool's lib/aiAnalysis.ts + lib/thumbnailGenerator.ts.
Providers are configured through the app's settings table (Settings page)
instead of environment variables. Results persist into the shared schema
(channel_content_ideas / channel_scripts / channel_growth_blueprints /
similar_channel_analysis).
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx

from s_q_ali_media_downloader.niche_research.storage import db
from s_q_ali_media_downloader.niche_research.tools.youtube_client import (
    ChannelInfo,
    VideoInfo,
    fetch_channel,
    fetch_videos,
)

logger = logging.getLogger(__name__)

AI_PROVIDERS = ("aihubmix", "groq", "openrouter", "google")
THUMB_STYLES = ("modern", "bold", "minimal", "cinematic", "vibrant")
_PROVIDER_SETTING_KEY = {
    "aihubmix": "aihubmix_api_key",
    "groq": "groq_api_key",
    "openrouter": "openrouter_api_key",
    "google": "google_ai_api_key",
}
_THINK_END = "</think>"
_JSON_RE = re.compile(r"\{[\s\S]*\}")

STYLE_PROMPTS = {
    "modern": "clean modern design, gradient background, bold sans-serif text, minimalist, professional",
    "bold": "bold dramatic design, high contrast, big typography, eye-catching colors, intense",
    "minimal": "minimalist design, simple composition, white space, elegant typography, clean",
    "cinematic": "cinematic look, dramatic lighting, film grain, moody atmosphere, professional photography",
    "vibrant": "vibrant colorful design, neon accents, dynamic composition, energetic, playful",
}


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass
class Strategy:
    contentType: list[str] = field(default_factory=list)
    postingSchedule: str = ""
    thumbnailStyle: str = ""
    titleFormula: str = ""
    tagStrategy: list[str] = field(default_factory=list)
    uniqueSellingPoints: list[str] = field(default_factory=list)


@dataclass
class ContentIdea:
    title: str = ""
    description: str = ""
    contentType: str = "video"
    estimatedViews: str = "medium"
    difficulty: str = "medium"


@dataclass
class Script:
    title: str = ""
    ideaTitle: str = ""
    hook: str = ""
    intro: str = ""
    bodySections: list[str] = field(default_factory=list)
    outro: str = ""
    estimatedDuration: int = 600


@dataclass
class GrowthPhase:
    goals: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)


@dataclass
class ChannelAnalysis:
    strategy: Strategy = field(default_factory=Strategy)
    contentIdeas: list[ContentIdea] = field(default_factory=list)
    scripts: list[Script] = field(default_factory=list)
    growthBlueprint: dict[str, GrowthPhase] = field(
        default_factory=lambda: {
            "30day": GrowthPhase(),
            "60day": GrowthPhase(),
            "90day": GrowthPhase(),
        }
    )


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #
def _provider_def(name: str, api_key: str) -> dict[str, Any]:
    if name == "groq":
        return {
            "name": "groq",
            "base_url": "https://api.groq.com/openai/v1",
            "model": "openai/gpt-oss-20b",
            "max_tokens": 4096,
            "api_key": api_key,
        }
    if name == "aihubmix":
        return {
            "name": "aihubmix",
            "base_url": "https://aihubmix.com/v1",
            "model": "gpt-5.5-free",
            "max_tokens": 4096,
            "api_key": api_key,
        }
    if name == "openrouter":
        return {
            "name": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "model": "openrouter/free",
            "max_tokens": 4096,
            "api_key": api_key,
        }
    if name == "google":
        return {
            "name": "google",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "model": "gemini-2.0-flash",
            "max_tokens": 8192,
            "api_key": api_key,
        }
    raise ValueError(f"Unknown provider: {name}")


def get_providers() -> list[dict[str, Any]]:
    """Configured providers; the primary one (Settings) is tried first."""
    ordered = list(AI_PROVIDERS)
    primary = db.get_setting("ai_primary_provider")
    if primary and primary in ordered:
        ordered.remove(primary)
        ordered.insert(0, primary)
    configured: list[dict[str, Any]] = []
    for name in ordered:
        key = db.get_setting(_PROVIDER_SETTING_KEY[name])
        if key and key.strip():
            configured.append(_provider_def(name, key.strip()))
    return configured


def _strip_thinking(content: str) -> str:
    idx = content.rfind(_THINK_END)
    if idx != -1:
        return content[idx + len(_THINK_END) :].strip()
    return content


JSON_TEMPLATE = """{"strategy":{"contentType":["types"],"postingSchedule":"freq","thumbnailStyle":"style","titleFormula":"formula","tagStrategy":["tags"],"uniqueSellingPoints":["points"]},"contentIdeas":[{"title":"title","description":"desc","contentType":"video","estimatedViews":"high","difficulty":"medium"}],"scripts":[{"title":"title","ideaTitle":"the content idea this script belongs to","hook":"hook","intro":"intro","bodySections":["s1"],"outro":"outro","estimatedDuration":600}],"growthBlueprint":{"30day":{"goals":["g"],"actions":["a"],"metrics":["m"]},"60day":{"goals":["g"],"actions":["a"],"metrics":["m"]},"90day":{"goals":["g"],"actions":["a"],"metrics":["m"]}}}"""


def build_analysis_prompt(channel: ChannelInfo, videos: list[VideoInfo]) -> str:
    video_list = "\n".join(
        f'- "{v.title}" | Views: {v.view_count:,}'
        + (f" | Likes: {v.like_count:,}" if v.like_count else "")
        for v in videos[:5]
    )
    return f"""Analyze this YouTube channel and return ONLY valid JSON (no markdown).

Channel: {channel.title}
Subscribers: {channel.subscriber_count:,}
Views: {channel.view_count:,}
Videos: {channel.video_count}
Description: {(channel.description or "")[:300]}

Top videos:
{video_list}

Return this JSON structure:
{JSON_TEMPLATE}

Generate 5 content ideas, 2 scripts, and detailed growth blueprints."""


def call_provider(provider: dict[str, Any], prompt: str) -> str:
    name = provider["name"]
    if name == "google":
        url = f"{provider['base_url']}/models/{provider['model']}:generateContent"
        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": provider["max_tokens"], "temperature": 0.7},
        }
    else:
        url = f"{provider['base_url']}/chat/completions"
        payload = {
            "model": provider["model"],
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": provider["max_tokens"],
            "temperature": 0.7,
        }
    # Gemini takes the key in the x-goog-api-key header (never the query string,
    # which would leak into logs/proxies); every other provider uses Bearer.
    headers = {"Content-Type": "application/json"}
    if name == "google":
        headers["x-goog-api-key"] = provider["api_key"]
    else:
        headers["Authorization"] = f"Bearer {provider['api_key']}"

    last_error: Exception | None = None
    for attempt in range(3):
        if attempt > 0:
            import time

            time.sleep(attempt * 5)
            logger.warning("Retrying %s in %ss (attempt %d/3)", name, attempt * 5, attempt + 1)
        try:
            with httpx.Client(timeout=120.0) as client:
                res = client.post(url, headers=headers, json=payload)
        except Exception as exc:
            last_error = exc
            continue
        if res.status_code == 429:
            if attempt < 2:
                logger.warning("%s rate limited, retrying...", name)
                continue
            raise RuntimeError(f"{name} rate limited: {res.text[:500]}")
        if 400 <= res.status_code < 500:
            raise RuntimeError(f"{name} API error {res.status_code}: {res.text[:500]}")
        if res.status_code != 200:
            if attempt < 2:
                logger.warning("%s API error %s, retrying...", name, res.status_code)
                continue
            raise RuntimeError(f"{name} API error {res.status_code}: {res.text[:500]}")
        return _parse_provider_response(name, res.json())
    raise last_error or RuntimeError(f"{name} failed after 3 attempts")


def _parse_provider_response(name: str, data: dict[str, Any]) -> str:
    if data.get("error"):
        message = data["error"].get("message") if isinstance(data["error"], dict) else data["error"]
        raise RuntimeError(f"{name} error: {message}")
    if name == "google":
        text = (
            data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        )
        return text
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return _strip_thinking(content)


def parse_analysis_response(text: str) -> ChannelAnalysis:
    match = _JSON_RE.search(text)
    if not match:
        raise RuntimeError("Failed to parse AI response as JSON")
    parsed = json.loads(match.group(0))

    strategy = Strategy(
        contentType=list(
            parsed.get("strategy", {}).get("contentType") or ["educational", "entertainment"]
        ),
        postingSchedule=parsed.get("strategy", {}).get("postingSchedule") or "3-4 videos per week",
        thumbnailStyle=parsed.get("strategy", {}).get("thumbnailStyle")
        or "Bold text, bright colors, face reactions",
        titleFormula=parsed.get("strategy", {}).get("titleFormula") or "Question + Curiosity gap",
        tagStrategy=[str(t) for t in parsed.get("strategy", {}).get("tagStrategy") or []],
        uniqueSellingPoints=[
            str(u) for u in parsed.get("strategy", {}).get("uniqueSellingPoints") or []
        ],
    )

    ideas: list[ContentIdea] = []
    for idea in (parsed.get("contentIdeas") or [])[:10]:
        ideas.append(
            ContentIdea(
                title=str(idea.get("title") or "Untitled"),
                description=str(idea.get("description") or ""),
                contentType=idea.get("contentType")
                if idea.get("contentType") in ("video", "short", "series")
                else "video",
                estimatedViews=idea.get("estimatedViews")
                if idea.get("estimatedViews") in ("high", "medium", "low")
                else "medium",
                difficulty=idea.get("difficulty")
                if idea.get("difficulty") in ("easy", "medium", "hard")
                else "medium",
            )
        )

    scripts: list[Script] = []
    for script in (parsed.get("scripts") or [])[:3]:
        scripts.append(
            Script(
                title=str(script.get("title") or "Untitled Script"),
                ideaTitle=str(script.get("ideaTitle") or ""),
                hook=str(script.get("hook") or ""),
                intro=str(script.get("intro") or ""),
                bodySections=[
                    str(s) for s in script.get("bodySections") or [] if isinstance(s, (str, int))
                ],
                outro=str(script.get("outro") or ""),
                estimatedDuration=int(script.get("estimatedDuration") or 600),
            )
        )

    blueprint: dict[str, GrowthPhase] = {}
    for phase in ("30day", "60day", "90day"):
        raw = parsed.get("growthBlueprint", {}).get(phase, {}) or {}
        blueprint[phase] = GrowthPhase(
            goals=[str(g) for g in raw.get("goals") or []],
            actions=[str(a) for a in raw.get("actions") or []],
            metrics=[str(m) for m in raw.get("metrics") or []],
        )

    return ChannelAnalysis(
        strategy=strategy, contentIdeas=ideas, scripts=scripts, growthBlueprint=blueprint
    )


def analyze_channel(
    channel_id: str,
    *,
    cookiefile: str | None = None,
    progress=None,
    cancel: Callable[[], bool] | None = None,
) -> ChannelAnalysis:
    """Fetch a channel + recent uploads, run AI analysis, persist the result.

    ``cancel`` is checked before every provider call: a cancelled analysis
    must not fall through to the next (paid) provider.
    """
    providers = get_providers()
    if not providers:
        raise RuntimeError(
            "No AI providers configured. Add an API key in the Niche Research > Settings page."
        )

    if progress:
        progress("Fetching channel data...")
    channel = fetch_channel(channel_id, cookiefile=cookiefile)
    upload_ids = [
        u.get("video_id") or u.get("id")
        for u in channel.uploads
        if u.get("video_id") or u.get("id")
    ][:20] or []
    videos = (
        fetch_videos(upload_ids, cookiefile=cookiefile, progress=progress) if upload_ids else []
    )
    videos = [v for v in videos if v and v.view_count is not None]

    if progress:
        progress(f"Analyzing {channel.title} with AI...")
    prompt = build_analysis_prompt(channel, videos)
    last_error: Exception | None = None
    for provider in providers:
        if cancel is not None and cancel():
            logger.info("Analysis cancelled before provider %s", provider["name"])
            raise RuntimeError("Analysis cancelled")
        if progress:
            progress(f"Trying {provider['name']}...")
        logger.info("Trying AI provider: %s", provider["name"])
        try:
            response = call_provider(provider, prompt)
            analysis = parse_analysis_response(response)
            logger.info("Success with provider: %s", provider["name"])
            save_analysis(channel_id, analysis)
            return analysis
        except Exception as exc:
            logger.warning("Provider %s failed: %s", provider["name"], exc)
            last_error = exc
    raise last_error or RuntimeError("All AI providers failed")


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
def save_analysis(channel_id: str, analysis: ChannelAnalysis) -> None:
    now = db.now()
    db.run("DELETE FROM channel_content_ideas WHERE channel_id = ?", (channel_id,))
    db.run("DELETE FROM channel_scripts WHERE channel_id = ?", (channel_id,))
    db.run("DELETE FROM channel_growth_blueprints WHERE channel_id = ?", (channel_id,))

    idea_ids: dict[str, int] = {}
    for idea in analysis.contentIdeas:
        cursor = db.run(
            "INSERT INTO channel_content_ideas (channel_id, idea_title, idea_description, "
            "content_type, estimated_views, difficulty, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                channel_id,
                idea.title,
                idea.description,
                idea.contentType,
                idea.estimatedViews,
                idea.difficulty,
                now,
            ),
        )
        idea_ids[idea.title.strip().lower()] = cursor.lastrowid
    for script in analysis.scripts:
        db.run(
            "INSERT INTO channel_scripts (channel_id, script_title, hook, intro, body_sections, "
            "outro, estimated_duration, idea_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                channel_id,
                script.title,
                script.hook,
                script.intro,
                json.dumps(script.bodySections),
                script.outro,
                script.estimatedDuration,
                idea_ids.get(script.ideaTitle.strip().lower()),
                now,
            ),
        )
    for phase, bp in analysis.growthBlueprint.items():
        db.run(
            "INSERT INTO channel_growth_blueprints (channel_id, phase, goals, actions, metrics, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                channel_id,
                phase,
                json.dumps(bp.goals),
                json.dumps(bp.actions),
                json.dumps(bp.metrics),
                now,
            ),
        )

    db.run(
        "UPDATE trending_channels SET last_analyzed = ? WHERE channel_id = ?",
        (now, channel_id),
    )
    db.run(
        "INSERT OR REPLACE INTO similar_channel_analysis (source_channel_id, target_channel_id, "
        "similarity_score, analysis_json, created_at) VALUES (?, ?, ?, ?, ?)",
        (channel_id, channel_id, 100, json.dumps(asdict(analysis), default=str), now),
    )


def get_analysis(channel_id: str) -> dict[str, Any]:
    strategy_row = db.get(
        "SELECT analysis_json FROM similar_channel_analysis "
        "WHERE source_channel_id = ? ORDER BY created_at DESC LIMIT 1",
        (channel_id,),
    )
    ideas = [
        {
            "title": r["idea_title"],
            "description": r["idea_description"],
            "contentType": r["content_type"],
            "estimatedViews": r["estimated_views"],
            "difficulty": r["difficulty"],
        }
        for r in db.all(
            "SELECT * FROM channel_content_ideas WHERE channel_id = ? ORDER BY id",
            (channel_id,),
        )
    ]
    scripts = [
        {
            "title": r["script_title"],
            "hook": r["hook"],
            "intro": r["intro"],
            "bodySections": json.loads(r["body_sections"] or "[]"),
            "outro": r["outro"],
            "estimatedDuration": r["estimated_duration"],
        }
        for r in db.all(
            "SELECT * FROM channel_scripts WHERE channel_id = ? ORDER BY id",
            (channel_id,),
        )
    ]
    blueprint: dict[str, Any] | None = None
    bp_rows = db.all(
        "SELECT * FROM channel_growth_blueprints WHERE channel_id = ? ORDER BY id",
        (channel_id,),
    )
    if bp_rows:
        blueprint = {}
        for row in bp_rows:
            blueprint[row["phase"]] = {
                "goals": json.loads(row["goals"] or "[]"),
                "actions": json.loads(row["actions"] or "[]"),
                "metrics": json.loads(row["metrics"] or "[]"),
            }
    stored: Any = json.loads(strategy_row["analysis_json"]) if strategy_row else None
    if isinstance(stored, dict) and "strategy" in stored:
        # The whole analysis is stored: strategy, ideas, scripts, blueprint.
        strategy = stored.get("strategy")
    else:
        # Legacy row: the strategy was stored on its own.
        strategy = stored
    return {
        "strategy": strategy,
        "contentIdeas": ideas,
        "scripts": scripts,
        "growthBlueprint": blueprint,
    }


def _scale_similarity(a: float, b: float) -> float:
    """1.0 when two numbers are equal, 0.0 when they differ by their max."""
    a = float(a or 0)
    b = float(b or 0)
    if a <= 0 or b <= 0:
        return 0.0
    lo, hi = sorted((a, b))
    if hi == lo:
        return 1.0
    return max(0.0, 1.0 - (hi - lo) / hi)


def find_similar_channels(channel_id: str, limit: int = 5) -> list[dict[str, Any]]:
    """The discovered channels that most resemble this one.

    "Create Similar Channel" used to compare the channel with itself and
    report a similarity of 100. This searches the locally discovered
    channels instead and scores every candidate on niche, format, subscriber
    scale and viral score.
    """
    rows = db.all(
        "SELECT channel_id, title, thumbnail_url, subscriber_count, view_count, "
        "video_count, viral_score, niche, video_format FROM trending_channels"
    )
    target = next((r for r in rows if r["channel_id"] == channel_id), None)
    if target is None:
        return []

    scored: list[dict[str, Any]] = []
    for row in rows:
        if row["channel_id"] == channel_id:
            continue
        score = 0.0
        if row["niche"] and row["niche"] == target["niche"]:
            score += 40
        if row["video_format"] == target["video_format"]:
            score += 20
        score += 25 * _scale_similarity(row["subscriber_count"], target["subscriber_count"])
        score += 15 * _scale_similarity(row["viral_score"], target["viral_score"])
        scored.append(
            {
                "channel_id": row["channel_id"],
                "title": row["title"] or row["channel_id"],
                "thumbnail_url": row["thumbnail_url"] or "",
                "subscriber_count": row["subscriber_count"] or 0,
                "view_count": row["view_count"] or 0,
                "video_count": row["video_count"] or 0,
                "viral_score": row["viral_score"] or 0,
                "niche": row["niche"] or "",
                "video_format": row["video_format"] or "",
                "similarity": round(min(100.0, score)),
            }
        )

    scored.sort(key=lambda r: r["similarity"], reverse=True)
    return scored[:limit]


def is_analyzed(channel_id: str) -> bool:
    """True when a stored analysis exists for this channel.

    The script count alone was too narrow: a model that returned no scripts
    still produced a strategy and ideas, but the modal kept offering "Ready to
    Analyze" — so the user paid for the same analysis twice.
    """
    if db.get(
        "SELECT 1 FROM similar_channel_analysis WHERE source_channel_id = ? LIMIT 1",
        (channel_id,),
    ):
        return True
    for table in ("channel_content_ideas", "channel_scripts", "channel_growth_blueprints"):
        if db.get(f"SELECT 1 FROM {table} WHERE channel_id = ? LIMIT 1", (channel_id,)):
            return True
    return False


def load_channel_analysis_data(
    channel_id: str, *, cookiefile: str | None = None, progress=None
) -> dict[str, Any]:
    """Everything the analysis modal needs for one channel (GET /api/similar/[id])."""
    from s_q_ali_media_downloader.niche_research.research.trending_engine import (
        get_trending_channel_by_id,
    )

    if progress:
        progress("Fetching channel...")
    channel = fetch_channel(channel_id, cookiefile=cookiefile, uploads_with_stats=True)
    trending = get_trending_channel_by_id(channel_id)

    recent: list[dict[str, Any]] = []
    for u in channel.uploads[:8]:
        video_id = u.get("video_id") or u.get("id")
        if video_id:
            recent.append(
                {
                    "videoId": video_id,
                    "title": u.get("title") or "",
                    "thumbnailUrl": u.get("thumbnail_url") or "",
                    "viewCount": u.get("view_count") or 0,
                    "publishedAt": _upload_date(u.get("upload_date", "")),
                }
            )

    analyzed = is_analyzed(channel_id)
    return {
        "channel": {
            "channelId": channel.channel_id,
            "title": channel.title,
            "description": channel.description,
            "thumbnailUrl": channel.thumbnail_url,
            "subscriberCount": channel.subscriber_count,
            "viewCount": channel.view_count,
            "videoCount": channel.video_count,
            "publishedAt": channel.publish_date,
            "country": channel.country,
            "topicCategories": channel.topic_categories,
            "channelTags": channel.channel_tags,
        },
        "trending": {
            "viralScore": trending.viral_score,
            "growthRate": trending.growth_rate,
            "viewSubRatio": trending.view_sub_ratio,
            "isNewlyCreated": bool(trending.is_newly_created),
            "categoryName": trending.category_name,
        }
        if trending
        else None,
        "analyzed": analyzed,
        "analysis": get_analysis(channel_id) if analyzed else None,
        "recentVideos": recent,
    }


def _upload_date(value: str) -> str:
    if len(value) == 8 and value.isdigit():
        return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"
    return value


# --------------------------------------------------------------------------- #
# Thumbnail generation (lib/thumbnailGenerator.ts)
# --------------------------------------------------------------------------- #
THUMB_IMAGE_PROVIDERS = ("aihubmix", "google", "openrouter")
_IMAGE_MODELS = {
    "aihubmix": "gpt-image-1",
    "google": "gemini-2.5-flash-image",
    "openrouter": "google/gemini-2.5-flash-image",
}


def _image_def(name: str, api_key: str) -> dict[str, Any]:
    if name == "google":
        return {
            "name": "google",
            "mode": "gemini_content",
            "path": (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{_IMAGE_MODELS['google']}:generateContent"
            ),
            "api_key": api_key,
        }
    if name == "openrouter":
        return {
            "name": "openrouter",
            "mode": "openrouter_images",
            "path": "https://openrouter.ai/api/v1/images",
            "model": _IMAGE_MODELS["openrouter"],
            "api_key": api_key,
        }
    return {
        "name": "aihubmix",
        "mode": "openai_images",
        "path": "https://aihubmix.com/v1/images/generations",
        "model": _IMAGE_MODELS["aihubmix"],
        "api_key": api_key,
    }


def _image_provider_defs() -> list[dict[str, Any]]:
    """Image-capable providers in priority order; the Settings primary first."""
    ordered = list(THUMB_IMAGE_PROVIDERS)
    primary = db.get_setting("ai_primary_provider")
    if primary and primary in ordered:
        ordered.remove(primary)
        ordered.insert(0, primary)
    configured: list[dict[str, Any]] = []
    for name in ordered:
        key = db.get_setting(_PROVIDER_SETTING_KEY[name])
        if key and key.strip():
            configured.append(_image_def(name, key.strip()))
    return configured


def _call_image_provider(provider: dict[str, Any], prompt: str) -> dict[str, Any]:
    mode = provider["mode"]
    headers = {"Content-Type": "application/json"}
    if mode == "gemini_content":
        headers["x-goog-api-key"] = provider["api_key"]
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "imageConfig": {"aspectRatio": "16:9"},
            },
        }
    else:
        headers["Authorization"] = f"Bearer {provider['api_key']}"
        if mode == "openai_images":
            payload = {
                "model": provider["model"],
                "prompt": prompt,
                "n": 1,
                "size": "1536x1024",
                "quality": "medium",
                "response_format": "b64_json",
            }
        else:  # openrouter_images
            payload = {
                "model": provider["model"],
                "prompt": prompt,
                "n": 1,
                "aspect_ratio": "16:9",
                "output_format": "png",
                "quality": "high",
            }
    try:
        with httpx.Client(timeout=180.0) as client:
            res = client.post(provider["path"], headers=headers, json=payload)
    except Exception as exc:
        return {"success": False, "error": str(exc)}
    if res.status_code != 200:
        return {"success": False, "error": f"API error {res.status_code}: {res.text[:300]}"}
    return _parse_image_response(provider["name"], mode, res.json())


def _parse_image_response(name: str, mode: str, data: dict[str, Any]) -> dict[str, Any]:
    if data.get("error"):
        message = data["error"].get("message") if isinstance(data["error"], dict) else data["error"]
        return {"success": False, "error": f"{name} error: {message}"}
    if mode == "gemini_content":
        for candidate in data.get("candidates") or []:
            for part in (candidate.get("content") or {}).get("parts") or []:
                inline = part.get("inlineData") or {}
                if inline.get("data"):
                    mime = inline.get("mimeType") or "image/png"
                    return {
                        "success": True,
                        "imageData": f"data:{mime};base64,{inline['data']}",
                    }
        return {"success": False, "error": "No image data in Gemini response"}
    image_data = (data.get("data") or [{}])[0].get("b64_json")
    if not image_data:
        return {"success": False, "error": "No image data in response"}
    return {"success": True, "imageData": f"data:image/png;base64,{image_data}"}


def generate_thumbnail(
    title: str, *, style: str = "bold", niche: str | None = None
) -> dict[str, Any]:
    """Generate a 16:9 thumbnail via an image model; returns base64 PNG data URI.

    Falls back across every configured image provider (aiHubMix → Google AI →
    OpenRouter), trying the Settings primary first.
    """
    style_prompt = STYLE_PROMPTS.get(style, STYLE_PROMPTS["bold"])
    niche_part = f"Niche: {niche}. " if niche else ""
    prompt = (
        f'YouTube thumbnail: "{title}". {style_prompt}. {niche_part}'
        "Aspect ratio 16:9, high resolution, clickable, professional quality."
    )

    providers = _image_provider_defs()
    if not providers:
        return {
            "success": False,
            "error": (
                "No AI image provider configured. Add an API key (aiHubMix, "
                "Google AI, or OpenRouter) in the Niche Research > Settings page."
            ),
        }

    errors: list[str] = []
    for provider in providers:
        logger.info("Trying image provider: %s", provider["name"])
        result = _call_image_provider(provider, prompt)
        if result.get("success"):
            logger.info("Thumbnail generated with provider: %s", provider["name"])
            return result
        logger.warning("Image provider %s failed: %s", provider["name"], result["error"])
        errors.append(f"{provider['name']}: {result['error']}")
    return {
        "success": False,
        "error": "Thumbnail generation failed on all providers. " + " | ".join(errors),
    }
