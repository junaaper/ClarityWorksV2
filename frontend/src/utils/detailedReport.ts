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
  analyzeVocabulary
} from './vocabularyAnalysis';
import {
  generateImprovementSuggestions,
  SuggestionInput
} from './improvementSuggestions';

export interface DetailedReportInput {
  title: string;
  created_at: string;

  predicted_grade_level: string;
  predicted_complexity: string;
  confidence: number;

  flesch_reading_ease: number;
  flesch_kincaid_grade: number;
  automated_readability_index: number;
  smog_readability: number;
  coleman_liau_index: number;

  word_count: number;
  sentence_count: number;
  avg_sentence_length: number;
  avg_word_length: number;
  avg_syllables_per_word: number;

  difficult_words_count: number;
  difficult_words_percentage: number;
  difficult_words: Array<{ word: string; position: number; syllables: number; reason: string }>;
  difficult_sentences: Array<{ sentence: string; position: number; word_count: number; reason: string; flesch_score?: number }>;

  original_text: string;
}

const BLUE: [number, number, number] = [59, 130, 246];
const TEAL: [number, number, number] = [20, 184, 166];
const DARK: [number, number, number] = [31, 41, 55];
const GRAY: [number, number, number] = [100, 116, 139];
const LIGHT_BG: [number, number, number] = [245, 247, 250];

