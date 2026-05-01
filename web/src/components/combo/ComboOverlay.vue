<script setup lang="ts">
/**
 * ComboOverlay — fullscreen, transparent, pointer-events:none, z-index 9999.
 * Mounted once in App.vue, consumes the global combo queue, plays animations
 * batch by batch (one user at a time).
 *
 * Per batch:
 *   1. Show the user header (avatar + name) for ~600ms
 *   2. Play their events one after another, ~1100ms apiece (fade-in/peak/fade-out)
 *   3. Move to next batch (advance the queue)
 *
 * Visual style is the validated proto-combo.html: italic-skewed labels with
 * heavy black stroke, gradient fill, screen-flash on big hits, sparks burst.
 *
 * Animations are CSS keyframes — no canvas, no rAF, just transition timing.
 */
import { ref, watch, computed, nextTick } from 'vue'
import { useComboQueue, type TrackerEvent } from '@/stores/comboQueue'
import { useI18n } from 'vue-i18n'

const queue = useComboQueue()
const { t } = useI18n()

const stage = ref<'idle' | 'header' | 'events' | 'fading'>('idle')
const currentEventIdx = ref(-1)
const flashKey = ref(0)
const sparks = ref<Array<{ id: number; angle: number; dist: number; color: string }>>([])
let sparkId = 0

const currentEvent = computed<TrackerEvent | null>(() => {
  const batch = queue.current
  if (!batch) return null
  if (currentEventIdx.value < 0 || currentEventIdx.value >= batch.events.length) return null
  return batch.events[currentEventIdx.value]
})

const TRACKER_VISUAL: Record<string, { variant: string; direction: string; color: string; flash: 'soft' | 'strong' }> = {
  group:       { variant: 'group',   direction: 'from-left',  color: '#aab0ff', flash: 'soft' },
  salat:       { variant: 'salat',   direction: 'from-right', color: '#ffd000', flash: 'soft' },
  on_time:     { variant: 'on_time', direction: 'from-left',  color: '#5ae0ff', flash: 'soft' },
  fire:        { variant: 'fire',    direction: 'from-right', color: '#ff7f3f', flash: 'strong' },
  perfect_day: { variant: 'perfect', direction: 'from-top',   color: '#ffeb3b', flash: 'strong' },
}

const labelText = computed(() => {
  const ev = currentEvent.value
  if (!ev) return ''
  if (ev.action === 'broken') return t(`trackers.${ev.tracker_id}.broken`)
  return t(`trackers.${ev.tracker_id}.combo`, { n: ev.combo })
})
const labelVariant = computed(() => {
  const ev = currentEvent.value
  if (!ev) return 'salat'
  if (ev.action === 'broken') return 'broken'
  return TRACKER_VISUAL[ev.tracker_id]?.variant ?? 'salat'
})
const labelDirection = computed(() => {
  const ev = currentEvent.value
  if (!ev || ev.action === 'broken') return 'from-top'
  return TRACKER_VISUAL[ev.tracker_id]?.direction ?? 'from-right'
})
const isHuge = computed(() => {
  const ev = currentEvent.value
  return ev?.tracker_id === 'fire' || ev?.tracker_id === 'perfect_day'
})

watch(() => queue.current, async (batch) => {
  if (!batch) {
    stage.value = 'idle'
    currentEventIdx.value = -1
    return
  }
  stage.value = 'header'
  currentEventIdx.value = -1
  await wait(700)
  await playEvents(batch.events)
  stage.value = 'fading'
  await wait(250)
  queue.done()
})

async function playEvents(events: TrackerEvent[]) {
  stage.value = 'events'
  for (let i = 0; i < events.length; i++) {
    currentEventIdx.value = i
    const ev = events[i]
    const visual = TRACKER_VISUAL[ev.tracker_id]
    if (visual && ev.action === 'increment') {
      flashKey.value++
      spawnSparks(visual.color, ev.tracker_id === 'fire' || ev.tracker_id === 'perfect_day' ? 14 : 8)
    }
    // animation lasts ~1100ms total
    await wait(1100)
  }
  currentEventIdx.value = -1
}

function spawnSparks(color: string, count: number) {
  const newSparks = Array.from({ length: count }, () => ({
    id: ++sparkId,
    angle: Math.random() * Math.PI * 2,
    dist: 80 + Math.random() * 60,
    color,
  }))
  sparks.value.push(...newSparks)
  setTimeout(() => {
    const ids = new Set(newSparks.map((s) => s.id))
    sparks.value = sparks.value.filter((s) => !ids.has(s.id))
  }, 700)
}

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

