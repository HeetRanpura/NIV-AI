"""
PDF report generator using ReportLab.
Takes PresentationOutput and VerdictOutput, generates a structured PDF.
Five pages: risk & verdict, scenario comparison, cash flow, behavioral flags, action items.
Returns PDF as bytes. No AI. No Firebase. Pure rendering.
"""
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak,
)
from schemas.schemas import PresentationOutput, VerdictOutput


# Brand colors
BRAND_BLUE = colors.HexColor("#1a56db")
BRAND_DARK = colors.HexColor("#111827")
SAFE_GREEN = colors.HexColor("#059669")
CAUTION_AMBER = colors.HexColor("#d97706")
RISK_RED = colors.HexColor("#dc2626")
LIGHT_BG = colors.HexColor("#f9fafb")
BORDER = colors.HexColor("#d1d5db")


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("Title2", parent=s["Title"], fontSize=22, textColor=BRAND_DARK, spaceAfter=4))
    s.add(ParagraphStyle("H2", parent=s["Heading2"], fontSize=14, textColor=BRAND_BLUE, spaceBefore=16, spaceAfter=8))
    s.add(ParagraphStyle("Body", parent=s["BodyText"], fontSize=10, leading=14, textColor=BRAND_DARK))
    s.add(ParagraphStyle("Small", parent=s["BodyText"], fontSize=8, textColor=colors.gray))
    return s


def generate_pdf(
    session_id: str,
    presentation_output: PresentationOutput,
    verdict_output: VerdictOutput,
) -> bytes:
    """
    Generates a structured PDF report.
    Returns PDF as bytes ready for GCS upload or direct download.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm, leftMargin=18*mm, rightMargin=18*mm)
    styles = _styles()
    story = []

    pdf = presentation_output.pdf_content

    # --- Title ---
    story.append(Paragraph("Home Buying Advisor — Analysis Report", styles["Title2"]))
    story.append(Paragraph(
        f"Prepared for <b>{pdf.user_name}</b> &nbsp;|&nbsp; "
        f"Session {pdf.session_id[:8]}… &nbsp;|&nbsp; {pdf.generated_at}",
        styles["Small"],
    ))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER))
    story.append(Spacer(1, 4))

    # --- Page 1: Risk Score & Verdict ---
    story.append(Paragraph(pdf.risk_score_section.title, styles["H2"]))
    for para in pdf.risk_score_section.content.split("\n\n"):
        cleaned = para.strip().replace("\n", "<br/>")
        if cleaned:
            story.append(Paragraph(cleaned, styles["Body"]))
            story.append(Spacer(1, 4))
    story.append(PageBreak())

    # --- Page 2: Scenario Comparison ---
    story.append(Paragraph(pdf.scenario_section.title, styles["H2"]))
    for para in pdf.scenario_section.content.split("\n\n"):
        cleaned = para.strip().replace("\n", "<br/>")
        if cleaned:
            story.append(Paragraph(cleaned, styles["Body"]))
            story.append(Spacer(1, 4))
    story.append(PageBreak())

    # --- Page 3: Cash Flow Summary ---
    story.append(Paragraph(pdf.cash_flow_section.title, styles["H2"]))
    for para in pdf.cash_flow_section.content.split("\n\n"):
        cleaned = para.strip().replace("\n", "<br/>")
        if cleaned:
            story.append(Paragraph(cleaned, styles["Body"]))
            story.append(Spacer(1, 4))
    story.append(PageBreak())

    # --- Page 4: Behavioral Flags & Assumptions ---
    story.append(Paragraph(pdf.behavioral_section.title, styles["H2"]))
    for para in pdf.behavioral_section.content.split("\n\n"):
        cleaned = para.strip().replace("\n", "<br/>")
        if cleaned:
            story.append(Paragraph(cleaned, styles["Body"]))
            story.append(Spacer(1, 4))
    story.append(PageBreak())

    # --- Page 5: Action Items ---
    story.append(Paragraph(pdf.action_items_section.title, styles["H2"]))
    for para in pdf.action_items_section.content.split("\n\n"):
        cleaned = para.strip().replace("\n", "<br/>")
        if cleaned:
            story.append(Paragraph(cleaned, styles["Body"]))
            story.append(Spacer(1, 4))

    # --- Footer / Disclaimer ---
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Paragraph(
        "This report is for informational purposes only and does not constitute financial advice. "
        "Consult a certified financial advisor before making any property purchase decisions.",
        styles["Small"],
    ))
    story.append(Paragraph(
        "Powered by NIV AI — aligned with UN SDG 1 (No Poverty) and SDG 10 (Reduced Inequalities).",
        styles["Small"],
    ))

    doc.build(story)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes
