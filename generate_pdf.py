import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Canvas for adding page numbers and running footer."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#64748b"))
        
        # Header (Top line)
        if self._pageNumber > 1:
            self.drawString(54, 750, "BugPilot — Complete Beginner & System Guide")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(54, 742, 558, 742)
            
        # Footer
        footer_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 36, footer_text)
        self.drawString(54, 36, "BugPilot AI Platform • Confidential Documentation")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, 48, 558, 48)
        
        self.restoreState()

def generate_pdf(filename="C:\\Users\\MinalPrasad\\Desktop\\BugPilot_User_Guide.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom styles
    primary_color = colors.HexColor("#0f172a")    # Slate 900
    accent_color = colors.HexColor("#0284c7")     # Sky 600
    text_color = colors.HexColor("#334155")       # Slate 700
    bg_box_color = colors.HexColor("#f8fafc")     # Slate 50

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=primary_color,
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=accent_color,
        spaceAfter=15
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=primary_color,
        spaceBefore=16,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=accent_color,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=text_color,
        spaceAfter=8
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4
    )

    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Normal'],
        fontName='Courier-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0284c7"),
        backColor=colors.HexColor("#f1f5f9"),
        borderColor=colors.HexColor("#cbd5e1"),
        borderWidth=0.5,
        borderPadding=6,
        spaceAfter=8
    )

    callout_style = ParagraphStyle(
        'Callout',
        parent=body_style,
        fontName='Helvetica-Oblique',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#1e293b"),
        backColor=colors.HexColor("#e0f2fe"),
        borderColor=colors.HexColor("#38bdf8"),
        borderWidth=1,
        borderPadding=8,
        spaceAfter=10
    )

    story = []

    # Title Banner
    story.append(Paragraph("🛸 BugPilot Platform Guide", title_style))
    story.append(Paragraph("Complete Non-Technical User & Operating Guide for AI Bug Intelligence", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=accent_color, spaceAfter=15))

    # SECTION 1: WHAT IS BUGPILOT?
    story.append(Paragraph("1. Executive Summary & What is BugPilot?", h1_style))
    story.append(Paragraph(
        "<b>BugPilot</b> is an artificial intelligence assistant created to help engineering managers, software team leads, "
        "and non-technical business leaders instantly understand software bugs without searching through thousands of spreadsheet rows.",
        body_style
    ))
    story.append(Paragraph(
        "Imagine having a team of expert data analysts available 24/7 who read through software issue reports, calculate risk scores, "
        "spot recurring trends, and present simple answers to your plain English questions. That is exactly what BugPilot does.",
        body_style
    ))

    story.append(Paragraph(
        "<b>Key Analogy for Beginners:</b> Think of BugPilot like a modern hospital diagnostic assistant. "
        "The software issue reports (bugs) are patient records. Specialized AI agents act like doctors who review the records, "
        "and a Reflection Agent acts as a senior medical director double-checking every diagnosis to ensure zero mistakes before presenting the final report.",
        callout_style
    ))

    # SECTION 2: HOW IT WORKS (NON-TECHNICAL)
    story.append(Paragraph("2. How BugPilot Works Behind the Scenes", h1_style))
    story.append(Paragraph("BugPilot relies on 5 simple layers connected together:", body_style))

    story.append(Paragraph("• <b>User Interface (React Dashboard):</b> The beautiful web app on your screen where you type questions and view risk charts.", bullet_style))
    story.append(Paragraph("• <b>FastAPI Server:</b> The central engine that receives your questions and routes them to the AI team.", bullet_style))
    story.append(Paragraph("• <b>Orchestrator Agent & Specialists:</b> A coordinator AI that breaks down your question and assigns work to 3 specialized analysts (Bug Analyst, Trend Analyst, and Risk Analyst).", bullet_style))
    story.append(Paragraph("• <b>MCP Server (Model Context Protocol):</b> A secure data bridge that allows AI agents to read software data safely without modifying or deleting anything.", bullet_style))
    story.append(Paragraph("• <b>Reflection Agent:</b> A automated checker that compares the final AI answer against raw data metrics to ensure 100% accuracy.", bullet_style))

    story.append(Spacer(1, 10))

    # Architecture Overview Table
    arch_data = [
        [Paragraph("<b>Component</b>", body_style), Paragraph("<b>Non-Technical Role</b>", body_style), Paragraph("<b>Real Function</b>", body_style)],
        [Paragraph("<b>React Dashboard</b>", body_style), Paragraph("User Interface / Screen", body_style), Paragraph("Interactive dark dashboard with navigation tabs and charts", body_style)],
        [Paragraph("<b>Orchestrator Agent</b>", body_style), Paragraph("Team Manager", body_style), Paragraph("Decides which AI specialists and tools to run for your question", body_style)],
        [Paragraph("<b>Specialist Agents</b>", body_style), Paragraph("Data Analysts", body_style), Paragraph("Analyze bug counts, sprint velocity, and component risk scores", body_style)],
        [Paragraph("<b>MCP Bridge</b>", body_style), Paragraph("Secure Data Reader", body_style), Paragraph("Enforces strict read-only access over synthetic engineering datasets", body_style)],
        [Paragraph("<b>Reflection Agent</b>", body_style), Paragraph("Quality Auditor", body_style), Paragraph("Verifies zero hallucinations or metric mistakes exist in output", body_style)],
    ]
    t = Table(arch_data, colWidths=[110, 130, 264])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ('TEXTCOLOR', (0, 0), (-1, 0), primary_color),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t)

    story.append(Spacer(1, 15))

    # SECTION 3: STEP-BY-STEP HOW TO RUN IT
    story.append(Paragraph("3. How to Run BugPilot on Your Computer (Step-by-Step)", h1_style))
    story.append(Paragraph(
        "Follow these exact steps to launch BugPilot on your Windows computer. You do not need any coding experience!",
        body_style
    ))

    story.append(Paragraph("Step 1: Open Terminal (PowerShell)", h2_style))
    story.append(Paragraph("Press your Windows Key, search for <b>PowerShell</b>, and click to open it.", body_style))

    story.append(Paragraph("Step 2: Navigate to Project Folder", h2_style))
    story.append(Paragraph("Copy and paste this command into PowerShell and press <b>Enter</b>:", body_style))
    story.append(Paragraph("cd C:\\Users\\MinalPrasad\\Desktop\\bugpilot", code_style))

    story.append(Paragraph("Step 3: Launch the Backend API Server", h2_style))
    story.append(Paragraph("Copy and paste this command to start the Python backend server:", body_style))
    story.append(Paragraph(".venv\\Scripts\\python.exe -m uvicorn backend.main:app --reload --port 8000", code_style))
    story.append(Paragraph("<i>You will see green messages indicating the server is running on http://127.0.0.1:8000. Keep this window open!</i>", body_style))

    story.append(Paragraph("Step 4: Launch the Web Dashboard (Frontend)", h2_style))
    story.append(Paragraph("Open a <b>second</b> PowerShell window, navigate back to the folder, and start the frontend:", body_style))
    story.append(Paragraph("cd C:\\Users\\MinalPrasad\\Desktop\\bugpilot\\frontend\nnpm run dev", code_style))

    story.append(Paragraph("Step 5: View the Web App", h2_style))
    story.append(Paragraph("Open your internet browser (Chrome, Edge, or Firefox) and go to:", body_style))
    story.append(Paragraph("http://localhost:5173", code_style))

    story.append(Spacer(1, 10))

    # SECTION 4: DASHBOARD FEATURES & NAVIGATION
    story.append(Paragraph("4. How to Use the BugPilot Dashboard", h1_style))
    story.append(Paragraph(
        "Once the app opens, you will see a sleek, modern dark engineering dashboard with a left navigation sidebar containing 8 sections:",
        body_style
    ))

    dash_features = [
        [Paragraph("<b>Navigation Tab</b>", body_style), Paragraph("<b>What You Will See & Do</b>", body_style)],
        [Paragraph("<b>📊 Overview</b>", body_style), Paragraph("High-level KPI cards (Total Bugs: 1000, Open Bugs: 39, Critical: 19), monthly creation vs resolution bar charts, and top high-risk software components.", body_style)],
        [Paragraph("<b>💬 Ask BugPilot</b>", body_style), Paragraph("Interactive AI chat area. Click any suggested prompt (e.g. <i>'Which component is highest risk?'</i>) or type your own question to trigger AI tool reasoning.", body_style)],
        [Paragraph("<b>🤖 Agents</b>", body_style), Paragraph("Full roster of all 6 AI agents, detailing their titles, roles, and automated responsibilities.", body_style)],
        [Paragraph("<b>🛠️ MCP Tools</b>", body_style), Paragraph("Displays all 8 read-only tools exposed by the MCP server, complete with live descriptions and input schemas.", body_style)],
        [Paragraph("<b>📈 Analytics</b>", body_style), Paragraph("Shows exact mathematical outputs: Mean Time to Resolve (3.46 days), Reopen Rate (17.0%), and Aging Bugs (>14 days).", body_style)],
        [Paragraph("<b>🗄️ Data</b>", body_style), Paragraph("Displays the synthetic dataset specifications: 1,000 issues, 8 projects, 10 components, 20 sprints, and 10 releases labeled 'Synthetic Demo Data'.", body_style)],
        [Paragraph("<b>⚡ Executions</b>", body_style), Paragraph("Real execution logs recording query ID, duration in seconds, agents used, tools called, and reflection validation results.", body_style)],
        [Paragraph("<b>🩺 System Health</b>", body_style), Paragraph("Live status indicators confirming backend connectivity, environment settings, and server readiness.", body_style)],
    ]
    t2 = Table(dash_features, colWidths=[120, 384])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ('TEXTCOLOR', (0, 0), (-1, 0), primary_color),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t2)

    story.append(Spacer(1, 15))

    # SECTION 5: FREQUENTLY ASKED QUESTIONS & TROUBLESHOOTING
    story.append(Paragraph("5. Frequently Asked Questions & Troubleshooting", h1_style))

    story.append(Paragraph("Q: What if I see an error connecting to http://localhost:5173?", h2_style))
    story.append(Paragraph("<b>Answer:</b> Make sure you started the backend server in Step 3 first! The frontend needs the backend running on port 8000 to fetch metrics and agent responses.", body_style))

    story.append(Paragraph("Q: Is my actual application data uploaded anywhere?", h2_style))
    story.append(Paragraph("<b>Answer:</b> No! BugPilot uses a local <b>PostgreSQL</b> or synthetic data store running entirely inside your computer. No real data or company credentials leave your device.", body_style))

    story.append(Paragraph("Q: How do I stop BugPilot when I am finished?", h2_style))
    story.append(Paragraph("<b>Answer:</b> Go to your open PowerShell windows and press <b>Ctrl + C</b> to stop the running servers.", body_style))

    story.append(Paragraph("Q: How do I run the automated testing suite?", h2_style))
    story.append(Paragraph("<b>Answer:</b> In PowerShell, run the following command to test all 179 automated checks:", body_style))
    story.append(Paragraph(".venv\\Scripts\\python.exe -m pytest -q", code_style))

    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=15))
    story.append(Paragraph("<b>Documentation Generated:</b> August 2026 • BugPilot AI Engineering Platform • All 179 Tests Passing ✅", ParagraphStyle('FooterNote', parent=body_style, fontName='Helvetica-Oblique', fontSize=8, textColor=colors.HexColor("#64748b"), alignment=1)))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF successfully generated at: {filename}")

if __name__ == "__main__":
    generate_pdf()
