# Thinking Machine — Architecture Overview

## Purpose

A Discord bot for managing **Dune classic board game faction selection drafts**. It automates the process of fairly distributing the 12 available Dune factions among 1–5 players using a snake-draft mechanism with random draws. Players can view faction details and rules PDFs before making selections, and the bot tracks all assignments in real-time across one or more concurrent drafts per server.

---

## Directory Structure

```
thinking-machine/
├── main.py             # Entry point; bot init, on_ready, slash command sync
├── bot.py              # Bot instance creation (discord.py Client)
├── commands.py         # All 8 slash command handlers
├── game.py             # Core turn flow: run_next_pick, handle_pick, show_final_results
├── models.py           # GameSession model + JSON persistence helpers
├── views.py            # Discord UI components (buttons, dropdowns)
├── factions.py         # Hardcoded definitions for all 12 Dune factions
├── game_state.json     # Persistent draft storage (written at runtime)
├── pdfs/
│   ├── rules.pdf       # Full Dune rulebook
│   └── errata.pdf      # Official errata
├── .env                # DISCORD_TOKEN (not committed)
├── requirements.txt    # discord.py>=2.0.0, python-dotenv>=1.0.0
├── README.md
├── COMMANDS.md
└── TESTING.md
```

---

## Tech Stack

| Category | Choice |
|----------|--------|
| Language | Python 3.x |
| Discord API | discord.py >= 2.0 |
| Config | python-dotenv |
| Persistence | JSON file (`game_state.json`) |

---

## Component Responsibilities

| File | Role |
|------|------|
| **main.py** | Loads `.env`, registers commands, calls `load_and_restore()` on `on_ready` |
| **bot.py** | Creates the single `discord.Bot` instance with `!` prefix and default intents |
| **commands.py** | Validates and dispatches all slash commands; enforces host-only and state-machine rules |
| **game.py** | Owns the draft turn loop: draws 3 random factions, awaits a pick, advances state, calls final results |
| **models.py** | `GameSession` dataclass + `get/set/delete_session` helpers + `to_dict/from_dict` for JSON serialization |
| **views.py** | `DraftView` (3 pick buttons + 3 details buttons), `DetailsButton` (ephemeral popup with PDFs), `FactionPoolSelect` (host setup dropdown) |
| **factions.py** | Static dict of 12 factions — name, description, emoji, color, expansion flag |

---

## Data Flow

```
Discord User
     │
     │  /newdraft / /joindraft / /startdraft
     ▼
commands.py  ──creates/updates──▶  GameSession (models.py)
     │                                   │
     │                             game_state.json
     │
     │  run_next_pick()
     ▼
game.py  ──draws 3 factions──▶  DraftView (views.py)
                                      │
                              Discord Thread
                                      │
                              Player clicks pick
                                      │
                              PickButton.callback()
                                      │
                              game.handle_pick()
                                      │
                    ┌─────────────────┴──────────────────┐
                    │                                    │
              advance turn                          end draft
           run_next_pick()                    show_final_results()
```

---

## Session State Machine

```
  joining    ←── /newdraft creates the session here
     │
     │  (host selects faction pool, players /joindraft)
     ▼
  drafting   ←── /startdraft transitions here, fires run_next_pick()
     │
     │  (each player picks until all are assigned)
     ▼
   done      ←── show_final_results() posts final assignments
```

A `GameSession` stores:

```json
{
  "name": "mygame",
  "host_id": 123,
  "player_ids": [123, 456, 789],
  "faction_pool": ["Atreides", "Fremen", "Harkonnen", "..."],
  "current_draw": ["Atreides", "Fremen", "Harkonnen"],
  "current_index": 1,
  "assignments": {"0": "Fremen"},
  "state": "drafting",
  "channel_id": 111,
  "draft_channel_id": 222,
  "test_mode": false
}
```

All sessions are keyed by `guild_id → draft_name` and written to disk after every state change.

---

## Slash Commands

| Command | Who | Description |
|---------|-----|-------------|
| `/newdraft` | Anyone | Create a draft, select faction pool via dropdown |
| `/joindraft` | Anyone | Join an open draft in pick order |
| `/startdraft` | Host | Lock the roster and begin the snake draft |
| `/canceldraft` | Host | Abort a draft and delete the thread |
| `/draftplayers` | Anyone | List players currently joined |
| `/renamedraft` | Host | Rename an in-progress draft |
| `/cleanupdraft` | Host | Remove a completed draft's state |
| `/listdrafts` | Anyone | Show all active drafts in the server |

---

## Key Design Decisions

- **Discord Threads** — each draft gets its own thread (`#draft-<name>`), keeping the main channel clean and all picks co-located.
- **Persistent views** — `DraftView` is registered as a persistent view so pick buttons survive bot restarts.
- **Bot restart recovery** — `load_and_restore()` reads `game_state.json` on startup and rebuilds in-memory state and persistent views for any active drafts.
- **Solo test mode** — `/newdraft name:test` pre-fills 3 seats with the host and disables turn enforcement for solo testing.
- **Lazy imports in views** — circular import between `game.py` and `views.py` is broken by importing `DraftView` inside functions rather than at module level.

---

## Factions

12 factions are defined in `factions.py` (6 base game, 6 expansion):

**Base**: Atreides, Harkonnen, Emperor, Spacing Guild, Bene Gesserit, Fremen  
**Expansion**: Ixians, Tleilaxu, CHOAM, Richese, Ecaz, Moritani
