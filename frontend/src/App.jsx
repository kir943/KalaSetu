import React, { useState, useEffect } from 'react';

const CRAFTS = ['Blue Pottery', 'Paithani Weaving'];
const NO_SOURCE_FALLBACK = 'Mere paas iska source nahi hai.';

const SAMPLE_QUESTIONS = [
  {
    label: 'Answerable: Blue Pottery Quartz Ratio',
    craft: 'Blue Pottery',
    q: 'How many parts of powdered quartz stone, katira gum, and multani mitti are mixed in Blue Pottery?',
  },
  {
    label: 'Answerable: Paithani Kadiyal Shuttles',
    craft: 'Paithani Weaving',
    q: 'How many wooden shuttles (dhote) are used on the handloom for the Kadiyal interlocking border?',
  },
  {
    label: 'Unanswerable: Export Price & GST',
    craft: 'Blue Pottery',
    q: 'What is the wholesale export price and GST tax rate for Blue Pottery vases?',
  },
  {
    label: 'Unanswerable: Powerloom Wattage',
    craft: 'Paithani Weaving',
    q: 'How many watts of electricity does a high-speed automated powerloom consume for polyester sarees?',
  },
];

function App() {
  const [activeTab, setActiveTab] = useState('ask');
  const [health, setHealth] = useState({ status: 'checking' });
  const [entries, setEntries] = useState([]);

  // Learner Q&A State (Block 4)
  const [selectedCraft, setSelectedCraft] = useState('Blue Pottery');
  const [question, setQuestion] = useState('');
  const [asking, setAsking] = useState(false);
  const [qaError, setQaError] = useState('');
  const [qaResult, setQaResult] = useState(null);
  const [voiceQuestionLoading, setVoiceQuestionLoading] = useState(false);

  // Bulbul Text-to-Speech State (Block 5)
  const [ttsLang, setTtsLang] = useState('hi-IN');
  const [ttsLoading, setTtsLoading] = useState(false);
  const [ttsAudioSrc, setTtsAudioSrc] = useState('');
  const [ttsError, setTtsError] = useState('');

  // 10-Question Grounding Benchmark State
  const [benchmark, setBenchmark] = useState(null);
  const [runningBenchmark, setRunningBenchmark] = useState(false);

  // Artisan Contribution State (Block 3)
  const [audioFile, setAudioFile] = useState(null);
  const [languageCode, setLanguageCode] = useState('hi-IN');
  const [transcribing, setTranscribing] = useState(false);
  const [transcribeError, setTranscribeError] = useState('');

  const [craft, setCraft] = useState(CRAFTS[0]);
  const [technique, setTechnique] = useState('');
  const [artisanName, setArtisanName] = useState('');
  const [transcript, setTranscript] = useState('');
  const [stepsText, setStepsText] = useState('');
  const [materialsText, setMaterialsText] = useState('');
  const [sourceAudio, setSourceAudio] = useState('');
  const [segment, setSegment] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState({ type: '', text: '' });

  const fetchEntries = () => {
    fetch('/api/entries')
      .then((res) => res.json())
      .then((data) => {
        if (data && Array.isArray(data.entries)) {
          setEntries(data.entries);
        }
      })
      .catch(() => {});
  };

  const fetchBenchmark = () => {
    setRunningBenchmark(true);
    fetch('/api/grounding-test')
      .then((res) => res.json())
      .then((data) => setBenchmark(data))
      .catch(() => {})
      .finally(() => setRunningBenchmark(false));
  };

  useEffect(() => {
    fetch('/api/health')
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => setHealth({ status: 'ok', data }))
      .catch((err) => setHealth({ status: 'error', error: err.message }));

    fetchEntries();
    fetchBenchmark();
  }, []);

  const handleAskQuestion = async (e) => {
    if (e) e.preventDefault();
    setQaError('');
    setQaResult(null);
    setTtsAudioSrc('');
    setTtsError('');

    if (!question.trim()) {
      setQaError('Please enter a question to ask the archive.');
      return;
    }

    setAsking(true);
    try {
      const res = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: question.trim(),
          craft: selectedCraft || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `Failed to get answer (HTTP ${res.status})`);
      }
      setQaResult(data);
      if (data.sources && data.sources.length > 0 && data.sources[0].language) {
        setTtsLang(data.sources[0].language);
      }
    } catch (err) {
      setQaError(`Technical API Error: ${err.message}`);
    } finally {
      setAsking(false);
    }
  };

  const handleListenAnswer = async () => {
    if (!qaResult || !qaResult.grounded || qaResult.answer === NO_SOURCE_FALLBACK) {
      return;
    }

    setTtsError('');
    setTtsAudioSrc('');
    setTtsLoading(true);

    try {
      const res = await fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: qaResult.answer,
          target_language_code: ttsLang,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `Speech generation failed (HTTP ${res.status})`);
      }
      const mime = data.mime_type || 'audio/wav';
      setTtsAudioSrc(`data:${mime};base64,${data.audio_base64}`);
    } catch (err) {
      setTtsError(`Audio playback unavailable (${err.message}). Showing text-only grounded answer above.`);
    } finally {
      setTtsLoading(false);
    }
  };

  const handleVoiceQuestionUpload = async (e) => {
    const file = e.target.files && e.target.files[0] ? e.target.files[0] : null;
    if (!file) return;

    setQaError('');
    setVoiceQuestionLoading(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('language_code', 'hi-IN');

    try {
      const res = await fetch('/api/transcribe', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `Voice question transcription failed (HTTP ${res.status})`);
      }
      setQuestion(data.transcript || '');
    } catch (err) {
      setQaError(`Voice Input Error: ${err.message}`);
    } finally {
      setVoiceQuestionLoading(false);
    }
  };

  const handleTranscribe = async (e) => {
    e.preventDefault();
    setTranscribeError('');
    setSaveMessage({ type: '', text: '' });

    if (!audioFile) {
      setTranscribeError('Please select an audio file (.wav, .mp3, .ogg, .m4a, .webm) first.');
      return;
    }

    const formData = new FormData();
    formData.append('file', audioFile);
    formData.append('language_code', languageCode);

    setTranscribing(true);
    try {
      const res = await fetch('/api/transcribe', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `Transcription failed (HTTP ${res.status})`);
      }
      setTranscript(data.transcript || '');
      setSourceAudio(data.source_audio || audioFile.name);
      setSegment(data.segment || 'Chunk 1 (Full uploaded audio clip)');
      if (data.language_code) {
        setLanguageCode(data.language_code);
      }
    } catch (err) {
      setTranscribeError(err.message);
    } finally {
      setTranscribing(false);
    }
  };

  const handleSaveEntry = async (e) => {
    e.preventDefault();
    setSaveMessage({ type: '', text: '' });

    if (!technique.trim() || !artisanName.trim() || !transcript.trim() || !sourceAudio.trim() || !segment.trim()) {
      setSaveMessage({
        type: 'error',
        text: 'Please fill in Artisan Name, Technique, Transcript, Source Audio, and Segment before saving.',
      });
      return;
    }

    setSaving(true);
    try {
      const payload = {
        craft,
        technique: technique.trim(),
        artisan_name: artisanName.trim(),
        language: languageCode,
        transcript: transcript.trim(),
        steps: stepsText,
        materials: materialsText,
        source_audio: sourceAudio.trim(),
        segment: segment.trim(),
        is_demo: false,
      };

      const res = await fetch('/api/entries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `Failed to save entry (HTTP ${res.status})`);
      }

      setSaveMessage({
        type: 'success',
        text: `Saved contribution to archive! Citation: ${data.citation}`,
      });
      setTechnique('');
      setStepsText('');
      setMaterialsText('');
      fetchEntries();
    } catch (err) {
      setSaveMessage({ type: 'error', text: err.message });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="container">
      <header>
        <div>
          <h1>KalaSetu — Every answer has a source</h1>
          <p className="tagline">
            “KalaSetu sirf wahi bolta hai jo kisi artisan ne record kiya hai, aur har jawab ke saath source dikhata hai.”
          </p>
        </div>
        <div>
          {health.status === 'checking' && <span className="status-badge checking">Checking API...</span>}
          {health.status === 'ok' && <span className="status-badge ok">Backend Connected</span>}
          {health.status === 'error' && <span className="status-badge error">API Offline: {health.error}</span>}
        </div>
      </header>

      <div className="tabs">
        <button
          type="button"
          className={`tab-btn ${activeTab === 'ask' ? 'active' : ''}`}
          onClick={() => setActiveTab('ask')}
        >
          Ask the Archive (Learner Q&amp;A)
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'record' ? 'active' : ''}`}
          onClick={() => setActiveTab('record')}
        >
          Record Artisan Knowledge
        </button>
      </div>

      <main>
        {activeTab === 'ask' && (
          <>
            <section className="card">
              <h2>Ask the Artisan Archive (Grounded in Recorded Sources)</h2>
              <p style={{ marginBottom: '0.75rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                Select a craft and ask a question. Answers are generated strictly from archived artisan testimony with citations.
                If the archive has no source, KalaSetu responds: <strong>“Mere paas iska source nahi hai.”</strong>
              </p>

              <div className="chip-row">
                {SAMPLE_QUESTIONS.map((sq, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="chip"
                    onClick={() => {
                      setSelectedCraft(sq.craft);
                      setQuestion(sq.q);
                    }}
                  >
                    {sq.label}
                  </button>
                ))}
              </div>

              {qaError && <div className="alert error">{qaError}</div>}

              <form onSubmit={handleAskQuestion}>
                <div className="form-grid">
                  <div className="form-group">
                    <label htmlFor="learner-craft-select">Craft Filter</label>
                    <select
                      id="learner-craft-select"
                      value={selectedCraft}
                      onChange={(e) => setSelectedCraft(e.target.value)}
                    >
                      <option value="">All Crafts</option>
                      {CRAFTS.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group">
                    <label htmlFor="voice-question-upload">
                      Or Upload Voice Question (Saaras STT)
                    </label>
                    <input
                      id="voice-question-upload"
                      type="file"
                      accept=".wav,.mp3,.ogg,.m4a,.flac,.aac,.webm,audio/*"
                      onChange={handleVoiceQuestionUpload}
                      disabled={voiceQuestionLoading}
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label htmlFor="learner-question-input">Learner Question *</label>
                  <input
                    id="learner-question-input"
                    type="text"
                    placeholder="Ask about materials, steps, or techniques recorded by artisans..."
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    required
                  />
                </div>

                <button type="submit" className="btn" disabled={asking || voiceQuestionLoading}>
                  {asking ? 'Searching Archive & Generating Grounded Answer...' : 'Ask the Archive'}
                </button>
              </form>

              {qaResult && (
                <div className="answer-box">
                  <div className="entry-header">
                    <strong>Archive Response</strong>
                    <span className={`badge ${qaResult.grounded ? 'live' : 'demo'}`}>
                      {qaResult.grounded ? 'GROUNDED IN ARCHIVE' : 'NO ARCHIVE SOURCE'}
                    </span>
                  </div>

                  <div className="answer-text">{qaResult.answer}</div>

                  {qaResult.citations && qaResult.citations.length > 0 && (
                    <div className="citation-box">
                      Verified Citation(s): {qaResult.citations.join(' | ')}
                    </div>
                  )}

                  {qaResult.grounded && qaResult.answer !== NO_SOURCE_FALLBACK && (
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.75rem',
                        flexWrap: 'wrap',
                        marginTop: '0.75rem',
                      }}
                    >
                      <select
                        aria-label="Spoken Answer Language"
                        value={ttsLang}
                        onChange={(e) => setTtsLang(e.target.value)}
                        style={{ padding: '0.45rem', borderRadius: '6px', border: '1px solid var(--border)' }}
                      >
                        <option value="hi-IN">Hindi Voice (hi-IN)</option>
                        <option value="mr-IN">Marathi Voice (mr-IN)</option>
                        <option value="en-IN">English Voice (en-IN)</option>
                      </select>

                      <button
                        type="button"
                        className="btn"
                        onClick={handleListenAnswer}
                        disabled={ttsLoading}
                      >
                        {ttsLoading ? 'Generating Audio (Bulbul)...' : 'Listen (Speak Answer)'}
                      </button>

                      {ttsAudioSrc && (
                        <audio controls autoPlay src={ttsAudioSrc} style={{ height: '38px' }}>
                          Your browser does not support audio playback.
                        </audio>
                      )}
                    </div>
                  )}

                  {ttsError && (
                    <div className="alert error" style={{ marginTop: '0.75rem' }}>
                      {ttsError}
                    </div>
                  )}

                  {qaResult.sources && qaResult.sources.length > 0 && (
                    <div style={{ marginTop: '0.85rem' }}>
                      <strong style={{ fontSize: '0.88rem' }}>
                        Inspect Retrieved Source Evidence ({qaResult.sources.length}):
                      </strong>
                      {qaResult.sources.map((src) => (
                        <div key={src.id} className="source-evidence-card">
                          <div>
                            <strong>{src.artisan_name}</strong> — <em>{src.technique}</em> ({src.craft})
                          </div>
                          <div>
                            <strong>Audio:</strong> {src.source_audio} | <strong>Segment:</strong> {src.segment}
                          </div>
                          <div style={{ marginTop: '0.35rem' }}>
                            <strong>Original Transcript:</strong> “{src.transcript}”
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </section>

            <section className="card">
              <div className="entry-header">
                <h2>10-Question Grounding Verification Suite</h2>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={fetchBenchmark}
                  disabled={runningBenchmark}
                >
                  {runningBenchmark ? 'Running...' : 'Re-run 10-Question Suite'}
                </button>
              </div>

              {benchmark && (
                <>
                  <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                    <strong>What counts as a pass:</strong> {benchmark.pass_criteria}
                  </p>
                  <div className="status-badge ok" style={{ marginBottom: '0.5rem' }}>
                    Measured Pass Rate: {benchmark.pass_rate}
                  </div>

                  <table className="test-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Craft</th>
                        <th>Question</th>
                        <th>Expected</th>
                        <th>Citation / Fallback Output</th>
                        <th>Result</th>
                      </tr>
                    </thead>
                    <tbody>
                      {benchmark.results.map((r) => (
                        <tr key={r.id}>
                          <td>{r.id}</td>
                          <td>{r.craft}</td>
                          <td>{r.question}</td>
                          <td>{r.expected_answerable ? 'Answerable' : 'Unanswerable'}</td>
                          <td>{r.grounded ? r.citations.join('; ') : r.answer}</td>
                          <td>
                            <span className={`badge ${r.passed ? 'live' : 'error'}`}>
                              {r.passed ? 'PASS' : 'FAIL'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </section>
          </>
        )}

        {activeTab === 'record' && (
          <>
            <section className="card">
              <h2>Record / Upload Artisan Knowledge (Sarvam Saaras STT)</h2>
              <p style={{ marginBottom: '1rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                Step 1: Upload an artisan voice recording in Hindi or Marathi to transcribe via Sarvam Saaras (`saaras:v3`).
              </p>

              {transcribeError && <div className="alert error">{transcribeError}</div>}

              <form onSubmit={handleTranscribe}>
                <div className="form-grid">
                  <div className="form-group">
                    <label htmlFor="audio-upload">Audio Clip (.wav, .mp3, .m4a, .ogg, .webm)</label>
                    <input
                      id="audio-upload"
                      type="file"
                      accept=".wav,.mp3,.ogg,.m4a,.flac,.aac,.webm,audio/*"
                      onChange={(e) => {
                        const f = e.target.files && e.target.files[0] ? e.target.files[0] : null;
                        setAudioFile(f);
                        if (f) {
                          setSourceAudio(f.name);
                          if (!segment) {
                            setSegment('Chunk 1 (Uploaded clip pending transcription)');
                          }
                        }
                      }}
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="lang-select">Spoken Language</label>
                    <select
                      id="lang-select"
                      value={languageCode}
                      onChange={(e) => setLanguageCode(e.target.value)}
                    >
                      <option value="hi-IN">Hindi (hi-IN)</option>
                      <option value="mr-IN">Marathi (mr-IN)</option>
                      <option value="en-IN">English / Mixed (en-IN)</option>
                    </select>
                  </div>
                </div>

                <button type="submit" className="btn" disabled={transcribing}>
                  {transcribing ? 'Transcribing with Sarvam Saaras...' : '1. Transcribe Audio with Saaras'}
                </button>
              </form>
            </section>

            <section className="card">
              <h2>Review &amp; Save Artisan Contribution</h2>
              <p style={{ marginBottom: '1rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                Step 2: Review or edit the transcript and metadata before saving to the permanent JSON archive.
              </p>

              {saveMessage.text && <div className={`alert ${saveMessage.type}`}>{saveMessage.text}</div>}

              <form onSubmit={handleSaveEntry}>
                <div className="form-grid">
                  <div className="form-group">
                    <label htmlFor="craft-select">Craft</label>
                    <select id="craft-select" value={craft} onChange={(e) => setCraft(e.target.value)}>
                      {CRAFTS.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group">
                    <label htmlFor="artisan-name">Artisan Name *</label>
                    <input
                      id="artisan-name"
                      type="text"
                      placeholder="e.g. Mohanlal Kumhar"
                      value={artisanName}
                      onChange={(e) => setArtisanName(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label htmlFor="technique-input">Technique Title *</label>
                  <input
                    id="technique-input"
                    type="text"
                    placeholder="e.g. Multani Mitti and Quartz Slip Glazing"
                    value={technique}
                    onChange={(e) => setTechnique(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="transcript-input">Reviewed Transcript (Hindi / Marathi / Hinglish) *</label>
                  <textarea
                    id="transcript-input"
                    placeholder="Transcribed text from Sarvam Saaras will appear here for review and editing..."
                    value={transcript}
                    onChange={(e) => setTranscript(e.target.value)}
                    required
                  />
                </div>

                <div className="form-grid">
                  <div className="form-group">
                    <label htmlFor="materials-input">Materials (comma or newline separated)</label>
                    <textarea
                      id="materials-input"
                      placeholder="e.g. Quartz powder, Katira gum, Cobalt oxide"
                      value={materialsText}
                      onChange={(e) => setMaterialsText(e.target.value)}
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="steps-input">Key Steps (newline separated)</label>
                    <textarea
                      id="steps-input"
                      placeholder="Step 1: Mix quartz and katira gum..."
                      value={stepsText}
                      onChange={(e) => setStepsText(e.target.value)}
                    />
                  </div>
                </div>

                <div className="form-grid">
                  <div className="form-group">
                    <label htmlFor="source-audio-input">Source Audio Filename *</label>
                    <input
                      id="source-audio-input"
                      type="text"
                      placeholder="e.g. artisan_clip.wav"
                      value={sourceAudio}
                      onChange={(e) => setSourceAudio(e.target.value)}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="segment-input">Source Segment / Chunk Metadata *</label>
                    <input
                      id="segment-input"
                      type="text"
                      placeholder="e.g. Chunk 1 (Full uploaded audio clip)"
                      value={segment}
                      onChange={(e) => setSegment(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <button type="submit" className="btn" disabled={saving}>
                  {saving ? 'Saving Entry...' : '2. Save Reviewed Entry to Archive'}
                </button>
              </form>
            </section>
          </>
        )}

        <section className="card">
          <h2>Archived Artisan Contributions ({entries.length})</h2>
          {entries.map((entry) => (
            <div key={entry.id} className="entry-item">
              <div className="entry-header">
                <strong>
                  {entry.craft} — {entry.technique}
                </strong>
                <span className={`badge ${entry.is_demo ? 'demo' : 'live'}`}>
                  {entry.is_demo ? 'DEMO DATA' : 'ARTISAN CONTRIBUTION'}
                </span>
              </div>
              <p style={{ fontSize: '0.9rem' }}>{entry.transcript}</p>
              <div className="citation-box">Source Citation: {entry.citation}</div>
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}

export default App;
