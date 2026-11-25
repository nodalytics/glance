
from datetime import datetime
from typing import Any, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------
# SHARED TYPES
# --------------------------------------------------

Rank = Literal[
    "A", "K", "Q", "J", "10",
    "9", "8", "7", "6", "5", "4", "3", "2"
]

Suit = Literal[
    "hearts",
    "diamonds",
    "clubs",
    "spades"
]

Street = Literal[
    "preflop",
    "flop",
    "turn",
    "river"
]

StateStatus = Literal[
    "valid",
    "partial",
    "invalid"
]

OccupancyState = Literal[
    "occupied",
    "empty",
    "unknown"
]

Confidence = Annotated[
    float,
    Field(ge=0.0, le=1.0)
]

NonNegativeInteger = Annotated[
    int,
    Field(ge=0, strict=True)
]

NonNegativeFloat = Annotated[
    float,
    Field(ge=0.0)
]


# --------------------------------------------------
# BASE MODEL
# --------------------------------------------------

class APIBaseModel(BaseModel):

    model_config = ConfigDict(
        extra="allow",
        allow_inf_nan=False
    )


# --------------------------------------------------
# CARD MODEL
# --------------------------------------------------

class CardModel(APIBaseModel):

    slot: str

    rank: Rank | None = None

    suit: Suit | None = None

    rank_confidence: Confidence | None = None

    suit_confidence: Confidence | None = None

    suit_margin: Confidence | None = None

    recognized: bool = False

    occupied: bool | None = None

    occupancy_state: OccupancyState | None = None

    ocr_skipped: bool | None = None


# --------------------------------------------------
# PLAYER MODEL
# --------------------------------------------------

class PlayerModel(APIBaseModel):

    seat: str

    name: str | None = None

    name_confidence: Confidence | None = None

    stack: NonNegativeInteger | None = None

    stack_confidence: Confidence | None = None

    bounty_display: str | None = None

    bounty_confidence: Confidence | None = None


# --------------------------------------------------
# TABLE MODEL
# --------------------------------------------------

class TableModel(APIBaseModel):

    small_blind: NonNegativeInteger | None = None

    big_blind: NonNegativeInteger | None = None

    pot: NonNegativeInteger | None = None

    prize_pool_display: str | None = None

    first_place_prize_display: str | None = None

    average_stack: NonNegativeInteger | None = None

    tournament_position: str | None = None


# --------------------------------------------------
# GAME MODEL
# --------------------------------------------------

class GameModel(APIBaseModel):

    variant: Literal["texas_holdem"]

    street: Street | None = None

    board_count: NonNegativeInteger

    hero_card_count: NonNegativeInteger

    occupied_count: NonNegativeInteger

    recognized_card_count: NonNegativeInteger


# --------------------------------------------------
# CARD COLLECTION MODEL
# --------------------------------------------------

class CardsModel(APIBaseModel):

    community: list[CardModel]

    hero: list[CardModel]

    board_slots: list[CardModel]

    hero_slots: list[CardModel]


# --------------------------------------------------
# VALIDATION ISSUE MODEL
# --------------------------------------------------

class ValidationIssueModel(APIBaseModel):

    code: str

    message: str

    slots: list[str] = Field(
        default_factory=list
    )


# --------------------------------------------------
# DUPLICATE CARD MODEL
# --------------------------------------------------

class DuplicateCardModel(APIBaseModel):

    rank: Rank

    suit: Suit

    slots: list[str]


# --------------------------------------------------
# CARD VALIDATION MODEL
# --------------------------------------------------

class CardValidationModel(APIBaseModel):

    valid: bool

    street: Street | None = None

    board_count: NonNegativeInteger

    hero_count: NonNegativeInteger

    occupied_count: NonNegativeInteger

    empty_count: NonNegativeInteger

    unknown_count: NonNegativeInteger

    recognized_cards: NonNegativeInteger

    duplicate_count: NonNegativeInteger

    duplicates: list[DuplicateCardModel] = Field(
        default_factory=list
    )

    error_count: NonNegativeInteger

    warning_count: NonNegativeInteger

    errors: list[ValidationIssueModel] = Field(
        default_factory=list
    )

    warnings: list[ValidationIssueModel] = Field(
        default_factory=list
    )


