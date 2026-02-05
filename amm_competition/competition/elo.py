"""Elo rating system for AMM competition."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
import math


@dataclass
class PlayerRating:
    """Rating information for a player (strategy)."""
    name: str
    rating: float = 1500.0
    matches_played: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0

    @property
    def win_rate(self) -> float:
        """Win rate as a percentage."""
        if self.matches_played == 0:
            return 0.0
        return self.wins / self.matches_played


class EloRating:
    """Elo rating system with margin-of-victory adjustment.

    Uses standard Elo formula with K-factor that decreases as
    players play more matches. Also includes margin-of-victory
    multiplier based on score difference.
    """

    def __init__(
        self,
        initial_rating: float = 1500.0,
        k_factor: float = 32.0,
        mov_factor: float = 0.5,
    ):
        """
        Args:
            initial_rating: Starting rating for new players
            k_factor: Base K-factor for rating changes
            mov_factor: Margin-of-victory sensitivity (0 = ignore, 1 = linear)
        """
        self.initial_rating = initial_rating
        self.k_factor = k_factor
        self.mov_factor = mov_factor
        self.ratings: dict[str, PlayerRating] = {}

    def get_rating(self, name: str) -> PlayerRating:
        """Get or create rating for a player."""
        if name not in self.ratings:
            self.ratings[name] = PlayerRating(
                name=name,
                rating=self.initial_rating,
            )
        return self.ratings[name]

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """Calculate expected score for player A against player B.

        Returns:
            Expected score between 0 and 1
        """
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))

    def get_k_factor(self, player: PlayerRating) -> float:
        """Get K-factor adjusted for number of matches played.

        New players have higher K to allow faster calibration.
        """
        if player.matches_played < 10:
            return self.k_factor * 1.5
        elif player.matches_played < 30:
            return self.k_factor
        else:
            return self.k_factor * 0.75

    def margin_multiplier(
        self, winner_score: int, loser_score: int, total_games: int
    ) -> float:
        """Calculate margin-of-victory multiplier.

        Args:
            winner_score: Games won by winner
            loser_score: Games won by loser
            total_games: Total games in match

        Returns:
            Multiplier >= 1.0
        """
        if total_games == 0:
            return 1.0

        margin = (winner_score - loser_score) / total_games
        # Logarithmic scaling to prevent extreme multipliers
        return 1.0 + self.mov_factor * math.log(1 + margin * 2)

    def update_ratings(
        self,
        player_a: str,
        player_b: str,
        score_a: int,
        score_b: int,
    ) -> tuple[float, float]:
        """Update ratings after a match.

        Args:
            player_a: Name of first player
            player_b: Name of second player
            score_a: Games won by player A
            score_b: Games won by player B

        Returns:
            Tuple of (new_rating_a, new_rating_b)
        """
        rating_a = self.get_rating(player_a)
        rating_b = self.get_rating(player_b)

        total_games = score_a + score_b
        if total_games == 0:
            return rating_a.rating, rating_b.rating

        # Determine actual scores (1 for win, 0.5 for draw, 0 for loss)
        if score_a > score_b:
            actual_a, actual_b = 1.0, 0.0
            rating_a.wins += 1
            rating_b.losses += 1
            multiplier = self.margin_multiplier(score_a, score_b, total_games)
        elif score_b > score_a:
            actual_a, actual_b = 0.0, 1.0
            rating_a.losses += 1
            rating_b.wins += 1
            multiplier = self.margin_multiplier(score_b, score_a, total_games)
        else:
            actual_a, actual_b = 0.5, 0.5
            rating_a.draws += 1
            rating_b.draws += 1
            multiplier = 1.0

        # Calculate expected scores
        expected_a = self.expected_score(rating_a.rating, rating_b.rating)
        expected_b = 1.0 - expected_a

        # Get K-factors
        k_a = self.get_k_factor(rating_a)
        k_b = self.get_k_factor(rating_b)

        # Update ratings
        rating_a.rating += k_a * multiplier * (actual_a - expected_a)
        rating_b.rating += k_b * multiplier * (actual_b - expected_b)

        # Update match counts
        rating_a.matches_played += 1
        rating_b.matches_played += 1

        return rating_a.rating, rating_b.rating

    def get_leaderboard(self) -> list[PlayerRating]:
        """Get all players sorted by rating (highest first)."""
        return sorted(
            self.ratings.values(),
            key=lambda p: p.rating,
            reverse=True,
        )
