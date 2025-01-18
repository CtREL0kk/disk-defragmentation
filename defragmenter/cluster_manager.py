import struct
from pathlib import Path

from defragmenter.cluster import Cluster
from defragmenter.directory_parser import DirectoryParser
from defragmenter.fat_reader import FatReader

FAT_ENTRY_MASK = 0x0FFFFFFF
FAT_FREE_MASK = 0x00000000

class ClusterManager:
    """
    Базовый класс для управления кластерами в файловой системе FAT32.
    """
    def __init__(self, image_path: Path, fat_reader: FatReader, directory_parser: DirectoryParser) -> None:
        self._image_path = image_path
        self._fat_reader = fat_reader
        self._directory_parser = directory_parser
        self._bpb = fat_reader.bpb
        self._free_clusters: list[int] = self._find_free_clusters()

    def find_fragmented_files(self, all_files: list[dict]) -> list[dict]:
        fragmented_files = []
        for file_entry in all_files:
            cluster_chain = self._fat_reader.get_cluster_chain(file_entry["starting_cluster"])
            if self._is_fragmented(cluster_chain):
                fragmented_files.append({
                    "path": file_entry["path"],
                    "cluster_chain": [cluster.index for cluster in cluster_chain]
                })

        return fragmented_files

    def _is_fragmented(self, cluster_chain: list[Cluster]) -> bool:
        """
        Проверяет, является ли кластерная цепочка фрагментированной.
        """
        for cluster_index in range(len(cluster_chain) - 1):
            if cluster_chain[cluster_index].next_index != (cluster_chain[cluster_index].index + 1):
                return True
        return False

    def _write_fat(self) -> None:
        """
        Записывает обновлённую FAT таблицу обратно в образ диска.
        """
        with open(self._image_path, 'r+b') as f:
            fat_start = self._bpb.reserved_sec_cnt * self._bpb.byts_per_sec
            fat_size = self._bpb.fat_size_32 * self._bpb.byts_per_sec
            fat_data = bytearray()

            for cluster in self._fat_reader.clusters:
                fat_entry = cluster.next_index & FAT_ENTRY_MASK
                fat_data += struct.pack("<I", fat_entry)

            f.seek(fat_start)
            f.write(fat_data[:fat_size])

        print("FAT таблицы обновлены.")

    def _find_free_clusters(self):
        """
        Находит все свободные кластеры.
        """
        return [cluster.index for cluster in self._fat_reader.clusters if cluster.next_index == FAT_FREE_MASK]

    def _copy_cluster_data(self, old_cluster_index: int, new_cluster_index: int) -> None:
        """
        Копирует данные из одного кластера в другой
        """
        with open(self._image_path, 'r+b') as f:
            old_data = self._fat_reader.read_cluster_data(self._fat_reader.clusters[old_cluster_index])
            f.seek(self._fat_reader.get_cluster_offset(new_cluster_index))
            f.write(old_data)

    def _update_directory_entry(self, file_entry: dict, new_start_cluster_index: int) -> None:
        """
        Обновляет поле starting_cluster для файла в каталоге.
        """
        self._directory_parser.update_starting_cluster(file_entry['path'], new_start_cluster_index)

    def _update_fat(self, old_clusters_indices: list[int], new_clusters_indices: list[int]) -> None:
        """
        Обновляет FAT таблицу: освобождает старые кластеры и связывает новые кластеры.
        """
        for cluster in old_clusters_indices:
            self._fat_reader.clusters[cluster].next_index = FAT_FREE_MASK

        for i in range(len(new_clusters_indices) - 1):
            self._fat_reader.clusters[new_clusters_indices[i]].next_index = new_clusters_indices[i + 1]
        self._fat_reader.clusters[new_clusters_indices[-1]].next_index = FAT_ENTRY_MASK
