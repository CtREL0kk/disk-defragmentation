from pathlib import Path

from cluster_manager import ClusterManager
from directory_parser import DirectoryParser
from fat_reader import FatReader

FAT_ENTRY_MASK = 0x0FFFFFFF
FAT_FREE_MASK = 0x00000000

ClusterIndexList = list[int]

class Defragmenter(ClusterManager):
    """
    Класс для дефрагментации файловой системы FAT32.
    """
    def __init__(self, image_path: Path, fat_reader: FatReader, directory_parser: DirectoryParser) -> None:
        super().__init__(image_path, fat_reader, directory_parser)

    def defragment(self) -> None:
        """
        Основной метод для дефрагментации файловой системы.
        """
        all_files = self._directory_parser.get_all_files(self._bpb.root_clus)

        for file in all_files:
            cluster_chain = self._fat_reader.get_cluster_chain(file["starting_cluster"])
            cluster_indices = [cluster.index for cluster in cluster_chain]

            if self._is_fragmented(cluster_chain):
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

    def _find_free_blocks(self) -> list[ClusterIndexList]:
        """
        Находит все непрерывные блоки свободных кластеров.
        """
        free_sorted = sorted(self._free_clusters)
        blocks: list[ClusterIndexList] = []
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
        raise Exception("Не удалось найти подходящий блок свободных кластеров.")

    def _allocate_clusters(self, clusters_count: int) -> list[int]:
        """
        Выделяет свободные кластеры для файла, используя алгоритм Best-Fit.
        """
        new_clusters = self._find_best_fit_free_clusters(clusters_count)
        # Удаляем выделенные кластеры из списка свободных
        for cluster in new_clusters:
            self._free_clusters.remove(cluster)
        return new_clusters


