# Thinking Machine

A Discord bot for managing faction selection drafts in the **Dune Classic** board game.

---

## How It Works

### 1. Create a Draft
A host runs `/newdraft` to open a draft session. The bot creates a dedicated thread and presents a dropdown to select which factions are available for the draw (up to all 12).

### 2. Players Join
Players run `/joindraft` to register in pick order (first come, first served — max 5 players).

### 3. Start the Draft
The host runs `/startdraft`. The bot locks the roster and begins the snake draft.

### 4. Each Player Picks
On each turn, 3 factions are drawn at random from the pool and presented to the current player as buttons. The player can:
- Click a faction button to **select** it
- Click a **Details** button to read a description and download the faction rules PDF before deciding

Once a faction is chosen, the other 2 go back into the pool. Chosen factions are removed permanently.

### 5. Draft Completes
After every player has picked, the bot posts a final summary showing each player and their assigned faction.

---

## Commands

| Command | Who | Description |
|---------|-----|-------------|
| `/newdraft` | Anyone | Start a new draft and select the faction pool |
| `/joindraft` | Anyone | Join an open draft in pick order |
| `/startdraft` | Host | Lock the roster and begin picking |
| `/canceldraft` | Host | Abort the draft and remove the thread |
| `/draftplayers` | Anyone | List players currently joined |
| `/renamedraft` | Host | Rename an in-progress draft |
| `/cleanupdraft` | Host | Remove a completed draft's saved state |
| `/listdrafts` | Anyone | Show all active drafts in the server |

---

## Factions

**Base game (6):** Atreides, Harkonnen, Emperor, Spacing Guild, Bene Gesserit, Fremen

**Expansion (6):** Ixians, Tleilaxu, CHOAM, Richese, Ecaz, Moritani

---

## Setup

1. Clone the repo and install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Create a `.env` file with your bot token:
   ```
   DISCORD_TOKEN=your_token_here
   ```
3. Run the bot:
   ```
   python main.py
   ```
