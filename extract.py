import shutil
import subprocess
import tempfile
from pathlib import Path


class UnsupportedFile(Exception):
    pass


TEXT_SUFFIXES = {".txt", ".md", ".csv", ".json", ".log"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}


def extract_text(filename, payload):
    suffix = Path(filename or "").suffix.lower()
    if suffix == ".pdf":
        return _from_pdf(payload)
    if suffix in IMAGE_SUFFIXES:
        return _from_image(payload, suffix)
    if suffix in TEXT_SUFFIXES or not suffix:
        return _decode(payload)
    raise UnsupportedFile(
        f"Unsupported file type {suffix}. Send a PDF, an image, or plain text."
    )


def _decode(payload):
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")


def _from_pdf(payload):
    if not shutil.which("pdftotext"):
        raise UnsupportedFile(
            "pdftotext is not installed. Install poppler-utils to read PDFs."
        )
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
        handle.write(payload)
        path = handle.name
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", path, "-"],
            capture_output=True,
            timeout=45,
            check=False,
        )
        text = result.stdout.decode("utf-8", errors="replace")
        if text.strip():
            return text
        return _ocr_pdf(path)
    finally:
        Path(path).unlink(missing_ok=True)


def _ocr_pdf(path):
    if not (shutil.which("tesseract") and shutil.which("pdftoppm")):
        raise UnsupportedFile(
            "This PDF has no text layer. Install tesseract and pdftoppm to read scans."
        )
    with tempfile.TemporaryDirectory() as workdir:
        prefix = str(Path(workdir) / "page")
        subprocess.run(
            ["pdftoppm", "-r", "200", "-png", "-f", "1", "-l", "1", path, prefix],
            capture_output=True,
            timeout=60,
            check=False,
        )
        pages = sorted(Path(workdir).glob("page*.png"))
        if not pages:
            raise UnsupportedFile("Could not render the first page of this PDF.")
        return _ocr_image(pages[0])


def _from_image(payload, suffix):
    if not shutil.which("tesseract"):
        raise UnsupportedFile(
            "Image receipts need tesseract. Install it, or send the text layer instead."
        )
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(payload)
        path = handle.name
    try:
        return _ocr_image(Path(path))
    finally:
        Path(path).unlink(missing_ok=True)


def _ocr_image(path):
    result = subprocess.run(
        ["tesseract", str(path), "stdout", "--psm", "6"],
        capture_output=True,
        timeout=60,
        check=False,
    )
    text = result.stdout.decode("utf-8", errors="replace")
    if not text.strip():
        raise UnsupportedFile("No readable text was found in that image.")
    return text
