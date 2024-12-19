from dataclasses import dataclass

MAX_VALID_INDEX = 0x0FFFFFF8
MIN_VALID_INDEX = 2

@dataclass
class Cluster:
    index: int
    next_index: int
    is_end: bool = False

    def is_valid(self) -> bool:
        """
        Проверяет, является ли кластер валидным
        """
        return MIN_VALID_INDEX <= self.index < MAX_VALID_INDEX
