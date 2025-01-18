import shutil
import argparse
from pathlib import Path

from defragmenter.bpb import BPB
from defragmenter.directory_parser import DirectoryParser
from defragmenter.fat_reader import FatReader
from defragmenter.defragmenter import Defragmenter
from defragmenter.fragmenter import Fragmenter
from defragmenter.cluster_manager import ClusterManager

arg_parser = argparse.ArgumentParser()
subparsers = arg_parser.add_subparsers(dest='command', help='Доступные команды', required=True)

defrag_parser = subparsers.add_parser('defragment')
defrag_parser.add_argument("image_path", type=str, help="Путь к образу файловой системы FAT32")

frag_parser = subparsers.add_parser('fragment')
frag_parser.add_argument("image_path", type=str, help="Путь к образу файловой системы FAT32")
frag_parser.add_argument("file_path", type=str, help="Путь к файлу для фрагментации")

check_parser = subparsers.add_parser('check', help="Просмотреть фрагментированные файлы")
check_parser.add_argument("image_path", type=str, help="Путь к образу файловой системы FAT32")


if __name__ == "__main__":
    args = arg_parser.parse_args()
    command = args.command

    image_path = Path(args.image_path)
    final_image_path = image_path.with_name(f"{image_path.name}_{command}ed")

    if command == "check":
        final_image_path = image_path
    else:
        shutil.copyfile(image_path, final_image_path)

    bpb = BPB(final_image_path)
    fat_reader = FatReader(final_image_path, bpb)
    parser = DirectoryParser(fat_reader)

    if command == "check":
        all_files = parser.get_all_files(bpb.root_clus)
        fragmented_files = ClusterManager(image_path, fat_reader, parser).find_fragmented_files(all_files)
        print("\nВсе файлы:")
        for file in all_files:
            print(f"path: {file['path']}, starting_cluster: {file['starting_cluster']}, size: {file['size']}")

        print("\nФрагментированные файлы:")
        for file in fragmented_files:
            print(f"path: {file['path']}, cluster_chain: {file['cluster_chain']}")

    elif command == "defragment":
        defragmenter = Defragmenter(final_image_path, fat_reader, parser)
        defragmenter.defragment()

    elif command == "fragment":
        file_path = Path(args.file_path)
        fragmenter = Fragmenter(final_image_path, fat_reader, parser)
        fragmenter.fragment_file(Path(args.file_path))
