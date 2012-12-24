import binascii
import mmap
import contextlib
from BinaryParser import *
import BinaryParser

class FileHeader(Block):
    def __init__(self, buf, offset):
        debug("FILE HEADER at %s." % (hex(offset)))
        super(FileHeader, self).__init__(buf, offset)
        self.declare_field("string", "magic", 0x0, 8)
        self.declare_field("qword",  "unused0")
        self.declare_field("qword",  "current_chunk_number")
        self.declare_field("qword",  "next_record_number")
        self.declare_field("dword",  "header_size")
        self.declare_field("word",   "minor_version")
        self.declare_field("word",   "major_version")
        self.declare_field("word",   "header_chunk_size")
        self.declare_field("word",   "chunk_count")
        self.declare_field("dword",  "flags")
        self.declare_field("binary", "unused1", length=0x4c)
        self.declare_field("dword",  "checksum")

    def check_magic(self):
        """
        @return A boolean that indicates if the first eight bytes of
          the FileHeader match the expected magic value.
        """
        return self.magic() == "ElfFile\x00"

    def calculate_checksum(self):
        """
        @return A integer in the range of an unsigned int that
          is the calculated CRC32 checksum off the first 0x78 bytes.
          This is consistent with the checksum stored by the FileHeader.
        """
        return binascii.crc32(self.unpack_binary(0, 0x78)) & 0xFFFFFFFF

    def verify(self):
        """
        @return A boolean that indicates that the FileHeader 
          successfully passes a set of heuristic checks that
          all EVTX FileHeaders should pass.
        """
        return self.check_magic() and \
            self.major_version() == 0x3 and \
            self.minor_version() == 0x1 and \
            self.header_chunk_size() == 0x1000 and \
            self.checksum() == self.calculate_checksum()

    def is_dirty(self):
        """
        @return A boolean that indicates that the log has been
          opened and was changed, though not all changes might be
          reflected in the file header.
        """
        return self.flags() & 0x1
              
    def is_full(self):
        """
        @return A boolean that indicates that the log
          has reached its maximum configured size and the retention
          policy in effect does not allow to reclaim a suitable amount
          of space from the oldest records and an event message could
          not be written to the log file.
        """
        return self.flags() & 0x2

    def first_chunk(self):
        """
        @return A ChunkHeader instance that is the first chunk
          in the log file, which is always found directly after
          the FileHeader.
        """
        ofs = self._offset + self.header_chunk_size()
        return ChunkHeader(self._buf, ofs)

    def current_chunk(self):
        """
        @return A ChunkHeader instance that is the current chunk
          indicated by the FileHeader.
        """
        ofs = self._offset + self.header_chunk_size()
        ofs += (self.current_chunk_number() * 0x10000)
        return ChunkHeader(self._buf, ofs)

    def chunks(self):
        """
        @return A generator that yields the chunks of the log file
          starting with the first chunk, which is always found directly
          after the FileHeader, and continuing to the end of the file.
        """
        ofs = self._offset + self.header_chunk_size()
        while ofs + 0x10000 < len(self._buf):
            yield ChunkHeader(self._buf, ofs)
            ofs += 0x10000


class ChunkHeader(Block):
    def __init__(self, buf, offset):
        debug("CHUNK HEADER at %s." % (hex(offset)))
        super(ChunkHeader, self).__init__(buf, offset)
        self.declare_field("string", "magic", 0x0, 8)
        self.declare_field("qword",  "log_first_record_number")
        self.declare_field("qword",  "log_last_record_number")
        self.declare_field("qword",  "file_first_record_number")
        self.declare_field("qword",  "file_last_record_number")
        self.declare_field("dword",  "header_size")
        self.declare_field("dword",  "last_record_offset")
        self.declare_field("dword",  "next_record_offset")
        self.declare_field("dword",  "data_checksum")
        self.declare_field("binary", "unused", length=0x44)
        self.declare_field("dword",  "header_checksum")

    def check_magic(self):
        """
        @return A boolean that indicates if the first eight bytes of
          the ChunkHeader match the expected magic value.
        """
        return self.magic() == "ElfChnk\x00"

    def calculate_header_checksum(self):
        """
        @return A integer in the range of an unsigned int that
          is the calculated CRC32 checksum of the ChunkHeader fields.
        """
        data = self.unpack_binary(0x0, 0x78)
        data += self.unpack_binary(0x80, 0x180)
        return binascii.crc32(data) & 0xFFFFFFFF

    def calculate_data_checksum(self):
        """
        @return A integer in the range of an unsigned int that
          is the calculated CRC32 checksum of the Chunk data.
        """
        data = self.unpack_binary(0x200, self.next_record_offset() - 0x200)
        return binascii.crc32(data) & 0xFFFFFFFF

    def verify(self):
        """
        @return A boolean that indicates that the FileHeader 
          successfully passes a set of heuristic checks that
          all EVTX ChunkHeaders should pass.
        """
        return self.check_magic() and \
            self.calculate_header_checksum() == self.header_checksum() and \
            self.calculate_data_checksum() == self.data_checksum()



def main():
    import sys    

    
    BinaryParser.verbose = True

    with open(sys.argv[1], 'r') as f:
        with contextlib.closing(mmap.mmap(f.fileno(), 0, 
                                          access=mmap.ACCESS_READ)) as buf:
            fh = FileHeader(buf, 0x0)
            print fh.verify()
            
            for ch in fh.chunks():
                print ch.verify()

if __name__ == "__main__":
    main()
