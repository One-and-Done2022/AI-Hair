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

const PROFESSIONAL_COLOR_SERIES_ALIASES = {
  base_color: ["基色", "打底色", "底色", "base"],
  classic_cover: ["覆盖", "遮白", "盖白发", "cover"],
  classic_natural: ["常规", "自然棕", "经典自然", "natural"],
  cool_mist: ["冷雾", "烟熏", "灰棕", "冷棕", "高级灰", "mist"],
  icy_gloss: ["冰感", "冷浅色", "冰透", "icy"],
  mist_clear: ["清透", "雾感", "轻透", "clear"],
  tool_color: ["工具色", "校色", "调色", "tool"]
};

const PROFESSIONAL_COLOR_TONE_ALIASES = {
  ash_brown: ["灰棕", "冷灰棕", "雾棕", "烟灰棕"],
  blue_black: ["蓝黑", "冷黑", "雾黑"],
  chestnut_brown: ["栗棕", "奶茶棕", "柔棕"],
  dark_brown: ["深棕", "自然深棕", "原生深棕"],
  honey_brown: ["蜂蜜棕", "暖茶棕", "焦糖棕", "茶棕"],
  linen_blonde: ["亚麻", "亚麻金", "浅金", "米金"],
  natural_black: ["自然黑", "原生黑", "黑色"]
};

const PROFESSIONAL_COLOR_TEMPERATURE_ALIASES = {
  cool: ["冷调", "冷色", "偏冷"],
  neutral: ["中性", "自然", "通用"],
  warm: ["暖调", "暖色", "偏暖"]
};

const PROFESSIONAL_COLOR_DEPTH_ALIASES = {
  deep: ["深色", "深发色", "低明度"],
  medium: ["中等明度", "中发色"],
  light: ["浅色", "高明度", "浅发色"]
};

const PROFESSIONAL_HAIR_COLOR_QUICK_KEYWORDS = [
  "5/72",
  "6/72",
  "奶茶",
  "冷雾",
  "灰棕",
  "亚麻",
  "蓝黑"
];

function normalizeKeyword(value) {
  let normalized = String(value || "");
  if (typeof normalized.normalize === "function") {
    try {
      normalized = normalized.normalize("NFKC");
    } catch (error) {
      normalized = String(value || "");
    }
  }
  return normalized
    .trim()
    .toLowerCase()
    .replace(/[／]/g, "/")
    .replace(/[—–－]/g, "-")
    .replace(/[·•・]/g, " ")
    .replace(/\s+/g, " ");
}

function compactKeyword(value) {
  return normalizeKeyword(value).replace(/[\s/_.,-]/g, "");
}

function dedupeList(items = []) {
  const result = [];
  const seen = new Set();
  (items || []).forEach((item) => {
    const normalized = normalizeKeyword(item);
    if (!normalized || seen.has(normalized)) {
      return;
    }
    seen.add(normalized);
    result.push(normalized);
  });
  return result;
}

function tokenizeSearchFragments(value) {
  return dedupeList(
    normalizeKeyword(value)
      .split(/[\s,，、|/\()（）【】[\]{}<>:：;；]+/)
      .map((item) => item.trim())
      .filter(Boolean)
  );
}

function buildCodeVariants(code) {
  const normalized = normalizeKeyword(code);
  if (!normalized) {
    return [];
  }
  const compact = compactKeyword(normalized);
  const variants = [normalized, compact];
  const parts = normalized.split("/");
  if (parts.length === 2 && parts[0] && parts[1]) {
    variants.push(`${parts[0]}-${parts[1]}`);
    variants.push(`${parts[0]} ${parts[1]}`);
    variants.push(`${parts[0]}／${parts[1]}`);
    variants.push(`${parts[0]}度${parts[1]}`);
  }
  return dedupeList(variants);
}

function addSearchTerms(termSet, compactSet, value) {
  const normalized = normalizeKeyword(value);
  if (!normalized) {
    return;
  }
  termSet.add(normalized);
  const compact = compactKeyword(normalized);
  if (compact) {
    compactSet.add(compact);
  }
  tokenizeSearchFragments(normalized).forEach((token) => {
    termSet.add(token);
    const compactToken = compactKeyword(token);
    if (compactToken) {
      compactSet.add(compactToken);
    }
  });
}

function buildProfessionalColorSearchProfile(item = {}) {
  const termSet = new Set();
  const compactSet = new Set();
  const aliases = []
    .concat(PROFESSIONAL_COLOR_SERIES_ALIASES[item.series_type] || [])
    .concat(PROFESSIONAL_COLOR_TONE_ALIASES[item.mapped_tone_id] || [])
    .concat(PROFESSIONAL_COLOR_TEMPERATURE_ALIASES[item.mapped_temperature] || [])
    .concat(PROFESSIONAL_COLOR_DEPTH_ALIASES[item.mapped_depth_bucket] || []);

  [
    item.code,
    item.label,
    item.brand,
    item.series_name,
    item.series_description,
    item.visual_note,
    item.mapped_tone_label,
    item.prompt_alias,
    ...(item.keywords || []),
    ...buildCodeVariants(item.code),
    ...aliases
  ].forEach((value) => addSearchTerms(termSet, compactSet, value));

  return {
    code: normalizeKeyword(item.code),
    codeCompact: compactKeyword(item.code),
    terms: Array.from(termSet),
    compactTerms: Array.from(compactSet)
  };
}

