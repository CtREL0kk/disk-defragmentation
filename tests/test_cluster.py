from defragmenter.cluster import Cluster

def test_is_valid():
    valid_index_cluster = Cluster(100, 101, False)
    assert valid_index_cluster.is_valid()
    invalid_index_cluster = Cluster(1, 2, False)
    assert not invalid_index_cluster.is_valid()
