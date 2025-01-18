import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from defragmenter.fragmenter import Fragmenter

def test_fragment_file_success(mock_fat_reader, mock_directory_parser):
    fragmenter = Fragmenter(Path("Images/FAT_32_32MB"), mock_fat_reader, mock_directory_parser)
    fragmenter.logger = MagicMock()
    fragmenter._write_fat = MagicMock()
    fragmenter._update_fat = MagicMock()
    fragmenter._update_directory_entry = MagicMock()
    fragmenter._copy_cluster_data = MagicMock()
    fragmenter._free_clusters = MagicMock().return_value = [i for i in range(1000)]

    mock_directory_parser.get_all_files.return_value = [
        {"path": "DIR1/FILE1.TXT", "starting_cluster": 2, "size": 4096}
    ]
    target_file = {"path": "DIR1/FILE1.TXT", "starting_cluster": 2, "size": 4096}
    mock_fat_reader.get_cluster_chain.side_effect = lambda start: mock_fat_reader.clusters[start:start+4]

    with patch('random.randrange', return_value=100):
        fragmenter.fragment_file(Path("DIR1/FILE1.TXT"))

    fragmenter._copy_cluster_data.assert_called()
    fragmenter._update_fat.assert_called()
    fragmenter._update_directory_entry.assert_called_with(target_file, 100)

def test_fragment_file_not_found(mock_fat_reader, mock_directory_parser):
    fragmenter = Fragmenter(Path("Images/FAT_32_32MB"), mock_fat_reader, mock_directory_parser)
    fragmenter.logger = MagicMock()
    mock_directory_parser.get_all_files.return_value = []
    with pytest.raises(FileNotFoundError):
        fragmenter.fragment_file(Path("DIR1/FILE1.TXT"))


def test_fragment_file_small_file(mock_fat_reader, mock_directory_parser):
    fragmenter = Fragmenter(Path("Images/FAT_32_32MB"), mock_fat_reader, mock_directory_parser)
    fragmenter.logger = MagicMock()
    mock_directory_parser.get_all_files.return_value = [
        {"path": "DIR1/SMALL.TXT", "starting_cluster": 2, "size": 512}  # Размер меньше 2 кластеров
    ]
    mock_fat_reader.get_cluster_chain.side_effect = lambda start: mock_fat_reader.clusters[start]
    with pytest.raises(ValueError):
        fragmenter.fragment_file(Path("DIR1/SMALL.TXT"))

def test_fragment_file_copy_failure(mock_fat_reader, mock_directory_parser):
    fragmenter = Fragmenter(Path("Images/FAT_32_32MB"), mock_fat_reader, mock_directory_parser)
    fragmenter.logger = MagicMock()
    fragmenter._copy_cluster_data = MagicMock(side_effect=Exception("Copy failed"))
    mock_directory_parser.get_all_files.return_value = [
        {"path": "DIR1/FILE1.TXT", "starting_cluster": 600, "size": 4096}
    ]
    mock_fat_reader.get_cluster_chain.side_effect = lambda start: mock_fat_reader.clusters[start:start+2]
    with pytest.raises(Exception):
        fragmenter.fragment_file(Path("DIR1/FILE1.TXT"))