export async function generateDetailedReport(input: DetailedReportInput) {
  const doc = new jsPDF();
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const margin = 20;
  const contentWidth = pageWidth - margin * 2;
  let yPos = 20;

  const complexityScore = calculateComplexityScore(input as ComplexityScoreInputs);
  const readingTime = calculateReadingTime({
    word_count: input.word_count,
    flesch_reading_ease: input.flesch_reading_ease
  });

  const checkPage = (need: number) => {
    if (yPos + need > pageHeight - 25) {
      doc.addPage();
      yPos = 25;
    }
  };

  const sectionHeader = (title: string) => {
    checkPage(30);
    doc.setFontSize(16);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(...DARK);
    doc.text(title, margin, yPos);
    yPos += 3;
    doc.setDrawColor(...BLUE);
    doc.setLineWidth(0.8);
    doc.line(margin, yPos, margin + 50, yPos);
    doc.setLineWidth(0.2);
    yPos += 10;
  };

  // ===== PAGE 1: COVER =====
  doc.setFillColor(...BLUE);
  doc.rect(0, 0, pageWidth, 44, 'F');

  doc.setTextColor(255, 255, 255);
  doc.setFontSize(26);
  doc.setFont('helvetica', 'bold');
  doc.text('ClarityWorks', pageWidth / 2, 22, { align: 'center' });

  doc.setFontSize(11);
  doc.setFont('helvetica', 'normal');
  doc.text('Detailed Readability Analysis Report', pageWidth / 2, 34, { align: 'center' });

  yPos = 62;

  doc.setTextColor(...DARK);
  doc.setFontSize(20);
  doc.setFont('helvetica', 'bold');
  const titleLines = doc.splitTextToSize(input.title || 'Text Analysis Report', contentWidth);
  doc.text(titleLines, pageWidth / 2, yPos, { align: 'center' });
  yPos += titleLines.length * 10 + 8;

  doc.setFontSize(10);
  doc.setFont('helvetica', 'italic');
  doc.setTextColor(...GRAY);
  doc.text(`Generated on ${new Date(input.created_at).toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric'
  })}`, pageWidth / 2, yPos, { align: 'center' });
  yPos += 25;

  // Executive Summary Box
  const summaryBoxHeight = 96;
  doc.setFillColor(...LIGHT_BG);
  doc.roundedRect(margin, yPos, contentWidth, summaryBoxHeight, 4, 4, 'F');
  doc.setDrawColor(200, 210, 220);
  doc.roundedRect(margin, yPos, contentWidth, summaryBoxHeight, 4, 4, 'S');

  yPos += 12;
  doc.setTextColor(...DARK);
  doc.setFontSize(13);
  doc.setFont('helvetica', 'bold');
  doc.text('Executive Summary', margin + 12, yPos);
  yPos += 10;

  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');

  const summaryRows = [
    [`Grade Level: ${input.predicted_grade_level}`, `Complexity: ${input.predicted_complexity}`],
    [`Complexity Score: ${complexityScore.score}/100 (${complexityScore.label})`, `Confidence: ${(input.confidence * 100).toFixed(0)}%`],
    [`Flesch Reading Ease: ${input.flesch_reading_ease.toFixed(1)}/100`, `Reading Time: ${readingTime.displayText}`],
    [`Words: ${input.word_count.toLocaleString()}`, `Sentences: ${input.sentence_count.toLocaleString()}`],
    [`Difficult Words: ${input.difficult_words_percentage.toFixed(1)}% (${input.difficult_words_count})`, `Avg Syllables/Word: ${input.avg_syllables_per_word.toFixed(2)}`],
  ];

  summaryRows.forEach(([left, right]) => {
    doc.setTextColor(...DARK);
    doc.text(left, margin + 12, yPos);
    doc.text(right, margin + contentWidth / 2, yPos);
    yPos += 7;
  });

  // At-a-Glance grade banner
  yPos += 20;
  const gradeBoxW = 90;
  const gradeBoxH = 36;
  const gradeBoxX = (pageWidth - gradeBoxW) / 2;
  doc.setFillColor(...BLUE);
  doc.roundedRect(gradeBoxX, yPos, gradeBoxW, gradeBoxH, 5, 5, 'F');
  doc.setTextColor(255, 255, 255);
  doc.setFontSize(18);
  doc.setFont('helvetica', 'bold');
  doc.text(input.predicted_grade_level, pageWidth / 2, yPos + 15, { align: 'center' });
  doc.setFontSize(9);
  doc.setFont('helvetica', 'normal');
  doc.text(`${input.predicted_complexity} | ${complexityScore.label}`, pageWidth / 2, yPos + 26, { align: 'center' });

  // ===== PAGE 2: READABILITY SCORES =====
  doc.addPage();
  yPos = 25;

  sectionHeader('Readability Scores');

  autoTable(doc, {
    startY: yPos,
    head: [['Metric', 'Score', 'Interpretation']],
    body: [
      ['Flesch Reading Ease', input.flesch_reading_ease.toFixed(1), getFleschInterpretation(input.flesch_reading_ease)],
      ['Flesch-Kincaid Grade', input.flesch_kincaid_grade.toFixed(1), `US Grade ${input.flesch_kincaid_grade.toFixed(1)}`],
      ['ARI (Automated Readability)', input.automated_readability_index.toFixed(1), `US Grade ${input.automated_readability_index.toFixed(1)}`],
      ['SMOG Index', input.smog_readability.toFixed(1), `Years of education: ${input.smog_readability.toFixed(1)}`],
      ['Coleman-Liau Index', input.coleman_liau_index.toFixed(1), `US Grade ${input.coleman_liau_index.toFixed(1)}`],
      ['Complexity Score', `${complexityScore.score}/100`, complexityScore.label],
    ],
    headStyles: { fillColor: BLUE, fontSize: 9, fontStyle: 'bold' },
    styles: { fontSize: 9.5, cellPadding: 4 },
    alternateRowStyles: { fillColor: [250, 251, 253] },
  });

  yPos = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 15;

  // Complexity Score Breakdown
  sectionHeader('Complexity Score Breakdown');

  const breakdown = complexityScore.breakdown;
  autoTable(doc, {
    startY: yPos,
    head: [['Component', 'Weight', 'Contribution', 'Description']],
    body: [
      ['Grade Level', '40%', `${breakdown.gradeContribution}/40`, `Based on predicted ${input.predicted_grade_level}`],
      ['Flesch Reading Ease', '30%', `${breakdown.fleschContribution}/30`, `Flesch score ${input.flesch_reading_ease.toFixed(1)} (inverted: lower ease = higher complexity)`],
      ['Difficult Words', '20%', `${breakdown.wordsContribution}/20`, `${input.difficult_words_percentage.toFixed(1)}% of words flagged as difficult`],
      ['Sentence Length', '10%', `${breakdown.sentenceContribution}/10`, `Avg ${input.avg_sentence_length.toFixed(1)} words/sentence`],
      ['Total', '100%', `${complexityScore.score}/100`, complexityScore.label],
    ],
    headStyles: { fillColor: TEAL, fontSize: 9, fontStyle: 'bold' },
    styles: { fontSize: 9, cellPadding: 3.5 },
    alternateRowStyles: { fillColor: [245, 253, 252] },
  });

  yPos = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 15;

  // Text Statistics
  sectionHeader('Text Statistics');

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
      ['Estimated Reading Time', `${readingTime.displayText} (${readingTime.wordsPerMinute} WPM adjusted)`],
    ],
    headStyles: { fillColor: BLUE, fontSize: 9, fontStyle: 'bold' },
    styles: { fontSize: 9.5, cellPadding: 3.5 },
    alternateRowStyles: { fillColor: [250, 251, 253] },
  });

  // ===== PAGE 3: IMPROVEMENT SUGGESTIONS =====
  doc.addPage();
  yPos = 25;

  sectionHeader('Improvement Suggestions');

  const suggestions = generateImprovementSuggestions(input as unknown as SuggestionInput);

  if (suggestions.length > 0) {
    suggestions.forEach((suggestion, index) => {
      checkPage(45);

      const priorityColors: Record<string, [number, number, number]> = {
        high: [220, 38, 38],
        medium: [245, 158, 11],
        low: [34, 197, 94],
      };
      const color = priorityColors[suggestion.priority] || GRAY;

      doc.setFillColor(color[0], color[1], color[2]);
      doc.circle(margin + 4, yPos - 1.5, 2.5, 'F');

      doc.setFontSize(11);
      doc.setFont('helvetica', 'bold');
      doc.setTextColor(...DARK);
      doc.text(`${index + 1}. ${suggestion.title}`, margin + 12, yPos);
      yPos += 2;

      doc.setFontSize(8);
      doc.setFont('helvetica', 'normal');
      doc.setTextColor(...color);
      doc.text(`${suggestion.priority.toUpperCase()} PRIORITY | ${suggestion.estimatedImpact}`, margin + 12, yPos + 4);
      yPos += 9;

      doc.setFontSize(9.5);
      doc.setTextColor(...DARK);
      const descLines = doc.splitTextToSize(suggestion.description, contentWidth - 14);
      doc.text(descLines, margin + 12, yPos);
      yPos += descLines.length * 4.5 + 2;

      doc.setFont('helvetica', 'italic');
      doc.setTextColor(...GRAY);
      const actionLines = doc.splitTextToSize(`Action: ${suggestion.action}`, contentWidth - 14);
      doc.text(actionLines, margin + 12, yPos);
      yPos += actionLines.length * 4.5 + 3;

      if (suggestion.details) {
        doc.setFont('helvetica', 'normal');
        doc.setFontSize(8.5);
        const detailLines = doc.splitTextToSize(suggestion.details, contentWidth - 14);
        doc.text(detailLines, margin + 12, yPos);
        yPos += detailLines.length * 4 + 2;
      }

      yPos += 6;
    });
  } else {
    doc.setFontSize(10);
    doc.setFont('helvetica', 'italic');
    doc.setTextColor(...GRAY);
    doc.text('Your text is already well-optimized. No major improvements suggested.', margin, yPos);
    yPos += 15;
  }

  // ===== PAGE 4: VOCABULARY ANALYSIS =====
  doc.addPage();
  yPos = 25;

  sectionHeader('Vocabulary Analysis');

  const vocabAnalysis = analyzeVocabulary({
    original_text: input.original_text,
    difficult_words: input.difficult_words
  });

  autoTable(doc, {
    startY: yPos,
    head: [['Level', 'Grade Range', 'Count', 'Percentage', 'Examples']],
    body: vocabAnalysis.levels.map(level => [
      level.level,
      level.gradeRange,
      level.count.toLocaleString(),
      `${level.percentage.toFixed(1)}%`,
      level.examples.slice(0, 5).join(', ') || '—'
    ]),
    headStyles: { fillColor: TEAL, fontSize: 9, fontStyle: 'bold' },
    styles: { fontSize: 9, cellPadding: 3.5 },
    alternateRowStyles: { fillColor: [245, 253, 252] },
    columnStyles: { 4: { cellWidth: 60 } },
  });

  yPos = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 12;

  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(...DARK);
  doc.text(`Total Words: ${vocabAnalysis.totalWords.toLocaleString()}  |  Unique Words: ${vocabAnalysis.uniqueWords.toLocaleString()}  |  Vocabulary Diversity: ${(vocabAnalysis.vocabularyDiversity * 100).toFixed(1)}%`, margin, yPos);

  // ===== PAGE 5: DIFFICULT PASSAGES =====
  if (input.difficult_sentences.length > 0 || input.difficult_words.length > 0) {
    doc.addPage();
    yPos = 25;

    sectionHeader('Difficult Passages');

    if (input.difficult_sentences.length > 0) {
      doc.setFontSize(12);
      doc.setFont('helvetica', 'bold');
      doc.setTextColor(...DARK);
      doc.text('Difficult Sentences', margin, yPos);
      yPos += 8;

      input.difficult_sentences.slice(0, 8).forEach((sent, index) => {
        checkPage(35);

        doc.setFontSize(9.5);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(...DARK);
        doc.text(`${index + 1}.`, margin, yPos);

        doc.setFont('helvetica', 'normal');
        const sentText = sent.sentence.length > 300 ? sent.sentence.substring(0, 300) + '...' : sent.sentence;
        const sentLines = doc.splitTextToSize(sentText, contentWidth - 10);
        doc.text(sentLines, margin + 8, yPos);
        yPos += sentLines.length * 4.5 + 2;

        doc.setFontSize(8);
        doc.setTextColor(...GRAY);
        const reasonLine = `${sent.reason} | ${sent.word_count} words${sent.flesch_score != null ? ` | Flesch: ${sent.flesch_score}` : ''}`;
        doc.text(reasonLine, margin + 8, yPos);
        yPos += 9;
        doc.setTextColor(...DARK);
      });
    }

    if (input.difficult_words.length > 0) {
      checkPage(40);
      yPos += 5;
      doc.setFontSize(12);
      doc.setFont('helvetica', 'bold');
      doc.setTextColor(...DARK);
      doc.text(`Difficult Words (Top ${Math.min(30, input.difficult_words.length)})`, margin, yPos);
      yPos += 8;

      autoTable(doc, {
        startY: yPos,
        head: [['Word', 'Syllables', 'Reason']],
        body: input.difficult_words.slice(0, 30).map(w => [
          w.word,
          w.syllables.toString(),
          w.reason
        ]),
        headStyles: { fillColor: BLUE, fontSize: 8.5, fontStyle: 'bold' },
        styles: { fontSize: 8, cellPadding: 3 },
        alternateRowStyles: { fillColor: [250, 251, 253] },
        columnStyles: {
          0: { cellWidth: 35, fontStyle: 'bold' },
          1: { cellWidth: 18, halign: 'center' },
          2: { cellWidth: 'auto' }
        },
      });
    }
  }

  // ===== FOOTER ON ALL PAGES =====
  const totalPages = doc.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);
    doc.setFontSize(7.5);
    doc.setTextColor(160, 170, 180);
    doc.text(
      `Page ${i} of ${totalPages}  |  ClarityWorks Readability Report  |  ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}`,
      pageWidth / 2,
      pageHeight - 8,
      { align: 'center' }
    );
  }

  doc.save(`${input.title.replace(/[^a-z0-9]/gi, '_')}_detailed_report.pdf`);
}

function getFleschInterpretation(score: number): string {
  if (score >= 90) return 'Very Easy — easily understood by 5th graders';
  if (score >= 80) return 'Easy — conversational English';
  if (score >= 70) return 'Fairly Easy — understood by 7th graders';
  if (score >= 60) return 'Standard — 8th to 9th grade level';
  if (score >= 50) return 'Fairly Difficult — 10th to 12th grade';
  if (score >= 30) return 'Difficult — college-level reading';
  return 'Very Difficult — best understood by college graduates';
}
