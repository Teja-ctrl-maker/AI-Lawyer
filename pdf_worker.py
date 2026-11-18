"""Disposable text extractor. Inputs and results travel only through pipes."""
import io
import json
from pathlib import Path
import re
import sys


def extract():
    dependencies = Path(__file__).with_name('.deps')
    if dependencies.is_dir():
        sys.path.insert(0, str(dependencies))
    try:
        from pypdf import PdfReader, __version__
    except ImportError:
        return {'error': 'Install the PDF dependency from requirements-pdf.txt to enable previews.'}
    version = re.match(r'^(\d+)\.(\d+)\.(\d+)', __version__)
    if not version or tuple(map(int, version.groups())) < (7, 0, 1):
        return {'error': 'The PDF parser needs an update. Install requirements-pdf.txt or paste the relevant text.'}

    from pypdf import overwrite_configuration
    overwrite_configuration(
        maximum_declared_stream_length=8_000_000,
        zlib_maximum_output_length=8_000_000,
        lzw_maximum_output_length=8_000_000,
        jbig2_maximum_output_length=8_000_000,
        run_length_maximum_output_length=8_000_000,
        brotli_maximum_output_length=8_000_000,
        array_based_stream_maximum_output_length=8_000_000,
        stream_decoding_work_maximum_length=24_000_000,
    )
    try:
        reader = PdfReader(io.BytesIO(sys.stdin.buffer.read(2_000_001)))
        if reader.is_encrypted or len(reader.pages) > 20:
            return {'error': 'Choose an unlocked PDF with at most 20 pages.'}
        pages = []
        for number, page in enumerate(reader.pages, 1):
            # Avoid walking image streams and rendering any page content.
            content = page.get_contents()
            if content is not None and len(content.get_data()) > 2_000_000:
                return {'error': 'The PDF page is too complex. Try a smaller text PDF.'}
            text = (page.extract_text() or '').strip()
            if text:
                pages.append({'page': number, 'text': text[:4000], 'truncated': len(text) > 4000})
        if not pages:
            return {'error': 'This PDF has no readable text layer. Paste the relevant passage from the scan.'}
        return {'pages': pages, 'page_count': len(reader.pages)}
    except Exception:
        return {'error': 'The PDF could not be read. Paste a short passage or try another text PDF.'}


if __name__ == '__main__':
    print(json.dumps(extract(), ensure_ascii=True))
