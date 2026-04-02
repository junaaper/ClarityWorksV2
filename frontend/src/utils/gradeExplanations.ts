export interface GradeExplanation {
  layman: string;
  technical: string;
  characteristics: {
    vocabulary: string;
    sentenceLength: string;
    structure: string;
    audience: string;
  };
}

export const GRADE_EXPLANATIONS: Record<string, GradeExplanation> = {
  "Grade 3": {
    layman: "This text is very simple and easy to read, suitable for early elementary school students (8-9 years old). It uses basic everyday words and short, simple sentences.",
    technical: "Grade 3 texts typically feature high-frequency vocabulary (Zipf >=5.5), short declarative sentences (8-10 words average), minimal subordinate clauses, and Flesch Reading Ease scores of 80-90.",
    characteristics: {
      vocabulary: "Simple, everyday words (1-2 syllables)",
      sentenceLength: "8-10 words per sentence",
      structure: "Simple sentences with basic subject-verb-object",
      audience: "Early elementary students (ages 8-9)"
    }
  },

  "Grade 4": {
    layman: "This text is simple and suitable for elementary school students (9-10 years old). It uses common words and mostly straightforward sentences with occasional complexity.",
    technical: "Grade 4 texts feature common vocabulary with some multi-syllabic words, sentences averaging 10-12 words, occasional compound sentences, and Flesch scores of 75-85.",
    characteristics: {
      vocabulary: "Common words, some 3-syllable words",
      sentenceLength: "10-12 words per sentence",
      structure: "Simple + occasional compound sentences (and/but)",
      audience: "Elementary students (ages 9-10)"
    }
  },

  "Grade 5": {
    layman: "This text is moderately easy, appropriate for upper elementary students (10-11 years old). It uses familiar words with some academic vocabulary beginning to appear.",
    technical: "Grade 5 texts introduce basic academic vocabulary, average 12-15 words per sentence, more frequent compound sentences, and Flesch scores of 70-80.",
    characteristics: {
      vocabulary: "Mix of common and some academic words",
      sentenceLength: "12-15 words per sentence",
      structure: "Compound sentences common, some complex",
      audience: "Upper elementary students (ages 10-11)"
    }
  },

  "Grade 6": {
    layman: "This text is moderately complex, suitable for middle school students (11-12 years old). It includes academic vocabulary and sentences with multiple ideas connected together.",
    technical: "Grade 6 texts feature emerging academic vocabulary (Zipf >=4.6), sentences of 15-18 words with subordinate clauses beginning to appear regularly, and Flesch scores of 65-75.",
    characteristics: {
      vocabulary: "Academic vocabulary begins (3-4 syllables)",
      sentenceLength: "15-18 words per sentence",
      structure: "Complex sentences with subordinate clauses",
      audience: "Middle school students (ages 11-12)"
    }
  },

  "Grade 7": {
    layman: "This text is moderately challenging, appropriate for middle school students (12-13 years old). It uses academic language and sentences with embedded clauses and multiple ideas.",
    technical: "Grade 7 texts display increased academic vocabulary, 16-19 words per sentence on average, higher subordinate clause density (1.5+ per sentence), and Flesch scores of 60-70.",
    characteristics: {
      vocabulary: "Academic/technical terms common",
      sentenceLength: "16-19 words per sentence",
      structure: "Complex with multiple embedded clauses",
      audience: "Middle school students (ages 12-13)"
    }
  },

  "Grade 8": {
    layman: "This text is challenging, suitable for advanced middle school students (13-14 years old). It features sophisticated vocabulary and complex sentence structures with multiple layers of meaning.",
    technical: "Grade 8 texts contain substantial academic vocabulary, sentences averaging 18-22 words, frequent use of passive voice and subordinate clauses, and Flesch scores of 55-65.",
    characteristics: {
      vocabulary: "Sophisticated academic vocabulary",
      sentenceLength: "18-22 words per sentence",
      structure: "Multiple clause structures, passive voice",
      audience: "Advanced middle school (ages 13-14)"
    }
  },

  "Grade 9": {
    layman: "This text is quite difficult, appropriate for high school freshmen (14-15 years old). It uses advanced vocabulary and intricate sentence structures requiring careful reading.",
    technical: "Grade 9 texts feature advanced vocabulary (Zipf >=3.7), 20-24 words per sentence, high clause complexity, increased passive constructions, and Flesch scores of 50-60.",
    characteristics: {
      vocabulary: "Advanced, subject-specific terms",
      sentenceLength: "20-24 words per sentence",
      structure: "Intricate, nested clause structures",
      audience: "High school freshmen (ages 14-15)"
    }
  },

  "Grade 10": {
    layman: "This text is very difficult, suitable for high school sophomores (15-16 years old). It demands strong reading skills with sophisticated vocabulary and complex argumentation.",
    technical: "Grade 10 texts display sophisticated academic vocabulary, sentences of 22-26 words, high syntactic complexity with multiple embedded clauses, and Flesch scores of 45-55.",
    characteristics: {
      vocabulary: "Sophisticated, discipline-specific",
      sentenceLength: "22-26 words per sentence",
      structure: "Advanced complexity, abstract concepts",
      audience: "High school sophomores (ages 15-16)"
    }
  },

  "Grade 11": {
    layman: "This text is highly challenging, appropriate for advanced high school juniors (16-17 years old). It requires mature reading comprehension with abstract concepts and dense prose.",
    technical: "Grade 11 texts contain highly specialized vocabulary, 24-28 words per sentence, sophisticated syntactic structures, frequent nominalization and abstraction, Flesch scores of 40-50.",
    characteristics: {
      vocabulary: "Highly specialized, abstract terms",
      sentenceLength: "24-28 words per sentence",
      structure: "Sophisticated, dense prose",
      audience: "High school juniors (ages 16-17)"
    }
  },

  "Grade 12": {
    layman: "This text is very advanced, suitable for high school seniors (17-18 years old) preparing for college. It features college-level vocabulary and argumentation requiring critical analysis.",
    technical: "Grade 12 texts approach college-level complexity with specialized terminology (Zipf >=2.8), sentences averaging 26-30+ words, high abstraction and nominalization, Flesch scores of 35-45.",
    characteristics: {
      vocabulary: "College-preparatory, specialized",
      sentenceLength: "26-30+ words per sentence",
      structure: "College-level complexity and abstraction",
      audience: "High school seniors (ages 17-18)"
    }
  },

  "College": {
    layman: "This text is extremely challenging, written at college level or higher. It requires advanced critical thinking, specialized knowledge, and comfort with abstract academic discourse.",
    technical: "College-level texts feature highly specialized disciplinary vocabulary, sentences often exceeding 30 words, sophisticated rhetorical structures, extensive use of nominalization and passive voice, Flesch scores typically below 40.",
    characteristics: {
      vocabulary: "Highly specialized, disciplinary jargon",
      sentenceLength: "30+ words per sentence",
      structure: "Sophisticated academic discourse",
      audience: "College students and academic researchers"
    }
  }
};

export function getGradeExplanation(gradeLevel: string): GradeExplanation {
  return GRADE_EXPLANATIONS[gradeLevel] || GRADE_EXPLANATIONS["Grade 6"];
}