const flashStrong = computed(() => {
  const ev = currentEvent.value
  if (!ev || ev.action === 'broken') return false
  return TRACKER_VISUAL[ev.tracker_id]?.flash === 'strong'
})
</script>

<template>
  <div class="combo-overlay" v-if="!queue.isIdle">
    <!-- Screen flash on each event -->
    <div
      :key="flashKey"
      v-if="currentEvent && currentEvent.action === 'increment'"
      :class="['combo-flash', flashStrong ? 'flash-strong' : 'flash-soft']"
    />

    <!-- User header -->
    <Transition name="combo-header">
      <div v-if="queue.current && stage !== 'idle'" class="combo-user">
        <span class="combo-user-emoji">{{ queue.current.user.emoji }}</span>
        <span class="combo-user-name">{{ queue.current.user.name }}</span>
      </div>
    </Transition>

    <!-- The combo label -->
    <Transition name="combo-label" :key="`${queue.current?.user.id}-${currentEventIdx}`">
      <div
        v-if="currentEvent"
        :class="['combo-label', `variant-${labelVariant}`, `direction-${labelDirection}`, { huge: isHuge }]"
      >{{ labelText }}</div>
    </Transition>

    <!-- Sparks -->
    <div
      v-for="s in sparks"
      :key="s.id"
      class="combo-spark"
      :style="{
        '--angle': `${s.angle}rad`,
        '--dist': `${s.dist}px`,
        color: s.color,
      } as any"
    />
  </div>
</template>

<style scoped>
.combo-overlay {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 9999;
  overflow: hidden;
  /* Hard clip — labels can never spill outside the viewport, even mid-overshoot. */
  contain: strict;
}

