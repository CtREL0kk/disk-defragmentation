import hashlib
import struct

class Defragmenter:
    """
    Класс для дефрагментации файловой системы FAT32.
    """
    def __init__(self, image_path, fat_reader, directory_parser):
        self.image_path = image_path
        self.fat_reader = fat_reader
        self.directory_parser = directory_parser
        self.bpb = fat_reader.bpb
        self.free_clusters = self._find_free_clusters()

    def is_fragmented(self, cluster_chain):
        for i in range(len(cluster_chain) - 1):
            if cluster_chain[i].next_index != (cluster_chain[i].index + 1):
                return True
        return False

    def _find_free_clusters(self):
        """
        Находит все свободные кластеры.
        """
        free = []
        for cluster in self.fat_reader.clusters:
            if cluster.next_index == 0:  # В FAT32, 0 означает свободный кластер
                free.append(cluster.index)
        print(f"Найдено {len(free)} свободных кластеров.")
        return free

    def _find_free_blocks(self):
        """
        Находит все непрерывные блоки свободных кластеров.
        """
        free_sorted = sorted(self.free_clusters)
        blocks = []
        current_block = []

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
        print(f"Найдено {len(blocks)} свободных блоков кластеров.")
        return blocks

    def _find_best_fit_free_clusters(self, num_clusters):
        """
        Находит наиболее подходящий блок свободных кластеров (Best-Fit) для размещения файла.
        """
        free_blocks = self._find_free_blocks()
        best_fit = None
        min_overflow = None

        for block in free_blocks:
            if len(block) >= num_clusters:
                overflow = len(block) - num_clusters
                if (min_overflow is None) or (overflow < min_overflow):
                    best_fit = block[:num_clusters]
                    min_overflow = overflow
                if overflow == 0:
                    break  # Наилучший возможный вариант
        if best_fit:
            print(f"Best-Fit найден: {best_fit} с переполнением {min_overflow}")
            return best_fit
        else:
            raise Exception("Не удалось найти подходящий блок свободных кластеров.")

    def _allocate_clusters(self, num_clusters):
        """
        Выделяет свободные кластеры для файла, используя алгоритм Best-Fit.
        """
        new_clusters = self._find_best_fit_free_clusters(num_clusters)
        # Удаляем выделенные кластеры из списка свободных
        for cluster in new_clusters:
            self.free_clusters.remove(cluster)
        return new_clusters

    def _copy_cluster_data(self, old_cluster, new_cluster):
        """
        Копирует данные из одного кластера в другой и проверяет целостность.
        """
        with open(self.image_path, 'r+b') as f:
            # Читаем данные из старого кластера
            old_data = self.fat_reader.read_cluster_data(self.fat_reader.clusters[old_cluster])
            # Читаем данные из нового кластера для сравнения (до записи)
            f.seek(self.fat_reader.get_cluster_offset(new_cluster))
            new_data_before = f.read(len(old_data))
            # Пишем данные в новый кластер
            f.seek(self.fat_reader.get_cluster_offset(new_cluster))
            f.write(old_data)
            # Читаем данные после записи для проверки
            f.seek(self.fat_reader.get_cluster_offset(new_cluster))
            new_data_after = f.read(len(old_data))

        # Сравниваем хеш-суммы
        if self.calculate_md5(old_data) != self.calculate_md5(new_data_after):
            print(f"Ошибка копирования данных: Кластер {old_cluster} не совпадает с {new_cluster}.")
            raise Exception(f"Ошибка копирования данных: Кластер {old_cluster} не совпадает с {new_cluster}.")
        else:
            print(f"Данные из кластера {old_cluster} успешно скопированы в {new_cluster}.")

    @staticmethod
    def calculate_md5(data):
        """
        Вычисляет MD5-хеш данных.
        """
        hash_md5 = hashlib.md5()
        hash_md5.update(data)
        return hash_md5.hexdigest()

    def _update_FAT(self, old_clusters, new_clusters):
        """
        Обновляет FAT таблицу: освобождает старые кластеры и связывает новые кластеры.
        """
        # Освобождаем старые кластеры
        for cluster in old_clusters:
            self.fat_reader.clusters[cluster.index].next_index = 0  # Помечаем как свободный

        # Обновляем новые кластеры
        for i in range(len(new_clusters)):
            current_cluster = new_clusters[i]
            if i < len(new_clusters) - 1:
                self.fat_reader.clusters[current_cluster].next_index = new_clusters[i + 1]
            else:
                self.fat_reader.clusters[current_cluster].next_index = 0x0FFFFFFF  # Конец цепочки
        print(f"FAT таблица обновлена для новых кластеров: {new_clusters}")

    def _update_directory_entry(self, file_entry, new_start_cluster):
        """
        Обновляет поле starting_cluster для файла в каталоге.
        """
        self.directory_parser.update_starting_cluster(file_entry['path'], new_start_cluster)

    def defragment(self):
        """
        Основной метод для дефрагментации файловой системы.
        """

        # Получаем все файлы
        all_files = self.directory_parser.get_all_files(self.bpb.root_clus)
        # Сортируем файлы по размеру (от большего к меньшему)
        all_files_sorted = sorted(all_files, key=lambda x: x['size'], reverse=True)
        fragmented_files = [file for file in all_files_sorted if self.is_fragmented(self.fat_reader.get_cluster_chain(file["starting_cluster"]))]

        print(f"Найдено {len(fragmented_files)} фрагментированных файлов для дефрагментации.")

        for file in fragmented_files:
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
        print("Дефрагментация завершена успешно.")

    def _write_FAT(self):
        """
        Записывает обновлённую FAT таблицу обратно в образ диска.
        """
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