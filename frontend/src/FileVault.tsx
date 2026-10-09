import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, checkScan, deleteFile, downloadFile, listFiles, uploadFile, type VaultFile } from "./api";

// keep in sync with ALLOWED_MAX_SIZE in main.py; the backend still enforces it
const MAX_SIZE = 10 * 1024 * 1024;

interface Props {
  token: string;
  onUnauthorized: () => void;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// the backend stores UTC times without a timezone, so add the "Z" before parsing
function formatDate(utc: string): string {
  return new Date(`${utc}Z`).toLocaleString();
}

function scanStatus(result: string | null): { label: string; tone: string } {
  if (!result) return { label: "Not scanned", tone: "neutral" };
  if (result.startsWith("pending:")) return { label: "Scan pending", tone: "neutral" };
  if (result === "clean") return { label: "Clean", tone: "good" };
  if (result === "malicious") return { label: "Malicious", tone: "bad" };
  if (result === "suspicious") return { label: "Suspicious", tone: "warn" };
  if (result === "scan_failed") return { label: "Scan failed", tone: "warn" };
  return { label: result, tone: "neutral" };
}

export default function FileVault({ token, onUnauthorized }: Props) {
  const [files, setFiles] = useState<VaultFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  // an expired token logs the user out; anything else is shown on the page
  const handleError = useCallback(
    (err: unknown) => {
      if (err instanceof ApiError && err.status === 401) onUnauthorized();
      else setError(err instanceof Error ? err.message : "Something went wrong");
    },
    [onUnauthorized],
  );

  const refresh = useCallback(async () => {
    try {
      setFiles(await listFiles(token));
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }, [token, handleError]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleUpload = async (event: FormEvent) => {
    event.preventDefault();
    const file = fileInput.current?.files?.[0];
    if (!file) return;

    setError(null);
    setMessage(null);
    if (file.size > MAX_SIZE) {
      setError("File too large. Max size is 10MB");
      return;
    }

    setUploading(true);
    try {
      const uploaded = await uploadFile(token, file);
      setMessage(`Uploaded ${uploaded.filename}`);
      if (fileInput.current) fileInput.current.value = "";
      await refresh();
    } catch (err) {
      handleError(err);
    } finally {
      setUploading(false);
    }
  };

  const handleDownload = async (file: VaultFile) => {
    setError(null);
    setBusyId(file.id);
    try {
      const blob = await downloadFile(token, file.id);
      // hand the bytes to the browser through a temporary link
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = file.filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      handleError(err);
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (file: VaultFile) => {
    if (!window.confirm(`Delete ${file.filename}? This can't be undone.`)) return;
    setError(null);
    setMessage(null);
    setBusyId(file.id);
    try {
      await deleteFile(token, file.id);
      setFiles((current) => current.filter((f) => f.id !== file.id));
      setMessage(`Deleted ${file.filename}`);
    } catch (err) {
      handleError(err);
    } finally {
      setBusyId(null);
    }
  };

  const handleScan = async (file: VaultFile) => {
    setError(null);
    setMessage(null);
    setBusyId(file.id);
    try {
      const { scan_result } = await checkScan(token, file.id);
      if (scan_result === "scanning in progress") {
        setMessage(`VirusTotal is still scanning ${file.filename}. Try again in a minute.`);
      } else {
        setFiles((current) => current.map((f) => (f.id === file.id ? { ...f, virustotal_result: scan_result } : f)));
      }
    } catch (err) {
      handleError(err);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <main>
      <form className="card upload" onSubmit={handleUpload}>
        <label>
          Upload a file
          <input ref={fileInput} type="file" required />
        </label>
        <button type="submit" disabled={uploading}>
          {uploading ? "Uploading…" : "Upload"}
        </button>
        <p className="hint">Up to 10MB. Every upload is sent to VirusTotal for a malware scan.</p>
      </form>

      {error && <p className="banner error">{error}</p>}
      {message && <p className="banner info">{message}</p>}

      <section className="card">
        <h2>Your files</h2>
        {loading ? (
          <p className="hint">Loading…</p>
        ) : files.length === 0 ? (
          <p className="hint">No files yet. Upload one above.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Size</th>
                  <th>Uploaded</th>
                  <th>Scan</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {files.map((file) => {
                  const status = scanStatus(file.virustotal_result);
                  const busy = busyId === file.id;
                  return (
                    <tr key={file.id}>
                      <td className="filename">{file.filename}</td>
                      <td>{formatSize(file.size)}</td>
                      <td>{formatDate(file.upload_time)}</td>
                      <td>
                        <span className={`badge ${status.tone}`}>{status.label}</span>
                      </td>
                      <td className="actions">
                        {file.virustotal_result?.startsWith("pending:") && (
                          <button className="secondary" disabled={busy} onClick={() => handleScan(file)}>
                            Check scan
                          </button>
                        )}
                        <button className="secondary" disabled={busy} onClick={() => handleDownload(file)}>
                          Download
                        </button>
                        <button className="danger" disabled={busy} onClick={() => handleDelete(file)}>
                          Delete
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
