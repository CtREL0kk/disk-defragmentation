from pathlib import Path

import pytest

from defragmenter.fat_reader import FatReader
from defragmenter.directory_parser import DirectoryParser
from defragmenter.bpb import BPB


@pytest.fixture
def directory_parser():
    project_root = Path(__file__).resolve().parent.parent
    image_path = project_root / "Images" / "FAT_32_32MB"
    assert image_path.exists(), f"Файл {image_path} не найден."
    fat_reader = FatReader(image_path, BPB(image_path))
    return DirectoryParser(fat_reader)

def test_init(directory_parser):
    assert directory_parser is not None


def test_parse_directory_entries(directory_parser):
    first_cluster = directory_parser.fat_reader.clusters[directory_parser.fat_reader.bpb.root_clus]
    cluster_data = directory_parser.fat_reader.read_cluster_data(first_cluster)

    entries = directory_parser.parse_directory_entries(cluster_data)

    assert isinstance(entries, list)

    expected_file = {
        'attributes': 32,
        'name': 'ASDA.TXT',
        'size': 1644,
        'starting_cluster': 6
    }

    assert expected_file in entries, f"{expected_file} не найден в записях каталога."


def test_get_all_files(directory_parser):
    all_files = directory_parser.get_all_files(directory_parser.fat_reader.bpb.root_clus)
    assert isinstance(all_files, list)
    expected_files = [
        {
            'path': 'ASDA.TXT',
            'size': 1644,
            'starting_cluster': 6
        },
        {
            'path': 'PortScan/Parser.py',
            'size': 2986,
            'starting_cluster': 9
        },
        {
            'path': 'PortScan/__pycache__/TCP_Scanner.cpython-311.pyc',
            'starting_cluster': 25,
            'size': 8589
        }
    ]

    for file in expected_files:
        assert file in all_files, f"Файл {file} не найден в списке всех файлов."


def test_find_directory_entry_existing_file(directory_parser):
    target_name = "ASDA.TXT"
    root_cluster = directory_parser.fat_reader.bpb.root_clus
    result = directory_parser.find_directory_entry(root_cluster, target_name)
    assert result is not None, f"Запись для {target_name} не найдена."
    entry_offset, cluster_index = result
    assert isinstance(entry_offset, int)
    assert isinstance(cluster_index, int)

def test_find_directory_entry_nonexistent_file(directory_parser):
    target_name = "NONEXISTENT.TXT"
    root_cluster = directory_parser.fat_reader.bpb.root_clus
    result = directory_parser.find_directory_entry(root_cluster, target_name)
    assert result is None, f"Запись для {target_name} должна отсутствовать."

def test_navigate_path_valid_path(directory_parser):
    path = ['PortScan', '__pycache__', 'TCP_Scanner.cpython-311.pyc']
    path_parts = path
    result = directory_parser.navigate_path(path_parts)
    assert isinstance(result, int)
    assert result >= 2

def test_navigate_path_invalid_path(directory_parser):
    path = ["nonexistent_dir", "file.txt"]
    path_parts = path
    result = directory_parser.navigate_path(path_parts)
    assert result is None, "Путь должен отсутствовать."

def test_find_subdirectory_cluster_existing(directory_parser):
    subdir_name = "PortScan"
    root_cluster = directory_parser.fat_reader.bpb.root_clus
    result = directory_parser.find_subdirectory_cluster(root_cluster, subdir_name)
    assert isinstance(result, int), "Кластер подкаталога должен быть целым числом."
    assert result >= 2, "Кластер должен быть валидным (>=2)."

def test_find_subdirectory_cluster_nonexistent(directory_parser):
    subdir_name = "ghost_dir"
    root_cluster = directory_parser.fat_reader.bpb.root_clus
    result = directory_parser.find_subdirectory_cluster(root_cluster, subdir_name)
    assert result is None, "Кластер подкаталога не должен существовать."
