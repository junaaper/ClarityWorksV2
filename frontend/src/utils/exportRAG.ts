import jsPDF from 'jspdf';
import { Document, Paragraph, HeadingLevel, AlignmentType, Packer } from 'docx';
import { saveAs } from 'file-saver';

interface RAGResult {
  text: string;
  metadata: {
    chunk_id: number;
    page_number?: number;
    word_count: number;
  };
  similarity_score: number;
  collection: string;
}

interface RAGExportData {
  query: string;
  answer?: string | null;
  results: RAGResult[];
  documentNames: string[];
}

export async function exportRAGResultsPDF(data: RAGExportData) {
  const doc = new jsPDF();
  let yPos = 20;

  // Title
  doc.setFontSize(20);
  doc.setFont('helvetica', 'bold');
  doc.text('ClarityWorks - RAG Query Results', 105, yPos, { align: 'center' });
  yPos += 15;

  // Query
  doc.setFontSize(12);
  doc.setFont('helvetica', 'bold');
  doc.text('Query:', 20, yPos);
  yPos += 7;

  doc.setFont('helvetica', 'italic');
  doc.setFontSize(11);
  const queryLines = doc.splitTextToSize(`"${data.query}"`, 170);
  doc.text(queryLines, 20, yPos);
  yPos += (queryLines.length * 5) + 10;

  // AI-Generated Answer
  if (data.answer) {
    if (yPos > 240) {
      doc.addPage();
      yPos = 20;
    }

    doc.setFontSize(14);
    doc.setFont('helvetica', 'bold');
    doc.text('AI-Generated Answer:', 20, yPos);
    yPos += 10;

    doc.setFontSize(10);
    doc.setFont('helvetica', 'normal');
    const answerLines = doc.splitTextToSize(data.answer, 170);
    doc.text(answerLines, 20, yPos);
    yPos += (answerLines.length * 5) + 15;
  }

  // Documents Searched
  if (yPos > 250) {
    doc.addPage();
    yPos = 20;
  }

  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  doc.text(`Documents searched: ${data.documentNames.join(', ')}`, 20, yPos);
  yPos += 7;

  doc.text(`Sources retrieved: ${data.results.length}`, 20, yPos);
  yPos += 15;

  // Source Documents
  doc.setFontSize(12);
  doc.setFont('helvetica', 'bold');
  doc.text('Source Documents:', 20, yPos);
  yPos += 10;

  data.results.forEach((result, index) => {
    if (yPos > 250) {
      doc.addPage();
      yPos = 20;
    }

    // Source header
    doc.setFontSize(11);
    doc.setFont('helvetica', 'bold');
    doc.text(`Source ${index + 1}`, 20, yPos);
    yPos += 7;

    // Metadata
    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    doc.text(
      `Page: ${result.metadata.page_number || 'N/A'} | Similarity: ${(result.similarity_score * 100).toFixed(1)}% | Words: ${result.metadata.word_count}`,
      20,
      yPos
    );
    yPos += 7;

    // Text
    doc.setFontSize(10);
    const textLines = doc.splitTextToSize(result.text, 170);
    doc.text(textLines, 20, yPos);
    yPos += (textLines.length * 5) + 10;
  });

  doc.save('rag-query-results.pdf');
}

export async function exportRAGResultsDOCX(data: RAGExportData) {
  const children: (typeof Paragraph extends new (...args: never[]) => infer R ? R : never)[] = [
    // Title
    new Paragraph({
      text: 'ClarityWorks - RAG Query Results',
      heading: HeadingLevel.HEADING_1,
      alignment: AlignmentType.CENTER,
      spacing: { after: 200 }
    }),

    // Query
    new Paragraph({
      text: 'Query',
      heading: HeadingLevel.HEADING_2,
      spacing: { before: 200, after: 100 }
    }),

    new Paragraph({
      text: `"${data.query}"`,
      spacing: { after: 200 }
    }),
  ];

  // AI-Generated Answer
  if (data.answer) {
    children.push(
      new Paragraph({
        text: 'AI-Generated Answer',
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 300, after: 100 }
      }),

      new Paragraph({
        text: data.answer,
        spacing: { after: 400 }
      })
    );
  }

  // Metadata
  children.push(
    new Paragraph({
      text: `Documents searched: ${data.documentNames.join(', ')}`,
      spacing: { before: 200, after: 100 }
    }),

    new Paragraph({
      text: `Sources retrieved: ${data.results.length}`,
      spacing: { after: 400 }
    }),

    // Source Documents Header
    new Paragraph({
      text: 'Source Documents',
      heading: HeadingLevel.HEADING_2,
      spacing: { before: 300, after: 200 }
    })
  );

  // Add sources
  data.results.forEach((result, index) => {
    children.push(
      new Paragraph({
        text: `Source ${index + 1}`,
        heading: HeadingLevel.HEADING_3,
        spacing: { before: 300, after: 100 }
      }),

      new Paragraph({
        text: `Page: ${result.metadata.page_number || 'N/A'} | Similarity: ${(result.similarity_score * 100).toFixed(1)}% | Words: ${result.metadata.word_count}`,
        spacing: { after: 100 }
      }),

      new Paragraph({
        text: result.text,
        spacing: { after: 200 }
      })
    );
  });

  const doc = new Document({
    sections: [{ properties: {}, children }]
  });

  const blob = await Packer.toBlob(doc);
  saveAs(blob, 'rag-query-results.docx');
}
