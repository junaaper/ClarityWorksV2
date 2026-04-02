import React, { useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText, Upload, Image, Mic, MicOff, AlertCircle, CheckCircle, Loader2, Sparkles
} from 'lucide-react';
import { analysisApi, textApi } from '../../services/api';
import LoadingSpinner from '../common/LoadingSpinner';

type InputMethod = 'text' | 'pdf' | 'doc' | 'image' | 'voice';

const SAMPLE_CATEGORIES = ['Elementary', 'Middle School', 'High School', 'College'] as const;

const SAMPLE_TEXTS = [
  {
    label: 'Grade 3',
    category: 'Elementary' as const,
    color: 'bg-green-100 text-green-700 hover:bg-green-200 border-green-300',
    title: 'Tom and Max',
    reason: 'Short sentences averaging 8-10 words. All common 1-2 syllable words (dog, run, play, ball). Simple subject-verb sentence patterns. Concrete, familiar topic about a boy and his pet.',
    text: "Tom had a small brown dog named Max who liked to run and play all day. Every day after lunch Tom and Max would go to the big park near their house. Tom threw a red ball far across the green grass for Max to fetch. Max would run as fast as he could to bring the ball back to Tom.\n\nOne warm day they took a long walk down to the old pond near the farm. They saw some fat ducks on the clear blue water by the tall grass. Max barked at the ducks but they did not seem to care at all about him. Tom held Max back so he would not jump in the cold water after them.\n\nAfter their walk they went home and Tom gave Max some food and cool water. Max ate all of his food and then lay down on his soft warm bed to rest. That night Tom sat next to Max and read a new book about ships and the deep blue sea. Max slept on the rug near his feet while the fire kept them warm.",
  },
  {
    label: 'Grade 4',
    category: 'Elementary' as const,
    color: 'bg-green-100 text-green-700 hover:bg-green-200 border-green-300',
    title: 'Our Garden',
    reason: 'Sentences average 12-14 words. Mostly 1-2 syllable words with a few longer ones (garden, morning, season). Simple compound sentences using "and"/"but". Familiar topic about family gardening.',
    text: "My dad keeps a small garden behind our house where we grow fresh food each year. He helps us dig rows in the soft brown dirt before we plant the tiny seeds. We put them in the ground about one inch deep and press the dirt down flat over them. Then we give each row a good long drink of water from the green hose.\n\nAfter about two weeks small green shoots start to push up through the dirt. We have to pull the weeds out so they do not crowd our tender young plants. The leaves get bigger as the days grow longer and the warm sun shines down on them. Bugs try to eat the leaves but we pick them off by hand each morning before school.\n\nBy the end of summer we can pick food right from our own back yard garden plot. Mom makes a fresh salad from the green beans and ripe red fruits that we grew over the season. Dad likes to grill the corn on the cob that grows tall along the back fence of the yard. We always share some of our extra food with the kind folks who live next door to us.\n\nGrowing food takes a lot of care but the fresh taste makes it all worth the hard work we put in.",
  },
  {
    label: 'Grade 5',
    category: 'Elementary' as const,
    color: 'bg-green-100 text-green-700 hover:bg-green-200 border-green-300',
    title: 'The Water Cycle',
    reason: 'Introduces basic science vocabulary (vapor, cycle, residents). Sentences average 13-15 words. Simple cause-and-effect relationships. Transitions from personal narrative to informational academic text.',
    text: "Water moves through nature in a pattern called the water cycle. The sun heats lakes and oceans until some water turns into vapor. This vapor rises into the sky and forms clouds. When the clouds hold enough water it falls back down as rain or snow.\n\nRain water flows into streams and rivers that carry it to the ocean. Some water soaks into the ground between rocks and soil. Plants use this water through their roots to grow and stay healthy. Animals also drink from streams and ponds along the way.\n\nPeople need the water cycle to keep working for clean drinking water. Farmers depend on regular rainfall to keep their crops growing. Towns build holding ponds to collect and store water for their residents. Without enough rain the crops can fail and people may run short.\n\nScientists study the water cycle to predict when storms might come. They also look at how dry spells affect different parts of the country. This helps communities plan ahead and save water when needed.",
  },
  {
    label: 'Grade 6',
    category: 'Middle School' as const,
    color: 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200 border-yellow-300',
    title: "Earth's Moving Layers",
    reason: 'Longer sentences averaging 16-18 words. Academic vocabulary appears (crust, buckle, trenches, energy). Subordinate clauses add complexity. Abstract geoscience concepts about plate tectonics.',
    text: "Deep below the ground there are layers of hot rock that slowly move and shift over time. This heated rock sometimes pushes up through cracks in the outer crust of the planet. When it reaches the surface it may flow out as melted rock and reshape the land nearby. These events have formed many of the mountains and valleys that we see around the world.\n\nThe outer layer of the planet is broken into large pieces that float on softer rock below. These giant pieces move very slowly and may push against each other with great force. Where two pieces press together the ground can buckle and form tall mountain ranges. Where they pull apart, valleys and trenches may form and fill with water.\n\nEarthquakes happen when stored energy between moving pieces gets released all at once. The ground shakes and buildings may crack or fall down during a strong release. Scientists use special tools in the ground to measure these movements. They study the patterns of past quakes to learn where future ones might happen.\n\nPeople who live near active zones should prepare for sudden ground movements. Families need clear safety plans ready for when shaking starts. Schools and offices practice drills so that everyone knows the right steps to take.",
  },
  {
    label: 'Grade 7',
    category: 'Middle School' as const,
    color: 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200 border-yellow-300',
    title: 'Body Systems',
    reason: 'Sentences average 18-22 words. Technical vocabulary (vessels, tissue, sensory, nerve signals). Multi-clause complex sentences. Requires understanding of interconnected biological systems.',
    text: "The human body relies on several major systems that work closely together to maintain good health. The heart pumps blood through a network of vessels that carry needed air and food to every living cell. The lungs take in clean air and remove the waste gas that builds up when cells break down food. These two vital systems depend on each other to keep the whole body running the right way.\n\nThe system that handles food begins its work in the mouth where the teeth crush each bite into smaller parts. This process then moves down to the stomach where stronger acids break apart the tougher portions of each meal. The useful parts of the food pass into the blood and travel through the body to reach the cells. Each cell uses these building blocks for growth and repair of worn or damaged tissue over time.\n\nThe brain serves as the main control center that sends signals through a network of nerves across the body. These signals direct the actions we choose to perform such as running or writing words on paper. They also manage things that happen without our thinking about them like breathing and heart rate. Sensory input from the eyes and ears flows into the brain where it gets sorted and turned into responses.\n\nWhen one system in the body becomes weak it can reduce the working power of other linked systems.",
  },
  {
    label: 'Grade 8',
    category: 'Middle School' as const,
    color: 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200 border-yellow-300',
    title: 'Weather Patterns',
    reason: 'Long sentences averaging 20-25 words. Technical weather vocabulary (pressure systems, precipitation, climate zones, fronts). Multi-clause sentences with embedded information. Interconnected scientific concepts.',
    text: "Weather patterns across the planet are driven by the way the sun heats the surface of land and water. Places closer to the middle of the globe get stronger sunlight and tend to have warmer weather than the polar zones. This gap in warmth between the regions creates broad movements of air and moisture that form the major wind patterns. Ocean currents also carry warmer and cooler water between the different climate zones around the world.\n\nWater vapor plays a key role in creating storms and the rainfall that shapes the weather in each region of the world. When moist air rises and starts to cool the vapor turns into tiny water drops that cluster and form clouds in the sky above. If enough moisture gathers in one area then the heavy clouds release their water as rain or sometimes as frozen snow. The amount of rainfall that a region gets during a normal year helps decide what kind of climate and plant life the area will support.\n\nPressure systems are another major factor in shaping local weather patterns from one day to the next. Higher pressure zones often produce clear skies and calm settled weather that can last for several days at a time. Lower pressure draws in moist air from nearby and often brings cloudy skies along with stormy weather and strong winds. The line where two pressure systems meet is called a front and it often brings rapid and sudden changes to the weather.\n\nModern weather science uses data from the sky and machine models to predict what is coming next for each area.",
  },
  {
    label: 'Grade 9',
    category: 'High School' as const,
    color: 'bg-orange-100 text-orange-700 hover:bg-orange-200 border-orange-300',
    title: 'Electricity and Circuits',
    reason: 'Complex sentences averaging 22-28 words. Technical physics vocabulary (voltage, current, resistance, circuits, electromagnetic). Abstract cause-effect reasoning about electromagnetic principles.',
    text: "Power flows through wires and circuits to drive many of the tools and devices that people depend on in their daily lives. The movement of tiny charged bits through a metal wire creates a steady stream of working power between any two linked points. Copper wire is widely chosen as a wiring metal because the charged bits travel through it with very little slowing of their forward motion. Knowing how this power flow acts in different circuit setups is quite useful for the people who design and build working power systems.\n\nVoltage gives the driving push that moves the charged bits forward through a full circuit from the source to the load and back again. Higher levels of voltage cause a greater amount of current to flow through the same length of wire between any two given points along the path. The opposing trait that limits how freely the bits can move through the wire and controls how much current will pass through is known as the load. These three linked traits follow a basic rule that trained workers use on a steady basis when they design and put together working power circuits.\n\nForce fields show up around a wire when current passes through it and these fields can be put to use in making motion and turning force. This key link between such force fields and the flow of current forms the basic working idea behind both turning machines and power making devices. Turning machines change incoming current into a spinning motion that can drive heavy tools and many common home devices found in most houses. The reverse type of device works the other way by changing spinning motion back into a steady flow of current for wider use across the power grid.",
  },
  {
    label: 'Grade 10',
    category: 'High School' as const,
    color: 'bg-orange-100 text-orange-700 hover:bg-orange-200 border-orange-300',
    title: 'Markets and Economics',
    reason: 'Long complex sentences averaging 25-30 words. Economics vocabulary (supply, demand, fiscal policy, monetary, exchange rates). Abstract market concepts with multi-layered argumentation about economic systems.',
    text: "Markets follow the basic rules of supply and demand that control how goods and services are valued within the broader trading system. When the demand for a certain product rises while the amount being made stays limited the market price will tend to go up. Makers then respond to these higher prices by stepping up their output because they stand to earn greater returns from selling more units. Over time the greater supply of the product slowly meets the demand and the market price settles back toward a stable balance point.\n\nChoices made by those who govern also shape the market through changes in tax levels and the pattern of public spending on shared needs. Higher tax rates on the money that workers earn reduce the total buying power that shoppers have on hand for getting goods and services. The central banking body may from time to time adjust lending rates which directly affect the cost of getting funds for firms that want to grow. These choices about lending rates and money supply can either boost broader market action during slower periods or hold things back when the market runs too hot.\n\nTrade between nations creates added layers of depth within the modern linked global market system that joins countries across the world. Single nations tend to focus their efforts on making the goods in which they hold certain clear strengths over their partner countries in other regions. The rates at which one form of money trades for another shift based on the relative strength of each nation and directly affect pricing. Formal trade deals between nations aim to lower barriers and promote the smoother movement of goods across their shared borders.",
  },
  {
    label: 'Grade 11',
    category: 'High School' as const,
    color: 'bg-red-100 text-red-700 hover:bg-red-200 border-red-300',
    title: 'Ecosystems and Energy',
    reason: 'Very long sentences averaging 28-35 words. Advanced science vocabulary (photosynthesis, nitrogen fixation, ecosystem, trophic). Complex interdependent systems across multiple biological scales.',
    text: "Living systems in nature depend on the steady movement of useful power through complex networks of creatures within linked habitat regions that support diverse groupings of life. Green plants capture sunlight and transform it into stored food through a basic process that takes place inside the special working cells within their leaves. Creatures that feed upon these plants then convert the stored food into body tissue along with the working force needed for the daily tasks of staying alive. Those hunters that feed at upper levels of the food chain obtain the power they need by catching and feeding upon the plant feeding creatures below them.\n\nKey building blocks cycle without pause through living things and the world around them in a finely kept balance that supports the health of whole natural groupings. Carbon moves between the air above and living systems below through the breathing process and the slow breaking down of dead matter on the forest floor over long spans of time. Another vital element enters the ground soil mainly through the working action of tiny living things in the dirt and then becomes ready for uptake through the root systems of plants. Water cycles between the sea and the air through patterns of rainfall and the return flow of surface water toward major river systems across the planet.\n\nHuman factory and farming efforts have in recent times upset these natural cycles of building block flow at rates that go well beyond the ability of the living systems around them to bounce back. The widespread clearing of forest land for farming use removes vital habitat areas and greatly cuts the ability of the land to pull harmful gases out of the air above. Dumping of waste from factories slowly breaks down water sources and drains the soil of the building blocks upon which entire networks of living things depend for their long term health.",
  },
  {
    label: 'Grade 12',
    category: 'High School' as const,
    color: 'bg-red-100 text-red-700 hover:bg-red-200 border-red-300',
    title: 'The Scientific Method',
    reason: 'Very long sentences of 30+ words. Sophisticated vocabulary (hypothetico-deductive, falsification, paradigmatic). Philosophy of science concepts requiring abstract meta-level reasoning about how knowledge is built.',
    text: "What we know about the natural world grows through a careful process of forming ideas about how things work and then testing those ideas against the hard facts gathered from planned study. Those who carry out this research work tend to begin by spotting patterns in what they observe and then building early working models to explain what they found. These proposed ways of thinking must then produce certain claims that can be checked through controlled test setups or through further rounds of planned study. Only those models that hold up after being tested again and again and that produce steady and trusted results across many different research programs gain broad support.\n\nThe rule that a valid claim about the natural world must be stated in terms that would allow contrary facts to show it is wrong serves as a key standard in this form of thinking. This basic standard draws a clear and useful line between reasoned study of the natural world and other ways of building knowledge that rest mainly upon personal feeling or long held custom. A working model of how things function gains standing not simply by gathering supporting facts in its favor but rather by holding up against sustained and purposeful efforts to prove it wrong. The most lasting models of how the world works have held up for decades of close review while staying in line with the full body of facts that have been gathered over time.\n\nThe path of progress in our grasp of the natural world rarely follows a straight line forward but instead tends to involve extended stretches of deep rethinking about the basic ideas that support an entire field of study. Well known working models may from time to time run into stubborn findings from the real world that simply refuse to fit within the currently held way of thinking about the matter. When enough of these problem cases build up a major shift in thinking may take place that reshapes the very basis of an entire field of research and opens new doors of understanding.",
  },
  {
    label: 'College',
    category: 'College' as const,
    color: 'bg-purple-100 text-purple-700 hover:bg-purple-200 border-purple-300',
    title: 'Knowledge and Epistemology',
    reason: 'Extremely long multi-clause sentences of 35+ words. Graduate-level vocabulary (epistemological, demarcation, paradigmatic). Highly abstract philosophical analysis about the nature and limits of human knowledge itself.',
    text: "Current thinking and debate about how we gain knowledge of the natural world through structured study calls for a careful review of the working methods that support research. The back and forth between what we observe in the real world and the abstract models we construct remains a deeply contested matter among scholars. Those who look into the complex ways in which knowledge is built up tend to focus on how careful study is checked and confirmed within the broader body of trained experts. This process of review and challenge forms the backbone of trusted knowledge across every major research discipline and field of study.\n\nCertain modern lines of critical thought have called into serious question the long held belief that truly fair and unbiased truth can be reached through any single method. These lines of thought tend to stress the deeply rooted and culturally shaped nature of all claims about how the world works. They pose a direct challenge to the view that our models can and do reflect things as they truly are apart from human perspective and cultural framing. The resulting tension between these competing outlooks has given rise to extensive scholarly discussion within broader academic circles.\n\nThe ongoing problem of drawing a clear line between sound research and forms of thinking that merely look like research but lack its rigor keeps producing lasting disputes. One major thinker put forward the idea that being able to prove a claim wrong is the key mark of real science in any field. This view has been challenged in important ways by later thinkers who point to the role of shared beliefs and group standards in shaping what counts as valid. Still other scholars argue that progress in knowledge does not follow a single straight path but instead moves through periods of dramatic change and upheaval.\n\nThese debates about the nature and limits of human knowledge carry profound weight for how we understand the path of progress in every field.",
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
    setIsLoading(true);

    try {
      let result;
      if (activeTab === 'pdf') {
        result = await textApi.extractPdf(file);
        setSuccess(`Extracted text from ${result.pageCount} pages`);
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
      navigate(`/analysis/${result.analysisId}`, { state: { analysis: result } });
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

  return (
    <div className="max-w-4xl mx-auto">
      {isLoading && <LoadingSpinner message="Analyzing text..." fullScreen />}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-800">New Analysis</h1>
        <p className="text-gray-600 mt-2">
          Enter or upload text to analyze its readability
        </p>
      </div>

      {/* Word Count Display */}
      <div className="bg-blue-50 border-2 border-blue-200 rounded-lg p-4 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-600">Current Word Count</p>
            <p className="text-3xl font-bold text-blue-600">{wordCount.toLocaleString()}</p>
          </div>
          <div className="text-sm text-gray-600">
            {wordCount === 0 && <span className="text-gray-400">Enter text to begin</span>}
            {wordCount > 0 && wordCount < 50 && <span className="text-red-600">Minimum 50 words required</span>}
            {wordCount >= 50 && wordCount <= 50000 && <span className="text-green-600">Valid length</span>}
            {wordCount > 50000 && <span className="text-red-600">Maximum 50,000 words</span>}
          </div>
        </div>
      </div>

      {/* Title Input */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Title (optional)
        </label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Give your analysis a title..."
          className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
        />
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="flex border-b">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-4 font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-primary-50 text-primary-700 border-b-2 border-primary-600'
                  : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              <tab.icon className="w-5 h-5" />
              <span className="hidden sm:inline">{tab.label}</span>
            </button>
          ))}
        </div>

        <div className="p-6">
          {/* Alerts */}
          {error && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg flex items-center gap-2 text-green-700">
              <CheckCircle className="w-5 h-5 flex-shrink-0" />
              <span>{success}</span>
            </div>
          )}

          {/* Text Input */}
          {activeTab === 'text' && (
            <div>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Paste or type your text here... (minimum 50 characters)"
                className="w-full h-64 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none resize-none"
              />
              <div className="flex justify-between mt-2 text-sm text-gray-500">
                <span>{wordCount} words</span>
                <span>{charCount} / 50,000 characters</span>
              </div>

              {/* Try a Sample */}
              <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
                <div className="flex items-center gap-2 mb-3">
                  <Sparkles className="w-4 h-4 text-primary-500" />
                  <span className="text-sm font-medium text-gray-700">Try a sample text</span>
                </div>
                <div className="space-y-2">
                  {SAMPLE_CATEGORIES.map((category) => (
                    <div key={category} className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider w-28 flex-shrink-0">{category}</span>
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
                          className={`px-3 py-1 text-xs font-medium rounded-full border transition-colors ${sample.color}`}
                        >
                          {sample.label}
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
                {selectedReason && (
                  <div className="mt-3 p-3 bg-blue-50 rounded-lg border border-blue-200">
                    <p className="text-xs font-semibold text-blue-800 mb-1">Why this grade level:</p>
                    <p className="text-xs text-blue-700">{selectedReason}</p>
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
                className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center cursor-pointer hover:border-primary-400 hover:bg-primary-50 transition-colors"
              >
                <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600 font-medium">
                  Click to upload or drag and drop
                </p>
                <p className="text-sm text-gray-500 mt-2">
                  {activeTab === 'pdf' && 'PDF files up to 10MB'}
                  {activeTab === 'doc' && 'DOC or DOCX files up to 10MB'}
                  {activeTab === 'image' && 'JPG, JPEG, or PNG files up to 5MB'}
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
                <div className="mt-6">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Extracted Text (edit if needed)
                  </label>
                  <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    className="w-full h-48 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none resize-none"
                  />
                  <div className="flex justify-between mt-2 text-sm text-gray-500">
                    <span>{wordCount} words</span>
                    <span>{charCount} characters</span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Voice Input */}
          {activeTab === 'voice' && (
            <div>
              <div className="text-center py-8">
                <button
                  onClick={isRecording ? stopRecording : startRecording}
                  className={`p-8 rounded-full transition-all ${
                    isRecording
                      ? 'bg-red-100 text-red-600 animate-pulse'
                      : 'bg-primary-100 text-primary-600 hover:bg-primary-200'
                  }`}
                >
                  {isRecording ? (
                    <MicOff className="w-12 h-12" />
                  ) : (
                    <Mic className="w-12 h-12" />
                  )}
                </button>
                <p className="mt-4 text-gray-600">
                  {isRecording
                    ? 'Recording... Click to stop'
                    : 'Click to start recording'}
                </p>
                {!('webkitSpeechRecognition' in window) &&
                  !('SpeechRecognition' in window) && (
                    <p className="mt-2 text-sm text-yellow-600">
                      Speech recognition may not be supported in this browser
                    </p>
                  )}
              </div>

              {text && (
                <div className="mt-6">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Transcribed Text (edit if needed)
                  </label>
                  <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    className="w-full h-48 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none resize-none"
                  />
                  <div className="flex justify-between mt-2 text-sm text-gray-500">
                    <span>{wordCount} words</span>
                    <span>{charCount} characters</span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Analyze Button */}
      <div className="mt-6">
        <button
          onClick={handleAnalyze}
          disabled={isLoading || text.trim().length < 50}
          className="w-full py-4 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 focus:ring-4 focus:ring-primary-200 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Analyzing...
            </>
          ) : (
            'Analyze Text'
          )}
        </button>
      </div>
    </div>
  );
};

export default TextInput;
