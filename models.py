import os
import json

STATE_FILE = "game_state.json"

game_sessions: dict[int, "GameSession"] = {}


class GameSession:
    def __init__(self, guild_id: int, host_id: int):
        self.guild_id = guild_id
        self.host_id = host_id
        self.player_ids: list[int] = []       # user IDs in join order (may repeat in test mode)
        self.faction_pool: set[str] = set()
        self.assignments: dict[int, str] = {} # seat index -> faction name
        self.current_index: int = 0
        self.current_draw: list[str] = []
        self.state: str = "setup"             # setup | joining | drafting | done
        self.channel_id: int | None = None
        self.test_mode: bool = False          # True when one person fills all seats

    @property
    def current_player_id(self) -> int | None:
        if self.current_index < len(self.player_ids):
            return self.player_ids[self.current_index]
        return None

    def to_dict(self) -> dict:
        return {
            "host_id": self.host_id,
            "player_ids": self.player_ids,
            "faction_pool": list(self.faction_pool),
            "assignments": {str(k): v for k, v in self.assignments.items()},
            "current_index": self.current_index,
            "current_draw": self.current_draw,
            "state": self.state,
            "channel_id": self.channel_id,
            "test_mode": self.test_mode,
        }

    @classmethod
    def from_dict(cls, guild_id: int, data: dict) -> "GameSession":
        s = cls(guild_id=guild_id, host_id=data["host_id"])
        s.player_ids = data["player_ids"]
        s.faction_pool = set(data["faction_pool"])
        s.assignments = {int(k): v for k, v in data["assignments"].items()}
        s.current_index = data["current_index"]
        s.current_draw = data["current_draw"]
        s.state = data["state"]
        s.channel_id = data.get("channel_id")
        s.test_mode = data.get("test_mode", False)
        return s


def save_state():
    data = {
        str(gid): s.to_dict()
        for gid, s in game_sessions.items()
        if s.state != "done"
    }
    with open(STATE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_raw_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}
