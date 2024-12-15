from BPM import *
from Cluster import Cluster

class FAT_Reader:
    '''
    Класс для чтения FAT таблицы
    '''
    def __init__(self, image_path : str, bpb : BPB) -> None:
        self.image_path = image_path
        self.bpb = bpb
        self.cluster_size = self.bpb.sec_per_clus * self.bpb.byts_per_sec
        self.clusters = self._read_FAT()

    def _read_FAT(self) -> list[Cluster]:
        '''
        Читает FAT таблицу, разбивая ее на кластеры
        '''
        fat_start = self.bpb.reserved_sec_cnt * self.bpb.byts_per_sec
        fat_size = self.bpb.FAT_size_32 * self.bpb.byts_per_sec
        max_clusters = fat_size // 4
        clusters = []
        with open(self.image_path, 'rb') as image_file:
            image_file.seek(fat_start)
            fat_data = image_file.read(fat_size)
            for i in range(0, len(fat_data), 4):
                cluster_value = struct.unpack("<I", fat_data[i:i + 4])[0] & 0x0FFFFFFF
                if len(clusters) >= max_clusters:
                    break
                is_end = cluster_value >= 0x0FFFFFF8
                clusters.append(Cluster(index=i // 4, next_index=cluster_value, is_end=is_end))
        return clusters

    def get_cluster_chain(self, start_cluster_index : int) -> list[Cluster]:
        '''
        Возвращает цепочку кластеров
        '''
        chain = []
        current_cluster_index = start_cluster_index
        visited = set()
        while 2 <= current_cluster_index < len(self.clusters) and self.clusters[current_cluster_index].is_valid():
            if current_cluster_index in visited:
                print(f"Цикл обнаружен в цепочке кластеров: {current_cluster_index}")
                break
            visited.add(current_cluster_index)
            cluster_obj = self.clusters[current_cluster_index]
            chain.append(cluster_obj)
            if cluster_obj.is_end:
                break
            current_cluster_index = cluster_obj.next_index
        return chain

    def read_cluster_data(self, cluster : Cluster) -> bytes:
        '''
        Читает данные кластера
        '''
        cluster_offset = self.get_cluster_offset(cluster.index)
        with open(self.image_path, 'rb') as image_file:
            image_file.seek(cluster_offset)
            return image_file.read(self.cluster_size)

    def get_cluster_offset(self, cluster_index : int) -> int:
        '''
        Вычисляет смещение кластера в байтах
        '''
        data_region = self.bpb.reserved_sec_cnt + (
                    self.bpb.num_FATs * self.bpb.FAT_size_32)
        cluster_start = data_region * self.bpb.byts_per_sec
        return cluster_start + (cluster_index - 2) * self.cluster_size