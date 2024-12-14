class Cluster:
    def __init__(self, index : int, next_index : int, is_end=False) -> None:
        self.index = index
        self.next_index = next_index
        self.is_end = is_end

    def is_valid(self) -> bool:
        '''
        Проверяет, является ли кластер валидным
        '''
        return 2 <= self.index < 0x0FFFFFF8