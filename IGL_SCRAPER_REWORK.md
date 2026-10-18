# Future IGL Scraper Rework

**Status: tentative; planning only.** No scraper or classifier behavior is changed by this document.

## Goal

Rework team/player scraping to use each team's main HLTV team page as the source of its player roster and any HLTV IGL designation. HLTV has started identifying the IGL on team pages, so that explicit tag should become the primary way to choose a team's IGL.

Keep the existing IGL probability score as a secondary signal and fallback for teams where HLTV does not provide a usable IGL tag.

## Proposed data flow

1. Load the teams to process.
2. Open each team's main team page, rather than relying on a date- and match-filtered stats page for the roster.
3. Inspect player entries only. Extract each rostered player's name and profile URL, and detect whether that player entry carries HLTV's IGL designation.
4. Scrape player metrics from the player's stats/profile page as needed by the existing dataset.
5. Store the explicit HLTV designation as a separate field (for example, `HLTV_IGL`) so it is not confused with the computed `igl_score` or the classifier's `is_igl`.
6. During classification, prefer the explicitly tagged player as the team's IGL. Retain the existing probability logic for cases without a usable explicit tag.

## IGL selection precedence

- **Exactly one roster player is tagged IGL:** select that player, regardless of which teammate has the highest `igl_score`.
- **No roster player is tagged IGL:** retain the current highest-`igl_score` selection as the fallback.
- **Multiple roster players are tagged IGL:** do not silently choose one based on page order. Preserve the tag data and log or report the ambiguity; decide the final policy during implementation.

The IGL tag should only be read from player entries on the team page. Do not infer it from coach, substitute, bench, or other non-player labels.

## Current behavior and motivation

- [`scrapers/team_scraper.py`](./scrapers/team_scraper.py) currently starts from an HLTV team stats list and uses team stats/profile pages to find player links. The stats list has date and match filters, so it is not a reliable source of every current roster.
- [`app/classifier.py`](./app/classifier.py) calculates an `igl_score` and assigns the highest-scoring player on each team as IGL. It has no input for an explicit HLTV IGL designation yet.
- Player records already have `igl_score` and `is_igl` fields in [`app/models.py`](./app/models.py). An explicit source designation should remain distinct from these derived/game-state fields.

The scrape should no longer treat a missing or filtered stats-page lineup as proof that a team has no players. The team's main page should be the source of roster membership; player stats pages remain sources for player metrics.

## Implementation checklist for later

- [ ] Confirm HLTV's current main-team-page URL and the actual HTML/accessibility marker used for the IGL designation.
- [ ] Add parser tests for a tagged IGL, no tag, multiple tags, non-player labels, and duplicate links.
- [ ] Fetch the team's player roster from the main team page; keep stats scraping separate.
- [ ] Persist the explicit designation without overwriting `igl_score` or `is_igl`.
- [ ] Update classification so a unique explicit tag takes precedence and the score remains the fallback.
- [ ] Verify that roster membership, player metric scraping, and downstream CSV/database loading agree on the new field.
- [ ] Run a small live scrape against a few teams and compare the detected IGLs with the tags shown on HLTV before broad collection.

