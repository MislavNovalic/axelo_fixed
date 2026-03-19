<template>
  <div class="auth-screen">
    <div class="auth-left">
      <div class="grid-texture"></div>
      <div class="auth-logo animate-fade-down">
        <div class="logo-mark">A</div>
        <span class="logo-name">Axelo</span>
      </div>
      <div class="auth-hero animate-fade-up">
        <h2>Your team's<br /><span>command centre.</span></h2>
        <p>Track issues, run sprints, and ship faster — all in one open-source platform your team actually wants to use.</p>
        <div class="feature-pills">
          <div class="pill" style="--delay: 0.5s"><span class="dot" style="background:#10b981"></span> Free forever</div>
          <div class="pill" style="--delay: 0.65s"><span class="dot" style="background:#00d97e"></span> Self-host or cloud</div>
          <div class="pill" style="--delay: 0.8s"><span class="dot" style="background:#ff8c42"></span> No per-seat pricing</div>
          <div class="pill" style="--delay: 0.95s"><span class="dot" style="background:#ffd166"></span> MIT licensed</div>
        </div>
      </div>
      <div class="auth-footer animate-fade-up" style="--delay: 0.3s">Open source · MIT License · Built with FastAPI + Vue 3</div>
    </div>

    <div class="auth-right">
      <div class="auth-card animate-slide-in">
        <div class="closed-icon">🔒</div>
        <div class="card-eyebrow">Registration</div>
        <h1>Registrations are<br/><span>currently closed</span></h1>
        <p class="subtitle">New account creation is temporarily disabled while we set up email verification. Check back soon!</p>

        <div class="info-box">
          <div class="info-row">
            <span class="info-dot"></span>
            <span>If you already have an account, you can sign in below.</span>
          </div>
          <div class="info-row">
            <span class="info-dot"></span>
            <span>Demo credentials: <code>alex@axelo.dev</code> / <code>password123</code></span>
          </div>
        </div>

        <router-link to="/login" class="btn-main">← Go to Sign In</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
</script>

<style scoped>
.auth-screen { min-height: 100vh; display: grid; grid-template-columns: 1fr 1fr; }
.auth-left { background: var(--bg2); border-right: 1px solid var(--border); display: flex; flex-direction: column; justify-content: space-between; padding: 2.5rem; position: relative; overflow: hidden; }
.auth-left::before { content: ''; position: absolute; inset: 0; pointer-events: none; background: linear-gradient(135deg, rgba(16,185,129,0.12) 0%, transparent 60%), radial-gradient(ellipse at 20% 80%, rgba(0,217,126,0.06) 0%, transparent 60%); }
.grid-texture { position: absolute; inset: 0; pointer-events: none; background-image: linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px); background-size: 40px 40px; }
.auth-logo { display: flex; align-items: center; gap: 10px; position: relative; z-index: 1; }
.logo-mark { width: 36px; height: 36px; background: var(--accent); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-family: var(--font-display); font-weight: 800; font-size: 18px; color: #fff; box-shadow: 0 0 24px var(--accent-glow); animation: logoPulse 3s ease-in-out infinite; }
@keyframes logoPulse { 0%, 100% { box-shadow: 0 0 16px var(--accent-glow); } 50% { box-shadow: 0 0 32px var(--accent-glow), 0 0 8px rgba(16,185,129,0.4); } }
.logo-name { font-family: var(--font-display); font-size: 1.2rem; font-weight: 700; letter-spacing: -0.02em; color: var(--text); }
.auth-hero { position: relative; z-index: 1; }
.auth-hero h2 { font-family: var(--font-display); font-size: 2.6rem; font-weight: 800; line-height: 1.1; letter-spacing: -0.04em; color: var(--text); margin-bottom: 1rem; }
.auth-hero h2 span { color: var(--green); }
.auth-hero p { font-size: 0.95rem; color: var(--text2); line-height: 1.6; max-width: 320px; }
.feature-pills { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 1.5rem; }
.pill { display: flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 100px; background: rgba(255,255,255,0.05); border: 1px solid var(--border); font-size: 0.78rem; color: var(--text2); opacity: 0; animation: pillIn 0.5s ease forwards; animation-delay: var(--delay, 0s); }
@keyframes pillIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
.pill .dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.auth-footer { font-size: 0.78rem; color: var(--text3); position: relative; z-index: 1; }

.auth-right { display: flex; align-items: center; justify-content: center; padding: 2rem; background: var(--bg); }
.auth-card { width: 100%; max-width: 420px; background: var(--bg2); border: 1px solid var(--border); border-radius: 20px; padding: 2.5rem; box-shadow: 0 24px 48px rgba(0,0,0,0.2); text-align: center; }
.animate-slide-in { animation: slideIn 0.5s cubic-bezier(0.22, 1, 0.36, 1) both; }
@keyframes slideIn { from { opacity: 0; transform: translateY(24px); } to { opacity: 1; transform: translateY(0); } }

.closed-icon { font-size: 2.5rem; margin-bottom: 1rem; }
.card-eyebrow { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--accent2); margin-bottom: 0.4rem; }
.auth-card h1 { font-family: var(--font-display); font-size: 1.8rem; font-weight: 800; letter-spacing: -0.03em; color: var(--text); margin-bottom: 0.75rem; line-height: 1.15; }
.auth-card h1 span { color: var(--orange, #ff8c42); }
.subtitle { font-size: 0.88rem; color: var(--text2); line-height: 1.6; margin-bottom: 1.75rem; }

.info-box { background: rgba(16,185,129,0.06); border: 1px solid rgba(16,185,129,0.2); border-radius: 10px; padding: 1rem 1.2rem; margin-bottom: 1.75rem; text-align: left; display: flex; flex-direction: column; gap: 0.6rem; }
.info-row { display: flex; align-items: flex-start; gap: 10px; font-size: 0.83rem; color: var(--text2); line-height: 1.5; }
.info-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); flex-shrink: 0; margin-top: 6px; }
code { font-family: var(--font-mono, monospace); font-size: 0.8rem; background: rgba(255,255,255,0.07); padding: 1px 5px; border-radius: 4px; color: var(--text); }

.btn-main { display: flex; align-items: center; justify-content: center; width: 100%; padding: 13px; background: var(--accent); color: #fff; border: none; border-radius: 10px; font-family: var(--font-display); font-size: 0.9rem; font-weight: 700; cursor: pointer; box-shadow: 0 4px 20px rgba(16,185,129,0.3); transition: transform 0.15s, box-shadow 0.2s; text-decoration: none; }
.btn-main:hover { transform: translateY(-2px); box-shadow: 0 8px 28px rgba(16,185,129,0.5); }

@media (max-width: 640px) { .auth-screen { grid-template-columns: 1fr; } .auth-left { display: none; } }
</style>
