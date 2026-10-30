from __future__ import annotations
import io, os, re, tempfile
from pathlib import Path
from typing import Literal
import pandas as pd
import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

MAX_FILE_BYTES = int(os.getenv("PDF_EXCEL_MAX_BYTES", str(25 * 1024 * 1024)))
MAX_FILES = int(os.getenv("PDF_EXCEL_MAX_FILES", "10"))
TESSERACT_CMD = os.getenv("TESSERACT_CMD")
if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

app = FastAPI(title="Digital SATHIDAR PDF to Excel API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000", "http://localhost:8000",
        "http://127.0.0.1:5500", "http://localhost:5500",
        "https://rayatsevaksujit.github.io",
    ],
    allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["*"],
)

def safe_sheet_name(name: str, used: set[str]) -> str:
    base = re.sub(r'[\\/*?:\[\]]', "_", Path(name).stem)[:25] or "PDF"
    candidate, n = base, 1
    while candidate.lower() in used:
        n += 1
        candidate = f"{base[:22]}_{n}"
    used.add(candidate.lower())
    return candidate

def clean_table(table) -> pd.DataFrame | None:
    if not table:
        return None
    rows = [[("" if v is None else str(v).strip()) for v in row] for row in table]
    rows = [r for r in rows if any(cell for cell in r)]
    if not rows:
        return None
    width = max(map(len, rows))
    rows = [r + [""] * (width-len(r)) for r in rows]
    # Use first row as headers only when it appears to be a header; otherwise preserve all rows.
    first = rows[0]
    if len(set(first)) == len(first) and any(first):
        headers = []
        seen = {}
        for i, val in enumerate(first):
            label = val or f"Column {i+1}"
            seen[label] = seen.get(label, 0) + 1
            headers.append(label if seen[label] == 1 else f"{label}_{seen[label]}")
        data = rows[1:] if len(rows) > 1 else []
        return pd.DataFrame(data, columns=headers)
    return pd.DataFrame(rows, columns=[f"Column {i+1}" for i in range(width)])

def is_legacy_marathi_garbled(text: str) -> bool:
    """Detect legacy-font Marathi text exposed as Latin glyph sequences by PDF extractors."""
    if not text or len(text.strip()) < 40:
        return False
    devanagari = len(re.findall(r"[\u0900-\u097F]", text))
    legacy_markers = len(re.findall(r"Eò|É|ªÉ|ºÉ|Æ|þ|³|´É|Ê|ú", text))
    return devanagari < max(3, int(len(text) * 0.015)) and legacy_markers >= 6


def page_requires_ocr(page) -> bool:
    try:
        return is_legacy_marathi_garbled(page.extract_text() or "")
    except Exception:
        return True


def digital_tables(pdf_bytes: bytes) -> list[tuple[str, pd.DataFrame]]:
    found = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            # Legacy-font pages can produce populated but unreadable table cells.
            if page_requires_ocr(page):
                continue
            tables = page.extract_tables() or []
            for table_no, table in enumerate(tables, start=1):
                df = clean_table(table)
                if df is not None and not df.empty:
                    found.append((f"Page {page_no} Table {table_no}", df))
    return found

def ocr_page_to_frame(image, languages: str) -> pd.DataFrame | None:
    # Tesseract TSV provides word positions; group words into text lines and approximate columns
    # by their horizontal centers. This is a best-effort table reconstruction, not guaranteed layout recovery.
    data = pytesseract.image_to_data(image, lang=languages, output_type=pytesseract.Output.DATAFRAME,
                                     config="--psm 6")
    data = data.dropna(subset=["text"])
    data["text"] = data["text"].astype(str).str.strip()
    data = data[(data["text"] != "") & (data["conf"].fillna(-1) >= 0)]
    if data.empty:
        return None
    # Group adjacent words by Tesseract's line identifiers and keep their x coordinates.
    rows = []
    for _, group in data.groupby(["block_num", "par_num", "line_num"], sort=True):
        words = sorted(zip(group["left"].astype(int), group["text"].tolist()), key=lambda x: x[0])
        if words:
            rows.append(words)
    if not rows:
        return None
    # Approximate columns by splitting large horizontal gaps relative to page width.
    page_width = max(1, image.width)
    gap_threshold = max(28, int(page_width * 0.035))
    token_rows = []
    all_centers = []
    for words in rows:
        cells, current, previous = [], [], None
        for x, word in words:
            if previous is not None and x - previous > gap_threshold:
                cells.append(" ".join(current)); current = []
            current.append(word); previous = x
        if current:
            cells.append(" ".join(current))
        token_rows.append(cells)
        all_centers.append(len(cells))
    width = max(all_centers, default=0)
    if not width:
        return None
    normalized = [row + [""] * (width-len(row)) for row in token_rows]
    # Preserve OCR rows as text columns rather than silently dropping Marathi characters.
    return pd.DataFrame(normalized, columns=[f"Column {i+1}" for i in range(width)])


