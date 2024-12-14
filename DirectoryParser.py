import struct

from FAT_Attributes import FATAttributes


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
            if (attrs & FATAttributes.LONG_NAME) == FATAttributes.LONG_NAME:
                # Это запись LFN
                seq_num = entry[0] & 0x1F  # Номер последовательности
                is_last = (entry[0] & 0x40) != 0  # Флаг последней записи LFN
                lfn_part = self.parse_lfn_entry(entry)
                lfn_entries.insert(0, lfn_part)  # Добавляем в начало для правильного порядка
                # Добавьте отладочное сообщение
                print(f"LFN Entry: seq_num={seq_num}, is_last={is_last}, name_part='{lfn_part}'")
                continue

            # Это основная запись каталога
            if lfn_entries:
                full_name = ''.join(lfn_entries)
                # Дополнительная фильтрация невалидных символов
                full_name = ''.join(c for c in full_name if c.isprintable())
                print(f"Собранное полное имя файла: '{full_name}'")
                lfn_entries = []  # Очищаем после использования
            else:
                # Используем короткое имя
                name = entry[0:8].decode('ascii', errors='ignore').strip()
                extension = entry[8:11].decode('ascii', errors='ignore').strip()
                full_name = f"{name}.{extension}" if extension else name
                print(f"Собранное короткое имя файла: '{full_name}'")

            # Пропускаем записи '.' и '..'
            if full_name in ('.', '..'):
                continue

            # Читаем starting_cluster и размер файла
            high_bytes = entry[20:22]
            low_bytes = entry[26:28]
            high = struct.unpack("<H", high_bytes)[0]
            low = struct.unpack("<H", low_bytes)[0]
            starting_cluster = (high << 16) | low
            file_size = struct.unpack("<I", entry[28:32])[0]

            # Добавляем отладочную информацию
            print(f"Directory Entry: name='{full_name}', DIR_FstClusHI={high}, DIR_FstClusLO={low}, starting_cluster={starting_cluster}, size={file_size}")
            print(f"Raw DIR_FstClusHI bytes: {high_bytes.hex()}, DIR_FstClusLO bytes: {low_bytes.hex()}")

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

    def update_starting_cluster(self, file_path, new_start_cluster):
        """
        Обновляет поле starting_cluster для указанного файла в каталоге.
        """
        with open(self.fat_reader.image_path, 'r+b') as f:
            # Разделить путь на компоненты
            parts = file_path.split('/')
            current_cluster = self.fat_reader.bpb.root_clus

            # Проход по всем каталогам в пути, кроме последнего (сам файл)
            for part in parts[:-1]:
                # Получить цепочку кластеров для текущего каталога
                cluster_chain = self.fat_reader.get_cluster_chain(current_cluster)
                found = False
                for cluster in cluster_chain:
                    cluster_data = self.fat_reader.read_cluster_data(cluster.index)
                    entries = self.parse_directory_entries(cluster_data)
                    for entry in entries:
                        if entry['name'].lower() == part.lower() and (entry['attributes'] & FATAttributes.DIRECTORY):
                            current_cluster = entry['starting_cluster']
                            found = True
                            print(f"Найден каталог '{part}' с кластером {current_cluster}.")
                            break
                    if found:
                        break
                if not found:
                    print(f"Каталог '{part}' не найден в пути '{file_path}'.")
                    return  # Каталог не найден, прекращаем выполнение

            # Теперь ищем файл в последнем каталоге
            cluster_chain = self.fat_reader.get_cluster_chain(current_cluster)
            for cluster in cluster_chain:
                cluster_data = self.fat_reader.read_cluster_data(cluster)
                entry_size = 32
                lfn_entries = []
                for i in range(0, len(cluster_data), entry_size):
                    entry = cluster_data[i:i + 32]
                    if entry[0] == 0x00:
                        break  # Свободная запись, конец каталога
                    if entry[0] == 0xE5:
                        continue  # Удалённая запись
                    attrs = FATAttributes(entry[11])

                    # Проверка, является ли запись LFN
                    if (attrs & FATAttributes.LONG_NAME) == FATAttributes.LONG_NAME:
                        # Это запись LFN
                        lfn_part = self.parse_lfn_entry(entry)
                        lfn_entries.insert(0, lfn_part)  # Добавляем в начало для правильного порядка
                        continue  # Переходим к следующей записи

                    # Это основная запись каталога
                    if lfn_entries:
                        full_name = ''.join(lfn_entries)
                        # Дополнительная фильтрация невалидных символов
                        full_name = ''.join(c for c in full_name if c.isprintable())
                        lfn_entries = []  # Очищаем после использования
                    else:
                        # Используем короткое имя
                        name = entry[0:8].decode('ascii', errors='ignore').strip()
                        extension = entry[8:11].decode('ascii', errors='ignore').strip()
                        full_name = f"{name}.{extension}" if extension else name

                    if full_name.lower() == parts[-1].lower():
                        # Найдено совпадение имени файла
                        # Вычислить смещение записи каталога в файле
                        cluster_offset = self.fat_reader.get_cluster_offset(cluster.index)
                        entry_offset = cluster_offset + i
                        # Обновить high и low слова
                        high = (new_start_cluster >> 16) & 0xFFFF
                        low = new_start_cluster & 0xFFFF
                        f.seek(entry_offset + 20)
                        f.write(struct.pack("<H", high))
                        f.seek(entry_offset + 26)
                        f.write(struct.pack("<H", low))
                        print(f"Updated starting_cluster for '{file_path}' to {new_start_cluster}.")
                        return  # Завершение после обновления

            print(f"File '{file_path}' not found for updating starting_cluster.")