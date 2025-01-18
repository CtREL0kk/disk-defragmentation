from pathlib import Path

from defragmenter.bpb import BPB

def test_init():
    project_root = Path(__file__).resolve().parent.parent
    image_path = project_root / "Images" / "FAT_32_32MB"
    assert image_path.exists(), f"Файл {image_path} не найден."
    bpb = BPB(image_path)
    assert bpb.root_clus == 2
    assert bpb.byts_per_sec == 512
    assert bpb.num_fats == 2
    assert bpb.reserved_sec_cnt == 2782
    assert bpb.total_sec_32 == 65536
    assert bpb.fat_size_32 == 14993
    assert bpb.sec_per_clus == 32