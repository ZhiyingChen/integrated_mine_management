import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


@dataclass
class CellValue:
    value: Any = None
    formula: Optional[str] = None
    ref: str = ""


def col_to_num(col: str) -> int:
    n = 0
    for ch in col:
        if ch.isalpha():
            n = n * 26 + ord(ch.upper()) - 64
    return n


def num_to_col(n: int) -> str:
    s = ""
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s


def split_ref(ref: str) -> Tuple[int, int]:
    col = "".join(ch for ch in ref if ch.isalpha())
    row = int("".join(ch for ch in ref if ch.isdigit()))
    return row, col_to_num(col)


def normalize_number(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    if number.is_integer():
        return int(number)
    return number


class WorkbookReader:
    def __init__(self, path: str):
        self.path = path
        self._zip = zipfile.ZipFile(path)
        self.shared_strings = self._read_shared_strings()
        self.sheet_targets = self._read_sheet_targets()
        self._sheet_cache: Dict[str, Dict[Tuple[int, int], CellValue]] = {}

    @property
    def sheet_names(self) -> List[str]:
        return list(self.sheet_targets.keys())

    def _read_shared_strings(self) -> List[str]:
        if "xl/sharedStrings.xml" not in self._zip.namelist():
            return []
        root = ET.fromstring(self._zip.read("xl/sharedStrings.xml"))
        strings = []
        for si in root.findall("main:si", NS):
            strings.append("".join(t.text or "" for t in si.iterfind(".//main:t", NS)))
        return strings

    def _read_sheet_targets(self) -> Dict[str, str]:
        workbook = ET.fromstring(self._zip.read("xl/workbook.xml"))
        rels = ET.fromstring(self._zip.read("xl/_rels/workbook.xml.rels"))
        rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"].lstrip("/")
            for rel in rels.findall("pkgrel:Relationship", NS)
        }
        targets = {}
        for sheet in workbook.find("main:sheets", NS):
            rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = rel_map[rid]
            if not target.startswith("xl/"):
                target = "xl/" + target
            targets[sheet.attrib["name"]] = target
        return targets

    def _parse_cell(self, cell) -> CellValue:
        ref = cell.attrib.get("r", "")
        t = cell.attrib.get("t")
        v = cell.find("main:v", NS)
        f = cell.find("main:f", NS)
        formula = f.text if f is not None and f.text is not None else None

        value = None
        if t == "s" and v is not None and v.text is not None:
            value = self.shared_strings[int(v.text)]
        elif t == "inlineStr":
            node = cell.find("main:is", NS)
            value = "".join(tn.text or "" for tn in node.iterfind(".//main:t", NS)) if node is not None else ""
        elif v is not None and v.text is not None:
            value = normalize_number(v.text)
        return CellValue(value=value, formula=formula, ref=ref)

    def sheet_cells(self, sheet_name: str) -> Dict[Tuple[int, int], CellValue]:
        if sheet_name in self._sheet_cache:
            return self._sheet_cache[sheet_name]
        root = ET.fromstring(self._zip.read(self.sheet_targets[sheet_name]))
        cells = {}
        for cell in root.iterfind(".//main:sheetData/main:row/main:c", NS):
            parsed = self._parse_cell(cell)
            if not parsed.ref:
                continue
            cells[split_ref(parsed.ref)] = parsed
        self._sheet_cache[sheet_name] = cells
        return cells

    def cell(self, sheet_name: str, row: int, col: int) -> CellValue:
        return self.sheet_cells(sheet_name).get((row, col), CellValue(ref=f"{num_to_col(col)}{row}"))

    def value(self, sheet_name: str, row: int, col: int, default=0):
        value = self.cell(sheet_name, row, col).value
        return default if value is None or value == "" else value

    def numeric_value(self, sheet_name: str, row: int, col: int, default: float = 0.0) -> float:
        value = self.value(sheet_name, row, col, default=default)
        if value is None or value == "":
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def max_row_col(self, sheet_name: str) -> Tuple[int, int]:
        cells = self.sheet_cells(sheet_name)
        if not cells:
            return 0, 0
        return max(r for r, _ in cells), max(c for _, c in cells)

    def header_map(self, sheet_name: str, header_row: int = 1) -> Dict[str, int]:
        _, max_col = self.max_row_col(sheet_name)
        result = {}
        for col in range(1, max_col + 1):
            cell = self.cell(sheet_name, header_row, col)
            header = cell.value
            if header is None or header == "":
                header = f"未命名_{num_to_col(col)}"
            result[str(header)] = col
        return result

    def iter_rows(self, sheet_name: str, min_row: int = 2) -> List[int]:
        cells = self.sheet_cells(sheet_name)
        return sorted({row for row, _ in cells if row >= min_row})

    def find_row_by_value(self, sheet_name: str, col: int, expected: str) -> Optional[int]:
        for row in self.iter_rows(sheet_name, min_row=1):
            if self.value(sheet_name, row, col, default=None) == expected:
                return row
        return None
