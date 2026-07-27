# Implementation Plan: Team Roster Needs and Player Recruitment

## Goal

Add a team-needs module so every team can identify the roles missing from its active roster and browse players who could fill those gaps. The first version should model roster structure and recommendations only. Budget-aware recruitment and intelligent replacement selection are planned follow-ups.

## Product Rules

### Required roster structure

Each team has a roster made up of players with classified roles:

- Exactly one `entry` player is required.
- Exactly one `awper` player is required. Normalize the user-facing spelling to `AWPer`; keep the stored role key consistent with the classifier (`awper`).
- Zero or more `support` players are allowed.
- Zero or more `lurker` players are allowed.
- The team IGL is selected from its current roster by the highest `igl_score`.
- IGL selection is independent of the player’s primary role. An entry, AWPer, support, or lurker can be the IGL.
- A team with no players eligible for IGL selection has no assigned IGL and should report that as a roster issue rather than silently selecting one.

The first implementation should not force a five-player maximum or require a minimum number of supports/lurkers. Those rules can be added later without changing the required-role model.

### Team needs

The team-needs result should expose:

- The team and current roster size.
- The current assigned IGL and its `igl_score`, when one exists.
- Missing compulsory roles: `entry`, `awper`, or both.
- Optional role counts for `support` and `lurker`.
- A stable status such as `complete`, `missing_roles`, or `empty`.
- Candidate players for each missing role, excluding players already on the target team.

Candidates should be ranked by role fit first (`role` and `confidence`), then by overall performance. IGL score should be displayed as supporting information for candidates, not used to replace the compulsory role match.

## Current Code Anchors

- [app/models.py](app/models.py): `Team.players` is the existing roster relationship; `Player.role`, `Player.igl_score`, and `Player.is_igl` already exist; `Player.price` is the current market-value calculation.
- [app/classifier.py](app/classifier.py): assigns the base role and calculates `igl_score`; it currently marks the best IGL per source team during seeding.
- [app/routes/teams.py](app/routes/teams.py): owns team listing, creation, and direct player assignment/removal.
- [app/routes/negotiations.py](app/routes/negotiations.py): moves a player to the target team after an accepted negotiation and already checks the manager budget.
- [app/schemas.py](app/schemas.py): owns `TeamResponse`, `PlayerResponse`, and API response contracts.
- [frontend/src/App.jsx](frontend/src/App.jsx): loads teams and players and owns the current team-selection and negotiation flows.
- [frontend/src/components/TeamRoster.jsx](frontend/src/components/TeamRoster.jsx): renders the existing roster view and is the natural place to show role coverage.

## Phase 1: Backend Roster Analysis

### 1. Add a roster-analysis service

Create a small service/helper module under `app/` that accepts a `Team` and computes a plain result object. Keep this logic outside the route so it can be tested without HTTP or database setup.

Suggested responsibilities:

- Normalize role values such as `entry igl` to the base role `entry`.
- Count each role in the current roster.
- Find missing compulsory roles using the rule `count == 0`.
- Select the roster IGL with `max(igl_score)` using a deterministic tie-breaker, such as overall rating and then player id.
- Return serializable data without mutating `Player.is_igl`.

Do not rely on the seeded `is_igl` flag for live roster analysis. That flag represents the classifier’s original team assignment and can become stale after transfers.

### 2. Add API schemas

Extend [app/schemas.py](app/schemas.py) with explicit response models for:

- Role counts.
- The assigned IGL summary.
- Missing roles.
- A candidate player summary.
- A team-needs response.

Keep candidate data compatible with `PlayerResponse`, adding only fields needed by this view such as `role_fit` or a normalized base role if those are not already present.

### 3. Add team-needs endpoints

Extend [app/routes/teams.py](app/routes/teams.py) with:

- `GET /teams/{team_id}/needs`: return roster status, role counts, missing compulsory roles, and the current IGL.
- `GET /teams/{team_id}/needs/candidates`: return candidates grouped or filtered by missing role.

Candidate queries should:

- Exclude players already on the team.
- Prefer players whose classified role matches a missing role.
- Include free agents and players belonging to other teams.
- Return price as read-only display data for now, without making affordability a selection constraint.

Use a clear `404` for an unknown team and return an empty candidate list when the team has no missing roles.

