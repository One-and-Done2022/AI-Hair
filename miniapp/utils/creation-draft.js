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
    resolution: options.resolution || ""
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
    resolution: draft.resolution || ""
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
    resolution: nextDraft.resolution
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
