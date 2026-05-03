# Dune Faction Draft Bot Commands

## `/newgame` [1–5]
Starts a new Dune faction draft game for your server.

**Parameters:**
- `player_count` (optional, 1–5): Solo testing mode. Pre-fills the specified number of seats so one person can run through the full draft alone.

**Flow:**
1. Creates a new game session
2. Presents a faction pool selector (must choose at least 3 factions)
3. Transitions to the player joining phase

---

## `/join`
Join an active Dune game.

**Requirements:**
- An active game must exist (started via `/newgame`)
- Game must be in the "joining" state
- You must not already be joined
- Game must have fewer than 5 players

**Response:**
- Shows updated player list with current player count (X/5)

---

## `/startdraft` [Host only]
Begin the faction draft. Only the game host can run this command.

**Requirements:**
- An active game must exist
- At least 1 player must have joined
- Faction pool must contain at least 3 factions
- Game must be in "joining" state

**Flow:**
1. Transitions game to "drafting" state
2. Records the channel where the draft will happen
3. Initiates the first faction pick

---

## `/endgame` [Host only]
Cancel the current game. Only the game host can run this command.

**Requirements:**
- An active game must exist

**Effect:**
- Completely removes the game session
- All player progress is lost

---

## `/players`
Display the current player lineup for the active game.

**Response:**
- Shows all joined players with their seat numbers (if in test mode with duplicate seats)
- Shows current player count

---

## Game Flow Summary

1. **Host** runs `/newgame` (optionally with `player_count` for testing)
2. **Host** selects factions from the pool
3. **Other players** run `/join` (up to 5 total)
4. **Host** runs `/startdraft` to begin the draft
5. Players take turns selecting factions until the draft completes
6. Game transitions to "done" state

To cancel at any point, the **host** can run `/endgame`.
