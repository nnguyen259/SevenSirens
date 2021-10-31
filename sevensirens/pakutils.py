import os
import shutil
import time
from io import BytesIO
from typing import Optional


def unpack(data: bytes, out_directory: Optional[str]) -> None:
    _unpack(BytesIO(data), out_directory)


def unpackfile(file: str, out_directory: Optional[str]) -> None:
    if not os.path.isfile(file):
        raise FileNotFoundError("Please specify a valid file to unpack.")

    with open(file, "rb") as infile:
        _unpack(infile, out_directory)


def _unpack(data: BytesIO, out_directory: Optional[str]) -> None:
    data_offset = int.from_bytes(data.read(4), "little")
    file_count = int.from_bytes(data.read(4), "little")
    current_offset = data.tell()
    if out_directory:
        os.makedirs(out_directory, exist_ok=True)

    for _ in range(file_count):
        data.seek(current_offset)
        data.read(16)
        offset = int.from_bytes(data.read(4), "little")
        file_size = int.from_bytes(data.read(4), "little")
        file_name = data.read(8)
        while not file_name.endswith((b"\0", b"?")):
            file_name += data.read(8)
        file_name = file_name.replace(b"?", b"").replace(b"\0", b"")
        file_name = file_name.decode("utf-8").replace(":", "/")
        if out_directory:
            file_name = os.path.join(out_directory, file_name)
        current_offset = data.tell()

        data.seek(data_offset + offset)
        data.read(64)
        file_content = data.read(file_size)

        os.makedirs(os.path.dirname(file_name), exist_ok=True)
        with open(file_name, "wb") as output:
            output.write(file_content)


def pack(directory: str) -> bytes:
    directory = os.path.normpath(directory)
    output = BytesIO()
    file_infos = list()
    file_name_size = 0
    for root, _, files in os.walk(directory):
        output.write(8 * b"\0")
        for file in files:
            file_info = dict()
            file_path = os.path.join(root, file)
            with open(file_path, "rb") as file_stream:
                file_content = file_stream.read()
                file_info["size"] = len(file_content)
                pad_size = 16 - (len(file_content) % 16)
                if pad_size % 16:
                    file_content += pad_size * b"?"
                file_info["data"] = file_content

            file_name = (
                file_path[len(directory) + 1 :]
                .replace("/", ":")
                .replace("\\", ":")
                .encode("utf-8")
            )
            file_name += b"\0"
            pad_size = 8 - (len(file_name) % 8)
            if pad_size % 8:
                file_name += pad_size * b"?"
            file_info["name"] = file_name
            file_name_size += len(file_name)

            file_infos.append(file_info)

    header_size = file_name_size + 24 * len(file_infos)
    while (header_size + 8) % 16:
        header_size += 1
    output.write(header_size * b"?")
    output.seek(0)
    output.write(int.to_bytes(8 + header_size, 4, "little"))
    output.write(int.to_bytes(len(file_infos), 4, "little"))

    data_offset = 0
    next_header_offset = 8
    for info in file_infos:
        output.seek(next_header_offset)
        output.write(b"FILELINK_____END")
        output.write(data_offset.to_bytes(4, "little"))
        output.write(info["size"].to_bytes(4, "little"))
        output.write(info["name"])
        next_header_offset = output.tell()

        output.seek(8 + header_size + data_offset)
        output.write(
            b"MANAGEDFILE_DATABLOCK_USED_IN_ENGINE_________________________END"
        )
        output.write(info["data"])
        data_offset = output.tell() - header_size - 8

    pad_size = 64 - (output.seek(0, 2) % 64)
    if pad_size % 64:
        output.write(pad_size * b"?")

    output.seek(0)
    return output.read()


def packtofile(directory: str, outputfile: str) -> None:
    if os.path.dirname(outputfile):
        os.makedirs(os.path.dirname(outputfile), exist_ok=True)
    with open(outputfile, "wb") as archive:
        archive.write(pack(directory))


if __name__ == '__main__':
    unpackfile('data.pak', 'data')