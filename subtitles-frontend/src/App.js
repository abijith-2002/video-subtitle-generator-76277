import React, { useState } from "react";
import axios from "axios";

/**
 * PUBLIC_INTERFACE
 * Subtitle Generator App
 * Allows uploading a video, tracks subtitle generation, and enables downloading .srt
 */
function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [videoId, setVideoId] = useState(null);
  const [srtUrl, setSrtUrl] = useState(null);
  const [error, setError] = useState("");
  const [step, setStep] = useState(0); // 0: initial, 1: uploaded, 2: srt ready
  const [checking, setChecking] = useState(false);

  const backendUrl =
    process.env.REACT_APP_BACKEND_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

  // PUBLIC_INTERFACE
  const handleFileChange = (event) => {
    setSelectedFile(event.target.files[0]);
    setError("");
    setStep(0);
    setVideoId(null);
    setSrtUrl(null);
  };

  // PUBLIC_INTERFACE
  const handleUpload = async (event) => {
    event.preventDefault();
    if (!selectedFile) {
      setError("Please select a video file to upload.");
      return;
    }

    const data = new FormData();
    data.append("file", selectedFile);

    setUploading(true);
    setError("");
    setStep(0);

    try {
      const response = await axios.post(`${backendUrl}/upload/`, data, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setVideoId(response.data.video_id);
      setStep(1);
      // Immediately try to get subtitle (may not be ready)
      checkForSubtitle(response.data.video_id, /*isFirstCheck=*/true);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Upload failed. Ensure video format is supported and backend is running."
      );
    } finally {
      setUploading(false);
    }
  };

  // PUBLIC_INTERFACE
  // checkForSubtitle: polls if subtitle file is ready, sets SRT URL when available
  const checkForSubtitle = async (vid, isFirstCheck = false) => {
    setChecking(true);
    try {
      const resp = await axios.get(`${backendUrl}/subtitles/${vid}/`);
      setSrtUrl(`${backendUrl}${resp.data.srt_url}`);
      setStep(2);
    } catch (err) {
      if (err.response?.status === 404) {
        // Not ready yet; poll again if it's the first check or after delay
        if (isFirstCheck) {
          setTimeout(() => checkForSubtitle(vid, false), 3000);
        }
      } else {
        setError(err.response?.data?.detail || "Subtitle status check failed.");
      }
    } finally {
      setChecking(false);
    }
  };

  // PUBLIC_INTERFACE
  const handleDownload = () => {
    // Download button will fetch the SRT as a file
    if (!srtUrl || !videoId) return;
    axios
      .get(srtUrl, { responseType: "blob" })
      .then((res) => {
        const url = window.URL.createObjectURL(new Blob([res.data]));
        const a = document.createElement("a");
        a.href = url;
        a.download = `${videoId}.srt`;
        document.body.appendChild(a);
        a.click();
        a.remove();
      })
      .catch(() => setError("Failed to download subtitle file."));
  };

  const handleCheckAgain = () => {
    if (videoId) checkForSubtitle(videoId, true);
  };

  // PUBLIC_INTERFACE
  return (
    <div style={styles.container}>
      <h1>Video Subtitle Generator</h1>
      <form onSubmit={handleUpload} style={styles.form}>
        <input
          type="file"
          accept="video/*"
          onChange={handleFileChange}
          style={styles.input}
        />
        <button
          type="submit"
          disabled={uploading || !selectedFile}
          style={styles.button}
        >
          {uploading ? "Uploading..." : "Upload"}
        </button>
      </form>
      {error && <div style={styles.error}>{error}</div>}
      {step === 1 && (
        <div style={styles.info}>
          Video uploaded.<br />
          Generating subtitles...{" "}
          {!checking && (
            <button onClick={handleCheckAgain} style={styles.buttonSmall}>
              Check Again
            </button>
          )}
        </div>
      )}
      {step === 2 && (
        <div style={styles.info}>
          <span>Subtitles are ready.</span>
          <button onClick={handleDownload} style={styles.button}>
            Download .srt
          </button>
        </div>
      )}
      <footer style={styles.footer}>
        <small>
          Powered by FastAPI backend.<br />
          <span style={{ color: "#888" }}>
            Set <b>REACT_APP_BACKEND_API_URL</b> in <b>.env</b> if backend is remote.
          </span>
        </small>
      </footer>
    </div>
  );
}

const styles = {
  container: {
    maxWidth: 480,
    margin: "40px auto",
    padding: 24,
    background: "#f9f9ff",
    borderRadius: 10,
    boxShadow: "0 2px 12px rgba(10,20,80,0.13)"
  },
  form: {
    display: "flex", flexDirection: "row", gap: 8, alignItems: "center", marginBottom: 18
  },
  input: { flex: 1 },
  button: {
    padding: "8px 18px",
    background: "#4763fb",
    color: "#fff",
    border: "none",
    borderRadius: 5,
    cursor: "pointer"
  },
  buttonSmall: {
    padding: "5px 10px",
    background: "#bbb",
    color: "#222",
    border: "none",
    borderRadius: 5,
    cursor: "pointer",
    fontSize: "0.94em"
  },
  error: { color: "#b72d2d", marginBottom: 8, marginTop: 3 },
  info: { margin: 15, fontSize: "1.1em" },
  footer: { marginTop: 30, textAlign: "center", color: "#777" }
};

export default App;
