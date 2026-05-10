import React, { useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText, Upload, Image, Mic, MicOff, AlertCircle, CheckCircle, Loader2, Sparkles
} from 'lucide-react';
import { analysisApi, textApi } from '../../services/api';
import LoadingSpinner from '../common/LoadingSpinner';

type InputMethod = 'text' | 'pdf' | 'doc' | 'image' | 'voice';

const SAMPLE_CATEGORIES = ['Elementary', 'Middle School', 'High School', 'College'] as const;

const gradeButtonStyle = (label: string): React.CSSProperties => {
  const n = label === 'College' ? 13 : parseInt(label.replace('Grade ', '')) || 0;
  if (n <= 5) return {
    background: 'var(--ok-50)', color: 'var(--ok-700)',
    border: '1px solid color-mix(in srgb, var(--ok-500) 25%, transparent)',
  };
  if (n <= 8) return {
    background: 'var(--warn-50)', color: 'var(--warn-700)',
    border: '1px solid color-mix(in srgb, var(--warn-500) 25%, transparent)',
  };
  if (n <= 10) return {
    background: 'var(--a-50)', color: 'var(--a-700)',
    border: '1px solid color-mix(in srgb, var(--a-500) 25%, transparent)',
  };
  if (n <= 12) return {
    background: 'var(--err-50)', color: 'var(--err-700)',
    border: '1px solid color-mix(in srgb, var(--err-500) 25%, transparent)',
  };
  return {
    background: 'var(--p-50)', color: 'var(--p-700)',
    border: '1px solid color-mix(in srgb, var(--p-500) 25%, transparent)',
  };
};

