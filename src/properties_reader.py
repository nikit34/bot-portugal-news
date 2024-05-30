import os


def get_secret_key(root_path, key):
    value = os.environ.get(key)
    if not value and os.path.isfile(root_path + "/secret"):
        with open(root_path + "/secret", "r") as f:
            for line in f.readlines():
                if key in line:
                    value = line.replace(key + '=', '').replace('\n', '')
                    break
    if not value:
        raise KeyError("ERROR: key not found")
    return value
