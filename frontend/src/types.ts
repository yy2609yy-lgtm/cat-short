export type Asset = {
  id: string;
  source: string;
  source_key: string;
  filename: string;
  mime: string;
  size_bytes: number;
  duration_sec: number | null;
  width: number | null;
  height: number | null;
  created_at: string;
};

export type CropParams = {
  start: number;
  end: number;
  focus_x: number;
  focus_y: number;
  zoom: number;
};

export type Job = {
  id: string;
  asset_id: string;
  stage: string;
  status: string;
  crop: CropParams | null;
  crop_fingerprint: string | null;
  has_render: boolean;
  youtube_video_id: string | null;
  youtube_privacy: string | null;
  youtube_mode: string | null;
  error_message: string | null;
  attempt: number;
  check_report: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  asset: Asset | null;
};

export type AppSettings = {
  drive_mode: string;
  youtube_mode: string;
  render_max_seconds: number;
  render_width: number;
  render_height: number;
  render_fps: number;
  admin_username: string;
};

export type SyncStatus = {
  drive_mode: string;
  last_sync_at: string | null;
  last_error: string | null;
  last_result: { ingested?: number; skipped?: number; errors?: string[] } | null;
};