def scanned_tables(pdf_bytes: bytes, languages: str, pages_to_scan: set[int] | None = None) -> list[tuple[str, pd.DataFrame]]:
    found = []
    try:
        images = convert_from_bytes(pdf_bytes, dpi=250, fmt="png")
    except Exception as exc:
        raise RuntimeError("PDF pages could not be rendered. Install Poppler and check PATH.") from exc
    for page_no, image in enumerate(images, start=1):
        if pages_to_scan is not None and page_no not in pages_to_scan:
            continue
        frame = ocr_page_to_frame(image, languages)
        if frame is not None and not frame.empty:
            found.append((f"Page {page_no} OCR", frame))
    return found

@app.get("/api/health")
def health():
    try:
        langs = pytesseract.get_languages(config="")
    except Exception:
        langs = []
    return {"ok": True, "tesseract_languages": langs, "marathi_available": "mar" in langs}

@app.post("/api/convert")
async def convert(
    files: list[UploadFile] = File(...),
    mode: Literal["auto", "digital", "ocr"] = Form("auto"),
    languages: Literal["eng", "mar", "eng+mar"] = Form("eng+mar"),
):
    if not files:
        raise HTTPException(400, "कृपया PDF फाइल निवडा.")
    if len(files) > MAX_FILES:
        raise HTTPException(413, f"एका वेळी जास्तीत जास्त {MAX_FILES} फाइल्स स्वीकारल्या जातात.")
    output_sheets: list[tuple[str, pd.DataFrame]] = []
    used_names: set[str] = set()
    try:
        for upload in files:
            name = Path(upload.filename or "document.pdf").name
            if not name.lower().endswith(".pdf"):
                raise HTTPException(415, f"{name}: फक्त PDF फाइल स्वीकारली जाते.")
            raw = await upload.read(MAX_FILE_BYTES + 1)
            if len(raw) > MAX_FILE_BYTES:
                raise HTTPException(413, f"{name}: फाइल आकार मर्यादा {MAX_FILE_BYTES // (1024*1024)} MB आहे.")
            if not raw.startswith(b"%PDF-"):
                raise HTTPException(400, f"{name}: वैध PDF फाइल वाटत नाही.")
            extracted = []
            if mode in ("auto", "digital"):
                try:
                    extracted = digital_tables(raw)
                except Exception as exc:
                    if mode == "digital":
                        raise HTTPException(422, f"{name}: डिजिटल टेबल्स वाचता आल्या नाहीत: {exc}")
            # In Automatic mode, OCR only pages where digital table extraction found no table.
            # This supports mixed PDFs containing both selectable-text and scanned pages.
            pages_to_scan = None
            if mode == "auto":
                try:
                    with pdfplumber.open(io.BytesIO(raw)) as pdf:
                        total_pages = len(pdf.pages)
                    digital_pages = {
                        int(match.group(1))
                        for label, _ in extracted
                        if (match := re.match(r"Page (\d+) Table", label))
                    }
                    with pdfplumber.open(io.BytesIO(raw)) as pdf:
                        unreadable_pages = {
                            page_no for page_no, page in enumerate(pdf.pages, start=1)
                            if page_requires_ocr(page)
                        }
                    pages_to_scan = (set(range(1, total_pages + 1)) - digital_pages) | unreadable_pages
                except Exception:
                    pages_to_scan = None
            if mode == "ocr" or (mode == "auto" and pages_to_scan):
                try:
                    ocr_results = scanned_tables(raw, languages, pages_to_scan if mode == "auto" else None)
                    if mode == "ocr":
                        extracted = ocr_results
                    else:
                        extracted.extend(ocr_results)
                except pytesseract.TesseractNotFoundError:
                    raise HTTPException(500, "Tesseract OCR सापडले नाही. README मधील installation पायऱ्या पहा.")
                except pytesseract.TesseractError as exc:
                    raise HTTPException(422, f"OCR भाषा/डेटा उपलब्ध नाही: {exc}. mar.traineddata तपासा.")
                except RuntimeError as exc:
                    raise HTTPException(500, str(exc))
            if not extracted:
                output_sheets.append((safe_sheet_name(name, used_names), pd.DataFrame({"सूचना": ["या PDF मधून टेबल/मजकूर मिळाला नाही. OCR mode वापरून पहा."]})))
            else:
                for label, frame in extracted:
                    sheet = safe_sheet_name(f"{Path(name).stem}_{label}", used_names)
                    output_sheets.append((sheet, frame))
            await upload.close()
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            for sheet_name, frame in output_sheets:
                frame.to_excel(writer, sheet_name=sheet_name[:31], index=False)
                ws = writer.sheets[sheet_name[:31]]
                ws.freeze_panes = "A2"
                ws.auto_filter.ref = ws.dimensions
                for cell in ws[1]:
                    cell.font = Font(bold=True, color="FFFFFF")
                    cell.fill = PatternFill("solid", fgColor="1D4ED8")
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
                for col_idx, col in enumerate(ws.columns, 1):
                    max_len = max((len(str(c.value or "")) for c in list(col)[:200]), default=10)
                    ws.column_dimensions[get_column_letter(col_idx)].width = min(max(max_len + 2, 12), 42)
                for row in ws.iter_rows(min_row=2):
                    for cell in row:
                        cell.alignment = Alignment(vertical="top", wrap_text=True)
        out.seek(0)
        return StreamingResponse(out, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="pdf-to-excel.xlsx"',
                     "X-Converted-Sheets": str(len(output_sheets))})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"रूपांतरण करताना त्रुटी: {type(exc).__name__}: {exc}") from exc
