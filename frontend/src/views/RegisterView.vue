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
      <div class="auth-card" :class="{ shake: shaking }">
        <div class="card-eyebrow animate-field" style="--delay: 0.1s">Get started</div>
        <h1 class="animate-field" style="--delay: 0.2s">Create your account</h1>
        <p class="subtitle animate-field" style="--delay: 0.3s">Join Axelo and start tracking in minutes</p>

        <transition name="error-pop">
          <div v-if="error" class="error-msg"><span class="error-icon">⚠</span> {{ error }}</div>
        </transition>

        <div class="form-group animate-field" style="--delay: 0.35s">
          <label class="fd-label" :class="{ 'label-active': nameFocused || name }">Full name</label>
          <div class="input-wrap" :class="{ focused: nameFocused, filled: name }">
            <span class="input-icon">👤</span>
            <input v-model="name" type="text" class="fd-input" placeholder="Alex Chen"
              @focus="nameFocused = true" @blur="nameFocused = false" @keyup.enter="submit" />
          </div>
        </div>

        <div class="form-group animate-field" style="--delay: 0.42s">
          <label class="fd-label" :class="{ 'label-active': emailFocused || email }">Email address</label>
          <div class="input-wrap" :class="{ focused: emailFocused, filled: email }">
            <span class="input-icon">✉</span>
            <input v-model="email" type="email" class="fd-input" placeholder="you@company.com"
              @focus="emailFocused = true" @blur="emailFocused = false" @keyup.enter="submit" />
          </div>
        </div>

        <div class="form-group animate-field" style="--delay: 0.49s">
          <label class="fd-label" :class="{ 'label-active': passFocused || password }">Password</label>
          <div class="input-wrap" :class="{ focused: passFocused, filled: password }">
            <span class="input-icon">🔒</span>
            <input v-model="password" :type="showPass ? 'text' : 'password'" class="fd-input"
              placeholder="Min. 8 characters, include a number"
              @focus="passFocused = true" @blur="passFocused = false" @keyup.enter="submit" />
            <button class="toggle-pass" @click="showPass = !showPass" type="button" tabindex="-1">
              {{ showPass ? '🙈' : '👁' }}
            </button>
          </div>
          <div class="strength-bar">
            <div class="strength-fill" :class="`strength-${passwordStrength.level}`" :style="`width:${passwordStrength.pct}%`"></div>
          </div>
          <div v-if="password" class="strength-label" :class="`strength-text-${passwordStrength.level}`">{{ passwordStrength.label }}</div>
        </div>

        <button class="btn-main animate-field" style="--delay: 0.56s" :disabled="loading" @click="submit">
          <span v-if="!loading" class="btn-text">Create account →</span>
          <span v-else class="btn-loader">
            <span class="dot-1"></span><span class="dot-2"></span><span class="dot-3"></span>
          </span>
        </button>

        <p class="auth-switch animate-field" style="--delay: 0.63s">
          Already have an account? <router-link to="/login">Sign in</router-link>
        </p>
      </div>
    </div>
  </div>

  <transition name="modal-pop">
    <div v-if="registered" class="check-email-overlay">
      <div class="check-email-card">
        <div class="check-email-icon">📧</div>
        <h2 class="check-email-title">Check your inbox</h2>
        <p class="check-email-sub">We sent a verification link to<br><strong>{{ registeredEmail }}</strong></p>
        <p class="check-email-hint">Click the link in the email to activate your account. The link expires in 24 hours.</p>
        <router-link to="/login" class="btn-login-link">Go to Login →</router-link>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'

const router = useRouter()
const auth   = useAuthStore()

const name     = ref('')
const email    = ref('')
const password = ref('')
const loading  = ref(false)
const error    = ref('')
const shaking  = ref(false)
const showPass = ref(false)
const nameFocused  = ref(false)
const emailFocused = ref(false)
const passFocused  = ref(false)
const registered      = ref(false)
const registeredEmail = ref('')

const passwordStrength = computed(() => {
  const p = password.value
  if (!p) return { level: 0, pct: 0, label: '' }
  let score = 0
  if (p.length >= 8)           score++
  if (p.length >= 12)          score++
  if (/[A-Z]/.test(p))         score++
  if (/[0-9]/.test(p))         score++
  if (/[^A-Za-z0-9]/.test(p)) score++
  if (score <= 1) return { level: 'weak',   pct: 25,  label: 'Weak — add numbers or symbols' }
  if (score <= 2) return { level: 'fair',   pct: 50,  label: 'Fair' }
  if (score <= 3) return { level: 'good',   pct: 75,  label: 'Good' }
  return               { level: 'strong', pct: 100, label: 'Strong' }
})

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