const SAMPLE_TEXTS = [
  {
    label: 'Grade 3',
    category: 'Elementary' as const,
    title: 'Tom and Max',
    reason: 'Short sentences averaging 8-10 words. All common 1-2 syllable words (dog, run, play, ball). Simple subject-verb sentence patterns. Concrete, familiar topic about a boy and his pet.',
    text: "Tom had a small brown dog named Max who liked to run and play all day. Every day after lunch Tom and Max would go to the big park near their house. Tom threw a red ball far across the green grass for Max to fetch. Max would run as fast as he could to bring the ball back to Tom.\n\nOne warm day they took a long walk down to the old pond near the farm. They saw some fat ducks on the clear blue water by the tall grass. Max barked at the ducks but they did not seem to care at all about him. Tom held Max back so he would not jump in the cold water after them.\n\nAfter their walk they went home and Tom gave Max some food and cool water. Max ate all of his food and then lay down on his soft warm bed to rest. That night Tom sat next to Max and read a new book about ships and the deep blue sea. Max slept on the rug near his feet while the fire kept them warm.",
  },
  {
    label: 'Grade 4',
    category: 'Elementary' as const,
    title: 'Our Garden',
    reason: 'Sentences average 12-14 words. Mostly 1-2 syllable words with a few longer ones (garden, morning, season). Simple compound sentences using "and"/"but". Familiar topic about family gardening.',
    text: "My dad keeps a small garden behind our house where we grow fresh food each year. He helps us dig rows in the soft brown dirt before we plant the tiny seeds. We put them in the ground about one inch deep and press the dirt down flat over them. Then we give each row a good long drink of water from the green hose.\n\nAfter about two weeks small green shoots start to push up through the dirt. We have to pull the weeds out so they do not crowd our tender young plants. The leaves get bigger as the days grow longer and the warm sun shines down on them. Bugs try to eat the leaves but we pick them off by hand each morning before school.\n\nBy the end of summer we can pick food right from our own back yard garden plot. Mom makes a fresh salad from the green beans and ripe red fruits that we grew over the season. Dad likes to grill the corn on the cob that grows tall along the back fence of the yard. We always share some of our extra food with the kind folks who live next door to us.\n\nGrowing food takes a lot of care but the fresh taste makes it all worth the hard work we put in.",
  },
  {
    label: 'Grade 5',
    category: 'Elementary' as const,
    title: 'The Water Cycle',
    reason: 'Introduces basic science vocabulary (vapor, cycle, residents). Sentences average 12-13 words. Simple cause-and-effect relationships. Transitions from personal narrative to informational academic text.',
    text: "Water moves through nature in a pattern called the water cycle. The sun heats lakes and oceans until some of the water turns into vapor. This vapor rises into the sky and forms clouds high above. When the clouds hold enough water it falls back down as rain or snow.\n\nRain water flows into streams and rivers that carry it to the ocean. Some water soaks into the ground between rocks and layers of soil. Plants use this water through their roots to grow and stay healthy. Animals also drink from streams and ponds along the way.\n\nPeople need the water cycle to keep working for clean drinking water. Farmers depend on regular rainfall to keep their crops growing each year. Towns build holding ponds to collect and store water for their residents. Without enough rain the crops can fail and people may run short.\n\nScientists study the water cycle to predict when storms or dry spells might come. They look at how dry spells affect different parts of the country. This research helps communities plan ahead and save water when it is needed.",
  },
  {
    label: 'Grade 6',
    category: 'Middle School' as const,
    title: "Earth's Moving Layers",
    reason: 'Longer sentences averaging about 15 words. Academic vocabulary appears (tectonic plates, crust, buckle, trenches, instruments). Subordinate clauses add complexity. Abstract geoscience concepts about plate tectonics.',
    text: "Deep below the ground there are layers of hot rock that slowly move and shift over time. This heated rock sometimes pushes up through cracks in the outer crust of the planet. When it reaches the surface it may flow out as melted rock and reshape the land nearby. These events have formed many of the mountains and valleys that we see around the world.\n\nThe outer layer of the planet is broken into large tectonic plates that float on softer rock below. These giant pieces move very slowly and may push against each other with great force. Where two pieces press together the ground can buckle and form tall mountain ranges. Where they pull apart, valleys and trenches may form and fill with water.\n\nEarthquakes happen when stored energy between moving pieces gets released all at once. The ground shakes and buildings may crack or fall down during a strong release. Scientists use sensitive instruments in the ground to measure these movements. They study the patterns of past quakes to learn where future ones might happen.\n\nPeople who live near active zones should prepare for sudden ground movements. Families need clear emergency plans ready before shaking starts because a few practiced steps can prevent serious injuries. Schools and offices practice drills so that everyone knows the right steps to take.",
  },
  {
    label: 'Grade 7',
    category: 'Middle School' as const,
    title: 'Body Systems',
    reason: 'Sentences average 18-22 words. Technical vocabulary (vessels, tissue, sensory, nerve signals). Multi-clause complex sentences. Requires understanding of interconnected biological systems.',
    text: "The human body relies on several major systems that work closely together to maintain good health. The heart pumps blood through a network of vessels that carry needed air and food to every living cell. The lungs take in clean air and remove the waste gas that builds up when cells break down food. These two vital systems depend on each other to keep the whole body running the right way.\n\nThe system that handles food begins its work in the mouth where the teeth crush each bite into smaller parts. This process then moves down to the stomach where stronger acids break apart the tougher portions of each meal. The useful parts of the food pass into the blood and travel through the body to reach the cells. Each cell uses these building blocks for growth and repair of worn or damaged tissue over time.\n\nThe brain serves as the main control center that sends signals through a network of nerves across the body. These signals direct the actions we choose to perform such as running or writing words on paper. They also manage things that happen without our thinking about them like breathing and heart rate. Sensory input from the eyes and ears flows into the brain where it gets sorted and turned into responses.\n\nWhen one system in the body becomes weak it can reduce the working power of other linked systems.",
  },
  {
    label: 'Grade 8',
    category: 'Middle School' as const,
    title: 'Weather Patterns',
    reason: 'Long sentences averaging 20-25 words. Technical weather vocabulary (pressure systems, precipitation, climate zones, fronts). Multi-clause sentences with embedded information. Interconnected scientific concepts.',
    text: "Weather patterns across the planet are driven by the way the sun heats the surface of land and water. Places closer to the middle of the globe get stronger sunlight and tend to have warmer weather than the polar zones. This gap in warmth between the regions creates broad movements of air and moisture that form the major wind patterns. Ocean currents also carry warmer and cooler water between the different climate zones around the world.\n\nWater vapor plays a key role in creating storms and the rainfall that shapes the weather in each region of the world. When moist air rises and starts to cool the vapor turns into tiny water drops that cluster and form clouds in the sky above. If enough moisture gathers in one area then the heavy clouds release their water as rain or sometimes as frozen snow. The amount of rainfall that a region gets during a normal year helps decide what kind of climate and plant life the area will support.\n\nPressure systems are another major factor in shaping local weather patterns from one day to the next. Higher pressure zones often produce clear skies and calm settled weather that can last for several days at a time. Lower pressure draws in moist air from nearby and often brings cloudy skies along with stormy weather and strong winds. The line where two pressure systems meet is called a front and it often brings rapid and sudden changes to the weather.\n\nModern weather science uses data from the sky and machine models to predict what is coming next for each area.",
  },
  {
    label: 'Grade 9',
    category: 'High School' as const,
    title: 'Electricity and Circuits',
    reason: 'Sentences averaging 19-20 words. Technical physics vocabulary (voltage, current, resistance, magnetic fields). Abstract cause-effect reasoning. Requires understanding of interconnected electrical principles.',
    text: "Power flows through wires and circuits to drive the many tools and devices that people depend on each day. The movement of tiny charged bits through a metal wire creates a steady stream of working power between any two linked points. Copper wire is widely used as a conductor because the charged bits travel through it with very little slowing. Knowing how power flow works in different circuit types is essential for those who design and build working systems.\n\nVoltage gives the push that moves charged bits forward through a circuit from the source to the load. Higher voltage causes a greater amount of current to flow through the same wire between any two points. The property that limits how freely bits can move and controls how much current will pass is called resistance. These three quantities are linked by a basic rule that trained engineers apply when they design and test circuits.\n\nMagnetic fields appear around a wire when electric current passes through it and these fields can be used to create motion. This connection between magnetic fields and current forms the basic principle behind both electric motors and generators. Motors change incoming current into spinning motion that can power tools and many common devices found in the home. Generators work in reverse by converting mechanical motion back into electrical current for delivery across the power grid.",
  },
  {
    label: 'Grade 10',
    category: 'High School' as const,
    title: 'Markets and Economics',
    reason: 'Long academic sentences averaging about 21 words. Economics vocabulary (supply, demand, monetary policy, lending rates, exchange rates). Abstract market concepts with layered reasoning about economic systems.',
    text: "Markets follow the basic rules of supply and demand that control how goods and services are valued within the broader trading system. When the demand for a certain product rises while the amount being made stays limited the market price will tend to go up. Makers then respond to these higher prices by stepping up their output because they stand to earn greater returns from selling more units. Over time the greater supply of the product slowly meets the demand and the market price settles back toward a stable balance point.\n\nChoices made by those who govern also shape the market through changes in tax levels and the pattern of public spending on shared needs. Higher tax rates on the money that workers earn reduce the total buying power that shoppers have on hand for getting goods and services. The central bank may adjust monetary policy and lending rates. Those choices affect borrowing costs for firms that want to grow. These choices about lending rates and money supply can either boost broader market action during slower periods or hold things back when the market runs too hot.\n\nTrade between nations creates added layers of depth within the modern linked global market system that joins countries across the world. Single nations tend to focus their efforts on making the goods in which they hold certain clear strengths over their partner countries in other regions. The rates at which one form of money trades for another shift based on the relative strength of each nation and directly affect pricing. Formal trade deals between nations aim to lower barriers and promote the smoother movement of goods across their shared borders.",
  },
  {
    label: 'Grade 11',
    category: 'High School' as const,
    title: 'Ecosystems and Energy',
    reason: 'Very long sentences averaging about 25 words. Advanced science vocabulary (ecosystems, carbon, uptake, habitat, cycles). Complex interdependent systems across multiple biological scales.',
    text: "Living systems in nature depend on the steady movement of useful power through complex networks of creatures within linked habitat regions that support diverse groupings of life. Green plants capture sunlight and transform it into stored food through a basic process that takes place inside the special working cells within their leaves. Creatures that feed upon these plants then convert the stored food into body tissue along with the working force needed for the daily tasks of staying alive. Those hunters that feed at upper levels of the food chain obtain the power they need by catching and feeding upon the plant feeding creatures below them.\n\nKey building blocks cycle without pause through living things and the world around them in a finely kept balance that supports the health of whole natural groupings. Carbon moves between the air above and living systems below through the breathing process and the slow breaking down of dead matter on the forest floor over long spans of time. Another vital element enters the ground soil mainly through the working action of tiny living things in the dirt and then becomes ready for uptake through the root systems of plants. Water cycles between the sea and the air through patterns of rainfall and the return flow of surface water toward major river systems across the planet.\n\nModern industry and farming have upset these natural cycles. In many regions the rate of change exceeds the ability of living systems to recover. The widespread clearing of forest land for farming use removes vital habitat areas and greatly cuts the ability of the land to pull harmful gases out of the air above. Dumping of waste from factories slowly breaks down water sources and drains the soil of the building blocks upon which entire networks of living things depend for their long term health.",
  },
  {
    label: 'Grade 12',
    category: 'High School' as const,
    title: 'The Scientific Method',
    reason: 'Very long sentences of 30+ words. Sophisticated vocabulary (hypothetico-deductive, falsification, paradigmatic). Philosophy of science concepts requiring abstract meta-level reasoning about how knowledge is built.',
    text: "What we know about the natural world grows through a careful process of forming ideas about how things work and then testing those ideas against the hard facts gathered from planned study. Those who carry out this research work tend to begin by spotting patterns in what they observe and then building early working models to explain what they found. These proposed ways of thinking must then produce certain claims that can be checked through controlled test setups or through further rounds of planned study. Only those models that hold up after being tested again and again and that produce steady and trusted results across many different research programs gain broad support.\n\nThe rule that a valid claim about the natural world must be stated in terms that would allow contrary facts to show it is wrong serves as a key standard in this form of thinking. This basic standard draws a clear and useful line between reasoned study of the natural world and other ways of building knowledge that rest mainly upon personal feeling or long held custom. A working model of how things function gains standing not simply by gathering supporting facts in its favor but rather by holding up against sustained and purposeful efforts to prove it wrong. The most lasting models of how the world works have held up for decades of close review while staying in line with the full body of facts that have been gathered over time.\n\nThe path of progress in our grasp of the natural world rarely follows a straight line forward but instead tends to involve extended stretches of deep rethinking about the basic ideas that support an entire field of study. Well known working models may from time to time run into stubborn findings from the real world that simply refuse to fit within the currently held way of thinking about the matter. When enough of these problem cases build up a major shift in thinking may take place that reshapes the very basis of an entire field of research and opens new doors of understanding.",
  },
  {
    label: 'College',
    category: 'College' as const,
    title: 'Knowledge and Epistemology',
    reason: 'Dense academic vocabulary (empirical, replication, falsification, pseudoscience, anomalies). Abstract philosophical analysis about knowledge, evidence, expertise, and the limits of scientific authority.',
    text: "Debates about how people gain reliable knowledge of the natural world require careful attention to the methods that guide research. The movement between empirical observation and abstract theory remains a contested issue because scholars disagree about where evidence ends and interpretation begins. Researchers who study knowledge production often focus on the systems of review, replication, and criticism that turn individual findings into claims a discipline can trust. These practices give scientific work its authority while also leaving each claim open to later revision.\n\nModern critics have questioned the older belief that a single neutral method can produce perfectly objective truth. They argue that research is shaped by language, culture, funding, and professional expectations, all of which influence what questions are asked and which answers seem convincing. This criticism does not mean that every claim is equally valid. Instead, it asks academic communities to explain how they identify bias, correct errors, and protect evidence from becoming only a reflection of shared assumptions.\n\nThe problem of separating science from pseudoscience also remains difficult. Karl Popper argued that a scientific claim must be open to falsification, meaning that some possible evidence could show it to be wrong. Later philosophers challenged this view by noting that scientists do not abandon a theory after every failed prediction. A research tradition often survives because it organizes useful questions, methods, and background beliefs, even while unresolved anomalies slowly build pressure for change.\n\nThese debates matter beyond philosophy because public decisions about medicine, climate, technology, and education depend on expert claims. A strong theory of knowledge must explain why expertise deserves trust while also showing how citizens can question institutions without rejecting evidence altogether.",
  },
];

