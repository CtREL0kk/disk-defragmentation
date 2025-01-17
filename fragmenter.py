import random
from pathlib import Path

from fat_reader import FatReader
from directory_parser import DirectoryParser
from cluster_manager import ClusterManager

FAT_ENTRY_MASK = 0x0FFFFFFF
FAT_FREE_MASK = 0x00000000


class Fragmenter(ClusterManager):
    """
    Класс для фрагментации файлов в файловой системе FAT32.
    """

    def __init__(self, image_path: Path, fat_reader: FatReader, directory_parser: DirectoryParser) -> None:
        super().__init__(image_path, fat_reader, directory_parser)

    def fragment_file(self, file_path: Path) -> None:
        """
        Фрагментирует указанный файл, разбивая его на несмежные кластеры.
        """
        all_files = self._directory_parser.get_all_files(self._bpb.root_clus)
        target_file = next(f for f in all_files if f["path"] == file_path)

        cluster_chain = self._fat_reader.get_cluster_chain(target_file["starting_cluster"])
        print(cluster_chain)
        cluster_indices = [cluster.index for cluster in cluster_chain]

        if len(cluster_indices) < 2:
            print(f"Файл '{file_path}' слишком мал для фрагментации.")
            return

        print(f"Фрагментируем файл '{file_path}'")

        new_clusters = []
        for old_cluster_index in cluster_indices:
            if not self._free_clusters:
                print("Нет свободных кластеров для фрагментации.")
                break
            index = random.randrange(len(self._free_clusters))
            new_cluster = self._free_clusters.pop(index)
            self._copy_cluster_data(old_cluster_index, new_cluster)
            new_clusters.append(new_cluster)

        self._update_directory_entry(target_file, new_clusters[0])
        self._update_fat(cluster_indices, new_clusters)
        self._write_fat()
        print(f"Файл '{file_path}' успешно фрагментирован.")