function validate() {
  if (!name.value.trim())                { error.value = 'Please enter your full name.'; return false }
  if (!EMAIL_RE.test(email.value.trim())) { error.value = 'Please enter a valid email address.'; return false }
  if (password.value.length < 8)         { error.value = 'Password must be at least 8 characters.'; return false }
  if (!/[0-9]/.test(password.value))     { error.value = 'Password must contain at least one number.'; return false }
  if (!/[A-Za-z]/.test(password.value))  { error.value = 'Password must contain at least one letter.'; return false }
  return true
}

async function submit() {
  error.value = ''
  if (!validate()) { triggerShake(); return }

  loading.value = true
  try {
    const user = await auth.register({
      full_name: name.value.trim(),
      email:     email.value.trim().toLowerCase(),
      password:  password.value,
    })

    if (user?.email_verified === false) {
      registeredEmail.value = email.value.trim()
      registered.value = true
    } else {
      // Auto-login after successful registration
      await auth.login(email.value.trim().toLowerCase(), password.value)
      router.push('/')
    }
  } catch (e) {
    const raw    = e?.response?.data?.detail
    const status = e?.response?.status
    const detail = Array.isArray(raw) ? raw.map(d => d.msg || d).join(', ') : (raw || '')

    if (detail === 'Email already registered') {
      error.value = 'This email is already registered. Try signing in instead.'
    } else if (status === 422 || detail.toLowerCase().includes('password')) {
      error.value = detail || 'Password does not meet requirements (min 8 chars, must include a letter and number).'
    } else if (status === 429) {
      error.value = 'Too many attempts. Please wait a moment and try again.'
    } else if (status >= 500) {
      error.value = 'Server error. Please try again in a moment.'
    } else {
      error.value = detail || 'Registration failed. Please try again.'
    }
    triggerShake()
  } finally {
    loading.value = false
  }
}

