import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, renderUrl, sourceUrl } from "../api";
import type { CropParams, Job } from "../types";

const emptyCrop = (duration: number): CropParams => ({
  start: 0,
  end: Math.min(duration || 8, 59),
  focus_x: 0.5,
  focus_y: 0.5,
  zoom: 1,
});

export default function Editor() {
  const { id } = useParams<{ id: string }>();
  const videoRef = useRef<HTMLVideoElement>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [crop, setCrop] = useState<CropParams>(emptyCrop(8));
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    if (!id) return;
    const j = await api.job(id);
    setJob(j);
    if (j.crop) setCrop(j.crop);
    else setCrop(emptyCrop(j.asset?.duration_sec ?? 8));
  }

  useEffect(() => {
    load().catch((e) => setErr(String(e.message || e)));
    const t = setInterval(() => {
      if (!id) return;
      api.job(id).then(setJob).catch(() => undefined);
    }, 2000);
    return () => clearInterval(t);
  }, [id]);

  function set<K extends keyof CropParams>(key: K, value: number) {
    setCrop((c) => ({ ...c, [key]: value }));
  }

  function onTime() {
    const v = videoRef.current;
    if (!v) return;
    if (v.currentTime < crop.start) v.currentTime = crop.start;
    if (v.currentTime > crop.end) {
      v.currentTime = crop.start;
      v.pause();
    }
  }

  async function confirm() {
    if (!id) return;
    setBusy(true);
    setErr("");
    try {
      const next = await api.confirm(id, crop);
      setJob(next);
      setMsg("已确认裁剪。后台将烧英文字幕 + 配乐，并上传 YouTube 私密草稿。");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "确认失败");
    } finally {
      setBusy(false);
    }
  }

  async function publish() {
    if (!id) return;
    setBusy(true);
    try {
      setJob(await api.publish(id));
      setMsg("已请求公开该草稿。");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "发布失败");
    } finally {
      setBusy(false);
    }
  }

  async function retry() {
    if (!id) return;
    setBusy(true);
    try {
      setJob(await api.retry(id));
      setMsg("已从当前阶段重试（不会回到待裁剪）。");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "重试失败");
    } finally {
      setBusy(false);
    }
  }

  if (!job || !id) {
    return (
      <div className="page">
        <p className="meta">{err || "加载中…"}</p>
      </div>
    );
  }

  const canEdit = job.stage === "NEW" || job.stage === "CROP_CONFIRMED";
  const duration = job.asset?.duration_sec ?? crop.end;

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand">
          <h1>裁剪确认</h1>
          <span className="en">{job.asset?.filename}</span>
        </div>
        <Link className="btn ghost" to="/">
          返回列表
        </Link>
      </header>

      <div className="editor">
        <div className="card">
          <div className="phone">
            <video
              ref={videoRef}
              src={sourceUrl(id)}
              controls
              playsInline
              onTimeUpdate={onTime}
              onLoadedMetadata={(e) => {
                const d = e.currentTarget.duration;
                if (!job.crop) setCrop((c) => ({ ...c, end: Math.min(d, 59) }));
              }}
            />
          </div>
          {job.has_render && (
            <p className="meta" style={{ marginTop: 12 }}>
              成片预览：
              <a href={renderUrl(id)} target="_blank" rel="noreferrer">
                打开渲染结果
              </a>
            </p>
          )}
        </div>

        <div className="card">
          <p className="meta">
            阶段 <span className="stage">{job.stage}</span> · {job.status}
            {job.youtube_video_id && (
              <>
                <br />
                YouTube {job.youtube_video_id} / {job.youtube_privacy} / {job.youtube_mode}
              </>
            )}
          </p>

          <div className="field">
            <label>开始 {crop.start.toFixed(1)}s</label>
            <input
              type="range"
              min={0}
              max={Math.max(0.1, duration - 0.2)}
              step={0.1}
              value={crop.start}
              disabled={!canEdit}
              onChange={(e) => set("start", Number(e.target.value))}
            />
          </div>
          <div className="field">
            <label>结束 {crop.end.toFixed(1)}s（成片 ≤ 59s）</label>
            <input
              type="range"
              min={crop.start + 0.2}
              max={duration}
              step={0.1}
              value={Math.min(crop.end, duration)}
              disabled={!canEdit}
              onChange={(e) => set("end", Number(e.target.value))}
            />
          </div>
          <div className="field">
            <label>横向取景 {crop.focus_x.toFixed(2)}</label>
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={crop.focus_x}
              disabled={!canEdit}
              onChange={(e) => set("focus_x", Number(e.target.value))}
            />
          </div>
          <div className="field">
            <label>纵向取景 {crop.focus_y.toFixed(2)}</label>
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={crop.focus_y}
              disabled={!canEdit}
              onChange={(e) => set("focus_y", Number(e.target.value))}
            />
          </div>
          <div className="field">
            <label>放大 {crop.zoom.toFixed(2)}×</label>
            <input
              type="range"
              min={1}
              max={2.5}
              step={0.05}
              value={crop.zoom}
              disabled={!canEdit}
              onChange={(e) => set("zoom", Number(e.target.value))}
            />
          </div>

          <p className="meta">
            确认后自动：竖屏 1080×1920 渲染 · 烧入 3–6 句英文字幕 · 铺 CC0 配乐 ·
            技术检查 · 上传 YouTube <b>私密草稿</b>。公开必须再点一次按钮。
          </p>

          {msg && <p className="ok">{msg}</p>}
          {err && <p className="err">{err}</p>}
          {job.error_message && <p className="err">{job.error_message}</p>}

          <div className="row-actions">
            {canEdit && (
              <button className="btn clay" disabled={busy} onClick={confirm}>
                确认裁剪并生成
              </button>
            )}
            {job.stage === "DRAFT" && (
              <button className="btn moss" disabled={busy} onClick={publish}>
                将此草稿设为公开
              </button>
            )}
            {job.status === "failed" && (
              <button className="btn gold" disabled={busy} onClick={retry}>
                从当前阶段重试
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
