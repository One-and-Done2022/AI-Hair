function findById(items, id) {
  if (!id) {
    return null;
  }
  return (items || []).find((item) => item.id === id) || null;
}

function resolveDetectedHairColor(upload) {
  if (!upload || !upload.detected_hair_color || !upload.detected_hair_color.tone_id) {
    return null;
  }
  return upload.detected_hair_color;
}

function resolveHairColorSelection({
  hairColors = [],
  hairColorTechniques = [],
  draft = {},
  hairstyle = null,
  upload = null
} = {}) {
  const detectedHairColor = resolveDetectedHairColor(upload);
  const tone =
    findById(hairColors, draft.hair_color_tone) ||
    findById(hairColors, detectedHairColor && detectedHairColor.tone_id) ||
    findById(hairColors, hairstyle && hairstyle.default_hair_color_tone) ||
    hairColors[0] ||
    null;

  const allowedTechniqueIds = tone ? (tone.allowed_techniques || []) : [];
  const techniqueOptions = (hairColorTechniques || []).filter((item) => {
    return !allowedTechniqueIds.length || allowedTechniqueIds.includes(item.id);
  });
  const technique =
    findById(techniqueOptions, draft.hair_color_technique) ||
    findById(techniqueOptions, tone && tone.default_technique) ||
    techniqueOptions[0] ||
    null;

  return {
    detectedHairColor,
    tone,
    technique,
    techniqueOptions
  };
}

function normalizeKeyword(value) {
  return String(value || "").trim().toLowerCase();
}

function filterProfessionalHairColors({
  professionalColors = [],
  selectedSeries = "all",
  keyword = "",
  recommendedOnly = true
} = {}) {
  const normalizedKeyword = normalizeKeyword(keyword);
  return (professionalColors || []).filter((item) => {
    if (recommendedOnly && !item.is_recommended_for_generation) {
      return false;
    }
    if (selectedSeries && selectedSeries !== "all" && item.series_type !== selectedSeries) {
      return false;
    }
    if (!normalizedKeyword) {
      return true;
    }
    const haystack = [
      item.code,
      item.label,
      item.series_name,
      item.visual_note,
      item.mapped_tone_label,
      ...(item.keywords || [])
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(normalizedKeyword);
  });
}

function resolveProfessionalHairColor({ professionalColors = [], draft = {} } = {}) {
  return findById(professionalColors, draft.hair_color_professional_id);
}

function buildTechniqueOptions(hairColorTechniques = [], tone = null) {
  const allowedTechniqueIds = tone ? (tone.allowed_techniques || []) : [];
  return (hairColorTechniques || []).filter((item) => {
    return !allowedTechniqueIds.length || allowedTechniqueIds.includes(item.id);
  });
}

function resolveProfessionalMappedSelection({
  professionalColor = null,
  hairColors = [],
  hairColorTechniques = [],
  currentTechnique = null
} = {}) {
  if (!professionalColor) {
    return {
      professionalColor: null,
      tone: null,
      technique: null,
      techniqueOptions: []
    };
  }
  const tone =
    findById(hairColors, professionalColor.mapped_tone_id) ||
    hairColors[0] ||
    null;
  const techniqueOptions = buildTechniqueOptions(hairColorTechniques, tone);
  const preferredTechniqueIds = [];
  if (currentTechnique && currentTechnique.id) {
    preferredTechniqueIds.push(currentTechnique.id);
  }
  preferredTechniqueIds.push(...(professionalColor.mapped_technique_ids || []));
  if (tone && tone.default_technique) {
    preferredTechniqueIds.push(tone.default_technique);
  }
  let technique = null;
  preferredTechniqueIds.some((id) => {
    const candidate = findById(techniqueOptions, id);
    if (candidate) {
      technique = candidate;
      return true;
    }
    return false;
  });
  if (!technique) {
    technique = techniqueOptions[0] || null;
  }
  return {
    professionalColor,
    tone,
    technique,
    techniqueOptions
  };
}

function shouldClearProfessionalColor(professionalColor, tone, technique) {
  if (!professionalColor) {
    return false;
  }
  if (tone && professionalColor.mapped_tone_id && professionalColor.mapped_tone_id !== tone.id) {
    return true;
  }
  if (
    technique &&
    professionalColor.mapped_technique_ids &&
    professionalColor.mapped_technique_ids.length &&
    !professionalColor.mapped_technique_ids.includes(technique.id)
  ) {
    return true;
  }
  return false;
}

module.exports = {
  buildTechniqueOptions,
  filterProfessionalHairColors,
  findHairColorById: findById,
  findProfessionalHairColorById: findById,
  resolveDetectedHairColor,
  resolveHairColorSelection,
  resolveProfessionalHairColor,
  resolveProfessionalMappedSelection,
  shouldClearProfessionalColor
};
