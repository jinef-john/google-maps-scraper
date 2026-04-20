"""Data models for Google Maps scraper results."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Reviewer:
    name: str = ""
    profile_url: str = ""
    avatar_url: str = ""
    user_id: str = ""
    review_count: str = ""
    is_local_guide: bool = False


@dataclass
class Review:
    reviewer: Reviewer = field(default_factory=Reviewer)
    rating: int = 0
    text: str = ""
    date: str = ""
    photos: list = field(default_factory=list)
    owner_reply: str = ""
    owner_reply_date: str = ""
    language: str = ""
    review_id: str = ""


@dataclass
class OpeningHours:
    periods: list = field(default_factory=list)  # list of day/time dicts
    weekday_text: list = field(default_factory=list)


@dataclass
class Place:
    place_id: str = ""
    name: str = ""
    address: str = ""
    address_components: list = field(default_factory=list)
    lat: float = 0.0
    lng: float = 0.0
    rating: float = 0.0
    review_count: int = 0
    categories: list = field(default_factory=list)
    website: str = ""
    phone: str = ""
    opening_hours: Optional[OpeningHours] = None
    photos: list = field(default_factory=list)
    price_level: str = ""
    description: str = ""
    featured_review_snippets: list = field(default_factory=list)
    reviews: list = field(default_factory=list)
    raw_data: dict = field(default_factory=dict)

    def to_dict(self):
        """Convert to a serializable dictionary."""
        d = {
            "place_id": self.place_id,
            "name": self.name,
            "address": self.address,
            "address_components": self.address_components,
            "coordinates": {"lat": self.lat, "lng": self.lng},
            "rating": self.rating,
            "review_count": self.review_count,
            "categories": self.categories,
            "website": self.website,
            "phone": self.phone,
            "price_level": self.price_level,
            "description": self.description,
            "photos": self.photos,
            "featured_review_snippets": self.featured_review_snippets,
        }
        if self.opening_hours:
            d["opening_hours"] = {
                "periods": self.opening_hours.periods,
                "weekday_text": self.opening_hours.weekday_text,
            }
        if self.reviews:
            d["reviews"] = [
                {
                    "reviewer": {
                        "name": r.reviewer.name,
                        "profile_url": r.reviewer.profile_url,
                        "avatar_url": r.reviewer.avatar_url,
                        "review_count": r.reviewer.review_count,
                        "is_local_guide": r.reviewer.is_local_guide,
                    },
                    "rating": r.rating,
                    "text": r.text,
                    "date": r.date,
                    "photos": r.photos,
                    "owner_reply": r.owner_reply,
                    "owner_reply_date": r.owner_reply_date,
                    "language": r.language,
                }
                for r in self.reviews
            ]
        return d
