import struct
from collections import namedtuple
from enum import IntFlag

class Defragmenter:
    def __init__(self, image_path, fat_reader, directory_parser):
        self.image_path = image_path
        self.fat_reader = fat_reader
        self.directory_parser = directory_parser
        self.bpb = fat_reader.bpb
        self.free_clusters = self._find_free_clusters()

    def _find_free_clusters(self):
        free = []
        for cluster in self.fat_reader.clusters:
            if cluster.next_index == 0:  # В FAT32, 0 означает свободный кластер
                free.append(cluster.index)
        print(f"Найдено {len(free)} свободных кластеров.")
        return free

    def _allocate_clusters(self, num_clusters):
        if len(self.free_clusters) < num_clusters:
            raise Exception("Недостаточно свободных кластеров для дефрагментации.")
        allocated = self.free_clusters[:num_clusters]
        self.free_clusters = self.free_clusters[num_clusters:]
        return allocated

    def _update_FAT(self, old_clusters, new_clusters):
        # Освобождаем старые кластеры
        for cluster in old_clusters:
            self.fat_reader.clusters[cluster].next_index = 0  # Помечаем как свободный

        # Обновляем новые кластеры
        for i in range(len(new_clusters)):
            if i < len(new_clusters) - 1:
                self.fat_reader.clusters[new_clusters[i]].next_index = new_clusters[i + 1]
            else:
                self.fat_reader.clusters[new_clusters[i]].next_index = 0x0FFFFFFF  # Конец цепочки

    def _copy_cluster_data(self, old_cluster, new_cluster):
        with open(self.image_path, 'r+b') as f:
            # Читаем данные из старого кластера
            old_data = self.fat_reader.read_cluster_data(old_cluster)
            # Пишем данные в новый кластер
            f.seek(self.fat_reader.get_cluster_offset(new_cluster))
            f.write(old_data)

    def _update_directory_entry(self, file_entry, new_start_cluster):
        with open(self.image_path, 'r+b') as f:
            # Найти запись каталога и обновить `starting_cluster`
            # Для этого нужно пройтись по всем каталогам и найти соответствующий файл
            # Это упрощенный пример, предполагающий, что у вас есть доступ к записи каталога
            # В реальном случае нужно добавить метод для поиска и обновления записи каталога

            # Пример:
            # f.seek(entry_offset)
            # high, low = new_start_cluster >> 16, new_start_cluster & 0xFFFF
            # f.write(struct.pack("<H", high))
            # f.write(struct.pack("<H", low))
            pass  # Реализуйте этот метод в соответствии с вашей структурой данных

    def defragment(self):
        # Получаем все файлы
        all_files = self.directory_parser.get_all_files(self.bpb.root_clus)

        for file in all_files:
            cluster_chain = self.fat_reader.get_cluster_chain(file["starting_cluster"])
            cluster_indices = [cluster.index for cluster in cluster_chain]

            # Проверяем, является ли файл фрагментированным
            if self.is_fragmented(cluster_chain):
                print(f"Файл '{file['path']}' фрагментирован. Перемещаем...")

                num_clusters = len(cluster_indices)
                new_clusters = self._allocate_clusters(num_clusters)

                # Копируем данные в новые кластеры
                for old, new in zip(cluster_indices, new_clusters):
                    self._copy_cluster_data(old, new)

                # Обновляем FAT таблицы
                old_cluster_objs = [self.fat_reader.clusters[cluster] for cluster in cluster_indices]
                self._update_FAT(old_cluster_objs, new_clusters)

                # Обновляем `starting_cluster` в записи каталога
                self._update_directory_entry(file, new_clusters[0])

                print(f"Файл '{file['path']}' перемещен в кластеры: {new_clusters}")

        # После перемещения всех файлов, необходимо записать обновленную FAT таблицу обратно в образ
        self._write_FAT()

    def _write_FAT(self):
        with open(self.image_path, 'r+b') as f:
            fat_start = self.bpb.reserved_sec_cnt * self.bpb.byts_per_sec
            fat_size = self.bpb.FAT_size_32 * self.bpb.byts_per_sec
            fat_data = bytearray()

            for cluster in self.fat_reader.clusters:
                fat_entry = cluster.next_index & 0x0FFFFFFF
                fat_data += struct.pack("<I", fat_entry)

            # Записываем FAT таблицу
            f.seek(fat_start)
            f.write(fat_data[:fat_size])

        print("FAT таблицы обновлены.")

    def is_fragmented(self, cluster_chain):
        for i in range(len(cluster_chain) - 1):
            if cluster_chain[i].next_index != cluster_chain[i + 1].index:
                return True
        return False