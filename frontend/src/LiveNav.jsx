import { useState, useEffect, useRef, useCallback, forwardRef, useImperativeHandle } from 'react';
import api from './api';

// ─────────────────────────────────────────────────────────────────────────────
// VOICE ENGINE — priority queue, dedup, rate-limit (Web Speech API)
// ─────────────────────────────────────────────────────────────────────────────
const voiceQueue = [];
let isSpeaking = false;

function speak(message, priority = 'low') {
  if (!window.speechSynthesis) return;
  if (voiceQueue.some(q => q.text === message)) return;
  voiceQueue.push({ text: message, priority });
  voiceQueue.sort((a, b) => {
    const rank = { high: 0, medium: 1, low: 2 };
    return (rank[a.priority] ?? 3) - (rank[b.priority] ?? 3);
  });
  if (!isSpeaking) processQueue();
}

function processQueue() {
  if (!voiceQueue.length) { isSpeaking = false; return; }
  isSpeaking = true;
  const { text } = voiceQueue.shift();
  const utt = new SpeechSynthesisUtterance(text);
  utt.rate = 0.92;
  utt.pitch = 1.05;
  utt.lang = 'en-US';
  utt.onend = processQueue;
  utt.onerror = processQueue;
  window.speechSynthesis.speak(utt);
}

function stopSpeech() {
  voiceQueue.length = 0;
  isSpeaking = false;
  window.speechSynthesis?.cancel();
}

// ─────────────────────────────────────────────────────────────────────────────
// STEP COUNTER — peak detection on accelerometer magnitude
// ─────────────────────────────────────────────────────────────────────────────
const STEP_THRESHOLD = 11;
let lastMag = 0;
let stepCooldown = false;

function detectStep(x, y, z) {
  const mag = Math.sqrt(x * x + y * y + z * z);
  const delta = Math.abs(mag - lastMag);
  lastMag = mag;
  if (delta > STEP_THRESHOLD && !stepCooldown) {
    stepCooldown = true;
    setTimeout(() => { stepCooldown = false; }, 380);
    return true;
  }
  return false;
}

// ─────────────────────────────────────────────────────────────────────────────
// TURN DETECTION — gyroscope heading delta
// ─────────────────────────────────────────────────────────────────────────────
const TURN_THRESHOLD = 28; // degrees before announcing a turn
let prevHeading = null;
let turnCooldown = false;

function detectTurn(heading) {
  if (prevHeading === null) { prevHeading = heading; return null; }
  let delta = heading - prevHeading;
  if (delta > 180) delta -= 360;
  if (delta < -180) delta += 360;
  prevHeading = heading;
  if (Math.abs(delta) < TURN_THRESHOLD || turnCooldown) return null;
  turnCooldown = true;
  setTimeout(() => { turnCooldown = false; }, 3000);
  if (Math.abs(delta) > 150) return { dir: 'U-turn',    deg: 180 };
  if (delta > 0)              return { dir: 'right turn', deg: Math.round(delta) };
  return                             { dir: 'left turn',  deg: Math.round(-delta) };
}

// ─────────────────────────────────────────────────────────────────────────────
// OBJECT POSITION — left / center / right based on bounding box
// ─────────────────────────────────────────────────────────────────────────────
function getPosition(bbox, frameW) {
  const cx = (bbox.x1 + bbox.x2) / 2;
  const r  = cx / (frameW || 640);
  if (r < 0.33) return 'on your left';
  if (r > 0.66) return 'on your right';
  return 'directly ahead';
}

// ─────────────────────────────────────────────────────────────────────────────
// COLORS
// ─────────────────────────────────────────────────────────────────────────────
const WARNING_COLORS = { high: '#ef4444', medium: '#f59e0b', low: '#22c55e' };

const COMPASS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];

