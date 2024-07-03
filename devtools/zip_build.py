import shutil

from fusion_collection.__version__ import VERSION

output_filename = f"dist/fusion-collection_v{VERSION}"
dir_name = "dist/fusion-collection"

shutil.make_archive(output_filename, "zip", dir_name)
