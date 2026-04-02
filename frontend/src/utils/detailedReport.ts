import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import {
  calculateComplexityScore,
  ComplexityScoreInputs
} from './complexityScore';
import {
  calculateReadingTime
} from './readingTime';
import {
  generateImprovementSuggestions,
  SuggestionInput
} from './improvementSuggestions';
import {
  analyzeVocabulary
} from './vocabularyAnalysis';

/**
 * Detailed PDF Report Generator
 *
 * Generates a comprehensive multi-page PDF report with:
 * - Cover page with executive summary
 * - Readability scores and metrics
 * - Text complexity visualization
 * - Improvement suggestions
 * - Vocabulary analysis
 * - Detailed metrics appendix
 */

export interface DetailedReportInput {
  // Basic info
  title: string;
  created_at: string;

  // Core metrics
  predicted_grade_level: string;
  predicted_complexity: string;
  confidence: number;

  // Readability scores
  flesch_reading_ease: number;
  flesch_kincaid_grade: number;
  automated_readability_index: number;
  smog_readability: number;
  coleman_liau_index: number;

  // Text metrics
  word_count: number;
  sentence_count: number;
  avg_sentence_length: number;
  avg_word_length: number;
  avg_syllables_per_word: number;

  // Difficulty
  difficult_words_count: number;
  difficult_words_percentage: number;
  difficult_words: Array<{ word: string; position: number; syllables: number; reason: string }>;
  difficult_sentences: Array<{ sentence: string; position: number; word_count: number; reason: string }>;

  // Original text
  original_text: string;
}

