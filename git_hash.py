import subprocess


def get_hash():
    process = subprocess.Popen(
        ["git", "rev-parse", "HEAD"], shell=False, stdout=subprocess.PIPE
    )
    hash_bytes = process.communicate()[0].strip()
    return hash_bytes.decode("utf-8")


with open("__hash__.py", "w") as f:
    f.write(f'HASH = "{get_hash()}"')
