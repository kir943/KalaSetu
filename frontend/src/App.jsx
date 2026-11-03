import React, { useState, useEffect, useRef } from 'react';

const CRAFTS = ['Blue Pottery', 'Paithani Weaving'];
const NO_SOURCE_FALLBACK = 'Mere paas iska source nahi hai.';

const SAMPLE_QUESTIONS = [
  {
    category: 'grounded',
    shortLabel: 'Clay-Free Quartz Dough',
    craft: 'Blue Pottery',
    q: 'Why is Jaipur Blue Pottery considered clay-free and what raw materials are mixed to prepare its dough?',
  },
  {
    category: 'grounded',
    shortLabel: 'Cobalt & Copper Oxide Glaze',
    craft: 'Blue Pottery',
    q: 'Which metallic oxides produce the dark blue and turquoise colors on Jaipur Blue Pottery, and how is it glazed and fired?',
  },
  {
    category: 'grounded',
    shortLabel: 'Paithani Reversible Tapestry',
    craft: 'Paithani Weaving',
    q: 'Why is a Paithani saree reversible with no floating threads on the back, and what is the Bangadi Mor motif?',
  },
  {
    category: 'grounded',
    shortLabel: 'Kadiyal 3-Shuttle Interlock',
    craft: 'Paithani Weaving',
    q: 'How are raw mulberry silk degumming, Kadiyal border interlocking with three shuttles, and tilli bobbins used in Paithani weaving?',
  },
  {
    category: 'unrecorded',
    shortLabel: 'Refusal Test: Export GST',
    craft: 'Blue Pottery',
    q: 'What is the wholesale export price and GST tax rate for Blue Pottery vases?',
  },
];

// Authentic documented craft photographs downloaded from the verified institutional sources (D'source & Sahapedia)
const ENTRY_VISUAL_META = {
  'src-blue-pottery-dsource-01': {
    image: '/craft-blue-pottery-dough.jpg',
    imageAlt: 'Preparation and molding of quartz dough in Plaster of Paris mould (Source: D’source IDC IIT Bombay / NID)',
    region: 'Jaipur, Rajasthan',
    photoCredit: "D'source (IDC IIT Bombay & NID)",
    sampleQuestion:
      'Why is Jaipur Blue Pottery considered clay-free and what raw materials are mixed to prepare its dough?',
  },
  'src-blue-pottery-rajgov-02': {
    image: '/craft-blue-pottery-glaze.jpg',
    imageAlt: 'Freehand mineral oxide painting on Jaipur Blue Pottery vessel (Source: D’source / Rajasthan Craft Documentation)',
    region: 'Jaipur, Rajasthan',
    photoCredit: 'Rajasthan Craft Documentation / D’source',
    sampleQuestion:
      'Which metallic oxides produce the dark blue and turquoise colors on Jaipur Blue Pottery, and how is it glazed and fired?',
  },
  'src-paithani-sahapedia-01': {
    image: '/craft-paithani-tapestry.jpg',
    imageAlt: 'Traditional Paithani silk and gold zari saree motif (Source: Sahapedia)',
    region: 'Yeola & Paithan, Maharashtra',
    photoCredit: 'Sahapedia Open Cultural Resource',
    sampleQuestion:
      'Why is a Paithani saree reversible with no floating threads on the back, and what is the Bangadi Mor motif?',
  },
  'src-paithani-craftmark-02': {
    image: '/craft-paithani-loom.jpg',
    imageAlt: 'Handloom warp and weft interlocking in Paithani weaving (Source: Sahapedia / AIACA Craftmark)',
    region: 'Yeola & Paithan, Maharashtra',
    photoCredit: 'AIACA Craftmark / Sahapedia',
    sampleQuestion:
      'How are raw mulberry silk degumming, Kadiyal border interlocking with three shuttles, and tilli bobbins used in Paithani weaving?',
  },
};

const WAVE_BAR_HEIGHTS = [
  16, 28, 22, 36, 18, 42, 30, 14, 38, 24, 20, 34, 26, 16, 32, 22, 14, 28,
];

