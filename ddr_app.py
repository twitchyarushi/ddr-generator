import streamlit as st
import fitz  # PyMuPDF
from groq import Groq
import tempfile
import os
import json
from PIL import Image
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
import base64
import re

# ── CONFIG ──────────────────────────────────────────────────────────────────
DEFAULT_API_KEY = os.getenv("GROQ_API_KEY", "")

st.set_page_config(page_title="DDR Report Generator", page_icon="🏗️", layout="centered")

st.sidebar.header("Settings")
groq_key = st.sidebar.text_input(
    "Groq API key",
    value=DEFAULT_API_KEY,
    type="password",
    help="Paste your Groq API key here"
)

if not groq_key:
    st.sidebar.warning("Enter your Groq API key to start.")
    st.stop()

client = Groq(api_key=groq_key)

# ── PDF EXTRACTION ───────────────────────────────────────────────────────────
def extract_from_pdf(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    full_text = ""
    images = []

    for page_num, page in enumerate(doc):
        full_text += f"\n[Page {page_num + 1}]\n"
        full_text += page.get_text()

        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            img_bytes = base_image["image"]
            img_ext = base_image["ext"]

            try:
                pil_img = Image.open(io.BytesIO(img_bytes))
                if pil_img.width > 50 and pil_img.height > 50:
                    images.append({
                        "page": page_num + 1,
                        "index": img_index,
                        "bytes": img_bytes,
                        "ext": img_ext,
                        "size": (pil_img.width, pil_img.height)
                    })
            except Exception:
                pass

    doc.close()
    return full_text, images

# ── CLAUDE AI ────────────────────────────────────────────────────────────────
def generate_ddr_with_claude(inspection_text, thermal_text):
    prompt = f"""
You are an expert property inspector writing a professional DDR (Detailed Diagnostic Report) for a client.

You have been given two documents:
1. INSPECTION REPORT - Contains site observations and issue descriptions
2. THERMAL REPORT - Contains temperature readings and thermal findings

Your job is to merge both documents and generate a structured DDR report in valid JSON format.

INSPECTION REPORT:
{inspection_text[:8000]}

THERMAL REPORT:
{thermal_text[:8000]}

Generate a JSON response with EXACTLY this structure:
{{
  "property_name": "extracted property name or Not Available",
  "report_date": "extracted date or Not Available",
  "property_issue_summary": "2-3 sentence overview of all issues found",
  "area_observations": [
    {{
      "area": "area name",
      "observation": "what was observed",
      "thermal_finding": "thermal reading if available or Not Available",
      "image_keyword": "keyword to match relevant image e.g. roof, wall, crack"
    }}
  ],
  "probable_root_causes": [
    "root cause 1",
    "root cause 2"
  ],
  "severity_assessment": [
    {{
      "issue": "issue name",
      "severity": "High/Medium/Low",
      "reasoning": "why this severity"
    }}
  ],
  "recommended_actions": [
    {{
      "action": "what to do",
      "priority": "Immediate/Short-term/Long-term"
    }}
  ],
  "additional_notes": "any extra observations or Not Available",
  "missing_information": [
    "missing item 1 or write None if nothing is missing"
  ]
}}

RULES:
- Do NOT invent facts
- If information is missing write "Not Available"
- If information conflicts mention the conflict
- Use simple client-friendly language
- Return ONLY valid JSON, no extra text
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'^```', '', raw)
    raw = re.sub(r'```$', '', raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        raise RuntimeError(f"Failed to parse JSON: {e}\nRaw output:\n{raw}")
        
# ── PDF REPORT BUILDER ───────────────────────────────────────────────────────
def build_pdf_report(ddr_data, all_images, output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Title'],
        fontSize=22,
        textColor=colors.HexColor('#1a1a2e'),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#666666'),
        spaceAfter=4,
        alignment=TA_CENTER
    )

    section_style = ParagraphStyle(
        'Section',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=colors.white,
        spaceBefore=16,
        spaceAfter=8,
        fontName='Helvetica-Bold',
        backColor=colors.HexColor('#1a1a2e'),
        leftIndent=-6,
        rightIndent=-6,
        borderPad=6
    )

    subsection_style = ParagraphStyle(
        'Subsection',
        parent=styles['Heading2'],
        fontSize=11,
        textColor=colors.HexColor('#1a1a2e'),
        spaceBefore=10,
        spaceAfter=4,
        fontName='Helvetica-Bold'
    )

    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#333333'),
        spaceAfter=4,
        leading=15,
        alignment=TA_JUSTIFY
    )

    label_style = ParagraphStyle(
        'Label',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#888888'),
        spaceAfter=2,
        fontName='Helvetica-Bold'
    )

    story = []

    # ── HEADER ──
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("DETAILED DIAGNOSTIC REPORT", title_style))
    story.append(Paragraph("DDR — Property Inspection & Thermal Analysis", subtitle_style))
    story.append(Spacer(1, 0.1 * inch))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1a1a2e')))
    story.append(Spacer(1, 0.1 * inch))

    # Property info table
    info_data = [
        [Paragraph("<b>Property</b>", body_style), Paragraph(ddr_data.get("property_name", "Not Available"), body_style)],
        [Paragraph("<b>Report Date</b>", body_style), Paragraph(ddr_data.get("report_date", "Not Available"), body_style)],
    ]
    info_table = Table(info_data, colWidths=[1.5 * inch, 5 * inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.2 * inch))

    # ── 1. PROPERTY ISSUE SUMMARY ──
    story.append(Paragraph("1. Property Issue Summary", section_style))
    story.append(Paragraph(ddr_data.get("property_issue_summary", "Not Available"), body_style))
    story.append(Spacer(1, 0.1 * inch))

    # ── 2. AREA-WISE OBSERVATIONS ──
    story.append(Paragraph("2. Area-wise Observations", section_style))

    area_obs = ddr_data.get("area_observations", [])
    for i, obs in enumerate(area_obs):
        area_name = obs.get("area", "Unknown Area")
        story.append(Paragraph(f"▶ {area_name}", subsection_style))

        obs_data = [
            [Paragraph("<b>Observation</b>", label_style), Paragraph(obs.get("observation", "Not Available"), body_style)],
            [Paragraph("<b>Thermal Finding</b>", label_style), Paragraph(obs.get("thermal_finding", "Not Available"), body_style)],
        ]
        obs_table = Table(obs_data, colWidths=[1.3 * inch, 5.2 * inch])
        obs_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f7f7f7')),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e0e0e0')),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(obs_table)

        # Match image
        keyword = obs.get("image_keyword", "").lower()
        matched_image = None
        if keyword and all_images:
            for img in all_images:
                if keyword in str(img.get("page", "")).lower():
                    matched_image = img
                    break
            if not matched_image and i < len(all_images):
                matched_image = all_images[i]

        if matched_image:
            try:
                img_io = io.BytesIO(matched_image["bytes"])
                pil_img = Image.open(img_io)
                if pil_img.mode in ("RGBA", "P"):
                    pil_img = pil_img.convert("RGB")
                tmp_img_path = tempfile.mktemp(suffix=".jpg")
                pil_img.save(tmp_img_path, "JPEG")
                max_w = 4.5 * inch
                max_h = 2.5 * inch
                w, h = pil_img.size
                ratio = min(max_w / w, max_h / h)
                rl_img = RLImage(tmp_img_path, width=w * ratio, height=h * ratio)
                story.append(Spacer(1, 0.05 * inch))
                story.append(rl_img)
                story.append(Paragraph(f"<i>Figure: {area_name}</i>", label_style))
            except Exception:
                story.append(Paragraph("<i>Image Not Available</i>", label_style))
        else:
            story.append(Paragraph("<i>Image Not Available</i>", label_style))

        story.append(Spacer(1, 0.1 * inch))

    # ── 3. PROBABLE ROOT CAUSES ──
    story.append(Paragraph("3. Probable Root Causes", section_style))
    for cause in ddr_data.get("probable_root_causes", ["Not Available"]):
        story.append(Paragraph(f"• {cause}", body_style))
    story.append(Spacer(1, 0.1 * inch))

    # ── 4. SEVERITY ASSESSMENT ──
    story.append(Paragraph("4. Severity Assessment", section_style))
    severity_list = ddr_data.get("severity_assessment", [])
    if severity_list:
        sev_data = [[
            Paragraph("<b>Issue</b>", label_style),
            Paragraph("<b>Severity</b>", label_style),
            Paragraph("<b>Reasoning</b>", label_style)
        ]]
        for s in severity_list:
            sev = s.get("severity", "").upper()
            if sev == "HIGH":
                sev_color = colors.HexColor('#cc0000')
            elif sev == "MEDIUM":
                sev_color = colors.HexColor('#e67e00')
            else:
                sev_color = colors.HexColor('#27ae60')

            sev_data.append([
                Paragraph(s.get("issue", ""), body_style),
                Paragraph(f"<b>{sev}</b>", ParagraphStyle('Sev', parent=body_style, textColor=sev_color)),
                Paragraph(s.get("reasoning", ""), body_style)
            ])
        sev_table = Table(sev_data, colWidths=[2 * inch, 1 * inch, 3.5 * inch])
        sev_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#dddddd')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(sev_table)
    story.append(Spacer(1, 0.1 * inch))

    # ── 5. RECOMMENDED ACTIONS ──
    story.append(Paragraph("5. Recommended Actions", section_style))
    actions = ddr_data.get("recommended_actions", [])
    if actions:
        act_data = [[
            Paragraph("<b>Action</b>", label_style),
            Paragraph("<b>Priority</b>", label_style)
        ]]
        for a in actions:
            pri = a.get("priority", "")
            if pri == "Immediate":
                pri_color = colors.HexColor('#cc0000')
            elif pri == "Short-term":
                pri_color = colors.HexColor('#e67e00')
            else:
                pri_color = colors.HexColor('#27ae60')

            act_data.append([
                Paragraph(a.get("action", ""), body_style),
                Paragraph(f"<b>{pri}</b>", ParagraphStyle('Pri', parent=body_style, textColor=pri_color))
            ])
        act_table = Table(act_data, colWidths=[5 * inch, 1.5 * inch])
        act_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#dddddd')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(act_table)
    story.append(Spacer(1, 0.1 * inch))

    # ── 6. ADDITIONAL NOTES ──
    story.append(Paragraph("6. Additional Notes", section_style))
    story.append(Paragraph(ddr_data.get("additional_notes", "Not Available"), body_style))
    story.append(Spacer(1, 0.1 * inch))

    # ── 7. MISSING / UNCLEAR INFORMATION ──
    story.append(Paragraph("7. Missing or Unclear Information", section_style))
    missing = ddr_data.get("missing_information", ["None"])
    for m in missing:
        story.append(Paragraph(f"• {m}", body_style))

    # ── FOOTER ──
    story.append(Spacer(1, 0.3 * inch))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cccccc')))
    story.append(Paragraph(
        "This report was generated by an AI-assisted DDR system. Please verify findings with a qualified inspector.",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
    ))

    doc.build(story)

st.title("🏗️ DDR Report Generator")
st.markdown("Upload your **Inspection Report** and **Thermal Report** to generate a professional PDF DDR.")
st.markdown("---")

col1, col2 = st.columns(2)
with col1:
    inspection_file = st.file_uploader("📋 Inspection Report (PDF)", type=["pdf"])
with col2:
    thermal_file = st.file_uploader("🌡️ Thermal Report (PDF)", type=["pdf"])

if inspection_file and thermal_file:
    if st.button("⚡ Generate DDR Report", use_container_width=True, type="primary"):
        with st.spinner("Extracting data from documents..."):
            inspection_text, inspection_images = extract_from_pdf(inspection_file.read())
            thermal_text, thermal_images = extract_from_pdf(thermal_file.read())
            all_images = inspection_images + thermal_images

        with st.spinner("Analysing report with Groq..."):
            try:
                ddr_data = generate_ddr_with_claude(inspection_text, thermal_text)
                st.success("✅ Analysis complete!")
            except Exception as e:
                st.error(f"AI Error: {e}")
                st.stop()

        with st.spinner("Building PDF report..."):
            output_path = tempfile.mktemp(suffix=".pdf")
            build_pdf_report(ddr_data, all_images, output_path)

        with open(output_path, "rb") as f:
            pdf_bytes = f.read()

        st.markdown("---")
        st.subheader("📄 Report Summary")

        # Human‑readable summary instead of raw JSON
        st.markdown(f"**Property**: {ddr_data.get('property_name', 'Not Available')}")
        st.markdown(f"**Report date**: {ddr_data.get('report_date', 'Not Available')}")
        st.markdown("**Overall summary**:")
        st.write(ddr_data.get("property_issue_summary", "Not Available"))

        st.markdown("**Key area observations:**")
        for obs in ddr_data.get("area_observations", [])[:5]:
            area = obs.get("area", "Unknown area")
            observation = obs.get("observation", "Not Available")
            thermal = obs.get("thermal_finding", "Not Available")
            st.markdown(f"- **{area}** – {observation}  \n  *Thermal:* {thermal}")

        st.markdown("**Top recommended actions:**")
        for action in ddr_data.get("recommended_actions", [])[:5]:
            txt = action.get("action", "Not Available")
            pri = action.get("priority", "Not Available")
            st.markdown(f"- **{pri}** – {txt}")

        st.download_button(
            label="⬇️ Download DDR Report (PDF)",
            data=pdf_bytes,
            file_name="DDR_Report.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary"
        )
else:
    st.info("👆 Please upload both PDF files to get started.")