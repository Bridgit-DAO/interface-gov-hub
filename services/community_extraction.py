"""Bounded local extraction. Documents are evidence, never agent instructions."""
import io
import zipfile
from xml.etree import ElementTree

MAX_BYTES = 5 * 1024 * 1024
MAX_TEXT = 100_000
MAX_PASSAGES = 200
SUPPORTED = {'txt', 'md', 'pdf', 'docx', 'png', 'jpg', 'jpeg'}


class ExtractionError(ValueError):
    pass


def extract(content, extension):
    warnings = []
    chunks = []
    if extension in {'md', 'txt'}:
        try:
            chunks = [('text', content.decode('utf-8-sig'))]
        except UnicodeDecodeError as exc:
            raise ExtractionError('Text must be UTF-8.') from exc
    elif extension == 'docx':
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if sum(x.file_size for x in archive.infolist()) > 20 * 1024 * 1024:
                    raise ExtractionError('Expanded document exceeds the 20 MB limit.')
                xml = archive.read('word/document.xml')
                if b'<!DOCTYPE' in xml or b'<!ENTITY' in xml:
                    raise ExtractionError('XML entities are not supported.')
                root = ElementTree.fromstring(xml)
                ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                chunks = [(f'paragraph {i}', ''.join(t.text or '' for t in p.findall('.//w:t', ns)))
                          for i, p in enumerate(root.findall('.//w:p', ns), 1)]
                warnings.append('DOCX: paragraph locators; embedded images, headers and footnotes are not extracted.')
        except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
            raise ExtractionError('Unreadable DOCX document.') from exc
    elif extension == 'pdf':
        try:
            import fitz
        except ImportError as exc:
            raise ExtractionError('PDF extraction requires PyMuPDF on the worker.') from exc
        try:
            with fitz.open(stream=content, filetype='pdf') as pdf:
                if pdf.needs_pass or len(pdf) > 50:
                    raise ExtractionError('Encrypted PDFs and PDFs over 50 pages are not supported.')
                for i, page in enumerate(pdf, 1):
                    text = page.get_text()
                    if not text.strip():
                        warnings.append(f'Page {i}: no text found; OCR is not configured.')
                    chunks.append((f'page {i}', text))
        except ExtractionError:
            raise
        except Exception as exc:
            raise ExtractionError('Unreadable PDF document.') from exc
    else:
        raise ExtractionError('Image/scanned-source OCR is not configured. Upload a text transcription for review.')
    passages = []
    total = 0
    for location, text in chunks:
        for line_no, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            for part in range(0, len(line), 2000):
                snippet = line[part:part + 2000]
                total += len(snippet)
                if total > MAX_TEXT or len(passages) >= MAX_PASSAGES:
                    warnings.append('Extraction truncated at 100,000 characters or 200 passages; review the original.')
                    return passages, warnings
                passages.append((f'{location}, line {line_no}, span {part + 1}', snippet))
    if not passages:
        raise ExtractionError('No readable text found. OCR is not configured; no claims were created.')
    warnings.insert(0, 'Local passage extraction only. Review attribution, negation and tentative plans before confirming.')
    return passages, warnings
