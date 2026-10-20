from pathlib import Path


def safe_media_filename(filename: str) -> str:
    basename = Path((filename or "upload").replace("\\", "/")).name
    printable = "".join(character for character in basename if character.isprintable())
    return (printable.strip() or "upload")[:255]
