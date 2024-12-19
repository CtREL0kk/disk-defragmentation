import struct

from cluster import Cluster
from directory_parser import DirectoryParser
from fat_reader import FatReader

FAT_END_MASK = 0x0FFFFFF8
FAT_ENTRY_MASK = 0x0FFFFFFF
FAT_FREE_MASK = 0x00000000

class Defragmenter:
    """
    Класс для дефрагментации файловой системы FAT32.
    """
    def __init__(self, image_path: str, fat_reader: FatReader, directory_parser: DirectoryParser) -> None:
        self.image_path = image_path
        self.fat_reader = fat_reader
        self.directory_parser = directory_parser
        self.bpb = fat_reader.bpb
        self.free_clusters: list[int] = self._find_free_clusters()

    def is_fragmented(self, cluster_chain: list[Cluster]) -> bool:
        """
        Проверяет, является ли кластерная цепочка фрагментированной.
        """
        for i in range(len(cluster_chain) - 1):
            if cluster_chain[i].next_index != (cluster_chain[i].index + 1):
                return True
        return False

    def defragment(self) -> None:
        """
        Основной метод для дефрагментации файловой системы.
        """
        all_files = self.directory_parser.get_all_files(self.bpb.root_clus)

        for file in all_files:
            cluster_chain = self.fat_reader.get_cluster_chain(file["starting_cluster"])
            cluster_indices = [cluster.index for cluster in cluster_chain]

            if self.is_fragmented(cluster_chain):
                print(f"Файл '{file['path']}' фрагментирован {cluster_indices}. Перемещаем...")

                clusters_count = len(cluster_indices)
                new_clusters_indices = self._allocate_clusters(clusters_count)

                for old, new in zip(cluster_indices, new_clusters_indices):
                    self._copy_cluster_data(old, new)

                self._update_fat(cluster_indices, new_clusters_indices)
                self._update_directory_entry(file, new_clusters_indices[0])

                print(f"Файл '{file['path']}' перемещен в кластеры: {new_clusters_indices}")

        self._write_fat()
        print("Дефрагментация завершена успешно.")

    def _find_free_clusters(self):
        """
        Находит все свободные кластеры.
        """
        free = [cluster.index for cluster in self.fat_reader.clusters if cluster.next_index == FAT_FREE_MASK]
        return free

    def _find_free_blocks(self) -> list[list[int]]:
        """
        Находит все непрерывные блоки свободных кластеров.
        """
        free_sorted = sorted(self.free_clusters)
        blocks: list[list[int]] = []
        current_block: list[int] = []

        for cluster in free_sorted:
            if not current_block:
                current_block = [cluster]
            elif cluster == current_block[-1] + 1:
                current_block.append(cluster)
            else:
                blocks.append(current_block)
                current_block = [cluster]
        if current_block:
            blocks.append(current_block)

        return blocks

    def _find_best_fit_free_clusters(self, clusters_count: int) -> list[int]:
        """
        Находит наиболее подходящий блок свободных кластеров (Best-Fit) для размещения файла.
        """
        free_blocks = self._find_free_blocks()
        best_fit = None
        min_overflow = None

        for block in free_blocks:
            if len(block) >= clusters_count:
                overflow = len(block) - clusters_count
                if (min_overflow is None) or (overflow < min_overflow):
                    best_fit = block[:clusters_count]
                    min_overflow = overflow
                if overflow == 0:
                    break  # Наилучший возможный вариант
        if best_fit:
            print(f"Best-Fit найден: {best_fit} с переполнением {min_overflow}")
            return best_fit
        else:
            raise Exception("Не удалось найти подходящий блок свободных кластеров.")

    def _allocate_clusters(self, clusters_count: int) -> list[int]:
        """
        Выделяет свободные кластеры для файла, используя алгоритм Best-Fit.
        """
        new_clusters = self._find_best_fit_free_clusters(clusters_count)
        # Удаляем выделенные кластеры из списка свободных
        for cluster in new_clusters:
            self.free_clusters.remove(cluster)
        return new_clusters

    def _copy_cluster_data(self, old_cluster_index: int, new_cluster_index: int) -> None:
        """
        Копирует данные из одного кластера в другой
        """
        with open(self.image_path, 'r+b') as f:
            old_data = self.fat_reader.read_cluster_data(self.fat_reader.clusters[old_cluster_index])
            f.seek(self.fat_reader.get_cluster_offset(new_cluster_index))
            f.write(old_data)

    def _update_fat(self, old_clusters_indices: list[int], new_clusters_indices: list[int]) -> None:
        """
        Обновляет FAT таблицу: освобождает старые кластеры и связывает новые кластеры.
        """
        for cluster in old_clusters_indices:
            self.fat_reader.clusters[cluster].next_index = FAT_FREE_MASK

        for i in range(len(new_clusters_indices)):
            current_cluster = new_clusters_indices[i]
            if i < len(new_clusters_indices) - 1:
                self.fat_reader.clusters[current_cluster].next_index = new_clusters_indices[i + 1]
            else:
                self.fat_reader.clusters[current_cluster].next_index = FAT_ENTRY_MASK
        print(f"FAT таблица обновлена для новых кластеров: {new_clusters_indices}")

    def _update_directory_entry(self, file_entry: dict, new_start_cluster_index: int) -> None:
        """
        Обновляет поле starting_cluster для файла в каталоге.
        """
        self.directory_parser.update_starting_cluster(file_entry['path'], new_start_cluster_index)

    def _write_fat(self) -> None:
        """
        Записывает обновлённую FAT таблицу обратно в образ диска.
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

        print("FAT таблицы обновлены.")
