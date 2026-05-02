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
  metricsOriginal?: {
    grade?: string;
    fleschReadingEase?: number;
    wordCount?: number;
    avgSentenceLength?: number;
  };
  metricsSimplified?: {
    grade?: string;
    fleschReadingEase?: number;
    wordCount?: number;
    avgSentenceLength?: number;
  };
}

export async function exportSimplificationPDF(data: SimplificationData) {
  const doc = new jsPDF();
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const margin = 20;
  const contentWidth = pageWidth - margin * 2;
  let yPos = 20;

  const checkPage = (need: number) => {
    if (yPos + need > pageHeight - 25) {
      doc.addPage();
      yPos = 25;
    }
  };

  // Header bar
  doc.setFillColor(59, 130, 246);
  doc.rect(0, 0, pageWidth, 36, 'F');
  doc.setTextColor(255, 255, 255);
  doc.setFontSize(22);
  doc.setFont('helvetica', 'bold');
  doc.text('ClarityWorks', pageWidth / 2, 18, { align: 'center' });
  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  doc.text('Text Rewrite Report', pageWidth / 2, 28, { align: 'center' });

  yPos = 50;

  // Target grade
  doc.setTextColor(31, 41, 55);
  doc.setFontSize(14);
  doc.setFont('helvetica', 'bold');
  doc.text(`Target Grade Level: Grade ${data.targetGrade}`, pageWidth / 2, yPos, { align: 'center' });
  yPos += 7;
  doc.setFontSize(9);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(100, 116, 139);
  doc.text(`Generated on ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}`, pageWidth / 2, yPos, { align: 'center' });
  yPos += 15;

  // Metrics comparison (if available)
  if (data.metricsOriginal && data.metricsSimplified) {
    doc.setFontSize(12);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(31, 41, 55);
    doc.text('Metrics Comparison', margin, yPos);
    yPos += 8;

    const metricsRows: string[][] = [];
    if (data.metricsOriginal.grade && data.metricsSimplified.grade) {
      metricsRows.push(['Grade Level', data.metricsOriginal.grade, data.metricsSimplified.grade]);
    }
    if (data.metricsOriginal.fleschReadingEase != null && data.metricsSimplified.fleschReadingEase != null) {
      metricsRows.push(['Flesch Reading Ease', data.metricsOriginal.fleschReadingEase.toFixed(1), data.metricsSimplified.fleschReadingEase.toFixed(1)]);
    }
    if (data.metricsOriginal.wordCount != null && data.metricsSimplified.wordCount != null) {
      metricsRows.push(['Word Count', data.metricsOriginal.wordCount.toString(), data.metricsSimplified.wordCount.toString()]);
    }
    if (data.metricsOriginal.avgSentenceLength != null && data.metricsSimplified.avgSentenceLength != null) {
      metricsRows.push(['Avg Sentence Length', data.metricsOriginal.avgSentenceLength.toFixed(1), data.metricsSimplified.avgSentenceLength.toFixed(1)]);
    }

    if (metricsRows.length > 0) {
      autoTable(doc, {
        startY: yPos,
        head: [['Metric', 'Original', 'Rewritten']],
        body: metricsRows,
        headStyles: { fillColor: [59, 130, 246], fontSize: 9, fontStyle: 'bold' },
        styles: { fontSize: 9.5, cellPadding: 3.5 },
        alternateRowStyles: { fillColor: [250, 251, 253] },
        columnStyles: { 0: { fontStyle: 'bold' } },
      });
      yPos = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 12;
    }
  }

  // Original Text
  checkPage(40);
  doc.setFontSize(12);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(220, 38, 38);
  doc.text('Original Text', margin, yPos);
  yPos += 7;

  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(31, 41, 55);
  const originalLines = doc.splitTextToSize(data.originalText, contentWidth);
  originalLines.forEach((line: string) => {
    checkPage(6);
    doc.text(line, margin, yPos);
    yPos += 5;
  });
  yPos += 8;

  // Simplified Text
  checkPage(40);
  doc.setFontSize(12);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(20, 184, 166);
  doc.text('Rewritten Text', margin, yPos);
  yPos += 7;

  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(31, 41, 55);
  const simplifiedLines = doc.splitTextToSize(data.simplifiedText, contentWidth);
  simplifiedLines.forEach((line: string) => {
    checkPage(6);
    doc.text(line, margin, yPos);
    yPos += 5;
  });
  yPos += 10;

  // Changes Table
  if (data.changes && data.changes.length > 0) {
    checkPage(30);
    doc.setFontSize(12);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(31, 41, 55);
    doc.text(`Changes Applied (${data.changes.length})`, margin, yPos);
    yPos += 8;

    autoTable(doc, {
      startY: yPos,
      head: [['Type', 'Original', 'Replacement', 'Reason']],
      body: data.changes.map(c => [
        c.type.replace(/_/g, ' '),
        c.original,
        c.simplified,
        c.reason
      ]),
      headStyles: { fillColor: [59, 130, 246], fontSize: 8.5, fontStyle: 'bold' },
      styles: { fontSize: 8, cellPadding: 3, overflow: 'linebreak' },
      alternateRowStyles: { fillColor: [250, 251, 253] },
      columnStyles: {
        0: { cellWidth: 25 },
        1: { cellWidth: 30 },
        2: { cellWidth: 30 },
        3: { cellWidth: 'auto' },
      },
    });
  }

  // Footer
  const totalPages = doc.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);
    doc.setFontSize(7.5);
    doc.setTextColor(160, 170, 180);
    doc.text(
      `Page ${i} of ${totalPages}  |  ClarityWorks Rewrite Report`,
      pageWidth / 2, pageHeight - 8, { align: 'center' }
    );
  }

  doc.save(`simplification-grade-${data.targetGrade}.pdf`);
}

