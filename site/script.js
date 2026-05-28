const demoConsole = document.querySelector("[data-demo-console]");
const demoStatus = document.querySelector("[data-demo-status]");
const demoMessage = document.querySelector("[data-demo-message]");
const armDemoButton = document.querySelector("[data-arm-demo]");
const stopDemoButton = document.querySelector("[data-stop-demo]");
const demoPlayer = document.querySelector(".demo-player");

let demoState = "idle";
let armedAt = 0;
let alarmTimer = 0;
let audioContext;

function setDemoState(state, message) {
  demoState = state;
  demoConsole?.classList.toggle("armed", state === "armed");
  demoConsole?.classList.toggle("alarming", state === "alarming");

  if (demoStatus) {
    demoStatus.textContent = state === "armed" ? "Demo armed" : state === "alarming" ? "Kunju alarm active" : "Demo idle";
  }

  if (demoMessage) {
    demoMessage.textContent = message;
  }
}

function getAudioContext() {
  audioContext ||= new AudioContext();
  return audioContext;
}

function playKunjuPulse() {
  const context = getAudioContext();
  const now = context.currentTime;
  const gain = context.createGain();
  gain.connect(context.destination);
  gain.gain.setValueAtTime(0.0001, now);
  gain.gain.exponentialRampToValueAtTime(0.32, now + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.34);

  [360, 520, 760].forEach((frequency, index) => {
    const oscillator = context.createOscillator();
    oscillator.type = index === 1 ? "square" : "sawtooth";
    oscillator.frequency.setValueAtTime(frequency, now);
    oscillator.frequency.exponentialRampToValueAtTime(frequency * 1.28, now + 0.18);
    oscillator.connect(gain);
    oscillator.start(now + index * 0.035);
    oscillator.stop(now + 0.34 + index * 0.035);
  });
}

function startAlarm() {
  if (demoState !== "armed" || Date.now() < armedAt) {
    return;
  }

  setDemoState("alarming", "Sairam! Sairam! Kunju caught the touch.");
  playKunjuPulse();
  alarmTimer = window.setInterval(playKunjuPulse, 620);
}

function stopAlarm() {
  window.clearInterval(alarmTimer);
  alarmTimer = 0;
  setDemoState("idle", "Kunju is waiting for your command.");
}

armDemoButton?.addEventListener("click", () => {
  window.clearInterval(alarmTimer);
  armedAt = Date.now() + 1200;
  setDemoState("armed", "Arming... move, tap, or press a key after one second.");

  window.setTimeout(() => {
    if (demoState === "armed") {
      setDemoState("armed", "Kunju is watching. Touch the page to trigger the alarm.");
    }
  }, 1200);
});

stopDemoButton?.addEventListener("click", stopAlarm);

demoPlayer?.addEventListener("click", () => {
  demoPlayer.classList.add("alarming");
  playKunjuPulse();
  window.setTimeout(() => demoPlayer.classList.remove("alarming"), 900);
});

["pointerdown", "mousemove", "keydown", "touchstart"].forEach((eventName) => {
  window.addEventListener(eventName, (event) => {
    const target = event.target;
    const isControl = target instanceof Element && target.closest("[data-arm-demo], [data-stop-demo], a, button");
    if (isControl) {
      return;
    }
    startAlarm();
  }, { passive: true });
});
