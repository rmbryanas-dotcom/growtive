let socket;
let pomodoroInterval = null;
let pomodoroSeconds = 25 * 60;
let pomodoroMode = "focus";

function initSocketIO(roomId) {
  if (typeof io === "undefined") return;
  socket = io();

  socket.on("connect", function () {
    socket.emit("join", { room_id: roomId });
  });

  socket.on("new_message", function (data) {
    appendChatMessage(data.user_name, data.content, data.timestamp);
  });

  const form = document.getElementById("chat-form");
  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      const input = document.getElementById("chat-input");
      const text = input.value.trim();
      if (!text) return;
      socket.emit("send_message", { room_id: roomId, message: text });
      input.value = "";
    });
  }
}

function appendChatMessage(user, content, timestamp) {
  const box = document.getElementById("chat-box");
  if (!box) return;
  const div = document.createElement("div");
  div.className = "chat-message";
  div.innerHTML =
    '<span class="user">' +
    user +
    "</span> <span class='text-muted'>[" +
    timestamp +
    "]</span>: " +
    content;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function formatTime(sec) {
  const m = Math.floor(sec / 60)
    .toString()
    .padStart(2, "0");
  const s = (sec % 60).toString().padStart(2, "0");
  return m + ":" + s;
}

function updatePomodoroDisplay() {
  const display = document.getElementById("pomodoro-display");
  const label = document.getElementById("pomodoro-label");
  if (!display || !label) return;
  display.textContent = formatTime(pomodoroSeconds);
  label.textContent = pomodoroMode === "focus" ? "Fokus" : "Istirahat";
}

function startPomodoro() {
  if (pomodoroInterval) return;
  pomodoroInterval = setInterval(() => {
    pomodoroSeconds--;
    if (pomodoroSeconds <= 0) {
      if (pomodoroMode === "focus") {
        pomodoroMode = "break";
        pomodoroSeconds = 5 * 60;
        alert("🎉 Fokus 25 menit selesai! Saatnya istirahat 5 menit.");
      } else {
        pomodoroMode = "focus";
        pomodoroSeconds = 25 * 60;
    alert("⏰ Istirahat selesai! Ayo mulai fokus lagi 25 menit.");
      }
    }
    updatePomodoroDisplay();
  }, 1000);
}

function pausePomodoro() {
  if (pomodoroInterval) {
    clearInterval(pomodoroInterval);
    pomodoroInterval = null;
  }
}

function resetPomodoro() {
  pausePomodoro();
  pomodoroMode = "focus";
  pomodoroSeconds = 25 * 60;
  updatePomodoroDisplay();
}