export async function exportSimplificationDOCX(data: SimplificationData) {
  const children: Paragraph[] = [
    new Paragraph({
      text: 'ClarityWorks - Text Rewrite Report',
      heading: HeadingLevel.HEADING_1,
      alignment: AlignmentType.CENTER,
      spacing: { after: 200 }
    }),
    new Paragraph({
      text: `Target Grade Level: Grade ${data.targetGrade}`,
      alignment: AlignmentType.CENTER,
      spacing: { after: 100 }
    }),
    new Paragraph({
      text: `Generated on ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}`,
      alignment: AlignmentType.CENTER,
      spacing: { after: 400 }
    }),
  ];

  // Metrics comparison
  if (data.metricsOriginal && data.metricsSimplified) {
    children.push(
      new Paragraph({ text: 'Metrics Comparison', heading: HeadingLevel.HEADING_2, spacing: { before: 200, after: 100 } })
    );

    const metricsEntries: [string, string, string][] = [];
    if (data.metricsOriginal.grade && data.metricsSimplified.grade) {
      metricsEntries.push(['Grade Level', data.metricsOriginal.grade, data.metricsSimplified.grade]);
    }
    if (data.metricsOriginal.fleschReadingEase != null && data.metricsSimplified.fleschReadingEase != null) {
      metricsEntries.push(['Flesch Score', data.metricsOriginal.fleschReadingEase.toFixed(1), data.metricsSimplified.fleschReadingEase.toFixed(1)]);
    }

    metricsEntries.forEach(([metric, orig, rewr]) => {
      children.push(new Paragraph({
        children: [
          new TextRun({ text: `${metric}: `, bold: true }),
          new TextRun({ text: `${orig} → ${rewr}` }),
        ],
        spacing: { after: 60 },
      }));
    });
  }

  children.push(
    new Paragraph({ text: 'Original Text', heading: HeadingLevel.HEADING_2, spacing: { before: 300, after: 100 } }),
    new Paragraph({ text: data.originalText, spacing: { after: 400 } }),
    new Paragraph({ text: 'Rewritten Text', heading: HeadingLevel.HEADING_2, spacing: { before: 200, after: 100 } }),
    new Paragraph({ text: data.simplifiedText, spacing: { after: 400 } }),
    new Paragraph({ text: `Changes Applied (${data.changes?.length || 0})`, heading: HeadingLevel.HEADING_2, spacing: { before: 200, after: 100 } }),
  );

  (data.changes || []).forEach(change => {
    children.push(
      new Paragraph({
        children: [
          new TextRun({ text: `${change.type.replace(/_/g, ' ').toUpperCase()}: `, bold: true }),
          new TextRun({ text: `"${change.original}" → "${change.simplified}"` }),
        ],
        spacing: { after: 40 },
      }),
      new Paragraph({
        children: [
          new TextRun({ text: `Reason: ${change.reason}`, italics: true }),
        ],
        spacing: { after: 140 },
      })
    );
  });

  const docx = new Document({ sections: [{ properties: {}, children }] });
  const blob = await Packer.toBlob(docx);
  saveAs(blob, `simplification-grade-${data.targetGrade}.docx`);
}
