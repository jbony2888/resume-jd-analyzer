"""PDF generation for tailored résumés based on gap analysis."""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER


class ResumePDFGenerator:
    """Generates tailored résumé PDFs based on gap analysis recommendations."""

    def __init__(self, output_path: str | Path):
        self.output_path = Path(output_path)

    def generate_from_analysis(
        self,
        original_resume_text: str,
        gap_analysis: str | dict,
        recommendations_section: bool = True,
        keywords_section: bool = True,
    ) -> Path:
        """
        Generate a PDF résumé with suggestions based on gap analysis.

        Args:
            original_resume_text: The original résumé content.
            gap_analysis: Output from GapAnalyzer.analyze() (text or structured dict).
            recommendations_section: Whether to add a "Tailoring Recommendations" section.
            keywords_section: Whether to add "Keywords to Add" section.

        Returns:
            Path to the generated PDF file.
        """
        doc = SimpleDocTemplate(
            str(self.output_path),
            pagesize=letter,
            rightMargin=inch,
            leftMargin=inch,
            topMargin=inch,
            bottomMargin=inch,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=18,
            spaceAfter=12,
            alignment=TA_CENTER,
        )
        heading_style = ParagraphStyle(
            "CustomHeading",
            parent=styles["Heading2"],
            fontSize=12,
            spaceBefore=12,
            spaceAfter=6,
        )
        body_style = styles["Normal"]

        story = []

        # Title
        story.append(Paragraph("Résumé – Tailored Version", title_style))
        story.append(Spacer(1, 0.2 * inch))

        # Original résumé content (preserve line breaks)
        story.append(Paragraph("Original Content", heading_style))
        for block in original_resume_text.split("\n\n"):
            if block.strip():
                story.append(Paragraph(block.replace("\n", "<br/>"), body_style))
        story.append(Spacer(1, 0.3 * inch))

        if recommendations_section or keywords_section:
            story.append(PageBreak())
            story.append(Paragraph("Tailoring Recommendations", title_style))
            story.append(Spacer(1, 0.2 * inch))

        if isinstance(gap_analysis, dict):
            if keywords_section and gap_analysis.get("keywords_to_add"):
                story.append(Paragraph("Keywords to Add", heading_style))
                for kw in gap_analysis["keywords_to_add"]:
                    story.append(Paragraph(f"• {kw}", body_style))
                story.append(Spacer(1, 0.2 * inch))

            if recommendations_section and gap_analysis.get("recommendations"):
                story.append(Paragraph("Action Items", heading_style))
                for rec in gap_analysis["recommendations"]:
                    story.append(Paragraph(f"• {rec}", body_style))

            if gap_analysis.get("fit_score") is not None:
                story.append(Spacer(1, 0.2 * inch))
                score = gap_analysis.get("fit_score", "N/A")
                justification = gap_analysis.get("fit_justification", "")
                story.append(
                    Paragraph(f"<b>Fit Score:</b> {score}/10 – {justification}", body_style)
                )
        elif isinstance(gap_analysis, str) and recommendations_section:
            story.append(Paragraph("Full Analysis", heading_style))
            for block in gap_analysis.split("\n\n"):
                if block.strip():
                    story.append(Paragraph(block.replace("\n", "<br/>"), body_style))

        doc.build(story)
        return self.output_path
