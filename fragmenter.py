import struct
import random
from pathlib import Path

from fat_reader import FatReader
from directory_parser import DirectoryParser

FAT_END_MASK = 0x0FFFFFF8
FAT_ENTRY_MASK = 0x0FFFFFFF
FAT_FREE_MASK = 0x00000000
MIN_VALID_INDEX = 2


class Fragmenter:
    """
    Класс для фрагментации файлов в файловой системе FAT32.
    """

    def __init__(self, image_path: Path, fat_reader: FatReader, directory_parser: DirectoryParser) -> None:
        self.image_path = image_path
        self.fat_reader = fat_reader
        self.directory_parser = directory_parser
        self.bpb = fat_reader.bpb
        self.free_clusters = self._find_free_clusters()

    def _find_free_clusters(self) -> list[int]:
        """
        Находит все свободные кластеры.
        """
        return [cluster.index for cluster in self.fat_reader.clusters if cluster.next_index == FAT_FREE_MASK]

    def fragment_file(self, file_path: Path) -> None:
        """
        Фрагментирует указанный файл, разбивая его на несмежные кластеры.
        """
        all_files = self.directory_parser.get_all_files(self.bpb.root_clus)
        target_file = next(f for f in all_files if f["path"].lower() == file_path)

        cluster_chain = self.fat_reader.get_cluster_chain(target_file["starting_cluster"])
        print(cluster_chain)
        cluster_indices = [cluster.index for cluster in cluster_chain]

        if len(cluster_indices) < 2:
            print(f"Файл '{file_path}' слишком мал для фрагментации.")
            return

        num_fragments = random.randint(2, min(50, len(cluster_indices)))
        clusters_to_move = random.sample(cluster_indices, num_fragments)
        print(f"Фрагментируем файл '{file_path}', перемещая кластеры: {clusters_to_move}")

        new_clusters = []
        for old_cluster_index in clusters_to_move:
            if not self.free_clusters:
                print("Нет свободных кластеров для фрагментации.")
                break
            index = random.randrange(len(self.free_clusters))
            new_cluster = self.free_clusters.pop(index)
            self._copy_cluster_data(old_cluster_index, new_cluster)
            new_clusters.append(new_cluster)
            self.fat_reader.clusters[old_cluster_index].next_index = FAT_FREE_MASK

        self.directory_parser.update_starting_cluster(target_file["path"], new_clusters[0])
        for i in range(len(new_clusters) - 1):
            self.fat_reader.clusters[new_clusters[i]].next_index = new_clusters[i + 1]
        self.fat_reader.clusters[new_clusters[-1]].next_index = FAT_ENTRY_MASK

        last_cluster = cluster_chain[-1]
        last_cluster.next_index = new_clusters[0]
        for i in range(len(new_clusters) - 1):
            self.fat_reader.clusters[new_clusters[i]].next_index = new_clusters[i + 1]
        self.fat_reader.clusters[new_clusters[-1]].next_index = FAT_ENTRY_MASK

        self._write_fat()
        print(f"Файл '{file_path}' успешно фрагментирован.")

    def _copy_cluster_data(self, old_cluster_index: int, new_cluster_index: int) -> None:
        """
        Копирует данные из одного кластера в другой.
        """
        with open(self.image_path, 'r+b') as f:
            old_offset = self.fat_reader.get_cluster_offset(old_cluster_index)
            new_offset = self.fat_reader.get_cluster_offset(new_cluster_index)
            f.seek(old_offset)
            data = f.read(self.fat_reader.cluster_size)
            f.seek(new_offset)
            f.write(data)
        print(f"Скопирован кластер {old_cluster_index} в {new_cluster_index}")

    def _write_fat(self) -> None:
        """
        Записывает обновленную таблицу FAT обратно в образ диска.
        """
        with open(self.image_path, 'r+b') as f:
            fat_start = self.bpb.reserved_sec_cnt * self.bpb.byts_per_sec
            fat_size = self.bpb.fat_size_32 * self.bpb.byts_per_sec
            fat_data = bytearray()

            for cluster in self.fat_reader.clusters:
                fat_entry = cluster.next_index & FAT_ENTRY_MASK
                fat_data += struct.pack("<I", fat_entry)

            f.seek(fat_start)
            f.write(fat_data[:fat_size])

        print("FAT таблица обновлена на диске.")
