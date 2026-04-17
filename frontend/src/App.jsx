import { useState, useRef } from 'react';
import axios from 'axios';
import './index.css';
import LiveNav from './LiveNav';
import VoiceBot from './VoiceBot';

function App() {
  const [mode, setMode]           = useState('floorplan');
  const [file, setFile]           = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult]       = useState(null);
  const [activeTab, setActiveTab] = useState('tactile');
  const [error, setError]         = useState(null);
  const [speaking, setSpeaking]   = useState(false);
  const fileInputRef  = useRef(null);
  const liveNavRef    = useRef(null);

  // ── Drag & drop ────────────────────────────────────────────────────────────
  const handleDragOver = (e) => {
    e.preventDefault();
    e.currentTarget.classList.add('drag-over');
  };

  const handleDragLeave = (e) => {
    e.currentTarget.classList.remove('drag-over');
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.currentTarget.classList.remove('drag-over');
    const dropped = e.dataTransfer.files[0];
    if (dropped && dropped.type.startsWith('image/')) {
      setFile(dropped);
      setError(null);
    } else {
      setError('Please drop an image file (PNG, JPG, etc.)');
    }
  };

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    if (selected) { setFile(selected); setError(null); }
  };

  // ── Pipeline submit ────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    setIsLoading(true);
    setResult(null);
    setError(null);
    try {
      let response;
      if (file) {
        const formData = new FormData();
        formData.append('file', file);
        response = await axios.post('/api/pipeline/process', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
      } else {
        response = await axios.post('/api/pipeline/process-mock?source=n1&target=n4');
      }
      setResult(response.data);
      setActiveTab('tactile');
    } catch (err) {
      setError(err.response?.data?.detail || 'Something went wrong. Is the backend running?');
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setResult(null);
    setError(null);
    stopSpeech();
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // ── Web Speech API ─────────────────────────────────────────────────────────
  const speakText = (text) => {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utt = new SpeechSynthesisUtterance(text);
    utt.rate = 0.95;
    utt.pitch = 1.0;
    utt.lang = 'en-US';
    utt.onstart = () => setSpeaking(true);
    utt.onend   = () => setSpeaking(false);
    utt.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(utt);
  };

  const stopSpeech = () => {
    window.speechSynthesis?.cancel();
    setSpeaking(false);
  };

  const handleVoiceCommand = (action, transcript) => {
    console.log("🗣️ Voice Command:", action, "| Transcript:", transcript);
    switch (action) {
      case 'switch_to_livenav':
        setMode('livenav');
        handleReset();
        // Give React a tick to mount LiveNav, then start it
        setTimeout(() => liveNavRef.current?.start(), 300);
        break;
      case 'switch_to_floorplan':
        setMode('floorplan');
        handleReset();
        break;
      case 'run_pipeline':
        setMode('floorplan');
        // Ensure state settles before starting task
        setTimeout(() => handleSubmit(), 50);
        break;
      case 'play_audio_guide':
        if (result && result.tts_text) {
          setActiveTab('audio');
          speakText(result.tts_text);
        }
        break;
      case 'stop_audio':
        stopSpeech();
        break;
      case 'reset':
        setMode('floorplan');
        handleReset();
        break;
      case 'show_tactile':
        if (result) setActiveTab('tactile');
        break;
      case 'show_screen_reader':
        if (result) setActiveTab('screen');
        break;
      default:
        console.log("Unmapped voice action:", action);
        break;
    }
  };

  // ── Download helpers ───────────────────────────────────────────────────────
  const downloadBlob = (content, filename, mime) => {
    const url = URL.createObjectURL(new Blob([content], { type: mime }));
    const a = document.createElement('a');
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="app">

      {/* Header */}
      <header className="app-header">
        <div className="header-badge">AI-Powered Accessibility</div>
        <h1 className="app-title">FloorSense <span className="title-accent">AI</span></h1>
        <p className="app-subtitle">
          Upload a floor plan to generate tactile maps, screen-reader navigation, and audio guides.
        </p>
      </header>

      {/* Mode switcher */}
      <div className="mode-switcher" role="tablist" aria-label="App mode">
        {[
          { key: 'floorplan', label: '🗺️  Floor Plan Analysis' },
          { key: 'livenav',   label: '📷  Live Navigation' },
        ].map(({ key, label }) => (
          <button
            key={key}
            role="tab"
            aria-selected={mode === key}
            className={`mode-btn ${mode === key ? 'mode-active' : ''}`}
            onClick={() => { setMode(key); handleReset(); }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Main */}
      <main className="app-main">

        {/* ── Live Navigation mode ── */}
        {mode === 'livenav' && <LiveNav ref={liveNavRef} />}

        {/* ── Floor Plan mode ── */}
        {mode === 'floorplan' && !result && (
          <div className="upload-section">
            <div
              className="drop-zone"
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              role="button"
              tabIndex={0}
              aria-label="Upload floor plan image"
              onKeyDown={(e) => e.key === 'Enter' && fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleFileChange}
                className="file-input-hidden"
                aria-hidden="true"
              />
              <div className="drop-icon">🗺️</div>
              {file ? (
                <div className="file-selected">
                  <span className="file-name">{file.name}</span>
                  <span className="file-size">({(file.size / 1024).toFixed(1)} KB)</span>
                </div>
              ) : (
                <>
                  <p className="drop-primary">Drag & drop your floor plan here</p>
                  <p className="drop-secondary">or click to browse — PNG, JPG supported</p>
                </>
              )}
            </div>

            {error && <p className="error-message" role="alert">{error}</p>}

            <div className="action-row">
              <button
                className="btn btn-primary"
                onClick={handleSubmit}
                disabled={isLoading}
                aria-busy={isLoading}
              >
                {isLoading ? (
                  <span className="loading-inner">
                    <span className="spinner" aria-hidden="true" />
                    Processing…
                  </span>
                ) : '⚡ Run Pipeline'}
              </button>
              <p className="demo-note">
                No file? Click <strong>Run Pipeline</strong> to test with a mock floor plan.
              </p>
            </div>
          </div>
        )}

        {/* ── Results ── */}
        {mode === 'floorplan' && result && (
          <div className="results-section">
            <div className="results-header">
              <h2 className="results-title">Pipeline Complete</h2>
              {result.path_narrative && (
                <p className="narrative-badge">{result.path_narrative}</p>
              )}
              <button className="btn btn-ghost" onClick={handleReset}>← New Floor Plan</button>
            </div>

            {/* Vision API error banner */}
            {result.vision_error && (
              <div className="api-error-banner" role="alert">
                <strong>⚠️ Floor plan used mock data</strong>
                <p>{result.vision_error}</p>
              </div>
            )}

            {/* Output tabs */}
            <div className="tabs" role="tablist" aria-label="Output formats">
              {[
                { key: 'tactile', label: '🖐 Tactile SVG'    },
                { key: 'screen',  label: '♿ Screen Reader'   },
                { key: 'audio',   label: '🔊 Audio Guide'     },
              ].map(({ key, label }) => (
                <button
                  key={key}
                  role="tab"
                  aria-selected={activeTab === key}
                  className={`tab-btn ${activeTab === key ? 'tab-active' : ''}`}
                  onClick={() => setActiveTab(key)}
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="tab-panel" role="tabpanel">

              {/* Tactile SVG */}
              {activeTab === 'tactile' && (
                <div className="output-card">
                  <div
                    className="svg-preview"
                    dangerouslySetInnerHTML={{ __html: result.tactile_svg }}
                    aria-label="Tactile floor plan SVG"
                  />
                  <button
                    className="btn btn-secondary"
                    onClick={() => downloadBlob(result.tactile_svg, 'tactile_map.svg', 'image/svg+xml')}
                  >
                    ↓ Download SVG
                  </button>
                </div>
              )}

              {/* Screen reader HTML */}
              {activeTab === 'screen' && (
                <div className="output-card">
                  <iframe
                    className="html-preview"
                    srcDoc={result.aria_html}
                    title="Screen reader accessible floor plan"
                    sandbox="allow-same-origin"
                  />
                  <button
                    className="btn btn-secondary"
                    onClick={() => downloadBlob(result.aria_html, 'accessible_map.html', 'text/html')}
                  >
                    ↓ Download HTML
                  </button>
                </div>
              )}

              {/* Audio guide — Web Speech API */}
              {activeTab === 'audio' && (
                <div className="output-card audio-card">
                  <div className="audio-icon">🎙️</div>
                  <p className="audio-label">Navigation Audio Guide</p>
                  <p className="audio-note">
                    Powered by your browser's built-in speech engine — no API key needed.
                  </p>

                  {result.tts_text ? (
                    <>
                      <p className="audio-script">{result.tts_text}</p>
                      <div className="audio-controls">
                        <button
                          className="btn btn-primary"
                          onClick={() => speakText(result.tts_text)}
                          disabled={speaking}
                        >
                          {speaking ? '🔊 Speaking…' : '▶ Play'}
                        </button>
                        {speaking && (
                          <button className="btn btn-ghost" onClick={stopSpeech}>
                            ⏹ Stop
                          </button>
                        )}
                      </div>
                    </>
                  ) : (
                    <p className="audio-note">No navigation text returned.</p>
                  )}
                </div>
              )}

            </div>
          </div>
        )}

      </main>

      <footer className="app-footer">
        <p>FloorSense AI · Built with FastAPI + React · Groq Vision · Web Speech API</p>
      </footer>
      <VoiceBot onCommand={handleVoiceCommand} />
    </div>
  );
}

export default App;
