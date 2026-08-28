(() => {
  const form = document.getElementById("generate-form");
  const fileInput = document.getElementById("audio_files");
  const uploadList = document.getElementById("upload-file-list");
  const recordedList = document.getElementById("recorded-clips");
  const startBtn = document.getElementById("rec-start-btn");
  const stopBtn = document.getElementById("rec-stop-btn");
  const statusEl = document.getElementById("rec-status");
  const sourceText = document.getElementById("source_text");

  if (!form || !fileInput) return;

  const recordedClips = [];
  let mediaRecorder = null;
  let mediaStream = null;
  let chunks = [];

  function renderUploadList() {
    if (!uploadList) return;
    uploadList.innerHTML = "";
    Array.from(fileInput.files || []).forEach((file) => {
      const li = document.createElement("li");
      li.textContent = `${file.name} (${Math.round(file.size / 1024)} KB)`;
      uploadList.appendChild(li);
    });
  }

  function renderRecordedClips() {
    if (!recordedList) return;
    recordedList.innerHTML = "";
    recordedClips.forEach((clip, index) => {
      const li = document.createElement("li");
      li.className = "clip-item";

      const label = document.createElement("span");
      label.textContent = `${clip.name} (${Math.round(clip.blob.size / 1024)} KB)`;

      const playBtn = document.createElement("button");
      playBtn.type = "button";
      playBtn.className = "btn secondary small";
      playBtn.textContent = "듣기";
      playBtn.addEventListener("click", () => {
        const audio = new Audio(URL.createObjectURL(clip.blob));
        audio.play();
      });

      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "btn secondary small";
      delBtn.textContent = "삭제";
      delBtn.addEventListener("click", () => {
        recordedClips.splice(index, 1);
        renderRecordedClips();
      });

      li.append(label, playBtn, delBtn);
      recordedList.appendChild(li);
    });
  }

  function mergeFilesIntoInput() {
    const dt = new DataTransfer();
    Array.from(fileInput.files || []).forEach((file) => dt.items.add(file));
    recordedClips.forEach((clip) => {
      dt.items.add(new File([clip.blob], clip.name, { type: clip.blob.type || "audio/webm" }));
    });
    fileInput.files = dt.files;
  }

  function hasAnyInput() {
    const text = (sourceText?.value || "").trim();
    const uploads = (fileInput.files?.length || 0) > 0;
    return Boolean(text) || uploads || recordedClips.length > 0;
  }

  fileInput.addEventListener("change", renderUploadList);

  startBtn?.addEventListener("click", async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      alert("이 브라우저는 마이크 녹음을 지원하지 않습니다.");
      return;
    }
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      mediaRecorder = new MediaRecorder(mediaStream, { mimeType });
      chunks = [];
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      mediaRecorder.onstop = () => {
        const blob = new Blob(chunks, { type: mediaRecorder.mimeType || "audio/webm" });
        if (blob.size > 0) {
          recordedClips.push({
            name: `recording-${recordedClips.length + 1}.webm`,
            blob,
          });
          renderRecordedClips();
        }
        mediaStream?.getTracks().forEach((track) => track.stop());
        mediaStream = null;
        statusEl.textContent = "대기 중";
        startBtn.disabled = false;
        stopBtn.disabled = true;
      };
      mediaRecorder.start();
      statusEl.textContent = "녹음 중…";
      startBtn.disabled = true;
      stopBtn.disabled = false;
    } catch (err) {
      alert("마이크 권한이 필요합니다. 브라우저 설정에서 허용해 주세요.");
      console.error(err);
    }
  });

  stopBtn?.addEventListener("click", () => {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
  });

  form.addEventListener("submit", (event) => {
    mergeFilesIntoInput();
    if (!hasAnyInput()) {
      event.preventDefault();
      alert("텍스트, 음성 업로드, 또는 녹음 중 하나 이상을 입력하세요.");
    }
  });
})();
