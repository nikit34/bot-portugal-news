import os

from src.static.sources import tmp_folder


def clean_tmp_folder():
    for filename in os.listdir(tmp_folder):
        if filename != ".gitkeep":
            file_path = os.path.join(tmp_folder, filename)
            os.remove(file_path)