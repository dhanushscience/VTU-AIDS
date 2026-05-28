import React, { useState, useEffect } from 'react';
import { Download, CalendarDays, Edit3, Bot, Shield, Zap, CheckCircle, AlertCircle } from 'lucide-react';
import './index.css';

function App() {
  const [downloaded, setDownloaded] = useState(false);
  const [clickPos, setClickPos] = useState({ x: '50%', y: '50%' });

  // Narrative Sequence State for Flip
  const [flipped, setFlipped] = useState(false);

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const isMobile =
      window.matchMedia('(max-width: 768px)').matches ||
      window.matchMedia('(hover: none) and (pointer: coarse)').matches;

    const root = document.documentElement;
    root.classList.toggle('is-mobile', isMobile);
    if (!prefersReducedMotion) {
      root.classList.add('intro-active');
    }

    // Chaos intro ~4s; extra buffer on mobile for slower GPUs / Safari.
    const flipDelay = prefersReducedMotion ? 800 : isMobile ? 5200 : 4500;
    const flipTimer = setTimeout(() => {
      setFlipped(true);
      root.classList.remove('intro-active');
    }, flipDelay);

    return () => {
      clearTimeout(flipTimer);
      root.classList.remove('intro-active');
    };
  }, []);

  const handleDownload = (e) => {
    setClickPos({ x: `${e.clientX}px`, y: `${e.clientY}px` });
    setDownloaded(true);
  };

  const resetPage = () => {
    setDownloaded(false);
  };

  return (
    <>
      {/* MASSIVE WAVE THEME OVERLAY (DOWNLOAD SUCCESS) - OUTSIDE FLIPPER SO IT DOESN'T FLIP */}
      <div 
        className={`success-page-overlay ${downloaded ? 'active' : ''}`}
        style={{ '--x': clickPos.x, '--y': clickPos.y }}
      >
        {downloaded && (
          <div className="success-content">
            <CheckCircle size={64} color="#34d399" />
            <h2>Brilliant Decision.</h2>
            <p>
              You just downloaded <span style={{ fontWeight: 700, color: 'white' }}>AIDs</span> — it won't kill you, but it will save you from manual diary torture. Productivity just got a whole lot less dramatic.
            </p>
            <p style={{ fontSize: '0.9rem', color: 'rgba(255,255,255,0.5)', marginTop: '2rem' }}>
              Your download should begin automatically.
            </p>
            <button 
              onClick={resetPage} 
              style={{
                marginTop: '1rem',
                background: 'transparent',
                border: '1px solid rgba(255,255,255,0.3)',
                color: 'white',
                padding: '0.5rem 1rem',
                borderRadius: '8px',
                cursor: 'pointer'
              }}
            >
              Back to Home
            </button>
          </div>
        )}
      </div>

      {/* Panic popup outside 3D flipper — iOS Safari drops animations inside preserve-3d */}
      {!flipped && (
        <div className="panic-popup-layer" aria-live="polite">
          <div className="panic-popup">
            <div className="panic-popup__header">Stop wasting time.</div>
            <div className="panic-popup__text">Save time and do productive work with VTU AIDS.</div>
          </div>
        </div>
      )}

      <div className="app-container">
        <div className={`flipper ${flipped ? 'is-flipped' : ''}`}>
          
          {/* FRONT FACE: VTU PORTAL EXPERIENCE */}
          <div className="face front">
            <div className="portal-skeleton">
              <div className="portal-topbar">
                <div className="portal-topbar__brand">
                  <span className="portal-dot"></span>
                  <span>VTU Portal</span>
                </div>
                <div className="portal-topbar__page">Intership Dairy — Edit Internship Diary Entry</div>
                <div className="portal-topbar__meta">31 Aug 2025</div>
              </div>

              <div className="manual-status">
                <div className="manual-status__label">Manually filling the VTU portal form... something is going wrong</div>
                <div className="manual-progress">
                  <div className="manual-progress__fill"></div>
                </div>
              </div>

              <div className="portal-body">
                <aside className="portal-sidebar">
                  <div className="sidebar-title">Student Dashboard</div>
                  {['Dashboard', 'Notifications', 'Profile', 'Internship Diary', 'Project'].map((item, index) => (
                    <div key={index} className="sidebar-item">
                      <div className="sidebar-icon"></div>
                      <div className="sidebar-text"></div>
                    </div>
                  ))}
                </aside>

                <main className="portal-main">
                  <div className="portal-card portal-card--header">
                    <div className="card-title"></div>
                    <div className="card-label"></div>
                  </div>

                  <div className="portal-card portal-card--content">
                    <div className="section-heading">Internship Diary Entry Details</div>
                    <div className="field-row">
                      <div className="field-block">
                        <div className="field-label"></div>
                        <div className="field-input"></div>
                      </div>
                      <div className="field-block">
                        <div className="field-label"></div>
                        <div className="field-input short"></div>
                      </div>
                    </div>

                    <div className="section-heading">What I worked on?</div>
                    <div className="text-block">
                      <div className="text-line"></div>
                      <div className="text-line wide"></div>
                      <div className="text-line medium"></div>
                      <div className="text-line full"></div>
                    </div>

                    <div className="section-heading">Hours worked</div>
                    <div className="field-input short"></div>

                    <div className="section-heading">Show Your Work (Links)</div>
                    <div className="text-block">
                      <div className="text-line"></div>
                      <div className="text-line wide"></div>
                    </div>
                  </div>
                </main>
              </div>
            </div>
          </div>

          {/* BACK FACE: THE AUTOMATED VTU AIDS WAY */}
          <div className="face back">
            <main className="main-content">
              <div className="split-layout">
                
                {/* Left Hero Section */}
                <section className="hero-section">
                  <div className="logo-wrap">
                    <img 
                      src="https://raw.githubusercontent.com/dhanushscience/VTU-AIDS/master/static/logo.png" 
                      alt="VTU AIDS Logo" 
                    />
                  </div>
                  
                  <h1>VTU AIDS</h1>
                  <p className="subtitle">
                    Automated Internship Diary System. Transform the way you write and manage day-wise internship entries using AI seamlessly after the VTU portal.
                  </p>

                  <div className="action-buttons">
                    <a 
                      href="https://github.com/dhanushscience/VTU-AIDS/releases/download/v2.0.0/VTU_AIDS_Setup.exe" 
                      className="btn btn-primary"
                      onClick={handleDownload}
                    >
                      <Download size={18} />
                      Download v2.0.0
                    </a>
                    <a href="https://github.com/dhanushscience/VTU-AIDS" className="btn btn-secondary">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path></svg>
                      GitHub
                    </a>
                  </div>

                  <div className="features-mini">
                    <div className="feature-item">
                      <div className="feature-icon"><Zap size={18} /></div>
                      <div className="feature-text">
                        <h4>Incredibly Fast</h4>
                        <p>Generate day-wise entries in seconds.</p>
                      </div>
                    </div>
                    <div className="feature-item">
                      <div className="feature-icon"><Shield size={18} /></div>
                      <div className="feature-text">
                        <h4>Local & Secure</h4>
                        <p>Data stored completely locally.</p>
                      </div>
                    </div>
                  </div>
                </section>

                {/* Right Mockup Section (Animated) */}
                <section className="mockup-container">
                  {/* Column 1 */}
                  <div className="mock-panel step-panel step-panel-1">
                    <div className="mock-header">
                      <div className="mock-icon">
                        <CalendarDays size={16} color="var(--primary-light)" />
                      </div>
                      <h3>1. Select Dates</h3>
                    </div>
                    <div className="mock-body">
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '4px', marginTop: '4px' }}>
                        {Array.from({length: 28}).map((_, i) => {
                          const isAnim = i === 14 || i === 15 || i === 16;
                          const delay = isAnim ? `${(i - 14) * 0.15}s` : '0s';
                          return (
                            <div key={i} 
                                 className={isAnim ? 'anim-date' : ''}
                                 style={{ 
                                   aspectRatio: '1', 
                                   borderRadius: '3px', 
                                   background: 'rgba(0,0,0,0.05)',
                                   opacity: 0.4,
                                   animationDelay: delay
                                 }}></div>
                          );
                        })}
                      </div>
                    </div>
                  </div>

                  {/* Column 2 */}
                  <div className="mock-panel step-panel step-panel-2">
                    <div className="mock-header">
                      <div className="mock-icon">
                        <Edit3 size={16} color="var(--primary-light)" />
                      </div>
                      <h3>2. Your Entry</h3>
                    </div>
                    <div className="mock-body">
                      <div className="skel-box" style={{ padding: '8px', height: '60px' }}>
                        <div className="skel-line anim-text" style={{ width: '40%', marginBottom: '8px', animationDelay: '2.0s' }}></div>
                        <div className="skel-line anim-text" style={{ width: '90%', marginBottom: '6px', animationDelay: '2.4s' }}></div>
                        <div className="skel-line anim-text" style={{ width: '70%', animationDelay: '2.8s' }}></div>
                      </div>
                      <div className="skel-box" style={{ padding: '8px', marginTop: '4px' }}>
                        <div className="skel-line anim-text" style={{ width: '50%', animationDelay: '3.2s' }}></div>
                      </div>
                      <div className="skel-btn anim-btn-gen" style={{ background: 'var(--primary-light)' }}>Generate with AI</div>
                    </div>
                  </div>

                  {/* Column 3 */}
                  <div className="mock-panel step-panel step-panel-3">
                    <div className="mock-header">
                      <div className="mock-icon">
                        <Bot size={16} color="var(--primary-light)" />
                      </div>
                      <h3>3. AI Entries</h3>
                    </div>
                    <div className="mock-body">
                      {[1, 2, 3].map((i) => (
                         <div key={i} className="skel-box anim-ai" style={{ padding: '8px', borderLeft: '3px solid transparent', animationDelay: `${4.0 + (i * 0.3)}s` }}>
                           <div className="skel-line" style={{ width: '30%', marginBottom: '6px', background: 'rgba(0,0,0,0.06)' }}></div>
                           <div className="skel-line" style={{ width: '100%', background: 'rgba(0,0,0,0.06)' }}></div>
                         </div>
                      ))}
                      <div className="skel-btn anim-btn-run" style={{ background: 'var(--text-light)' }}>Run automation</div>
                    </div>
                  </div>
                </section>

              </div>
            </main>

            <footer className="back-footer">
              <span>&copy; {new Date().getFullYear()} VTU AIDS</span>
              <span className="back-footer__sep">·</span>
              <span>Windows 10/11</span>
              <span className="back-footer__sep">·</span>
              <span>Not affiliated with VTU or Internyet</span>
              <span className="back-footer__sep">·</span>
              <span>Ideated by Dhanush Science</span>
            </footer>
          </div>

        </div>
      </div>
    </>
  );
}

export default App;
