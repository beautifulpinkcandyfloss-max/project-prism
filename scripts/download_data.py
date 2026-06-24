#!/usr/bin/env python3
"""Download and extract processed_data bundle for Project Prism.

Usage:
  - Set `DATA_URL` environment variable or pass `--url` argument.
  - The script supports ZIP and tar.gz archives and plain file downloads.

Example:
  DATA_URL=https://example.com/processed_data.zip python scripts/download_data.py
"""
import argparse
import os
import sys
import shutil
import tempfile
import urllib.request
import zipfile
import tarfile


def download(url: str, dst: str):
    with urllib.request.urlopen(url) as r:
        with open(dst, "wb") as f:
            shutil.copyfileobj(r, f)


def extract(archive_path: str, out_dir: str):
    if archive_path.endswith('.zip'):
        with zipfile.ZipFile(archive_path, 'r') as z:
            z.extractall(out_dir)
    elif archive_path.endswith(('.tar.gz', '.tgz', '.tar')):
        with tarfile.open(archive_path, 'r:*') as t:
            t.extractall(out_dir)
    else:
        # unknown archive type; treat as single file
        os.makedirs(out_dir, exist_ok=True)
        shutil.copy(archive_path, os.path.join(out_dir, os.path.basename(archive_path)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', help='Download URL for processed_data archive')
    parser.add_argument('--dest', default='processed_data', help='Destination folder')
    args = parser.parse_args()

    url = args.url or os.environ.get('DATA_URL')
    if not url:
        print('ERROR: No DATA_URL provided. Set DATA_URL env var or pass --url.', file=sys.stderr)
        sys.exit(2)

    dest = args.dest
    tmpdir = tempfile.mkdtemp(prefix='prism_dl_')
    try:
        filename = os.path.join(tmpdir, 'data_archive')
        print('Downloading', url)
        download(url, filename)
        print('Extracting to', dest)
        extract(filename, dest)
        print('Download and extraction complete.')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == '__main__':
    main()