export async function generateDetailedReport(input: DetailedReportInput) {
  const doc = new jsPDF();
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  let yPos = 20;

  // ===== PAGE 1: COVER PAGE =====

  // Logo/Header
  doc.setFillColor(59, 130, 246);  // Blue
  doc.rect(0, 0, pageWidth, 40, 'F');

  doc.setTextColor(255, 255, 255);
  doc.setFontSize(28);
  doc.setFont('helvetica', 'bold');
  doc.text('ClarityWorks', pageWidth / 2, 25, { align: 'center' });

  doc.setFontSize(12);
  doc.setFont('helvetica', 'normal');
  doc.text('Readability Analysis Report', pageWidth / 2, 32, { align: 'center' });

  yPos = 60;

  // Report title
  doc.setTextColor(0, 0, 0);
  doc.setFontSize(20);
  doc.setFont('helvetica', 'bold');
  const titleLines = doc.splitTextToSize(input.title || 'Text Analysis Report', pageWidth - 40);
  doc.text(titleLines, pageWidth / 2, yPos, { align: 'center' });
  yPos += (titleLines.length * 10) + 15;

  // Date
  doc.setFontSize(10);
  doc.setFont('helvetica', 'italic');
  doc.setTextColor(100, 100, 100);
  doc.text(`Generated on ${new Date(input.created_at).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })}`, pageWidth / 2, yPos, { align: 'center' });
  yPos += 30;

  // Executive Summary Box
  doc.setFillColor(245, 247, 250);
  doc.roundedRect(20, yPos, pageWidth - 40, 80, 5, 5, 'F');

  yPos += 10;
  doc.setTextColor(0, 0, 0);
  doc.setFontSize(14);
  doc.setFont('helvetica', 'bold');
  doc.text('Executive Summary', 30, yPos);
  yPos += 12;

  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');

  // Calculate additional metrics
  const complexityScore = calculateComplexityScore(input as ComplexityScoreInputs);
  const readingTime = calculateReadingTime({
    word_count: input.word_count,
    flesch_reading_ease: input.flesch_reading_ease
  });

  const summaryText = [
    `Grade Level: ${input.predicted_grade_level} (${input.predicted_complexity})`,
    `Complexity Score: ${complexityScore.score}/100 (${complexityScore.label})`,
    `Flesch Reading Ease: ${input.flesch_reading_ease.toFixed(1)}/100`,
    `Reading Time: ${readingTime.displayText} (${readingTime.wordsPerMinute} WPM)`,
    `Word Count: ${input.word_count.toLocaleString()} words`,
    `Difficult Words: ${input.difficult_words_percentage.toFixed(1)}% (${input.difficult_words_count} total)`,
    `Confidence: ${(input.confidence * 100).toFixed(0)}%`
  ];

  summaryText.forEach(line => {
    doc.text(line, 30, yPos);
    yPos += 7;
  });

  // ===== PAGE 2: READABILITY SCORES =====
  doc.addPage();
  yPos = 20;

  // Page header
  doc.setFontSize(18);
  doc.setFont('helvetica', 'bold');
  doc.text('Readability Scores', 20, yPos);
  yPos += 15;

  // Scores table
  autoTable(doc, {
    startY: yPos,
    head: [['Metric', 'Score', 'Interpretation']],
    body: [
      ['Flesch Reading Ease', input.flesch_reading_ease.toFixed(1), getFleschInterpretation(input.flesch_reading_ease)],
      ['Flesch-Kincaid Grade', input.flesch_kincaid_grade.toFixed(1), `US Grade ${input.flesch_kincaid_grade.toFixed(1)}`],
      ['ARI (Automated Readability)', input.automated_readability_index.toFixed(1), `US Grade ${input.automated_readability_index.toFixed(1)}`],
      ['SMOG Index', input.smog_readability.toFixed(1), `Years of education: ${input.smog_readability.toFixed(1)}`],
      ['Coleman-Liau Index', input.coleman_liau_index.toFixed(1), `US Grade ${input.coleman_liau_index.toFixed(1)}`],
      ['Complexity Score', `${complexityScore.score}/100`, complexityScore.label]
    ],
    headStyles: { fillColor: [59, 130, 246] },
    styles: { fontSize: 10 }
  });

  yPos = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY;
  yPos += 15;

  // Text Statistics
  doc.setFontSize(16);
  doc.setFont('helvetica', 'bold');
  doc.text('Text Statistics', 20, yPos);
  yPos += 10;

  autoTable(doc, {
    startY: yPos,
    head: [['Metric', 'Value']],
    body: [
      ['Total Words', input.word_count.toLocaleString()],
      ['Total Sentences', input.sentence_count.toString()],
      ['Average Sentence Length', `${input.avg_sentence_length.toFixed(1)} words`],
      ['Average Word Length', `${input.avg_word_length.toFixed(1)} characters`],
      ['Average Syllables per Word', input.avg_syllables_per_word.toFixed(2)],
      ['Difficult Words', `${input.difficult_words_count} (${input.difficult_words_percentage.toFixed(1)}%)`],
      ['Estimated Reading Time', readingTime.displayText]
    ],
    headStyles: { fillColor: [59, 130, 246] },
    styles: { fontSize: 10 }
  });

  // ===== PAGE 3: IMPROVEMENT SUGGESTIONS =====
  doc.addPage();
  yPos = 20;

  doc.setFontSize(18);
  doc.setFont('helvetica', 'bold');
  doc.text('Improvement Suggestions', 20, yPos);
  yPos += 15;

  const suggestions = generateImprovementSuggestions(input as unknown as SuggestionInput);

  suggestions.forEach((suggestion) => {
    if (yPos > pageHeight - 50) {
      doc.addPage();
      yPos = 20;
    }

    // Suggestion box
    doc.setFillColor(245, 247, 250);
    const boxHeight = 40 + (suggestion.details ? 10 : 0);
    doc.roundedRect(20, yPos, pageWidth - 40, boxHeight, 3, 3, 'F');

    yPos += 8;

    // Priority badge
    const priorityColor = suggestion.priority === 'high' ? [239, 68, 68] :
                         suggestion.priority === 'medium' ? [251, 191, 36] :
                         [59, 130, 246];
    doc.setFillColor(priorityColor[0], priorityColor[1], priorityColor[2]);
    doc.setTextColor(255, 255, 255);
    doc.setFontSize(8);
    doc.rect(25, yPos - 3, 30, 5, 'F');
    doc.text(suggestion.priority.toUpperCase(), 27, yPos);

    // Title
    doc.setTextColor(0, 0, 0);
    doc.setFontSize(12);
    doc.setFont('helvetica', 'bold');
    doc.text(`${suggestion.icon} ${suggestion.title}`, 60, yPos);
    yPos += 8;

    // Description
    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    const descLines = doc.splitTextToSize(suggestion.description, pageWidth - 50);
    doc.text(descLines, 25, yPos);
    yPos += descLines.length * 5;

    // Action
    doc.setFont('helvetica', 'bold');
    doc.text('Action: ', 25, yPos);
    doc.setFont('helvetica', 'normal');
    const actionLines = doc.splitTextToSize(suggestion.action, pageWidth - 60);
    doc.text(actionLines, 42, yPos);
    yPos += actionLines.length * 5;

    // Impact
    doc.setTextColor(59, 130, 246);
    doc.setFont('helvetica', 'italic');
    doc.text(`Impact: ${suggestion.estimatedImpact}`, 25, yPos);

    yPos += boxHeight - 25 + 10;
  });

  // ===== PAGE 4: VOCABULARY ANALYSIS =====
  doc.addPage();
  yPos = 20;

  doc.setTextColor(0, 0, 0);
  doc.setFontSize(18);
  doc.setFont('helvetica', 'bold');
  doc.text('Vocabulary Analysis', 20, yPos);
  yPos += 15;

  const vocabAnalysis = analyzeVocabulary({
    original_text: input.original_text,
    difficult_words: input.difficult_words
  });

  // Vocabulary distribution table
  autoTable(doc, {
    startY: yPos,
    head: [['Level', 'Grade Range', 'Word Count', 'Percentage', 'Examples']],
    body: vocabAnalysis.levels.map(level => [
      level.level,
      level.gradeRange,
      level.count.toLocaleString(),
      `${level.percentage.toFixed(1)}%`,
      level.examples.slice(0, 3).join(', ')
    ]),
    headStyles: { fillColor: [59, 130, 246] },
    styles: { fontSize: 9 }
  });

  yPos = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 15;

  // Vocabulary stats
  doc.setFontSize(11);
  doc.text(`Total Words: ${vocabAnalysis.totalWords.toLocaleString()}`, 20, yPos);
  yPos += 7;
  doc.text(`Unique Words: ${vocabAnalysis.uniqueWords.toLocaleString()}`, 20, yPos);
  yPos += 7;
  doc.text(`Vocabulary Diversity: ${(vocabAnalysis.vocabularyDiversity * 100).toFixed(1)}%`, 20, yPos);

  // ===== PAGE 5: DIFFICULT PASSAGES =====
  if (input.difficult_words.length > 0 || input.difficult_sentences.length > 0) {
    doc.addPage();
    yPos = 20;

    doc.setFontSize(18);
    doc.setFont('helvetica', 'bold');
    doc.text('Difficult Passages', 20, yPos);
    yPos += 15;

    // Difficult sentences
    if (input.difficult_sentences.length > 0) {
      doc.setFontSize(14);
      doc.text('Difficult Sentences', 20, yPos);
      yPos += 10;

      input.difficult_sentences.slice(0, 5).forEach((sent, index) => {
        if (yPos > pageHeight - 40) {
          doc.addPage();
          yPos = 20;
        }

        doc.setFontSize(10);
        doc.setFont('helvetica', 'bold');
        doc.text(`${index + 1}. `, 20, yPos);

        doc.setFont('helvetica', 'normal');
        const sentLines = doc.splitTextToSize(sent.sentence, pageWidth - 35);
        doc.text(sentLines, 27, yPos);
        yPos += sentLines.length * 5 + 2;

        doc.setFontSize(8);
        doc.setTextColor(100, 100, 100);
        doc.text(`Reason: ${sent.reason}`, 27, yPos);
        yPos += 10;

        doc.setTextColor(0, 0, 0);
      });
    }

    // Difficult words (top 20)
    if (input.difficult_words.length > 0 && yPos < pageHeight - 60) {
      yPos += 10;
      doc.setFontSize(14);
      doc.setFont('helvetica', 'bold');
      doc.text('Difficult Words (Top 20)', 20, yPos);
      yPos += 10;

      const wordRows = input.difficult_words
        .slice(0, 20)
        .map(w => [w.word, w.syllables.toString(), w.reason.substring(0, 60)]);

      autoTable(doc, {
        startY: yPos,
        head: [['Word', 'Syllables', 'Reason']],
        body: wordRows,
        headStyles: { fillColor: [59, 130, 246] },
        styles: { fontSize: 8 },
        columnStyles: {
          0: { cellWidth: 40 },
          1: { cellWidth: 20 },
          2: { cellWidth: 'auto' }
        }
      });
    }
  }

  // ===== FOOTER ON ALL PAGES =====
  const totalPages = doc.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);
    doc.setFontSize(8);
    doc.setTextColor(150, 150, 150);
    doc.text(
      `Page ${i} of ${totalPages} | Generated by ClarityWorks | ${new Date().toLocaleDateString()}`,
      pageWidth / 2,
      pageHeight - 10,
      { align: 'center' }
    );
  }

  // Save
  doc.save(`${input.title.replace(/[^a-z0-9]/gi, '_')}_detailed_report.pdf`);
}

/**
 * Helper: Get Flesch score interpretation
 */
function getFleschInterpretation(score: number): string {
  if (score >= 90) return 'Very Easy (Grade 5)';
  if (score >= 80) return 'Easy (Grade 6)';
  if (score >= 70) return 'Fairly Easy (Grade 7)';
  if (score >= 60) return 'Standard (Grades 8-9)';
  if (score >= 50) return 'Fairly Difficult (Grades 10-12)';
  if (score >= 30) return 'Difficult (College)';
  return 'Very Difficult (College Graduate)';
}
