"""Data models for places, reviews, and related entities."""

from dataclasses import dataclass, field


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
    language: str = ""
    photos: list = field(default_factory=list)
    owner_reply: str = ""
    owner_reply_date: str = ""
    review_id: str = ""

    def to_dict(self):
        return {
            "review_id": self.review_id,
            "reviewer_name": self.reviewer.name,
            "reviewer_profile_url": self.reviewer.profile_url,
            "reviewer_avatar_url": self.reviewer.avatar_url,
            "reviewer_user_id": self.reviewer.user_id,
            "reviewer_review_count": self.reviewer.review_count,
            "reviewer_is_local_guide": self.reviewer.is_local_guide,
            "rating": self.rating,
            "text": self.text,
            "date": self.date,
            "language": self.language,
            "photos": self.photos,
            "owner_reply": self.owner_reply,
            "owner_reply_date": self.owner_reply_date,
        }


@dataclass
class OpeningHours:
    periods: list = field(default_factory=list)
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
    opening_hours: OpeningHours | None = None
    photos: list = field(default_factory=list)
    price_level: str = ""
    description: str = ""
    about: list = field(default_factory=list)
    menu: list = field(default_factory=list)
    booking_links: list = field(default_factory=list)

    def to_dict(self):
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
            "about": self.about,
            "menu": self.menu,
            "booking_links": self.booking_links,
            "photos": self.photos,
        }
        if self.opening_hours:
            d["opening_hours"] = {
                "periods": self.opening_hours.periods,
                "weekday_text": self.opening_hours.weekday_text,
            }
        return d
