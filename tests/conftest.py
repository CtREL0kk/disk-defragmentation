import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_fat_reader():
    fat_reader = MagicMock()
    fat_reader.bpb = MagicMock()
    fat_reader.bpb.reserved_sec_cnt = 32
    fat_reader.bpb.byts_per_sec = 512
    fat_reader.bpb.fat_size_32 = 256
    fat_reader.bpb.root_clus = 2
    fat_reader.bpb.sec_per_clus = 8
    fat_reader.bpb.total_sec_32 = 100000
    fat_reader.cluster_size = 4096
    fat_reader.clusters = []
    for _ in range(1000):
        fat_reader.clusters.append(MagicMock())
    for i, cluster in enumerate(fat_reader.clusters):
        cluster.index = i
        cluster.next_index = i + 1 if i <= 500 else i + 2 if i < 998 else 0x0FFFFFFF
    fat_reader.get_cluster_offset.side_effect = lambda x: x * fat_reader.cluster_size
    #fat_reader.read_cluster_data.side_effect = lambda cluster: b'Data' * 1024
    fat_reader.write_fat.return_value = None
    return fat_reader

@pytest.fixture
def mock_directory_parser():
    directory_parser = MagicMock()
    directory_parser.get_all_files.return_value = [
        {"path": "DIR1/FILE1.TXT", "starting_cluster": 2, "size": 2048},
        {"path": "DIR2/FILE2.TXT", "starting_cluster": 10, "size": 4096},
    ]
    directory_parser.update_starting_cluster.return_value = None
    return directory_parser
