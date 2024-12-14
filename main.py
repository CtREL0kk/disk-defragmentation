from Structures import *


class DirectoryParser:
    def __init__(self, fat_reader):
        self.fat_reader = fat_reader

    def parse_directory_entries(self, cluster_data):
        entries = []
        entry_size = 32
        lfn_entries = []
        for i in range(0, len(cluster_data), entry_size):
            entry = cluster_data[i:i + entry_size]
            if entry[0] == 0x00:
                break  # Свободная запись, конец каталога
            if entry[0] == 0xE5:
                continue  # Удалённая запись
            attrs = FATAttributes(entry[11])

            # Проверка, является ли запись LFN
            if attrs == (FATAttributes.READ_ONLY | FATAttributes.HIDDEN | FATAttributes.SYSTEM | FATAttributes.VOLUME_ID):
                # Это запись LFN
                seq_num = entry[0] & 0x1F  # Номер последовательности
                is_last = (entry[0] & 0x40) != 0  # Флаг последней записи LFN
                lfn_part = self.parse_lfn_entry(entry)
                lfn_entries.insert(0, lfn_part)  # Добавляем в начало для правильного порядка
                continue

            # Это основная запись каталога
            if lfn_entries:
                full_name = ''.join(lfn_entries)
                lfn_entries = []
            else:
                # Используем короткое имя
                name = entry[0:8].decode('ascii', errors='ignore').strip()
                extension = entry[8:11].decode('ascii', errors='ignore').strip()
                full_name = f"{name}.{extension}" if extension else name

            # Пропускаем записи '.' и '..'
            if full_name in ('.', '..'):
                continue

            # Читаем starting_cluster и размер файла
            high = struct.unpack("<H", entry[20:22])[0]
            low = struct.unpack("<H", entry[26:28])[0]
            starting_cluster = (high << 16) | low
            file_size = struct.unpack("<I", entry[28:32])[0]

            # Добавляем отладочную информацию
            print(f"Entry: name='{full_name}', DIR_FstClusHI={high}, DIR_FstClusLO={low}, starting_cluster={starting_cluster}, size={file_size}")

            # Проверяем корректность starting_cluster
            if starting_cluster < 2 or starting_cluster >= len(self.fat_reader.clusters):
                print(f"Предупреждение: Неверный начальный кластер {starting_cluster} для файла {full_name}")
                continue

            # Добавляем запись
            entries.append({
                "name": full_name,
                "attributes": attrs,
                "starting_cluster": starting_cluster,
                "size": file_size
            })
        return entries

    def parse_lfn_entry(self, entry):
        # Разбираем части длинного имени
        name1 = entry[1:11].decode('utf-16le', errors='ignore').rstrip('\x00').rstrip('\xFF')
        name2 = entry[14:26].decode('utf-16le', errors='ignore').rstrip('\x00').rstrip('\xFF')
        name3 = entry[28:32].decode('utf-16le', errors='ignore').rstrip('\x00').rstrip('\xFF')
        return name1 + name2 + name3

    def get_all_files(self, start_cluster):
        all_files = []

        def traverse(cluster, path):
            print(f"Обрабатываем каталог: {path if path else 'root'} (Кластер: {cluster})")
            cluster_chain = self.fat_reader.get_cluster_chain(cluster)
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

        traverse(start_cluster, "")
        return all_files

class FragmentationChecker:
    def __init__(self, fat_reader):
        self.fat_reader = fat_reader

    def is_fragmented(self, cluster_chain):
        for i in range(len(cluster_chain) - 1):
            if cluster_chain[i].next_index != (cluster_chain[i].index + 1):
                return True
        return False

    def find_fragmented_files(self, files):
        fragmented_files = []
        for file_entry in files:
            cluster_chain = self.fat_reader.get_cluster_chain(file_entry["starting_cluster"])
            for ind in [cluster.index for cluster in cluster_chain]:
                print(ind, end=" ")
            print()
            if self.is_fragmented(cluster_chain):
                fragmented_files.append({
                    "path": file_entry["path"],
                    "cluster_chain": [cluster.index for cluster in cluster_chain]
                })

        return fragmented_files

if __name__ == "__main__":
    image_path = "FAT_32_fragmented"  # Убедитесь, что расширение корректно
    bpb = BPB(image_path)
    print(f"BPB: bytes_per_sec={bpb.byts_per_sec}, sec_per_clus={bpb.sec_per_clus}, reserved_sec_cnt={bpb.reserved_sec_cnt}, num_FATs={bpb.num_FATs}, total_sec_32={bpb.total_sec_32}, FAT_size_32={bpb.FAT_size_32}, root_clus={bpb.root_clus}")
    fat_reader = FATReader(image_path, bpb)
    parser = DirectoryParser(fat_reader)
    checker = FragmentationChecker(fat_reader)

    all_files = parser.get_all_files(bpb.root_clus)
    fragmented_files = checker.find_fragmented_files(all_files)

    print("\nВсе файлы:")
    for file in all_files:
        print(file)

    print("\nФрагментированные файлы:")
    for file in fragmented_files:
        print(file)