# Commands Reference

All commands are Discord slash commands. Type `/` in any channel to see them.

Draft names are **case-insensitive** and whitespace is trimmed — `Friday Night` and `friday-night` refer to the same draft. The character sequence `::` is not allowed in names.

---

## `/newdraft`

Creates a new faction draft and opens the faction pool selector.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | A short name for the draft (e.g. `friday-night`) |
| `player_count` | integer 1–5 | No | Pre-fills seats with your account for solo testing |

**Notes**
- Only one draft per name can be active at a time in a server.
- The person who runs this command becomes the **host** and is the only one who can start or cancel the draft.
- After running the command, a dropdown appears to select which factions enter the draw pool. At least 3 must be selected.
- If `player_count` is provided the draft enters **solo test mode**: seats are pre-filled with your account and turn enforcement is bypassed so you can pick for every seat yourself.

**Examples**
```
/newdraft name:friday-night
/newdraft name:test player_count:3
```

---

## `/joindraft`

Joins an open draft. Players are added in the order they run this command — this determines pick order.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Name of the draft to join |

**Notes**
- Only works while the draft is in the **open** (joining) phase, after the host has selected the faction pool and before `/startdraft` is run.
- Maximum 5 players per draft.
- Each Discord account can only join once.
- Not available in solo test mode drafts.

**Example**
```
/joindraft name:friday-night
```

---

## `/startdraft`

Begins the faction pick sequence. Only the host can run this.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Name of the draft to start |

**Notes**
- Requires at least 1 player to have joined and at least 3 factions in the pool.
- Once started, the bot draws 3 factions for the first player and presents **Choose** and **Details** buttons.

**Example**
```
/startdraft name:friday-night
```

---

## `/enddraft`

Cancels and removes a draft. Only the host can run this.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Name of the draft to cancel |

**Notes**
- Works at any stage — setup, joining, or mid-draft.
- Once cancelled, a new draft with the same name can be created immediately.

**Example**
```
/enddraft name:friday-night
```

---

## `/draftplayers`

Shows the current player lineup for a draft, in pick order.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Name of the draft |

**Notes**
- Available at any stage.
- In solo test mode, seats are labelled `YourName (Seat 2)` etc. when the same account holds multiple seats.

**Example**
```
/draftplayers name:friday-night
```

---

## `/listdrafts`

Lists all active drafts in the server with their current status and player count.

| Parameter | Type | Required | Description |
|---|---|---|---|
| — | — | — | No parameters |

**Status labels**

| Label | Meaning |
|---|---|
| ⏳ setting up | Host has created the draft but not yet selected the faction pool |
| 🟢 open | Faction pool is set, players can join |
| 🎲 in progress | Draft has started, picks are underway |

**Example**
```
/listdrafts
```

---

## Draft Flow

```
/newdraft  →  (select faction pool)  →  /joindraft (×N players)  →  /startdraft  →  picks  →  final results
```

1. Host runs `/newdraft name:<name>` and selects factions from the dropdown
2. Players run `/joindraft name:<name>` in the order they want to pick (first come, first served)
3. Host runs `/startdraft name:<name>`
4. The bot draws 3 factions for the current player
5. That player clicks **Details** to read about a faction (visible only to them), then **Choose** to pick one
6. The chosen faction is removed from the pool; the other 2 return to it
7. Steps 4–6 repeat for each player
8. Once all players have picked, the bot posts the final assignment list

### Faction pool math

Each pick removes 1 faction from the pool (3 drawn, 1 chosen, 2 returned). With 5 players and exactly 6 factions, the last player will see 2 choices instead of 3 — this is expected.

| Players | Minimum factions recommended |
|---|---|
| 1–3 | 3+ |
| 4 | 4+ |
| 5 | 5+ (6 for 3 choices each round) |