// ─────────────────────────────────────────────────────────────────────────────
// COMPONENT
// ─────────────────────────────────────────────────────────────────────────────
const LiveNav = forwardRef(function LiveNav(_, ref) {
  const videoRef      = useRef(null);
  const canvasRef     = useRef(null);  // hidden capture canvas
  const overlayRef    = useRef(null);  // visible bounding-box canvas
  const streamRef     = useRef(null);
  const detectingRef  = useRef(false);
  const lastSpokenRef = useRef({});
  const stepsRef      = useRef(0);     // ref copy for sensor callbacks

  const [active,       setActive]       = useState(false);
  const [emergency,    setEmergency]    = useState(false);
  const [lowLight,     setLowLight]     = useState(false);
  const [steps,        setSteps]        = useState(0);
  const [heading,      setHeading]      = useState(null);
  const [turnMsg,      setTurnMsg]      = useState('');
  const [detections,   setDetections]   = useState([]);
  const [ocrText,      setOcrText]      = useState('');
  const [ocrLoading,   setOcrLoading]   = useState(false);
  const [statusMsg,    setStatusMsg]    = useState('Tap Start to begin navigation');
  const [sensorOk,     setSensorOk]     = useState(false);
  const [camError,     setCamError]     = useState(null);

  // ── Camera ────────────────────────────────────────────────────────────────
  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      });
      streamRef.current = stream;
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      setCamError(null);
      setLowLight(false);
    } catch (err) {
      setCamError('Camera access denied. Running in sensor-only mode.');
      setLowLight(true); // fallback to sensor-only
    }
  };

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  };

  // ── Frame capture ─────────────────────────────────────────────────────────
  const captureFrame = useCallback(() => {
    const video  = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2) return null;
    canvas.width  = video.videoWidth  || 640;
    canvas.height = video.videoHeight || 480;
    canvas.getContext('2d').drawImage(video, 0, 0);

    // Low-light detection: sample brightness
    const ctx = canvas.getContext('2d');
    const px = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    let brightness = 0;
    for (let i = 0; i < px.length; i += 16) brightness += (px[i] + px[i+1] + px[i+2]) / 3;
    brightness /= (px.length / 16);
    setLowLight(brightness < 30);

    return canvas.toDataURL('image/jpeg', 0.7);
  }, []);

  // ── Draw bounding boxes ───────────────────────────────────────────────────
  const drawDetections = useCallback((dets, frameW, frameH) => {
    const overlay = overlayRef.current;
    if (!overlay) return;
    overlay.width  = videoRef.current?.clientWidth  || 640;
    overlay.height = videoRef.current?.clientHeight || 480;
    const ctx = overlay.getContext('2d');
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    const sx = overlay.width  / (frameW || 640);
    const sy = overlay.height / (frameH || 480);

    dets.forEach(det => {
      const color = WARNING_COLORS[det.warning_level] || '#fff';
      const bx = det.bbox.x1 * sx, by = det.bbox.y1 * sy;
      const bw = (det.bbox.x2 - det.bbox.x1) * sx;
      const bh = (det.bbox.y2 - det.bbox.y1) * sy;

      // Box glow for high warnings
      if (det.warning_level === 'high') {
        ctx.shadowColor = color;
        ctx.shadowBlur  = 12;
      }
      ctx.strokeStyle = color;
      ctx.lineWidth   = det.warning_level === 'high' ? 4 : 2.5;
      ctx.strokeRect(bx, by, bw, bh);
      ctx.shadowBlur  = 0;

      // Label pill
      const pos   = getPosition(det.bbox, frameW);
      const label = `${det.label} • ${pos}`;
      ctx.font = 'bold 13px Arial';
      const tw = ctx.measureText(label).width;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.roundRect(bx, by - 24, tw + 12, 22, 4);
      ctx.fill();
      ctx.fillStyle = '#000';
      ctx.fillText(label, bx + 6, by - 7);
    });
  }, []);

  // ── Detection loop ────────────────────────────────────────────────────────
  const runDetectionLoop = useCallback(async () => {
    if (!detectingRef.current) return;

    // In low-light or sensor-only mode, skip camera detection
    if (!lowLight && streamRef.current) {
      const frame = captureFrame();
      if (frame) {
        try {
          const res = await api.post('/api/live-nav/detect', { image: frame });
          const { detections: dets, frame_width: fw, frame_height: fh } = res.data;

          // Emergency mode: only care about exits/stairs
          const filtered = emergency
            ? dets.filter(d => ['exit', 'stairs', 'elevator', 'lift'].includes(d.label))
            : dets;

          setDetections(filtered);
          drawDetections(filtered, fw, fh);

          // Voice announcements with positional context
          const now = Date.now();
          filtered.forEach(det => {
            if (det.warning_level === 'low' && !emergency) return;
            const last     = lastSpokenRef.current[det.label] || 0;
            const cooldown = det.warning_level === 'high' ? 3000 : 6000;
            if (now - last > cooldown) {
              const pos = getPosition(det.bbox, fw);
              speak(`${det.label} ${pos}`, det.warning_level);
              lastSpokenRef.current[det.label] = now;
            }
          });

          // Emergency mode: no exits found
          if (emergency && filtered.length === 0) {
            speak('No exit detected. Keep moving forward slowly.', 'medium');
          }

          const highCount = filtered.filter(d => d.warning_level === 'high').length;
          setStatusMsg(
            emergency
              ? filtered.length > 0 ? `🚨 Exit detected!` : '🔴 Searching for exit…'
              : highCount > 0
                ? `⚠️ ${highCount} obstacle${highCount > 1 ? 's' : ''} detected`
                : filtered.length > 0 ? `${filtered.length} object${filtered.length > 1 ? 's' : ''} in view`
                : 'Path clear'
          );
        } catch { /* silent */ }
      }
    } else if (lowLight) {
      // Low-light fallback — sensor-only guidance
      setStatusMsg('🌑 Low light — sensor mode active');
      const s = stepsRef.current;
      if (s > 0 && s % 10 === 0) {
        speak(`${s} steps taken. Continue forward.`, 'low');
      }
    }

    if (detectingRef.current) setTimeout(runDetectionLoop, 800);
  }, [captureFrame, drawDetections, emergency, lowLight]);

  // ── Sensors ───────────────────────────────────────────────────────────────
  const startSensors = useCallback(async () => {
    if (typeof DeviceMotionEvent?.requestPermission === 'function') {
      try {
        const p = await DeviceMotionEvent.requestPermission();
        if (p !== 'granted') return;
      } catch { return; }
    }

    window.addEventListener('devicemotion', (e) => {
      const a = e.accelerationIncludingGravity;
      if (!a) return;
      if (detectStep(a.x || 0, a.y || 0, a.z || 0)) {
        setSteps(s => {
          const next = s + 1;
          stepsRef.current = next;
          // Announce every 5 steps
          if (next % 5 === 0) speak(`${next} steps taken`, 'low');
          return next;
        });
      }
    });

    window.addEventListener('deviceorientationabsolute', handleOrientation, true);
    window.addEventListener('deviceorientation',         handleOrientation, true);
    setSensorOk(true);
  }, []);

  const handleOrientation = (e) => {
    if (e.alpha === null) return;
    const deg = Math.round(e.alpha);
    setHeading(deg);
    setSensorOk(true);

    const turn = detectTurn(deg);
    if (turn) {
      const msg = `${turn.dir} detected. ${turn.deg} degrees.`;
      setTurnMsg(msg);
      speak(msg, 'medium');
      setTimeout(() => setTurnMsg(''), 4000);
    }
  };

  // ── OCR scan ──────────────────────────────────────────────────────────────
  const handleOCRScan = async () => {
    const frame = captureFrame();
    if (!frame) { speak('Camera not available for scanning', 'medium'); return; }
    setOcrLoading(true);
    setOcrText('');
    try {
      const res  = await api.post('/api/live-nav/ocr', { image: frame });
      const text = res.data.combined;
      setOcrText(text || 'No text detected');
      if (text) speak(text, 'medium');
      else      speak('No readable text found', 'low');
    } catch {
      setOcrText('OCR request failed');
    } finally {
      setOcrLoading(false);
    }
  };

  // ── Emergency exit mode ───────────────────────────────────────────────────
  const toggleEmergency = () => {
    setEmergency(prev => {
      const next = !prev;
      if (next) {
        speak('Emergency mode activated. Searching for nearest exit.', 'high');
        setStatusMsg('🚨 Emergency — searching for exit…');
      } else {
        speak('Emergency mode deactivated.', 'low');
      }
      return next;
    });
  };

  // ── Start / Stop ──────────────────────────────────────────────────────────
  const handleStart = async () => {
    prevHeading = null;
    stepsRef.current = 0;
    await startCamera();
    await startSensors();
    detectingRef.current = true;
    setActive(true);
    setSteps(0);
    setDetections([]);
    setOcrText('');
    setTurnMsg('');
    speak('Live navigation started. Camera and sensors are active. Point the camera forward.', 'low');
    setTimeout(runDetectionLoop, 600);
  };

  const handleStop = () => {
    detectingRef.current = false;
    stopCamera();
    stopSpeech();
    setActive(false);
    setEmergency(false);
    setDetections([]);
    setTurnMsg('');
    setStatusMsg('Navigation stopped');
    overlayRef.current?.getContext('2d').clearRect(
      0, 0, overlayRef.current.width, overlayRef.current.height
    );
  };

  useEffect(() => () => handleStop(), []);

  // Expose start() so App.jsx can call it via voice command
  useImperativeHandle(ref, () => ({
    start: () => { if (!active) handleStart(); },
  }));

  const headingLabel = heading !== null ? COMPASS[Math.round(heading / 45) % 8] : '—';
  const headingDeg   = heading !== null ? `${heading}°` : '—';

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className={`livenav ${emergency ? 'livenav-emergency' : ''}`}>

      {/* Header */}
      <div className="livenav-header">
        <h2 className="livenav-title">Live Navigation</h2>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          {lowLight && active && (
            <span className="livenav-badge" style={{ background: 'rgba(99,102,241,0.15)', color: '#818cf8', border: '1px solid rgba(129,140,248,0.3)' }}>
              🌑 SENSOR ONLY
            </span>
          )}
          <span className={`livenav-badge ${emergency ? 'badge-emergency' : active ? 'badge-active' : 'badge-idle'}`}>
            {emergency ? '🚨 EMERGENCY' : active ? '● LIVE' : '○ IDLE'}
          </span>
        </div>
      </div>

      {/* Camera + overlay */}
      <div className="camera-wrap">
        <video ref={videoRef} className="camera-feed" muted playsInline />
        <canvas ref={overlayRef} className="camera-overlay" />
        <canvas ref={canvasRef} style={{ display: 'none' }} />

        {!active && (
          <div className="camera-placeholder">
            <span className="camera-icon">📷</span>
            <p>Camera inactive</p>
          </div>
        )}

        {active && (
          <div className={`status-pill ${
            emergency                                          ? 'pill-emergency'
            : detections.some(d => d.warning_level === 'high') ? 'pill-danger'
            : 'pill-ok'
          }`}>
            {statusMsg}
          </div>
        )}
      </div>

      {/* Camera error */}
      {camError && <p className="livenav-error">{camError}</p>}

      {/* Turn announcement */}
      {turnMsg && (
        <div className="turn-alert" role="alert" aria-live="assertive">
          🔄 {turnMsg}
        </div>
      )}

      {/* Controls */}
      <div className="livenav-controls">
        {!active ? (
          <button className="btn btn-primary btn-lg" onClick={handleStart}>
            ▶ Start Navigation
          </button>
        ) : (
          <>
            <button className="btn btn-danger" onClick={handleStop}>
              ■ Stop
            </button>
            <button
              className="btn btn-secondary"
              onClick={handleOCRScan}
              disabled={ocrLoading}
            >
              {ocrLoading ? '🔍 Scanning…' : '🔤 Scan Sign'}
            </button>
            <button
              className={`btn ${emergency ? 'btn-emergency-off' : 'btn-emergency'}`}
              onClick={toggleEmergency}
            >
              {emergency ? '✕ Exit Emergency' : '🚨 Emergency Exit'}
            </button>
          </>
        )}
      </div>

      {/* Sensor grid */}
      <div className="sensor-grid">
        <div className="sensor-card">
          <div className="sensor-icon">👣</div>
          <div className="sensor-value">{steps}</div>
          <div className="sensor-label">Steps</div>
        </div>
        <div className="sensor-card">
          <div className="sensor-icon">🧭</div>
          <div className="sensor-value">{headingLabel}</div>
          <div className="sensor-label">{headingDeg}</div>
        </div>
        <div className="sensor-card">
          <div className="sensor-icon">🎯</div>
          <div className="sensor-value">{detections.length}</div>
          <div className="sensor-label">Objects</div>
        </div>
        <div className="sensor-card">
          <div className="sensor-icon">{sensorOk ? '✅' : '⏳'}</div>
          <div className="sensor-value" style={{ fontSize: '0.85rem' }}>
            {sensorOk ? 'Active' : 'Waiting'}
          </div>
          <div className="sensor-label">Sensors</div>
        </div>
      </div>

      {/* Detection list */}
      {detections.length > 0 && (
        <div className="detection-list">
          <h3 className="detection-list-title">Detected Objects</h3>
          {detections.map((det, i) => {
            const pos = getPosition(det.bbox, 640);
            return (
              <div key={i} className={`detection-item det-${det.warning_level}`}>
                <span className="det-label">{det.label}</span>
                <span className="det-pos">{pos}</span>
                <span className="det-conf">{Math.round(det.confidence * 100)}%</span>
                <button
                  className="det-speak"
                  onClick={() => speak(`${det.label} ${pos}`, det.warning_level)}
                  aria-label={`Speak ${det.label}`}
                >🔊</button>
              </div>
            );
          })}
        </div>
      )}

      {/* OCR result */}
      {ocrText && (
        <div className="ocr-result">
          <h3 className="ocr-title">🔤 Sign Detected</h3>
          <p className="ocr-text">{ocrText}</p>
          <button className="btn btn-ghost btn-sm" onClick={() => speak(ocrText, 'medium')}>
            🔊 Read aloud
          </button>
        </div>
      )}

      {/* Low-light guidance panel */}
      {lowLight && active && (
        <div className="lowlight-panel">
          <p>🌑 <strong>Low-light mode</strong> — Camera detection paused. Using step and direction sensors only.</p>
          <p style={{ fontSize: '0.82rem', marginTop: '0.4rem', opacity: 0.7 }}>
            Move to a brighter area to re-enable obstacle detection.
          </p>
        </div>
      )}

    </div>
  );
});

export default LiveNav;
