const PENDING_HISTORY_STORAGE_KEY = "pendingHistoryJobs";

const ACTIVE_PENDING_STATUSES = new Set([
  "pending",
  "hair_generating",
  "hair_ready",
  "scene_generating",
  "scene_partial",
  "preview_ready"
]);

function parseTimestamp(value) {
  if (!value) {
    return 0;
  }
  const normalized = String(value).replace(/\+00:00$/, "Z");
  const timestamp = Date.parse(normalized);
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function sortByCreatedAtDesc(items) {
  return (items || []).slice().sort((left, right) => {
    return parseTimestamp(right.created_at) - parseTimestamp(left.created_at);
  });
}

function isPendingStatus(status) {
  return ACTIVE_PENDING_STATUSES.has(status || "");
}

function normalizePendingJob(job = {}) {
  if (!job || !job.job_id) {
    return null;
  }

  const resultImageUrls = Array.isArray(job.result_image_urls)
    ? job.result_image_urls.filter(Boolean)
    : [];
  const hairPreviewUrl = job.hair_preview_url || "";
  const resultImageUrl =
    job.result_image_url ||
    resultImageUrls[0] ||
    hairPreviewUrl ||
    "";

  return {
    job_id: job.job_id,
    status: job.status || "pending",
    upload_url: job.upload_url || "",
    hair_preview_url: hairPreviewUrl,
    result_image_url: resultImageUrl,
    result_image_urls: resultImageUrls,
    completed_scene_count: Number(job.completed_scene_count || resultImageUrls.length || 0),
    media_expired: !!job.media_expired,
    media_expires_at: job.media_expires_at || "",
    hairstyle_id: job.hairstyle_id || "",
    hairstyle_name: job.hairstyle_name || "",
    scene_id: job.scene_id || "",
    scene_name: job.scene_name || "",
    generator_backend: job.generator_backend || "",
    error_code: job.error_code || "",
    error_message: job.error_message || "",
    created_at: job.created_at || new Date().toISOString(),
    updated_at: job.updated_at || job.created_at || new Date().toISOString(),
    is_pending_local: true
  };
}

function readPendingHistoryJobs() {
  const stored = wx.getStorageSync(PENDING_HISTORY_STORAGE_KEY);
  if (!Array.isArray(stored)) {
    return [];
  }

  return sortByCreatedAtDesc(
    stored
      .map((item) => normalizePendingJob(item))
      .filter((item) => item && isPendingStatus(item.status))
  );
}

function writePendingHistoryJobs(items) {
  if (!items || !items.length) {
    wx.removeStorageSync(PENDING_HISTORY_STORAGE_KEY);
    return;
  }
  wx.setStorageSync(PENDING_HISTORY_STORAGE_KEY, items);
}

function upsertPendingHistoryJob(job) {
  const normalized = normalizePendingJob(job);
  if (!normalized) {
    return [];
  }

  const nextItems = readPendingHistoryJobs().filter((item) => item.job_id !== normalized.job_id);
  if (isPendingStatus(normalized.status)) {
    nextItems.push(normalized);
  }

  const sorted = sortByCreatedAtDesc(nextItems);
  writePendingHistoryJobs(sorted);
  return sorted;
}

function removePendingHistoryJob(jobId) {
  if (!jobId) {
    return [];
  }
  const nextItems = readPendingHistoryJobs().filter((item) => item.job_id !== jobId);
  writePendingHistoryJobs(nextItems);
  return nextItems;
}

function mergePendingHistoryJobs(serverItems = []) {
  const pendingItems = readPendingHistoryJobs();
  const serverIds = new Set(
    (serverItems || [])
      .map((item) => item && item.job_id)
      .filter(Boolean)
  );
  const retainedPending = pendingItems.filter((item) => !serverIds.has(item.job_id));
  writePendingHistoryJobs(retainedPending);
  return sortByCreatedAtDesc([...(serverItems || []), ...retainedPending]);
}

module.exports = {
  mergePendingHistoryJobs,
  removePendingHistoryJob,
  upsertPendingHistoryJob
};
