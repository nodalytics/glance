
export type Rank =
  | 'A'
  | 'K'
  | 'Q'
  | 'J'
  | '10'
  | '9'
  | '8'
  | '7'
  | '6'
  | '5'
  | '4'
  | '3'
  | '2'

export type Suit =
  | 'hearts'
  | 'diamonds'
  | 'clubs'
  | 'spades'

export type Street =
  | 'preflop'
  | 'flop'
  | 'turn'
  | 'river'

export type StateStatus =
  | 'valid'
  | 'partial'
  | 'invalid'

export type OccupancyState =
  | 'occupied'
  | 'empty'
  | 'unknown'

export interface PokerCard {
  slot: string
  rank: Rank | null
  suit: Suit | null
  rank_confidence: number | null
  suit_confidence: number | null
  suit_margin: number | null
  recognized: boolean
  occupied: boolean | null
  occupancy_state?: OccupancyState | null
  ocr_skipped?: boolean | null
}

export interface PokerPlayer {
  seat: string
  name: string | null
  name_confidence: number | null
  stack: number | null
  stack_confidence: number | null
  bounty_display: string | null
  bounty_confidence: number | null
}

export interface TableInformation {
  small_blind: number | null
  big_blind: number | null
  pot: number | null
  prize_pool_display: string | null
  first_place_prize_display: string | null
  average_stack: number | null
  tournament_position: string | null
}

export interface GameInformation {
  variant: 'texas_holdem'
  street: Street | null
  board_count: number
  hero_card_count: number
  occupied_count: number
  recognized_card_count: number
}

export interface CardsInformation {
  community: PokerCard[]
  hero: PokerCard[]
  board_slots: PokerCard[]
  hero_slots: PokerCard[]
}

export interface ValidationIssue {
  code: string
  message: string
  slots: string[]
}

export interface DuplicateCard {
  rank: Rank
  suit: Suit
  slots: string[]
}

export interface CardValidation {
  valid: boolean
  street: Street | null
  board_count: number
  hero_count: number
  occupied_count: number
  empty_count: number
  unknown_count: number
  recognized_cards: number
  duplicate_count: number
  duplicates: DuplicateCard[]
  error_count: number
  warning_count: number
  errors: ValidationIssue[]
  warnings: ValidationIssue[]
}

export interface StateValidation {
  valid: boolean
  error_count: number
  warning_count: number
  errors: ValidationIssue[]
  warnings: ValidationIssue[]
  card_validation: CardValidation
  table_validation: Record<string, unknown>
  parser_validation?: Record<string, unknown> | null
}

export interface RecognitionProfileInfo {
  profile: string
  recognizer: string
  template_count: number
  occupancy_detection_enabled: boolean
  rank_confidence_threshold: number
  suit_confidence_threshold: number
  suit_margin_threshold: number
}

export interface ProcessingTimings {
  initialization_seconds?: number | null
  recognition_seconds?: number | null
  state_building_seconds?: number | null
  total_seconds?: number | null
  image_loading_seconds?: number | null
  directory_total_seconds?: number | null
  screenshot_loading_seconds?: number | null
  table_extraction_seconds?: number | null
  card_cropping_seconds?: number | null
  screenshot_total_seconds?: number | null
}

export interface ScreenshotMetadata {
  filename: string
  width: number
  height: number
  layout: string
}

export interface UploadMetadata {
  filename: string
  extension: string
  format: string
  width: number
  height: number
  file_size_bytes: number
}

export interface ProcessingMetadata {
  recognition_profile: string | null
  processing_time_seconds: number | null
  player_count: number

  dataset_type?: string | null

  profile_info?: RecognitionProfileInfo | null

  timings?: ProcessingTimings | null

  card_slots?:
    | Record<string, unknown>
    | unknown[]
    | null

  recognition_statistics?:
    | Record<string, unknown>
    | null

  screenshot?: ScreenshotMetadata | null

  table_data_origin?: string | null

  ocr_item_count?: number | null

  upload?: UploadMetadata | null

  service_processing_seconds?: number | null
}

export interface PokerState {
  schema_version: string
  timestamp_utc: string

  source:
    | 'offline_simulator'
    | 'offline_screenshot'

  status: StateStatus

  table: TableInformation
  game: GameInformation
  cards: CardsInformation
  players: PokerPlayer[]
  validation: StateValidation
  metadata: ProcessingMetadata
}
