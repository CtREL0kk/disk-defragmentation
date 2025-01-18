from pathlib import Path

from defragmenter.bpb import BPB
from defragmenter.cluster_manager import ClusterManager
from defragmenter.directory_parser import DirectoryParser
from defragmenter.fat_reader import FatReader


def test_is_fragmented_not_fragmented(mock_fat_reader, mock_directory_parser):
    manager = ClusterManager(Path("Images/FAT_32_32MB"), mock_fat_reader, mock_directory_parser)
    cluster_chain = [mock_fat_reader.clusters[i] for i in range(2, 7)]
    for i, cluster in enumerate(cluster_chain):
        if i < len(cluster_chain) - 1:
            cluster.next_index = cluster.index + 1
        else:
            cluster.next_index = 0x0FFFFFFF
    assert not manager._is_fragmented(cluster_chain)

def test_is_fragmented_fragmented(mock_fat_reader, mock_directory_parser):
    manager = ClusterManager(Path("Images/FAT_32_32MB"), mock_fat_reader, mock_directory_parser)
    cluster_chain = [mock_fat_reader.clusters[i] for i in range(2, 7)]
    cluster_chain[2].next_index = 20
    assert manager._is_fragmented(cluster_chain)

def test_update_directory_entry_success(mock_fat_reader, mock_directory_parser):
    manager = ClusterManager(Path("Images/FAT_32_32MB"), mock_fat_reader, mock_directory_parser)
    file_entry = {"path": "DIR1/FILE1.TXT"}
    manager._update_directory_entry(file_entry, 5)
    mock_directory_parser.update_starting_cluster.assert_called_with("DIR1/FILE1.TXT", 5)

def test_find_fragmented_files():
    project_root = Path(__file__).resolve().parent.parent
    image_path = project_root / "Images" / "FAT_32_fragmented"
    bpb = BPB(image_path)
    fat_reader = FatReader(image_path, bpb)
    directory_parser = DirectoryParser(fat_reader)
    all_files = directory_parser.get_all_files(bpb.root_clus)
    manager = ClusterManager(image_path, fat_reader, directory_parser)
    fragmented_files = manager.find_fragmented_files(all_files)
    expected_fragmented_files = [
        {
            'path': 'ASDA.TXT',
            'cluster_chain': [6, 1552, 1553, 1554, 1555, 1556]
        },
        {
            'path': 'ipset-discord.txt',
            'cluster_chain': [1337, 1557, 1558, 1559, 1560, 1561]
        },
        {
            'path': 'list-discord.txt',
            'cluster_chain': [1546, 1742]
        }
    ]
    assert expected_fragmented_files == fragmented_files
