import shutil
from BPM import BPB
from DirectoryParser import DirectoryParser
from FAT_Reader import FAT_Reader
from Defragmenter import Defragmenter

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
    image_path = "FAT_32_fragmented_2_defragmented" # Убедитесь, что расширение корректно
    # shutil.copyfile(image_path, f"{image_path}_defragmented")
    # image_path = f"{image_path}_defragmented"
    bpb = BPB(image_path)
    print(f"BPB: bytes_per_sec={bpb.byts_per_sec}, sec_per_clus={bpb.sec_per_clus}, reserved_sec_cnt={bpb.reserved_sec_cnt}, num_FATs={bpb.num_FATs}, total_sec_32={bpb.total_sec_32}, FAT_size_32={bpb.FAT_size_32}, root_clus={bpb.root_clus}")
    fat_reader = FAT_Reader(image_path, bpb)
    parser = DirectoryParser(fat_reader)
    checker = FragmentationChecker(fat_reader)
    # defragment = Defragmenter(image_path,fat_reader,parser)

    all_files = parser.get_all_files(bpb.root_clus)
    fragmented_files = checker.find_fragmented_files(all_files)

    print("\nВсе файлы:")
    for file in all_files:
        print(file)

    print("\nФрагментированные файлы:")
    for file in fragmented_files:
        print(file)
    # defragment.defragment()