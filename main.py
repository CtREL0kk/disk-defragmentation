import shutil
import argparse
from BPM import BPB
from DirectoryParser import DirectoryParser
from FAT_Reader import FAT_Reader
from Defragmenter import Defragmenter

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument("image_path",type=str)

if __name__ == "__main__":
    args = arg_parser.parse_args()
    image_path = args.image_path
    shutil.copyfile(image_path, f"{image_path}_defragmented")
    image_path = f"{image_path}_defragmented"
    bpb = BPB(image_path)
    fat_reader = FAT_Reader(image_path, bpb)
    parser = DirectoryParser(fat_reader)
    defragmenter = Defragmenter(image_path, fat_reader, parser)
    defragmenter.defragment()