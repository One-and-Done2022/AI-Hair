const {
  clearRecommendationCache,
  getCurrentImagePath,
  setCurrentImagePath
} = require("./recommendation");

function readCreationDraft() {
  const selection = wx.getStorageSync("templateSelection") || {};
  const options = wx.getStorageSync("generationOptions") || {};
  const hairstyle = selection.hairstyle || null;
  const scene = selection.scene || null;

  return {
    imagePath: getCurrentImagePath(),
    hairstyle,
    scene,
    gender:
      selection.gender ||
      (hairstyle && hairstyle.gender) ||
      "",
    generator_backend: options.generator_backend || "",
    aspect_ratio: options.aspect_ratio || "",
    resolution: options.resolution || "",
    hair_color_tone: options.hair_color_tone || "",
    hair_color_tone_label: options.hair_color_tone_label || "",
    hair_color_technique: options.hair_color_technique || "",
    hair_color_technique_label: options.hair_color_technique_label || "",
    hair_color_selection_mode: options.hair_color_selection_mode || "basic",
    hair_color_professional_id: options.hair_color_professional_id || "",
    hair_color_professional_brand: options.hair_color_professional_brand || "",
    hair_color_professional_series: options.hair_color_professional_series || "",
    hair_color_professional_series_label: options.hair_color_professional_series_label || "",
    hair_color_professional_code: options.hair_color_professional_code || "",
    hair_color_professional_note: options.hair_color_professional_note || "",
    hair_color_professional_hex_estimate: options.hair_color_professional_hex_estimate || ""
  };
}

function writeCreationDraft(draft = {}) {
  const nextDraft = {
    imagePath: draft.imagePath || "",
    hairstyle: draft.hairstyle || null,
    scene: draft.scene || null,
    gender:
      draft.gender ||
      (draft.hairstyle && draft.hairstyle.gender) ||
      "",
    generator_backend: draft.generator_backend || "",
    aspect_ratio: draft.aspect_ratio || "",
    resolution: draft.resolution || "",
    hair_color_tone: draft.hair_color_tone || "",
    hair_color_tone_label: draft.hair_color_tone_label || "",
    hair_color_technique: draft.hair_color_technique || "",
    hair_color_technique_label: draft.hair_color_technique_label || "",
    hair_color_selection_mode: draft.hair_color_selection_mode || "basic",
    hair_color_professional_id: draft.hair_color_professional_id || "",
    hair_color_professional_brand: draft.hair_color_professional_brand || "",
    hair_color_professional_series: draft.hair_color_professional_series || "",
    hair_color_professional_series_label: draft.hair_color_professional_series_label || "",
    hair_color_professional_code: draft.hair_color_professional_code || "",
    hair_color_professional_note: draft.hair_color_professional_note || "",
    hair_color_professional_hex_estimate: draft.hair_color_professional_hex_estimate || ""
  };

  if (nextDraft.imagePath) {
    setCurrentImagePath(nextDraft.imagePath);
  } else {
    setCurrentImagePath("");
  }

  wx.setStorageSync("templateSelection", {
    hairstyle: nextDraft.hairstyle,
    scene: nextDraft.scene,
    gender: nextDraft.gender
  });
  wx.setStorageSync("generationOptions", {
    generator_backend: nextDraft.generator_backend,
    aspect_ratio: nextDraft.aspect_ratio,
    resolution: nextDraft.resolution,
    hair_color_tone: nextDraft.hair_color_tone,
    hair_color_tone_label: nextDraft.hair_color_tone_label,
    hair_color_technique: nextDraft.hair_color_technique,
    hair_color_technique_label: nextDraft.hair_color_technique_label,
    hair_color_selection_mode: nextDraft.hair_color_selection_mode,
    hair_color_professional_id: nextDraft.hair_color_professional_id,
    hair_color_professional_brand: nextDraft.hair_color_professional_brand,
    hair_color_professional_series: nextDraft.hair_color_professional_series,
    hair_color_professional_series_label: nextDraft.hair_color_professional_series_label,
    hair_color_professional_code: nextDraft.hair_color_professional_code,
    hair_color_professional_note: nextDraft.hair_color_professional_note,
    hair_color_professional_hex_estimate: nextDraft.hair_color_professional_hex_estimate
  });

  return nextDraft;
}

function updateCreationDraft(patch = {}) {
  const current = readCreationDraft();
  return writeCreationDraft({
    ...current,
    ...patch
  });
}

function resetCreationDraft() {
  wx.removeStorageSync("templateSelection");
  wx.removeStorageSync("generationOptions");
  clearRecommendationCache();
}

module.exports = {
  readCreationDraft,
  writeCreationDraft,
  updateCreationDraft,
  resetCreationDraft
};
