function getLegacyHairstyles(catalog = {}) {
  return Array.isArray(catalog.hairstyles) ? catalog.hairstyles : [];
}

function getMalePresetHairstyles(catalog = {}) {
  return Array.isArray(catalog.hairstyle_presets_male)
    ? catalog.hairstyle_presets_male
    : [];
}

function getSelectableHairstyles(catalog = {}) {
  const femaleAndLegacy = getLegacyHairstyles(catalog).filter((item) => item.gender !== "male");
  return getMalePresetHairstyles(catalog).concat(femaleAndLegacy);
}

function getAllHairstyles(catalog = {}) {
  return getMalePresetHairstyles(catalog).concat(getLegacyHairstyles(catalog));
}

function buildCandidateIds(selection) {
  if (!selection) {
    return [];
  }
  if (typeof selection === "string") {
    return selection ? [selection] : [];
  }
  return [
    selection.preset_id,
    selection.id,
    selection.hairstyle_id,
    selection.resolved_hairstyle_id,
    selection.source_hairstyle_id
  ].filter(Boolean);
}

function findCatalogHairstyle(catalog = {}, selection = null) {
  const items = getAllHairstyles(catalog);
  const candidateIds = buildCandidateIds(selection);
  for (let i = 0; i < candidateIds.length; i += 1) {
    const matched = items.find((item) => item.id === candidateIds[i]);
    if (matched) {
      return matched;
    }
  }
  return null;
}

function isMalePresetHairstyle(item) {
  return !!(item && (item.preset_id || item.selection_source === "male_preset"));
}

function buildJobCreatePayload({
  uploadId,
  hairstyle,
  scene,
  generatorBackend,
  aspectRatio,
  resolution,
  hairColorTone,
  hairColorTechnique,
  hairColorProfessionalId
} = {}) {
  const payload = {
    upload_id: uploadId,
    scene_id: scene && scene.id ? scene.id : "",
    generator_backend: generatorBackend,
    aspect_ratio: aspectRatio,
    resolution: resolution || null,
    hair_color_tone: hairColorTone || null,
    hair_color_technique: hairColorTechnique || null,
    hair_color_professional_id: hairColorProfessionalId || null
  };

  if (isMalePresetHairstyle(hairstyle)) {
    payload.preset_id = hairstyle.preset_id || hairstyle.id;
  } else {
    payload.hairstyle_id = hairstyle && hairstyle.id ? hairstyle.id : "";
  }

  return payload;
}

module.exports = {
  buildJobCreatePayload,
  findCatalogHairstyle,
  getAllHairstyles,
  getMalePresetHairstyles,
  getSelectableHairstyles,
  isMalePresetHairstyle
};