const TextInput: React.FC = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<InputMethod>('text');
  const [text, setText] = useState('');
  const [title, setTitle] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [extractionWarnings, setExtractionWarnings] = useState<string[]>([]);
  const [selectedReason, setSelectedReason] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  const tabs = [
    { id: 'text' as InputMethod, label: 'Text', icon: FileText },
    { id: 'pdf' as InputMethod, label: 'PDF', icon: Upload },
    { id: 'doc' as InputMethod, label: 'DOC/DOCX', icon: Upload },
    { id: 'image' as InputMethod, label: 'Image (OCR)', icon: Image },
    { id: 'voice' as InputMethod, label: 'Voice', icon: Mic },
  ];

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setError(null);
    setSuccess(null);
    setExtractionWarnings([]);
    setIsLoading(true);

    try {
      let result;
      if (activeTab === 'pdf') {
        result = await textApi.extractPdf(file);
        const warnings = result.warnings || [];
        setExtractionWarnings(warnings);
        setSuccess(
          `Extracted text from ${result.pageCount} pages${warnings.length ? ' with quality warnings' : ''}`
        );
      } else if (activeTab === 'doc') {
        result = await textApi.extractDoc(file);
        setSuccess('Text extracted successfully');
      } else if (activeTab === 'image') {
        result = await textApi.extractImage(file);
        setSuccess(`Text extracted with ${result.confidence}% confidence`);
      }

      if (result?.text) {
        setText(result.text);
        setTitle(file.name.replace(/\.[^/.]+$/, ''));
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Error extracting text';
      if (typeof err === 'object' && err !== null && 'response' in err) {
        const axiosError = err as { response?: { data?: { error?: string } } };
        setError(axiosError.response?.data?.error || errorMessage);
      } else {
        setError(errorMessage);
      }
    } finally {
      setIsLoading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const startRecording = useCallback(() => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      setError('Speech recognition is not supported in this browser');
      return;
    }

    const SpeechRecognition = (window as Window & { SpeechRecognition?: new () => SpeechRecognition; webkitSpeechRecognition?: new () => SpeechRecognition }).SpeechRecognition || (window as Window & { webkitSpeechRecognition: new () => SpeechRecognition }).webkitSpeechRecognition;
    const recognition = new SpeechRecognition();

    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let finalTranscript = '';
      let interimTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript + ' ';
        } else {
          interimTranscript += transcript;
        }
      }

      setText((prev) => prev + finalTranscript);
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      setError(`Speech recognition error: ${event.error}`);
      setIsRecording(false);
    };

    recognition.onend = () => {
      setIsRecording(false);
    };

    recognitionRef.current = recognition;
    recognition.start();
    setIsRecording(true);
    setError(null);
  }, []);

  const stopRecording = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      setIsRecording(false);
    }
  }, []);

  const handleAnalyze = async () => {
    if (text.trim().length < 50) {
      setError('Please enter at least 50 characters of text');
      return;
    }

    setError(null);
    setIsLoading(true);

    try {
      const result = await analysisApi.analyze(text, title || undefined);
      navigate(`/analysis/${result.analysisId}`, { state: { analysis: result, originalText: text } });
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Error analyzing text';
      if (typeof err === 'object' && err !== null && 'response' in err) {
        const axiosError = err as { response?: { data?: { error?: string } } };
        setError(axiosError.response?.data?.error || errorMessage);
      } else {
        setError(errorMessage);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const getFileAccept = () => {
    switch (activeTab) {
      case 'pdf':
        return '.pdf';
      case 'doc':
        return '.doc,.docx';
      case 'image':
        return '.jpg,.jpeg,.png';
      default:
        return '';
    }
  };

  const wordCount = text.trim().split(/\s+/).filter(Boolean).length;
  const charCount = text.length;

  const validityState = (() => {
    if (wordCount === 0) return { label: 'Enter text to begin', tone: 'neutral' as const };
    if (wordCount < 50) return { label: `${50 - wordCount} more words needed`, tone: 'warn' as const };
    if (wordCount > 50000) return { label: 'Exceeds 50,000 word limit', tone: 'err' as const };
    return { label: 'Ready for analysis', tone: 'ok' as const };
  })();

  return (
    <div className="space-y-6">
      {isLoading && <LoadingSpinner message="Analyzing text..." fullScreen />}

      {/* Hero */}
      <section>
        <span className="cw-eyebrow">Analysis Workbench</span>
        <h1 className="cw-hero mt-2">New Analysis</h1>
        <p className="mt-2" style={{ color: 'var(--text-2)', fontSize: 13 }}>
          Enter or upload text. Minimum 50 words — maximum 50,000.
        </p>
      </section>

      {/* Meta row: word count + title */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="cw-card cw-card-pad lg:col-span-1">
          <div className="flex items-center justify-between mb-1">
            <span className="cw-eyebrow">Word Count</span>
            <FileText className="w-3.5 h-3.5" style={{ color: 'var(--text-4)' }} />
          </div>
          <div
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: 30,
              fontWeight: 800,
              letterSpacing: '-0.02em',
              color: 'var(--p-900)',
              lineHeight: 1,
            }}
          >
            {wordCount.toLocaleString()}
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span
              className={`cw-badge ${
                validityState.tone === 'ok'
                  ? 'cw-badge-ok'
                  : validityState.tone === 'err'
                  ? 'cw-badge-err'
                  : validityState.tone === 'warn'
                  ? 'cw-badge-warn'
                  : 'cw-badge-neutral'
              }`}
            >
              {validityState.label}
            </span>
            <span style={{ fontSize: 10.5, color: 'var(--text-4)' }}>{charCount.toLocaleString()} chars</span>
          </div>
        </div>

        <div className="lg:col-span-2 cw-card cw-card-pad">
          <label className="cw-eyebrow block mb-2">Title (optional)</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Give your analysis a title…"
            className="cw-input"
            style={{ height: 40, fontSize: 13.5 }}
          />
          <p className="mt-2" style={{ fontSize: 11, color: 'var(--text-4)' }}>
            Auto-generated from file name when uploading.
          </p>
        </div>
      </section>

      {/* Input surface */}
      <section className="cw-card overflow-hidden">
        {/* Tab rail */}
        <div className="flex items-center" style={{ borderBottom: '1px solid var(--divider)' }}>
          {tabs.map((tab) => {
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className="flex-1 flex items-center justify-center gap-2 py-3 transition-colors relative"
                style={{
                  fontSize: 12,
                  fontWeight: active ? 600 : 500,
                  color: active ? 'var(--p-900)' : 'var(--text-3)',
                  background: active ? 'var(--surface-alt)' : 'transparent',
                }}
              >
                {active && (
                  <span
                    className="absolute bottom-0 left-0 right-0"
                    style={{ height: 2, background: 'var(--p-900)' }}
                  />
                )}
                <tab.icon className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">{tab.label}</span>
              </button>
            );
          })}
        </div>

        <div className="p-5">
          {/* Alerts */}
          {error && (
            <div
              className="mb-3 px-3.5 py-2.5 flex items-center gap-2 rounded-md"
              style={{
                background: 'var(--err-50)',
                color: 'var(--err-700)',
                fontSize: 12.5,
                border: '1px solid color-mix(in srgb, var(--err-500) 22%, transparent)',
              }}
            >
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}
          {success && (
            <div
              className="mb-3 px-3.5 py-2.5 flex items-center gap-2 rounded-md"
              style={{
                background: 'var(--ok-50)',
                color: 'var(--ok-700)',
                fontSize: 12.5,
                border: '1px solid color-mix(in srgb, var(--ok-500) 22%, transparent)',
              }}
            >
              <CheckCircle className="w-4 h-4 flex-shrink-0" />
              <span>{success}</span>
            </div>
          )}
          {extractionWarnings.length > 0 && (
            <div
              className="mb-3 px-3.5 py-2.5 rounded-md"
              style={{
                background: 'var(--warn-50)',
                color: 'var(--warn-700)',
                fontSize: 12.5,
                border: '1px solid color-mix(in srgb, var(--warn-500) 28%, transparent)',
              }}
            >
              <div className="flex items-start gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <div>
                  {extractionWarnings.map((warning, index) => (
                    <div key={`${warning}-${index}`}>{warning}</div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Text */}
          {activeTab === 'text' && (
            <div>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Paste or type your text here…"
                className="cw-textarea"
                style={{ minHeight: 260, fontSize: 13.5, lineHeight: 1.6 }}
              />
              <div
                className="flex justify-between mt-2"
                style={{ fontSize: 10.5, color: 'var(--text-4)', letterSpacing: '0.04em' }}
              >
                <span>{wordCount.toLocaleString()} WORDS</span>
                <span>{charCount.toLocaleString()} / 50,000 CHARS</span>
              </div>

              {/* Samples */}
              <div
                className="mt-5 rounded-lg"
                style={{ background: 'var(--surface-alt)', padding: 14 }}
              >
                <div className="flex items-center gap-2 mb-3">
                  <Sparkles className="w-3.5 h-3.5" style={{ color: 'var(--p-700)' }} />
                  <span className="cw-eyebrow" style={{ color: 'var(--text-2)' }}>
                    Try a calibrated sample
                  </span>
                </div>
                <div className="space-y-2.5">
                  {SAMPLE_CATEGORIES.map((category) => (
                    <div key={category} className="flex items-center gap-2 flex-wrap">
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          letterSpacing: '0.1em',
                          textTransform: 'uppercase',
                          color: 'var(--text-4)',
                          width: 104,
                        }}
                        className="flex-shrink-0"
                      >
                        {category}
                      </span>
                      {SAMPLE_TEXTS.filter((s) => s.category === category).map((sample) => (
                        <button
                          key={sample.label}
                          onClick={() => {
                            setText(sample.text);
                            setTitle(sample.title);
                            setSelectedReason(sample.reason);
                            setError(null);
                            setSuccess(null);
                          }}
                          className="cw-btn cw-btn-sm"
                          style={gradeButtonStyle(sample.label)}
                        >
                          {sample.label}
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
                {selectedReason && (
                  <div
                    className="mt-3 rounded-md"
                    style={{
                      background: 'var(--surface-raised)',
                      padding: '10px 12px',
                      borderLeft: '2px solid var(--p-700)',
                    }}
                  >
                    <p
                      style={{
                        fontSize: 10.5,
                        fontWeight: 700,
                        color: 'var(--p-900)',
                        letterSpacing: '0.08em',
                        textTransform: 'uppercase',
                        marginBottom: 4,
                      }}
                    >
                      Why this grade level
                    </p>
                    <p style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.5 }}>{selectedReason}</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* File Upload */}
          {(activeTab === 'pdf' || activeTab === 'doc' || activeTab === 'image') && (
            <div>
              <div
                onClick={() => fileInputRef.current?.click()}
                className="cursor-pointer text-center transition-colors"
                style={{
                  border: '1px dashed var(--border-strong)',
                  borderRadius: 'var(--r-lg)',
                  padding: '40px 20px',
                  background: 'var(--surface-alt)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--p-500)';
                  e.currentTarget.style.background = 'color-mix(in srgb, var(--p-500) 5%, var(--surface-alt))';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--border-strong)';
                  e.currentTarget.style.background = 'var(--surface-alt)';
                }}
              >
                <Upload className="w-8 h-8 mx-auto mb-3" style={{ color: 'var(--text-3)' }} />
                <p style={{ color: 'var(--text-1)', fontSize: 13, fontWeight: 600 }}>
                  Click to upload a file
                </p>
                <p className="mt-1" style={{ color: 'var(--text-4)', fontSize: 11.5 }}>
                  {activeTab === 'pdf' && 'PDF files up to 10 MB'}
                  {activeTab === 'doc' && 'DOC or DOCX files up to 10 MB'}
                  {activeTab === 'image' && 'JPG, JPEG or PNG files up to 5 MB'}
                </p>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept={getFileAccept()}
                onChange={handleFileUpload}
                className="hidden"
              />

              {text && (
                <div className="mt-5">
                  <label className="cw-eyebrow block mb-1.5">Extracted Text (editable)</label>
                  <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    className="cw-textarea"
                    style={{ minHeight: 200, fontSize: 13.5, lineHeight: 1.6 }}
                  />
                  <div
                    className="flex justify-between mt-2"
                    style={{ fontSize: 10.5, color: 'var(--text-4)', letterSpacing: '0.04em' }}
                  >
                    <span>{wordCount.toLocaleString()} WORDS</span>
                    <span>{charCount.toLocaleString()} CHARS</span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Voice */}
          {activeTab === 'voice' && (
            <div>
              <div className="text-center py-6">
                <button
                  onClick={isRecording ? stopRecording : startRecording}
                  className="grid place-items-center mx-auto transition-all"
                  style={{
                    width: 96,
                    height: 96,
                    borderRadius: '50%',
                    background: isRecording ? 'var(--err-500)' : 'var(--g-scholar)',
                    color: '#fff',
                    boxShadow: isRecording ? '0 0 0 8px color-mix(in srgb, var(--err-500) 22%, transparent)' : 'var(--sh-3)',
                    animation: isRecording ? 'pulse 1.6s ease-in-out infinite' : 'none',
                  }}
                >
                  {isRecording ? <MicOff className="w-8 h-8" /> : <Mic className="w-8 h-8" />}
                </button>
                <p className="mt-3" style={{ color: 'var(--text-2)', fontSize: 12.5, fontWeight: 500 }}>
                  {isRecording ? 'Recording · click to stop' : 'Click to start recording'}
                </p>
                {!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window) && (
                  <p className="mt-2" style={{ fontSize: 11, color: 'var(--warn-700)' }}>
                    Speech recognition may not be supported in this browser
                  </p>
                )}
              </div>

              {text && (
                <div className="mt-3">
                  <label className="cw-eyebrow block mb-1.5">Transcribed Text (editable)</label>
                  <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    className="cw-textarea"
                    style={{ minHeight: 180, fontSize: 13.5, lineHeight: 1.6 }}
                  />
                  <div
                    className="flex justify-between mt-2"
                    style={{ fontSize: 10.5, color: 'var(--text-4)', letterSpacing: '0.04em' }}
                  >
                    <span>{wordCount.toLocaleString()} WORDS</span>
                    <span>{charCount.toLocaleString()} CHARS</span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      {/* Action row */}
      <section className="flex items-center justify-end gap-2">
        <button
          onClick={handleAnalyze}
          disabled={isLoading || text.trim().length < 50}
          className="cw-btn cw-btn-primary cw-btn-lg"
          style={{ minWidth: 200 }}
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Analyzing…
            </>
          ) : (
            <>
              Analyze Text
              <Sparkles className="w-4 h-4" />
            </>
          )}
        </button>
      </section>
    </div>
  );
};

export default TextInput;
