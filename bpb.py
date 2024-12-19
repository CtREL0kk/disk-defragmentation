import struct

class BPB:
    def __init__(self, image_path: str) -> None:
        """
        Класс для чтения BPB
        """
        with open(image_path, 'rb') as image_file:
            first_sector = image_file.read(512)
            self.byts_per_sec = struct.unpack("<H", first_sector[11:13])[0]
            self.sec_per_clus = struct.unpack("<B", first_sector[13:14])[0]
            self.reserved_sec_cnt = struct.unpack("<H", first_sector[14:16])[0]
            self.num_fats = struct.unpack("<B", first_sector[16:17])[0]
            self.total_sec_32 = struct.unpack("<I", first_sector[32:36])[0]
            self.fat_size_32 = struct.unpack("<I", first_sector[36:40])[0]
            self.root_clus = struct.unpack("<I", first_sector[44:48])[0]
