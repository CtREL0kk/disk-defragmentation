import struct
from FAT_Attributes import FATAttributes
from FAT_Reader import FAT_Reader


class DirectoryParser:
    '''
    Класс для парсинга каталога
    '''
    def __init__(self, fat_reader : FAT_Reader) -> None:
        self.fat_reader = fat_reader

    def parse_directory_entries(self, cluster_data : bytes) -> list[dict]:
        entries = []
        entry_size = 32
        lfn_entries = []
        for i in range(0, len(cluster_data), entry_size):
            entry = cluster_data[i:i + entry_size]
            if entry[0] == 0x00:
                break
            if entry[0] == 0xE5:
                continue

            parsed_entry = self.parse_single_entry(entry, lfn_entries)
            if parsed_entry is None:
                continue

            full_name, attrs, starting_cluster, file_size = parsed_entry
            if full_name in ('.', '..'):
                lfn_entries = []
                continue

            if starting_cluster < 2 or starting_cluster >= len(self.fat_reader.clusters):
                print(f"Предупреждение: Неверный начальный кластер {starting_cluster} для файла {full_name}")
                lfn_entries = []
                continue

            entries.append({
                "name": full_name,
                "attributes": attrs,
                "starting_cluster": starting_cluster,
                "size": file_size
            })
            lfn_entries = []
        return entries

    def parse_single_entry(self, entry: bytes, lfn_entries: list[str]) -> tuple[str, FATAttributes, int, int] | None:
        '''
        Разбор одной записи (32 байта). Возвращает кортеж (full_name, attrs, starting_cluster, file_size) или None,
        если запись обрабатывать не нужно (например, LFN-части).
        '''
        attrs = FATAttributes(entry[11])
        if (attrs & FATAttributes.LONG_NAME) == FATAttributes.LONG_NAME:
            lfn_part = self.parse_lfn_entry(entry)
            lfn_entries.insert(0, lfn_part)
            return None

        if lfn_entries:
            full_name = ''.join(lfn_entries)
            full_name = ''.join(c for c in full_name if c.isprintable())
        else:
            name = entry[0:8].decode('ascii', errors='ignore').strip()
            extension = entry[8:11].decode('ascii', errors='ignore').strip()
            full_name = f"{name}.{extension}" if extension else name

        high_bytes = entry[20:22]
        low_bytes = entry[26:28]
        high = struct.unpack("<H", high_bytes)[0]
        low = struct.unpack("<H", low_bytes)[0]
        starting_cluster = (high << 16) | low
        file_size = struct.unpack("<I", entry[28:32])[0]

        return (full_name, attrs, starting_cluster, file_size)

    def parse_lfn_entry(self, entry : bytes) -> str:
        '''
        Разбираем части длинного имени
        '''
        name1 = entry[1:11].decode('utf-16le', errors='ignore').rstrip('\x00').rstrip('\xFF')
        name2 = entry[14:26].decode('utf-16le', errors='ignore').rstrip('\x00').rstrip('\xFF')
        name3 = entry[28:32].decode('utf-16le', errors='ignore').rstrip('\x00').rstrip('\xFF')
        return name1 + name2 + name3

    def get_all_files(self, start_cluster_index : int) -> list[dict]:
        all_files = []

        def traverse(cluster_index, path):
            print(f"Обрабатываем каталог: {path if path else 'root'} (Кластер: {cluster_index})")
            cluster_chain = self.fat_reader.get_cluster_chain(cluster_index)
            for cluster_obj in cluster_chain:
                cluster_data = self.fat_reader.read_cluster_data(cluster_obj)
                entries = self.parse_directory_entries(cluster_data)
                for entry in entries:
                    file_path = f"{path}/{entry['name']}" if path else entry['name']
                    print(f"Найдено: {file_path} (Атрибуты: {entry['attributes']})")
                    if entry['name'] in ('.', '..'):
                        continue
                    if (entry["attributes"] & FATAttributes.DIRECTORY) and entry["starting_cluster"] != 0:
                        traverse(entry["starting_cluster"], file_path)
                    elif entry["starting_cluster"] != 0:
                        all_files.append({
                            "path": file_path,
                            "starting_cluster": entry["starting_cluster"],
                            "size": entry["size"]
                        })

        traverse(start_cluster_index, "")
        return all_files

    def find_directory_entry(self, dir_cluster_index: int, target_name: str) -> tuple[int, int] | None:
        '''
        Ищет запись файла или каталога в заданном кластере. Возвращает смещение записи и индекс кластера,
        в котором она найдена.
        '''
        cluster_chain = self.fat_reader.get_cluster_chain(dir_cluster_index)
        entry_size = 32

        for cluster in cluster_chain:
            cluster_data = self.fat_reader.read_cluster_data(cluster)
            lfn_entries = []
            for i in range(0, len(cluster_data), entry_size):
                entry = cluster_data[i:i + entry_size]
                if entry[0] == 0x00:
                    break
                if entry[0] == 0xE5:
                    continue

                attrs = FATAttributes(entry[11])
                if (attrs & FATAttributes.LONG_NAME) == FATAttributes.LONG_NAME:
                    lfn_part = self.parse_lfn_entry(entry)
                    lfn_entries.insert(0, lfn_part)
                    continue

                if lfn_entries:
                    full_name = ''.join(lfn_entries)
                    full_name = ''.join(c for c in full_name if c.isprintable())
                    lfn_entries = []
                else:
                    name = entry[0:8].decode('ascii', errors='ignore').strip()
                    extension = entry[8:11].decode('ascii', errors='ignore').strip()
                    full_name = f"{name}.{extension}" if extension else name

                if full_name.lower() == target_name.lower():
                    cluster_offset = self.fat_reader.get_cluster_offset(cluster.index)
                    entry_offset = cluster_offset + i
                    return entry_offset, cluster.index

        return None

    def navigate_path(self, path_parts: list[str]) -> int | None:
        '''
        Переходит по пути, возвращая кластер каталога, в котором находится последний элемент.
        '''
        current_cluster = self.fat_reader.bpb.root_clus
        for part in path_parts[:-1]:
            found_cluster = self.find_subdirectory_cluster(current_cluster, part)
            if found_cluster is None:
                print(f"Каталог '{part}' не найден.")
                return None
            current_cluster = found_cluster
        return current_cluster

    def find_subdirectory_cluster(self, dir_cluster_index: int, subdir_name: str) -> int | None:
        '''
        Ищет подкаталог subdir_name в заданном каталоге, возвращает кластер этого подкаталога
        '''
        cluster_chain = self.fat_reader.get_cluster_chain(dir_cluster_index)

        for cluster in cluster_chain:
            cluster_data = self.fat_reader.read_cluster_data(cluster)
            entries = self.parse_directory_entries(cluster_data)
            for entry in entries:
                if entry["name"].lower() == subdir_name.lower() and (entry["attributes"] & FATAttributes.DIRECTORY):
                    return entry["starting_cluster"]
        return None

    def update_starting_cluster(self, file_path : str, new_start_cluster_index : int) -> None:
        """
        Обновляет поле starting_cluster для указанного файла в каталоге.
        """
        with open(self.fat_reader.image_path, 'r+b') as f:
            parts = file_path.split('/')
            current_cluster = self.navigate_path(parts)
            if current_cluster is None:
                return

            result = self.find_directory_entry(current_cluster, parts[-1])
            if result is None:
                print(f"Файл '{file_path}' не найден для обновления starting_cluster.")
                return

            entry_offset, cluster_index = result
            high = (new_start_cluster_index >> 16) & 0xFFFF
            low = new_start_cluster_index & 0xFFFF
            f.seek(entry_offset + 20)
            f.write(struct.pack("<H", high))
            f.seek(entry_offset + 26)
            f.write(struct.pack("<H", low))
            print(f"Updated starting_cluster for '{file_path}' to {new_start_cluster_index}.")