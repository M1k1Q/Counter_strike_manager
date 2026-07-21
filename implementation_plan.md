# Implementation Plan: Realistic Transfer Negotiation & Team Willingness Modelling

This document outlines the transfer negotiation model for CS2 Manager. Top-tier teams (e.g., Vitality, Spirit, Mouz, G2, FaZe) will treat their star players as untouchable, requiring prohibitive buyouts or refusing standard transfer offers.

## Key Principles & Design Decisions

> [!IMPORTANT]
> **Untouchable / Franchise Star Status**: Top 5 ranked teams will treat high-performing players (Rating ≥ 84 or Overall HLTV ≥ 1.15) as **Untouchable**. Standard market offers (1.0x–1.3x) will be rejected automatically with clear feedback ("Team X refuses to enter negotiations for their franchise star").

1. **Source Team Rank Weighting**:
   - **Top 5 Teams (Rank 1–5)**: Extremely low willingness to sell star players. Prohibitive buyout multipliers required (2.5x – 4.0x+).
   - **Mid-tier Teams (Rank 6–20)**: Open to selling if offered a premium (1.3x – 2.0x market value).
   - **Low-tier / Unassigned Teams**: Willing to accept fair-market or slight premium offers.

2. **Prestige Gap Penalty**:
   - Players from top-ranked teams will resist transferring to significantly lower-ranked or custom teams (prestige penalty applied to success chance).

3. **Offer-Ratio Driven Calculations**:
   - Success chance will scale dynamically with `Offer Amount / Player Valuation Price`, rather than player rating alone.

---

## Detailed Model Rules

### Minimum Buyout Thresholds
- **Top 3 Teams (Rank 1-3)**: Star players require a minimum offer of **2.5x base price** to open negotiations. Offers below this threshold are rejected immediately as "Not For Sale".
- **Top 10 Teams (Rank 4-10)**: Require at least **1.5x base price**.
- **Other Teams (Rank 11+)**: Standard negotiation starting at **1.1x base price**.

---

## Proposed Changes

### Backend Core (`app/`)

#### [models.py](file:///c:/Users/hp/Desktop/Proj/app/models.py)
- Refactor `Negotiation.calculate_success()` to model willingness to sell based on:
  - **Source Team Standing**: `source_rank_factor` (Rank 1 = high resistance, Rank 30 = low resistance).
  - **Player Importance**: `star_power` derived from player `Rating` or `overall_rating`.
  - **Prestige Gap**: Difference between `source_team.ranking` and `target_team.ranking`.
  - **Offer Ratio**: `offer_amount / player.price`.
- Introduce helper methods/properties on `Negotiation`:
  - `is_untouchable`: Returns `True` if player is on a Top 5 team with Rating ≥ 84 and offer is below top-team threshold.
  - `min_required_offer`: Calculates minimum offer ratio needed for source team to entertain negotiations.

#### [negotiations.py](file:///c:/Users/hp/Desktop/Proj/app/routes/negotiations.py)
- Refactor `start_negotiation` and `make_offer`:
  - Enforce initial checks for "Untouchable" status (return clear status `"rejected"` with descriptive reason).
  - Update `some_acceptance_check()` to require higher offer ratios depending on source team rank.
  - Record detailed status messages (e.g. `"Vitality refuses to sell ZywOo to a lower-ranked team unless offered $1,500,000+"`).

#### [schemas.py](file:///c:/Users/hp/Desktop/Proj/app/schemas.py)
- Add `status_message` field to `NegotiationResponse` so the frontend can display exact explanations to the manager.

---

### Frontend UI (`frontend/src/`)

#### [App.jsx](file:///c:/Users/hp/Desktop/Proj/frontend/src/App.jsx) & [PlayerModal.jsx](file:///c:/Users/hp/Desktop/Proj/frontend/src/components/PlayerModal.jsx)
- Display team unwillingness / untouchable indicators in `PlayerModal`.
- Show contextual feedback messages in the modal when an offer is rejected by a top team.

---

## Verification Plan

### Automated Tests
- Run unit tests verifying `calculate_success()`:
  - Top 3 team star player with 1.0x offer returns ~0–5% success chance or rejection.
  - Low-ranked team player with 1.5x offer returns high success chance (>70%).
- `python -m unittest tests/test_negotiations.py`

### Manual Verification
- Test initiating a transfer offer for ZywOo (Vitality) or donk (Spirit) in the web UI.
- Verify that standard offers are rejected with a clear message explaining team unwillingness.
- Test offering a 3x buyout to verify willingness scales appropriately.
