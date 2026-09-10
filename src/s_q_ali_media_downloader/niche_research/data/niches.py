"""Niche catalog — ported from the companion research web tool's lib/niches.ts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VideoFormat:
    id: str
    name: str
    ratio: str


@dataclass(frozen=True)
class Rpm:
    min: float
    max: float
    avg: float


@dataclass(frozen=True)
class Niche:
    id: str
    name: str
    queries: tuple[str, ...]
    rpm: Rpm
    competition: str  # low | medium | high
    difficulty: str  # easy | medium | hard


LONGFORM = VideoFormat(id="longform", name="Longform", ratio="16:9")
SHORTFORM = VideoFormat(id="shortform", name="Shortform", ratio="9:16")

VIDEO_FORMATS: dict[str, VideoFormat] = {LONGFORM.id: LONGFORM, SHORTFORM.id: SHORTFORM}


def _niche(
    niche_id: str,
    name: str,
    queries: list[str],
    rpm_min: float,
    rpm_max: float,
    competition: str,
    difficulty: str,
) -> Niche:
    return Niche(
        id=niche_id,
        name=name,
        queries=tuple(queries),
        rpm=Rpm(min=rpm_min, max=rpm_max, avg=round((rpm_min + rpm_max) / 2, 2)),
        competition=competition,
        difficulty=difficulty,
    )


LONGFORM_NICHES: dict[str, Niche] = {
    niche.id: niche
    for niche in [
        _niche(
            "finance",
            "Finance",
            [
                "stock market crash",
                "how to build credit",
                "crypto explained",
                "passive income ideas",
            ],
            6.0,
            18.0,
            "medium",
            "hard",
        ),
        _niche(
            "insurance",
            "Insurance",
            ["life insurance explained", "term life insurance", "health insurance tips"],
            9.0,
            20.0,
            "medium",
            "medium",
        ),
        _niche(
            "legal",
            "Legal",
            ["legal rights explained", "how to find a good lawyer", "contract law basics"],
            6.0,
            15.0,
            "medium",
            "medium",
        ),
        _niche(
            "realestate",
            "Real Estate",
            ["first time home buyer", "how to invest in real estate", "real estate for beginners"],
            5.0,
            16.0,
            "medium",
            "medium",
        ),
        _niche(
            "saas",
            "SaaS",
            ["saas explained", "how to build a saas", "saas business models"],
            5.0,
            15.0,
            "high",
            "hard",
        ),
        _niche(
            "tech_ai",
            "Tech & AI",
            [
                "chatgpt explained",
                "ai tools for productivity",
                "machine learning basics",
                "future of ai",
            ],
            4.0,
            12.0,
            "high",
            "hard",
        ),
        _niche(
            "health",
            "Health & Fitness",
            ["how to build muscle", "healthy meal prep", "best workouts at home"],
            3.0,
            10.0,
            "high",
            "easy",
        ),
        _niche(
            "education",
            "Education",
            ["how to study effectively", "learn to code from zero", "study tips for exams"],
            2.5,
            8.0,
            "high",
            "easy",
        ),
        _niche(
            "gaming",
            "Gaming",
            ["best video games 2025", "how to rank up in valorant", "best settings for gaming"],
            2.0,
            6.0,
            "high",
            "easy",
        ),
        _niche(
            "entertainment",
            "Entertainment",
            ["movie breakdowns", "pop culture analysis", "movie theories"],
            1.5,
            6.0,
            "high",
            "easy",
        ),
        _niche(
            "vlogging",
            "Vlogging",
            ["day in the life", "daily vlog", "lifestyle vlog"],
            1.5,
            6.0,
            "high",
            "easy",
        ),
        _niche(
            "business",
            "Business",
            ["how to start a business", "small business tips", "business ideas 2025"],
            6.0,
            17.0,
            "medium",
            "medium",
        ),
        _niche(
            "true_crime",
            "True Crime",
            ["unsolved mysteries", "true crime documentaries", "cold cases"],
            3.0,
            9.0,
            "medium",
            "medium",
        ),
        _niche(
            "beauty_fashion",
            "Beauty & Fashion",
            ["makeup tutorials", "skincare routines", "fashion hauls"],
            2.0,
            8.0,
            "high",
            "easy",
        ),
        _niche(
            "cooking",
            "Cooking",
            ["easy recipes for beginners", "meal prep ideas", "quick weeknight dinners"],
            2.0,
            7.0,
            "high",
            "easy",
        ),
        _niche(
            "diy",
            "DIY & Crafts",
            ["diy home decor", "craft ideas", "beginner woodworking"],
            2.0,
            7.0,
            "medium",
            "easy",
        ),
        _niche(
            "automotive",
            "Automotive",
            ["car reviews 2025", "how cars work", "car maintenance tips"],
            3.0,
            10.0,
            "medium",
            "medium",
        ),
        _niche(
            "parenting",
            "Parenting",
            ["parenting tips", "how to raise kids", "toddler activities"],
            2.0,
            7.0,
            "medium",
            "easy",
        ),
        _niche(
            "documentary",
            "Documentary",
            ["science documentaries", "space documentary", "history documentaries"],
            1.5,
            6.0,
            "medium",
            "medium",
        ),
        _niche(
            "faceless",
            "Faceless YouTube",
            ["faceless youtube automation", "faceless channel ideas", "youtube automation"],
            1.0,
            5.0,
            "low",
            "easy",
        ),
        _niche(
            "crypto",
            "Crypto",
            ["crypto for beginners", "how to buy crypto", "bitcoin explained"],
            5.0,
            16.0,
            "medium",
            "hard",
        ),
        _niche(
            "travel",
            "Travel",
            ["travel vlogs", "best places to visit", "travel tips"],
            1.5,
            7.0,
            "medium",
            "easy",
        ),
        _niche(
            "music",
            "Music",
            ["music production", "how to make beats", "music theory basics"],
            1.0,
            6.0,
            "medium",
            "medium",
        ),
        _niche(
            "pets",
            "Pets & Animals",
            ["dog training tips", "cat care guide", "pet facts"],
            2.0,
            7.0,
            "medium",
            "easy",
        ),
        _niche(
            "news_politics",
            "News & Politics",
            ["world news today", "politics explained", "current events"],
            1.0,
            5.0,
            "high",
            "hard",
        ),
    ]
}


SHORTFORM_NICHES: dict[str, Niche] = {
    niche.id: niche
    for niche in [
        _niche(
            "faceless",
            "Faceless Shorts",
            ["faceless shorts ideas", "faceless youtube shorts", "ai shorts channel"],
            0.1,
            0.5,
            "low",
            "easy",
        ),
        _niche(
            "tech_ai",
            "Tech & AI Shorts",
            ["ai tools to try", "tech facts shorts", "ai news shorts"],
            0.1,
            0.4,
            "high",
            "easy",
        ),
        _niche(
            "micro_learning",
            "Micro Learning",
            ["quick history facts", "science in 60 seconds", "learn something new daily"],
            0.1,
            0.4,
            "medium",
            "easy",
        ),
        _niche(
            "comedy",
            "Comedy Shorts",
            ["funny shorts", "skit ideas", "relatable humor"],
            0.1,
            0.3,
            "high",
            "easy",
        ),
        _niche(
            "fitness",
            "Fitness Shorts",
            ["quick workouts", "fitness tips shorts", "home workout shorts"],
            0.1,
            0.4,
            "high",
            "easy",
        ),
        _niche(
            "gaming",
            "Gaming Shorts",
            ["gaming moments shorts", "gaming tips shorts", "game highlights"],
            0.05,
            0.3,
            "high",
            "easy",
        ),
        _niche(
            "finance",
            "Finance Shorts",
            ["money tips shorts", "saving money shorts", "investing basics"],
            0.2,
            0.6,
            "medium",
            "easy",
        ),
        _niche(
            "motivation",
            "Motivation Shorts",
            ["daily motivation", "motivational shorts", "success quotes"],
            0.1,
            0.3,
            "medium",
            "easy",
        ),
        _niche(
            "animals",
            "Animals Shorts",
            ["cute animals shorts", "animal facts shorts", "pet tricks"],
            0.1,
            0.4,
            "high",
            "easy",
        ),
        _niche(
            "products",
            "Product Reviews Shorts",
            ["gadget reviews shorts", "product unboxing", "tech gadgets"],
            0.1,
            0.4,
            "medium",
            "medium",
        ),
        _niche(
            "cooking",
            "Cooking Shorts",
            ["quick recipes shorts", "easy cooking", "5 minute meals"],
            0.1,
            0.4,
            "high",
            "easy",
        ),
        _niche(
            "beauty_fashion",
            "Beauty Shorts",
            ["makeup hacks shorts", "skincare tips", "outfit ideas"],
            0.1,
            0.4,
            "high",
            "easy",
        ),
        _niche(
            "compilations",
            "Compilations",
            ["best moments compilation", "funny moments", "satisfying videos"],
            0.05,
            0.2,
            "medium",
            "easy",
        ),
        _niche(
            "facts",
            "Facts Shorts",
            ["amazing facts shorts", "unknown facts", "did you know shorts"],
            0.1,
            0.3,
            "medium",
            "easy",
        ),
        _niche(
            "travel",
            "Travel Shorts",
            ["travel shorts", "places to visit shorts", "travel inspiration"],
            0.1,
            0.4,
            "medium",
            "easy",
        ),
        _niche(
            "diy",
            "DIY Shorts",
            ["diy hacks shorts", "life hacks shorts", "craft shorts"],
            0.1,
            0.4,
            "medium",
            "easy",
        ),
        _niche(
            "dance",
            "Dance Shorts",
            ["dance challenges", "dance tutorials", "choreography"],
            0.1,
            0.3,
            "high",
            "easy",
        ),
        _niche(
            "scary",
            "Scary Shorts",
            ["scary stories shorts", "horror stories", "creepy facts"],
            0.1,
            0.3,
            "medium",
            "medium",
        ),
        _niche(
            "asmr",
            "ASMR Shorts",
            ["asmr shorts", "relaxing sounds", "asmr triggers"],
            0.05,
            0.2,
            "medium",
            "easy",
        ),
        _niche(
            "cars",
            "Car Shorts",
            ["car shorts", "supercars shorts", "car modifications"],
            0.1,
            0.4,
            "medium",
            "easy",
        ),
        _niche(
            "sports",
            "Sports Shorts",
            ["sports highlights shorts", "football shorts", "basketball plays"],
            0.1,
            0.3,
            "high",
            "easy",
        ),
        _niche(
            "family",
            "Family Shorts",
            ["family fun shorts", "kids activities", "family moments"],
            0.1,
            0.3,
            "medium",
            "easy",
        ),
        _niche(
            "art",
            "Art Shorts",
            ["drawing shorts", "art process", "digital art"],
            0.1,
            0.4,
            "medium",
            "easy",
        ),
        _niche(
            "education",
            "Education Shorts",
            ["school tips shorts", "study hacks shorts", "quick lessons"],
            0.1,
            0.4,
            "high",
            "easy",
        ),
        _niche(
            "commentary",
            "Commentary Shorts",
            ["internet drama", "pop culture commentary", "react videos"],
            0.1,
            0.3,
            "medium",
            "easy",
        ),
        _niche(
            "news",
            "News Shorts",
            ["daily news shorts", "breaking news shorts", "top stories"],
            0.05,
            0.2,
            "high",
            "medium",
        ),
    ]
}


NICHES: dict[str, dict[str, Niche]] = {
    "longform": LONGFORM_NICHES,
    "shortform": SHORTFORM_NICHES,
}


def get_niches(video_format: str | None = None) -> dict[str, Niche]:
    """Return niches, optionally filtered by format id ('longform' | 'shortform')."""
    if video_format is None:
        return {k: v for values in NICHES.values() for k, v in values.items()}
    return dict(NICHES.get(video_format, {}))


def get_niche(video_format: str, niche_id: str) -> Niche | None:
    return NICHES.get(video_format, {}).get(niche_id)


def format_name(video_format: str) -> str:
    fmt = VIDEO_FORMATS.get(video_format)
    return fmt.name if fmt else video_format
