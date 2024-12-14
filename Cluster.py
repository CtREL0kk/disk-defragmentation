class Cluster:
    def __init__(self, index, next_index, is_end=False):
        self.index = index
        self.next_index = next_index
        self.is_end = is_end

    def is_valid(self):
        return 2 <= self.index < 0x0FFFFFF8