## Phase 2: Recruitment UI

### Team needs module

Add a dedicated frontend component, for example `TeamNeeds`, and expose it from the team-management area in [frontend/src/App.jsx](frontend/src/App.jsx).

The module should show:

- A compact roster health summary.
- Required role slots with clear filled/missing states.
- The selected IGL and IGL score.
- Candidate lists under each missing role.
- Player role, confidence, rating, current team, and market price.
- A link/action that opens the existing player or negotiation flow for a candidate.

Reuse the existing role badge and modal patterns. Keep the module useful when the roster is empty, complete, or contains multiple players with the same role.

### Refresh behavior

Refresh team needs after:

- Selecting a team.
- Adding or removing a player.
- A negotiation is accepted and the player changes teams.

Avoid duplicating roster calculations in React; the API should be the source of truth.

## Phase 3: Transfer Integration

After an accepted transfer in [app/routes/negotiations.py](app/routes/negotiations.py):

- The target team’s needs should immediately reflect the new roster.
- The source team’s needs should immediately reflect the lost player.
- The frontend should refresh both affected team views when possible.

Add a focused integration test proving that moving an entry player away changes the source team’s missing roles and that moving an AWPer into a team clears its AWPer need.

## Deferred Phase 4: Affordability-Aware Recruitment

Do not implement this in the first pass beyond exposing `Player.price` to the UI.

Later, add a team-level or manager-level recruitment budget policy and apply it consistently to:

- Candidate filtering (`affordable` versus `over_budget`).
- The sign/offer action.
- Negotiation validation and error messages.
- Budget updates after an accepted transfer.

The existing manager budget check in [app/routes/negotiations.py](app/routes/negotiations.py) is the current transaction guard. Avoid duplicating a second affordability rule in the needs service until the ownership of the budget is decided.

## Deferred Phase 5: Like-for-Like Replacement Recruitment

When a player leaves a team, later introduce a transfer event or replacement workflow that records:

- Departing player id, base role, role confidence, IGL status, and key performance values.
- The source team’s missing role after the transfer.
- Candidate similarity to the departed player.

Replacement ranking should first require the missing compulsory role, then score similarity using the departed player’s role fit and performance profile. If the departed player was the IGL, prioritize candidates with a high `igl_score`, but still choose the team IGL from the complete resulting roster rather than permanently assigning the replacement.

This should be a separate recommendation policy from the basic `GET /teams/{team_id}/needs/candidates` endpoint so the first version remains simple.

## Data and Migration Considerations

- No new database table is required for Phase 1 because roster membership already lives in `Player.team_id`.
- Do not persist derived missing-role state; calculate it from the current roster to avoid stale data after transfers.
- If future rules require contract state, transfer history, budgets per team, or replacement events, add those as separate models and migrations rather than overloading `Team` or `Player`.
- Confirm whether the existing SQLite database is recreated on startup in development before adding persistent columns.

## Test Plan

Add unit tests for the roster-analysis service:

1. Empty team reports `empty` and missing `entry` and `awper`.
2. A team with an entry but no AWPer reports only `awper` as missing.
3. `entry igl` satisfies the entry slot and can be selected as IGL.
4. Multiple supports and lurkers are valid and counted without creating missing-role errors.
5. The highest `igl_score` wins, with deterministic behavior for ties.
6. A player with no role does not accidentally satisfy a compulsory slot.
7. Candidate results exclude players already on the target team and rank matching roles first.

Extend negotiation tests in [tests/test_negotiations.py](tests/test_negotiations.py) with the post-transfer roster effect. Keep existing buyout and acceptance tests intact.

Suggested commands:

```powershell
python -m unittest discover -s tests -v
```

For the frontend, manually verify an empty team, a partially filled team, a complete team, and an accepted transfer in the running app. Add component tests if a frontend test runner is introduced later.

## Acceptance Criteria

- A manager can open any team and see its compulsory role gaps.
- The module identifies exactly one live IGL using the highest current `igl_score`.
- Supports and lurkers remain optional and may occur any number of times.
- Missing-role candidates are visible and actionable through the existing negotiation flow.
- Accepted transfers update the needs of both the buying and selling teams.
- No candidate is rejected solely because of price in the first implementation.
- Affordability and like-for-like replacement are documented extension points, not partially implemented hidden behavior.
