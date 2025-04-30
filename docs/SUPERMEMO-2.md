# SuperMemo-2 (SM-2) Algorithm Overview

## Summary

SuperMemo-2 (SM-2) is a popular spaced repetition system (SRS) algorithm designed by Piotr Woźniak in the late 1980s. Its primary goal is to help users memorize information efficiently by scheduling reviews at optimal intervals. The core idea is to review information just before the user is likely to forget it. SM-2 calculates the next review date for a flashcard based on the user's performance (how easily they recalled the information) during the previous review.

This document outlines the conceptual basis of SM-2 and how card statuses and transitions are handled *within this specific project's implementation* (`server/app.py`), which is inspired by SM-2 and Anki's modifications but has its own specific logic.

## Card Statuses

Cards progress through different states managed by their `queue` and `type` properties in the database:

*   **New (`queue=0`, `type=0`):** A card that has not been reviewed yet or was answered "Again" during its very first learning step.
*   **Learning (`queue=1`, `type=1`):** A card currently in the initial learning phase. It's shown at short, predefined intervals (e.g., 1 minute, 10 minutes) based on the deck's configuration (`dconf['new']['delays']`).
*   **Review (`queue=2`, `type=2`):** A card that has graduated from the Learning phase. It's reviewed at increasing intervals measured in days (e.g., 1 day, 4 days, 10 days...).
    *   **Young:** A review card with an interval (`ivl`) less than 21 days.
    *   **Mature:** A review card with an interval (`ivl`) of 21 days or more.
*   **Relearning (`queue=1`, `type=3`):** A Review card that was forgotten (answered "Again"). It re-enters a learning phase, similar to new cards but using different steps defined in the deck's lapse configuration (`dconf['lapse']['delays']`). Its `type` distinguishes it from initial learning cards.
*   **Suspended (`queue=-1`):** Manually suspended by the user. Not shown for review.
*   **Buried (`queue=-2`, `queue=-3`):** Automatically hidden temporarily (e.g., siblings of a card just reviewed, or user-buried). Not shown for review until the next day.

## Status Transitions (Based on `app.py` Implementation)

When a card is reviewed via the `/review` endpoint and answered via the `/answer` endpoint, its status changes based on the `ease` rating provided (1: Again, 2: Hard, 3: Good, 4: Easy).

**1. From New (`queue=0`)**

*   **Ease 1 (Again):** -> Learning (`queue=1`, `type=1`). Card stays in the first learning step defined in `dconf['new']['delays']`. Due soon (e.g., 1 minute).
*   **Ease 2 (Hard):** -> Learning (`queue=1`, `type=1`). Moves to the first learning step. Due soon (e.g., 1 minute).
*   **Ease 3 (Good):** -> Learning (`queue=1`, `type=1`). Moves to the *next* learning step. If no more steps, graduates.
*   **Ease 4 (Easy):** -> Learning (`queue=1`, `type=1`). Moves to the *next* learning step (typically same as "Good" in multi-step learning) or graduates immediately if only one step defined. *Note: In some systems, Easy might graduate directly.*

**2. From Learning (`queue=1`, `type=1`)**

*   **Ease 1 (Again):** -> Learning (`queue=1`, `type=1`). Resets to the *first* learning step. Due soon.
*   **Ease 2 (Hard):** -> Learning (`queue=1`, `type=1`). Repeats the *current* learning step's delay. Due again after that delay.
*   **Ease 3 (Good):** -> Learning (`queue=1`, `type=1`) moving to the *next* step, OR graduates to Review (`queue=2`, `type=2`) if it was the *last* learning step. Graduated interval is typically 1 day (`new_interval=1`, `new_due = dayCutoff + 1`).
*   **Ease 4 (Easy):** -> Graduates to Review (`queue=2`, `type=2`). Graduated interval is typically 1 day (`new_interval=1`, `new_due = dayCutoff + 1`).

**3. From Review (`queue=2`, `type=2`)**

