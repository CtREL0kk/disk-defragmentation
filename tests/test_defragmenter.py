import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from defragmenter.defragmenter import Defragmenter

def test_defragment_no_fragmented_files(mock_fat_reader, mock_directory_parser):
    defragmenter = Defragmenter(Path("Images/FAT_32_32MB"), mock_fat_reader, mock_directory_parser)
    defragmenter.logger = MagicMock()

    mock_directory_parser.get_all_files.return_value = [
        {"path": "DIR1/FILE1.TXT", "starting_cluster": 2, "size": 4096},
    ]
    cluster_chain = [mock_fat_reader.clusters[i] for i in range(2, 7)]
    for i, cluster in enumerate(cluster_chain):
        if i < len(cluster_chain) - 1:
            cluster.next_index = cluster.index + 1
        else:
            cluster.next_index = 0x0FFFFFFF
    defragmenter._copy_cluster_data = MagicMock()
    with patch('defragmenter.defragmenter.ClusterManager._write_fat', side_effect=None):
        defragmenter.defragment()
    defragmenter._copy_cluster_data.assert_not_called()

def test_defragment_with_fragmented_files(mock_fat_reader, mock_directory_parser):
    defragmenter = Defragmenter(Path("Images/FAT_32_32MB"), mock_fat_reader, mock_directory_parser)
    defragmenter.logger = MagicMock()
    mock_directory_parser.get_all_files.return_value = [
        {"path": "DIR1/FILE1.TXT", "starting_cluster": 567, "size": 4096},
    ]
    cluster_chain = [mock_fat_reader.clusters[i] for i in range(2, 7)]
    cluster_chain[2].next_index = 20
    mock_fat_reader.get_cluster_chain = MagicMock()
    mock_fat_reader.get_cluster_chain.return_value = cluster_chain
    defragmenter._copy_cluster_data = MagicMock()
    defragmenter._update_fat = MagicMock()
    defragmenter._update_directory_entry = MagicMock()
    defragmenter._allocate_clusters = MagicMock()
    defragmenter._allocate_clusters.return_value = [i for i in range(500, 505)]

    with patch('defragmenter.defragmenter.ClusterManager._write_fat', side_effect=None):
        defragmenter.defragment()

    defragmenter._copy_cluster_data.assert_called()
    defragmenter._update_fat.assert_called()
    defragmenter._update_directory_entry.assert_called_with(mock_directory_parser.get_all_files.return_value[0],
                                                            defragmenter._allocate_clusters.return_value[0])

def test_defragment_write_fat_failure(mock_fat_reader, mock_directory_parser):
    defragmenter = Defragmenter(Path("Images/FAT_32_32MB"), mock_fat_reader, mock_directory_parser)
    mock_directory_parser.get_all_files.return_value = [
        {"path": "DIR1/FILE1.TXT", "starting_cluster": 2, "size": 4096},
    ]
    cluster_chain = [mock_fat_reader.clusters[i] for i in range(2, 7)]
    cluster_chain[2].next_index = 20
    with pytest.raises(Exception):
        with patch('defragmenter.defragmenter.ClusterManager._write_fat', side_effect=Exception("Write FAT failed")):
            defragmenter.defragment()

def test_find_free_blocks(mock_fat_reader, mock_directory_parser):
    defragmenter = Defragmenter(Path("Images/FAT_32_32MB"), mock_fat_reader, mock_directory_parser)
    defragmenter._free_clusters = MagicMock().return_value = [2, 3, 4, 7, 8, 10, 11, 12, 13]
    assert defragmenter._find_free_blocks() == [[2, 3, 4], [7, 8], [10, 11, 12, 13]]