import React from 'react';
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts';
import type { ReadabilityScores, BasicMetrics, Statistics, DifficultWord } from '../../types';

interface RadarChartProps {
  scores: ReadabilityScores;
}

export const ReadabilityRadarChart: React.FC<RadarChartProps> = ({ scores }) => {
  // Normalize scores to 0-100 scale
  const data = [
    {
      metric: 'Flesch Ease',
      value: Math.max(0, Math.min(100, scores.flesch_reading_ease)),
      fullMark: 100,
    },
    {
      metric: 'FK Grade',
      value: Math.max(0, Math.min(100, (18 - scores.flesch_kincaid_grade) * 100 / 18)),
      fullMark: 100,
    },
    {
      metric: 'ARI',
      value: Math.max(0, Math.min(100, (18 - scores.automated_readability_index) * 100 / 18)),
      fullMark: 100,
    },
    {
      metric: 'SMOG',
      value: Math.max(0, Math.min(100, (18 - scores.smog_readability) * 100 / 18)),
      fullMark: 100,
    },
    {
      metric: 'Coleman-Liau',
      value: Math.max(0, Math.min(100, (18 - scores.coleman_liau_index) * 100 / 18)),
      fullMark: 100,
    },
  ];

  return (
    <ResponsiveContainer width="100%" height={300}>
      <RadarChart data={data}>
        <PolarGrid />
        <PolarAngleAxis dataKey="metric" tick={{ fontSize: 12 }} />
        <PolarRadiusAxis angle={30} domain={[0, 100]} />
        <Radar
          name="Readability"
          dataKey="value"
          stroke="#3b82f6"
          fill="#3b82f6"
          fillOpacity={0.5}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
};

interface StatsBarChartProps {
  metrics: BasicMetrics;
  statistics: Statistics;
}

export const TextStatsBarChart: React.FC<StatsBarChartProps> = ({ metrics, statistics }) => {
  const data = [
    { name: 'Words', value: metrics.word_count, color: '#3b82f6' },
    { name: 'Sentences', value: metrics.sentence_count, color: '#10b981' },
    { name: 'Avg Words/Sent', value: Math.round(metrics.avg_sentence_length), color: '#f59e0b' },
    { name: 'Difficult Words', value: statistics.difficult_words_count, color: '#ef4444' },
  ];

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="name" tick={{ fontSize: 12 }} />
        <YAxis />
        <Tooltip />
        <Bar dataKey="value" fill="#3b82f6">
          {data.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={entry.color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
};

interface GradeLevelGaugeProps {
  gradeLevel: string;
}

export const GradeLevelGauge: React.FC<GradeLevelGaugeProps> = ({ gradeLevel }) => {
  const gradeNumber = gradeLevel.replace('Grade ', '');
  let numericGrade: number;

  if (gradeNumber === 'College') {
    numericGrade = 13;
  } else {
    numericGrade = parseInt(gradeNumber) || 6;
  }

  // Create gauge data
  const percentage = ((numericGrade - 3) / 10) * 100;
  const data = [
    { name: 'Level', value: percentage },
    { name: 'Remaining', value: 100 - percentage },
  ];

  const getColor = (grade: number): string => {
    if (grade <= 5) return '#10b981'; // green - elementary
    if (grade <= 8) return '#f59e0b'; // yellow - middle school
    if (grade <= 10) return '#f97316'; // orange - high school
    return '#ef4444'; // red - advanced
  };

  const COLORS = [getColor(numericGrade), '#e5e7eb'];

  return (
    <div className="text-center">
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            startAngle={180}
            endAngle={0}
            innerRadius={60}
            outerRadius={80}
            paddingAngle={0}
            dataKey="value"
          >
            {data.map((_, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index]} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="-mt-16 relative z-10">
        <p className="text-3xl font-bold text-gray-800">{gradeLevel}</p>
        <p className="text-sm text-gray-500">Reading Level</p>
      </div>
    </div>
  );
};

interface WordDifficultyPieChartProps {
  statistics: Statistics;
  wordCount: number;
}

export const WordDifficultyPieChart: React.FC<WordDifficultyPieChartProps> = ({
  statistics,
  wordCount,
}) => {
  const commonWords = wordCount - statistics.difficult_words_count;

  const data = [
    { name: 'Common Words', value: commonWords },
    { name: 'Difficult Words', value: statistics.difficult_words_count },
  ];

  const COLORS = ['#10b981', '#ef4444'];

  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          labelLine={false}
          label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(1)}%`}
          outerRadius={100}
          fill="#8884d8"
          dataKey="value"
        >
          {data.map((_, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index]} />
          ))}
        </Pie>
        <Legend />
        <Tooltip />
      </PieChart>
    </ResponsiveContainer>
  );
};

interface DifficultWordsChartProps {
  words: DifficultWord[];
}

export const DifficultWordsChart: React.FC<DifficultWordsChartProps> = ({ words }) => {
  const data = words.slice(0, 10).map((w) => ({
    word: w.word.length > 12 ? w.word.substring(0, 12) + '...' : w.word,
    syllables: w.syllables,
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} layout="vertical">
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis type="number" />
        <YAxis dataKey="word" type="category" width={100} tick={{ fontSize: 12 }} />
        <Tooltip />
        <Bar dataKey="syllables" fill="#ef4444" name="Syllables" />
      </BarChart>
    </ResponsiveContainer>
  );
};

// Stop words to exclude from common words analysis
const STOP_WORDS = new Set([
  'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i',
  'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at',
  'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she',
  'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there', 'their', 'what',
  'so', 'up', 'out', 'if', 'about', 'who', 'get', 'which', 'go', 'me',
  'when', 'make', 'can', 'like', 'time', 'no', 'just', 'him', 'know', 'take',
  'people', 'into', 'year', 'your', 'good', 'some', 'could', 'them', 'see', 'other',
  'than', 'then', 'now', 'look', 'only', 'come', 'its', 'over', 'think', 'also',
  'back', 'after', 'use', 'two', 'how', 'our', 'work', 'first', 'well', 'way',
  'even', 'new', 'want', 'because', 'any', 'these', 'give', 'day', 'most', 'us',
  'is', 'are', 'was', 'were', 'been', 'being', 'has', 'had', 'did', 'does',
  'am', 'more', 'very', 'much', 'such', 'each', 'own', 'should', 'may', 'might',
]);

interface CommonWordsChartProps {
  text: string;
}

export const CommonWordsChart: React.FC<CommonWordsChartProps> = ({ text }) => {
  const words = text
    .toLowerCase()
    .replace(/[^a-z\s]/g, '')
    .split(/\s+/)
    .filter((w) => w.length > 2 && !STOP_WORDS.has(w));

  const freq: Record<string, number> = {};
  for (const word of words) {
    freq[word] = (freq[word] || 0) + 1;
  }

  const data = Object.entries(freq)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 15)
    .map(([word, count]) => ({ word, count }));

  if (data.length === 0) {
    return <p className="text-gray-400 text-center py-8">Not enough content words to display</p>;
  }

  const COLORS = ['#3b82f6', '#6366f1', '#8b5cf6', '#a855f7', '#d946ef',
    '#ec4899', '#f43f5e', '#ef4444', '#f97316', '#f59e0b',
    '#eab308', '#84cc16', '#22c55e', '#14b8a6', '#06b6d4'];

  return (
    <ResponsiveContainer width="100%" height={Math.max(300, data.length * 32)}>
      <BarChart data={data} layout="vertical" margin={{ left: 10, right: 20 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis type="number" />
        <YAxis dataKey="word" type="category" width={100} tick={{ fontSize: 12 }} />
        <Tooltip />
        <Bar dataKey="count" name="Occurrences">
          {data.map((_, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
};