*   **Ease 1 (Again):** -> Relearning (`queue=1`, `type=3`). Lapses count increments. Enters relearning steps defined in `dconf['lapse']['delays']`. Due soon based on the first lapse step. Factor might be penalized.
*   **Ease 2 (Hard):** -> Review (`queue=2`, `type=2`). Interval (`ivl`) increases based on `current_interval * hardFactor * interval_factor`. Due date (`due`) updated (`dayCutoff + new_interval`). Factor penalized (e.g., -150).
*   **Ease 3 (Good):** -> Review (`queue=2`, `type=2`). Interval (`ivl`) increases based on `current_interval * interval_factor`. Due date (`due`) updated (`dayCutoff + new_interval`). Factor unchanged in this implementation.
*   **Ease 4 (Easy):** -> Review (`queue=2`, `type=2`). Interval (`ivl`) increases based on `current_interval * easy_bonus * interval_factor`. Due date (`due`) updated (`dayCutoff + new_interval`). Factor increased (e.g., +150).

**4. From Relearning (`queue=1`, `type=3`)**

*   (Transitions function similarly to the **Learning** state, but uses lapse steps/configuration)
*   **Ease 1 (Again):** -> Relearning (`queue=1`, `type=3`). Resets to the *first* lapse step.
*   **Ease 2 (Hard):** -> Relearning (`queue=1`, `type=3`). Repeats the *current* lapse step's delay.
*   **Ease 3 (Good):** -> Relearning (`queue=1`, `type=3`) moving to the *next* lapse step, OR graduates back to Review (`queue=2`, `type=2`) if it was the *last* lapse step. Graduated interval depends on lapse settings.
*   **Ease 4 (Easy):** -> Graduates back to Review (`queue=2`, `type=2`).

## Algorithm Parameters (Conceptual SM-2)

The standard SM-2 algorithm relies on these key parameters:

*   **Easiness Factor (EF):** A number (starting around 2.5, minimum 1.3) representing how easy a card is. Lower means harder. It's adjusted after each review based on performance (`q`, quality 0-5).
    *   Formula: `EF' = EF + (0.1 - (5-q)*(0.08 + (5-q)*0.02))` (EF' cannot be < 1.3)
*   **Interval (Ivl):** The number of days between reviews.
    *   Calculation: `I(1) = 1`, `I(2) = 6`, `I(n) = I(n-1) * EF'` for n > 2.

## Deviation in this Project

It's important to note that the current implementation in `app.py` **deviates significantly** from the pure SM-2 formulas above, particularly in the `/answer` route:

1.  **Easiness Factor:** Instead of the SM-2 formula, the factor (`factor` column, EF * 1000) is adjusted using fixed increments/decrements based on the ease button pressed (e.g., -150 for Hard, 0 for Good, +150 for Easy, similar to Anki's modifications).
2.  **Interval Calculation:** The next interval for review cards is not calculated directly using the *new* Easiness Factor. Instead, it's calculated by multiplying the *previous* interval by multipliers sourced from the deck configuration (`hardFactor`, `ivlFct`, `ease4`).

While functional, this means the scheduling behavior is controlled more by the deck configuration parameters than by the dynamically calculated Easiness Factor as in pure SM-2.

## References

*   **Original SuperMemo Algorithm Page:** [Algorithm SM-2 used in the computer input based variant of the SuperMemo method](https://www.supermemo.com/en/archives1990-2015/english/ol/sm2) (Piotr Woźniak)
*   **Anki Manual - Scheduling:** [Anki Manual - Scheduling Section](https://docs.ankiweb.net/studying.html#scheduling) (Describes Anki's modified algorithm, which shares similarities with this project's implementation)
*   **Nice Explanation of SM-2:** [Implementing the SM2 Spaced Repetition Algorithm](https://www.freshconsulting.com/insights/blog/implementing-the-sm2-spaced-repetition-algorithm/) (Blog post with code examples) 