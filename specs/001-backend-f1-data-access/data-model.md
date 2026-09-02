# Data Model: Backend Foundation & F1 Data Access

This feature has no persistent database model. These entities define the API
request, deterministic response, and error boundary.

## Session Request

Identifies one Formula 1 session through path parameters.

| Field | Type | Rules |
|---|---|---|
| `year` | integer | At least 1950; only `2025` is supported by this feature |
| `event` | string | Lowercase URL slug; only `italian-grand-prix` is supported |
| `session` | string | Lowercase URL slug; only `race` is supported |

The shape is generic even though the supported set contains only the control
tuple. A well-formed tuple outside that set is unsupported, not malformed.

## Session Summary

Top-level successful response for a loaded session.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `year` | integer | Yes | Championship season from FastF1 event data |
| `event` | Event Summary | Yes | Event identity and location |
| `session` | Session Identity | Yes | Session name/type |
| `circuit` | Circuit Summary | Yes | Circuit identity from FastF1 data |
| `timing` | Session Timing | Yes | Scheduled start and race distance metadata |
| `participants` | Participant array | Yes | Drivers and teams present in source results |
| `data_availability` | Data Availability | Yes | Status of relevant FastF1 data categories |
| `source` | Source Provenance | Yes | Approved provider identity |

The response contains no retrieval timestamp, random identifier, or cache-hit
state. The same source snapshot therefore produces the same response.

## Event Summary

| Field | Type | Required | Validation |
|---|---|---|---|
| `name` | string | Yes | Non-empty source event name |
| `round_number` | integer or null | Yes | Positive when supplied by the source |
| `country` | string or null | Yes | Source value or null |
| `location` | string or null | Yes | Source value or null |

## Session Identity

| Field | Type | Required | Validation |
|---|---|---|---|
| `name` | string | Yes | Non-empty source session name |
| `type` | string | Yes | Canonical API slug, `race` for the control session |

## Circuit Summary

| Field | Type | Required | Validation |
|---|---|---|---|
| `name` | string | Yes | Non-empty FastF1 circuit or event-location value |

Prefer FastF1's circuit short name and use its event location only when the
circuit field is absent. If neither source field is usable, the required
session summary cannot be produced. No value is inferred from unrelated
knowledge.

## Session Timing

| Field | Type | Required | Validation |
|---|---|---|---|
| `scheduled_start_utc` | UTC date-time | Yes | ISO 8601 serialization of FastF1 session date |
| `total_laps` | integer or null | Yes | Positive source value, otherwise null |

## Participant

| Field | Type | Required | Validation |
|---|---|---|---|
| `position` | integer or null | Yes | Positive classified position or null |
| `driver_number` | string | Yes | Non-empty source driver number |
| `abbreviation` | string or null | Yes | Source abbreviation or null |
| `full_name` | string or null | Yes | Source full name or null |
| `team_name` | string or null | Yes | Source team name or null |

Participants retain deterministic source classification order. Rows without a
classified position follow classified rows in stable source order.

## Data Availability

Each field uses one of three statuses:

- `available`: requested and present in the loaded session
- `unavailable`: requested but absent or empty
- `not_requested`: deliberately excluded from this feature's load profile

| Field | Control-session load policy |
|---|---|
| `session_info` | Requested |
| `results` | Requested and required for a successful participant response |
| `laps` | Requested |
| `telemetry` | Not requested |
| `weather` | Not requested |
| `race_control_messages` | Not requested |

## Source Provenance

| Field | Type | Required | Value |
|---|---|---|---|
| `provider` | string literal | Yes | `FastF1` |

## Error Response

Custom feature errors use an `error` object with:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `code` | string | Yes | Stable machine-readable category |
| `message` | string | Yes | Safe human-readable explanation |

Feature codes:

- `session_not_supported` with HTTP `404`
- `data_source_unavailable` with HTTP `503`

Malformed path values use FastAPI's structured HTTP `422` validation response.
Unexpected defects remain HTTP `500` errors and must be logged rather than
misrepresented as source outages.

## Request Lifecycle

```text
received
  -> path validation failed (422)
  -> supported-scope check failed (404)
  -> FastF1 load failed in an expected source-related way (503)
  -> required source data absent (503)
  -> mapped and response-validated (200)
```