function triggerShake() {
  shaking.value = true
  setTimeout(() => { shaking.value = false }, 600)
}
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
@keyframes pillIn { from { opacity: 0; transform: translateY(10px) scale(0.96); } to { opacity: 1; transform: translateY(0) scale(1); } }
.pill .dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.auth-footer { font-size: 0.78rem; color: var(--text3); position: relative; z-index: 1; }
.auth-right { display: flex; align-items: center; justify-content: center; padding: 2rem; background: var(--bg); }
.auth-card { width: 100%; max-width: 400px; animation: cardSlideIn 0.5s cubic-bezier(0.22, 1, 0.36, 1) both; }
@keyframes cardSlideIn { from { opacity: 0; transform: translateY(24px); } to { opacity: 1; transform: translateY(0); } }
.auth-card.shake { animation: shake 0.5s cubic-bezier(0.36, 0.07, 0.19, 0.97); }
@keyframes shake { 10%, 90% { transform: translateX(-3px); } 20%, 80% { transform: translateX(5px); } 30%, 50%, 70% { transform: translateX(-5px); } 40%, 60% { transform: translateX(5px); } 100% { transform: translateX(0); } }
.card-eyebrow { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--green); margin-bottom: 0.4rem; }
.auth-card h1 { font-family: var(--font-display); font-size: 1.9rem; font-weight: 800; letter-spacing: -0.035em; color: var(--text); margin-bottom: 0.35rem; line-height: 1.1; }
.subtitle { font-size: 0.88rem; color: var(--text2); margin-bottom: 2rem; }
.animate-field { opacity: 0; animation: fieldIn 0.45s ease forwards; animation-delay: var(--delay, 0s); }
@keyframes fieldIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
.animate-fade-down { animation: fadeDown 0.6s ease both; }
@keyframes fadeDown { from { opacity: 0; transform: translateY(-16px); } to { opacity: 1; transform: translateY(0); } }
.animate-fade-up { opacity: 0; animation: fadeUp 0.6s ease forwards; animation-delay: var(--delay, 0.2s); }
@keyframes fadeUp { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }
.error-msg { display: flex; align-items: center; gap: 8px; background: rgba(255,79,106,0.1); border: 1px solid rgba(255,79,106,0.3); border-radius: 8px; padding: 10px 14px; font-size: 0.82rem; color: var(--red); margin-bottom: 1.1rem; }
.error-pop-enter-active { animation: errorIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); }
.error-pop-leave-active { animation: errorIn 0.2s reverse ease; }
@keyframes errorIn { from { opacity: 0; transform: scale(0.95) translateY(-6px); } to { opacity: 1; transform: scale(1) translateY(0); } }
.form-group { margin-bottom: 1.1rem; }
.fd-label { display: block; font-size: 0.78rem; font-weight: 600; color: var(--text2); margin-bottom: 6px; transition: color 0.2s; }
.fd-label.label-active { color: var(--accent2); }
.input-wrap { display: flex; align-items: center; gap: 8px; border: 1.5px solid var(--border2); border-radius: 10px; background: var(--bg2); padding: 0 12px; transition: border-color 0.2s, box-shadow 0.2s; }
.input-wrap.focused { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(16,185,129,0.18); }
.input-wrap.filled:not(.focused) { border-color: rgba(16,185,129,0.3); }
.input-icon { font-size: 0.85rem; opacity: 0.5; flex-shrink: 0; }
.fd-input { flex: 1; padding: 11px 0; border: none; outline: none; background: transparent; color: var(--text); font-size: 0.9rem; font-family: var(--font-body); }
.toggle-pass { background: none; border: none; cursor: pointer; padding: 0; font-size: 0.85rem; opacity: 0.5; transition: opacity 0.15s; }
.toggle-pass:hover { opacity: 1; }
.strength-bar { height: 3px; background: var(--bg3); border-radius: 2px; margin-top: 6px; overflow: hidden; }
.strength-fill { height: 100%; border-radius: 2px; transition: width 0.3s ease, background 0.3s ease; }
.strength-weak   { background: var(--red); }
.strength-fair   { background: var(--orange); }
.strength-good   { background: var(--yellow); }
.strength-strong { background: var(--green); }
.strength-label { font-size: 0.7rem; margin-top: 3px; font-weight: 500; }
.strength-text-weak   { color: var(--red); }
.strength-text-fair   { color: var(--orange); }
.strength-text-good   { color: var(--yellow); }
.strength-text-strong { color: var(--green); }
.btn-main { width: 100%; padding: 13px; background: var(--accent); color: #fff; border: none; border-radius: 10px; font-family: var(--font-display); font-size: 0.9rem; font-weight: 700; cursor: pointer; margin-top: 0.5rem; box-shadow: 0 4px 20px rgba(16,185,129,0.3); transition: transform 0.15s, box-shadow 0.2s, opacity 0.15s; display: flex; align-items: center; justify-content: center; min-height: 46px; }
.btn-main:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 8px 28px rgba(16,185,129,0.5); }
.btn-main:active:not(:disabled) { transform: translateY(0); }
.btn-main:disabled { opacity: 0.55; cursor: not-allowed; }
.btn-loader { display: flex; gap: 5px; align-items: center; }
.btn-loader span { width: 7px; height: 7px; border-radius: 50%; background: #fff; animation: bounce 0.8s ease-in-out infinite; }
.dot-2 { animation-delay: 0.15s !important; } .dot-3 { animation-delay: 0.3s !important; }
@keyframes bounce { 0%, 60%, 100% { transform: translateY(0); opacity: 0.6; } 30% { transform: translateY(-7px); opacity: 1; } }
.auth-switch { text-align: center; margin-top: 1.25rem; font-size: 0.85rem; color: var(--text2); }
.auth-switch a { color: var(--accent2); font-weight: 500; text-decoration: none; }
.auth-switch a:hover { text-decoration: underline; }
.check-email-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 100; backdrop-filter: blur(4px); }
.check-email-card { background: var(--bg2); border: 1px solid var(--border); border-radius: 16px; padding: 2.5rem 2rem; max-width: 380px; width: 90%; text-align: center; box-shadow: 0 24px 80px rgba(0,0,0,0.5); }
.check-email-icon { font-size: 2.5rem; margin-bottom: 0.75rem; }
.check-email-title { margin: 0 0 0.75rem; font-size: 1.25rem; font-weight: 800; color: var(--text); }
.check-email-sub { font-size: 0.9rem; color: var(--text3); line-height: 1.5; margin: 0 0 0.75rem; }
.check-email-sub strong { color: var(--text); }
.check-email-hint { font-size: 0.8rem; color: var(--text3); line-height: 1.5; margin: 0 0 1.25rem; }
.btn-login-link { display: inline-block; padding: 10px 24px; background: linear-gradient(135deg, #10b981, #06b6d4); color: #fff; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 0.88rem; }
@media (max-width: 640px) { .auth-screen { grid-template-columns: 1fr; } .auth-left { display: none; } }
</style>
