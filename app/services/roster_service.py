from sqlalchemy.orm import Session

from app import models


class RosterService:
    def __init__(self, db: Session):
        self.db = db

    def analyze(self, team: models.Team) -> dict:
        roles_count = {"entry": 0, "support": 0, "awper": 0, "lurker": 0, "igl": 0, "unknown": 0}
        for player in team.players:
            if player.is_igl:
                roles_count["igl"] += 1
            normalized_role = self._normalize_role(player.role)
            if normalized_role in roles_count:
                roles_count[normalized_role] += 1
        return {"team_name": team.name, "team_id": team.id, "roles_count": roles_count}

    def select_igl(self, team: models.Team):
        players = team.players
        if not players:
            return None

        best_igl = None
        max_score = float("-inf")
        for player in players:
            player.is_igl = False
            score = player.igl_score or 0.0
            if score > max_score:
                max_score = score
                best_igl = player

        if best_igl:
            best_igl.is_igl = True
            current_role = best_igl.role or ""
            if "igl" not in current_role.lower():
                best_igl.role = f"{current_role} igl".strip()

        self.db.commit()
        return best_igl

    @staticmethod
    def _normalize_role(role: str) -> str:
        if not role:
            return "unknown"
        role = role.lower().strip()
        if "entry" in role:
            return "entry"
        if "support" in role:
            return "support"
        if "awper" in role:
            return "awper"
        if "lurker" in role:
            return "lurker"
        return "unknown"
