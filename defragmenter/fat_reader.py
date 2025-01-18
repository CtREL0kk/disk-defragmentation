import struct
from pathlib import Path

from defragmenter.bpb import BPB
from defragmenter.cluster import Cluster

FAT_ENTRY_SIZE = 4
FAT_ENTRY_MASK = 0x0FFFFFFF
FAT_END_MASK = 0x0FFFFFF8

class FatReader:
    """
    Класс для чтения FAT таблицы
    """
    def __init__(self, image_path: Path, bpb: BPB) -> None:
        self.image_path = image_path
        self.bpb = bpb
        self.cluster_size = self.bpb.sec_per_clus * self.bpb.byts_per_sec
        self.clusters: list[Cluster] = self._read_fat()

    def _read_fat(self) -> list[Cluster]:
        """
        Читает FAT таблицу, разбивая ее на кластеры
        """
        fat_start = self.bpb.reserved_sec_cnt * self.bpb.byts_per_sec
        fat_size = self.bpb.fat_size_32 * self.bpb.byts_per_sec
        max_clusters = fat_size // FAT_ENTRY_SIZE
        clusters: list[Cluster] = []

        with open(self.image_path, 'rb') as image_file:
            image_file.seek(fat_start)
            fat_data = image_file.read(fat_size)

            for i in range(0, len(fat_data), FAT_ENTRY_SIZE):
                entry_data = fat_data[i:i + FAT_ENTRY_SIZE]
                cluster_value = struct.unpack("<I", entry_data)[0] & FAT_ENTRY_MASK
                if len(clusters) >= max_clusters:
                    break
                is_end = cluster_value >= FAT_END_MASK
                clusters.append(Cluster(index=i // FAT_ENTRY_SIZE, next_index=cluster_value, is_end=is_end))
        return clusters

    def get_cluster_chain(self, start_cluster_index: int) -> list[Cluster]:
        """
        Возвращает цепочку кластеров
        """
        chain: list[Cluster] = []
        current_cluster_index: int = start_cluster_index
        visited: set[int] = set()
        while 2 <= current_cluster_index < len(self.clusters) and self.clusters[current_cluster_index].is_valid():
            if current_cluster_index in visited:
                print(f"Цикл обнаружен в цепочке кластеров: {current_cluster_index}")
                break

            visited.add(current_cluster_index)
            cluster_obj = self.clusters[current_cluster_index]
            chain.append(cluster_obj)
            if cluster_obj.is_end:
                break

            current_cluster_index = cluster_obj.next_index
        return chain

    def read_cluster_data(self, cluster: Cluster) -> bytes:
        """
        Читает данные кластера
        """
        cluster_offset = self.get_cluster_offset(cluster.index)

        with open(self.image_path, 'rb') as image_file:
            image_file.seek(cluster_offset)
            return image_file.read(self.cluster_size)

    def get_cluster_offset(self, cluster_index: int) -> int:
        """
        Вычисляет смещение кластера в байтах
        """
        data_region = self.bpb.reserved_sec_cnt + (self.bpb.num_fats * self.bpb.fat_size_32)
        cluster_start = data_region * self.bpb.byts_per_sec
        cluster_offset = cluster_start + (cluster_index - 2) * self.cluster_size
        return cluster_offset
