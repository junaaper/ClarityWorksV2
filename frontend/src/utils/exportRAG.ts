import jsPDF from 'jspdf';
import { Document, Paragraph, TextRun, HeadingLevel, AlignmentType, Packer } from 'docx';
import { saveAs } from 'file-saver';

interface RAGResult {
  text: string;
  metadata: {
    chunk_id: number;
    page_number?: number;
    word_count: number;
  };
  similarity_score: number;
  semantic_score?: number;
  keyword_score?: number;
  relevance_score?: number;
  relevance_label?: string;
  rerank_score?: number;
  collection: string;
}

interface RAGExportData {
  query: string;
  answer?: string | null;
  results: RAGResult[];
  documentNames: string[];
}

const semanticScore = (result: RAGResult) => result.semantic_score ?? result.similarity_score ?? 0;
const relevanceScore = (result: RAGResult) =>
  result.relevance_score ?? result.rerank_score ?? result.similarity_score ?? 0;
const relevanceLabel = (result: RAGResult) => {
  if (result.relevance_label) return result.relevance_label;
  const score = relevanceScore(result);
  if (score >= 0.65) return 'Strong';
  if (score >= 0.35) return 'Moderate';
  return 'Weak';
};
const sourceMeta = (result: RAGResult) =>
  `${relevanceLabel(result)} relevance (${(relevanceScore(result) * 100).toFixed(0)}%)  |  Semantic ${(semanticScore(result) * 100).toFixed(1)}%  |  ${result.metadata.word_count} words${result.metadata.page_number ? `  |  Page ${result.metadata.page_number}` : ''}`;

export async function exportRAGResultsPDF(data: RAGExportData) {
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

  // Header
  doc.setFillColor(20, 184, 166);
  doc.rect(0, 0, pageWidth, 36, 'F');
  doc.setTextColor(255, 255, 255);
  doc.setFontSize(22);
  doc.setFont('helvetica', 'bold');
  doc.text('ClarityWorks', pageWidth / 2, 18, { align: 'center' });
  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  doc.text('Textbook Query Results', pageWidth / 2, 28, { align: 'center' });

  yPos = 50;

  // Query
  doc.setFontSize(12);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(31, 41, 55);
  doc.text('Query', margin, yPos);
  yPos += 7;

  doc.setFont('helvetica', 'italic');
  doc.setFontSize(11);
  doc.setTextColor(71, 85, 105);
  const queryLines = doc.splitTextToSize(`"${data.query}"`, contentWidth);
  doc.text(queryLines, margin, yPos);
  yPos += queryLines.length * 5.5 + 8;

  // Metadata
  doc.setFontSize(9);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(100, 116, 139);
  doc.text(`Documents searched: ${data.documentNames.join(', ')}`, margin, yPos);
  yPos += 5;
  doc.text(`Sources retrieved: ${data.results.length}  |  ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}`, margin, yPos);
  yPos += 12;

  // Answer
  if (data.answer) {
    checkPage(30);
    doc.setDrawColor(20, 184, 166);
    doc.setLineWidth(0.8);
    doc.line(margin, yPos, margin + 40, yPos);
    doc.setLineWidth(0.2);
    yPos += 6;

    doc.setFontSize(13);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(31, 41, 55);
    doc.text('Answer', margin, yPos);
    yPos += 8;

    doc.setFontSize(10);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(31, 41, 55);
    const answerLines = doc.splitTextToSize(data.answer, contentWidth);
    answerLines.forEach((line: string) => {
      checkPage(6);
      doc.text(line, margin, yPos);
      yPos += 5;
    });
    yPos += 12;
  }

  // Source Documents
  checkPage(20);
  doc.setDrawColor(59, 130, 246);
  doc.setLineWidth(0.8);
  doc.line(margin, yPos, margin + 40, yPos);
  doc.setLineWidth(0.2);
  yPos += 6;

  doc.setFontSize(13);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(31, 41, 55);
  doc.text('Source Documents', margin, yPos);
  yPos += 10;

  data.results.forEach((result, index) => {
    checkPage(35);

    // Source header
    doc.setFillColor(245, 247, 250);
    doc.roundedRect(margin, yPos - 3, contentWidth, 10, 2, 2, 'F');

    doc.setFontSize(10);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(59, 130, 246);
    doc.text(`Source ${index + 1}`, margin + 4, yPos + 3);

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8);
    doc.setTextColor(100, 116, 139);
    const meta = sourceMeta(result);
    doc.text(meta, margin + contentWidth - 4, yPos + 3, { align: 'right' });
    yPos += 12;

    // Text
    doc.setFontSize(9.5);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(31, 41, 55);
    const textLines = doc.splitTextToSize(result.text, contentWidth - 8);
    textLines.forEach((line: string) => {
      checkPage(5);
      doc.text(line, margin + 4, yPos);
      yPos += 4.5;
    });
    yPos += 10;
  });

  // Footer
  const totalPages = doc.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);
    doc.setFontSize(7.5);
    doc.setTextColor(160, 170, 180);
    doc.text(
      `Page ${i} of ${totalPages}  |  ClarityWorks Textbook Query`,
      pageWidth / 2, pageHeight - 8, { align: 'center' }
    );
  }

  doc.save('rag-query-results.pdf');
}

export async function exportRAGResultsDOCX(data: RAGExportData) {
  const children: Paragraph[] = [
    new Paragraph({
      text: 'ClarityWorks - Textbook Query Results',
      heading: HeadingLevel.HEADING_1,
      alignment: AlignmentType.CENTER,
      spacing: { after: 200 }
    }),

    new Paragraph({ text: 'Query', heading: HeadingLevel.HEADING_2, spacing: { before: 200, after: 100 } }),
    new Paragraph({ children: [new TextRun({ text: `"${data.query}"`, italics: true })], spacing: { after: 100 } }),

    new Paragraph({
      children: [new TextRun({ text: `Documents: ${data.documentNames.join(', ')}  |  Sources: ${data.results.length}`, color: '64748b' })],
      spacing: { after: 300 },
    }),
  ];

  if (data.answer) {
    children.push(
      new Paragraph({ text: 'Answer', heading: HeadingLevel.HEADING_2, spacing: { before: 300, after: 100 } }),
      new Paragraph({ text: data.answer, spacing: { after: 400 } })
    );
  }

  children.push(
    new Paragraph({ text: 'Source Documents', heading: HeadingLevel.HEADING_2, spacing: { before: 300, after: 200 } })
  );

  data.results.forEach((result, index) => {
    children.push(
      new Paragraph({
        text: `Source ${index + 1}`,
        heading: HeadingLevel.HEADING_3,
        spacing: { before: 300, after: 60 }
      }),
      new Paragraph({
        children: [
          new TextRun({
            text: sourceMeta(result),
            color: '64748b',
            size: 18,
          }),
        ],
        spacing: { after: 80 },
      }),
      new Paragraph({ text: result.text, spacing: { after: 200 } })
    );
  });

  const docx = new Document({ sections: [{ properties: {}, children }] });
  const blob = await Packer.toBlob(docx);
  saveAs(blob, 'rag-query-results.docx');
}
