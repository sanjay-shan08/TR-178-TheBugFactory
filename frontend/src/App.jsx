import { useState, useRef } from 'react';
import axios from 'axios';
import './index.css';

function App() {
  const [file, setFile] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [activeTab, setActiveTab] = useState('tactile');
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

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
    if (selected) {
      setFile(selected);
      setError(null);
    }
  };

  const handleSubmit = async () => {
    setIsLoading(true);
    setResult(null);
    setError(null);
    try {
      let response;
      if (file) {
        const formData = new FormData();
        formData.append("file", file);
        response = await axios.post('/api/pipeline/process', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
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
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-badge">AI-Powered Accessibility</div>
        <h1 className="app-title">FloorSense <span className="title-accent">AI</span></h1>
        <p className="app-subtitle">
          Upload a floor plan to generate tactile maps, screen-reader navigation, and audio guides.
        </p>
      </header>

      <main className="app-main">
        {!result ? (
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
                  <p className="drop-secondary">or click to browse — PNG, JPG, PDF supported</p>
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
                ) : (
                  '⚡ Run Pipeline'
                )}
              </button>
              <p className="demo-note">
                No file? Click <strong>Run Pipeline</strong> to test with a mock floor plan.
              </p>
            </div>
          </div>
        ) : (
          <div className="results-section">
            <div className="results-header">
              <h2 className="results-title">Pipeline Complete</h2>
              {result.path_narrative && (
                <p className="narrative-badge">{result.path_narrative}</p>
              )}
              <button className="btn btn-ghost" onClick={handleReset}>← New Floor Plan</button>
            </div>

            <div className="tabs" role="tablist" aria-label="Output formats">
              {[
                { key: 'tactile', label: '🖐 Tactile SVG' },
                { key: 'screen', label: '♿ Screen Reader' },
                { key: 'audio', label: '🔊 Audio Guide' },
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
              {activeTab === 'tactile' && (
                <div className="output-card">
                  <div
                    className="svg-preview"
                    dangerouslySetInnerHTML={{ __html: result.tactile_svg }}
                    aria-label="Tactile floor plan SVG"
                  />
                  <button
                    className="btn btn-secondary"
                    onClick={() => {
                      const blob = new Blob([result.tactile_svg], { type: 'image/svg+xml' });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement('a');
                      a.href = url;
                      a.download = 'tactile_map.svg';
                      a.click();
                      URL.revokeObjectURL(url);
                    }}
                  >
                    ↓ Download SVG
                  </button>
                </div>
              )}

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
                    onClick={() => {
                      const blob = new Blob([result.aria_html], { type: 'text/html' });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement('a');
                      a.href = url;
                      a.download = 'accessible_map.html';
                      a.click();
                      URL.revokeObjectURL(url);
                    }}
                  >
                    ↓ Download HTML
                  </button>
                </div>
              )}

              {activeTab === 'audio' && (
                <div className="output-card audio-card">
                  <div className="audio-icon">🎙️</div>
                  <p className="audio-label">Audio guide generated via OpenAI TTS</p>
                  <p className="audio-note">
                    {result.tts_audio_url
                      ? 'TTS output is ready. In production this would stream an MP3.'
                      : 'No audio URL returned.'}
                  </p>
                  <p className="audio-url">{result.tts_audio_url}</p>
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      <footer className="app-footer">
        <p>FloorSense AI · Phase 1–3 Demo · Built with FastAPI + React</p>
      </footer>
    </div>
  );
}

export default App;
