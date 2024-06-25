from fusion_collection.__version__ import VERSION
from fusion_collection.ui.__hash__ import HASH

v = list([int(x) for x in VERSION.split(".")])
v.append(0)

file_content = f"""VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=({v[0]}, {v[1]}, {v[2]}, {v[3]}),
        prodvers=({v[0]}, {v[1]}, {v[2]}, {v[3]}),
        # Contains a bitmask that specifies the valid bits 'flags'r
        mask=0x3F,
        # Contains a bitmask that specifies the Boolean attributes of the file.
        flags=0x0,
        # The operating system for which this file was designed.
        # 0x4 - NT and there is no need to change it.
        OS=0x40004,
        # The general type of file.
        # 0x1 - the file is an application.
        fileType=0x1,
        # The function of the file.
        # 0x0 - the function is not defined for this fileType
        subtype=0x0,
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct(
                            "FileVersion", "{v[0]}.{v[1]}.{v[2]}.{v[3]} (commit {HASH})"
                        ),
                        StringStruct("OriginalFilename", "fusion-collection.exe"),
                        StringStruct(
                            "ProductName", "Fusion Collection"
                        ),
                        StringStruct("ProductVersion", "{v[0]}.{v[1]}.{v[2]}.{v[3]}"),
                    ],
                )
            ]
        )
    ],
)
"""

with open("version_text_file", "w") as f:
    f.write(file_content)
