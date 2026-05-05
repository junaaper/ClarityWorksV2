from openai import OpenAI
import os
import json
import spacy
from collections import Counter

FIREWORKS_MODEL = "accounts/fireworks/models/llama-v3p3-70b-instruct"

nlp = spacy.load('en_core_web_sm')


class ConceptExtractor:
    """Extract concept prerequisite graphs from text using spaCy + Fireworks AI"""

    def __init__(self):
        api_key = os.getenv('FIREWORKS_API_KEY')

        if not api_key:
            print("Warning: FIREWORKS_API_KEY not found - concept extraction disabled")
            self.client = None
        else:
            self.client = OpenAI(
                base_url="https://api.fireworks.ai/inference/v1",
                api_key=api_key,
            )
            print("Fireworks API initialized for concept extraction")

    def extract(self, text):
        """
        Extract concept prerequisite graph from text.

        Args:
            text: Input text (analysis text or concatenated chunks)

        Returns:
            dict with 'concepts' and 'edges', or None on failure
        """
        if not self.client:
            return None

        if not text or len(text.strip()) < 200:
            return None

        try:
            noun_phrases = self._extract_noun_phrases(text)
            return self._call_llm(text[:4000], noun_phrases)
        except Exception as e:
            print(f"Concept extraction error: {e}")
            return None

    def extract_from_chunks(self, chunks):
        """
        Extract concept prerequisite graph from document chunks (RAG).
        Samples chunks for the LLM but extracts noun phrases from all.

        Args:
            chunks: List of text chunks from ChromaDB

        Returns:
            dict with 'concepts' and 'edges', or None on failure
        """
        if not self.client or not chunks:
            return None

        all_text = " ".join(chunks)
        if len(all_text.strip()) < 200:
            return None

        try:
            noun_phrases = self._extract_noun_phrases(all_text)

            sampled_text = self._sample_chunks(chunks, max_chars=6000)

            return self._call_llm(sampled_text, noun_phrases)
        except Exception as e:
            print(f"Concept extraction from chunks error: {e}")
            return None

    def _extract_noun_phrases(self, text):
        """Extract and rank noun phrases using spaCy."""
        doc = nlp(text[:50000])

        phrase_counts = Counter()
        for chunk in doc.noun_chunks:
            phrase = chunk.text.strip().lower()
            if len(phrase) < 3 or len(phrase.split()) > 5:
                continue
            skip_words = {'this', 'that', 'these', 'those', 'it', 'they', 'them',
                          'he', 'she', 'we', 'you', 'i', 'my', 'your', 'his', 'her',
                          'its', 'our', 'their', 'the', 'a', 'an', 'some', 'any',
                          'each', 'every', 'which', 'what', 'who'}
            if phrase in skip_words:
                continue
            if all(t.pos_ in ('DET', 'PRON', 'ADP') for t in chunk):
                continue
            phrase_counts[phrase] += 1

        ranked = sorted(phrase_counts.items(), key=lambda x: x[1], reverse=True)
        return [phrase for phrase, _ in ranked[:30]]

    def _sample_chunks(self, chunks, max_chars=6000):
        """Sample representative chunks from a long document."""
        if not chunks:
            return ""

        total = len(chunks)
        if total <= 3:
            return "\n\n".join(chunks)[:max_chars]

        indices = [0, total // 2, total - 1]
        if total > 6:
            indices.extend([total // 4, 3 * total // 4])
        indices = sorted(set(indices))

        sampled = []
        char_count = 0
        for i in indices:
            if char_count + len(chunks[i]) > max_chars:
                remaining = max_chars - char_count
                if remaining > 200:
                    sampled.append(chunks[i][:remaining])
                break
            sampled.append(chunks[i])
            char_count += len(chunks[i])

        return "\n\n".join(sampled)

    def _call_llm(self, text, noun_phrases):
        """Call Fireworks LLM to extract concepts and prerequisites."""
        phrases_str = ", ".join(noun_phrases[:25]) if noun_phrases else "(none extracted)"

        prompt = f"""You are analyzing a text to build a concept prerequisite graph.
A concept prerequisite graph shows what knowledge a reader needs before they can understand the main ideas.

TEXT:
{text}

KEY NOUN PHRASES FOUND:
{phrases_str}

TASK: Extract 5-15 key concepts from this text and map their prerequisite dependencies.
For each concept, identify what prior knowledge a reader needs to understand it.

Return ONLY valid JSON (no markdown, no code blocks):
{{
  "concepts": [
    {{"id": "c1", "label": "Short Name", "tier": "target", "description": "One sentence description"}},
    {{"id": "c2", "label": "Short Name", "tier": "intermediate", "description": "One sentence description"}},
    {{"id": "c3", "label": "Short Name", "tier": "prerequisite", "description": "One sentence description"}}
  ],
  "edges": [
    {{"from": "c3", "to": "c2", "relationship": "required_for"}},
    {{"from": "c2", "to": "c1", "relationship": "required_for"}}
  ]
}}

RULES:
- tier "prerequisite": foundational knowledge the text assumes the reader already has
- tier "intermediate": bridging concepts that connect prerequisites to the main ideas
- tier "target": the main concepts the text is teaching
- Edges flow from simpler to more complex (prerequisite -> dependent concept)
- Each concept must have at least one edge connection
- Labels should be 1-3 words
- Use the noun phrases as hints but include important concepts even if not in the list
- Return 5-15 concepts total
- Every edge "from" and "to" must reference a valid concept id"""

        response = self.client.chat.completions.create(
            model=FIREWORKS_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1500
        )

        content = response.choices[0].message.content.strip()
        result = self._parse_json_response(content)

        if result:
            result = self._validate_graph(result)

        return result

    def _parse_json_response(self, content):
        """Parse JSON from LLM response, stripping markdown if present."""
        if not content:
            return None

        cleaned = content.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('```')[1]
            if cleaned.startswith('json'):
                cleaned = cleaned[4:]
        try:
            return json.loads(cleaned)
        except Exception:
            try:
                start = cleaned.find('{')
                end = cleaned.rfind('}')
                if start != -1 and end != -1:
                    return json.loads(cleaned[start:end + 1])
            except Exception:
                pass
            print(f"Failed to parse concept graph JSON: {cleaned[:200]}")
            return None

    def _validate_graph(self, data):
        """Validate and clean the concept graph data."""
        if not isinstance(data, dict):
            return None

        concepts = data.get('concepts', [])
        edges = data.get('edges', [])

        if not concepts or len(concepts) < 2:
            return None

        valid_ids = set()
        clean_concepts = []
        for c in concepts:
            if not isinstance(c, dict):
                continue
            cid = c.get('id', '')
            label = c.get('label', '')
            tier = c.get('tier', 'intermediate')
            if not cid or not label:
                continue
            if tier not in ('prerequisite', 'intermediate', 'target'):
                tier = 'intermediate'
            valid_ids.add(cid)
            clean_concepts.append({
                'id': cid,
                'label': label,
                'tier': tier,
                'description': c.get('description', ''),
            })

        clean_edges = []
        connected_ids = set()
        for e in edges:
            if not isinstance(e, dict):
                continue
            src = e.get('from', '')
            tgt = e.get('to', '')
            if src in valid_ids and tgt in valid_ids and src != tgt:
                clean_edges.append({
                    'from': src,
                    'to': tgt,
                    'relationship': e.get('relationship', 'required_for'),
                })
                connected_ids.add(src)
                connected_ids.add(tgt)

        clean_concepts = [c for c in clean_concepts if c['id'] in connected_ids]

        if len(clean_concepts) < 2 or len(clean_edges) < 1:
            return None

        return {
            'concepts': clean_concepts,
            'edges': clean_edges,
        }
