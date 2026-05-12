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

> Slash commands can take up to 1 hour to propagate globally. To test instantly, sync to a specific guild — see section 7 at the bottom.

---

## 4. Command Reference

| Command | Parameters | Who can use | Description |
|---|---|---|---|
| `/newdraft` | `name` (required), `player_count` (optional 1–5) | Anyone | Creates a new draft and opens the faction pool selector |
| `/joindraft` | `name` (required) | Anyone | Joins an open draft in the order you run the command |
| `/startdraft` | `name` (required) | Host only | Begins the faction pick sequence |
| `/enddraft` | `name` (required) | Host only | Cancels and removes a draft |
| `/draftplayers` | `name` (required) | Anyone | Shows the current player lineup for a draft |
| `/listdrafts` | — | Anyone | Lists all active drafts in the server |

**Draft names** are case-insensitive and stripped of leading/trailing spaces (`Friday Night` and `friday-night` are the same draft). The `::` character is not allowed in names.

### Solo testing (no second account needed)

Pass `player_count` to `/newdraft` to pre-fill seats with your own account. The turn enforcement is bypassed for the host, so you can click picks for every seat yourself:

```
/newdraft name:test player_count:3
```

---

## 5. Testing the Full Draft Flow

### Solo (one account)

1. `/newdraft name:test player_count:3` — select all factions in the pool dropdown
2. `/startdraft name:test` — draft begins
3. Click **Choose** for each seat in turn — you can click any button since you are the host
4. After all 3 seats have picked, confirm the final assignments embed appears with seat labels (e.g. "YourName (Seat 2)")

### Multiplayer (two or more accounts)

Open a second account in an incognito window or a second browser.

1. **Host** runs `/newdraft name:friday-night` — selects faction pool
2. **Each player** runs `/joindraft name:friday-night` in the order they want to pick
3. Verify `/draftplayers name:friday-night` shows the correct join order
4. **Host** runs `/startdraft name:friday-night`
5. Player 1 sees their 3 draws — click a **Details** button first to confirm it's ephemeral
6. Player 1 clicks a **Choose** button — confirm the embed updates and player 2's draw appears
7. Repeat until complete — confirm the final embed lists everyone with no duplicate factions

### Running two drafts simultaneously

```
/newdraft name:game-1
/newdraft name:game-2
```

Both run independently. Use `/listdrafts` to see both listed. Each draft's buttons only affect that draft.

---

## 6. Edge Case Tests

| Scenario | Expected result |
|---|---|
| `/newdraft name:x` when `x` is already running | Ephemeral error: "A draft named x is already running" |
| `/joindraft` before faction pool is set | Ephemeral error: not in joining phase |
| `/joindraft` on a solo test mode draft | Ephemeral error: seats are pre-filled |
| `/joindraft` twice with the same account | Ephemeral error: "You've already joined" |
| `/joindraft` as a 6th player | Ephemeral error: "This draft is full" |
| `/startdraft` with 0 players | Ephemeral error: "At least 1 player must join" |
| `/startdraft` as non-host | Ephemeral error: "Only the host can start" |
| `/enddraft` as non-host | Ephemeral error: "Only the host can cancel" |
| `/enddraft` mid-draft | Draft cancelled cleanly, new draft with same name allowed |
| Wrong player clicks a Choose button | Ephemeral error: "It's X's turn!" |
| 5 players, all 6 base factions in pool | Player 5 gets 2 choices instead of 3 (expected — pool math) |
| Bot restarts mid-draft | Bot sends a recovery message; existing buttons remain valid |

---

## 7. Instant Slash Command Sync (Optional)

By default, `bot.tree.sync()` syncs globally (up to 1 hour delay). To sync instantly to one server during development, replace the `on_ready` event in `main.py`:

```python
TEST_GUILD_ID = 123456789012345678  # your server ID

@bot.event
async def on_ready():
    await load_and_restore()
    guild = discord.Object(id=TEST_GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Slash commands synced to test guild.")
```

Replace `TEST_GUILD_ID` with your server's ID (right-click your server icon → **Copy Server ID** — requires Developer Mode enabled in Discord settings).