function professionalColorOrder(left, right) {
  const leftPriority = Number.isFinite(left.display_priority) ? left.display_priority : 9999;
  const rightPriority = Number.isFinite(right.display_priority) ? right.display_priority : 9999;
  if (leftPriority !== rightPriority) {
    return leftPriority - rightPriority;
  }
  return String(left.code || "").localeCompare(String(right.code || ""));
}

function scoreProfessionalColor(item, keyword) {
  const normalizedKeyword = normalizeKeyword(keyword);
  if (!normalizedKeyword) {
    return 1;
  }

  const keywordCompact = compactKeyword(normalizedKeyword);
  const queryTokens = tokenizeSearchFragments(normalizedKeyword);
  const profile = buildProfessionalColorSearchProfile(item);
  let score = 0;

  if (normalizedKeyword === profile.code) {
    score += 520;
  } else if (keywordCompact && keywordCompact === profile.codeCompact) {
    score += 500;
  } else if (profile.terms.includes(normalizedKeyword)) {
    score += 380;
  } else if (keywordCompact && profile.compactTerms.includes(keywordCompact)) {
    score += 340;
  } else if (
    profile.code.indexOf(normalizedKeyword) >= 0 ||
    (keywordCompact && profile.codeCompact.indexOf(keywordCompact) >= 0)
  ) {
    score += 280;
  } else if (
    profile.terms.some((term) => term.indexOf(normalizedKeyword) >= 0) ||
    (keywordCompact && profile.compactTerms.some((term) => term.indexOf(keywordCompact) >= 0))
  ) {
    score += 220;
  }

  const matchedAllTokens = queryTokens.every((token) => {
    const tokenCompact = compactKeyword(token);
    if (token === profile.code || (tokenCompact && tokenCompact === profile.codeCompact)) {
      score += 90;
      return true;
    }
    if (profile.terms.includes(token) || (tokenCompact && profile.compactTerms.includes(tokenCompact))) {
      score += 70;
      return true;
    }
    if (
      profile.terms.some((term) => term.indexOf(token) >= 0) ||
      (tokenCompact && profile.compactTerms.some((term) => term.indexOf(tokenCompact) >= 0))
    ) {
      score += 48;
      return true;
    }
    return false;
  });

  return matchedAllTokens ? score : 0;
}

function searchProfessionalHairColors({
  professionalColors = [],
  selectedSeries = "all",
  keyword = "",
  recommendedOnly = true
} = {}) {
  const normalizedKeyword = normalizeKeyword(keyword);
  const usesGlobalSearch = !!normalizedKeyword;
  const scopedItems = (professionalColors || []).filter((item) => {
    if (recommendedOnly && !item.is_recommended_for_generation) {
      return false;
    }
    if (!usesGlobalSearch && selectedSeries && selectedSeries !== "all" && item.series_type !== selectedSeries) {
      return false;
    }
    return true;
  });

  if (!normalizedKeyword) {
    const orderedItems = scopedItems.slice().sort(professionalColorOrder);
    return {
      items: orderedItems,
      matchedCount: orderedItems.length,
      recommendedCount: orderedItems.filter((item) => item.is_recommended_for_generation).length,
      usesGlobalSearch: false
    };
  }

  const matchedItems = scopedItems
    .map((item) => ({
      item,
      score: scoreProfessionalColor(item, normalizedKeyword)
    }))
    .filter((item) => item.score > 0)
    .sort((left, right) => {
      if (right.score !== left.score) {
        return right.score - left.score;
      }
      if (left.item.is_recommended_for_generation !== right.item.is_recommended_for_generation) {
        return left.item.is_recommended_for_generation ? -1 : 1;
      }
      return professionalColorOrder(left.item, right.item);
    })
    .map((item) => item.item);

  return {
    items: matchedItems,
    matchedCount: matchedItems.length,
    recommendedCount: matchedItems.filter((item) => item.is_recommended_for_generation).length,
    usesGlobalSearch: true
  };
}

function filterProfessionalHairColors({
  professionalColors = [],
  selectedSeries = "all",
  keyword = "",
  recommendedOnly = true
} = {}) {
  return searchProfessionalHairColors({
    professionalColors,
    selectedSeries,
    keyword,
    recommendedOnly
  }).items;
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
  PROFESSIONAL_HAIR_COLOR_QUICK_KEYWORDS,
  buildTechniqueOptions,
  filterProfessionalHairColors,
  findHairColorById: findById,
  findProfessionalHairColorById: findById,
  resolveDetectedHairColor,
  resolveHairColorSelection,
  resolveProfessionalHairColor,
  resolveProfessionalMappedSelection,
  searchProfessionalHairColors,
  shouldClearProfessionalColor
};
