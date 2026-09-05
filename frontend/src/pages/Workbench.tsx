import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, setToken } from "../api";
import type { AppSettings, Job, SyncStatus } from "../types";

const STAGE_LABEL: Record<string, string> = {
  NEW: "待裁剪",
  CROP_CONFIRMED: "已确认，排队渲染",
  RENDERING: "渲染中",
  RENDERED: "已渲染",
  CHECKING: "技术检查",
  CHECKED: "检查通过",
  UPLOADING: "上传草稿",
  DRAFT: "YouTube 私密草稿",
  PUBLISHING: "发布中",
  PUBLIC: "已公开",
};

function stageClass(job: Job) {
  if (job.status === "failed") return "stage bad";
  if (job.stage === "PUBLIC" || job.stage === "DRAFT") return "stage ok";
  return "stage";
}

export default function Workbench() {
  const nav = useNavigate();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [sync, setSync] = useState<SyncStatus | null>(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const [j, s, st] = await Promise.all([api.jobs(), api.settings(), api.syncStatus()]);
    setJobs(j);
    setSettings(s);
    setSync(st);
  }

  useEffect(() => {
    refresh().catch((e) => setErr(String(e.message || e)));
    const t = setInterval(() => {
      api.jobs().then(setJobs).catch(() => undefined);
      api.syncStatus().then(setSync).catch(() => undefined);
    }, 2500);
    return () => clearInterval(t);
  }, []);

  async function doSync() {
    setBusy(true);
    setErr("");
    try {
      const r = await api.syncNow();
      setMsg(`同步完成：新增 ${r.ingested}，跳过 ${r.skipped}`);
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "同步失败");
    } finally {
      setBusy(false);
    }
  }

  async function onUpload(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setErr("");
    try {
      const job = await api.upload(file);
      setMsg(`已入库：${job.asset?.filename}`);
      await refresh();
      nav(`/jobs/${job.id}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "上传失败");
    } finally {
      setBusy(false);
    }
  }

  async function publish(id: string) {
    setBusy(true);
    try {
      await api.publish(id);
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "发布失败");
    } finally {
      setBusy(false);
    }
  }

  async function retry(id: string) {
    setBusy(true);
    try {
      await api.retry(id);
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "重试失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand">
          <h1>猫咪短视频工作台</h1>
          <span className="en">Cat Shorts Workbench</span>
        </div>
        <div className="pills">
          <span className="pill">Drive {settings?.drive_mode === "live" ? "正式" : "模拟"}</span>
          <span className="pill">YouTube {settings?.youtube_mode === "live" ? "正式" : "模拟"}</span>
          <span className="pill">
            {settings?.render_width}×{settings?.render_height} · {settings?.render_fps}fps · ≤
            {settings?.render_max_seconds}s
          </span>
          <button className="btn ghost" onClick={() => { setToken(null); nav("/login"); }}>
            退出
          </button>
        </div>
      </header>

      <div className="toolbar">
        <button className="btn" disabled={busy} onClick={doSync}>
          同步素材（Drive / 收件箱）
        </button>
        <label className="btn ghost" style={{ cursor: "pointer" }}>
          上传本地演示视频
          <input
            type="file"
            accept="video/*"
            hidden
            onChange={(e) => onUpload(e.target.files?.[0])}
          />
        </label>
        {sync?.last_sync_at && (
          <span className="meta">上次同步 {new Date(sync.last_sync_at).toLocaleString()}</span>
        )}
      </div>
      {msg && <p className="ok">{msg}</p>}
      {err && <p className="err">{err}</p>}
      {sync?.last_error && <p className="err">同步备注：{sync.last_error}</p>}

      {jobs.length === 0 ? (
        <div className="card empty">
          还没有任务。把手机视频放到收件箱（默认 <code>/data/inbox</code>）后点同步，
          或直接上传本地演示视频。Compose 启动时会放入一条 <code>sample-cat.mp4</code>。
        </div>
      ) : (
        <div className="grid">
          {jobs.map((job) => (
            <article className="card job-card" key={job.id}>
              <h3>{job.asset?.filename ?? job.id}</h3>
              <div className="meta">
                <span className={stageClass(job)}>
                  {STAGE_LABEL[job.stage] ?? job.stage} · {job.status}
                </span>
                <div>
                  {job.asset?.width}×{job.asset?.height} · {job.asset?.duration_sec?.toFixed(1)}s ·{" "}
                  {job.asset?.source}
                </div>
                {job.youtube_video_id && (
                  <div>
                    YT：{job.youtube_video_id}（{job.youtube_privacy} / {job.youtube_mode}）
                  </div>
                )}
                {job.error_message && <div className="err">{job.error_message}</div>}
              </div>
              <div className="row-actions">
                <Link className="btn" to={`/jobs/${job.id}`}>
                  {job.stage === "NEW" ? "裁剪确认" : "打开"}
                </Link>
                {job.stage === "DRAFT" && (
                  <button className="btn moss" disabled={busy} onClick={() => publish(job.id)}>
                    发布公开
                  </button>
                )}
                {job.status === "failed" && (
                  <button className="btn gold" disabled={busy} onClick={() => retry(job.id)}>
                    从当前阶段重试
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