/* ---- User header ---- */
.combo-user {
  position: absolute;
  top: 24%;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.combo-user-emoji {
  font-size: 4rem;
  filter: drop-shadow(0 4px 12px rgba(0,0,0,0.5));
}
.combo-user-name {
  font-family: 'Russo One', sans-serif;
  font-size: 1.4rem;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: #fff;
  -webkit-text-stroke: 2px #000;
  paint-order: stroke fill;
  text-shadow: 0 4px 14px rgba(0,0,0,0.7);
}

.combo-header-enter-active { animation: headerIn 400ms cubic-bezier(.18,.89,.32,1.28); }
.combo-header-leave-active { animation: headerOut 250ms ease-in; }
@keyframes headerIn {
  from { transform: translateX(-50%) scale(0.4); opacity: 0; }
  60%  { transform: translateX(-50%) scale(1.12); }
  to   { transform: translateX(-50%) scale(1); opacity: 1; }
}
@keyframes headerOut {
  to { transform: translateX(-50%) scale(0.8); opacity: 0; }
}

/* ---- Combo label (the star) ---- */
.combo-label {
  position: absolute;
  top: 44%;
  left: 50%;
  font-family: 'Bowlby One SC', 'Russo One', sans-serif;
  font-size: clamp(1.3rem, 3.6vw, 2.6rem);
  font-style: italic;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  text-align: center;
  /* Wrap onto 2 lines instead of bleeding off the side on narrow screens. */
  white-space: normal;
  word-break: keep-all;
  line-height: 1.05;
  /* Stay safely inside the viewport even at peak overshoot scale. */
  max-width: min(80vw, 38ch);
  padding: 0 8px;
  -webkit-text-stroke: 3px #000;
  paint-order: stroke fill;
  text-shadow:
    0 0 18px currentColor,
    0 4px 0 rgba(0,0,0,0.55),
    0 8px 22px rgba(0,0,0,0.8);
}
.combo-label.huge {
  font-size: clamp(1.6rem, 4.8vw, 3.6rem);
  max-width: min(85vw, 42ch);
}

/* Variant gradient fills */
.combo-label.variant-salat {
  background: linear-gradient(180deg, #fff700 0%, #ffd000 50%, #ff6a00 100%);
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
}
.combo-label.variant-group {
  background: linear-gradient(180deg, #b3b8ff 0%, #6a5cff 50%, #00c2ff 100%);
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
}
.combo-label.variant-on_time {
  background: linear-gradient(180deg, #d4ffff 0%, #5ae0ff 50%, #00a5d9 100%);
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
}
.combo-label.variant-fire {
  background: linear-gradient(180deg, #ffeb3b 0%, #ff7f3f 50%, #d62828 100%);
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
}
.combo-label.variant-perfect {
  background: linear-gradient(180deg, #ffffff 0%, #ffeb3b 40%, #ff8a00 100%);
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
}
.combo-label.variant-broken {
  color: #888;
  -webkit-text-stroke: 3px #2a2a2a;
  filter: grayscale(0.8);
  opacity: 0.85;
}

/* Entry direction = enter-active animation */
.combo-label-enter-active.direction-from-right {
  animation: labelFromRight 1100ms cubic-bezier(.18,.89,.32,1.28);
}
.combo-label-enter-active.direction-from-left {
  animation: labelFromLeft 1100ms cubic-bezier(.18,.89,.32,1.28);
}
.combo-label-enter-active.direction-from-top {
  animation: labelFromTop 1100ms cubic-bezier(.18,.89,.32,1.28);
}
.combo-label-leave-active { animation: labelLeave 200ms ease-in; }

@keyframes labelFromRight {
  0%   { transform: translate(calc(-50% + 280px), 0) scale(0.4) rotate(-5deg); opacity: 0; filter: blur(14px); }
  30%  { transform: translate(-50%, 0) scale(1.12) rotate(-5deg); opacity: 1; filter: blur(0); }
  38%  { transform: translate(-50%, 0) scale(1.12) rotate(-5deg); }
  50%  { transform: translate(-50%, 0) scale(0.92) rotate(-5deg); }
  60%  { transform: translate(-50%, 0) scale(1.05) rotate(-5deg); }
  72%  { transform: translate(-50%, 0) scale(1) rotate(-5deg); opacity: 1; }
  100% { transform: translate(-50%, -40px) scale(0.9) rotate(-5deg); opacity: 0; }
}
@keyframes labelFromLeft {
  0%   { transform: translate(calc(-50% - 280px), 0) scale(0.4) rotate(4deg); opacity: 0; filter: blur(14px); }
  30%  { transform: translate(-50%, 0) scale(1.12) rotate(4deg); opacity: 1; filter: blur(0); }
  38%  { transform: translate(-50%, 0) scale(1.12) rotate(4deg); }
  50%  { transform: translate(-50%, 0) scale(0.92) rotate(4deg); }
  60%  { transform: translate(-50%, 0) scale(1.05) rotate(4deg); }
  72%  { transform: translate(-50%, 0) scale(1) rotate(4deg); opacity: 1; }
  100% { transform: translate(-50%, -40px) scale(0.9) rotate(4deg); opacity: 0; }
}
@keyframes labelFromTop {
  0%   { transform: translate(-50%, -280px) scale(0.3) rotate(-5deg); opacity: 0; filter: blur(14px); }
  26%  { transform: translate(-50%, 30px) scale(1.2) rotate(-5deg); opacity: 1; filter: blur(0); }
  34%  { transform: translate(-50%, 30px) scale(1.2) rotate(-5deg); }
  46%  { transform: translate(-50%, 0) scale(0.9) rotate(-5deg); }
  58%  { transform: translate(-50%, 0) scale(1.08) rotate(-5deg); }
  72%  { transform: translate(-50%, 0) scale(1) rotate(-5deg); opacity: 1; }
  100% { transform: translate(-50%, -60px) scale(0.85) rotate(-5deg); opacity: 0; }
}
@keyframes labelLeave {
  to { opacity: 0; }
}

/* ---- Screen flash ---- */
.combo-flash {
  position: absolute;
  inset: 0;
  background: white;
  opacity: 0;
  pointer-events: none;
}
.combo-flash.flash-soft   { animation: flashSoft 200ms ease-out; }
.combo-flash.flash-strong { animation: flashStrong 320ms ease-out; }
@keyframes flashSoft {
  0%, 100% { opacity: 0; }
  20%      { opacity: 0.18; }
}
@keyframes flashStrong {
  0%, 100% { opacity: 0; }
  15%      { opacity: 0.45; }
}

/* ---- Sparks ---- */
.combo-spark {
  position: absolute;
  top: 42%; left: 50%;
  width: 10px; height: 10px;
  background: currentColor;
  transform: translate(-50%, -50%) rotate(45deg);
  box-shadow: 0 0 10px currentColor;
  animation: sparkFly 600ms cubic-bezier(.2,.7,.3,1) forwards;
  pointer-events: none;
}
@keyframes sparkFly {
  0%   { transform: translate(-50%, -50%) rotate(45deg) scale(1); opacity: 1; }
  100% {
    transform:
      translate(-50%, -50%)
      translate(calc(cos(var(--angle)) * var(--dist)), calc(sin(var(--angle)) * var(--dist)))
      rotate(135deg) scale(0);
    opacity: 0;
  }
}
</style>
