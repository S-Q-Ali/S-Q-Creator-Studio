"""Data schemas for YouTube Discovery and Social Presence Agent."""

from enum import Enum

from pydantic import BaseModel, Field


class SocialPlatform(str, Enum):
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"


class SocialStatus(str, Enum):
    VERIFIED = "verified"
    NOT_FOUND = "not_found"
    UNVERIFIED_HANDLE = "unverified_handle"
    INCONCLUSIVE = "inconclusive"


class SocialPresence(BaseModel):
    platform: SocialPlatform
    status: SocialStatus = SocialStatus.NOT_FOUND
    verified_url: str | None = None
    handle: str | None = None
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    # Where the candidate URL came from: "bio_link" (explicit link in the
    # creator's own bio — high precision), "handle_guess" (fabricated from the
    # creator handle — low precision), or "probe" (directly probed URL).
    source: str = "probe"


class ChannelMetadata(BaseModel):
    channel_id: str
    title: str
    handle: str | None = None
    subscribers: int = 0
    subscribers_formatted: str = "0"
    youtube_url: str
    avatar_url: str | None = None
    description: str = ""
    banner_links: list[str] = Field(default_factory=list)
    facebook: SocialPresence = Field(
        default_factory=lambda: SocialPresence(platform=SocialPlatform.FACEBOOK)
    )
    instagram: SocialPresence = Field(
        default_factory=lambda: SocialPresence(platform=SocialPlatform.INSTAGRAM)
    )
    tiktok: SocialPresence = Field(
        default_factory=lambda: SocialPresence(platform=SocialPlatform.TIKTOK)
    )
    latest_video_url: str | None = None
    has_no_socials: bool = False
    opportunity_flag: str = "PROSPECT"


class TikTokProfileMetadata(BaseModel):
    """A TikTok creator profile discovered by the TikTok-first search mode."""

    profile_id: str
    handle: str  # without '@' prefix
    nickname: str = "TikTok Creator"
    followers: int = 0
    followers_formatted: str = "N/A"
    video_count: int = 0
    bio: str = ""
    profile_url: str = ""
    avatar_url: str | None = None
    youtube: SocialPresence = Field(
        default_factory=lambda: SocialPresence(platform=SocialPlatform.YOUTUBE)
    )
    facebook: SocialPresence = Field(
        default_factory=lambda: SocialPresence(platform=SocialPlatform.FACEBOOK)
    )
    instagram: SocialPresence = Field(
        default_factory=lambda: SocialPresence(platform=SocialPlatform.INSTAGRAM)
    )
    has_youtube: bool = False
    opportunity_flag: str = "PROSPECT"


class TikTokSearchResult(BaseModel):
    query: str
    total_searched: int = 0
    profiles_matching_filter: int = 0
    no_youtube_count: int = 0
    execution_time_seconds: float = 0.0
    timestamp: str = ""
    profiles: list[TikTokProfileMetadata] = Field(default_factory=list)


class AgentSearchResult(BaseModel):
    query: str
    total_searched: int = 0
    channels_matching_filter: int = 0
    execution_time_seconds: float = 0.0
    timestamp: str = ""
    channels: list[ChannelMetadata] = Field(default_factory=list)
    # Platforms the user actually enabled for probing, e.g. ["facebook", "instagram"].
    # "has_no_socials" must only be computed over these.
    checked_platforms: list[str] = Field(default_factory=list)
