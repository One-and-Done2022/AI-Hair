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

module.exports = {
  findHairColorById: findById,
  resolveDetectedHairColor,
  resolveHairColorSelection
};