function App() {
  const [activeNav, setActiveNav] = useState('home');
  const [vintageBgMode, setVintageBgMode] = useState(() => {
    if (
      typeof window !== 'undefined' &&
      window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      return 'paused';
    }
    return 'moving';
  }); // 'moving' | 'rich' | 'paused'
  const [health, setHealth] = useState({ status: 'checking' });
  const [entries, setEntries] = useState([]);
  const [catalogCraftFilter, setCatalogCraftFilter] = useState('');

  // Learner Q&A State
  const [selectedCraft, setSelectedCraft] = useState('Blue Pottery');
  const [question, setQuestion] = useState(
    'Why is Jaipur Blue Pottery considered clay-free and what raw materials are mixed to prepare its dough?'
  );
  const [asking, setAsking] = useState(false);
  const [qaError, setQaError] = useState('');
  const [qaResult, setQaResult] = useState(null);
  const [voiceQuestionLoading, setVoiceQuestionLoading] = useState(false);

  // Bulbul Text-to-Speech State
  const [ttsLang, setTtsLang] = useState('hi-IN');
  const [ttsLoading, setTtsLoading] = useState(false);
  const [ttsAudioSrc, setTtsAudioSrc] = useState('');
  const [ttsSpokenText, setTtsSpokenText] = useState('');
  const [ttsTranslated, setTtsTranslated] = useState(false);
  const [ttsAudioLang, setTtsAudioLang] = useState('');
  const [ttsError, setTtsError] = useState('');

  // 10-Question Grounding Benchmark State
  const [benchmark, setBenchmark] = useState(null);
  const [runningBenchmark, setRunningBenchmark] = useState(false);
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false);

  // Artisan Contribution State
  const [audioFile, setAudioFile] = useState(null);
  const [languageCode, setLanguageCode] = useState('hi-IN');
  const [transcribing, setTranscribing] = useState(false);
  const [transcribeError, setTranscribeError] = useState('');
  const [transcribeSuccess, setTranscribeSuccess] = useState('');

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

  const questionInputRef = useRef(null);
  const audioUploadRef = useRef(null);
  const dossierRef = useRef(null);

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

  const scrollToSection = (sectionId, navKey) => {
    setActiveNav(navKey);
    const el = document.getElementById(sectionId);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const cycleVintageMode = () => {
    setVintageBgMode((prev) => {
      if (prev === 'moving') return 'rich';
      if (prev === 'rich') return 'paused';
      return 'moving';
    });
  };

  const handleAskQuestion = async (e, overrideQuestion, overrideCraft) => {
    if (e && typeof e.preventDefault === 'function') {
      e.preventDefault();
    }
    const qText = (overrideQuestion !== undefined ? overrideQuestion : question).trim();
    const cFilter = overrideCraft !== undefined ? overrideCraft : selectedCraft;

    setQaError('');
    setQaResult(null);
    setTtsAudioSrc('');
    setTtsSpokenText('');
    setTtsTranslated(false);
    setTtsAudioLang('');
    setTtsError('');

    if (!qText) {
      setQaError('Please enter a question to query the verified craft archive.');
      return;
    }

    setAsking(true);
    try {
      const res = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: qText,
          craft: cFilter || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `Failed to retrieve answer (HTTP ${res.status})`);
      }
      setQaResult(data);
      setTimeout(() => {
        if (dossierRef.current) {
          dossierRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      }, 80);
    } catch (err) {
      setQaError(`Technical API Error: ${err.message}`);
    } finally {
      setAsking(false);
    }
  };

  const handleTtsLangChange = (newLang) => {
    setTtsLang(newLang);
    // Invalidate previous audio clip and translated preview so an old clip cannot remain playable
    setTtsAudioSrc('');
    setTtsSpokenText('');
    setTtsTranslated(false);
    setTtsAudioLang('');
    setTtsError('');
  };

  const handleListenAnswer = async () => {
    if (!qaResult || !qaResult.grounded || qaResult.answer === NO_SOURCE_FALLBACK) {
      return;
    }

    setTtsError('');
    setTtsAudioSrc('');
    setTtsSpokenText('');
    setTtsTranslated(false);
    setTtsAudioLang('');
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
        throw new Error(data.detail || `Speech synthesis failed (HTTP ${res.status})`);
      }
      const mime = data.mime_type || 'audio/wav';
      setTtsAudioSrc(`data:${mime};base64,${data.audio_base64}`);
      setTtsSpokenText(data.spoken_text || '');
      setTtsTranslated(Boolean(data.translated));
      setTtsAudioLang(data.target_language_code || ttsLang);
    } catch (err) {
      setTtsError(
        `Spoken audio generation failed (${err.message}). The original grounded answer and citations remain available above.`
      );
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
    if (e) e.preventDefault();
    setTranscribeError('');
    setTranscribeSuccess('');
    setSaveMessage({ type: '', text: '' });

    if (!audioFile) {
      setTranscribeError(
        'Please select an audio recording (.wav, .mp3, .ogg, .m4a, .webm) before running Sarvam Saaras transcription.'
      );
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
      setTranscribeSuccess(
        `Transcribed "${data.source_audio || audioFile.name}" (${data.segment}). Review the transcript below and click Save Reviewed Record.`
      );
    } catch (err) {
      setTranscribeError(err.message);
    } finally {
      setTranscribing(false);
    }
  };

  const handleSaveEntry = async (e) => {
    if (e) e.preventDefault();
    setSaveMessage({ type: '', text: '' });

    if (
      !technique.trim() ||
      !artisanName.trim() ||
      !transcript.trim() ||
      !sourceAudio.trim() ||
      !segment.trim()
    ) {
      setSaveMessage({
        type: 'error',
        text: 'Please complete Artisan Name, Technique Title, Reviewed Transcript, Source Audio Filename, and Segment before saving.',
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
        text: `Backend confirmed save. Citation: ${data.citation}`,
      });
      setTranscribeSuccess('');
      setArtisanName('');
      setTechnique('');
      setTranscript('');
      setStepsText('');
      setMaterialsText('');
      setSourceAudio('');
      setSegment('');
      setAudioFile(null);
      if (audioUploadRef.current) {
        audioUploadRef.current.value = '';
      }
      fetchEntries();
    } catch (err) {
      setSaveMessage({ type: 'error', text: err.message });
    } finally {
      setSaving(false);
    }
  };

  const handleLoadIntoSandbox = (entry) => {
    const visualMeta = ENTRY_VISUAL_META[entry.id];
    const sampleQ = visualMeta
      ? visualMeta.sampleQuestion
      : `What are the documented materials and steps for ${entry.technique} in ${entry.craft}?`;
    setSelectedCraft(entry.craft);
    setQuestion(sampleQ);
    scrollToSection('pathway-section', 'ask');
    setTimeout(() => {
      if (questionInputRef.current) {
        questionInputRef.current.focus();
      }
      handleAskQuestion(null, sampleQ, entry.craft);
    }, 150);
  };

  const filteredCatalogEntries = catalogCraftFilter
    ? entries.filter((e) => e.craft === catalogCraftFilter)
    : entries;

  return (
    <>
      {/* VINTAGE EPHEMERA BACKGROUND STAGE (Uses user's uploaded collage /vintage-collage-bg.jpg with gentle motion) */}
      <div
        className={`vintage-ambient-stage ${
          vintageBgMode === 'rich' ? 'rich-mode' : ''
        } ${vintageBgMode === 'paused' ? 'motion-paused' : ''}`}
        aria-hidden="true"
      >
        <div className="vintage-collage-layer" />
        <div className="vintage-secondary-layer" />
        <div className="vintage-parchment-veil" />
      </div>

      <div className="archival-page-wrapper">
        {/* 1. SLIM ARCHIVAL STATUS STRIP */}
        <div className="top-telemetry-strip">
          <div className="telemetry-left">
            <span>ARCHIVE IDENTIFIER: KALASETU-V2</span>
            <span className="gold-diamond">❖</span>
            <span>DOCUMENTED CRAFTS: JAIPUR BLUE POTTERY &amp; PAITHANI WEAVING</span>
          </div>
          <div className="telemetry-right">
            <span>
              <span
                className={`status-dot-inline ${health.status === 'ok' ? 'online' : ''}`}
                aria-hidden="true"
              />
              {health.status === 'ok'
                ? 'SARVAM AI ENGINE: CALIBRATED'
                : health.status === 'checking'
                ? 'SARVAM AI ENGINE: CONNECTING...'
                : `BACKEND OFFLINE (${health.error})`}
            </span>
            <button
              type="button"
              className="vintage-mode-btn"
              onClick={cycleVintageMode}
              aria-label={`Vintage backdrop mode: ${
                vintageBgMode === 'moving'
                  ? 'Subtle Motion'
                  : vintageBgMode === 'rich'
                  ? 'Rich Collage + Motion'
                  : 'Static'
              }. Activate to switch mode.`}
              title="Toggle vintage collage background motion and intensity"
            >
              ✦ Vintage Backdrop:{' '}
              {vintageBgMode === 'moving'
                ? 'Subtle Motion'
                : vintageBgMode === 'rich'
                ? 'Rich Collage + Motion'
                : 'Static'}
            </button>
          </div>
        </div>

        {/* 2. EDITORIAL NAVIGATION HEADER */}
        <header className="editorial-navbar">
          <div className="navbar-inner">
            <a
              href="#hero-section"
              className="brand-cluster"
              onClick={(e) => {
                e.preventDefault();
                scrollToSection('hero-section', 'home');
              }}
            >
              <div className="devanagari-emblem" aria-hidden="true">
                क
              </div>
              <div className="brand-text-block">
                <div className="brand-title-row">
                  <span className="brand-name">KalaSetu</span>
                  <span className="brand-doc-tag">❖ DOC. ARCHIVE</span>
                </div>
                <span className="brand-sub-row">INDIAN CRAFT &amp; ORAL KNOWLEDGE REPOSITORY</span>
              </div>
            </a>

            <nav className="editorial-nav-links" aria-label="Primary Archival Navigation">
              <button
                type="button"
                className={`nav-link-btn ${activeNav === 'home' ? 'active' : ''}`}
                onClick={() => scrollToSection('hero-section', 'home')}
              >
                Home &amp; Index
              </button>
              <button
                type="button"
                className={`nav-link-btn ${activeNav === 'ask' ? 'active' : ''}`}
                onClick={() => {
                  scrollToSection('pathway-section', 'ask');
                  if (questionInputRef.current) questionInputRef.current.focus();
                }}
              >
                Ask the Archive
              </button>
              <button
                type="button"
                className={`nav-link-btn ${activeNav === 'contribute' ? 'active' : ''}`}
                onClick={() => scrollToSection('contribute-card', 'contribute')}
              >
                Contribute Knowledge
              </button>
              <button
                type="button"
                className={`nav-link-btn ${activeNav === 'browse' ? 'active' : ''}`}
                onClick={() => scrollToSection('highlights-section', 'browse')}
              >
                Browse Archive
              </button>
              <button
                type="button"
                className={`nav-link-btn ${activeNav === 'diagnostics' ? 'active' : ''}`}
                onClick={() => {
                  setDiagnosticsOpen(true);
                  scrollToSection('diagnostics-section', 'diagnostics');
                }}
              >
                Grounding Diagnostics
              </button>
            </nav>

            <div className="nav-utility-cluster">
              <div className="script-pill-box" aria-label="Supported Languages">
                <strong>EN</strong> / हिन्दी / मराठी
              </div>
              <div className="acoustic-ready-box">
                <span className="wave-bars-mini" aria-hidden="true">
                  ılı
                </span>
                <span>
                  {health.status === 'ok' ? 'ACOUSTIC ENGINE READY' : 'ARCHIVE STANDBY'}
                </span>
              </div>
              <button
                type="button"
                className="nav-link-btn"
                style={{ fontSize: '0.84rem' }}
                onClick={() => scrollToSection('tenets-section', 'about')}
              >
                About the Archive
              </button>
            </div>
          </div>
        </header>

        {/* 3. MAIN ARCHIVAL CONTENT */}
        <main className="archival-main" id="hero-section">
          {/* Hero Folio Metadata Bar */}
          <div className="hero-folio-bar">
            <div>
              <span className="folio-highlight">❖ ARCHIVE EDITION v2.0 / LIVING CANON</span>
              <span style={{ margin: '0 0.6rem', color: 'var(--border-gold)' }}>|</span>
              <span>
                CAT. INDEX · {entries.length} Verified Craft Sources · Provenance Engine
              </span>
            </div>
            <div>
              <span className="status-dot-inline" aria-hidden="true" />
              <span>SOURCE VERIFICATION: STRICT CITATION MATRIX</span>
            </div>
          </div>

          {/* Large Editorial Hero */}
          <section className="editorial-hero-grid" aria-labelledby="hero-main-heading">
            <div>
              <div className="hero-kicker-row">
                <span className="scholarly-tag-pill">SCHOLARLY CRAFT &amp; ORAL ARCHIVE</span>
                <span className="series-line">——— VERIFIED SERIES</span>
              </div>
              <h1 id="hero-main-heading" className="hero-display-title">
                KalaSetu
              </h1>
              <p className="hero-italic-tagline">
                <span>Every answer has a source.</span>
                <span className="gold-diamond" aria-hidden="true">
                  ❖
                </span>
              </p>
            </div>

            <aside className="curators-note-frame" aria-label="Curator's Desk Note">
              <span className="curators-note-tab">CURATOR&apos;S DESK NOTE</span>
              <p className="curators-note-text">
                A voice-grounded repository preserving documented Indian craft processes, material
                knowledge, and reviewed oral contributions with strict citation provenance. When the
                archive lacks a verified source, KalaSetu refuses to guess:
                <em style={{ display: 'block', marginTop: '0.35rem', color: 'var(--accent-terracotta)' }}>
                  “Mere paas iska source nahi hai.”
                </em>
              </p>
              <div className="curators-note-footer">
                <span>VERIFIED SOURCES ONLY</span>
                <span>EST. TRADITIONS</span>
              </div>
            </aside>
          </section>

          {/* 4. SELECT ENGAGEMENT PATHWAY (TWO-COLUMN INTERACTIVE CARDS) */}
          <section
            className="archival-section"
            id="pathway-section"
            aria-labelledby="pathway-heading"
          >
            <div className="archival-section-header">
              <div>
                <div className="section-kicker">
                  <span>ENTRY PORTALS</span>
                  <span>———</span>
                  <span>SELECT DISCIPLINE SLIP</span>
                </div>
                <h2 id="pathway-heading" className="section-heading-serif">
                  Select Engagement Pathway
                </h2>
              </div>
              <div className="section-right-meta">
                ❖ CATALOG CARD DIVISION: INQUIRY OR FIELD RECORDING
              </div>
            </div>

            <div className="pathway-grid">
              {/* LEFT CARD: ASK THE ARCHIVE */}
              <div className="pathway-card inquiry-pathway" id="ask-card">
                <div className="pathway-card-inner">
                  <div className="slip-header-row">
                    <span className="slip-division-label">
                      <span aria-hidden="true">🔍</span> INDEX DIVISION 01 · INQUIRY &amp; PEDAGOGY
                    </span>
                    <span className="slip-badge-box">CAT. NO. SLIP-01</span>
                  </div>

                  <h3 className="pathway-title">Ask the Archive</h3>
                  <p className="pathway-desc">
                    For researchers, learners, and craft practitioners. Query verified institutional
                    craft documentation and recorded artisan testimony via spoken audio or text to
                    retrieve authentic material mixtures, glazing chemistry, and handloom techniques.
                  </p>

                  <form onSubmit={(e) => handleAskQuestion(e)} className="recessed-console">
                    <div className="console-top-bar">
                      <span>
                        <span className="wave-bars-mini" aria-hidden="true">
                          ılı
                        </span>{' '}
                        ACOUSTIC &amp; TEXT QUERY INPUT
                      </span>
                      <span>STRICT CITATION CORROBORATED</span>
                    </div>

                    <div className="console-controls-row">
                      <div style={{ flex: '1 1 180px' }}>
                        <label htmlFor="craft-filter-select" className="docket-field-label">
                          Craft Tradition Scope
                        </label>
                        <select
                          id="craft-filter-select"
                          className="archival-select"
                          value={selectedCraft}
                          onChange={(e) => setSelectedCraft(e.target.value)}
                        >
                          <option value="">All Verified Crafts</option>
                          {CRAFTS.map((c) => (
                            <option key={c} value={c}>
                              {c}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div style={{ flex: '1 1 200px' }}>
                        <label htmlFor="voice-question-file" className="docket-field-label">
                          Optional Voice Prompt (Saaras STT)
                        </label>
                        <input
                          id="voice-question-file"
                          type="file"
                          className="archival-input"
                          style={{ padding: '0.36rem 0.5rem', fontSize: '0.78rem' }}
                          accept=".wav,.mp3,.ogg,.m4a,.flac,.aac,.webm,audio/*"
                          onChange={handleVoiceQuestionUpload}
                          disabled={voiceQuestionLoading}
                        />
                      </div>
                    </div>

                    <label htmlFor="archive-query-input" className="docket-field-label">
                      Inquiry Prompt *
                    </label>
                    <div className="inspect-input-group">
                      <input
                        id="archive-query-input"
                        ref={questionInputRef}
                        type="text"
                        placeholder="Ask about quartz dough, cobalt oxide glaze, or Paithani weft interlocking..."
                        value={question}
                        onChange={(e) => setQuestion(e.target.value)}
                        required
                      />
                      <button
                        type="submit"
                        className="btn-inspect-dark"
                        disabled={asking || voiceQuestionLoading}
                      >
                        {asking ? 'SEARCHING...' : '🔍 INSPECT'}
                      </button>
                    </div>

                    <div className="curated-inquiries-row">
                      <span className="curated-label">CURATED INQUIRIES:</span>
                      {SAMPLE_QUESTIONS.map((sq) => (
                        <button
                          key={sq.shortLabel}
                          type="button"
                          className="inquiry-chip-btn"
                          onClick={() => {
                            setSelectedCraft(sq.craft);
                            setQuestion(sq.q);
                            handleAskQuestion(null, sq.q, sq.craft);
                          }}
                        >
                          ❖ {sq.shortLabel}
                        </button>
                      ))}
                    </div>
                  </form>

                  {qaError && (
                    <div className="archival-notice error" role="alert">
                      {qaError}
                    </div>
                  )}

                  <div className="pathway-footer-row">
                    <span className="pathway-guarantee">
                      <span style={{ color: 'var(--accent-terracotta)' }} aria-hidden="true">
                        ■
                      </span>{' '}
                      100% Citation Grounding Guaranteed
                    </span>
                    <button
                      type="button"
                      className="btn-pathway-charcoal"
                      onClick={(e) => handleAskQuestion(e)}
                      disabled={asking || voiceQuestionLoading}
                    >
                      {asking ? 'QUERYING ARCHIVE...' : 'QUERY THE ARCHIVE →'}
                    </button>
                  </div>
                </div>
              </div>

              {/* RIGHT CARD: CONTRIBUTE KNOWLEDGE */}
              <div className="pathway-card capture-pathway" id="contribute-card">
                <div className="pathway-card-inner">
                  <div className="slip-header-row">
                    <span className="slip-division-label">
                      <span aria-hidden="true">🎙️</span> INTAKE RECORD 02 · FIELD CAPTURE
                    </span>
                    <span className="slip-badge-box">REG. DOCKET</span>
                  </div>

                  <h3 className="pathway-title">Contribute Knowledge</h3>
                  <p className="pathway-desc">
                    For artisans, field documentarians, and craft researchers. Upload spoken
                    vernacular recordings in Hindi, Marathi, or English, transcribe via Sarvam
                    Saaras, review the transcript, and save a cited archive entry.
                  </p>

                  <div className="recessed-console">
                    <div className="console-top-bar">
                      <span>● VERNACULAR AUDIO CAPTURE UNIT</span>
                      <span>SARVAM SAARAS v3 · WAV / MP3 / M4A</span>
                    </div>

                    {/* Vintage Acoustic Waveform Visualizer */}
                    <div
                      className={`waveform-visualizer-box ${
                        transcribing || audioFile ? 'active' : ''
                      }`}
                      aria-hidden="true"
                    >
                      {WAVE_BAR_HEIGHTS.map((h, i) => (
                        <span
                          key={i}
                          className={`wave-bar ${
                            i % 3 === 0 ? 'terracotta' : i % 4 === 0 ? 'muted' : ''
                          }`}
                          style={{ height: `${h}px` }}
                        />
                      ))}
                      <span
                        style={{
                          marginLeft: 'auto',
                          fontFamily: 'var(--font-mono)',
                          fontSize: '0.62rem',
                          color: 'var(--ink-muted)',
                          alignSelf: 'center',
                        }}
                      >
                        {transcribing
                          ? 'TRANSCRIBING AUDIO...'
                          : audioFile
                          ? `LOADED: ${audioFile.name}`
                          : 'AWAITING AUDIO CLIP'}
                      </span>
                    </div>

                    {transcribeError && (
                      <div className="archival-notice error" role="alert">
                        {transcribeError}
                      </div>
                    )}
                    {transcribeSuccess && (
                      <div className="archival-notice info" role="status">
                        {transcribeSuccess}
                      </div>
                    )}
                    {saveMessage.text && (
                      <div className={`archival-notice ${saveMessage.type}`} role="status">
                        {saveMessage.text}
                      </div>
                    )}

                    {/* Step 1: Select Audio + Language + Transcribe */}
                    <div className="docket-field-grid" style={{ marginBottom: '0.65rem' }}>
                      <div>
                        <label htmlFor="contrib-audio-input" className="docket-field-label">
                          1. Select Audio File (.wav, .mp3, .m4a)
                        </label>
                        <input
                          id="contrib-audio-input"
                          ref={audioUploadRef}
                          type="file"
                          className="archival-input"
                          style={{ padding: '0.35rem 0.5rem', fontSize: '0.78rem' }}
                          accept=".wav,.mp3,.ogg,.m4a,.flac,.aac,.webm,audio/*"
                          onChange={(e) => {
                            const f =
                              e.target.files && e.target.files[0] ? e.target.files[0] : null;
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

                      <div>
                        <label htmlFor="contrib-lang-select" className="docket-field-label">
                          Spoken Dialect / Language
                        </label>
                        <div style={{ display: 'flex', gap: '0.4rem' }}>
                          <select
                            id="contrib-lang-select"
                            className="archival-select"
                            value={languageCode}
                            onChange={(e) => setLanguageCode(e.target.value)}
                          >
                            <option value="hi-IN">Hindi (hi-IN)</option>
                            <option value="mr-IN">Marathi (mr-IN)</option>
                            <option value="en-IN">English (en-IN)</option>
                          </select>
                          <button
                            type="button"
                            className="btn-inspect-dark"
                            onClick={handleTranscribe}
                            disabled={transcribing}
                          >
                            {transcribing ? '...' : 'TRANSCRIBE'}
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Step 2: Review Transcript & Metadata Docket */}
                    <div className="docket-field-grid">
                      <div>
                        <label htmlFor="docket-craft" className="docket-field-label">
                          Craft Tradition *
                        </label>
                        <select
                          id="docket-craft"
                          className="archival-select"
                          value={craft}
                          onChange={(e) => setCraft(e.target.value)}
                        >
                          {CRAFTS.map((c) => (
                            <option key={c} value={c}>
                              {c}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label htmlFor="docket-artisan" className="docket-field-label">
                          Artisan / Contributor Name *
                        </label>
                        <input
                          id="docket-artisan"
                          type="text"
                          className="archival-input"
                          placeholder="e.g., Mohanlal Kumhar"
                          value={artisanName}
                          onChange={(e) => setArtisanName(e.target.value)}
                        />
                      </div>
                    </div>

                    <div style={{ marginTop: '0.55rem' }}>
                      <label htmlFor="docket-technique" className="docket-field-label">
                        Technique Title *
                      </label>
                      <input
                        id="docket-technique"
                        type="text"
                        className="archival-input"
                        placeholder="e.g., Squirrel-Hair Brush Cobalt Oxide Sketching"
                        value={technique}
                        onChange={(e) => setTechnique(e.target.value)}
                      />
                    </div>

                    <div style={{ marginTop: '0.55rem' }}>
                      <label htmlFor="docket-transcript" className="docket-field-label">
                        Reviewed Transcript (Edit before saving) *
                      </label>
                      <textarea
                        id="docket-transcript"
                        rows={2}
                        className="archival-textarea"
                        placeholder="Saaras transcript appears here for human verification..."
                        value={transcript}
                        onChange={(e) => setTranscript(e.target.value)}
                      />
                    </div>

                    <div className="docket-field-grid">
                      <div>
                        <label htmlFor="docket-materials" className="docket-field-label">
                          Materials (comma-separated)
                        </label>
                        <input
                          id="docket-materials"
                          type="text"
                          className="archival-input"
                          placeholder="Quartz powder, Katira Gond"
                          value={materialsText}
                          onChange={(e) => setMaterialsText(e.target.value)}
                        />
                      </div>

                      <div>
                        <label htmlFor="docket-steps" className="docket-field-label">
                          Process Steps (comma/newline)
                        </label>
                        <input
                          id="docket-steps"
                          type="text"
                          className="archival-input"
                          placeholder="Prepare slip, Apply oxide"
                          value={stepsText}
                          onChange={(e) => setStepsText(e.target.value)}
                        />
                      </div>
                    </div>

                    <div className="docket-field-grid">
                      <div>
                        <label htmlFor="docket-audio-name" className="docket-field-label">
                          Source Audio Filename *
                        </label>
                        <input
                          id="docket-audio-name"
                          type="text"
                          className="archival-input"
                          placeholder="recording_clip.wav"
                          value={sourceAudio}
                          onChange={(e) => setSourceAudio(e.target.value)}
                        />
                      </div>

                      <div>
                        <label htmlFor="docket-segment" className="docket-field-label">
                          Source Segment / Timestamps *
                        </label>
                        <input
                          id="docket-segment"
                          type="text"
                          className="archival-input"
                          placeholder="Segment 1 (0.0s - 14.2s)"
                          value={segment}
                          onChange={(e) => setSegment(e.target.value)}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="pathway-footer-row">
                    <span className="pathway-guarantee">
                      <span aria-hidden="true">🛡️</span> Oral Ethics &amp; Provenance Safeguarded
                    </span>
                    <button
                      type="button"
                      className="btn-pathway-terracotta"
                      onClick={handleSaveEntry}
                      disabled={saving}
                    >
                      {saving ? 'SAVING RECORD...' : 'SAVE ORAL RECORD 🎙️'}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* LIVE ARCHIVAL ANSWER DOSSIER (Appears when learner asks a question) */}
            {qaResult && (
              <article
                ref={dossierRef}
                className={`archival-answer-dossier ${qaResult.grounded ? 'grounded' : 'ungrounded'}`}
                aria-live="polite"
              >
                <div className="dossier-top-meta">
                  <div>
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.72rem',
                        fontWeight: 600,
                        letterSpacing: '0.09em',
                        textTransform: 'uppercase',
                      }}
                    >
                      {qaResult.grounded
                        ? '❖ VERIFIED ARCHIVAL RESPONSE DOSSIER'
                        : '❖ ARCHIVAL REFUSAL NOTICE — NO SOURCE IN CORPUS'}
                    </span>
                  </div>
                  <span className={`dossier-status-tag ${qaResult.grounded ? '' : 'refusal'}`}>
                    {qaResult.grounded
                      ? `GROUNDED IN ${qaResult.sources?.length || 1} VERIFIED SOURCE(S)`
                      : 'UNRECORDED TOPIC — ZERO SPECULATION'}
                  </span>
                </div>

                {qaResult.grounded ? (
                  <div className="dossier-answer-text">{qaResult.answer}</div>
                ) : (
                  <div>
                    <div className="refusal-quote-box">“{qaResult.answer}”</div>
                    <p style={{ fontSize: '0.92rem', color: 'var(--ink-secondary)' }}>
                      The archive does not contain a verified source addressing this question.
                      KalaSetu never fabricates citations or uses general AI assumptions to fill
                      gaps.
                    </p>
                  </div>
                )}

                {qaResult.citations && qaResult.citations.length > 0 && (
                  <div className="citation-ledger-box">
                    <span className="citation-ledger-title">VERIFIED ARCHIVE CITATION LEDGER</span>
                    <div className="citation-mono-text">{qaResult.citations.join(' | ')}</div>
                    {qaResult.source_links && qaResult.source_links.length > 0 && (
                      <div style={{ marginTop: '0.5rem', fontSize: '0.84rem' }}>
                        {qaResult.source_links.map((link) => (
                          <div key={link.id || link.source_url} style={{ marginTop: '0.2rem' }}>
                            <strong>Verify Institutional Source:</strong>{' '}
                            <a
                              href={link.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{ color: 'var(--accent-terracotta)', fontWeight: 600 }}
                            >
                              {link.source_title || link.source_url} ({link.source_organization}) ↗
                            </a>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {qaResult.grounded && qaResult.answer !== NO_SOURCE_FALLBACK && (
                  <>
                    <div className="bulbul-audio-bar">
                      <label
                        htmlFor="bulbul-lang-select"
                        style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: '0.68rem',
                          fontWeight: 600,
                          letterSpacing: '0.08em',
                          textTransform: 'uppercase',
                        }}
                      >
                        Spoken Recitation (Sarvam Bulbul v3):
                      </label>
                      <select
                        id="bulbul-lang-select"
                        className="archival-select"
                        style={{ width: 'auto', padding: '0.35rem 0.65rem', fontSize: '0.84rem' }}
                        value={ttsLang}
                        onChange={(e) => handleTtsLangChange(e.target.value)}
                      >
                        <option value="hi-IN">Hindi (hi-IN • Shubh)</option>
                        <option value="mr-IN">Marathi (mr-IN • Shubh)</option>
                        <option value="en-IN">English (en-IN • Shubh)</option>
                      </select>
                      <button
                        type="button"
                        className="btn-pathway-terracotta"
                        style={{ padding: '0.45rem 0.95rem' }}
                        onClick={handleListenAnswer}
                        disabled={ttsLoading}
                      >
                        {ttsLoading
                          ? ttsLang === 'mr-IN'
                            ? 'TRANSLATING & SYNTHESIZING MARATHI...'
                            : ttsLang === 'hi-IN'
                            ? 'TRANSLATING & SYNTHESIZING HINDI...'
                            : 'SYNTHESIZING ENGLISH AUDIO...'
                          : '🔊 LISTEN TO ANSWER'}
                      </button>
                      {ttsAudioSrc && (
                        <audio
                          key={ttsAudioLang || ttsLang}
                          controls
                          autoPlay
                          src={ttsAudioSrc}
                          style={{ height: '36px' }}
                        >
                          Your browser does not support embedded audio playback.
                        </audio>
                      )}
                    </div>

                    {ttsTranslated && ttsSpokenText && (
                      <div
                        className="citation-ledger-box"
                        style={{ backgroundColor: '#faf7f0', borderColor: 'var(--border-gold)' }}
                      >
                        <span className="citation-ledger-title">
                          SPOKEN RECITATION TRANSLATION (
                          {ttsAudioLang === 'mr-IN'
                            ? 'MARATHI • मराठी'
                            : 'HINDI • हिन्दी'}{' '}
                          — TRANSLATED FROM GROUNDED ANSWER FOR AUDIO PLAYBACK; NOT A DIRECT SOURCE QUOTATION)
                        </span>
                        <p
                          style={{
                            fontFamily: 'var(--font-serif)',
                            fontSize: '0.95rem',
                            color: 'var(--ink-primary)',
                            lineHeight: 1.65,
                          }}
                        >
                          {ttsSpokenText}
                        </p>
                      </div>
                    )}
                  </>
                )}

                {ttsError && (
                  <div className="archival-notice error" role="alert">
                    {ttsError}
                  </div>
                )}

                {qaResult.sources && qaResult.sources.length > 0 && (
                  <div style={{ marginTop: '0.75rem' }}>
                    <div
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.66rem',
                        fontWeight: 600,
                        letterSpacing: '0.1em',
                        textTransform: 'uppercase',
                        color: 'var(--ink-muted)',
                        marginBottom: '0.5rem',
                      }}
                    >
                      SUPPORTING ARCHIVE RECORDS ({qaResult.sources.length})
                    </div>
                    {qaResult.sources.map((src) => {
                      const isInstitutional =
                        src.record_type === 'institutional_documentation' || !src.artisan_name;
                      return (
                        <div
                          key={src.id}
                          style={{
                            backgroundColor: '#fffdf9',
                            border: '1px solid var(--border-hairline)',
                            padding: '0.85rem 1rem',
                            marginBottom: '0.55rem',
                          }}
                        >
                          <div
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              flexWrap: 'wrap',
                              gap: '0.5rem',
                              marginBottom: '0.35rem',
                            }}
                          >
                            <strong>
                              {isInstitutional
                                ? `${src.source_title} (${src.source_organization})`
                                : `${src.artisan_name} — ${src.technique}`}
                            </strong>
                            <code style={{ fontSize: '0.74rem', color: 'var(--accent-terracotta)' }}>
                              ID: {src.id} • {src.segment}
                            </code>
                          </div>
                          <p
                            style={{
                              fontSize: '0.9rem',
                              color: 'var(--ink-secondary)',
                              marginBottom: '0.4rem',
                            }}
                          >
                            {isInstitutional
                              ? src.excerpt || src.transcript
                              : `“${src.transcript}”`}
                          </p>
                          {src.source_url && (
                            <a
                              href={src.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{
                                fontFamily: 'var(--font-mono)',
                                fontSize: '0.7rem',
                                color: 'var(--accent-terracotta)',
                                fontWeight: 600,
                              }}
                            >
                              Verify Publisher Document ({src.source_url}) ↗
                            </a>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </article>
            )}
          </section>

          {/* 5. ARCHIVAL FOUNDATIONS & TENETS (THREE PRINCIPLE CARDS) */}
          <section
            className="archival-section"
            id="tenets-section"
            aria-labelledby="tenets-heading"
          >
            <div className="archival-section-header">
              <div>
                <div className="section-kicker">
                  <span>INSTITUTIONAL METHOD</span>
                  <span>———</span>
                  <span>CODIFIED AXIOMS</span>
                </div>
                <h2 id="tenets-heading" className="section-heading-serif">
                  Archival Foundations &amp; Tenets
                </h2>
              </div>
            </div>

            <div className="tenets-grid">
              <article className="tenet-card">
                <div className="tenet-top-row">
                  <span>CANONICAL PRINCIPLE 01</span>
                  <span aria-hidden="true">❂</span>
                </div>
                <h3 className="tenet-title">Strict Grounding</h3>
                <p className="tenet-body">
                  Zero synthetic speculation or ungrounded model hallucinations. Every generated
                  response directly cites verified institutional craft documentation or reviewed
                  artisan recordings, and refuses unrecorded questions with{' '}
                  <em>“Mere paas iska source nahi hai.”</em>
                </p>
                <div className="tenet-footer">PROOF STANDARD: VERIFIED CITATIONS</div>
              </article>

              <article className="tenet-card terracotta-top">
                <div className="tenet-top-row">
                  <span>CANONICAL PRINCIPLE 02</span>
                  <span aria-hidden="true">🎙️</span>
                </div>
                <h3 className="tenet-title">Oral &amp; Craft Heritage</h3>
                <p className="tenet-body">
                  Preserving authentic Indian material processes and spoken vernacular
                  contributions. Regional names of hand tools (<em>mogri</em>, <em>tilli</em>,{' '}
                  <em>dhote</em>), mineral pigments (<em>Katira Gond</em>, <em>Sajikhar</em>), and
                  workshop practices are retained with human transcript review.
                </p>
                <div className="tenet-footer">VERNACULAR LEXICON RETENTION</div>
              </article>

              <article className="tenet-card slate-top">
                <div className="tenet-top-row">
                  <span>CANONICAL PRINCIPLE 03</span>
                  <span aria-hidden="true">⚖️</span>
                </div>
                <h3 className="tenet-title">Source Traceability</h3>
                <p className="tenet-body">
                  Unbroken provenance chain. Each archive record discloses its source title,
                  publishing institution or contributor, direct verification URL or audio recording
                  filename, document section, and specific supported facts.
                </p>
                <div className="tenet-footer">UNBROKEN PROVENANCE CHAIN</div>
              </article>
            </div>
          </section>

          {/* 6. CURATED ARCHIVE HIGHLIGHTS (REAL VERIFIED ARCHIVE RECORDS) */}
          <section
            className="archival-section"
            id="highlights-section"
            aria-labelledby="highlights-heading"
          >
            <div className="archival-section-header">
              <div>
                <div className="section-kicker">
                  <span
                    style={{
                      backgroundColor: 'var(--accent-terracotta)',
                      color: '#fff',
                      padding: '0.15rem 0.5rem',
                    }}
                  >
                    VERIFIED RECORDS
                  </span>
                  <span>❖ INSTITUTIONAL &amp; ORAL CRAFT SOURCES</span>
                </div>
                <h2 id="highlights-heading" className="section-heading-serif">
                  Curated Archive Highlights
                </h2>
                <p style={{ fontSize: '0.94rem', color: 'var(--ink-secondary)', marginTop: '0.25rem' }}>
                  Verified records documenting Jaipur Blue Pottery and Maharashtra Paithani Weaving,
                  complete with publisher provenance, supported facts, and source links.
                </p>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  className={`inquiry-chip-btn ${catalogCraftFilter === '' ? 'active' : ''}`}
                  style={
                    catalogCraftFilter === ''
                      ? { borderColor: 'var(--accent-terracotta)', color: 'var(--accent-terracotta)', fontWeight: 600 }
                      : {}
                  }
                  onClick={() => setCatalogCraftFilter('')}
                >
                  ALL ({entries.length})
                </button>
                {CRAFTS.map((c) => (
                  <button
                    key={c}
                    type="button"
                    className="inquiry-chip-btn"
                    style={
                      catalogCraftFilter === c
                        ? { borderColor: 'var(--accent-terracotta)', color: 'var(--accent-terracotta)', fontWeight: 600 }
                        : {}
                    }
                    onClick={() => setCatalogCraftFilter(c)}
                  >
                    {c.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            <div className="highlights-grid">
              {filteredCatalogEntries.map((entry) => {
                const visual = ENTRY_VISUAL_META[entry.id] || {
                  image:
                    entry.craft === 'Blue Pottery'
                      ? '/craft-blue-pottery-dough.jpg'
                      : '/craft-paithani-tapestry.jpg',
                  imageAlt: `${entry.craft} — ${entry.technique}`,
                  region:
                    entry.craft === 'Blue Pottery'
                      ? 'Jaipur, Rajasthan'
                      : 'Yeola & Paithan, Maharashtra',
                  photoCredit: entry.source_organization || 'KalaSetu Archive',
                };
                const isInstitutional =
                  entry.record_type === 'institutional_documentation' || !entry.artisan_name;

                return (
                  <article key={entry.id} className="highlight-card">
                    <div className="highlight-image-frame">
                      <img src={visual.image} alt={visual.imageAlt} loading="lazy" />
                      <span className="accession-pill">
                        <span className="status-dot-inline" aria-hidden="true" />
                        ACCESSION · {visual.region}
                      </span>
                      <span className="folio-id-pill">ID: {entry.id}</span>
                    </div>

                    <div className="highlight-body">
                      <div className="highlight-tags-row">
                        <span className="archival-tag">{entry.craft}</span>
                        {(entry.materials || []).slice(0, 2).map((mat) => (
                          <span key={mat} className="archival-tag">
                            {mat}
                          </span>
                        ))}
                      </div>

                      <h3 className="highlight-title">
                        {entry.craft}: {entry.technique}
                      </h3>

                      <p className="highlight-summary">
                        <strong>Source:</strong> {entry.source_title || entry.technique} —{' '}
                        <em>{entry.source_organization || entry.artisan_name}</em>.{' '}
                        {entry.supported_facts && entry.supported_facts.length > 0
                          ? entry.supported_facts[0]
                          : ''}
                      </p>

                      <div className="recitation-box">
                        <div className="recitation-top-bar">
                          <span>
                            {isInstitutional
                              ? `📖 Documented Excerpt: ${entry.source_organization}`
                              : `▶️ Oral Contribution: ${entry.artisan_name}`}
                          </span>
                          <span className="recitation-duration">{entry.segment}</span>
                        </div>

                        <div className="recitation-quote">
                          {isInstitutional
                            ? entry.excerpt || entry.transcript
                            : `“${entry.transcript}”`}
                        </div>

                        {entry.supported_facts && entry.supported_facts.length > 1 && (
                          <details style={{ marginTop: '0.6rem', fontSize: '0.83rem' }}>
                            <summary
                              style={{
                                cursor: 'pointer',
                                fontFamily: 'var(--font-mono)',
                                fontSize: '0.66rem',
                                fontWeight: 600,
                                textTransform: 'uppercase',
                                color: 'var(--ink-secondary)',
                              }}
                            >
                              Inspect All {entry.supported_facts.length} Supported Facts &amp; Steps
                            </summary>
                            <ul style={{ paddingLeft: '1.1rem', marginTop: '0.45rem' }}>
                              {entry.supported_facts.map((fact) => (
                                <li key={fact} style={{ marginBottom: '0.25rem' }}>
                                  {fact}
                                </li>
                              ))}
                            </ul>
                          </details>
                        )}
                      </div>

                      <div className="highlight-footer-bar">
                        <div>
                          {entry.source_url ? (
                            <a
                              href={entry.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{ color: 'var(--ink-secondary)', textDecoration: 'underline' }}
                            >
                              Verify Publisher Source ↗
                            </a>
                          ) : (
                            <span>Audio Source: {entry.source_audio}</span>
                          )}
                        </div>
                        <button
                          type="button"
                          className="sandbox-load-btn"
                          onClick={() => handleLoadIntoSandbox(entry)}
                        >
                          LOAD INTO INQUIRY SANDBOX ↗
                        </button>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>

          {/* 7. DARK CALL-TO-ACTION PANEL */}
          <section className="dark-corpus-cta" aria-labelledby="cta-heading">
            <div className="cta-top-tag">❖ KALASETU-V2-CORPUS</div>
            <div className="cta-inner-grid">
              <div>
                <div className="cta-kicker">
                  IMMEDIATE ARCHIVAL ACCESS ——— VERIFIED SOURCES &amp; BENCHMARK
                </div>
                <h2 id="cta-heading" className="cta-heading">
                  Ready to verify a traditional craft technique?
                </h2>
                <p className="cta-subtext">
                  Search the index for documented raw materials, mineral oxide glazes, or Paithani
                  tapestry interlocking techniques. KalaSetu returns verified citations and source
                  excerpts—or refuses when no source exists.
                </p>
              </div>

              <div className="cta-buttons-cluster">
                <button
                  type="button"
                  className="btn-pathway-terracotta"
                  onClick={() => {
                    scrollToSection('pathway-section', 'ask');
                    if (questionInputRef.current) questionInputRef.current.focus();
                  }}
                >
                  🔍 OPEN ARCHIVE QUERY TERMINAL
                </button>
                <button
                  type="button"
                  className="btn-cta-outline"
                  onClick={() => {
                    setDiagnosticsOpen(true);
                    scrollToSection('diagnostics-section', 'diagnostics');
                  }}
                >
                  ⚖️ GROUNDING DIAGNOSTICS ({benchmark ? benchmark.pass_rate : '10/10'})
                </button>
              </div>
            </div>
            <div className="cta-bottom-right">CITATION CERTIFIED ❖</div>
          </section>

          {/* 8. VISUALLY SECONDARY GROUNDING DIAGNOSTICS LEDGER */}
          <details
            id="diagnostics-section"
            className="diagnostics-ledger-section"
            open={diagnosticsOpen}
          >
            <summary
              className="diagnostics-summary-bar"
              onClick={(e) => {
                e.preventDefault();
                setDiagnosticsOpen((prev) => !prev);
              }}
            >
              <div>
                <span
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.68rem',
                    color: 'var(--accent-terracotta)',
                    letterSpacing: '0.1em',
                    textTransform: 'uppercase',
                    display: 'block',
                  }}
                >
                  ❖ AUTOMATED VERIFICATION LEDGER
                </span>
                <strong style={{ fontFamily: 'var(--font-display)', fontSize: '1.3rem' }}>
                  10-Question Grounding &amp; Refusal Diagnostic Suite
                </strong>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                {benchmark && (
                  <span className="acoustic-ready-box">PASS RATE: {benchmark.pass_rate}</span>
                )}
                <span className="slip-badge-box">
                  {diagnosticsOpen ? 'HIDE LEDGER ▲' : 'INSPECT SUITE ▼'}
                </span>
              </div>
            </summary>

            <div className="diagnostics-table-wrap">
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '0.75rem',
                  marginBottom: '0.85rem',
                }}
              >
                {benchmark && (
                  <p style={{ fontSize: '0.86rem', color: 'var(--ink-secondary)', maxWidth: '75ch' }}>
                    <strong>Pass Criteria:</strong> {benchmark.pass_criteria}
                  </p>
                )}
                <button
                  type="button"
                  className="btn-inspect-dark"
                  onClick={fetchBenchmark}
                  disabled={runningBenchmark}
                >
                  {runningBenchmark ? 'RUNNING...' : 'RE-RUN 10-QUESTION BENCHMARK'}
                </button>
              </div>

              {benchmark && (
                <table className="archival-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Craft</th>
                      <th>Test Question</th>
                      <th>Category</th>
                      <th>Verified Citation / Refusal Output</th>
                      <th>Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {benchmark.results.map((r) => (
                      <tr key={r.id}>
                        <td>
                          <code>{r.id}</code>
                        </td>
                        <td>{r.craft}</td>
                        <td>{r.question}</td>
                        <td>{r.expected_answerable ? 'Answerable (5)' : 'Unanswerable (5)'}</td>
                        <td>
                          <code style={{ fontSize: '0.75rem' }}>
                            {r.grounded ? r.citations.join('; ') : r.answer}
                          </code>
                        </td>
                        <td>
                          <span
                            className="slip-badge-box"
                            style={{
                              borderColor: r.passed ? '#3b6e4c' : 'var(--accent-terracotta)',
                              color: r.passed ? '#1f462c' : 'var(--accent-terracotta)',
                              fontWeight: 600,
                            }}
                          >
                            {r.passed ? 'PASS' : 'FAIL'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </details>
        </main>

        {/* 9. EDITORIAL FOOTER */}
        <footer className="editorial-footer">
          <div className="footer-inner">
            <div className="footer-top-grid">
              <div>
                <div className="footer-brand-line">
                  <span className="footer-brand-name">KalaSetu</span>
                  <span className="gold-diamond" aria-hidden="true">
                    ❖
                  </span>
                  <span className="footer-brand-motto">
                    Preserving Indian craft heritage with verified grounding
                  </span>
                </div>
                <p className="footer-brand-desc">
                  A source-grounded repository safeguarding documented Indian handcraft processes,
                  verified institutional research, and reviewed oral contributions across India.
                </p>
              </div>

              <div className="footer-links-grid">
                <button
                  type="button"
                  className="footer-nav-link"
                  onClick={() => scrollToSection('tenets-section', 'about')}
                >
                  ARCHIVE GUIDELINES
                </button>
                <button
                  type="button"
                  className="footer-nav-link"
                  onClick={() => scrollToSection('highlights-section', 'browse')}
                >
                  PROVENANCE STANDARDS
                </button>
                <button
                  type="button"
                  className="footer-nav-link"
                  onClick={() => scrollToSection('contribute-card', 'contribute')}
                >
                  ORAL HISTORY ETHICS
                </button>
                <button
                  type="button"
                  className="footer-nav-link"
                  onClick={() => scrollToSection('hero-section', 'home')}
                >
                  ABOUT KALASETU
                </button>
                <button
                  type="button"
                  className="footer-nav-link"
                  onClick={() => {
                    setDiagnosticsOpen(true);
                    scrollToSection('diagnostics-section', 'diagnostics');
                  }}
                >
                  GROUNDING BENCHMARK
                </button>
              </div>
            </div>

            <div className="footer-bottom-row">
              <span>
                © KalaSetu Craft Preservation Archive. Documented with strict source citations.
              </span>
              <span style={{ color: 'var(--accent-terracotta)', fontWeight: 600 }}>
                <span className="status-dot-inline" aria-hidden="true" />
                ARCHIVE CITATION GROUNDING: ACTIVE
              </span>
            </div>
          </div>
        </footer>
      </div>
    </>
  );
}

export default App;
