"""PDF generation for tailored résumés - professional formatting."""

import re
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black, HexColor


def _clean_text(text: str) -> str:
    """Strip markdown markers for PDF (no hash symbols, bold, or links)."""
    text = re.sub(r"^#+\s*", "", text)  # strip leading # (e.g. ##### or ##)
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    return text.strip()


def _is_category_label(line: str) -> bool:
    """Detect short ALL-CAPS lines like LANGUAGES, FRAMEWORKS & PLATFORMS."""
    cleaned = _clean_text(line)
    if len(cleaned) > 60 or not cleaned:
        return False
    letters = sum(1 for c in cleaned if c.isalpha())
    caps = sum(1 for c in cleaned if c.isupper())
    return letters > 0 and caps / letters >= 0.7


def generate_tailored_pdf(tailored_text: str, candidate_name: str = "Candidate") -> bytes:
    """
    Generate PDF from markdown-formatted tailored resume.
    Professional layout: generous spacing, clear hierarchy.
    """
    buffer = BytesIO()
    doc = canvas.Canvas(buffer, pagesize=letter)
    page_width, page_height = letter
    margin = 0.75 * inch
    content_width = page_width - (margin * 2)
    cursor_y = page_height - margin

    LINE_HEIGHT = 14
    BULLET_INDENT = 16
    SECTION_SPACING = 20
    MAJOR_SECTION_SPACING = 28

    def check_page_break(needed_height: float = 20) -> None:
        nonlocal cursor_y
        if cursor_y - needed_height < margin:
            doc.showPage()
            cursor_y = page_height - margin

    def split_lines(text: str, font: str, size: int, max_width: float) -> list[str]:
        """Wrap text to fit width."""
        words = text.split()
        lines = []
        current = []
        for w in words:
            test = " ".join(current + [w])
            if doc.stringWidth(test, font, size) <= max_width:
                current.append(w)
            else:
                if current:
                    lines.append(" ".join(current))
                current = [w]
        if current:
            lines.append(" ".join(current))
        return lines if lines else [text]

    text_dark = HexColor("#1e293b")
    text_body = HexColor("#334155")

    lines = tailored_text.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(r"^={3,}$", line) or re.match(r"^-{3,}$", line):
            continue

        # 1. NAME / H1 (# )
        if line.startswith("# "):
            check_page_break(50)
            text = _clean_text(line[2:])
            doc.setFont("Helvetica-Bold", 26)
            doc.setFillColor(black)
            tw = doc.stringWidth(text, "Helvetica-Bold", 26)
            x = (page_width - tw) / 2
            doc.drawString(x, cursor_y, text[:80])
            cursor_y -= LINE_HEIGHT + 8
            doc.setStrokeColor(black)
            doc.setLineWidth(0.4)
            doc.line(margin, cursor_y, page_width - margin, cursor_y)
            cursor_y -= MAJOR_SECTION_SPACING

        # 2. MAJOR SECTION (## ) - Contact, Summary, Core Skills, etc.
        elif line.startswith("## "):
            check_page_break(45)
            cursor_y -= 6
            header_text = _clean_text(line[3:]).upper()
            doc.setFont("Helvetica-Bold", 12)
            doc.setFillColor(black)
            doc.drawString(margin, cursor_y, header_text[:120])
            cursor_y -= 4
            doc.setStrokeColor(black)
            doc.setLineWidth(0.5)
            doc.line(margin, cursor_y, page_width - margin, cursor_y)
            cursor_y -= SECTION_SPACING

        # 3. SECTION HEADER (### )
        elif line.startswith("### "):
            check_page_break(40)
            cursor_y -= 6
            header_text = _clean_text(line[4:]).upper()
            doc.setFont("Helvetica-Bold", 11)
            doc.setFillColor(black)
            doc.drawString(margin, cursor_y, header_text[:120])
            cursor_y -= 4
            doc.setStrokeColor(black)
            doc.setLineWidth(0.4)
            doc.line(margin, cursor_y, page_width - margin, cursor_y)
            cursor_y -= SECTION_SPACING

        # 4. SUB-HEADER (#### or #####) - job title, role
        elif re.match(r"^#{4,}\s", line):
            check_page_break(28)
            cursor_y -= 4
            doc.setFont("Helvetica-Bold", 11)
            doc.setFillColor(text_dark)
            doc.drawString(margin, cursor_y, _clean_text(line)[:120])
            cursor_y -= LINE_HEIGHT + 4

        # 5. CATEGORY LABEL (LANGUAGES, FRAMEWORKS & PLATFORMS, etc.)
        elif _is_category_label(line):
            check_page_break(24)
            cursor_y -= 4
            doc.setFont("Helvetica-Bold", 10)
            doc.setFillColor(text_dark)
            doc.drawString(margin, cursor_y, _clean_text(line)[:80])
            cursor_y -= LINE_HEIGHT + 2

        # 6. IMPACT / small sub-heading
        elif line.upper() in ("IMPACT", "IMPACT:"):
            check_page_break(24)
            cursor_y -= 6
            doc.setFont("Helvetica-Bold", 10)
            doc.setFillColor(text_dark)
            doc.drawString(margin, cursor_y, "Impact")
            cursor_y -= LINE_HEIGHT + 2

        # 7. BULLET (- or *)
        elif line.startswith("- ") or line.startswith("* "):
            bullet_text = _clean_text(line[2:])
            wrapped = split_lines(bullet_text, "Helvetica", 10, content_width - BULLET_INDENT)
            check_page_break(len(wrapped) * LINE_HEIGHT + 6)
            doc.setFont("Helvetica", 10)
            doc.setFillColor(black)
            doc.drawString(margin + 4, cursor_y, "•")
            doc.setFillColor(text_body)
            for w in wrapped:
                doc.drawString(margin + BULLET_INDENT, cursor_y, w[:150])
                cursor_y -= LINE_HEIGHT
            cursor_y -= 3

        # 8. KEY-VALUE (**key**: value)
        elif re.match(r"^\*\*.*?\*\*:", line):
            m = re.match(r"^\*\*(.*?)\*\*:(.*)", line)
            if m:
                key = m.group(1) + ":"
                val = _clean_text(m.group(2))
                doc.setFont("Helvetica-Bold", 10)
                doc.setFillColor(text_dark)
                kw = doc.stringWidth(key, "Helvetica-Bold", 10)
                avail = content_width - kw - 4
                val_lines = split_lines(val, "Helvetica", 10, avail)
                check_page_break(len(val_lines) * LINE_HEIGHT + 4)
                doc.drawString(margin, cursor_y, key)
                doc.setFont("Helvetica", 10)
                doc.setFillColor(text_body)
                for w in val_lines:
                    doc.drawString(margin + kw + 4, cursor_y, w[:120])
                    cursor_y -= LINE_HEIGHT
                cursor_y -= 4
            else:
                doc.setFont("Helvetica", 10)
                doc.setFillColor(text_body)
                for w in split_lines(_clean_text(line), "Helvetica", 10, content_width):
                    check_page_break(LINE_HEIGHT)
                    doc.drawString(margin, cursor_y, w[:150])
                    cursor_y -= LINE_HEIGHT
                cursor_y -= 4
        else:
            doc.setFont("Helvetica", 10)
            doc.setFillColor(text_body)
            for w in split_lines(_clean_text(line), "Helvetica", 10, content_width):
                check_page_break(LINE_HEIGHT)
                doc.drawString(margin, cursor_y, w[:150])
                cursor_y -= LINE_HEIGHT
            cursor_y -= 4

    doc.save()
    buffer.seek(0)
    return buffer.getvalue()
