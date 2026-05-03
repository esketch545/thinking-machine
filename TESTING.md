# Testing Guide

## 1. Create a Discord Test Bot

1. Go to https://discord.com/developers/applications
2. Click **New Application**, give it a name (e.g. "Dune Bot Test")
3. Go to the **Bot** tab → click **Add Bot**
4. Under **Token**, click **Reset Token** and copy it
5. Paste it into your `.env` file:
   ```
   DISCORD_TOKEN=your_token_here
   ```
6. Scroll down to **Privileged Gateway Intents** and enable:
   - **Server Members Intent**
   - **Message Content Intent**

## 2. Invite the Bot to a Test Server

1. In the Developer Portal, go to **OAuth2 → URL Generator**
2. Under **Scopes**, check: `bot` and `applications.commands`
3. Under **Bot Permissions**, check: `Send Messages`, `Embed Links`, `Read Message History`
4. Copy the generated URL and open it in your browser to invite the bot to your test server

## 3. Install Dependencies & Run

```bash
pip install -r requirements.txt
python main.py
```

You should see:
```
Logged in as YourBot#1234 (ID: ...)
Slash commands synced.
```

> Slash commands can take up to 1 hour to propagate globally. To test instantly, sync to a specific guild by adding your server ID — see the note at the bottom.

---

## 4. Testing the Full Draft Flow

Open your test server and run through this sequence:

### Step 1 — Start a game
```
/newgame
```
A dropdown appears. Select at least 3 factions (select all 12 to test expansion factions). Confirm the pool is shown correctly.

### Step 2 — Join as players
Have 2–5 accounts (or use a second account in a different browser) run:
```
/join
```
Each join should show an updated numbered player list. Verify:
- You cannot join twice
- A 6th player is rejected with "game is full"

### Step 3 — View the player list
```
/players
```
Confirm the order matches the join order.

### Step 4 — Start the draft
As the host (the account that ran `/newgame`):
```
/startdraft
```
Verify:
- A non-host account gets an "Only the host" error
- The first player sees 3 faction draw buttons (row 1) and 3 Details buttons (row 2)

### Step 5 — Test Details buttons
Click a **Details** button. Confirm:
- The response is ephemeral (only you see it)
- It shows the faction description and PDF URL field

### Step 6 — Test wrong-player enforcement
Have a different account (not the current player) click a **Choose** button. Confirm they get an ephemeral "It's X's turn!" error.

### Step 7 — Pick a faction
The current player clicks a **Choose** button. Confirm:
- The embed updates to show who chose what
- The next player's draw appears, including an "Assignments so far" section
- The chosen faction does not reappear in the pool

### Step 8 — Complete the draft
Continue until all players have chosen. Confirm:
- The final embed lists every player and their faction
- No faction appears twice

---

## 5. Edge Case Tests

| Scenario | Expected Result |
|---|---|
| `/newgame` when a game is already running | Ephemeral error: "A game is already running" |
| `/join` before faction pool is set | Ephemeral error: game not in joining phase |
| `/startdraft` with 0 players | Ephemeral error: "At least 1 player must join" |
| `/endgame` as non-host | Ephemeral error: "Only the host can cancel" |
| `/endgame` as host mid-draft | Game cancelled, session cleared |
| `/newgame` after `/endgame` | Works cleanly |
| 5 players, all 6 base factions in pool | Player 5 gets only 2 choices (expected — pool math) |

---

## 6. Instant Slash Command Sync (Optional)

By default, `bot.tree.sync()` syncs globally (up to 1 hour delay). To sync instantly to one server during development, replace the `on_ready` event in `main.py`:

```python
TEST_GUILD_ID = 123456789012345678  # your server ID

@bot.event
async def on_ready():
    guild = discord.Object(id=TEST_GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Slash commands synced to test guild.")
```

Replace `TEST_GUILD_ID` with your server's ID (right-click your server icon → **Copy Server ID** — requires Developer Mode to be on in Discord settings).
