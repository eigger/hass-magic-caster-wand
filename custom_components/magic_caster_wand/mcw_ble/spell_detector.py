import numpy as np

from abc import ABC, abstractmethod

class SpellDetector(ABC):
    """Base class for spell detection from normalized position data."""

    SPELL_NAMES = [
        "The_Force_Spell",
        "Colloportus",
        "Colloshoo",
        "The_Hour_Reversal_Reversal_Charm",
        "Evanesco",
        "Herbivicus",
        "Orchideous",
        "Brachiabindo",
        "Meteolojinx",
        "Riddikulus",
        "Silencio",
        "Immobulus",
        "Confringo",
        "Petrificus_Totalus",
        "Flipendo",
        "The_Cheering_Charm",
        "Salvio_Hexia",
        "Pestis_Incendium",
        "Alohomora",
        "Protego",
        "Langlock",
        "Mucus_Ad_Nauseum",
        "Flagrate",
        "Glacius",
        "Finite",
        "Anteoculatia",
        "Expelliarmus",
        "Expecto_Patronum",
        "Descendo",
        "Depulso",
        "Reducto",
        "Colovaria",
        "Aberto",
        "Confundo",
        "Densaugeo",
        "The_Stretching_Jinx",
        "Entomorphis",
        "The_Hair_Thickening_Growing_Charm",
        "Bombarda",
        "Finestra",
        "The_Sleeping_Charm",
        "Rictusempra",
        "Piertotum_Locomotor",
        "Expulso",
        "Impedimenta",
        "Ascendio",
        "Incarcerous",
        "Ventus",
        "Revelio",
        "Accio",
        "Melefors",
        "Scourgify",
        "Wingardium_Leviosa",
        "Nox",
        "Stupefy",
        "Spongify",
        "Lumos",
        "Appare_Vestigium",
        "Verdimillious",
        "Fulgari",
        "Reparo",
        "Locomotor",
        "Quietus",
        "Everte_Statum",
        "Incendio",
        "Aguamenti",
        "Sonorus",
        "Cantis",
        "Arania_Exumai",
        "Calvorio",
        "The_Hour_Reversal_Charm",
        "Vermillious",
        "The_Pepper-Breath_Hex",
    ]

    @abstractmethod
    async def detect(self, positions: np.ndarray, confidence_threshold: np.float32) -> str | None:
        """
        Detect a spell from normalized position data.

        Args:
            positions: A (50, 2) float32 array of normalized positions in [0, 1] range.
            confidence_threshold: Minimum confidence required for a valid detection.

        Returns:
            The detected spell name as a string, or None if no spell was recognized
            with sufficient confidence.
        """
        pass
