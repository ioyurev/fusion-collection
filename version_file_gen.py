import tomllib

with open("../pyproject.toml", "rb") as f:
    data = tomllib.load(f)
version = data["tool"]["poetry"]["version"]
v = list([int(x) for x in version.split(".")])
v.append(0)
with open("version_text_file", "r") as f:
    lines = f.readlines()
lines[8] = f"    filevers=({v[0]}, {v[1]}, {v[2]}, {v[3]}),"
lines[9] = f"    prodvers=({v[0]}, {v[1]}, {v[2]}, {v[3]}),"

with open("version_text_file", "w") as f:
    f.writelines(lines)
