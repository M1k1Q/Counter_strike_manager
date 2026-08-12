from app import models


class RatingService:
    @staticmethod
    def calculate_player_price(player: models.Player) -> int:
        return player.price
