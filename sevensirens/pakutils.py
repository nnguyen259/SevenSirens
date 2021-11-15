import os
from io import BytesIO


def unpack(data: bytes, out_directory=".") -> None:
    _unpack(BytesIO(data), out_directory)


def unpackfile(file: str, out_directory=".") -> None:
    if not os.path.isfile(file):
        raise FileNotFoundError("Please specify a valid file to unpack.")

    with open(file, "rb") as infile:
        _unpack(
            infile, out_directory, f"{os.path.basename(file).rsplit('.', 1)[0]}.txt"
        )


def _unpack(data: BytesIO, out_directory=".", file_list_name="file_list.txt") -> None:
    data_offset = int.from_bytes(data.read(4), "little")
    file_count = int.from_bytes(data.read(4), "little")
    file_names = list()
    current_offset = data.tell()
    if not os.path.exists(out_directory):
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
        file_names.append(file_name)
        if out_directory:
            file_name = os.path.join(out_directory, file_name)
        current_offset = data.tell()

        data.seek(data_offset + offset)
        data.read(64)
        file_content = data.read(file_size)

        os.makedirs(os.path.dirname(file_name), exist_ok=True)
        with open(file_name, "wb") as output:
            output.write(file_content)

    with open(os.path.join(out_directory, file_list_name), "w") as name_file:
        name_file.write("\n".join(file_names))


def pack(directory: str, file_list="file_list.txt") -> bytes:
    directory = os.path.normpath(directory)
    with open(os.path.join(directory, file_list)) as name_file:
        file_names = name_file.read().splitlines()
    output = BytesIO()
    file_infos = list()
    file_name_size = 0
    output.write(8 * b"\0")
    for file in file_names:
        file_info = dict()
        file_path = os.path.join(directory, os.path.normpath(file))
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


def packtofile(directory: str, outputfile: str, file_list="file_list.txt") -> None:
    if os.path.dirname(outputfile):
        os.makedirs(os.path.dirname(outputfile), exist_ok=True)
    with open(outputfile, "wb") as archive:
        archive.write(pack(directory, file_list))