# --------------------------------------------------
# OVERALL VALIDATION MODEL
# --------------------------------------------------

class ValidationModel(APIBaseModel):

    valid: bool

    error_count: NonNegativeInteger

    warning_count: NonNegativeInteger

    errors: list[ValidationIssueModel] = Field(
        default_factory=list
    )

    warnings: list[ValidationIssueModel] = Field(
        default_factory=list
    )

    card_validation: CardValidationModel

    table_validation: dict[str, Any]

    parser_validation: dict[str, Any] | None = None


# --------------------------------------------------
# RECOGNITION PROFILE MODEL
# --------------------------------------------------

class RecognitionProfileModel(APIBaseModel):

    profile: str

    recognizer: str

    template_count: NonNegativeInteger

    occupancy_detection_enabled: bool

    rank_confidence_threshold: Confidence

    suit_confidence_threshold: Confidence

    suit_margin_threshold: Confidence


# --------------------------------------------------
# PROCESSING TIMINGS MODEL
# --------------------------------------------------

class ProcessingTimingsModel(APIBaseModel):

    initialization_seconds: NonNegativeFloat | None = None

    recognition_seconds: NonNegativeFloat | None = None

    state_building_seconds: NonNegativeFloat | None = None

    total_seconds: NonNegativeFloat | None = None

    image_loading_seconds: NonNegativeFloat | None = None

    directory_total_seconds: NonNegativeFloat | None = None

    screenshot_loading_seconds: NonNegativeFloat | None = None

    table_extraction_seconds: NonNegativeFloat | None = None

    card_cropping_seconds: NonNegativeFloat | None = None

    screenshot_total_seconds: NonNegativeFloat | None = None


# --------------------------------------------------
# SCREENSHOT METADATA MODEL
# --------------------------------------------------

class ScreenshotMetadataModel(APIBaseModel):

    filename: str

    width: NonNegativeInteger

    height: NonNegativeInteger

    layout: str


# --------------------------------------------------
# METADATA MODEL
# --------------------------------------------------

class MetadataModel(APIBaseModel):

    recognition_profile: str | None = None

    processing_time_seconds: NonNegativeFloat | None = None

    player_count: NonNegativeInteger

    dataset_type: str | None = None

    profile_info: RecognitionProfileModel | None = None

    timings: ProcessingTimingsModel | None = None

    card_slots: dict[str, Any] | list[Any] | None = None

    recognition_statistics: dict[str, Any] | None = None

    screenshot: ScreenshotMetadataModel | None = None

    table_data_origin: str | None = None

    ocr_item_count: NonNegativeInteger | None = None


# --------------------------------------------------
# COMPLETE POKER STATE MODEL
# --------------------------------------------------

class PokerStateModel(APIBaseModel):

    schema_version: str

    timestamp_utc: datetime

    source: Literal[
        "offline_simulator",
        "offline_screenshot"
    ]

    status: StateStatus

    table: TableModel

    game: GameModel

    cards: CardsModel

    players: list[PlayerModel]

    validation: ValidationModel

    metadata: MetadataModel


# --------------------------------------------------
# HEALTH RESPONSE MODEL
# --------------------------------------------------

class HealthResponseModel(APIBaseModel):

    status: Literal[
        "ok",
        "degraded"
    ] = "ok"

    service: str = "poker-apis"

    version: str = "1.0.0"

    mode: Literal["offline"] = "offline"


# --------------------------------------------------
# APPLICATION INFORMATION MODEL
# --------------------------------------------------

class ApplicationInfoModel(APIBaseModel):

    name: str

    version: str

    description: str

    mode: Literal["offline"] = "offline"

    schema_version: str = "1.0.0"

    supported_image_formats: list[str]

    max_upload_size_bytes: NonNegativeInteger


# --------------------------------------------------
# ERROR RESPONSE MODEL
# --------------------------------------------------

class ErrorDetailModel(APIBaseModel):

    code: str

    message: str

    details: dict[str, Any] | None = None


class ErrorResponseModel(APIBaseModel):

    success: Literal[False] = False

    error: ErrorDetailModel
