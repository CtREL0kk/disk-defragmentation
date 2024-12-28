import shutil
import argparse
from pathlib import Path

from bpb import BPB
from directory_parser import DirectoryParser
from fat_reader import FatReader
from defragmenter import Defragmenter

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument("image_path", type=str)

if __name__ == "__main__":
    args = arg_parser.parse_args()
    image_path = Path(args.image_path)
    final_image_path = image_path.with_name(f"{image_path.name}_defragmented")

    shutil.copyfile(image_path, final_image_path)
    bpb = BPB(final_image_path)
    fat_reader = FatReader(final_image_path, bpb)
    parser = DirectoryParser(fat_reader)
    defragmenter = Defragmenter(image_path, fat_reader, parser)
    defragmenter.defragment()
