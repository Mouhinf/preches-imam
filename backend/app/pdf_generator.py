"""Generate a beautiful, presentable PDF from a sermon's HTML content.

Supports Arabic (RTL), French and English. Uses ReportLab with arabic-reshaper
and python-bidi to handle Arabic correctly.
"""
from io import BytesIO
from pathlib import Path
from datetime import datetime
from typing import Optional
import re

from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, Color
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
    PageBreak, KeepTogether,
)
from reportlab.pdfgen import canvas
import arabic_reshaper
from bidi.algorithm import get_display


BASE_DIR = Path(__file__).resolve().parent.parent
FONTS_DIR = BASE_DIR / "fonts"

# Brand colors
PRIMARY = HexColor("#0e7c5a")      # deep green
SECONDARY = HexColor("#b58c3a")    # gold
DARK = HexColor("#1f2937")
LIGHT = HexColor("#f3f4f6")
MUTED = HexColor("#6b7280")


_fonts_registered = False


def _register_fonts():
    """Register fonts. Use system fallbacks if custom fonts are missing."""
    global _fonts_registered
    if _fonts_registered:
        return

    # Try to register Amiri (Arabic) and a Latin font if available locally.
    candidates_ar = [
        FONTS_DIR / "Amiri-Regular.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    ]
    candidates_ar_bold = [
        FONTS_DIR / "Amiri-Bold.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ]
    candidates_latin = [
        FONTS_DIR / "DejaVuSans.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    ]
    candidates_latin_bold = [
        FONTS_DIR / "DejaVuSans-Bold.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ]

    def _first_existing(paths):
        for p in paths:
            if p.exists():
                return p
        return None

    ar_path = _first_existing(candidates_ar)
    ar_bold_path = _first_existing(candidates_ar_bold)
    latin_path = _first_existing(candidates_latin)
    latin_bold_path = _first_existing(candidates_latin_bold)

    if ar_path:
        pdfmetrics.registerFont(TTFont("Arabic", str(ar_path)))
    if ar_bold_path:
        pdfmetrics.registerFont(TTFont("Arabic-Bold", str(ar_bold_path)))
    if latin_path:
        pdfmetrics.registerFont(TTFont("Latin", str(latin_path)))
    if latin_bold_path:
        pdfmetrics.registerFont(TTFont("Latin-Bold", str(latin_bold_path)))

    _fonts_registered = True


def _shape_arabic(text: str) -> str:
    """Reshape Arabic text and apply the bidi algorithm for correct display."""
    if not text:
        return ""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


def _html_to_paragraphs(html: str, language: str) -> list[str]:
    """Convert TipTap HTML to a list of paragraph strings.

    For Arabic content, we shape each paragraph for RTL display.
    """
    if not html or not html.strip():
        return []

    soup = BeautifulSoup(html, "html.parser")

    paragraphs: list[str] = []

    # Handle block-level elements
    for block in soup.find_all(["p", "h1", "h2", "h3", "li", "blockquote"]):
        text = block.get_text(" ", strip=True)
        if not text:
            continue
        tag = block.name
        if language == "ar":
            text = _shape_arabic(text)
        if tag == "h1":
            paragraphs.append(("__H1__", text))
        elif tag == "h2":
            paragraphs.append(("__H2__", text))
        elif tag == "h3":
            paragraphs.append(("__H3__", text))
        elif tag == "blockquote":
            paragraphs.append(("__QUOTE__", text))
        elif tag == "li":
            paragraphs.append(("__LI__", text))
        else:
            paragraphs.append(("__P__", text))

    # If no block-level elements found, fall back to raw text
    if not paragraphs:
        text = soup.get_text(" ", strip=True)
        if text:
            if language == "ar":
                text = _shape_arabic(text)
            paragraphs.append(("__P__", text))

    return paragraphs


# --- Page decoration -------------------------------------------------------

def _draw_cover_decoration(canvas_obj, doc, language: str):
    """Draw the cover page background decoration."""
    width, height = A4

    # Top band
    canvas_obj.setFillColor(PRIMARY)
    canvas_obj.rect(0, height - 4 * cm, width, 4 * cm, fill=1, stroke=0)

    # Gold accent line under the band
    canvas_obj.setFillColor(SECONDARY)
    canvas_obj.rect(0, height - 4.2 * cm, width, 0.2 * cm, fill=1, stroke=0)

    # Bottom band (small)
    canvas_obj.setFillColor(PRIMARY)
    canvas_obj.rect(0, 0, width, 1.5 * cm, fill=1, stroke=0)
    canvas_obj.setFillColor(SECONDARY)
    canvas_obj.rect(0, 1.5 * cm, width, 0.1 * cm, fill=1, stroke=0)

    # Decorative circles (very subtle)
    canvas_obj.setStrokeColor(SECONDARY)
    canvas_obj.setLineWidth(0.7)
    canvas_obj.circle(width / 2, height / 2 - 1 * cm, 6 * cm, stroke=1, fill=0)
    canvas_obj.circle(width / 2, height / 2 - 1 * cm, 5 * cm, stroke=1, fill=0)


def _draw_content_header(canvas_obj, doc, title: str, language: str):
    width, height = A4
    # Header bar
    canvas_obj.setFillColor(PRIMARY)
    canvas_obj.rect(0, height - 1.6 * cm, width, 1.6 * cm, fill=1, stroke=0)
    canvas_obj.setFillColor(SECONDARY)
    canvas_obj.rect(0, height - 1.7 * cm, width, 0.1 * cm, fill=1, stroke=0)

    # Title text in header
    font = "Arabic-Bold" if language == "ar" else "Latin-Bold"
    try:
        canvas_obj.setFont(font, 11)
    except Exception:
        canvas_obj.setFont("Helvetica-Bold", 11)
    canvas_obj.setFillColor(Color(1, 1, 1))

    display_title = _shape_arabic(title) if language == "ar" else title
    if language == "ar":
        canvas_obj.drawRightString(width - 2 * cm, height - 1.05 * cm, display_title)
    else:
        canvas_obj.drawString(2 * cm, height - 1.05 * cm, display_title)

    # Footer
    canvas_obj.setFillColor(SECONDARY)
    canvas_obj.rect(0, 1 * cm, width, 0.08 * cm, fill=1, stroke=0)
    try:
        canvas_obj.setFont("Latin", 9)
    except Exception:
        canvas_obj.setFont("Helvetica", 9)
    canvas_obj.setFillColor(MUTED)
    page_num = canvas_obj.getPageNumber()
    canvas_obj.drawCentredString(width / 2, 0.5 * cm, f"— {page_num} —")


# --- Main PDF generation --------------------------------------------------

def generate_pdf(
    title: str,
    imam_name: Optional[str],
    sermon_date: Optional[str],
    html_content: str,
    language: str,
    output_path: Path,
):
    """Generate a styled PDF file for a sermon in the given language.

    language: 'ar', 'fr' or 'en'
    """
    _register_fonts()

    is_rtl = language == "ar"
    body_font = "Arabic" if is_rtl else "Latin"
    body_font_bold = "Arabic-Bold" if is_rtl else "Latin-Bold"

    # Fallback to Helvetica if fonts didn't register
    available = pdfmetrics.getRegisteredFontNames()
    if body_font not in available:
        body_font = "Helvetica"
    if body_font_bold not in available:
        body_font_bold = "Helvetica-Bold"

    alignment_body = TA_RIGHT if is_rtl else TA_JUSTIFY

    # Styles
    title_style = ParagraphStyle(
        "Title",
        fontName=body_font_bold,
        fontSize=28,
        leading=34,
        textColor=Color(1, 1, 1),
        alignment=TA_CENTER,
        spaceAfter=12,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        fontName=body_font,
        fontSize=14,
        leading=18,
        textColor=Color(1, 1, 1),
        alignment=TA_CENTER,
    )
    cover_meta_style = ParagraphStyle(
        "CoverMeta",
        fontName=body_font,
        fontSize=12,
        leading=16,
        textColor=DARK,
        alignment=TA_CENTER,
        spaceAfter=6,
    )
    h1_style = ParagraphStyle(
        "H1",
        fontName=body_font_bold,
        fontSize=18,
        leading=24,
        textColor=PRIMARY,
        alignment=TA_RIGHT if is_rtl else TA_LEFT,
        spaceBefore=14,
        spaceAfter=8,
    )
    h2_style = ParagraphStyle(
        "H2",
        fontName=body_font_bold,
        fontSize=15,
        leading=20,
        textColor=PRIMARY,
        alignment=TA_RIGHT if is_rtl else TA_LEFT,
        spaceBefore=10,
        spaceAfter=6,
    )
    h3_style = ParagraphStyle(
        "H3",
        fontName=body_font_bold,
        fontSize=12,
        leading=16,
        textColor=SECONDARY,
        alignment=TA_RIGHT if is_rtl else TA_LEFT,
        spaceBefore=8,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "Body",
        fontName=body_font,
        fontSize=12,
        leading=20,
        textColor=DARK,
        alignment=alignment_body,
        spaceAfter=8,
        firstLineIndent=0 if is_rtl else 14,
        wordWrap="RTL" if is_rtl else None,
    )
    quote_style = ParagraphStyle(
        "Quote",
        fontName=body_font,
        fontSize=12,
        leading=20,
        textColor=PRIMARY,
        alignment=TA_CENTER,
        leftIndent=24,
        rightIndent=24,
        spaceBefore=8,
        spaceAfter=8,
        borderPadding=6,
    )
    li_style = ParagraphStyle(
        "Li",
        parent=body_style,
        leftIndent=20,
        firstLineIndent=0,
        bulletIndent=8,
    )

    # Build document
    buffer = BytesIO()
    doc = BaseDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2.2 * cm,
        rightMargin=2.2 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2 * cm,
        title=title,
        author=imam_name or "Prêches de l'imam",
    )

    # Cover frame: full page
    cover_frame = Frame(
        0, 0, A4[0], A4[1],
        leftPadding=2.5 * cm, rightPadding=2.5 * cm,
        topPadding=5 * cm, bottomPadding=3 * cm,
        id="cover",
    )
    content_frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        A4[0] - doc.leftMargin - doc.rightMargin,
        A4[1] - doc.topMargin - doc.bottomMargin,
        id="content",
    )

    def on_cover(c, d):
        _draw_cover_decoration(c, d, language)

    def on_content(c, d):
        _draw_content_header(c, d, title, language)

    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[cover_frame], onPage=on_cover),
        PageTemplate(id="content", frames=[content_frame], onPage=on_content),
    ])

    story = []

    # --- Cover page ---
    label_map = {
        "ar": "خُطبة",
        "fr": "Prêche",
        "en": "Sermon",
    }
    by_map = {"ar": "الإمام", "fr": "Imam", "en": "Imam"}
    date_label = {"ar": "التاريخ", "fr": "Date", "en": "Date"}

    cover_label = label_map.get(language, "Prêche")
    if is_rtl:
        cover_label = _shape_arabic(cover_label)

    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph(cover_label, subtitle_style))
    story.append(Spacer(1, 0.5 * cm))

    display_title = _shape_arabic(title) if is_rtl else title
    story.append(Paragraph(display_title, title_style))
    story.append(Spacer(1, 3 * cm))

    if imam_name:
        imam_text = f"{by_map.get(language, 'Imam')} : {imam_name}"
        if is_rtl:
            imam_text = _shape_arabic(imam_text)
        story.append(Paragraph(imam_text, cover_meta_style))

    if sermon_date:
        date_text = f"{date_label.get(language, 'Date')} : {sermon_date}"
        if is_rtl:
            date_text = _shape_arabic(date_text)
        story.append(Paragraph(date_text, cover_meta_style))

    # Generation footer note
    story.append(Spacer(1, 6 * cm))
    gen_text = f"Document généré le {datetime.now().strftime('%d/%m/%Y')}"
    if language == "en":
        gen_text = f"Document generated on {datetime.now().strftime('%Y-%m-%d')}"
    elif is_rtl:
        gen_text = _shape_arabic(
            f"تم إنشاء المستند في {datetime.now().strftime('%Y/%m/%d')}"
        )
    story.append(Paragraph(
        gen_text,
        ParagraphStyle("Gen", parent=cover_meta_style, fontSize=9, textColor=MUTED),
    ))

    # Switch to content template
    from reportlab.platypus import NextPageTemplate
    story.append(NextPageTemplate("content"))
    story.append(PageBreak())

    # --- Body ---
    paragraphs = _html_to_paragraphs(html_content, language)
    if not paragraphs:
        empty_msg = {
            "ar": _shape_arabic("لا يوجد محتوى بعد."),
            "fr": "Aucun contenu pour le moment.",
            "en": "No content yet.",
        }.get(language, "")
        story.append(Paragraph(empty_msg, body_style))
    else:
        for kind, text in paragraphs:
            if kind == "__H1__":
                story.append(Paragraph(text, h1_style))
            elif kind == "__H2__":
                story.append(Paragraph(text, h2_style))
            elif kind == "__H3__":
                story.append(Paragraph(text, h3_style))
            elif kind == "__QUOTE__":
                story.append(Paragraph(f"« {text} »", quote_style))
            elif kind == "__LI__":
                bullet = "•"
                story.append(Paragraph(f"{bullet}  {text}", li_style))
            else:
                story.append(Paragraph(text, body_style))

    doc.build(story)
    return output_path
