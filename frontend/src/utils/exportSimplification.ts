import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import { Document, Paragraph, TextRun, HeadingLevel, AlignmentType, Packer } from 'docx';
import { saveAs } from 'file-saver';

interface SimplificationData {
  originalText: string;
  simplifiedText: string;
  targetGrade: number;
  changes: Array<{
    type: string;
    original: string;
    simplified: string;
    reason: string;
  }>;
  metricsOriginal?: any;
  metricsSimplified?: any;
}

export async function exportSimplificationPDF(data: SimplificationData) {
  const doc = new jsPDF();
  let yPos = 20;

  // Title
  doc.setFontSize(20);
  doc.setFont('helvetica', 'bold');
  doc.text('ClarityWorks - Text Simplification Report', 105, yPos, { align: 'center' });
  yPos += 15;

  // Subtitle
  doc.setFontSize(12);
  doc.setFont('helvetica', 'normal');
  doc.text(`Target Grade Level: Grade ${data.targetGrade}`, 105, yPos, { align: 'center' });
  yPos += 15;

  // Original Text Section
  doc.setFontSize(14);
  doc.setFont('helvetica', 'bold');
  doc.text('Original Text', 20, yPos);
  yPos += 8;

  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  const originalLines = doc.splitTextToSize(data.originalText, 170);
  doc.text(originalLines, 20, yPos);
  yPos += (originalLines.length * 5) + 10;

  // Check if need new page
  if (yPos > 250) {
    doc.addPage();
    yPos = 20;
  }

  // Simplified Text Section
  doc.setFontSize(14);
  doc.setFont('helvetica', 'bold');
  doc.text('Simplified Text', 20, yPos);
  yPos += 8;

  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  const simplifiedLines = doc.splitTextToSize(data.simplifiedText, 170);
  doc.text(simplifiedLines, 20, yPos);
  yPos += (simplifiedLines.length * 5) + 10;

  if (yPos > 250) {
    doc.addPage();
    yPos = 20;
  }

  // Changes Table
  if (data.changes && data.changes.length > 0) {
    doc.setFontSize(14);
    doc.setFont('helvetica', 'bold');
    doc.text('Changes Applied', 20, yPos);
    yPos += 10;

    const changesData = data.changes.map(c => [
      c.type.replace('_', ' ').toUpperCase(),
      c.original,
      c.simplified,
      c.reason
    ]);

    autoTable(doc, {
      head: [['Type', 'Original', 'Simplified', 'Reason']],
      body: changesData,
      startY: yPos,
      styles: { fontSize: 8 },
      headStyles: { fillColor: [59, 130, 246] }
    });
  }

  // Save
  doc.save(`simplification-grade-${data.targetGrade}.pdf`);
}

export async function exportSimplificationDOCX(data: SimplificationData) {
  const doc = new Document({
    sections: [{
      properties: {},
      children: [
        // Title
        new Paragraph({
          text: 'ClarityWorks - Text Simplification Report',
          heading: HeadingLevel.HEADING_1,
          alignment: AlignmentType.CENTER,
          spacing: { after: 200 }
        }),

        new Paragraph({
          text: `Target Grade Level: Grade ${data.targetGrade}`,
          alignment: AlignmentType.CENTER,
          spacing: { after: 400 }
        }),

        // Original Text
        new Paragraph({
          text: 'Original Text',
          heading: HeadingLevel.HEADING_2,
          spacing: { before: 200, after: 100 }
        }),

        new Paragraph({
          text: data.originalText,
          spacing: { after: 400 }
        }),

        // Simplified Text
        new Paragraph({
          text: 'Simplified Text',
          heading: HeadingLevel.HEADING_2,
          spacing: { before: 200, after: 100 }
        }),

        new Paragraph({
          text: data.simplifiedText,
          spacing: { after: 400 }
        }),

        // Changes
        new Paragraph({
          text: 'Changes Applied',
          heading: HeadingLevel.HEADING_2,
          spacing: { before: 200, after: 100 }
        }),

        ...(data.changes || []).flatMap(change => [
          new Paragraph({
            children: [
              new TextRun({
                text: `${change.type.replace('_', ' ').toUpperCase()}: `,
                bold: true
              }),
              new TextRun({
                text: `"${change.original}" -> "${change.simplified}"`
              })
            ]
          }),
          new Paragraph({
            text: `Reason: ${change.reason}`,
            spacing: { after: 100 }
          })
        ])
      ]
    }]
  });

  const blob = await Packer.toBlob(doc);
  saveAs(blob, `simplification-grade-${data.targetGrade}.docx`);
}
