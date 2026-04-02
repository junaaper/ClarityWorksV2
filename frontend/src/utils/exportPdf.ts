import { jsPDF } from 'jspdf';
import type { Analysis } from '../types';

interface ExportData {
  title: string;
  createdAt: string;
  analysis: Analysis;
  originalText?: string;
}

export const exportAnalysisToPdf = (data: ExportData): void => {
  const doc = new jsPDF();
  const pageWidth = doc.internal.pageSize.getWidth();
  const margin = 20;
  const contentWidth = pageWidth - (margin * 2);
  let yPosition = 20;

  // Helper function to add a new page if needed
  const checkPageBreak = (requiredSpace: number) => {
    if (yPosition + requiredSpace > doc.internal.pageSize.getHeight() - 20) {
      doc.addPage();
      yPosition = 20;
    }
  };

  // Title
  doc.setFontSize(24);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(79, 70, 229); // Primary color
  doc.text('ClarityWorks', margin, yPosition);
  yPosition += 10;

  doc.setFontSize(12);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(107, 114, 128); // Gray
  doc.text('Text Readability Analysis Report', margin, yPosition);
  yPosition += 15;

  // Report Title
  doc.setFontSize(18);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(31, 41, 55);
  const titleLines = doc.splitTextToSize(data.title || 'Untitled Analysis', contentWidth);
  doc.text(titleLines, margin, yPosition);
  yPosition += titleLines.length * 8 + 5;

  // Date
  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(107, 114, 128);
  doc.text(`Generated: ${new Date(data.createdAt).toLocaleString()}`, margin, yPosition);
  yPosition += 15;

  // Horizontal line
  doc.setDrawColor(229, 231, 235);
  doc.line(margin, yPosition, pageWidth - margin, yPosition);
  yPosition += 10;

  // Summary Section
  doc.setFontSize(14);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(31, 41, 55);
  doc.text('Summary', margin, yPosition);
  yPosition += 10;

  // Summary cards as a grid
  const summaryItems = [
    { label: 'Grade Level', value: data.analysis.predictions.predicted_grade_level },
    { label: 'Complexity', value: data.analysis.predictions.predicted_complexity },
    { label: 'Flesch Ease', value: data.analysis.readability_scores.flesch_reading_ease.toFixed(1) },
    { label: 'Confidence', value: `${(data.analysis.predictions.confidence * 100).toFixed(0)}%` },
  ];

  doc.setFontSize(10);
  summaryItems.forEach((item, index) => {
    const xPos = margin + (index % 2) * (contentWidth / 2);
    const yPos = yPosition + Math.floor(index / 2) * 20;

    doc.setFont('helvetica', 'normal');
    doc.setTextColor(107, 114, 128);
    doc.text(item.label, xPos, yPos);

    doc.setFont('helvetica', 'bold');
    doc.setTextColor(31, 41, 55);
    doc.text(item.value, xPos, yPos + 6);
  });
  yPosition += 45;

  // Horizontal line
  doc.setDrawColor(229, 231, 235);
  doc.line(margin, yPosition, pageWidth - margin, yPosition);
  yPosition += 10;

  // Text Statistics Section
  checkPageBreak(60);
  doc.setFontSize(14);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(31, 41, 55);
  doc.text('Text Statistics', margin, yPosition);
  yPosition += 10;

  const textStats = [
    { label: 'Word Count', value: data.analysis.basic_metrics.word_count.toLocaleString() },
    { label: 'Sentence Count', value: data.analysis.basic_metrics.sentence_count.toString() },
    { label: 'Paragraph Count', value: data.analysis.basic_metrics.paragraph_count.toString() },
    { label: 'Avg. Words per Sentence', value: data.analysis.basic_metrics.avg_sentence_length.toFixed(1) },
    { label: 'Avg. Syllables per Word', value: data.analysis.basic_metrics.avg_syllables_per_word.toFixed(2) },
    { label: 'Difficult Words', value: `${data.analysis.statistics.difficult_words_count} (${data.analysis.statistics.difficult_words_percentage.toFixed(1)}%)` },
  ];

  doc.setFontSize(10);
  textStats.forEach((stat, index) => {
    const xPos = margin + (index % 2) * (contentWidth / 2);
    const yPos = yPosition + Math.floor(index / 2) * 12;

    doc.setFont('helvetica', 'normal');
    doc.setTextColor(107, 114, 128);
    doc.text(stat.label + ':', xPos, yPos);

    doc.setFont('helvetica', 'bold');
    doc.setTextColor(31, 41, 55);
    doc.text(stat.value, xPos + 60, yPos);
  });
  yPosition += Math.ceil(textStats.length / 2) * 12 + 10;

  // Horizontal line
  checkPageBreak(80);
  doc.setDrawColor(229, 231, 235);
  doc.line(margin, yPosition, pageWidth - margin, yPosition);
  yPosition += 10;

  // Readability Scores Section
  doc.setFontSize(14);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(31, 41, 55);
  doc.text('Readability Scores', margin, yPosition);
  yPosition += 10;

  const readabilityScores = [
    {
      name: 'Flesch Reading Ease',
      score: data.analysis.readability_scores.flesch_reading_ease.toFixed(2),
      description: '0-100 scale, higher = easier',
    },
    {
      name: 'Flesch-Kincaid Grade',
      score: data.analysis.readability_scores.flesch_kincaid_grade.toFixed(2),
      description: 'US grade level needed',
    },
    {
      name: 'Automated Readability Index',
      score: data.analysis.readability_scores.automated_readability_index.toFixed(2),
      description: 'US grade level estimate',
    },
    {
      name: 'SMOG Index',
      score: data.analysis.readability_scores.smog_readability.toFixed(2),
      description: 'Years of education needed',
    },
    {
      name: 'Coleman-Liau Index',
      score: data.analysis.readability_scores.coleman_liau_index.toFixed(2),
      description: 'US grade level estimate',
    },
  ];

  // Table header
  doc.setFillColor(249, 250, 251);
  doc.rect(margin, yPosition - 3, contentWidth, 10, 'F');
  doc.setFontSize(9);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(107, 114, 128);
  doc.text('Metric', margin + 2, yPosition + 3);
  doc.text('Score', margin + 80, yPosition + 3);
  doc.text('Interpretation', margin + 110, yPosition + 3);
  yPosition += 12;

  // Table rows
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(31, 41, 55);
  readabilityScores.forEach((item) => {
    checkPageBreak(10);
    doc.text(item.name, margin + 2, yPosition);
    doc.text(item.score, margin + 80, yPosition);
    doc.setTextColor(107, 114, 128);
    doc.text(item.description, margin + 110, yPosition);
    doc.setTextColor(31, 41, 55);
    yPosition += 8;
  });
  yPosition += 10;

  // Difficult Words Section
  if (data.analysis.difficult_elements.difficult_words.length > 0) {
    checkPageBreak(60);
    doc.setDrawColor(229, 231, 235);
    doc.line(margin, yPosition, pageWidth - margin, yPosition);
    yPosition += 10;

    doc.setFontSize(14);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(31, 41, 55);
    doc.text('Difficult Words (Top 10)', margin, yPosition);
    yPosition += 10;

    doc.setFontSize(9);
    const topWords = data.analysis.difficult_elements.difficult_words.slice(0, 10);

    topWords.forEach((word, index) => {
      checkPageBreak(8);
      doc.setFont('helvetica', 'bold');
      doc.text(`${index + 1}. ${word.word}`, margin, yPosition);
      doc.setFont('helvetica', 'normal');
      doc.setTextColor(107, 114, 128);
      doc.text(`(${word.syllables} syllables) - ${word.reason}`, margin + 50, yPosition);
      doc.setTextColor(31, 41, 55);
      yPosition += 7;
    });
    yPosition += 10;
  }

  // Difficult Sentences Section
  if (data.analysis.difficult_elements.difficult_sentences.length > 0) {
    checkPageBreak(60);
    doc.setDrawColor(229, 231, 235);
    doc.line(margin, yPosition, pageWidth - margin, yPosition);
    yPosition += 10;

    doc.setFontSize(14);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(31, 41, 55);
    doc.text('Difficult Sentences', margin, yPosition);
    yPosition += 10;

    doc.setFontSize(9);
    const sentences = data.analysis.difficult_elements.difficult_sentences.slice(0, 5);

    sentences.forEach((sentence, index) => {
      checkPageBreak(25);
      doc.setFont('helvetica', 'bold');
      doc.text(`${index + 1}. `, margin, yPosition);

      doc.setFont('helvetica', 'normal');
      const truncatedSentence = sentence.sentence.length > 150
        ? sentence.sentence.substring(0, 150) + '...'
        : sentence.sentence;
      const sentenceLines = doc.splitTextToSize(truncatedSentence, contentWidth - 10);
      doc.text(sentenceLines, margin + 8, yPosition);
      yPosition += sentenceLines.length * 4 + 2;

      doc.setTextColor(107, 114, 128);
      doc.text(`Reason: ${sentence.reason} | Words: ${sentence.word_count} | Flesch: ${sentence.flesch_score}`, margin + 8, yPosition);
      doc.setTextColor(31, 41, 55);
      yPosition += 10;
    });
  }

  // Footer
  const pageCount = doc.getNumberOfPages();
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    doc.setFontSize(8);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(156, 163, 175);
    doc.text(
      `Page ${i} of ${pageCount} | Generated by ClarityWorks`,
      pageWidth / 2,
      doc.internal.pageSize.getHeight() - 10,
      { align: 'center' }
    );
  }

  // Save the PDF
  const fileName = `clarityworks-analysis-${data.title?.replace(/[^a-z0-9]/gi, '-').toLowerCase() || 'report'}-${new Date().toISOString().split('T')[0]}.pdf`;
  doc.save(fileName);
};
